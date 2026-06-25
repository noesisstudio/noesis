"""Orquestador del chatbot web (arquitectura híbrida).

1) Intenta resolver con el CEREBRO LOCAL (gratis, interno, sin APIs).
2) Si no lo entiende y hay ANTHROPIC_API_KEY, delega en la IA (Claude).
3) Si no hay clave, responde con la ayuda.

Así la app funciona aunque no haya ninguna API configurada, y el coste por IA solo
aparece en las consultas realmente complejas.
"""

from __future__ import annotations

import json

from .. import config, nlu
from ..tools import run_tool

# Agentes IA por negocio (solo se crean si hay API key y se usan en el fallback).
_agents: dict[int, object] = {}


def handle(business_id: int, message: str) -> dict:
    parsed = nlu.parse(message)

    if parsed:
        tool, args = parsed
        if tool == nlu.HELP:
            return {"reply": nlu.help_text(), "source": "local"}
        if tool == "__need_date__":
            return {"reply": "¿Para qué día lo agendo? Por ejemplo: «mañana por la "
                             "mañana» o «el jueves a las 10».", "source": "local"}
        result = json.loads(run_tool(tool, args, business_id))
        return {"reply": nlu.format_reply(tool, result), "source": "local"}

    # Fallback a la IA (solo si está configurada).
    if config.ANTHROPIC_API_KEY:
        from ..agent import NoesisAgent
        agent = _agents.get(business_id)
        if agent is None:
            agent = NoesisAgent(business_id)
            _agents[business_id] = agent
        return {"reply": agent.send(message), "source": "ia"}

    return {"reply": nlu.help_text(), "source": "local"}
