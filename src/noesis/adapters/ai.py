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


class LocalAIError(RuntimeError):
    """El servicio local no respondió con un contrato utilizable."""


def local_available() -> bool:
    return bool(config.LOCAL_AI_BASE_URL and config.LOCAL_AI_MODEL)


def _endpoint() -> str:
    base = config.LOCAL_AI_BASE_URL.strip().rstrip("/")
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


def local_chat(
    *, system: str, messages: list[dict], tools: list[dict], max_tokens: int = 1024
) -> dict:
    """Llama al servicio privado con un contrato OpenAI-compatible."""
    if not local_available():
        raise LocalAIError("El servicio de IA privada no está configurado.")
    payload = {
        "model": config.LOCAL_AI_MODEL,
        "messages": [{"role": "system", "content": system}, *messages],
        "tools": _openai_tools(tools),
        "tool_choice": "auto",
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        _endpoint(),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
    )
    request.add_header("Content-Type", "application/json")
    if config.LOCAL_AI_API_KEY:
        request.add_header("Authorization", f"Bearer {config.LOCAL_AI_API_KEY}")
    try:
        with urllib.request.urlopen(
            request, timeout=config.LOCAL_AI_TIMEOUT_SECONDS
        ) as response:
            result = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - se degrada al siguiente cerebro
        raise LocalAIError(f"El servicio local no respondió: {type(exc).__name__}") from exc
    choices = result.get("choices") if isinstance(result, dict) else None
    if (
        not choices
        or not isinstance(choices[0], dict)
        or not isinstance(choices[0].get("message"), dict)
    ):
        raise LocalAIError("El servicio local devolvió una respuesta incompleta.")
    return result
