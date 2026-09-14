"""Paginas HTML de Bynoesis."""

from __future__ import annotations

import logging
import json
import threading
import time
from collections import deque
from datetime import date
from xml.sax.saxutils import escape

from fastapi import APIRouter, Request
from fastapi.responses import (
    FileResponse, HTMLResponse, RedirectResponse, Response,
)
from starlette.concurrency import run_in_threadpool

from ... import config, db, verifactu_client
from ...adapters import billing as billing_adapter
from .. import whatsapp
from ..deps import HERE, TEMPLATES
from ..public_marketing import PUBLIC_EVENTS, PUBLIC_EVENT_PAGES, marketing_context

router = APIRouter()
log = logging.getLogger("noesis.billing")

# Techo global por proceso, sin IP ni huella de visitante. Analítica orientativa.
_public_event_times: deque = deque()
_public_event_lock = threading.Lock()


@router.post("/public/event", include_in_schema=False)
async def public_event(request: Request):
    origin = request.headers.get("origin", "")
    if origin not in {config.BASE_URL.rstrip("/"), str(request.base_url).rstrip("/")}:
        return Response(status_code=403)
    if request.headers.get("sec-fetch-site", "same-origin") != "same-origin":
        return Response(status_code=403)
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        return Response(status_code=415)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 256:
            return Response(status_code=413)
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return Response(status_code=400)
    if (not isinstance(payload, dict) or set(payload) != {"event", "page"}
            or not isinstance(payload["event"], str) or not isinstance(payload["page"], str)
            or payload["event"] not in PUBLIC_EVENTS or payload["page"] not in PUBLIC_EVENT_PAGES):
        return Response(status_code=400)
    with _public_event_lock:
        now = time.monotonic()
        while _public_event_times and _public_event_times[0] < now - 60:
            _public_event_times.popleft()
        if len(_public_event_times) >= 300:
            return Response(status_code=429)
        _public_event_times.append(now)
    try:
        await run_in_threadpool(
            db.record_page_view, f"@event:{payload['page']}:{payload['event']}"
        )
    except Exception:
        # Una medición perdida no debe impedir navegar ni reservar.
        log.warning("public_event_not_counted")
    return Response(status_code=204)

_PAGES = {
    "resumen": "Inicio", "tesoreria": "Tesorería", "analisis": "Análisis",
    "ingresos": "Ingresos", "costes": "Costes", "presupuestos": "Presupuestos",
    "facturas": "Facturas", "cobros": "Cobros", "impuestos": "Impuestos",
    "agenda": "Trabajos", "proyectos": "Proyectos", "equipo": "Equipo", "clientes": "Clientes",
    "crm": "CRM", "productos": "Productos y servicios",
    "oficios": "Plantillas por oficio",
    "documentos": "Documentos",
    "asistente": "Asistente", "ajustes": "Ajustes",
}


def _legal_context(request: Request) -> dict:
    """Datos legales públicos; nunca incluye credenciales ni valores internos.

    Lleva también la sesión porque estas páginas comparten cabecera con el resto
    del sitio: quien ya ha entrado debe ver su panel, no una invitación a entrar.
    """
    return {
        "business_id": request.session.get("bid"),
        "legal_name": config.LEGAL_NAME,
        "legal_nif": config.LEGAL_NIF,
        "legal_address": config.LEGAL_ADDRESS,
        "legal_email": config.LEGAL_EMAIL or config.PUBLIC_CONTACT_EMAIL,
        "legal_registry": config.LEGAL_REGISTRY,
        "legal_ready": config.legal_publication_ready(),
        "legal_document_version": config.LEGAL_DOCUMENT_VERSION,
        "smtp_provider_name": (
            "Brevo" if config.BREVO_API_KEY else config.SMTP_PROVIDER_NAME
        ),
        "smtp_provider_region": "" if config.BREVO_API_KEY else config.SMTP_PROVIDER_REGION,
        "compat_ai_legal_name": config.COMPAT_AI_LEGAL_NAME,
        "compat_ai_region": config.COMPAT_AI_REGION,
        "anthropic_enabled": bool(config.ANTHROPIC_API_KEY),
        "groq_enabled": bool(config.GROQ_API_KEY),
        "google_oauth_enabled": config.google_oauth_available(),
        "stripe_enabled": bool(config.STRIPE_SECRET_KEY),
        "backup_provider_name": config.BACKUP_S3_PROVIDER_NAME,
        "backup_provider_region": config.BACKUP_S3_DATA_REGION,
    }


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    bid = request.session.get("bid")
    return TEMPLATES.TemplateResponse(request, "landing.html", {
        **marketing_context("inicio", signup_available=TEMPLATES.env.globals["public_signup_available"]),
        "business_id": bid,
        "site_active": "inicio",
        "prices": billing_adapter.PLAN_PRICES,
        "annual_prices": billing_adapter.PLAN_ANNUAL_PRICES,
        "annual_savings": billing_adapter.PLAN_ANNUAL_SAVINGS,
        "google_oauth_available": config.google_oauth_available(),
    })


@router.get("/app")
def app_entry(request: Request):
    """Punto de entrada de la app instalada: panel activo o selector de acceso."""
    bid = request.session.get("bid")
    if bid:
        target = f"/b/{bid}/resumen"
    elif request.session.get("gid"):
        target = "/gestoria"
    else:
        target = "/acceso"
    return RedirectResponse(target, status_code=303)


@router.get("/acceso", response_class=HTMLResponse)
def access_entry(request: Request):
    """Puerta común que explica cada espacio sin mezclar identidades ni permisos."""
    bid = request.session.get("bid")
    if bid:
        return RedirectResponse(f"/b/{bid}/resumen", status_code=303)
    if request.session.get("gid"):
        return RedirectResponse("/gestoria", status_code=303)
    return TEMPLATES.TemplateResponse(request, "access_entry.html", {})


# Apartados del sitio publico: cada seccion es su propia pagina.
_SITE_PAGES = {
    "autonomos": "site_autonomos.html",
    "gestorias": "site_gestorias.html",
    "precios": "site_precios.html",
    "equipo": "site_equipo.html",
    "preguntas": "site_preguntas.html",
    "contacto": "site_contacto.html",
}


# Páginas que deben salir en buscadores. El panel, el acceso y los portales
# privados quedan fuera a propósito: no aportan nada en una búsqueda y no
# queremos que se indexen enlaces con datos de clientes.
_INDEXABLES = (
    "/",
    "/autonomos",
    "/gestorias",
    "/precios",
    "/solicitar-acceso",
    "/contacto",
    "/preguntas",
    "/equipo",
    "/cumplimiento",
    "/privacidad",
    "/terminos",
    "/aviso-legal",
    "/cookies",
    "/encargado-tratamiento",
)
INDEXABLE_PATHS = frozenset(_INDEXABLES)


@router.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Navegadores y agregadores antiguos piden esta ruta fija; se sirve el SVG."""
    return FileResponse(
        HERE / "static" / "noesis-mark.svg", media_type="image/svg+xml"
    )


@router.get("/robots.txt", include_in_schema=False)
def robots():
    """Qué puede rastrear un buscador y dónde está el mapa del sitio."""
    lineas = [
        "User-agent: *",
        # Nada de esto tiene sentido en un buscador y algunos llevan datos privados.
        "Disallow: /b/",
        "Disallow: /api/",
        "Disallow: /admin",
        "Disallow: /p/",
        "Disallow: /g/",
        "Disallow: /t/",
        # El fin de línea evita que la zona privada /gestoria bloquee por prefijo
        # la página pública /gestorias. Login se deja rastrear para que lea noindex.
        "Disallow: /gestoria$",
        "Allow: /gestoria/login$",
        "Disallow: /gestoria/",
        "Disallow: /webhook/",
        "Disallow: /health",
        "Disallow: /ready",
        "",
        f"Sitemap: {config.BASE_URL}/sitemap.xml",
        "",
    ]
    return Response("\n".join(lineas), media_type="text/plain")


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap():
    """Mapa del sitio con las páginas públicas que sí queremos indexadas."""
    urls = "".join(
        f"<url><loc>{escape(config.BASE_URL + ruta)}</loc></url>"
        for ruta in _INDEXABLES
    )
    cuerpo = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{urls}</urlset>"
    )
    return Response(cuerpo, media_type="application/xml")


@router.get("/llms.txt", include_in_schema=False)
def llms_txt():
    """Ficha en Markdown para asistentes de IA, según la convención llms.txt.

    Se construye con el catálogo, el contacto y el estado del alta vigentes: una
    cifra copiada a mano acabaría contradiciendo a /precios. Solo resume lo que la
    web pública ya afirma; no añade clientes, valoraciones ni certificaciones.
    """
    base = config.BASE_URL.rstrip("/")
    planes = "\n".join(
        f"- {plan['name']}: {plan['price']} € al mes + IVA, o "
        f"{billing_adapter.PLAN_ANNUAL_PRICES[clave]} € al año + IVA."
        for clave, plan in billing_adapter.PLANS.items()
    )
    if TEMPLATES.env.globals["public_signup_available"]:
        acceso = f"Prueba de {config.TRIAL_DAYS} días desde {base}/precios."
    else:
        acceso = (
            "El alta pública está cerrada durante el piloto acompañado; el acceso "
            f"se solicita en {base}/solicitar-acceso."
        )
    texto = f"""# Bynoesis

> Bynoesis es un software de gestión por WhatsApp para autónomos y pequeños negocios de servicios en España. Prepara facturas y presupuestos, guarda tickets y documentos y ayuda a llevar clientes, agenda y cobros. El titular revisa y confirma antes de emitir, enviar o mover dinero.

Bynoesis es un producto independiente: no pertenece a WhatsApp ni a Meta. Funciona en castellano, catalán e inglés, con un panel web para revisar el detalle.

## Para quién

- Autónomos y microempresas de servicios de 1 a 10 personas: fontanería, electricidad, reformas, climatización, mantenimiento, limpieza y jardinería.
- Gestorías y asesorías que llevan la documentación de esos negocios.

## Qué hace

- Facturas y presupuestos a partir de un mensaje: cliente, concepto, IVA e IRPF en un borrador que el titular revisa antes de emitir.
- Documentos: tickets, facturas recibidas y PDF ordenados por empresa, año y trimestre.
- Cobros y agenda: facturas pendientes, recordatorios que el titular confirma y trabajos del día.
- Gestoría: espacio profesional para revisar varias empresas por período, pedir lo que falta y consultar borradores fiscales orientativos.
- Equipo y proyectos (planes Negocio y Premium): fichaje, costes y margen por proyecto.

## Qué no hace

- No presenta impuestos ni sustituye a la gestoría.
- No emite, envía ni paga sin la confirmación del titular.
- Veri*Factu: el registro, la huella encadenada y el QR están preparados; la conexión con la AEAT se activa tras certificado y pruebas. Bynoesis no declara una certificación de la AEAT.

## Precios

{planes}

El pago anual da 12 meses de acceso por el precio de 11. {acceso}

## Páginas

- [Inicio]({base}/): cómo se gestiona un negocio por WhatsApp.
- [Autónomos]({base}/autonomos): un día de trabajo con Bynoesis.
- [Gestorías]({base}/gestorias): el espacio profesional para despachos.
- [Precios]({base}/precios): planes y qué incluye cada uno.
- [Preguntas frecuentes]({base}/preguntas): WhatsApp, Veri*Factu, datos y equipo.
- [Equipo]({base}/equipo): quién construye Bynoesis.
- [Contacto]({base}/contacto): demo con el equipo.
- [Cumplimiento]({base}/cumplimiento): dónde están los datos y cómo se protegen.

## Optional

- [Privacidad]({base}/privacidad)
- [Términos]({base}/terminos)
- [Aviso legal]({base}/aviso-legal)
- [Encargado del tratamiento]({base}/encargado-tratamiento)

## Contacto

- {config.PUBLIC_CONTACT_EMAIL}
"""
    return Response(texto, media_type="text/markdown")


@router.get("/producto", include_in_schema=False)
def producto_redirect():
    """La portada absorbió el contenido de Producto; los enlaces antiguos siguen vivos."""
    return RedirectResponse("/#como-funciona", status_code=301)


@router.get("/demo", include_in_schema=False)
def demo_redirect():
    """Las reservas viven ahora en Contáctanos."""
    return RedirectResponse("/contacto", status_code=301)


@router.get("/demo/cliente", include_in_schema=False)
def showcase_client_redirect():
    """Entrada estable al portal ficticio de la demostración comercial."""
    from ... import demo

    owner = db.get_user_by_email(demo.SHOWCASE_OWNER_EMAIL)
    business = db.get_business(owner["business_id"]) if owner else None
    if not business or not business.get("is_demo"):
        return RedirectResponse("/contacto", status_code=303)
    clients = db.list_clients(business["id"])
    portal_client = next(
        (
            client for client in clients
            if client["name"] == demo.SHOWCASE_PORTAL_CLIENT
        ),
        clients[0] if clients else None,
    )
    if not portal_client:
        return RedirectResponse("/contacto", status_code=303)
    token = db.get_or_create_portal_token(
        business["id"], portal_client["id"], ttl_days=3650
    )
    return RedirectResponse(f"/p/{token}", status_code=303)


@router.get("/precios", response_class=HTMLResponse)
@router.get("/autonomos", response_class=HTMLResponse)
@router.get("/gestorias", response_class=HTMLResponse)
@router.get("/equipo", response_class=HTMLResponse)
@router.get("/preguntas", response_class=HTMLResponse)
@router.get("/contacto", response_class=HTMLResponse)
def site_page(request: Request):
    section = request.url.path.strip("/") or "precios"
    return TEMPLATES.TemplateResponse(request, _SITE_PAGES[section], {
        **marketing_context(
            section,
            signup_available=TEMPLATES.env.globals["public_signup_available"],
            voice_available=TEMPLATES.env.globals["voice_available"],
            ocr_available=TEMPLATES.env.globals["ocr_available"],
        ),
        "site_active": section,
        "business_id": request.session.get("bid"),
        "prices": billing_adapter.PLAN_PRICES,
        "annual_prices": billing_adapter.PLAN_ANNUAL_PRICES,
        "annual_savings": billing_adapter.PLAN_ANNUAL_SAVINGS,
    })


@router.get("/bienvenida", response_class=HTMLResponse)
def bienvenida(request: Request):
    """Guía para quien ya tiene acceso: se enlaza desde el correo de invitación.

    No está en ``_INDEXABLES``: recibe ``noindex`` y no sale en el sitemap.
    """
    return TEMPLATES.TemplateResponse(request, "site_bienvenida.html", {
        "site_active": "bienvenida",
        "business_id": request.session.get("bid"),
        "welcome_video_id": config.WELCOME_VIDEO_ID,
    })


@router.get("/sw.js")
def service_worker():
    # Servido desde la raiz para que el service worker controle toda la app (scope /).
    return Response(content=(HERE / "static" / "sw.js").read_text(encoding="utf-8"),
                    media_type="application/javascript")


@router.get("/privacidad", response_class=HTMLResponse)
def privacidad(request: Request):
    return TEMPLATES.TemplateResponse(request, "privacidad.html", _legal_context(request))


@router.get("/terminos", response_class=HTMLResponse)
def terminos(request: Request):
    return TEMPLATES.TemplateResponse(request, "terminos.html", _legal_context(request))


@router.get("/aviso-legal", response_class=HTMLResponse)
def aviso_legal(request: Request):
    return TEMPLATES.TemplateResponse(request, "aviso-legal.html", _legal_context(request))


@router.get("/cookies", response_class=HTMLResponse)
def cookies(request: Request):
    return TEMPLATES.TemplateResponse(request, "cookies.html", _legal_context(request))


@router.get("/encargado-tratamiento", response_class=HTMLResponse)
def encargado_tratamiento(request: Request):
    return TEMPLATES.TemplateResponse(
        request, "encargado-tratamiento.html", _legal_context(request)
    )


@router.get("/cumplimiento", response_class=HTMLResponse)
def cumplimiento(request: Request):
    return TEMPLATES.TemplateResponse(request, "cumplimiento.html", _legal_context(request))


@router.get("/b/{business_id}/suscripcion", response_class=HTMLResponse)
def subscription_page(
    request: Request, business_id: int, status: str = "", plan: str = "",
    billing: str = "", feature: str = "",
):
    # Definida antes de la ruta generica /b/{id}/{page} para que no la capture esta.
    biz = db.get_business(business_id)
    if (
        biz
        and status in {"checkout_return", "portal_return"}
        and biz.get("subscription_status") in {
            "pending", "incomplete", "active", "trialing",
        }
    ):
        provider = billing_adapter.get_provider()
        snapshot = provider.subscription_snapshot(biz)
        evidence = billing_adapter.subscription_evidence(biz, snapshot)
        if evidence:
            try:
                biz = db.reconcile_stripe_subscription(
                    business_id, **evidence,
                )
                db.record_product_event(
                    business_id, "subscription_reconciled_after_checkout"
                )
            except ValueError as exc:
                log.warning(
                    "Stripe no pudo reconciliar la cuenta %s: %s",
                    business_id, exc,
                )
    active_plan = str((biz or {}).get("plan") or "")
    is_active_subscription = (biz or {}).get("subscription_status") in {
        "active", "trialing",
    }
    # El estado se queda en "trial" al vencer la prueba: la caducidad se deduce
    # de la fecha, igual que en db.subscription_allows_access. Sin esto la
    # pagina anuncia "En prueba" a una cuenta que ya esta en modo consulta.
    trial_ends = str((biz or {}).get("trial_ends_at") or "")
    trial_expired = bool(trial_ends) and trial_ends < date.today().isoformat()
    preferred_plan = (
        active_plan
        if is_active_subscription
        and active_plan in billing_adapter.PLAN_PRICES
        else plan if plan in billing_adapter.PLAN_PRICES
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
        "is_active_subscription": is_active_subscription,
        "trial_expired": trial_expired,
        "current_plan": active_plan if is_active_subscription else "",
        "current_plan_label": {
            "autonomo": "Autónomo", "pro": "Negocio", "premium": "Premium",
        }.get(active_plan, "Plan activo"),
        "current_plan_rank": {
            "autonomo": 0, "pro": 1, "premium": 2,
        }.get(active_plan, -1),
        "plan_ranks": {"autonomo": 0, "pro": 1, "premium": 2},
        "upgrade_feature_label": billing_adapter.ENTITLEMENT_LABELS.get(feature, ""),
        "entitlements": billing_adapter.entitlements_for(biz),
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
        "entitlements": billing_adapter.entitlements_for(biz),
        # El parte de sección: la figura de Bynoesis en cada pantalla — lectura,
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
        context["privacy_request"] = db.get_open_privacy_request(business_id)
        context["legal_email"] = config.LEGAL_EMAIL or config.PUBLIC_CONTACT_EMAIL
        context["support_grant"] = db.active_support_grant(business_id)
        context["support_scopes"] = db.SUPPORT_SCOPES
        context["support_notice"] = request.session.pop("support_notice", "")
        context["support_error"] = request.session.pop("support_error", "")
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
        context["gestoria_access"] = db.list_gestoria_access_for_business(
            business_id
        )
        context["gestoria_invite_link"] = request.session.pop(
            "gestoria_invite_link", ""
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
    if page == "documentos" and config.INBOUND_EMAIL_ENABLED:
        from ...documents import inbound_email

        if inbound_email.configured():
            context["inbound_email_address"] = inbound_email.ensure_route(
                business_id
            )["address"]
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
        context["assistant_prompts"] = chat.assistant_prompts(biz)
    return TEMPLATES.TemplateResponse(request, f"{page}.html", context)
