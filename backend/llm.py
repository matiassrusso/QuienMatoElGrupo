"""Llamadas a proveedores de LLM externos usando la API key que trae el usuario (BYOK)."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash-lite",
    "groq": "llama-3.3-70b-versatile",
}


class LLMError(Exception):
    pass


def _extract_error_message(response: httpx.Response) -> str | None:
    try:
        return response.json().get("error", {}).get("message")
    except Exception:
        return None


async def call_llm(provider: str, api_key: str, model: str | None, system_prompt: str, user_prompt: str) -> str:
    resolved_model = model or DEFAULT_MODELS.get(provider)
    if resolved_model is None:
        raise LLMError(f"Proveedor de IA desconocido: {provider}")

    if provider == "anthropic":
        return await _call_anthropic(api_key, resolved_model, system_prompt, user_prompt)
    if provider == "openai":
        return await _call_openai_compatible(
            "https://api.openai.com/v1/chat/completions", "OpenAI", api_key, resolved_model, system_prompt, user_prompt
        )
    if provider == "groq":
        return await _call_openai_compatible(
            "https://api.groq.com/openai/v1/chat/completions", "Groq", api_key, resolved_model, system_prompt, user_prompt
        )
    if provider == "gemini":
        return await _call_gemini(api_key, resolved_model, system_prompt, user_prompt)
    raise LLMError(f"Proveedor de IA desconocido: {provider}")


async def _call_anthropic(api_key: str, model: str, system_prompt: str, user_prompt: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 400,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                },
            )
        except httpx.HTTPError as exc:
            raise LLMError("No se pudo contactar a Anthropic.") from exc

    if response.status_code == 401:
        raise LLMError("La API key de Anthropic no es valida.")
    if response.status_code >= 400:
        detail = _extract_error_message(response)
        suffix = f": {detail}" if detail else "."
        raise LLMError(f"Anthropic devolvio un error ({response.status_code}){suffix}")

    data = response.json()
    return "".join(block.get("text", "") for block in data.get("content", [])).strip()


async def _call_openai_compatible(
    endpoint: str, label: str, api_key: str, model: str, system_prompt: str, user_prompt: str
) -> str:
    """OpenAI/Groq comparten el mismo formato de request y response (chat completions)."""
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 400,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
        except httpx.HTTPError as exc:
            raise LLMError(f"No se pudo contactar a {label}.") from exc

    if response.status_code == 401:
        raise LLMError(f"La API key de {label} no es valida.")
    if response.status_code >= 400:
        detail = _extract_error_message(response)
        suffix = f": {detail}" if detail else "."
        raise LLMError(f"{label} devolvio un error ({response.status_code}){suffix}")

    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


async def _call_gemini(api_key: str, model: str, system_prompt: str, user_prompt: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": api_key},
                headers={"content-type": "application/json"},
                json={
                    "system_instruction": {"parts": [{"text": system_prompt}]},
                    "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                    "generationConfig": {"maxOutputTokens": 400},
                },
            )
        except httpx.HTTPError as exc:
            raise LLMError("No se pudo contactar a Gemini.") from exc

    if response.status_code >= 400:
        detail = _extract_error_message(response)
        if detail and "api key" in detail.lower():
            raise LLMError("La API key de Gemini no es valida.")
        suffix = f": {detail}" if detail else "."
        raise LLMError(f"Gemini devolvio un error ({response.status_code}){suffix}")

    data = response.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise LLMError("Gemini no devolvio ninguna respuesta (puede haber bloqueado el contenido).")
    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(part.get("text", "") for part in parts).strip()


# --- Streaming multi-turno (usado por el clon del grupo) ---------------------
#
# Los 4 providers soportan SSE nativamente, asi que no hace falta un fallback
# a respuesta completa para ninguno: Anthropic y Gemini con su propio formato
# de evento, OpenAI/Groq comparten el formato "OpenAI-compatible" de siempre.


async def _raise_for_stream_error(response: httpx.Response, label: str) -> None:
    if response.status_code < 400:
        return
    await response.aread()
    detail = _extract_error_message(response)
    if response.status_code == 401:
        raise LLMError(f"La API key de {label} no es valida.")
    if label == "Gemini" and detail and "api key" in detail.lower():
        raise LLMError("La API key de Gemini no es valida.")
    suffix = f": {detail}" if detail else "."
    raise LLMError(f"{label} devolvio un error ({response.status_code}){suffix}")


async def stream_llm_chat(
    provider: str,
    api_key: str,
    model: str | None,
    system_prompt: str,
    history: list[dict[str, str]],
) -> AsyncIterator[str]:
    """Como call_llm pero con historial multi-turno, devolviendo el texto en
    chunks a medida que el proveedor los va generando (SSE)."""
    resolved_model = model or DEFAULT_MODELS.get(provider)
    if resolved_model is None:
        raise LLMError(f"Proveedor de IA desconocido: {provider}")

    if provider == "anthropic":
        stream = _stream_anthropic(api_key, resolved_model, system_prompt, history)
    elif provider == "openai":
        stream = _stream_openai_compatible(
            "https://api.openai.com/v1/chat/completions", "OpenAI", api_key, resolved_model, system_prompt, history
        )
    elif provider == "groq":
        stream = _stream_openai_compatible(
            "https://api.groq.com/openai/v1/chat/completions", "Groq", api_key, resolved_model, system_prompt, history
        )
    elif provider == "gemini":
        stream = _stream_gemini(api_key, resolved_model, system_prompt, history)
    else:
        raise LLMError(f"Proveedor de IA desconocido: {provider}")

    async for chunk in stream:
        yield chunk


async def _stream_anthropic(
    api_key: str, model: str, system_prompt: str, history: list[dict[str, str]]
) -> AsyncIterator[str]:
    messages = [{"role": item["role"], "content": item["content"]} for item in history]
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={"model": model, "max_tokens": 500, "system": system_prompt, "messages": messages, "stream": True},
            ) as response:
                await _raise_for_stream_error(response, "Anthropic")
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        event = json.loads(line[len("data: "):])
                    except ValueError:
                        continue
                    if event.get("type") != "content_block_delta":
                        continue
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        yield delta["text"]
    except httpx.HTTPError as exc:
        raise LLMError("No se pudo contactar a Anthropic.") from exc


async def _stream_openai_compatible(
    endpoint: str, label: str, api_key: str, model: str, system_prompt: str, history: list[dict[str, str]]
) -> AsyncIterator[str]:
    messages = [{"role": "system", "content": system_prompt}] + [
        {"role": item["role"], "content": item["content"]} for item in history
    ]
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                endpoint,
                headers={"Authorization": f"Bearer {api_key}", "content-type": "application/json"},
                json={"model": model, "max_tokens": 500, "messages": messages, "stream": True},
            ) as response:
                await _raise_for_stream_error(response, label)
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[len("data: "):]
                    if payload == "[DONE]":
                        break
                    try:
                        event = json.loads(payload)
                    except ValueError:
                        continue
                    choices = event.get("choices") or [{}]
                    text = choices[0].get("delta", {}).get("content")
                    if text:
                        yield text
    except httpx.HTTPError as exc:
        raise LLMError(f"No se pudo contactar a {label}.") from exc


async def _stream_gemini(
    api_key: str, model: str, system_prompt: str, history: list[dict[str, str]]
) -> AsyncIterator[str]:
    contents = [
        {"role": "model" if item["role"] == "assistant" else "user", "parts": [{"text": item["content"]}]}
        for item in history
    ]
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent",
                params={"key": api_key, "alt": "sse"},
                headers={"content-type": "application/json"},
                json={
                    "system_instruction": {"parts": [{"text": system_prompt}]},
                    "contents": contents,
                    "generationConfig": {"maxOutputTokens": 500},
                },
            ) as response:
                await _raise_for_stream_error(response, "Gemini")
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        event = json.loads(line[len("data: "):])
                    except ValueError:
                        continue
                    candidates = event.get("candidates") or []
                    if not candidates:
                        continue
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = "".join(part.get("text", "") for part in parts)
                    if text:
                        yield text
    except httpx.HTTPError as exc:
        raise LLMError("No se pudo contactar a Gemini.") from exc
