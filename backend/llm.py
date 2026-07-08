"""Llamadas a proveedores de LLM externos usando la API key que trae el usuario (BYOK)."""
from __future__ import annotations

import httpx

DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
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
        return await _call_openai(api_key, resolved_model, system_prompt, user_prompt)
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


async def _call_openai(api_key: str, model: str, system_prompt: str, user_prompt: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
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
            raise LLMError("No se pudo contactar a OpenAI.") from exc

    if response.status_code == 401:
        raise LLMError("La API key de OpenAI no es valida.")
    if response.status_code >= 400:
        detail = _extract_error_message(response)
        suffix = f": {detail}" if detail else "."
        raise LLMError(f"OpenAI devolvio un error ({response.status_code}){suffix}")

    data = response.json()
    return data["choices"][0]["message"]["content"].strip()
