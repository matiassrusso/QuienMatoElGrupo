"""Llamadas a proveedores de LLM externos usando la API key que trae el usuario (BYOK)."""
from __future__ import annotations

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
