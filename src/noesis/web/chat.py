"""Orquestador del chatbot web (arquitectura híbrida).

1) Intenta resolver con el CEREBRO LOCAL (gratis, interno, sin APIs).
2) Si no lo entiende y hay ANTHROPIC_API_KEY, delega en la IA (Claude).
3) Si no hay clave, responde con la ayuda.

Así la app funciona aunque no haya ninguna API configurada, y el coste por IA solo
aparece en las consultas realmente complejas.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import date

from .. import config, db, nlu
from ..tools import run_tool

# Agentes IA por negocio (solo se crean si hay API key y se usan en el fallback).
_agents: dict[int, object] = {}
_agents_lock = threading.Lock()
log = logging.getLogger("noesis.chat")


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
        "unbilled": db.unbilled_jobs(business_id),
        "quotes_sent": db.list_quotes(business_id, status="enviado"),
    }


def _daily_plan(state: dict) -> list[dict]:
    """Plan priorizado con el PORQUÉ de cada acción. El orden importa: primero el
    dinero que ya es tuyo, luego el trabajo hecho sin cobrar, luego lo de hoy."""
    plan: list[dict] = []
    if state["late"]:
        total = sum(p["total"] for p in state["late"])
        plan.append({
            "topic": "cobros",
            "do": f"Reclama {len(state['late'])} cobro(s) atrasado(s) por {_eur(total)}.",
            "why": "Es dinero que ya es tuyo y lleva más de una semana fuera de caja.",
        })
    if state["unbilled"]:
        names = ", ".join(dict.fromkeys(
            (j.get("client_name") or "—") for j in state["unbilled"][:3]))
        plan.append({
            "topic": "facturas",
            "do": f"Factura {len(state['unbilled'])} trabajo(s) ya hechos ({names}).",
            "why": "Trabajo terminado sin factura: es donde más dinero se escapa sin que te des cuenta.",
        })
    if state["agenda"]:
        plan.append({
            "topic": "agenda",
            "do": f"Prepara los {len(state['agenda'])} trabajo(s) de hoy.",
            "why": "Si dejas la factura lista al cerrar cada uno, no se te queda ninguno sin cobrar.",
        })
    if state["quotes_sent"]:
        total = sum(q["total"] for q in state["quotes_sent"])
        plan.append({
            "topic": "presupuestos",
            "do": f"Haz seguimiento de {len(state['quotes_sent'])} presupuesto(s) enviados ({_eur(total)} en juego).",
            "why": "Un recordatorio amable a tiempo sube mucho la conversión.",
        })
    billing = state["billing"]
    if billing["invoiced"] and billing["expenses"] / max(billing["invoiced"], 1) > .65:
        plan.append({
            "topic": "costes",
            "do": "Revisa los gastos del mes.",
            "why": "El coste pesa demasiado sobre lo facturado; el margen se está estrechando.",
        })
    if not plan:
        plan.append({
            "topic": "orden",
            "do": "Registra lo nuevo en cuanto ocurra y revisa cobros una vez al día.",
            "why": "Vas al día. Mantener el hábito es lo que evita los sustos.",
        })
    return plan


def daily_plan(business_id: int) -> list[dict]:
    """Plan diario priorizado (con el porqué) para alimentar el dashboard. Mismo
    cerebro que el asistente. Además REGISTRA cada recomendación en el ledger
    (idempotente) y devuelve su id/estado para poder marcarla aceptada/completada."""
    plan = _daily_plan(_business_state(business_id))
    out = []
    for item in plan:
        if item["topic"] == "orden":  # "vas al día": no es una acción que registrar.
            out.append({**item, "id": None, "status": None})
            continue
        rec = db.record_recommendation(business_id, item["topic"], item["do"])
        out.append({**item, "id": rec["id"], "status": rec["status"]})
    return out


def _coach_reply(business_id: int, message: str = "") -> str:
    biz = db.get_business(business_id) or {}
    state = _business_state(business_id)
    billing = state["billing"]
    pending = state["pending"]
    plan = _daily_plan(state)
    top = plan[0]

    lines = [
        f"Así veo {biz.get('name', 'tu negocio')} ahora mismo: facturado "
        f"**{_eur(billing['invoiced'])}** este mes, cobrado {_eur(billing['collected'])}, "
        f"pendiente {_eur(sum(p['total'] for p in pending))} y beneficio estimado "
        f"**{_eur(billing['estimated_profit'])}**.",
        "",
        "**Tu plan para hoy**, por orden de prioridad:",
    ]
    for i, item in enumerate(plan[:4], 1):
        lines.append(f"{i}. {item['do']}")
        lines.append(f"   _Por qué:_ {item['why']}")

    clients = state["clients"]
    total_client_income = sum(c.get("facturado") or 0 for c in clients)
    top_client = clients[0] if clients else None
    if top_client and total_client_income and \
            top_client.get("facturado", 0) / total_client_income > .4:
        lines += ["", f"Ojo a la concentración: {top_client['name']} es el "
                  f"{round(top_client['facturado'] / total_client_income * 100)}% de lo "
                  "facturado. No es malo, pero conviene cuidarlo y abrir una segunda fuente."]

    lines += ["", f"Dime **“ver {top['topic']}”** para ir directo, o háblame con una "
              "frase normal para registrar factura, gasto o trabajo."]
    return "\n".join(lines)


def _unbilled_reply(business_id: int) -> str:
    jobs = db.unbilled_jobs(business_id)
    if not jobs:
        return ("No veo trabajos hechos sin facturar. Buena señal: vas al día con la "
                "facturación. Cuando cierres uno nuevo, dímelo y te dejo la factura lista.")
    lines = [f"Tienes **{len(jobs)} trabajo(s)** que parecen hechos y aún sin factura:"]
    for j in jobs[:8]:
        when = (j.get("scheduled_for") or "")[:10]
        est = f" · ~{_eur(j['price_estimate'])}" if j.get("price_estimate") else ""
        lines.append(f"• {j.get('client_name') or '—'} — {j['description']}"
                     + (f" ({when})" if when else "") + est)
    lines.append("Si alguno ya lo cobraste o no procede facturarlo, ignóralo. Para el "
                 "resto: «factura a [cliente] por [concepto] [importe]».")
    return "\n".join(lines)


def handle(business_id: int, message: str) -> dict:
    norm = nlu._norm(message)  # reutiliza el normalizador local; no sale del servidor.
    if any(x in norm for x in ("sin facturar", "pendiente de facturar", "por facturar",
                               "que me falta facturar", "trabajos sin cobrar")):
        return {"reply": _unbilled_reply(business_id), "source": "local"}
    if any(x in norm for x in ("que harias", "prioridad", "aconsej", "recomiend",
                               "diagnostico", "como lo ves", "mente", "piensa", "plan",
                               "que hago", "por donde empiezo", "que toca")):
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
        if tool in {"crear_factura", "crear_presupuesto"} and "iva incluido" in norm:
            business = db.get_business(business_id) or {}
            rate = float(business.get("default_vat") or 21)
            args["base"] = round(float(args["base"]) / (1 + rate / 100), 2)
            args["iva"] = rate
        result = json.loads(run_tool(tool, args, business_id))
        return {"reply": nlu.format_reply(tool, result), "source": "local"}

    # Fallback a la IA (solo si está configurada).
    if config.ANTHROPIC_API_KEY:
        from ..agent import NoesisAgent
        with _agents_lock:
            agent = _agents.get(business_id)
            if agent is None:
                # Respaldo barato (Haiku): solo lo paga lo que el cerebro local
                # no resuelve. La mayoría de mensajes ni llegan aquí.
                agent = NoesisAgent(business_id, model=config.FALLBACK_MODEL)
                _agents[business_id] = agent
        try:
            return {"reply": agent.send(message), "source": "ia"}
        except Exception:  # noqa: BLE001
            log.exception("El proveedor de IA falló para el negocio %s.", business_id)
            return {
                "reply": "Ahora mismo no puedo usar la IA externa. "
                         "Las órdenes habituales siguen disponibles.",
                "source": "local",
            }

    return {"reply": _coach_reply(business_id, message), "source": "local"}
