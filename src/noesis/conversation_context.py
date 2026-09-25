"""Identidad de conversación fijada por el canal autenticado, nunca por el modelo."""
from contextvars import ContextVar

current: ContextVar[tuple[int, str] | None] = ContextVar("conversation_actor", default=None)


def actor_for(business_id: int) -> str | None:
    value = current.get()
    return value[1] if value and value[0] == business_id else None
