"""Orquestador del chatbot web (arquitectura híbrida).

1) Intenta resolver con el CEREBRO LOCAL (gratis, interno, sin APIs).
2) Si no lo entiende y hay ANTHROPIC_API_KEY, delega en la IA (Claude).
3) Si no hay clave, responde con la ayuda.

Así la app funciona aunque no haya ninguna API configurada, y el coste por IA solo
aparece en las consultas realmente complejas.
"""

from __future__ import annotations

import json
from datetime import date

from .. import config, db, nlu
from ..tools import run_tool

# Agentes IA por negocio (solo se crean si hay API key y se usan en el fallback).
_agents: dict[int, object] = {}


def _eur(n) -> str:
    return f"{(n or 0):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _business_state(business_id: int) -> dict:
    today = date.today().isoformat()
    billing = db.month_billing(business_id=business_id)
    pending = db.pending_payments(business_id)
    agenda = db.jobs_for_date(today, business_id)
    clients = db.client_stats(business_id)
    expenses = db.list_expenses(business_id)
    late = [p for p in pending if (p.get("days_outstanding") or 0) > 7]
    return {
        "billing": billing,
        "pending": pending,
        "late": late,
        "agenda": agenda,
        "clients": clients,
        "expenses": expenses,
    }


def _next_action(state: dict) -> tuple[str, str]:
    late = state["late"]
    agenda = state["agenda"]
    billing = state["billing"]
    expenses = state["expenses"]
    if late:
        total = sum(p["total"] for p in late)
        return ("cobros", f"Reclamar {len(late)} factura(s) atrasada(s): {_eur(total)} que ya debería estar en caja.")
    if agenda:
        return ("agenda", f"Preparar {len(agenda)} trabajo(s) de hoy: cliente, zona, material y posible factura.")
    if billing["invoiced"] and billing["expenses"] / max(billing["invoiced"], 1) > .65:
        return ("margen", "Revisar gastos: este mes el coste pesa demasiado sobre lo facturado.")
    if not expenses:
        return ("gastos", "Registrar gastos recientes para que el beneficio no sea una foto demasiado optimista.")
    return ("orden", "Mantener el hábito: registrar lo nuevo en cuanto ocurra y revisar cobros una vez al día.")


def _coach_reply(business_id: int, message: str = "") -> str:
    biz = db.get_business(business_id) or {}
    state = _business_state(business_id)
    billing = state["billing"]
    pending = state["pending"]
    clients = state["clients"]
    topic, action = _next_action(state)
    top_client = clients[0] if clients else None
    concentration = ""
    total_client_income = sum(c.get("facturado") or 0 for c in clients)
    if top_client and total_client_income and top_client.get("facturado", 0) / total_client_income > .4:
        concentration = (f"\n\nVeo una dependencia fuerte de {top_client['name']}: "
                         f"{round(top_client['facturado'] / total_client_income * 100)}% de lo facturado. "
                         "No es malo, pero conviene cuidarlo y abrir segunda fuente.")

    return (
        f"Estoy mirando {biz.get('name', 'tu negocio')} como lo miraría una oficina pequeña: "
        "caja, agenda, margen y próximos pasos.\n\n"
        f"Ahora mismo has facturado **{_eur(billing['invoiced'])}** este mes, "
        f"has cobrado {_eur(billing['collected'])}, tienes pendiente {_eur(sum(p['total'] for p in pending))} "
        f"y el beneficio estimado va por **{_eur(billing['estimated_profit'])}**.\n\n"
        f"Mi prioridad para ti: **{action}**\n\n"
        f"Si quieres, te lo convierto en acción: dime **“ver {topic}”**, "
        "**“qué tengo hoy”**, **“quién me debe”** o háblame con una frase normal "
        "para registrar factura, gasto o trabajo."
        f"{concentration}"
    )


def handle(business_id: int, message: str) -> dict:
    norm = nlu._norm(message)  # reutiliza el normalizador local; no sale del servidor.
    if any(x in norm for x in ("que harias", "prioridad", "aconsej", "recomiend", "diagnostico",
                               "como lo ves", "mente", "piensa")):
        return {"reply": _coach_reply(business_id, message), "source": "local"}

    parsed = nlu.parse(message)

    if parsed:
        tool, args = parsed
        if tool == nlu.HELP:
            return {"reply": _coach_reply(business_id, message), "source": "local"}
        if tool == "__need_date__":
            return {"reply": "Te lo puedo agendar, pero me falta el día. Dímelo como lo dirías por WhatsApp: "
                             "**mañana por la mañana**, **el jueves a las 10** o "
                             "**el lunes por la tarde en Badalona**.", "source": "local"}
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

    return {"reply": _coach_reply(business_id, message), "source": "local"}
