"""Paginas HTML de Noesis."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from ... import config, db, verifactu_client
from ...adapters import billing as billing_adapter
from .. import whatsapp
from ..deps import HERE, TEMPLATES

router = APIRouter()

_PAGES = {
    "resumen": "Inicio", "tesoreria": "Tesorería", "analisis": "Análisis",
    "ingresos": "Ingresos", "costes": "Costes", "presupuestos": "Presupuestos",
    "facturas": "Facturas", "cobros": "Cobros", "impuestos": "Impuestos",
    "agenda": "Trabajos", "proyectos": "Proyectos", "equipo": "Equipo", "clientes": "Clientes",
    "crm": "CRM", "productos": "Productos y servicios",
    "documentos": "Documentos",
    "asistente": "Asistente", "ajustes": "Ajustes",
}


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    bid = request.session.get("bid")
    return TEMPLATES.TemplateResponse(request, "landing.html", {
        "business_id": bid,
        "site_active": "inicio",
        "prices": billing_adapter.PLAN_PRICES,
        "annual_prices": billing_adapter.PLAN_ANNUAL_PRICES,
        "annual_savings": billing_adapter.PLAN_ANNUAL_SAVINGS,
        "google_oauth_available": config.google_oauth_available(),
    })


@router.get("/app")
def app_entry(request: Request):
    """Punto de entrada de la app instalada (PWA): directo al panel o al login."""
    bid = request.session.get("bid")
    target = f"/b/{bid}/resumen" if bid else "/login"
    return RedirectResponse(target, status_code=303)


# Apartados del sitio publico: cada seccion es su propia pagina.
_SITE_PAGES = {
    "producto": "site_producto.html",
    "precios": "site_precios.html",
    "equipo": "site_equipo.html",
    "preguntas": "site_preguntas.html",
}


@router.get("/producto", response_class=HTMLResponse)
@router.get("/precios", response_class=HTMLResponse)
@router.get("/equipo", response_class=HTMLResponse)
@router.get("/preguntas", response_class=HTMLResponse)
def site_page(request: Request):
    section = request.url.path.strip("/") or "producto"
    return TEMPLATES.TemplateResponse(request, _SITE_PAGES[section], {
        "site_active": section,
        "business_id": request.session.get("bid"),
        "prices": billing_adapter.PLAN_PRICES,
        "annual_prices": billing_adapter.PLAN_ANNUAL_PRICES,
        "annual_savings": billing_adapter.PLAN_ANNUAL_SAVINGS,
    })


@router.get("/sw.js")
def service_worker():
    # Servido desde la raiz para que el service worker controle toda la app (scope /).
    return Response(content=(HERE / "static" / "sw.js").read_text(encoding="utf-8"),
                    media_type="application/javascript")


@router.get("/privacidad", response_class=HTMLResponse)
def privacidad(request: Request):
    return TEMPLATES.TemplateResponse(request, "privacidad.html", {
        "compat_ai_legal_name": config.COMPAT_AI_LEGAL_NAME,
        "compat_ai_region": config.COMPAT_AI_REGION,
    })


@router.get("/terminos", response_class=HTMLResponse)
def terminos(request: Request):
    return TEMPLATES.TemplateResponse(request, "terminos.html", {})


@router.get("/aviso-legal", response_class=HTMLResponse)
def aviso_legal(request: Request):
    return TEMPLATES.TemplateResponse(request, "aviso-legal.html", {})


@router.get("/cookies", response_class=HTMLResponse)
def cookies(request: Request):
    return TEMPLATES.TemplateResponse(request, "cookies.html", {})


@router.get("/encargado-tratamiento", response_class=HTMLResponse)
def encargado_tratamiento(request: Request):
    return TEMPLATES.TemplateResponse(request, "encargado-tratamiento.html", {
        "compat_ai_legal_name": config.COMPAT_AI_LEGAL_NAME,
        "compat_ai_region": config.COMPAT_AI_REGION,
    })


@router.get("/cumplimiento", response_class=HTMLResponse)
def cumplimiento(request: Request):
    return TEMPLATES.TemplateResponse(request, "cumplimiento.html", {})


@router.get("/b/{business_id}/suscripcion", response_class=HTMLResponse)
def subscription_page(
    request: Request, business_id: int, status: str = "", plan: str = "",
    billing: str = "",
):
    # Definida antes de la ruta generica /b/{id}/{page} para que no la capture esta.
    biz = db.get_business(business_id)
    preferred_plan = (
        plan if plan in billing_adapter.PLAN_PRICES
        else str(request.session.get("signup_plan") or "pro")
    )
    preferred_billing = (
        billing if billing in {"monthly", "annual"}
        else str(request.session.get("signup_billing") or "monthly")
    )
    return TEMPLATES.TemplateResponse(request, "suscripcion.html", {
        "business": biz, "active": "ajustes", "page_title": "Suscripción",
        "status": status, "billing_on": billing_adapter.get_provider().available(),
        "prices": billing_adapter.PLAN_PRICES,
        "annual_prices": billing_adapter.PLAN_ANNUAL_PRICES,
        "annual_savings": billing_adapter.PLAN_ANNUAL_SAVINGS,
        "preferred_plan": preferred_plan,
        "preferred_billing": preferred_billing,
        "subscription_read_only": not db.subscription_allows_access(biz),
    })


@router.get("/b/{business_id}/{page}", response_class=HTMLResponse)
def page(request: Request, business_id: int, page: str):
    if page not in _PAGES:
        return RedirectResponse(f"/b/{business_id}/resumen")
    biz = db.get_business(business_id)
    if not biz:
        return RedirectResponse("/login")
    from .. import chat

    context = {
        "business": biz,
        "active": page,
        "page_title": _PAGES[page],
        "activation": db.activation_snapshot(business_id),
        # El parte de sección: la figura de Noesis en cada pantalla — lectura,
        # cifras clave y puerta al acompañante (None en el Home, que tiene el suyo).
        "page_brief": chat.page_brief(business_id, page),
        "subscription_read_only": not db.subscription_allows_access(biz),
    }
    if page == "resumen":
        layout = db.resolve_panel_layout(biz)
        context["panel_order"] = layout["order"]
        context["panel_hidden"] = layout["hidden"]
        context["panel_blocks"] = db.PANEL_BLOCKS
        context["briefing"] = chat.daily_briefing(business_id)
    if page == "agenda":
        token = biz.get("calendar_token")
        context["calendar_feed_url"] = (
            f"{config.BASE_URL}/cal/{token}.ics" if token else ""
        )
    if page == "cobros":
        context["bank_transactions"] = db.list_bank_transactions(
            business_id, limit=50
        )
        context["bank_summary"] = db.bank_reconciliation_summary(business_id)
    if (
        page == "ajustes"
        and biz.get("whatsapp_status") != "conectado"
        and db.subscription_allows_access(biz)
    ):
        context["wa"] = whatsapp.start_link(business_id)
    if page == "ajustes":
        ai_setting = db.integration_setting(business_id, "ai_external") or {}
        context["ai_external_preference"] = (
            ai_setting.get("mode") != "disabled"
        )
        context["assistant_memories"] = db.list_memories(business_id)
        context["automation_permissions"] = db.automation_catalog(business_id)
        context["automation_mode_labels"] = db.AUTOMATION_MODE_LABELS
        context["assistant_actions"] = db.list_assistant_actions(
            business_id, limit=8
        )
        context["gestoria_deliveries"] = db.list_gestoria_deliveries(
            business_id, limit=6
        )
        context["wa_reports"] = db.resolve_whatsapp_reports(
            biz.get("whatsapp_reports")
        )
        if biz.get("gestoria_token"):
            context["gestoria_link"] = (
                f"{config.BASE_URL}/g/{biz['gestoria_token']}"
            )
        context["verifactu_errors"] = db.verifactu_configuration_errors()
        context["verifactu_ready"] = not context["verifactu_errors"]
        context["verifactu_transmission_enabled"] = (
            verifactu_client.is_enabled()
        )
        context["verifactu_aeat_env"] = config.VERIFACTU_AEAT_ENV
        queue = db.list_verifactu_outbox(business_id, limit=500)
        context["verifactu_queue"] = {
            status: sum(1 for item in queue if item["status"] == status)
            for status in (
                "pendiente", "enviado", "aceptado",
                "aceptado_con_errores", "rechazado",
            )
        }
    if page == "facturas":
        context["concept_suggestions"] = db.invoice_concept_suggestions(biz)
    if page == "proyectos":
        context["clients"] = db.list_clients(business_id)
        context["workers"] = db.list_workers(business_id, include_inactive=False)
    if page == "costes":
        context["projects"] = [
            project for project in db.list_projects(business_id)
            if project.get("status") != "terminado"
        ]
    if page == "asistente":
        from ...adapters import transcription

        context["voice_on"] = transcription.available()
    return TEMPLATES.TemplateResponse(request, f"{page}.html", context)
