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
from datetime import date, datetime

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
        "docs_pending": _docs_pending(business_id),
        "received_pending": db.list_received_invoices(business_id,
                                                      status="pendiente"),
        "leads_due": db.leads_due_today(business_id),
        # Solo lo que pide la gestoría espera respuesta del autónomo; sus
        # propias notas no son una tarea pendiente.
        "gestoria_open": [
            r for r in db.list_gestoria_requests(business_id, status="abierta")
            if r["requested_by"] == "gestoria"
        ],
    }


def _docs_pending(business_id: int) -> list[dict]:
    from ..documents import repo as docrepo
    return docrepo.list_pending_review(business_id)


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
    if state.get("leads_due"):
        names = ", ".join(dict.fromkeys(
            lead["name"] for lead in state["leads_due"][:3]))
        plan.append({
            "topic": "crm",
            "do": f"Sigue a {len(state['leads_due'])} posible(s) cliente(s) ({names}).",
            "why": "Tenían seguimiento para hoy o antes; en frío, un presupuesto se pierde.",
        })
    if state.get("gestoria_open"):
        plan.append({
            "topic": "gestoria",
            "do": f"Responde a tu gestoría: {len(state['gestoria_open'])} solicitud(es) abiertas.",
            "why": "Sin esos papeles no puede cerrar tu trimestre; está en Documentos.",
        })
    if state.get("docs_pending"):
        plan.append({
            "topic": "documentos",
            "do": f"Revisa {len(state['docs_pending'])} documento(s) pendientes de confirmar.",
            "why": "Un papel sin clasificar es un gasto sin deducir o una factura perdida.",
        })
    if state.get("received_pending"):
        total = sum(r["total"] for r in state["received_pending"])
        plan.append({
            "topic": "pagos",
            "do": f"Tienes {len(state['received_pending'])} factura(s) de proveedor por pagar ({_eur(total)}).",
            "why": "Pagar a tiempo evita recargos y mantiene a tus proveedores de tu lado.",
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


# Cada tema del plan vive en una página del menú (algunos dentro de otra sección).
_TOPIC_PAGE = {
    "cobros": "cobros", "facturas": "facturas", "agenda": "agenda",
    "presupuestos": "presupuestos", "crm": "crm", "gestoria": "documentos",
    "documentos": "documentos", "pagos": "costes", "costes": "costes",
}
_TOPIC_ACTION = {
    "cobros": "Revisar cobros", "facturas": "Ver facturas",
    "agenda": "Ver la agenda", "presupuestos": "Ver presupuestos",
    "crm": "Ver posibles clientes", "gestoria": "Ir a Documentos",
    "documentos": "Revisar documentos", "pagos": "Facturas de proveedor",
    "costes": "Revisar gastos",
}


def _greeting(hour: int) -> str:
    if 6 <= hour < 14:
        return "Buenos días"
    if 14 <= hour < 21:
        return "Buenas tardes"
    return "Buenas noches"


def daily_briefing(business_id: int) -> dict:
    """El 'parte' del día, en primera persona: Noesis ha revisado el negocio y dice
    lo importante, con su acción al lado. Reutiliza el mismo cerebro que el plan y el
    asistente. NUNCA inventa: si no hay nada que ordenar, lo dice con honestidad."""
    biz = db.get_business(business_id) or {}
    name = (biz.get("name") or "").strip().split()[0] if biz.get("name") else ""
    state = _business_state(business_id)
    plan = _daily_plan(state)
    billing = state["billing"]

    on_track = len(plan) == 1 and plan[0]["topic"] == "orden"
    has_activity = bool(
        billing.get("invoiced") or state["pending"] or state["agenda"]
        or state["clients"] or state["unbilled"]
    )

    items = []
    if not on_track:
        for item in plan[:4]:
            topic = item["topic"]
            items.append({
                "do": item["do"],
                "why": item["why"],
                "topic": topic,
                "href": f"/b/{business_id}/{_TOPIC_PAGE.get(topic, 'resumen')}",
                "action": _TOPIC_ACTION.get(topic, "Ver"),
            })

    if items:
        lead = "He revisado tu negocio. Esto es lo importante de hoy:"
    elif not has_activity:
        lead = ("Aún no tengo nada que ordenarte. En cuanto crees tu primer cliente, "
                "factura o trabajo, cada día te doy el parte con lo importante.")
    else:
        lead = ("He revisado tu negocio y vas al día: nada urgente ahora mismo. "
                "Sigue registrando lo nuevo en cuanto pase y yo te aviso.")

    return {
        "greeting": _greeting(datetime.now().hour),
        "name": name,
        "lead": lead,
        "on_track": on_track,
        "has_activity": has_activity,
        "visits_today": len(state["agenda"]),
        "tasks": items,
        "money": {
            "invoiced": billing.get("invoiced") or 0,
            "collected": billing.get("collected") or 0,
            "pending": sum(p["total"] for p in state["pending"]),
        },
    }


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


# Qué es cada página, para que el asistente pueda explicar dónde está el usuario.
_PAGE_HINTS = {
    "resumen": "tu centro de mando: qué pasa hoy, qué cobrar y el plan del día",
    "tesoreria": "tu caja: qué te deben, qué debes (IVA/IRPF) y qué entrará",
    "analisis": "tus ratios: margen, tasa de cobro, morosidad y concentración",
    "ingresos": "lo que facturas y cobras, mes a mes",
    "costes": "tus gastos, las facturas de proveedor y dónde se va el dinero",
    "facturas": "tus facturas emitidas y su estado (borrador, enviada, cobrada)",
    "presupuestos": "los presupuestos enviados y cuáles siguen sin respuesta",
    "cobros": "lo pendiente de cobrar, con lo más atrasado primero",
    "impuestos": "una estimación orientativa del IVA (303) e IRPF (130); la declaración final es de tu gestoría",
    "agenda": "tus trabajos y citas, por día",
    "equipo": "tus trabajadores, su fichaje y sus horas",
    "clientes": "tu lista de clientes y lo que mueve cada uno",
    "crm": "los posibles clientes: quién pidió precio y a quién seguir hoy",
    "productos": "tu catálogo: qué vendes, a qué precio y con qué margen",
    "documentos": "tus papeles: subes o fotografías, Noesis propone y tú confirmas",
    "ajustes": "los datos de tu negocio: fiscales, marca, gestoría, idioma y canales",
}


def page_briefing(business_id: int, page: str) -> str | None:
    """Explica la página actual con los datos REALES del negocio. Sin inventar:
    si no hay datos, lo dice."""
    hint = _PAGE_HINTS.get(page)
    if not hint:
        return None
    lines = [f"Estás en **{page.capitalize()}**: {hint}."]
    state = _business_state(business_id)
    if page in {"resumen", "cobros", "tesoreria"}:
        pending = sum(p["total"] for p in state["pending"])
        lines.append(f"Ahora mismo tienes {_eur(pending)} pendientes de cobro"
                     + (f", {len(state['late'])} cobro(s) con más de una semana."
                        if state["late"] else ".") )
    if page == "documentos":
        n = len(state["docs_pending"])
        lines.append(f"Tienes {n} documento(s) pendientes de revisar."
                     if n else "No tienes documentos pendientes de revisar.")
        if state["gestoria_open"]:
            lines.append(f"Tu gestoría tiene {len(state['gestoria_open'])} "
                         "solicitud(es) abiertas esperándote.")
    if page == "costes":
        n = len(state["received_pending"])
        if n:
            total = sum(r["total"] for r in state["received_pending"])
            lines.append(f"Hay {n} factura(s) de proveedor por pagar ({_eur(total)}).")
    if page == "crm":
        due = state["leads_due"]
        lines.append(f"Hoy toca seguir a {len(due)} posible(s) cliente(s)."
                     if due else "No tienes seguimientos vencidos. Bien.")
    if page in {"facturas", "presupuestos"} and state["quotes_sent"]:
        lines.append(f"Tienes {len(state['quotes_sent'])} presupuesto(s) enviados "
                     "sin respuesta: un recordatorio a tiempo sube la conversión.")
    lines.append("Pregúntame lo que quieras de esta página o dime «plan» y te "
                 "digo por dónde empezar hoy.")
    return "\n\n".join(lines)


def handle(business_id: int, message: str, page: str | None = None) -> dict:
    norm = nlu._norm(message)  # reutiliza el normalizador local; no sale del servidor.
    if page and any(x in norm for x in (
            "esta pagina", "que veo aqui", "donde estoy", "que significa esto",
            "explica esta", "explicame esta", "que es esto")):
        briefing = page_briefing(business_id, page)
        if briefing:
            return {"reply": briefing, "source": "local"}
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
            # Contexto y preferencia de idioma van como marco del mensaje: el
            # agente ya está acotado al negocio; esto solo orienta la respuesta.
            business = db.get_business(business_id) or {}
            prefix = ""
            if page and page in _PAGE_HINTS:
                prefix += f"[El usuario está en la página '{page}' ({_PAGE_HINTS[page]})] "
            language = business.get("language") or "es"
            if language != "es":
                prefix += ("[Responde en catalán salvo que el usuario escriba "
                           "claramente en otro idioma] " if language == "ca" else
                           "[Reply in English unless the user clearly writes "
                           "in another language] ")
            return {"reply": agent.send(prefix + message), "source": "ia"}
        except Exception:  # noqa: BLE001
            log.exception("El proveedor de IA falló para el negocio %s.", business_id)
            return {
                "reply": "Ahora mismo no puedo usar la IA externa. "
                         "Las órdenes habituales siguen disponibles.",
                "source": "local",
            }

    return {"reply": _coach_reply(business_id, message), "source": "local"}
