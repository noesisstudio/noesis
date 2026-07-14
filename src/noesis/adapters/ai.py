"""Adaptadores del cerebro avanzado de Noesis.

El camino rutinario nunca llega aquí: ``nlu.py`` resuelve primero dentro del
proceso. Este módulo permite que el segundo nivel sea un servicio privado
compatible con la API de OpenAI (Ollama, llama.cpp o vLLM) sin añadir SDKs ni
acoplar el producto a un modelo concreto.
"""

from __future__ import annotations

import json
import urllib.request

from .. import config


class CompatibleAIError(RuntimeError):
    """El servicio compatible no respondió con un contrato utilizable."""


# Nombre conservado para no romper imports anteriores.
LocalAIError = CompatibleAIError


def local_available() -> bool:
    return bool(config.LOCAL_AI_BASE_URL and config.LOCAL_AI_MODEL)


def external_available() -> bool:
    return bool(
        config.COMPAT_AI_BASE_URL
        and config.COMPAT_AI_BASE_URL.startswith("https://")
        and config.COMPAT_AI_MODEL
        and config.COMPAT_AI_API_KEY
        and config.COMPAT_AI_LEGAL_NAME
        and config.COMPAT_AI_REGION
    )


def _endpoint(base_url: str) -> str:
    base = base_url.strip().rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _openai_tools(tools: list[dict]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description") or "",
                "parameters": tool.get("input_schema") or {
                    "type": "object", "properties": {}
                },
            },
        }
        for tool in tools
    ]


def compatible_chat(
    *,
    base_url: str,
    model: str,
    api_key: str,
    timeout_seconds: int,
    system: str,
    messages: list[dict],
    tools: list[dict],
    max_tokens: int = 1024,
) -> dict:
    """Llama a cualquier servicio con contrato OpenAI-compatible."""
    if not base_url or not model:
        raise CompatibleAIError("El servicio de IA no está configurado.")
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, *messages],
        "tools": _openai_tools(tools),
        "tool_choice": "auto",
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        _endpoint(base_url),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
    )
    request.add_header("Content-Type", "application/json")
    if api_key:
        request.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(
            request, timeout=timeout_seconds
        ) as response:
            result = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - se degrada al siguiente cerebro
        raise CompatibleAIError(
            f"El servicio compatible no respondió: {type(exc).__name__}"
        ) from exc
    choices = result.get("choices") if isinstance(result, dict) else None
    if (
        not choices
        or not isinstance(choices[0], dict)
        or not isinstance(choices[0].get("message"), dict)
    ):
        raise CompatibleAIError(
            "El servicio compatible devolvió una respuesta incompleta."
        )
    return result


def local_chat(
    *, system: str, messages: list[dict], tools: list[dict], max_tokens: int = 1024
) -> dict:
    """Llama al servicio privado con un contrato OpenAI-compatible."""
    if not local_available():
        raise CompatibleAIError("El servicio de IA privada no está configurado.")
    return compatible_chat(
        base_url=config.LOCAL_AI_BASE_URL,
        model=config.LOCAL_AI_MODEL,
        api_key=config.LOCAL_AI_API_KEY,
        timeout_seconds=config.LOCAL_AI_TIMEOUT_SECONDS,
        system=system,
        messages=messages,
        tools=tools,
        max_tokens=max_tokens,
    )


def external_chat(
    *, system: str, messages: list[dict], tools: list[dict], max_tokens: int = 1024
) -> dict:
    """Llama al proveedor compatible externo configurado para el respaldo barato."""
    if not external_available():
        raise CompatibleAIError(
            "El proveedor compatible externo no está configurado."
        )
    return compatible_chat(
        base_url=config.COMPAT_AI_BASE_URL,
        model=config.COMPAT_AI_MODEL,
        api_key=config.COMPAT_AI_API_KEY,
        timeout_seconds=config.COMPAT_AI_TIMEOUT_SECONDS,
        system=system,
        messages=messages,
        tools=tools,
        max_tokens=max_tokens,
    )
