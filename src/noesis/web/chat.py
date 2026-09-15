"""Orquestador híbrido compartido por el acompañante web y WhatsApp.

Resuelve primero con reglas internas, después con un servicio privado opcional y,
solo con consentimiento y créditos, con el proveedor externo. Si falla un nivel,
Bynoesis conserva la respuesta y las órdenes rutinarias locales.
"""

from __future__ import annotations

import json
import re
import logging
import threading
from datetime import date, datetime

from .. import config, db, internal_brain, nlu
from ..adapters import ai as ai_adapter
from ..adapters import billing as billing_adapter
from ..tools import run_tool

# Agentes por negocio. El historial y el bloqueo nunca se comparten entre empresas.
_agents: dict[int, object] = {}
_local_agents: dict[int, object] = {}
_compatible_agents: dict[int, object] = {}
_agents_lock = threading.Lock()
log = logging.getLogger("noesis.chat")


def _eur(n) -> str:
    return f"{(n or 0):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _count(n: int, singular: str, plural: str | None = None) -> str:
    return f"{n} {singular if n == 1 else (plural or singular + 's')}"


def assistant_prompts(business: dict | None) -> list[str]:
    """Ejemplos útiles sin asumir que todos los negocios son de fontanería."""
    sector = nlu._norm(str((business or {}).get("sector") or ""))
    common = [
        "¿Qué harías tú ahora con mi negocio?",
        "Dame un diagnóstico rápido",
        "¿Qué tengo hoy?",
        "¿Quién me debe dinero?",
    ]
    if "limp" in sector:
        examples = [
            "Factura a Marta por limpieza de oficina 95 euros",
            "Agenda a Marta mañana a las 10 para una limpieza",
            "Gasté 45 euros en productos de limpieza",
        ]
    elif "electric" in sector:
        examples = [
            "Factura a Marta por revisión del cuadro eléctrico 95 euros",
            "Agenda a Marta mañana a las 10 para revisar una avería",
            "Gasté 45 euros en material eléctrico",
        ]
    elif "jardin" in sector:
        examples = [
            "Factura a Marta por mantenimiento del jardín 95 euros",
            "Agenda a Marta mañana a las 10 para podar el jardín",
            "Gasté 45 euros en plantas y material",
        ]
    elif any(word in sector for word in ("fontan", "reform", "constru")):
        examples = [
            "Factura a Juan por cambio de grifo 95 euros",
            "Agenda a Marta mañana a las 10 en Badalona",
            "Gasté 45 euros en material",
        ]
    else:
        examples = [
            "Factura a Marta por servicio realizado 95 euros",
            "Agenda a Marta mañana a las 10 para un trabajo",
            "Gasté 45 euros en material",
        ]
    return [*common, *examples, "Dame el resumen del mes"]


def _business_state(business_id: int) -> dict:
    business = db.get_business(business_id)
    today = date.today().isoformat()
    billing = db.month_billing(business_id=business_id)
    pending = db.pending_payments(business_id)
    agenda = db.jobs_for_date(today, business_id)
    clients = db.client_stats(business_id)
    expenses = db.list_expenses(business_id)
    late = [p for p in pending if (p.get("days_outstanding") or 0) > 7]
    projects = (
        db.list_projects(business_id)
        if billing_adapter.has_entitlement(
            business, billing_adapter.ENTITLEMENT_PROJECTS
        )
        else []
    )
    project_alerts = []
    if db.automation_decision(business_id, "project_alerts")["allowed"]:
        for project in projects:
            if project.get("status") == "terminado":
                continue
            if project.get("margin", 0) < 0:
                reason = "presupuesto_superado"
            elif project.get("missing_hourly_cost_worker_ids"):
                reason = "coste_hora_incompleto"
            elif (
                project.get("progress")
                and project.get("actual_cost", 0)
                > project.get("budget", 0) * (project["progress"] / 100 + .10)
            ):
                reason = "coste_adelantado"
            else:
                continue
            project_alerts.append({**project, "alert_reason": reason})
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
        "gestoria_open": (
            [
                r for r in db.list_gestoria_requests(
                    business_id, status="abierta"
                )
                if r["requested_by"] == "gestoria"
            ]
            if billing_adapter.has_entitlement(
                business, billing_adapter.ENTITLEMENT_GESTORIA
            )
            else []
        ),
        "projects": projects,
        "project_alerts": project_alerts,
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
            "do": f"Reclama {_count(len(state['late']), 'cobro atrasado', 'cobros atrasados')} por {_eur(total)}.",
            "why": "Es dinero que ya es tuyo y lleva más de una semana fuera de caja.",
        })
    if state["unbilled"]:
        names = ", ".join(dict.fromkeys(
            (j.get("client_name") or "—") for j in state["unbilled"][:3]))
        plan.append({
            "topic": "facturas",
            "do": f"Factura {_count(len(state['unbilled']), 'trabajo ya hecho', 'trabajos ya hechos')} ({names}).",
            "why": "Trabajo terminado sin factura: es donde más dinero se escapa sin que te des cuenta.",
        })
    if state.get("project_alerts"):
        project = state["project_alerts"][0]
        reason = project["alert_reason"]
        if reason == "presupuesto_superado":
            do = (
                f"Revisa {project['name']}: supera el presupuesto en "
                f"{_eur(abs(project['margin']))}."
            )
            why = "Las horas y los gastos conectados ya han consumido todo el margen."
        elif reason == "coste_hora_incompleto":
            do = f"Completa el coste por hora del equipo en {project['name']}."
            why = "Hay horas fichadas, pero sin ese coste el margen no sería fiable."
        else:
            do = f"Revisa el ritmo de gasto de {project['name']}."
            why = "El coste va por delante del avance registrado del proyecto."
        plan.append({"topic": "proyectos", "do": do, "why": why})
    if state["agenda"]:
        plan.append({
            "topic": "agenda",
            "do": f"Prepara {_count(len(state['agenda']), 'trabajo', 'trabajos')} de hoy.",
            "why": "Si dejas la factura lista al cerrar cada uno, no se te queda ninguno sin cobrar.",
        })
    if state["quotes_sent"]:
        total = sum(q["total"] for q in state["quotes_sent"])
        plan.append({
            "topic": "presupuestos",
            "do": f"Haz seguimiento de {_count(len(state['quotes_sent']), 'presupuesto enviado', 'presupuestos enviados')} ({_eur(total)} en juego).",
            "why": "Un recordatorio amable a tiempo sube mucho la conversión.",
        })
    if state.get("leads_due"):
        names = ", ".join(dict.fromkeys(
            lead["name"] for lead in state["leads_due"][:3]))
        plan.append({
            "topic": "crm",
            "do": f"Sigue a {_count(len(state['leads_due']), 'posible cliente', 'posibles clientes')} ({names}).",
            "why": "Tenían seguimiento para hoy o antes; en frío, un presupuesto se pierde.",
        })
    if state.get("gestoria_open"):
        plan.append({
            "topic": "gestoria",
            "do": f"Responde a tu gestoría: {_count(len(state['gestoria_open']), 'solicitud abierta', 'solicitudes abiertas')}.",
            "why": "Sin esos papeles no puede cerrar tu trimestre; está en Documentos.",
        })
    if state.get("docs_pending"):
        plan.append({
            "topic": "documentos",
            "do": f"Revisa {_count(len(state['docs_pending']), 'documento pendiente', 'documentos pendientes')} de confirmar.",
            "why": "Un papel sin clasificar es un gasto sin deducir o una factura perdida.",
        })
    if state.get("received_pending"):
        total = sum(r["total"] for r in state["received_pending"])
        plan.append({
            "topic": "pagos",
            "do": f"Tienes {_count(len(state['received_pending']), 'factura de proveedor', 'facturas de proveedor')} por pagar ({_eur(total)}).",
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


def daily_plan(business_id: int, *, record: bool = True) -> list[dict]:
    """Plan diario priorizado (con el porqué) para alimentar el dashboard. Mismo
    cerebro que el asistente. Si ``record`` está activo, registra cada recomendación
    en el ledger (idempotente) y devuelve su estado; el modo consulta solo la lee."""
    plan = _daily_plan(_business_state(business_id))
    out = []
    for item in plan:
        if item["topic"] == "orden" or not record:
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
    "proyectos": "proyectos",
}
_TOPIC_ACTION = {
    "cobros": "Revisar cobros", "facturas": "Ver facturas",
    "agenda": "Ver la agenda", "presupuestos": "Ver presupuestos",
    "crm": "Ver posibles clientes", "gestoria": "Ir a Documentos",
    "documentos": "Revisar documentos", "pagos": "Facturas de proveedor",
    "costes": "Revisar gastos",
    "proyectos": "Revisar proyecto",
}


def _greeting(hour: int) -> str:
    if 6 <= hour < 14:
        return "Buenos días"
    if 14 <= hour < 21:
        return "Buenas tardes"
    return "Buenas noches"


def daily_briefing(business_id: int) -> dict:
    """El 'parte' del día, resiliente: si algo falla al leer el negocio, el Home NO
    se cae — devuelve un parte mínimo y honesto y el detalle sigue debajo. La lógica
    real vive en `_compose_briefing`."""
    try:
        return _compose_briefing(business_id)
    except Exception:  # noqa: BLE001 — el parte jamás debe tumbar la página esencial
        log.exception("daily_briefing falló para el negocio %s", business_id)
        return {
            "greeting": _greeting(datetime.now().hour), "name": "",
            "lead": ("Aquí tienes tu negocio. No he podido preparar el parte del día "
                     "ahora mismo; tienes el detalle más abajo."),
            "on_track": False, "has_activity": False, "visits_today": 0,
            "tasks": [], "money": {"invoiced": 0, "collected": 0, "pending": 0},
        }


def _compose_briefing(business_id: int) -> dict:
    """El 'parte' del día, en primera persona: Bynoesis ha revisado el negocio y dice
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
        or state["clients"] or state["unbilled"] or state["projects"]
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
        f"**{_eur(billing['invoiced'])}** este mes, han entrado {_eur(billing['collected'])}, "
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
    lines = [f"Tienes **{_count(len(jobs), 'trabajo', 'trabajos')}** que parecen hechos y aún sin factura:"]
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
    "proyectos": "tus obras e instalaciones: avance, horas, costes y margen",
    "equipo": "tus trabajadores, su fichaje y sus horas",
    "clientes": "tu lista de clientes y lo que mueve cada uno",
    "crm": "los posibles clientes: quién pidió precio y a quién seguir hoy",
    "productos": "tu catálogo: qué vendes, a qué precio y con qué margen",
    "documentos": "tus papeles: subes o fotografías, Bynoesis propone y tú confirmas",
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
                     + (f", {_count(len(state['late']), 'cobro', 'cobros')} con más de una semana."
                        if state["late"] else ".") )
    if page == "documentos":
        n = len(state["docs_pending"])
        lines.append(f"Tienes {_count(n, 'documento pendiente', 'documentos pendientes')} de revisar."
                     if n else "No tienes documentos pendientes de revisar.")
        if state["gestoria_open"]:
            lines.append(f"Tu gestoría tiene {len(state['gestoria_open'])} "
                         "solicitud(es) abiertas esperándote.")
    if page == "costes":
        n = len(state["received_pending"])
        if n:
            total = sum(r["total"] for r in state["received_pending"])
            lines.append(f"Hay {_count(n, 'factura de proveedor', 'facturas de proveedor')} por pagar ({_eur(total)}).")
    if page == "crm":
        due = state["leads_due"]
        lines.append(f"Hoy toca seguir a {_count(len(due), 'posible cliente', 'posibles clientes')}."
                     if due else "No tienes seguimientos vencidos. Bien.")
    if page in {"facturas", "presupuestos"} and state["quotes_sent"]:
        lines.append(f"Tienes {_count(len(state['quotes_sent']), 'presupuesto enviado', 'presupuestos enviados')} "
                     "sin respuesta: un recordatorio a tiempo sube la conversión.")
    lines.append("Pregúntame lo que quieras de esta página o dime «plan» y te "
                 "digo por dónde empezar hoy.")
    return "\n\n".join(lines)


def page_note(business_id: int, page: str, state: dict | None = None) -> str | None:
    """La voz de Bynoesis en la cabecera de cada pantalla: UNA línea con un dato real
    del negocio, en primera persona. Resiliente (nunca tumba la página) y honesta
    (si no hay nada, lo dice). Devuelve None en el Home (ya tiene su parte) y en
    páginas sin lectura útil. Acepta el estado precomputado para no leer dos veces."""
    if page == "resumen" or page not in _PAGE_HINTS:
        return None
    try:
        state = state or _business_state(business_id)
    except Exception:  # noqa: BLE001 — una cabecera nunca puede tumbar la pantalla
        log.exception("page_note falló para %s en %s", page, business_id)
        return None
    if page in {"cobros", "tesoreria"}:
        pend = sum(p["total"] for p in state["pending"])
        if pend:
            late = len(state["late"])
            return (f"Te deben {_eur(pend)}"
                    + (f", y {late} llevan más de una semana fuera de caja. "
                       "Yo empezaría por esos." if late else ". Vas bastante al día."))
        return "Ahora mismo no te deben nada. Caja limpia."
    if page == "documentos":
        bits = []
        if state["docs_pending"]:
            bits.append(f"{_count(len(state['docs_pending']), 'documento', 'documentos')} por revisar")
        if state["gestoria_open"]:
            bits.append(f"{len(state['gestoria_open'])} solicitud(es) de tu gestoría")
        return ("Tienes " + " y ".join(bits) + "." if bits
                else "Todo al día por aquí. Sube una foto: te propongo dónde va y tú confirmas.")
    if page == "costes":
        rec = state["received_pending"]
        if rec:
            total = sum(r["total"] for r in rec)
            return f"Hay {_count(len(rec), 'factura de proveedor', 'facturas de proveedor')} por pagar ({_eur(total)})."
        return "Aquí controlas dónde se va el dinero. Sube un ticket y lo registro."
    if page == "proyectos":
        summary = db.project_summary(business_id)
        if not summary["active_count"]:
            return "Aún no hay proyectos activos. Crea uno y vigilaré avance, horas y margen contigo."
        return (f"Tienes {_count(summary['active_count'], 'proyecto activo', 'proyectos activos')}, con "
                f"{_eur(summary['margin'])} de margen disponible en conjunto.")
    if page == "analisis":
        billing = state["billing"]
        invoiced = billing.get("invoiced") or 0
        profit = billing.get("estimated_profit") or 0
        if not invoiced:
            return "Aún no hay facturación este mes. Cuando la haya, te explicaré margen, cobro y riesgo sin jerga."
        margin = round(profit / max(billing.get("revenue_base") or 1, 1) * 100)
        return (f"Este mes el beneficio estimado es {_eur(profit)} y el margen ronda el {margin}%. "
                "No es una nota: es lo que queda después de los gastos registrados.")
    if page == "ingresos":
        billing = state["billing"]
        return (f"Este mes has facturado {_eur(billing.get('invoiced'))} y han entrado "
                f"{_eur(billing.get('collected'))}. Lo facturado no siempre es dinero ya disponible.")
    if page == "agenda":
        jobs = state["agenda"]
        return (f"Hoy tienes {_count(len(jobs), 'trabajo', 'trabajos')}. Al cerrar cada uno, te ayudaré a dejarlo facturado."
                if jobs else "Hoy no tienes trabajos en agenda. Puedes añadir uno y dejar cliente, hora y encargo atados.")
    if page == "equipo":
        team = db.clockins_today(business_id)
        working = sum(1 for worker in team if worker.get("open_shift"))
        return (f"Hay {_count(len(team), 'persona', 'personas')} en el equipo y {working} trabajando ahora. "
                "Las horas salen del fichaje real, no de una estimación."
                if team else "Aún no hay equipo. Cuando lo añadas, cada persona verá sus trabajos y fichará desde su panel.")
    if page == "clientes":
        clients = state["clients"]
        active = sum(1 for client in clients if client.get("n_trabajos") or client.get("n_facturas"))
        return (f"Conozco {_count(len(clients), 'cliente', 'clientes')}; {active} ya tienen actividad registrada. "
                "Aquí importa su historia, no solo sus datos de contacto."
                if clients else "Aún no hay clientes. Crea el primero y reuniré aquí trabajos, presupuestos, facturas y cobros.")
    if page == "productos":
        products = db.list_products(business_id)
        known_margin = [p for p in products if p.get("margin_pct") is not None]
        return (f"Tienes {_count(len(products), 'servicio o producto', 'servicios o productos')}; "
                f"conozco el margen de {len(known_margin)}. Completa el coste para que no te aconseje a ciegas."
                if products else "Aún no hay catálogo. Añade lo que vendes y su coste para presupuestar con margen real.")
    if page == "impuestos":
        today = date.today()
        taxes = db.tax_quarter(today.year, (today.month - 1) // 3 + 1, business_id)
        reserve = max(taxes["iva_resultado"], 0) + taxes["irpf_pago"]
        return (f"Con lo registrado, conviene reservar aproximadamente {_eur(reserve)} este trimestre. "
                "Es una estimación de apoyo; tu gestoría valida la presentación.")
    if page == "crm":
        due = len(state["leads_due"])
        return (f"Hoy toca seguir a {_count(due, 'posible cliente', 'posibles clientes')}; en frío se enfrían."
                if due else "Sin seguimientos vencidos. Apunta a quien te pida precio.")
    if page == "facturas":
        pend = sum(p["total"] for p in state["pending"])
        if state["unbilled"]:
            extra = f" Y te deben {_eur(pend)} de las ya enviadas." if pend else ""
            return (f"Tienes {_count(len(state['unbilled']), 'trabajo hecho sin facturar', 'trabajos hechos sin facturar')}: "
                    f"ahí es donde se escapa el dinero.{extra}")
        if pend:
            late = len(state["late"])
            return (f"Te deben {_eur(pend)} de {_count(len(state['pending']), 'factura enviada', 'facturas enviadas')}"
                    + (f"; {late} llevan más de una semana. Yo reclamaría hoy." if late else ". Vas al día."))
        return ("Todo lo facturado está cobrado. Cuando cierres un trabajo, "
                "dímelo y la factura sale sola de aquí.")
    if page == "presupuestos" and state["quotes_sent"]:
        q = state["quotes_sent"]
        total = sum(x["total"] for x in q)
        return (f"{_count(len(q), 'presupuesto enviado', 'presupuestos enviados')} esperan respuesta "
                f"({_eur(total)} en juego). Un recordatorio a tiempo convierte.")
    if page == "presupuestos":
        return "No hay presupuestos esperando respuesta. Aquí preparas, envías y sigues cada oportunidad hasta aceptarla o cerrarla."
    if page == "ajustes":
        return "Aquí decides cómo trabaja Bynoesis contigo: datos fiscales, permisos, integraciones y nivel de explicación."
    return f"Aquí tienes {_PAGE_HINTS[page]}."


# Pregunta natural con la que el botón "Explícamelo" abre el acompañante en cada
# pantalla. La figura de Bynoesis es la misma en todas partes: lee, muestra y explica.
_PAGE_ASK = {
    "facturas": "Explícame cómo va mi facturación este mes y qué harías tú.",
    "cobros": "¿A quién le reclamo primero y qué mensaje le mando?",
    "presupuestos": "¿Qué presupuestos debería mover hoy?",
    "clientes": "¿Qué clientes debería cuidar más ahora mismo?",
    "crm": "¿Qué posible cliente tengo más caliente y qué le digo?",
    "documentos": "¿Qué hago con los documentos pendientes?",
    "costes": "¿Dónde se me está yendo el dinero este mes?",
    "ingresos": "¿Cómo van mis ingresos comparados con lo normal?",
    "tesoreria": "Explícame mi caja en dos frases.",
    "analisis": "Explícame estos números como si no supiera de finanzas.",
    "impuestos": "¿Cuánto debería apartar para Hacienda este trimestre?",
    "agenda": "Organízame el día de hoy.",
    "equipo": "¿Cómo va el equipo esta semana?",
    "productos": "¿Qué me deja más margen de lo que vendo?",
    "proyectos": "¿Qué proyecto me está comiendo el margen?",
}

_PAGE_PROMPTS = {
    "facturas": ["¿Qué tengo que facturar hoy?", "Explícame lo pendiente"],
    "cobros": ["¿A quién reclamo primero?", "Redáctame un recordatorio"],
    "presupuestos": ["¿Qué presupuesto moverías?", "¿Qué tengo en juego?"],
    "clientes": ["¿A quién debería cuidar?", "¿Dependo demasiado de alguien?"],
    "crm": ["¿A quién sigo hoy?", "Prepárame el siguiente mensaje"],
    "documentos": ["¿Qué falta por confirmar?", "¿Qué verá mi gestoría?"],
    "costes": ["¿Dónde se va el dinero?", "¿Qué pago vence primero?"],
    "ingresos": ["¿Cuánto ha entrado de verdad?", "Explícame la diferencia"],
    "tesoreria": ["¿Cuánta caja tendré?", "¿Qué dinero no puedo gastar?"],
    "analisis": ["Explícame mi margen", "¿Qué número debería mejorar?"],
    "impuestos": ["¿Cuánto aparto?", "¿De dónde sale esta cifra?"],
    "agenda": ["Ordéname el día", "¿Qué debería dejar preparado?"],
    "equipo": ["¿Quién está trabajando?", "¿Falta algún fichaje?"],
    "productos": ["¿Qué me deja más margen?", "¿Qué coste me falta?"],
    "proyectos": ["¿Qué proyecto está en riesgo?", "Explícame el margen"],
    "ajustes": ["¿Qué integración me falta?", "Explícame estos permisos"],
}

_PAGE_TOPICS = {
    "tesoreria": {"cobros", "pagos", "costes"},
    "analisis": {"cobros", "costes", "proyectos"},
    "ingresos": {"facturas", "cobros"},
    "costes": {"costes", "pagos", "documentos"},
    "facturas": {"facturas", "cobros"},
    "presupuestos": {"presupuestos"},
    "cobros": {"cobros"},
    "impuestos": {"documentos", "gestoria", "costes"},
    "agenda": {"agenda"},
    "proyectos": {"proyectos"},
    "equipo": {"agenda", "proyectos"},
    "clientes": {"cobros", "presupuestos", "crm"},
    "crm": {"crm", "presupuestos"},
    "productos": {"costes"},
    "documentos": {"documentos", "gestoria", "pagos"},
}


def _page_focus(page: str, state: dict) -> dict | None:
    """Primera acción del plan que pertenece a esta pantalla. No convierte cada
    sección en un dashboard: conecta su propósito con el siguiente paso real."""
    topics = _PAGE_TOPICS.get(page, set())
    for item in _daily_plan(state):
        if item["topic"] in topics:
            return {"do": item["do"], "why": item["why"]}
    return None


def _note_stats(page: str, state: dict) -> list[dict]:
    """Las 2-4 cifras clave de cada pantalla, presentadas POR Bynoesis (no una pared
    de KPIs muda). Solo datos ya leídos en el estado: cero consultas nuevas."""
    def chip(label, value, tone=""):
        return {"label": label, "value": value, "tone": tone}

    billing = state["billing"]
    pend = sum(p["total"] for p in state["pending"])
    late_total = sum(p["total"] for p in state["late"])
    if page == "facturas":
        chips = [chip("Facturado (mes)", _eur(billing.get("invoiced"))),
                 chip("Ha entrado (mes)", _eur(billing.get("collected")), "good"),
                 chip("Te deben", _eur(pend), "warn" if pend else "good")]
        if state["unbilled"]:
            chips.append(chip("Sin facturar", str(len(state["unbilled"])), "bad"))
        return chips
    if page == "cobros":
        return [chip("Te deben", _eur(pend), "warn" if pend else "good"),
                chip("Más de 7 días", _eur(late_total), "bad" if late_total else "good"),
                chip("Facturas", str(len(state["pending"])))]
    if page == "presupuestos" and state["quotes_sent"]:
        return [chip("Enviados", str(len(state["quotes_sent"]))),
                chip("En juego", _eur(sum(q["total"] for q in state["quotes_sent"])), "warn")]
    if page == "clientes":
        cs = state["clients"]
        active = sum(1 for c in cs if c.get("n_trabajos") or c.get("n_facturas"))
        return [chip("Clientes", str(len(cs))),
                chip("Con actividad", str(active)),
                chip("Facturado", _eur(sum(c.get("facturado") or 0 for c in cs)))]
    if page == "crm" and state["leads_due"]:
        return [chip("Para seguir hoy", str(len(state["leads_due"])), "warn")]
    if page == "documentos":
        chips = []
        if state["docs_pending"]:
            chips.append(chip("Por revisar", str(len(state["docs_pending"])), "warn"))
        if state["gestoria_open"]:
            chips.append(chip("Gestoría", str(len(state["gestoria_open"])), "warn"))
        if state["received_pending"]:
            chips.append(chip("Proveedor por pagar",
                              _eur(sum(r["total"] for r in state["received_pending"])), "warn"))
        return chips
    if page == "costes":
        chips = [chip("Gastos (mes)", _eur(billing.get("expenses")))]
        if state["received_pending"]:
            chips.append(chip("Proveedor por pagar",
                              _eur(sum(r["total"] for r in state["received_pending"])), "warn"))
        return chips
    if page == "agenda" and state["agenda"]:
        return [chip("Trabajos hoy", str(len(state["agenda"])))]
    if page == "proyectos":
        active = [p for p in state.get("projects", []) if p.get("status") != "terminado"]
        if active:
            margin = sum(p.get("margin") or 0 for p in active)
            return [chip("Activos", str(len(active))),
                    chip("Margen disponible", _eur(margin),
                         "bad" if margin < 0 else "good")]
    return []


def page_brief(business_id: int, page: str) -> dict | None:
    """El parte de sección: la figura de Bynoesis en cada pantalla — su lectura en
    primera persona, las cifras clave que la sostienen y la puerta para pedirle
    que lo explique. Una sola pieza en toda la app; resiliente como page_note."""
    if page == "resumen" or page not in _PAGE_HINTS:
        return None
    try:
        state = _business_state(business_id)
    except Exception:  # noqa: BLE001
        log.exception("page_brief falló para %s en %s", page, business_id)
        return {"text": f"Aquí tienes {_PAGE_HINTS[page]}.", "stats": [],
                "ask": _PAGE_ASK.get(page), "prompts": _PAGE_PROMPTS.get(page, []),
                "focus": None}
    text = page_note(business_id, page, state)
    if not text:
        return None
    try:
        stats = _note_stats(page, state)
    except Exception:  # noqa: BLE001 — las cifras nunca tumban la lectura
        log.exception("_note_stats falló para %s en %s", page, business_id)
        stats = []
    return {"text": text, "stats": stats, "ask": _PAGE_ASK.get(page),
            "prompts": _PAGE_PROMPTS.get(page, []),
            "focus": _page_focus(page, state)}


_LAST_CLIENT_RE = re.compile(
    r"^(?:(?:el|al|la|mi|mis)\s+)?ultim[oa]s?\s+client[ea]s?\b"
)


def _resolve_last_client(business_id: int, args: dict) -> str | None:
    """Sustituye «el último cliente» por su ficha real; nunca crea esa ficha.

    Devuelve una respuesta cuando no hay a quién referirse.
    """
    if not _LAST_CLIENT_RE.match(nlu._norm(str(args.get("cliente") or ""))):
        return None
    latest = db.list_invoices(business_id, limit=1)
    client = db.get_client(latest[0]["client_id"], business_id) if latest else None
    if not client:
        clients = db.list_clients(business_id)
        client = max(clients, key=lambda c: c["id"]) if clients else None
    if not client:
        return ("Aún no tienes clientes guardados. Dime su nombre y lo preparo; "
                "no he creado nada.")
    args["cliente"] = client["name"]
    return None


def _full_invoice_offer(business_id: int, args: dict, channel: str) -> dict | None:
    """Un ticket por encima del límite se reconduce a factura completa en borrador."""
    business = db.get_business(business_id) or {}
    base = float(args.get("base") or 0)
    if args.get("importe_incluye_iva"):
        gross = base
    else:
        rate = args.get("iva")
        rate = float(business.get("default_vat") or 21) if rate is None else float(rate)
        gross = round(base * (1 + rate / 100), 2)
    if db._fits_simplified_invoice(gross):
        return None
    amount = _eur(gross) + (" IVA incluido" if args.get("importe_incluye_iva") else "")
    lines = [
        f"No puedo hacerlo como ticket: un ticket (factura simplificada) solo vale "
        f"hasta 400 € IVA incluido y este es de **{_eur(gross)}**. Es la norma de "
        "facturación, no una limitación de Bynoesis. No he creado nada.",
        "",
    ]
    client = str(args.get("cliente") or "").strip()
    if not client:
        lines.append(
            "Lo que sí puedo hacer es prepararlo como **factura completa**. "
            f"Dime a qué cliente, por ejemplo: «factura a Marta por reforma {amount}»."
        )
        return {"reply": "\n".join(lines), "source": "local", "invoice_ids": []}
    lines.append(
        f"Lo que sí puedo hacer: preparar una **factura completa** para {client} "
        f"por {amount}, en borrador."
    )
    if channel == "whatsapp":
        lines.append("Responde **SÍ** y la dejo lista. Para emitirla te pediré "
                     "después el NIF y la dirección del cliente.")
    else:
        lines.append(f"Escribe «factura a {client} por {args.get('concepto') or 'Servicio'} "
                     f"{amount}» y la dejo lista.")
    return {
        "reply": "\n".join(lines),
        "source": "local",
        "invoice_ids": [],
        "full_invoice_offer": {**args, "tipo_factura": "F1"},
    }


def _ai_unavailable_reply(channel: str) -> str:
    examples = [
        "• «Factura a Marta por reparar la caldera 120 euros»",
        "• «Gasté 45 euros en gasolina»",
        "• «¿Quién me debe?»",
    ]
    if channel == "whatsapp":
        examples[1:1] = [
            "• «Últimos 3 tickets en PDF»",
            "• «Pásame la factura 12 en PDF»",
        ]
    return (
        "No he sabido interpretar esa frase y ahora mismo la IA avanzada no está "
        "disponible. No he guardado ni enviado nada.\n\n"
        "Estas órdenes funcionan siempre:\n" + "\n".join(examples)
    )


def _handle(
    business_id: int,
    message: str,
    page: str | None = None,
    *,
    channel: str = "web",
    actor_phone: str | None = None,
) -> dict:
    norm = nlu._norm(message)  # reutiliza el normalizador local; no sale del servidor.
    refusal = nlu.safety_refusal(message)
    if refusal:
        return {"reply": refusal, "source": "local"}
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

    communication = internal_brain.prepare_response(
        business_id,
        message,
        channel=channel,
        actor_phone=actor_phone,
    )
    if communication:
        return communication

    parsed = nlu.parse(message)

    if parsed:
        tool, args = parsed
        if tool == nlu.NEED_REVIEW:
            return {"reply": args["reply"], "source": "local"}
        if tool == "registrar_pago" and not config.ASSISTANT_REVIEW_ENABLED:
            return {"reply": "Abre la factura en Facturas para revisar y registrar el cobro. No he cambiado su estado.", "source": "local"}
        if tool == nlu.HELP:
            return {"reply": _coach_reply(business_id, message), "source": "local"}
        if tool == nlu.NEED_INVOICE:
            return {
                "reply": "Claro. Dime **cliente, concepto e importe**; por ejemplo: "
                         "«factura a Ana por reparar el termo 120 euros».",
                "source": "local",
                "clarification_kind": "invoice",
            }
        if tool == nlu.NEED_USER_INVITE:
            return {
                "reply": "Para dar acceso a alguien necesito su correo y el rol. "
                         "Hazlo desde Equipo para que reciba una invitación segura; "
                         "no crearé una contraseña ni daré permisos desde un mensaje incompleto.",
                "source": "local",
            }
        if tool == "__need_date__":
            return {"reply": "Te lo puedo agendar, pero me falta el día. Dímelo como lo dirías por WhatsApp: "
                             "**mañana por la mañana**, **el jueves a las 10** o "
                             "**el lunes por la tarde en Badalona**.", "source": "local"}
        if (tool in {"crear_factura", "crear_presupuesto"}
                and "iva incluido" in norm
                and not args.get("importe_incluye_iva")):
            business = db.get_business(business_id) or {}
            rate = float(business.get("default_vat") or 21)
            args["base"] = round(float(args["base"]) / (1 + rate / 100), 2)
            args["iva"] = rate
        if tool in {"crear_factura", "crear_presupuesto", "agendar_trabajo"}:
            unresolved = _resolve_last_client(business_id, args)
            if unresolved:
                return {"reply": unresolved, "source": "local"}
        if tool == "crear_factura" and args.get("tipo_factura") == "F2":
            offer = _full_invoice_offer(business_id, args, channel)
            if offer:
                return offer
        ledger_channel = "whatsapp" if channel == "whatsapp" else "web"
        result = json.loads(
            run_tool(tool, args, business_id, channel=ledger_channel)
        )
        return {"reply": nlu.format_reply(tool, result), "source": "local"}

    # Marco común para el segundo nivel, sea privado o externo.
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
    level = business.get("explanation_level") or "claro"
    if level == "directo":
        prefix += "[Responde de forma profesional y muy breve; ve directo a la acción] "
    elif level == "detallado":
        prefix += "[Explica el porqué y añade el detalle numérico útil sin perder claridad] "
    else:
        prefix += "[Explica con palabras sencillas y acompaña cada número con su significado] "

    # Si existe un servicio privado, tiene prioridad y no consume créditos externos.
    if ai_adapter.local_available():
        from ..agent import LocalNoesisAgent, PartialAgentExecutionError
        try:
            with _agents_lock:
                local_agent = _local_agents.get(business_id)
                if local_agent is None:
                    local_agent = LocalNoesisAgent(business_id)
                    _local_agents[business_id] = local_agent
            return {
                "reply": local_agent.send(prefix + message),
                "source": "ia_local",
            }
        except Exception as exc:  # noqa: BLE001 - continúa con el respaldo externo
            log.exception("La IA privada falló para el negocio %s.", business_id)
            try:
                db.record_integration_result(
                    business_id, "ai_local", type(exc).__name__
                )
            except Exception:  # noqa: BLE001
                pass
            if isinstance(exc, PartialAgentExecutionError):
                return {
                    "reply": "La operación pudo quedar preparada antes de que la IA "
                             "se interrumpiera. Revisa la actividad reciente; no la "
                             "voy a repetir automáticamente.",
                    "source": "local",
                }

    # Respaldo externo, solo si está configurado y consentido. El proveedor
    # OpenAI-compatible barato se intenta antes de Anthropic. Ambos comparten una
    # única reserva por mensaje, incluso cuando hay fallback entre proveedores.
    external_available = bool(
        ai_adapter.external_available() or config.ANTHROPIC_API_KEY
    )
    if external_available and db.integration_enabled(
        business_id, "ai_external", available=True
    ):
        credit_provider = (
            config.COMPAT_AI_PROVIDER
            if ai_adapter.external_available()
            else "anthropic"
        )
        credit = db.claim_ai_credit(
            business_id, provider=credit_provider or "compatible"
        )
        if not credit["allowed"]:
            return {
                "reply": _coach_reply(business_id, message) + "\n\n"
                         "Has usado las consultas avanzadas incluidas este mes. "
                         "Las órdenes habituales y el cerebro local siguen activos.",
                "source": "local",
            }
        if ai_adapter.external_available():
            from ..agent import CompatibleNoesisAgent, PartialAgentExecutionError
            try:
                with _agents_lock:
                    compatible_agent = _compatible_agents.get(business_id)
                    if compatible_agent is None:
                        compatible_agent = CompatibleNoesisAgent(business_id)
                        _compatible_agents[business_id] = compatible_agent
                return {
                    "reply": compatible_agent.send(prefix + message),
                    "source": "ia_compatible",
                }
            except Exception as exc:  # noqa: BLE001 - Anthropic aún puede responder
                log.exception(
                    "La IA compatible falló para el negocio %s.", business_id
                )
                try:
                    db.record_integration_result(
                        business_id, "ai_external", type(exc).__name__
                    )
                except Exception:  # noqa: BLE001
                    pass
                if isinstance(exc, PartialAgentExecutionError):
                    return {
                        "reply": "La operación pudo quedar preparada antes de que "
                                 "la IA se interrumpiera. Revisa la actividad "
                                 "reciente; no la voy a repetir automáticamente.",
                        "source": "local",
                    }

        if config.ANTHROPIC_API_KEY:
            from ..agent import NoesisAgent, PartialAgentExecutionError
            with _agents_lock:
                agent = _agents.get(business_id)
                if agent is None:
                    # Haiku paga solo lo que no resolvieron las capas anteriores.
                    agent = NoesisAgent(business_id, model=config.FALLBACK_MODEL)
                    _agents[business_id] = agent
            try:
                return {"reply": agent.send(prefix + message), "source": "ia"}
            except Exception as exc:  # noqa: BLE001
                log.exception(
                    "El proveedor de IA falló para el negocio %s.", business_id
                )
                try:
                    db.record_integration_result(
                        business_id, "ai_external", type(exc).__name__
                    )
                except Exception:  # noqa: BLE001
                    pass
                if isinstance(exc, PartialAgentExecutionError):
                    return {
                        "reply": "La operación pudo quedar preparada antes de que "
                                 "la IA se interrumpiera. Revisa la actividad "
                                 "reciente antes de intentarlo otra vez.",
                        "source": "local",
                    }
        return {"reply": _ai_unavailable_reply(channel), "source": "local"}

    from .. import learning
    if learning.enabled():
        return {"reply": "No he podido identificar una operación concreta y no he guardado cambios. "
                "¿Quieres preparar una factura, registrar un gasto, agendar un trabajo o consultar datos? "
                "Dime la orden completa empezando por «corregir:»; por ejemplo, «corregir: gasté 35 euros en gasolina».",
                "source": "local", "needs_clarification": True}
    return {"reply": _coach_reply(business_id, message), "source": "local"}


_READ_ONLY_TOOLS = {
    "ver_control_noesis",
    "ver_agenda",
    "ver_cobros_pendientes",
    "ver_proyectos",
    "ver_equipo",
    "ver_documentos_pendientes",
    "ver_solicitudes_gestoria",
    "resumen_negocio",
    "listar_clientes",
}


def handle_read_only(
    business_id: int, message: str, page: str | None = None
) -> dict:
    """Conversación segura para demos: consulta datos sin persistir ni ejecutar.

    No pasa por agentes privados o externos porque una herramienta de un agente
    podría escribir. Tampoco guarda historial: la cuenta comercial sigue siendo
    reproducible y de solo lectura.
    """
    norm = nlu._norm(message)
    if page and any(fragment in norm for fragment in (
        "esta pagina", "que veo aqui", "donde estoy", "que significa esto",
        "explica esta", "explicame esta", "que es esto",
    )):
        briefing = page_briefing(business_id, page)
        if briefing:
            return {"reply": briefing, "source": "local"}
    if any(fragment in norm for fragment in (
        "sin facturar", "pendiente de facturar", "por facturar",
        "que me falta facturar", "trabajos sin cobrar",
    )):
        return {"reply": _unbilled_reply(business_id), "source": "local"}
    if any(fragment in norm for fragment in (
        "que harias", "prioridad", "aconsej", "recomiend", "diagnostico",
        "como lo ves", "mente", "piensa", "plan", "que hago",
        "por donde empiezo", "que toca",
    )):
        return {"reply": _coach_reply(business_id, message), "source": "local"}

    parsed = nlu.parse(message)
    if parsed:
        tool, args = parsed
        if tool == nlu.HELP:
            return {"reply": nlu.help_text(), "source": "local"}
        if tool == "__need_date__":
            return {
                "reply": (
                    "Te lo podría agendar, pero falta el día. En tu cuenta propia "
                    "podrás decirlo como por WhatsApp: **mañana por la mañana**, "
                    "**el jueves a las 10** o **el lunes por la tarde**."
                ),
                "source": "local",
            }
        if tool in _READ_ONLY_TOOLS:
            result = json.loads(run_tool(tool, args, business_id))
            return {"reply": nlu.format_reply(tool, result), "source": "local"}
        return {
            "reply": (
                "Esta demostración es de solo lectura: puedo enseñarte el resultado, "
                "pero no guardar cambios. Prueba **¿Qué tengo hoy?**, **¿Quién me debe?** "
                "o **Dame el resumen del mes**. En tu cuenta, Bynoesis dejará la acción "
                "preparada para que la revises; nunca enviará dinero o documentación "
                "fiscal sin tu confirmación."
            ),
            "source": "local",
        }
    return {"reply": _coach_reply(business_id, message), "source": "local"}


def handle(
    business_id: int,
    message: str,
    page: str | None = None,
    *,
    channel: str = "web",
    actor_phone: str | None = None,
    actor_id: str | None = None,
) -> dict:
    """Entrada común del acompañante: responde y conserva la relación.

    El guardado es deliberadamente resiliente: una incidencia en el historial no
    puede impedir que el autónomo consulte o ejecute una tarea habitual.
    """
    try:
        db.add_assistant_message(
            business_id, "user", message, channel=channel, page=page,
        )
        db.record_product_event(
            business_id, "assistant_message", f"channel={channel};page={page or ''}"
        )
    except Exception:  # noqa: BLE001
        log.exception("No se pudo guardar la entrada del asistente para %s.", business_id)
    from .. import action_review, learning
    enabled = config.ASSISTANT_REVIEW_ENABLED
    actor = f"wa:{actor_phone}" if channel == "whatsapp" else f"web:{actor_id or 'owner'}"
    turn = {"message": message, "original": message}
    if learning.enabled():
        try:
            turn = learning.prepare(business_id, actor, message)
        except Exception:  # noqa: BLE001 - no ejecutar una interpretación si la memoria falla
            return {"reply": "No he podido revisar la memoria. No he ejecutado nada; escribe la orden completa de nuevo.", "source": "local"}
    message = turn["message"]
    if "reply" in turn and enabled:
        db.clear_pending_action(business_id, actor)
    result = {"reply": turn["reply"], "source": "local", "needs_clarification": turn.get("needs_clarification", False)} if "reply" in turn else (
        action_review.respond(business_id, actor, message) if enabled else None)
    if result is None:
        if enabled:
            # Cualquier nueva orden invalida la anterior, incluso si la corrección
            # es incompleta. Un SÍ posterior nunca confirma datos antiguos.
            db.clear_pending_action(business_id, actor)
            if nlu._norm(message).startswith("corregir:"):
                message = message.split(":", 1)[1].strip()
        state = {"actor": actor}
        token = action_review.context.set(state if enabled else None)
        try:
            if turn.get("tool_call"):
                call = turn["tool_call"]
                result = json.loads(run_tool(call["name"], call["args"], business_id, channel=channel))
            else:
                from ..tools import execution_receipts
                receipts = []
                receipt_token = execution_receipts.set(receipts)
                try:
                    result = _handle(business_id, message, page, channel=channel, actor_phone=actor_phone)
                finally:
                    execution_receipts.reset(receipt_token)
                invoice_receipts = [r for r in receipts if r["business_id"] == business_id
                                    and r["tool"] in {"crear_factura", "preparar_factura_trabajo"}]
                if invoice_receipts and not state.get("proposal"):
                    result["reply"] = "\n\n".join(
                        nlu.format_reply(r["tool"], r["result"]) for r in invoice_receipts
                    )
                    result["invoice_ids"] = [r["result"]["factura"]["id"]
                                             for r in invoice_receipts
                                             if r["result"].get("factura") and not r["result"].get("error")]
                elif str(result.get("source", "")).startswith("ia"):
                    reply_norm = nlu._norm(result.get("reply", ""))
                    if re.search(r"\b(factura|ticket|tiquet)\b", reply_norm) and re.search(
                        r"\b(emitid[oa]|emes[ao]?|emesa|guardad[oa]|guardat|cread[oa]|creat|"
                        r"preparad[oa]|preparat|registrad[oa]|registrat)\b", reply_norm
                    ) and not receipts:
                        result["reply"] = (
                            "No tengo una ejecución verificada de esa factura o ticket en este turno. "
                            "Indica su número para consultarlo, o cliente, concepto e importe para preparar un borrador."
                        )
                        result["invoice_ids"] = []
            if state.get("proposal"):
                result = {**state["proposal"], "source": "local"}
        finally:
            action_review.context.reset(token)
    if learning.enabled():
        if str(result.get("source", "")).startswith("ia") and not result.get("confirmation_required"):
            result["reply"] += "\n\nNo he guardado cambios ni enviado nada en esta respuesta."
        try:
            result = learning.finish(business_id, actor, turn, result)
        except Exception:  # noqa: BLE001 - un fallo al aprender jamás reintenta el negocio
            log.warning("No se pudo completar el aprendizaje; no se repite la operación.")
    try:
        db.add_assistant_message(
            business_id, "assistant", result.get("reply") or "",
            channel=channel, page=page, source=result.get("source"),
        )
    except Exception:  # noqa: BLE001
        log.exception("No se pudo guardar la respuesta del asistente para %s.", business_id)
    return result
