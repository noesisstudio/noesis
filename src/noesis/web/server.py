"""Servidor web de Noesis (FastAPI) — app multipágina.

Un único proceso, fácil de desplegar 24/7, sirve:
  1. Las PÁGINAS del producto (resumen, ingresos, costes, facturas, cobros,
     agenda, clientes, asistente, ajustes) — cada una su propia vista en detalle.
  2. La API JSON que las alimenta (y que mañana usará la app móvil).
  3. El ONBOARDING (alta de negocio + conexión de WhatsApp).
  4. El CHATBOT interno (cerebro local + IA opcional).
  5. El WEBHOOK de WhatsApp (stub, listo para Meta Cloud API).

Arrancar:   noesis-web
Producción: uvicorn noesis.web.server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import json
import os
import hashlib
import logging
import re
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.concurrency import run_in_threadpool

from .. import config, db, verifactu_client
from ..adapters import billing as billing_adapter
from ..adapters import email as email_adapter
from ..tools import run_tool
from . import auth, backups, chat, reports, whatsapp
from .scheduler import start_scheduler

HERE = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=str(HERE / "templates"))


def _asset_version() -> str:
    """Versión de los assets a partir de su fecha de modificación, para romper la
    caché del navegador automáticamente cada vez que cambian CSS/JS (clave en
    producción: si no, los usuarios verían estilos viejos tras un despliegue)."""
    paths = [HERE / "static" / "app.css", HERE / "static" / "app.js"]
    try:
        return str(int(max(p.stat().st_mtime for p in paths if p.exists())))
    except ValueError:
        return "1"


# Disponible en todas las plantillas como {{ asset_v }}.
TEMPLATES.env.globals["asset_v"] = _asset_version()


def _eur(value) -> str:
    """Formato de dinero en español (1.234,56 €) para las plantillas."""
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        n = 0.0
    return f"{n:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


# Disponible en plantillas como {{ importe | eur }}.
TEMPLATES.env.filters["eur"] = _eur

@asynccontextmanager
async def lifespan(app: "FastAPI"):
    # Arranque de la app (sustituye al obsoleto @app.on_event("startup")).
    _startup()
    yield


app = FastAPI(title="Noesis", version="0.3.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")


# --- Guardia de seguridad: protege /b/ y /api/ y comprueba que el usuario sea
#     dueño del negocio que pide (aislamiento entre clientes). Se define ANTES de
#     añadir SessionMiddleware para que éste quede por fuera y la sesión exista aquí.
@app.middleware("http")
async def auth_guard(request: Request, call_next):
    path = request.url.path
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not path.startswith(
        "/webhook/"
    ):
        origin = request.headers.get("origin")
        fetch_site = request.headers.get("sec-fetch-site", "")
        if fetch_site == "cross-site":
            return JSONResponse({"error": "petición cross-site rechazada"}, status_code=403)
        if origin:
            origin_url = urlsplit(origin)
            if origin_url.netloc.lower() != request.headers.get("host", "").lower():
                return JSONResponse({"error": "origen no autorizado"}, status_code=403)

    if path.startswith("/b/") or path.startswith("/api/"):
        user = auth.current_user(request)
        if not user:
            request.session.clear()
            if path.startswith("/api/"):
                return JSONResponse({"error": "no autenticado"}, status_code=401)
            return RedirectResponse("/login")
        parts = path.split("/")
        try:
            wanted = int(parts[2])
        except (IndexError, ValueError):
            wanted = None
        own_business_id = user["business_id"]
        if wanted is not None and own_business_id != wanted:
            if path.startswith("/api/"):
                return JSONResponse({"error": "no autorizado"}, status_code=403)
            return RedirectResponse(f"/b/{own_business_id}/resumen")
        business = db.get_business(own_business_id)
        allowed_when_blocked = (
            path.startswith(f"/b/{own_business_id}/suscripcion")
            or path == f"/b/{own_business_id}/account/delete"
            or path == f"/api/{own_business_id}/export"
        )
        if not db.subscription_allows_access(business) and not allowed_when_blocked:
            if path.startswith("/api/"):
                return JSONResponse(
                    {"error": "La suscripción no está activa."}, status_code=402
                )
            return RedirectResponse(f"/b/{own_business_id}/suscripcion?status=required")
    return await call_next(request)


app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY,
                   max_age=60 * 60 * 24 * 14,        # 14 días
                   same_site="lax", https_only=config.HTTPS_ONLY)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), geolocation=(self), payment=()"
        if request.url.path.startswith("/t/")
        else "camera=(), geolocation=(), payment=()"
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; font-src 'self'; "
        "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; "
        "form-action 'self' https://checkout.stripe.com"
    )
    if config.HTTPS_ONLY:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    if request.url.path.startswith(("/b/", "/api/", "/admin", "/t/")):
        response.headers["Cache-Control"] = "no-store"
    if request.url.path.startswith("/t/"):
        response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _startup() -> None:
    import logging
    log = logging.getLogger("uvicorn.error")
    if config.IS_PRODUCTION and config.SECRET_KEY == "dev-secret-cambiar-en-produccion":
        raise RuntimeError(
            "NOESIS_SECRET es obligatoria en producción y debe ser larga y aleatoria."
        )
    if config.IS_PRODUCTION and not config.BASE_URL.startswith("https://"):
        log.error(
            "NOESIS_BASE_URL no usa HTTPS. La app continuará disponible, pero los "
            "enlaces de recuperación y Stripe pueden ser incorrectos. Configura "
            "NOESIS_BASE_URL o habilita un dominio público en Railway."
        )
    if config.IS_PRODUCTION and os.getenv("WHATSAPP_TOKEN") and not config.WHATSAPP_APP_SECRET:
        raise RuntimeError(
            "WHATSAPP_APP_SECRET es obligatorio al activar WhatsApp en producción."
        )
    if config.IS_PRODUCTION and config.STRIPE_SECRET_KEY and not config.STRIPE_WEBHOOK_SECRET:
        raise RuntimeError(
            "STRIPE_WEBHOOK_SECRET es obligatorio al activar Stripe en producción."
        )
    if config.RESET_DB:
        if config.DATABASE_URL:
            raise RuntimeError("NOESIS_RESET_DB no se admite con Postgres.")
        # Reinicio de UN SOLO USO: borra todo una vez y deja un marcador, para que
        # aunque olvides quitar la variable NO se vuelva a borrar en cada despliegue.
        marker = Path(config.DB_PATH).parent / ".db_reset_done"
        if marker.exists():
            db.init_db()
            log.info("NOESIS_RESET_DB presente, pero ya se reinició antes: no se borra.")
        else:
            db.reset_db()
            try:
                marker.write_text("done")
            except OSError:
                pass
            log.warning("NOESIS_RESET_DB: base de datos REINICIADA (una sola vez).")
    else:
        db.init_db()
    # Datos demo solo si se piden explícitamente (producción arranca limpia y real).
    if config.SEED_DEMO:
        demo_user = db.get_user_by_email("demo@bynoesis.com")
        if not demo_user:
            from .. import demo
            demo_business_id = demo.seed(reset=False)
            db.create_user(
                "demo@bynoesis.com", auth.hash_password("demo1234"),
                demo_business_id,
            )
    start_scheduler()


# ============================================================== PÁGINAS ===== #
_PAGES = {
    "resumen": "Resumen", "tesoreria": "Tesorería", "analisis": "Análisis",
    "ingresos": "Ingresos", "costes": "Costes", "presupuestos": "Presupuestos",
    "facturas": "Facturas", "cobros": "Cobros", "impuestos": "Impuestos",
    "agenda": "Agenda", "equipo": "Equipo", "clientes": "Clientes",
    "documentos": "Documentos",
    "asistente": "Asistente", "ajustes": "Ajustes",
}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    bid = request.session.get("bid")
    return TEMPLATES.TemplateResponse(request, "landing.html",
                                      {"business_id": bid, "site_active": "inicio"})


@app.get("/app")
def app_entry(request: Request):
    """Punto de entrada de la app instalada (PWA): directo al panel o al login."""
    bid = request.session.get("bid")
    target = f"/b/{bid}/resumen" if bid else "/login"
    return RedirectResponse(target, status_code=303)


# Apartados del sitio público: cada sección es su propia página.
_SITE_PAGES = {
    "producto": "site_producto.html",
    "precios": "site_precios.html",
    "preguntas": "site_preguntas.html",
}


@app.get("/producto", response_class=HTMLResponse)
@app.get("/precios", response_class=HTMLResponse)
@app.get("/preguntas", response_class=HTMLResponse)
def site_page(request: Request):
    section = request.url.path.strip("/")
    return TEMPLATES.TemplateResponse(request, _SITE_PAGES[section], {
        "business_id": request.session.get("bid"),
        "site_active": section,
    })


@app.get("/health")
def health():
    """Liveness para el proveedor cloud: el proceso HTTP está respondiendo."""
    return {"status": "ok", "service": "noesis", "version": app.version}


@app.get("/ready")
def readiness():
    """Readiness: comprueba que el almacenamiento está inicializado y accesible."""
    try:
        from .. import migrations
        ready = migrations.is_current()
    except db.DatabaseError:
        ready = False
    if not ready:
        return JSONResponse({"status": "not_ready"}, status_code=503)
    return {"status": "ready"}


@app.get("/sw.js")
def service_worker():
    # Servido desde la raíz para que el service worker controle toda la app (scope /).
    return Response(content=(HERE / "static" / "sw.js").read_text(encoding="utf-8"),
                    media_type="application/javascript")


@app.get("/privacidad", response_class=HTMLResponse)
def privacidad(request: Request):
    return TEMPLATES.TemplateResponse(request, "privacidad.html", {})


@app.get("/terminos", response_class=HTMLResponse)
def terminos(request: Request):
    return TEMPLATES.TemplateResponse(request, "terminos.html", {})


@app.get("/aviso-legal", response_class=HTMLResponse)
def aviso_legal(request: Request):
    return TEMPLATES.TemplateResponse(request, "aviso-legal.html", {})


@app.get("/cookies", response_class=HTMLResponse)
def cookies(request: Request):
    return TEMPLATES.TemplateResponse(request, "cookies.html", {})


@app.get("/encargado-tratamiento", response_class=HTMLResponse)
def encargado_tratamiento(request: Request):
    return TEMPLATES.TemplateResponse(request, "encargado-tratamiento.html", {})


@app.get("/cumplimiento", response_class=HTMLResponse)
def cumplimiento(request: Request):
    return TEMPLATES.TemplateResponse(request, "cumplimiento.html", {})


# ====================================================== PORTAL DEL CLIENTE === #
# Enlace privado SIN contraseña (estilo "client hub" de Jobber). Es público a
# propósito: el cliente del autónomo no tiene cuenta. El token va ligado a un único
# (negocio, cliente) y solo da acceso a SUS presupuestos y facturas — nunca a los de
# otro cliente. Las rutas /p/ quedan FUERA del auth_guard (no son /b/ ni /api/).
def _token_scan_blocked(request: Request, kind: str) -> bool:
    """Frena el escaneo de enlaces públicos: cada token inválido cuenta contra la IP.
    Los tokens son de 192 bits (imposibles de adivinar); esto solo corta el ruido."""
    return auth.is_rate_limited(f"token-scan:{kind}:{auth.client_ip(request)}")


def _record_token_miss(request: Request, kind: str) -> None:
    auth.record_failed_attempt(f"token-scan:{kind}:{auth.client_ip(request)}")


@app.get("/p/{token}", response_class=HTMLResponse)
def portal_home(request: Request, token: str, ok: str = ""):
    if _token_scan_blocked(request, "portal"):
        return Response("Demasiados intentos. Espera unos minutos.", status_code=429)
    ref = db.resolve_portal_token(token)
    if not ref:
        _record_token_miss(request, "portal")
        return TEMPLATES.TemplateResponse(
            request, "portal.html", {"token": token, "data": None, "ok": ""},
            status_code=404)
    data = db.client_portal_view(ref["business_id"], ref["client_id"])
    if data is None:
        return TEMPLATES.TemplateResponse(
            request, "portal.html", {"token": token, "data": None, "ok": ""},
            status_code=404)
    return TEMPLATES.TemplateResponse(
        request, "portal.html", {"token": token, "data": data, "ok": ok})


@app.post("/p/{token}/quotes/{quote_id}/accept")
def portal_accept_quote(request: Request, token: str, quote_id: int):
    ref = db.resolve_portal_token(token)
    if not ref:
        return RedirectResponse(f"/p/{token}", status_code=303)
    q = db.get_quote(quote_id, ref["business_id"])
    if not q or q.get("client_id") != ref["client_id"]:
        return RedirectResponse(f"/p/{token}?ok=nojusto", status_code=303)
    try:
        db.accept_quote(quote_id, ref["business_id"])
    except ValueError:
        return RedirectResponse(f"/p/{token}?ok=error", status_code=303)
    return RedirectResponse(f"/p/{token}?ok=aceptado", status_code=303)


@app.post("/p/{token}/quotes/{quote_id}/reject")
def portal_reject_quote(request: Request, token: str, quote_id: int):
    ref = db.resolve_portal_token(token)
    if not ref:
        return RedirectResponse(f"/p/{token}", status_code=303)
    q = db.get_quote(quote_id, ref["business_id"])
    if not q or q.get("client_id") != ref["client_id"]:
        return RedirectResponse(f"/p/{token}?ok=nojusto", status_code=303)
    db.reject_quote(quote_id, ref["business_id"])
    return RedirectResponse(f"/p/{token}?ok=rechazado", status_code=303)


@app.get("/p/{token}/invoices/{invoice_id}/pdf")
def portal_invoice_pdf(request: Request, token: str, invoice_id: int):
    if _token_scan_blocked(request, "portal"):
        return Response("Demasiados intentos. Espera unos minutos.", status_code=429)
    ref = db.resolve_portal_token(token)
    if not ref:
        _record_token_miss(request, "portal")
        return JSONResponse({"error": "Enlace no válido o caducado."}, status_code=404)
    inv = db.get_invoice(invoice_id, ref["business_id"])
    if not inv or inv.get("client_id") != ref["client_id"]:
        return JSONResponse({"error": "Factura no encontrada."}, status_code=404)
    if inv.get("status") not in {"enviada", "parcial", "cobrada"}:
        return JSONResponse({"error": "La factura aún no está disponible."},
                            status_code=404)
    from .invoice_pdf import build_invoice_pdf
    data = build_invoice_pdf(invoice_id, ref["business_id"])
    if data is None:
        return JSONResponse({"error": "Factura no encontrada."}, status_code=404)
    name = f"factura_{inv.get('number') or invoice_id}.pdf"
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{name}"'})


# ====================================================== PORTAL DE GESTORÍA === #
# Enlace privado para la gestoría del negocio: lista los períodos cerrados y
# descarga el paquete (facturas PDF+CSV, gastos con justificantes, resumen).
# Público a propósito (la gestoría no tiene cuenta); token revocable de 192 bits
# con el mismo freno anti-escaneo que el portal del cliente.
@app.get("/g/{token}", response_class=HTMLResponse)
def gestoria_home(request: Request, token: str):
    if _token_scan_blocked(request, "gestoria"):
        return Response("Demasiados intentos. Espera unos minutos.",
                        status_code=429)
    business = db.resolve_gestoria_token(token)
    if not business:
        _record_token_miss(request, "gestoria")
        return TEMPLATES.TemplateResponse(
            request, "gestoria.html",
            {"token": token, "business": None, "periods": []},
            status_code=404)
    return TEMPLATES.TemplateResponse(request, "gestoria.html", {
        "token": token,
        "business": business,
        "periods": db.gestoria_periods(business["id"]),
    })


@app.get("/g/{token}/paquete/{label}")
def gestoria_package(request: Request, token: str, label: str):
    if _token_scan_blocked(request, "gestoria"):
        return Response("Demasiados intentos. Espera unos minutos.",
                        status_code=429)
    business = db.resolve_gestoria_token(token)
    if not business:
        _record_token_miss(request, "gestoria")
        return JSONResponse({"error": "Enlace no válido."}, status_code=404)
    from . import gestoria as gestoria_service
    try:
        package = gestoria_service.build_package(business["id"], label)
    except ValueError:
        return JSONResponse({"error": "Período no válido."}, status_code=404)
    if not package:
        return JSONResponse({"error": "Período no válido."}, status_code=404)
    data, _meta = package
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition":
                f'attachment; filename="noesis-{label}.zip"'
        },
    )


# ======================================================== PORTAL DE FICHAJE === #
def _worker_token_verified(request: Request, token: str) -> bool:
    expected = hashlib.sha256(token.encode()).hexdigest()
    return request.session.get("worker_token_hash") == expected


def _worker_portal_context(request: Request, token: str) -> dict:
    ref = db.resolve_worker_token(token)
    if not ref:
        return {"token": token, "data": None}
    worker = ref["worker"]
    business = ref["business"]
    pin_required = bool(worker.get("pin_hash"))
    unlocked = not pin_required or _worker_token_verified(request, token)
    safe_worker = {
        key: worker.get(key)
        for key in ("id", "name", "color", "business_id", "has_pin")
    }
    initials = "".join(
        part[0].upper() for part in (business.get("name") or "N").split()[:2]
    )
    # El logo subido en Ajustes también viste el portal del trabajador.
    logo = None
    if business.get("logo_data") and business.get("logo_mime"):
        logo = f"data:{business['logo_mime']};base64,{business['logo_data']}"
    data = {
        "worker": safe_worker,
        "business": {
            "name": business.get("name"),
            "brand_color": db.business_brand_color(business),
            "initials": initials or "N",
            "logo": logo,
        },
        "pin_required": pin_required,
        "unlocked": unlocked,
        "jobs": (
            db.jobs_for_worker(worker["id"], business["id"], date.today().isoformat())
            if unlocked else []
        ),
        "open_shift": (
            db.worker_open_shift(worker["id"], business["id"]) if unlocked else None
        ),
        "history": (
            db.worker_clockin_history(
                worker["id"],
                business["id"],
                from_day=(date.today() - timedelta(days=29)).isoformat(),
                to_day=date.today().isoformat(),
            )
            if unlocked else []
        ),
        "clockin_policy": business.get("clockin_policy"),
        "info_ack": request.session.get("clockin_info_ack") == hashlib.sha256(
            token.encode()
        ).hexdigest(),
    }
    return {"token": token, "data": data}


@app.get("/t/{token}", response_class=HTMLResponse)
def worker_portal(request: Request, token: str):
    if _token_scan_blocked(request, "fichaje"):
        return Response("Demasiados intentos. Espera unos minutos.", status_code=429)
    context = _worker_portal_context(request, token)
    if not context["data"]:
        _record_token_miss(request, "fichaje")
    return TEMPLATES.TemplateResponse(
        request,
        "fichaje.html",
        context,
        status_code=200 if context["data"] else 404,
    )


@app.post("/t/{token}/pin")
async def worker_portal_pin(request: Request, token: str):
    ref = db.resolve_worker_token(token)
    if not ref:
        return JSONResponse({"error": "Enlace no válido o caducado."}, status_code=404)
    worker = ref["worker"]
    if not worker.get("pin_hash"):
        request.session["worker_token_hash"] = hashlib.sha256(token.encode()).hexdigest()
        return {"ok": True}
    key = f"worker-pin:{worker['id']}:{auth.client_ip(request)}"
    if auth.is_rate_limited(key):
        return JSONResponse(
            {"error": "Demasiados intentos. Espera unos minutos."}, status_code=429
        )
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if not auth.verify_password(str(body.get("pin") or ""), worker["pin_hash"]):
        auth.record_failed_attempt(key)
        return JSONResponse({"error": "PIN incorrecto."}, status_code=401)
    auth.clear_attempts(key)
    request.session["worker_token_hash"] = hashlib.sha256(token.encode()).hexdigest()
    return {"ok": True}


@app.post("/t/{token}/clock")
async def worker_portal_clock(request: Request, token: str):
    ref = db.resolve_worker_token(token)
    if not ref:
        return JSONResponse({"error": "Enlace no válido o caducado."}, status_code=404)
    worker = ref["worker"]
    if worker.get("pin_hash") and not _worker_token_verified(request, token):
        return JSONResponse({"error": "Introduce tu PIN primero."}, status_code=403)
    try:
        body = await _read_json(request)
        job_id = body.get("job_id")
        if job_id in ("", None):
            job_id = None
        else:
            job_id = int(job_id)
        clockin = db.clock_worker(
            ref["business"]["id"],
            worker["id"],
            str(body.get("action") or ""),
            "web",
            job_id=job_id,
            lat=body.get("lat"),
            lng=body.get("lng"),
            accuracy=body.get("accuracy"),
        )
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"ok": True, "clockin": clockin}


@app.post("/t/{token}/ack")
def worker_portal_ack(request: Request, token: str):
    ref = db.resolve_worker_token(token)
    if not ref:
        return JSONResponse({"error": "Enlace no válido o caducado."}, status_code=404)
    worker = ref["worker"]
    if worker.get("pin_hash") and not _worker_token_verified(request, token):
        return JSONResponse({"error": "Introduce tu PIN primero."}, status_code=403)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    db.record_product_event(
        ref["business"]["id"],
        "fichaje_info_ack",
        json.dumps(
            {"worker_id": worker["id"], "ack_at": date.today().isoformat()},
            ensure_ascii=False,
        ),
    )
    request.session["clockin_info_ack"] = token_hash
    return {"ok": True}


# ================================================================ AUTH ====== #
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    return TEMPLATES.TemplateResponse(request, "login.html", {"error": error})


@app.post("/login")
def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    key = f"login:{auth.client_ip(request)}"
    if auth.is_rate_limited(key):
        return RedirectResponse("/login?error=throttle", status_code=303)
    user = db.get_user_by_email((email or "").strip().lower())
    if not user or not auth.verify_password(password, user["password_hash"]):
        auth.record_failed_attempt(key)
        return RedirectResponse("/login?error=1", status_code=303)
    auth.clear_attempts(key)
    request.session.clear()
    request.session["uid"] = user["id"]
    request.session["bid"] = user["business_id"]
    request.session["sv"] = user.get("session_version", 0)
    return RedirectResponse(f"/b/{user['business_id']}/resumen", status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/b/{business_id}/suscripcion", response_class=HTMLResponse)
def subscription_page(request: Request, business_id: int, status: str = ""):
    # Definida ANTES de la ruta genérica /b/{id}/{page} para que no la capture ésta.
    biz = db.get_business(business_id)
    return TEMPLATES.TemplateResponse(request, "suscripcion.html", {
        "business": biz, "active": "ajustes", "page_title": "Suscripción",
        "status": status, "billing_on": billing_adapter.get_provider().available(),
        "prices": billing_adapter.PLAN_PRICES})


@app.get("/b/{business_id}/{page}", response_class=HTMLResponse)
def page(request: Request, business_id: int, page: str):
    if page not in _PAGES:
        return RedirectResponse(f"/b/{business_id}/resumen")
    biz = db.get_business(business_id)
    if not biz:
        return RedirectResponse("/login")
    context = {
        "business": biz,
        "active": page,
        "page_title": _PAGES[page],
        "activation": db.activation_snapshot(business_id),
    }
    if page == "resumen":
        layout = db.resolve_panel_layout(biz)
        context["panel_order"] = layout["order"]
        context["panel_hidden"] = layout["hidden"]
        context["panel_blocks"] = db.PANEL_BLOCKS
    if page == "ajustes" and biz.get("whatsapp_status") != "conectado":
        context["wa"] = whatsapp.start_link(business_id)
    if page == "ajustes":
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
    if page == "asistente":
        from ..adapters import transcription
        context["voice_on"] = transcription.available()
    return TEMPLATES.TemplateResponse(request, f"{page}.html", context)


# ================================================================= API ====== #
async def _read_json(request: Request) -> dict:
    declared = request.headers.get("content-length")
    if declared:
        try:
            declared_size = int(declared)
        except ValueError as exc:
            raise ValueError("Content-Length no es válido.") from exc
        if declared_size > config.MAX_JSON_BYTES:
            raise ValueError("La petición es demasiado grande.")
    raw = await request.body()
    if len(raw) > config.MAX_JSON_BYTES:
        raise ValueError("La petición es demasiado grande.")
    try:
        data = json.loads(raw or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("El JSON no es válido.") from exc
    if not isinstance(data, dict):
        raise ValueError("El cuerpo debe ser un objeto JSON.")
    return data


@app.get("/api/{business_id}/summary")
def api_summary(business_id: int):
    m = db.month_billing(business_id=business_id)
    pend = db.pending_payments(business_id)
    today = date.today().isoformat()
    return {**m,
            "clients": len(db.list_clients(business_id)),
            "jobs_today": len(db.jobs_for_date(today, business_id)),
            "pending_count": len(pend),
            "pending_total": round(sum(p["total"] for p in pend), 2)}


@app.get("/api/{business_id}/activation")
def api_activation(business_id: int):
    return db.activation_snapshot(business_id)


@app.get("/api/{business_id}/series")
def api_series(business_id: int):
    return db.monthly_series(business_id)


@app.get("/api/{business_id}/plan")
def api_plan(business_id: int):
    # Plan diario del copiloto (mismo cerebro que el asistente), para el dashboard.
    return chat.daily_plan(business_id)


@app.get("/api/{business_id}/recommendations")
def api_recommendations(business_id: int):
    # Ledger del copiloto: histórico de consejos y conteo por estado.
    return {"items": db.list_recommendations(business_id),
            "stats": db.recommendation_stats(business_id)}


@app.post("/api/{business_id}/recommendations/{rec_id}/status")
async def api_recommendation_status(business_id: int, rec_id: int, request: Request):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    try:
        rec = db.set_recommendation_status(rec_id, business_id, body.get("status"))
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if rec is None:
        return JSONResponse({"error": "Recomendación no encontrada."}, status_code=404)
    return rec


@app.post("/api/{business_id}/panel-layout")
async def api_panel_layout(business_id: int, request: Request):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    order = body.get("order")
    hidden = body.get("hidden")
    if not isinstance(order, list) or not isinstance(hidden, list):
        return JSONResponse({"error": "Formato de panel no válido."}, status_code=400)
    db.update_panel_layout(business_id, order, hidden)
    return {"ok": True}


@app.get("/api/{business_id}/analysis")
def api_analysis(business_id: int):
    return {**db.financial_analysis(business_id),
            "series": db.monthly_series(business_id, months=12)}


@app.get("/api/{business_id}/forecast")
def api_forecast(business_id: int, days: int = 30):
    """Previsión de caja: entra − sale − IVA a apartar, a N días vista."""
    return db.cash_forecast(business_id, days=days)


@app.get("/api/{business_id}/search")
def api_search(business_id: int, q: str = ""):
    """Buscador global: clientes, facturas, presupuestos y trabajos."""
    return db.global_search(business_id, q)


@app.get("/api/{business_id}/clients")
def api_clients(business_id: int):
    return db.list_clients(business_id)


@app.get("/api/{business_id}/clients/stats")
def api_clients_stats(business_id: int):
    return db.client_stats(business_id)


@app.get("/api/{business_id}/clients/{client_id}/portal-link")
def api_portal_link(business_id: int, client_id: int):
    """Enlace privado del cliente (Client Hub) para que el autónomo lo envíe por
    WhatsApp. Reutiliza el mismo enlace si ya existe uno vigente."""
    token = db.get_or_create_portal_token(business_id, client_id)
    if not token:
        return JSONResponse({"error": "Cliente no encontrado."}, status_code=404)
    return {"url": f"{config.BASE_URL}/p/{token}", "path": f"/p/{token}"}


def _worker_json(worker: dict) -> dict:
    return {
        key: value for key, value in worker.items()
        if key not in {"pin_hash", "phone_norm"}
    }


@app.get("/api/{business_id}/workers")
def api_workers(business_id: int):
    return db.clockins_today(business_id)


@app.get("/api/{business_id}/workers/productivity")
def api_workers_productivity(business_id: int, days: int = 30):
    """Rendimiento por persona (trabajos, ventas, horas) para el dueño."""
    return db.team_productivity(business_id, days=days)


@app.get("/api/{business_id}/workers/{worker_id}/clockins")
def api_worker_clockins(
    business_id: int,
    worker_id: int,
    from_: str = Query("", alias="from"),
    to: str = "",
):
    if not db.get_worker(worker_id, business_id):
        return JSONResponse({"error": "Trabajador no encontrado."}, status_code=404)
    try:
        start = (
            date.fromisoformat(from_).isoformat()
            if from_ else (date.today() - timedelta(days=29)).isoformat()
        )
        end = date.fromisoformat(to).isoformat() if to else date.today().isoformat()
    except ValueError:
        return JSONResponse({"error": "El rango de fechas no es válido."}, status_code=400)
    return {
        "items": db.worker_clockin_history(
            worker_id, business_id, from_day=start, to_day=end
        ),
        "integrity": db.verify_clockin_chain(business_id, worker_id),
    }


@app.post("/api/{business_id}/workers")
async def api_create_worker(business_id: int, request: Request):
    try:
        body = await _read_json(request)
        worker = db.create_worker(
            business_id,
            body.get("name"),
            phone=body.get("phone"),
            color=body.get("color"),
            pin=body.get("pin"),
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return _worker_json(worker)


@app.post("/api/{business_id}/workers/{worker_id}")
async def api_update_worker(
    business_id: int, worker_id: int, request: Request
):
    try:
        body = await _read_json(request)
        worker = db.update_worker(
            worker_id,
            business_id,
            name=body.get("name") if "name" in body else None,
            phone=body.get("phone") if "phone" in body else None,
            color=body.get("color") if "color" in body else None,
        )
        if worker is not None and "pin" in body:
            worker = db.set_worker_pin(
                worker_id, business_id, body.get("pin")
            )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if worker is None:
        return JSONResponse({"error": "Trabajador no encontrado."}, status_code=404)
    return _worker_json(worker)


@app.post("/api/{business_id}/workers/{worker_id}/active")
async def api_worker_active(
    business_id: int, worker_id: int, request: Request
):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if not isinstance(body.get("active"), bool):
        return JSONResponse({"error": "El estado activo no es válido."}, status_code=400)
    worker = db.set_worker_active(worker_id, business_id, body["active"])
    if worker is None:
        return JSONResponse({"error": "Trabajador no encontrado."}, status_code=404)
    return _worker_json(worker)


@app.post(
    "/api/{business_id}/workers/{worker_id}/clockins/{clockin_id}/correct"
)
async def api_correct_worker_clockin(
    request: Request,
    business_id: int,
    worker_id: int,
    clockin_id: int,
):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    user = auth.current_user(request)
    try:
        correction = db.correct_worker_clockin(
            business_id,
            worker_id,
            clockin_id,
            user["id"],
            new_at=body.get("new_at"),
            reason=body.get("reason"),
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if correction is None:
        return JSONResponse({"error": "Fichaje no encontrado."}, status_code=404)
    return {"ok": True, "correction": correction}


@app.post("/api/{business_id}/jobs/{job_id}/assign")
async def api_assign_job_worker(
    business_id: int, job_id: int, request: Request
):
    try:
        body = await _read_json(request)
        worker_id = body.get("worker_id")
        if worker_id in ("", None):
            worker_id = None
        else:
            worker_id = int(worker_id)
        job = db.assign_job_worker(job_id, worker_id, business_id)
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if job is None:
        return JSONResponse({"error": "Trabajo no encontrado."}, status_code=404)
    return job


@app.post("/api/{business_id}/workers/{worker_id}/send-day")
def api_send_worker_day(business_id: int, worker_id: int):
    worker = db.get_worker(worker_id, business_id)
    if not worker or not worker.get("active"):
        return JSONResponse({"error": "Trabajador no encontrado."}, status_code=404)
    if not worker.get("phone"):
        return JSONResponse(
            {"error": "Añade o vincula el teléfono del trabajador primero."},
            status_code=400,
        )
    today = date.today().isoformat()
    jobs = db.jobs_for_worker(worker_id, business_id, today)
    if jobs:
        lines = []
        for job in jobs:
            hour = str(job.get("scheduled_for") or "")[11:16] or "Sin hora"
            place = job.get("client_zone") or job.get("zone") or ""
            suffix = f" · {place}" if place else ""
            lines.append(
                f"• {hour} — {job.get('client_name') or 'Cliente'}: "
                f"{job.get('description') or 'Trabajo'}{suffix}"
            )
        body = (
            f"Hola, {worker['name']}. Tu planning de hoy:\n"
            + "\n".join(lines)
        )
    else:
        body = f"Hola, {worker['name']}. Hoy no tienes trabajos asignados."
    target_phone = "".join(
        character for character in worker["phone"] if character.isdigit()
    )
    if len(target_phone) == 9:
        target_phone = "34" + target_phone
    message = whatsapp.queue_text(
        target_phone,
        body,
        business_id=business_id,
        idempotency_key=f"worker-day:{business_id}:{worker_id}:{today}",
    )
    return {"ok": True, "message_id": message["id"], "status": message["status"]}


@app.get("/api/{business_id}/workers/{worker_id}/link")
def api_worker_link(business_id: int, worker_id: int):
    worker = db.get_worker(worker_id, business_id)
    if not worker or not worker.get("active"):
        return JSONResponse({"error": "Trabajador no encontrado."}, status_code=404)
    token = db.get_or_create_worker_token(business_id, worker_id)
    if not token:
        return JSONResponse({"error": "No se pudo crear el enlace."}, status_code=400)
    command = f"NOESIS EQUIPO {business_id} {worker['access_code']}"
    return {
        "url": f"{config.BASE_URL}/t/{token}",
        "path": f"/t/{token}",
        "access_code": worker["access_code"],
        "whatsapp_command": command,
    }


@app.get("/api/{business_id}/workers/{worker_id}/report")
def api_worker_report(
    business_id: int,
    worker_id: int,
    from_: str = Query("", alias="from"),
    to: str = "",
    format: str = "pdf",
):
    try:
        start = (
            date.fromisoformat(from_).isoformat()
            if from_ else (date.today() - timedelta(days=29)).isoformat()
        )
        end = date.fromisoformat(to).isoformat() if to else date.today().isoformat()
        data = db.clockin_report_data(business_id, worker_id, start, end)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if data is None:
        return JSONResponse({"error": "Trabajador no encontrado."}, status_code=404)
    from .work_reports import build_clockin_csv, build_clockin_pdf
    safe_name = "".join(
        character if character.isalnum() else "_"
        for character in data["worker"]["name"].lower()
    ).strip("_") or f"trabajador_{worker_id}"
    if format.lower() == "csv":
        payload = build_clockin_csv(data)
        return Response(
            content=payload,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="jornada_{safe_name}_{start}_{end}.csv"'
                )
            },
        )
    if format.lower() != "pdf":
        return JSONResponse({"error": "Formato de informe no válido."}, status_code=400)
    payload = build_clockin_pdf(data)
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="jornada_{safe_name}_{start}_{end}.pdf"'
            )
        },
    )


@app.get("/api/{business_id}/invoices")
def api_invoices(business_id: int):
    return db.list_invoices(business_id)


@app.post("/api/{business_id}/invoices")
async def api_create_invoice(business_id: int, request: Request):
    """Crea una factura en borrador desde la web (además de por el asistente).

    Acepta un cliente existente (client_id) o un nombre nuevo (client_name), que se
    da de alta al vuelo para que la primera factura no exija crear antes la ficha.
    """
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    client_id = body.get("client_id")
    if not client_id:
        new_name = (body.get("client_name") or "").strip()
        if not new_name:
            return JSONResponse(
                {"error": "Indica un cliente para la factura."}, status_code=400
            )
        existing = db.find_client(new_name, business_id)
        client_id = existing["id"] if existing else db.add_client(
            new_name, business_id=business_id
        )["id"]
    try:
        client_id = int(client_id)
        invoice = db.add_invoice(
            client_id,
            (body.get("concept") or "").strip(),
            body.get("base"),
            vat_rate=body.get("vat_rate", config.DEFAULT_VAT_RATE),
            irpf_rate=body.get("irpf_rate", 0),
            business_id=business_id,
        )
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return invoice


@app.post("/api/{business_id}/invoices/{invoice_id}/rectify")
async def api_rectify_invoice(
    business_id: int, invoice_id: int, request: Request
):
    try:
        body = await _read_json(request)
        invoice = db.create_rectifying_invoice(
            invoice_id,
            business_id,
            concept=body.get("concept"),
            base=body.get("base"),
            vat_rate=body.get("vat_rate", 21),
            irpf_rate=body.get("irpf_rate", 0),
            invoice_type=body.get("invoice_type", "R1"),
            reason=body.get("reason"),
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return invoice


@app.get("/api/{business_id}/verifactu/export.xml")
def api_verifactu_export(
    business_id: int,
    from_: str = Query("", alias="from"),
    to: str = "",
):
    try:
        start = date.fromisoformat(from_).isoformat() if from_ else None
        end = date.fromisoformat(to).isoformat() if to else None
        payload = db.export_verifactu_xml(
            business_id, from_day=start, to_day=end
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return Response(
        content=payload,
        media_type="application/xml; charset=utf-8",
        headers={
            "Content-Disposition": (
                'attachment; filename="registros_verifactu.xml"'
            )
        },
    )


@app.get("/api/{business_id}/verifactu/integrity")
def api_verifactu_integrity(business_id: int):
    return db.verify_invoice_record_chain(business_id)


@app.get("/api/{business_id}/expenses")
def api_expenses(business_id: int):
    return db.list_expenses(business_id)


@app.post("/api/{business_id}/expenses/from-photo", status_code=201)
async def api_expense_from_photo(
    business_id: int, file: UploadFile = File(...)
):
    """Guarda la foto y devuelve sugerencias; nunca crea el gasto."""
    from ..adapters import extraction
    from ..documents import service as docservice, storage

    filename = file.filename or "ticket"
    if storage.ext_of(filename) not in storage.IMAGE_EXTS:
        return JSONResponse(
            {"error": "Sube una foto JPG, PNG, WEBP o HEIC."},
            status_code=400,
        )
    max_bytes = config.MAX_UPLOAD_MB * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        return JSONResponse(
            {"error": f"El archivo supera el límite de {config.MAX_UPLOAD_MB} MB."},
            status_code=413,
        )
    try:
        document = docservice.upload(
            business_id,
            filename,
            data,
            kind="ticket",
            run_ocr=False,
        )
    except docservice.UploadError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    extracted = await run_in_threadpool(
        extraction.extract_expense,
        data,
        storage.mime_for(filename),
    )
    fields = extracted or {
        "concept": None,
        "amount": None,
        "vat_rate": None,
        "date": None,
        "supplier": None,
    }
    return {
        "document": document,
        "extracted": extracted is not None,
        "draft": {
            **fields,
            "category": "Ticket",
            "document_id": document["id"],
        },
    }


@app.post("/api/{business_id}/expenses")
async def api_add_expense(business_id: int, request: Request):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    concept = (body.get("concept") or "").strip()
    try:
        amount = float(body.get("amount"))
    except (TypeError, ValueError):
        amount = 0
    if not concept or amount <= 0:
        return JSONResponse({"error": "Concepto e importe (>0) son obligatorios."},
                            status_code=400)
    try:
        return db.add_expense(
            concept,
            amount,
            vat_rate=body.get("vat_rate"),
            category=body.get("category"),
            spent_on=body.get("spent_on") or body.get("date"),
            document_id=body.get("document_id"),
            business_id=business_id,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.delete("/api/{business_id}/expenses/{expense_id}")
def api_delete_expense(business_id: int, expense_id: int):
    db.delete_expense(expense_id, business_id)
    return {"ok": True}


@app.post("/api/{business_id}/clients")
async def api_create_client(business_id: int, request: Request):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    name = (body.get("name") or "").strip()
    if not name:
        return JSONResponse({"error": "El nombre es obligatorio."}, status_code=400)
    return db.add_client(name, phone=body.get("phone"), address=body.get("address"),
                         zone=body.get("zone"), nif=body.get("nif"),
                         email=body.get("email"), business_id=business_id)


@app.post("/api/{business_id}/clients/import")
async def api_import_clients(business_id: int, request: Request):
    """Alta en bloque de clientes pegados como texto (una línea por cliente).

    Formato tolerante separado por comas o tabuladores:
    nombre, teléfono, email, NIF, zona. Solo el nombre es obligatorio.
    """
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    raw = (body.get("text") or "").strip()
    if not raw:
        return JSONResponse({"error": "Pega al menos un cliente."}, status_code=400)
    fields = ("name", "phone", "email", "nif", "zone")
    rows: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        cells = [c.strip() for c in line.replace("\t", ",").split(",")]
        # Ignora una posible cabecera pegada desde una hoja de cálculo.
        if not rows and cells[0].lower() in {"nombre", "name", "cliente"}:
            continue
        rows.append({fields[i]: cells[i] for i in range(min(len(cells), len(fields)))})
    if not rows:
        return JSONResponse({"error": "No se reconoció ningún cliente."},
                            status_code=400)
    return db.import_clients(rows, business_id)


@app.post("/api/{business_id}/clients/{client_id}")
async def api_update_client(business_id: int, client_id: int, request: Request):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if not (body.get("name") or "").strip():
        return JSONResponse({"error": "El nombre es obligatorio."}, status_code=400)
    client = db.update_client(
        client_id, business_id, name=body.get("name"), phone=body.get("phone"),
        address=body.get("address"), zone=body.get("zone"), nif=body.get("nif"),
        email=body.get("email"),
    )
    if client is None:
        return JSONResponse({"error": "Cliente no encontrado."}, status_code=404)
    return client


@app.delete("/api/{business_id}/clients/{client_id}")
def api_delete_client(business_id: int, client_id: int):
    try:
        db.delete_client(client_id, business_id)
    except db.IntegrityError:
        return JSONResponse(
            {"error": "El cliente tiene datos asociados y no se puede borrar así."},
            status_code=409,
        )
    return {"ok": True}


@app.delete("/api/{business_id}/invoices/{invoice_id}")
def api_delete_invoice(business_id: int, invoice_id: int):
    if not db.delete_invoice(invoice_id, business_id):
        return JSONResponse(
            {"error": "Solo se pueden borrar facturas en borrador."},
            status_code=409,
        )
    return {"ok": True}


@app.delete("/api/{business_id}/jobs/{job_id}")
def api_delete_job(business_id: int, job_id: int):
    try:
        db.delete_job(job_id, business_id)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)
    return {"ok": True}


@app.get("/api/{business_id}/invoices/{invoice_id}/pdf")
def api_invoice_pdf(business_id: int, invoice_id: int):
    from .invoice_pdf import build_invoice_pdf
    data = build_invoice_pdf(invoice_id, business_id)
    if data is None:
        return JSONResponse({"error": "Factura no encontrada."}, status_code=404)
    inv = db.get_invoice(invoice_id, business_id)
    name = f"factura_{inv.get('number') or invoice_id}.pdf"
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{name}"'})


@app.get("/api/{business_id}/costs/breakdown")
def api_costs_breakdown(business_id: int):
    return db.expenses_by_category(business_id)


@app.get("/api/{business_id}/income/by-client")
def api_income_by_client(business_id: int):
    return db.income_by_client(business_id)


@app.get("/api/{business_id}/pending")
def api_pending(business_id: int):
    return db.pending_payments(business_id)


@app.get("/api/{business_id}/agenda")
def api_agenda(business_id: int, week: bool = False, start: str = "", end: str = ""):
    if start and end:
        return db.jobs_between(start, end, business_id)
    if week:
        today = date.today()
        return db.jobs_between(today.isoformat(),
                               (today + timedelta(days=6)).isoformat(), business_id)
    return db.jobs_for_date(date.today().isoformat(), business_id)


@app.post("/api/{business_id}/invoices/{invoice_id}/pay")
def api_mark_paid(business_id: int, invoice_id: int):
    inv = db.mark_invoice_paid(invoice_id, business_id)
    if inv is None:
        return JSONResponse(
            {"error": "Solo se puede cobrar una factura emitida."}, status_code=409
        )
    return inv


@app.get("/api/{business_id}/invoices/{invoice_id}/payments")
def api_invoice_payments(business_id: int, invoice_id: int):
    if not db.get_invoice(invoice_id, business_id):
        return JSONResponse({"error": "Factura no encontrada."}, status_code=404)
    return db.list_invoice_payments(invoice_id, business_id)


@app.post(
    "/api/{business_id}/invoices/{invoice_id}/payments",
    status_code=201,
)
async def api_add_invoice_payment(
    business_id: int, invoice_id: int, request: Request
):
    if not db.get_invoice(invoice_id, business_id):
        return JSONResponse({"error": "Factura no encontrada."}, status_code=404)
    try:
        body = await _read_json(request)
        return db.add_invoice_payment(
            invoice_id,
            body.get("amount"),
            business_id=business_id,
            method=body.get("method"),
            paid_at=body.get("paid_at"),
            note=body.get("note"),
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.post("/api/{business_id}/invoices/{invoice_id}/send")
def api_send_invoice(business_id: int, invoice_id: int):
    # Emite una factura borrador desde la web (mismo flujo que el chat, aislado).
    result = json.loads(run_tool("enviar_factura",
                                 {"factura_id": invoice_id}, business_id))
    if not result.get("ok"):
        return JSONResponse({"error": result.get("error", "No se pudo enviar.")},
                            status_code=400)
    return result["factura"]


# ----------------------------------------------------------- Presupuestos ---
@app.get("/api/{business_id}/quotes")
def api_quotes(business_id: int):
    return db.list_quotes(business_id)


@app.post("/api/{business_id}/quotes")
async def api_add_quote(business_id: int, request: Request):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    cliente = (body.get("cliente") or "").strip()
    concepto = (body.get("concepto") or "").strip()
    try:
        base = float(body.get("base"))
    except (TypeError, ValueError):
        base = 0
    if not cliente or not concepto or base <= 0:
        return JSONResponse({"error": "Cliente, concepto e importe (>0) son obligatorios."},
                            status_code=400)
    args = {"cliente": cliente, "concepto": concepto, "base": base}
    if body.get("iva") is not None:
        args["iva"] = body["iva"]
    if body.get("irpf") is not None:
        args["irpf"] = body["irpf"]
    result = json.loads(run_tool("crear_presupuesto", args, business_id))
    if not result.get("ok"):
        return JSONResponse({"error": result.get("error", "No se pudo crear.")},
                            status_code=400)
    return result["presupuesto"]


@app.post("/api/{business_id}/quotes/{quote_id}/send")
def api_send_quote(business_id: int, quote_id: int):
    try:
        q = db.mark_quote_sent(quote_id, business_id)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)
    if q is None:
        return JSONResponse({"error": "Presupuesto no encontrado."}, status_code=404)
    return q


@app.post("/api/{business_id}/quotes/{quote_id}/accept")
def api_accept_quote(business_id: int, quote_id: int):
    try:
        res = db.accept_quote(quote_id, business_id)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)
    if res is None:
        return JSONResponse({"error": "Presupuesto no encontrado."}, status_code=404)
    return res


@app.post("/api/{business_id}/quotes/{quote_id}/reject")
def api_reject_quote(business_id: int, quote_id: int):
    q = db.reject_quote(quote_id, business_id)
    if q is None:
        return JSONResponse({"error": "Presupuesto no encontrado."}, status_code=404)
    return q


@app.delete("/api/{business_id}/quotes/{quote_id}")
def api_delete_quote(business_id: int, quote_id: int):
    if not db.delete_quote(quote_id, business_id):
        return JSONResponse(
            {"error": "Solo se pueden borrar presupuestos en borrador."},
            status_code=409,
        )
    return {"ok": True}


# -------------------------------------------------------------- Impuestos ---
@app.get("/api/{business_id}/taxes")
def api_taxes(business_id: int, year: int = 0, quarter: int = 0):
    today = date.today()
    year = year or today.year
    quarter = quarter or (today.month - 1) // 3 + 1
    try:
        return {**db.tax_quarter(year, quarter, business_id),
                "current_year": today.year}
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.post("/api/{business_id}/chat")
async def api_chat(business_id: int, request: Request):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    message = str(body.get("message") or "").strip()
    if not message or len(message) > config.MAX_CHAT_CHARS:
        return JSONResponse(
            {"error": "El mensaje está vacío o es demasiado largo."}, status_code=400
        )
    return await run_in_threadpool(chat.handle, business_id, message)


@app.post("/api/{business_id}/chat/audio")
async def api_chat_audio(business_id: int, audio: UploadFile = File(...)):
    # Nota de voz -> texto (Whisper local, sin coste por uso) -> cerebro local.
    from ..adapters import transcription
    tr = transcription.get_transcriber()
    if tr is None:
        return JSONResponse(
            {"error": "Transcripción de voz no disponible en este servidor."},
            status_code=503)
    data = await audio.read(config.MAX_AUDIO_BYTES + 1)
    if len(data) > config.MAX_AUDIO_BYTES:
        return JSONResponse({"error": "El audio es demasiado grande."}, status_code=413)
    try:
        text = await run_in_threadpool(
            tr.transcribe, data, audio.filename or "audio"
        )
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "No he podido entender el audio."}, status_code=422)
    if not text:
        return JSONResponse({"error": "El audio estaba vacío o no se entendió."},
                            status_code=422)
    result = await run_in_threadpool(chat.handle, business_id, text)
    return {"transcription": text, **result}


# ============================================================= INFORMES ===== #
def _csv_response(text: str, filename: str) -> Response:
    return Response(content="﻿" + text,
                    media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/{business_id}/reports/costs.csv")
def report_costs(business_id: int):
    return _csv_response(reports.costs_csv(business_id), "noesis_costes.csv")


@app.get("/api/{business_id}/reports/invoices.csv")
def report_invoices(business_id: int):
    return _csv_response(reports.invoices_csv(business_id), "noesis_facturas.csv")


# =========================================================== DOCUMENTOS ===== #
@app.get("/api/{business_id}/documents")
def api_documents(business_id: int, client_id: int = 0):
    from ..documents import repo as docrepo
    return docrepo.list_for_business(business_id, client_id or None)


@app.get("/api/{business_id}/documents/ocr-status")
def api_ocr_status(business_id: int):
    """Indica si la lectura de fotos (OCR) está activa en este servidor."""
    from ..documents import ocr
    return {"ocr": ocr.available()}


@app.post("/api/{business_id}/documents")
async def api_upload_document(business_id: int, file: UploadFile = File(...),
                              kind: str = Form("documento"),
                              client_id: str = Form(""), invoice_id: str = Form(""),
                              note: str = Form("")):
    from ..documents import service as docservice
    # Lectura ACOTADA: nunca cargamos en memoria más de lo permitido. Sin este tope,
    # un archivo enorme agotaría la RAM antes de que el servicio validara el tamaño.
    max_bytes = config.MAX_UPLOAD_MB * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        return JSONResponse(
            {"error": f"El archivo supera el límite de {config.MAX_UPLOAD_MB} MB."},
            status_code=413,
        )

    def _opt_int(v):
        try:
            return int(v) if str(v).strip() else None
        except (TypeError, ValueError):
            return None

    try:
        doc = docservice.upload(business_id, file.filename or "documento", data,
                                kind=kind, client_id=_opt_int(client_id),
                                invoice_id=_opt_int(invoice_id), note=note or None)
    except docservice.UploadError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return doc


@app.get("/api/{business_id}/documents/{doc_id}/file")
def api_document_file(business_id: int, doc_id: int):
    from ..documents import service as docservice
    got = docservice.file_bytes(business_id, doc_id)
    if got is None:
        return JSONResponse({"error": "Documento no encontrado."}, status_code=404)
    data, mime, filename = got
    # Sanea el nombre para la cabecera: sin comillas ni saltos que la rompan.
    safe_name = re.sub(r'[\r\n"\\]', "_", filename or "documento")[:120]
    return Response(content=data, media_type=mime,
                    headers={"Content-Disposition": f'inline; filename="{safe_name}"'})


@app.delete("/api/{business_id}/documents/{doc_id}")
def api_delete_document(business_id: int, doc_id: int):
    from ..documents import service as docservice
    if not docservice.delete(business_id, doc_id):
        return JSONResponse({"error": "Documento no encontrado."}, status_code=404)
    return {"ok": True}


@app.post("/api/{business_id}/documents/{doc_id}/to-expense")
async def api_document_to_expense(business_id: int, doc_id: int, request: Request):
    """Convierte un ticket/factura escaneada en un gasto (usa el importe del OCR)."""
    from ..documents import service as docservice
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    amount = body.get("amount")
    try:
        amount = float(amount) if amount not in (None, "") else None
    except (TypeError, ValueError):
        amount = None
    try:
        gasto = docservice.convert_ticket_to_expense(
            business_id,
            doc_id,
            concept=body.get("concept"),
            amount=amount,
            vat_rate=body.get("vat_rate"),
            spent_on=body.get("spent_on") or body.get("date"),
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if gasto is None:
        return JSONResponse(
            {"error": "No hay importe para registrar. Indica uno o sube una foto legible."},
            status_code=400)
    return gasto


# ================================================================ RGPD ====== #
def _json_download(data: dict, filename: str) -> Response:
    return Response(content=json.dumps(data, ensure_ascii=False, indent=2, default=str),
                    media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/{business_id}/export")
def api_export_account(business_id: int):
    """Portabilidad RGPD: descarga TODOS los datos de la cuenta en JSON."""
    return _json_download(db.export_business_data(business_id),
                          "noesis_datos_cuenta.json")


@app.get("/api/{business_id}/clients/{client_id}/export")
def api_export_client(business_id: int, client_id: int):
    data = db.export_client_data(client_id, business_id)
    if data is None:
        return JSONResponse({"error": "Cliente no encontrado."}, status_code=404)
    return _json_download(data, f"noesis_cliente_{client_id}.json")


@app.delete("/api/{business_id}/clients/{client_id}/erase")
def api_erase_client(business_id: int, client_id: int):
    """Borra datos prescindibles y conserva lo sujeto a obligación fiscal."""
    ok = db.delete_client_cascade(client_id, business_id)
    if not ok:
        return JSONResponse({"error": "Cliente no encontrado."}, status_code=404)
    return {"ok": True}


@app.post("/b/{business_id}/account/delete")
def delete_account(request: Request, business_id: int, confirm: str = Form(""),
                   password: str = Form("")):
    """Baja total de la cuenta del autónomo (RGPD). Pide escribir BORRAR."""
    if confirm.strip().upper() != "BORRAR":
        return RedirectResponse(f"/b/{business_id}/ajustes?error=confirma", status_code=303)
    user = auth.current_user(request)
    if not user or not auth.verify_password(password, user["password_hash"]):
        return RedirectResponse(
            f"/b/{business_id}/ajustes?error=password", status_code=303
        )
    try:
        db.delete_business_cascade(business_id)
    except ValueError:
        return RedirectResponse(
            f"/b/{business_id}/ajustes?error=conservacion_fiscal", status_code=303
        )
    request.session.clear()
    return RedirectResponse("/?bye=1", status_code=303)


# =========================================================== ONBOARDING ===== #
@app.get("/onboarding", response_class=HTMLResponse)
def onboarding(request: Request, error: str = ""):
    return TEMPLATES.TemplateResponse(request, "onboarding.html", {"error": error})


@app.post("/onboarding/signup")
def onboarding_signup(request: Request, name: str = Form(...),
                      email: str = Form(...), password: str = Form(...),
                      sector: str = Form(""), acepto: str = Form("")):
    key = f"signup:{auth.client_ip(request)}"
    if auth.is_rate_limited(key):
        return RedirectResponse("/onboarding?error=throttle", status_code=303)
    email = (email or "").strip().lower()
    name = (name or "").strip()
    if not name:
        return RedirectResponse("/onboarding?error=name", status_code=303)
    if not acepto:
        return RedirectResponse("/onboarding?error=consent", status_code=303)
    if not auth.valid_email(email):
        return RedirectResponse("/onboarding?error=email_format", status_code=303)
    if len(password) < 12 or len(password) > 1024:
        auth.record_failed_attempt(key)
        return RedirectResponse("/onboarding?error=password", status_code=303)
    if db.get_user_by_email(email):
        return RedirectResponse("/onboarding?error=email", status_code=303)
    try:
        biz, user = db.create_account(
            name, email, auth.hash_password(password), sector or None,
            trial_days=config.TRIAL_DAYS,
        )
    except (ValueError, *db.IntegrityError):
        auth.record_failed_attempt(key)
        return RedirectResponse("/onboarding?error=email", status_code=303)
    auth.clear_attempts(key)
    request.session.clear()
    request.session["uid"] = user["id"]
    request.session["bid"] = biz["id"]
    request.session["sv"] = user.get("session_version", 0)
    db.record_product_event(biz["id"], "account_created")
    # Evidencia de consentimiento: quién aceptó qué versión, cuándo y desde dónde.
    db.record_product_event(biz["id"], "legal_accepted", json.dumps({
        "version": "2026-06-30",
        "documents": ["terminos", "privacidad", "encargado-tratamiento"],
        "ip": auth.client_ip(request),
    }))
    return RedirectResponse(f"/onboarding/setup/{biz['id']}", status_code=303)


@app.get("/onboarding/setup/{business_id}", response_class=HTMLResponse)
def onboarding_setup(request: Request, business_id: int, error: str = ""):
    user = auth.current_user(request)
    if not user or user["business_id"] != business_id:
        return RedirectResponse("/login", status_code=303)
    biz = db.get_business(business_id)
    if not biz:
        return RedirectResponse("/onboarding", status_code=303)
    return TEMPLATES.TemplateResponse(
        request, "onboarding_setup.html", {"business": biz, "error": error}
    )


@app.post("/onboarding/setup/{business_id}")
def onboarding_setup_submit(
    request: Request,
    business_id: int,
    sector: str = Form(...),
    team_size: str = Form(...),
    primary_goal: str = Form(...),
    province: str = Form(""),
):
    user = auth.current_user(request)
    if not user or user["business_id"] != business_id:
        return RedirectResponse("/login", status_code=303)
    try:
        db.update_business_profile(
            business_id,
            sector=sector,
            team_size=team_size,
            primary_goal=primary_goal,
            province=province,
        )
    except ValueError:
        return RedirectResponse(
            f"/onboarding/setup/{business_id}?error=profile", status_code=303
        )
    db.record_product_event(
        business_id,
        "business_profile_completed",
        f"team_size={team_size};goal={primary_goal}",
    )
    return RedirectResponse(f"/onboarding/whatsapp/{business_id}", status_code=303)


@app.get("/onboarding/whatsapp/{business_id}", response_class=HTMLResponse)
def onboarding_whatsapp(request: Request, business_id: int):
    # Aislamiento: solo el dueño de ESTE negocio puede ver su onboarding.
    user = auth.current_user(request)
    if not user or user["business_id"] != business_id:
        return RedirectResponse("/login", status_code=303)
    biz = db.get_business(business_id)
    link = whatsapp.start_link(business_id)
    return TEMPLATES.TemplateResponse(request, "whatsapp_connect.html",
                                      {"business": biz, "wa": link})


@app.post("/b/{business_id}/fiscal")
def update_fiscal(business_id: int, name: str = Form(""), nif: str = Form(""),
                  address: str = Form(""), default_vat: float = Form(21),
                  default_irpf: float = Form(0)):
    try:
        db.update_fiscal(business_id, name=name or None, nif=nif or None,
                         address=address or None, default_vat=default_vat,
                         default_irpf=default_irpf)
    except ValueError:
        return RedirectResponse(
            f"/b/{business_id}/ajustes?error=fiscal", status_code=303
        )
    db.record_product_event(business_id, "fiscal_profile_updated")
    return RedirectResponse(f"/b/{business_id}/ajustes", status_code=303)


@app.post("/b/{business_id}/payment-details")
def update_payment_details(business_id: int, payment_iban: str = Form(""),
                           payment_bizum: str = Form(""), payment_note: str = Form("")):
    try:
        db.update_payment_details(business_id, iban=payment_iban,
                                  bizum=payment_bizum, note=payment_note)
    except ValueError:
        return RedirectResponse(
            f"/b/{business_id}/ajustes?error=cobro#cobro", status_code=303
        )
    db.record_product_event(business_id, "payment_details_updated")
    return RedirectResponse(f"/b/{business_id}/ajustes#cobro", status_code=303)


@app.post("/b/{business_id}/payment-reminders")
def update_payment_reminders(
    business_id: int,
    payment_reminders_enabled: str = Form(""),
    payment_reminder_days: str = Form("3,7,15"),
):
    try:
        settings = db.update_payment_reminder_settings(
            business_id,
            enabled=payment_reminders_enabled in {
                "1", "true", "on", "si", "sí"
            },
            days=payment_reminder_days,
        )
    except ValueError:
        return RedirectResponse(
            f"/b/{business_id}/ajustes?error=recordatorios#recordatorios",
            status_code=303,
        )
    if settings is None:
        return RedirectResponse("/login", status_code=303)
    db.record_product_event(business_id, "payment_reminder_settings_updated")
    return RedirectResponse(
        f"/b/{business_id}/ajustes#recordatorios", status_code=303
    )


@app.post("/b/{business_id}/whatsapp-reports")
def update_whatsapp_reports(
    business_id: int,
    brief_manana: str = Form(""),
    cierre_tarde: str = Form(""),
    hora_tarde: str = Form("19"),
    resumen_semanal: str = Form(""),
    aviso_fiscal: str = Form(""),
):
    on = {"1", "true", "on", "si", "sí"}
    try:
        hora = int(hora_tarde)
    except ValueError:
        hora = 19
    settings = db.update_whatsapp_reports(business_id, {
        "brief_manana": brief_manana in on,
        "cierre_tarde": cierre_tarde in on,
        "hora_tarde": hora,
        "resumen_semanal": resumen_semanal in on,
        "aviso_fiscal": aviso_fiscal in on,
    })
    if settings is None:
        return RedirectResponse("/login", status_code=303)
    db.record_product_event(business_id, "whatsapp_reports_updated")
    return RedirectResponse(
        f"/b/{business_id}/ajustes#informes", status_code=303
    )


@app.post("/b/{business_id}/gestoria")
def update_gestoria(
    business_id: int,
    gestoria_name: str = Form(""),
    gestoria_email: str = Form(""),
    gestoria_cadence: str = Form("off"),
):
    try:
        settings = db.update_gestoria_settings(
            business_id,
            name=gestoria_name,
            email=gestoria_email,
            cadence=gestoria_cadence,
        )
    except ValueError:
        return RedirectResponse(
            f"/b/{business_id}/ajustes?error=gestoria#gestoria",
            status_code=303,
        )
    if settings is None:
        return RedirectResponse("/login", status_code=303)
    db.record_product_event(business_id, "gestoria_settings_updated")
    return RedirectResponse(
        f"/b/{business_id}/ajustes#gestoria", status_code=303
    )


@app.post("/b/{business_id}/gestoria/send-now")
def gestoria_send_now(business_id: int):
    from . import gestoria as gestoria_service
    business = db.get_business(business_id)
    if not business or (business.get("gestoria_cadence") or "off") == "off":
        return RedirectResponse(
            f"/b/{business_id}/ajustes?error=gestoria#gestoria",
            status_code=303,
        )
    label = gestoria_service.previous_label(business["gestoria_cadence"])
    emailed = gestoria_service.notify_gestoria(business, label)
    db.record_product_event(
        business_id, "gestoria_send_now",
        json.dumps({"label": label, "emailed": bool(emailed)},
                   separators=(",", ":")),
    )
    ok = "gestoria-enviado" if emailed else "gestoria-enlace"
    return RedirectResponse(
        f"/b/{business_id}/ajustes?ok={ok}#gestoria", status_code=303
    )


@app.post("/b/{business_id}/clockin-policy")
def update_clockin_policy(
    business_id: int, clockin_policy: str = Form("")
):
    try:
        db.update_clockin_policy(business_id, clockin_policy)
    except ValueError:
        return RedirectResponse(
            f"/b/{business_id}/ajustes?error=clockin-policy", status_code=303
        )
    db.record_product_event(business_id, "clockin_policy_updated")
    return RedirectResponse(f"/b/{business_id}/ajustes", status_code=303)


@app.post("/b/{business_id}/verifactu")
def update_verifactu_mode(
    business_id: int, verifactu_enabled: str = Form("")
):
    try:
        db.update_verifactu_mode(
            business_id, verifactu_enabled in {"1", "true", "on", "si"}
        )
    except ValueError:
        return RedirectResponse(
            f"/b/{business_id}/ajustes?error=verifactu", status_code=303
        )
    db.record_product_event(business_id, "verifactu_mode_updated")
    return RedirectResponse(f"/b/{business_id}/ajustes", status_code=303)


@app.post("/b/{business_id}/branding")
async def update_branding(business_id: int, template: str = Form("clasica"),
                          brand_color: str = Form(""), remove_logo: str = Form(""),
                          logo: UploadFile = File(None)):
    """Personalización de documentos: plantilla, color de marca y logo (o monograma
    automático si no se sube ninguno). El logo se guarda en base64 en la BD."""
    import base64
    logo_data = logo_mime = None
    clear = bool(remove_logo)
    if not clear and logo is not None and logo.filename:
        if logo.content_type not in ("image/png", "image/jpeg"):
            return RedirectResponse(
                f"/b/{business_id}/ajustes?error=logo", status_code=303)
        raw = await logo.read(db.MAX_LOGO_B64)  # límite de lectura defensivo
        if not raw or len(raw) >= db.MAX_LOGO_B64:
            return RedirectResponse(
                f"/b/{business_id}/ajustes?error=logo", status_code=303)
        logo_data = base64.b64encode(raw).decode()
        logo_mime = logo.content_type
    try:
        db.update_branding(business_id, template=template, brand_color=brand_color,
                           logo_data=logo_data, logo_mime=logo_mime, clear_logo=clear)
    except ValueError:
        return RedirectResponse(
            f"/b/{business_id}/ajustes?error=marca", status_code=303)
    return RedirectResponse(f"/b/{business_id}/ajustes", status_code=303)


@app.post("/onboarding/whatsapp/{business_id}/connect")
def onboarding_whatsapp_connect(request: Request, business_id: int):
    # La vinculación real solo ocurre al recibir el código desde ese WhatsApp.
    user = auth.current_user(request)
    if not user or user["business_id"] != business_id:
        return RedirectResponse("/login", status_code=303)
    business = db.get_business(business_id)
    if not business or business.get("whatsapp_status") != "conectado":
        db.set_whatsapp_status(business_id, "no_conectado")
    db.finish_onboarding(business_id)
    db.record_product_event(
        business_id,
        "onboarding_completed",
        f"whatsapp={business.get('whatsapp_status') if business else 'unknown'}",
    )
    return RedirectResponse(f"/b/{business_id}/resumen", status_code=303)


# ============================================================== WEBHOOK ===== #
@app.get("/webhook/whatsapp")
def whatsapp_verify(request: Request):
    # Verificación del webhook de Meta: devuelve el challenge solo si el token coincide.
    params = request.query_params
    expected = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == expected:
        return Response(content=params.get("hub.challenge", ""))
    if not expected and not config.IS_PRODUCTION:
        return Response(content=params.get("hub.challenge", "ok"))
    return JSONResponse({"error": "token inválido"}, status_code=403)


@app.post("/webhook/whatsapp")
async def whatsapp_inbound(request: Request):
    # Enruta el mensaje entrante: vincula por código o lo pasa al cerebro del negocio.
    raw = await request.body()
    if len(raw) > config.MAX_JSON_BYTES:
        return JSONResponse({"error": "payload demasiado grande"}, status_code=413)
    if not whatsapp.verify_signature(
        raw, request.headers.get("x-hub-signature-256", "")
    ):
        return JSONResponse({"error": "firma inválida"}, status_code=401)
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JSONResponse({"error": "JSON inválido"}, status_code=400)
    try:
        result = await run_in_threadpool(whatsapp.handle_inbound, payload)
    except whatsapp.WebhookInProgress:
        return JSONResponse(
            {"error": "evento todavía en proceso"}, status_code=503
        )
    except Exception:
        logging.getLogger("uvicorn.error").exception(
            "Falló el procesamiento del webhook de WhatsApp."
        )
        return JSONResponse({"error": "procesamiento fallido"}, status_code=500)
    return {"status": "processed", **result}


# ============================================================ SUSCRIPCIÓN === #
@app.post("/b/{business_id}/suscripcion/checkout")
def subscription_checkout(request: Request, business_id: int, plan: str = Form("autonomo")):
    if plan not in billing_adapter.PLAN_PRICES:
        return RedirectResponse(
            f"/b/{business_id}/suscripcion?status=invalid", status_code=303
        )
    biz = db.get_business(business_id)
    db.record_product_event(business_id, "checkout_started", f"plan={plan}")
    provider = billing_adapter.get_provider()
    base = f"{config.BASE_URL}/b/{business_id}/suscripcion"
    url = provider.checkout_url(biz, plan, f"{base}?status=ok", f"{base}?status=cancel")
    if not url:
        # Sin Stripe configurado: deja constancia de la intención (alta manual).
        return RedirectResponse(f"{base}?status=manual", status_code=303)
    return RedirectResponse(url, status_code=303)


@app.post("/b/{business_id}/suscripcion/portal")
def subscription_portal(request: Request, business_id: int):
    biz = db.get_business(business_id)
    url = billing_adapter.get_provider().portal_url(
        biz, f"{config.BASE_URL}/b/{business_id}/suscripcion")
    if not url:
        return RedirectResponse(f"/b/{business_id}/suscripcion?status=noportal",
                                status_code=303)
    return RedirectResponse(url, status_code=303)


@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Recibe eventos de Stripe y actualiza el estado de la suscripción del negocio."""
    payload = await request.body()
    event = billing_adapter.verify_webhook(payload, request.headers.get("stripe-signature", ""))
    if event is None:
        return JSONResponse({"error": "firma inválida"}, status_code=400)
    event_id = str(event.get("id") or "")
    if not event_id:
        return JSONResponse({"error": "evento sin id"}, status_code=400)
    if not db.claim_webhook_event("stripe", event_id):
        claimed = db.webhook_event("stripe", event_id) or {}
        if claimed.get("status") == "processing":
            return JSONResponse(
                {"error": "evento todavía en proceso"}, status_code=503
            )
        return {"received": True, "duplicate": True}
    try:
        _apply_stripe_event(event)
    except Exception as exc:
        db.fail_webhook_event("stripe", event_id, str(exc))
        logging.getLogger("uvicorn.error").exception(
            "Falló el procesamiento del webhook de Stripe %s.", event_id
        )
        return JSONResponse({"error": "procesamiento fallido"}, status_code=500)
    db.complete_webhook_event("stripe", event_id)
    return {"received": True}


def _apply_stripe_event(event: dict) -> None:
    """Aplica un evento ya verificado; el endpoint gestiona su ciclo idempotente."""
    obj = event.get("data", {}).get("object", {})
    etype = event.get("type", "")
    bid = (obj.get("metadata") or {}).get("business_id") or obj.get("client_reference_id")
    try:
        bid = int(bid) if bid else None
    except (TypeError, ValueError):
        bid = None
    if etype == "checkout.session.completed" and bid:
        biz = db.get_business(bid)
        if biz:
            db.set_subscription(
                bid,
                "active",
                plan=(obj.get("metadata") or {}).get("plan"),
                customer_id=obj.get("customer"),
                subscription_id=obj.get("subscription"),
            )
            db.record_product_event(bid, "subscription_activated")
    elif etype in ("customer.subscription.created", "customer.subscription.updated"):
        biz = db.get_business_by_stripe_customer(obj.get("customer"))
        if not biz and bid:
            biz = db.get_business(bid)
        if biz:
            stripe_status = obj.get("status")
            status = {
                "active": "active", "trialing": "active",
                "past_due": "past_due", "unpaid": "past_due",
                "canceled": "canceled", "incomplete_expired": "canceled",
            }.get(stripe_status, "trial")
            db.set_subscription(
                biz["id"], status,
                plan=(obj.get("metadata") or {}).get("plan"),
                customer_id=obj.get("customer"),
                subscription_id=obj.get("id"),
            )
            if status == "active":
                db.record_product_event(biz["id"], "subscription_active")
    elif etype == "customer.subscription.deleted":
        biz = db.get_business_by_stripe_customer(obj.get("customer"))
        if biz:
            db.set_subscription(biz["id"], "canceled")
    elif etype == "invoice.payment_failed":
        biz = db.get_business_by_stripe_customer(obj.get("customer"))
        if biz:
            db.set_subscription(biz["id"], "past_due")
            db.record_product_event(biz["id"], "subscription_payment_failed")
    elif etype in ("invoice.paid", "invoice.payment_succeeded"):
        biz = db.get_business_by_stripe_customer(obj.get("customer"))
        if biz:
            db.set_subscription(biz["id"], "active")
            db.record_product_event(biz["id"], "subscription_invoice_paid")


# ========================================================= ADMIN (fundador) = #
def _is_admin(request: Request) -> bool:
    user = auth.current_user(request)
    if not user:
        return False
    if user.get("is_admin"):
        return True
    return bool(config.ADMIN_EMAIL) and user["email"].lower() == config.ADMIN_EMAIL


@app.get("/admin", response_class=HTMLResponse)
def admin_panel(request: Request):
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    data = db.admin_overview()
    data["backup"] = backups.admin_backup_status()
    return TEMPLATES.TemplateResponse(request, "admin.html",
                                      {"data": data})


@app.get("/admin/backups/latest")
def admin_download_latest_backup(request: Request):
    if not _is_admin(request):
        return Response("No autorizado.", status_code=403)
    path = backups.latest_verified_backup()
    if not path:
        return Response("No hay ninguna copia verificada disponible.", status_code=404)
    media_type = (
        "application/gzip"
        if path.name.endswith((".gz", ".dump"))
        else "application/vnd.sqlite3"
    )
    return FileResponse(path, media_type=media_type, filename=path.name)


# ===================================================== RESET DE CONTRASEÑA == #
import secrets  # noqa: E402


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@app.get("/recuperar", response_class=HTMLResponse)
def forgot_page(request: Request, sent: str = ""):
    return TEMPLATES.TemplateResponse(request, "forgot.html", {"sent": sent})


@app.post("/recuperar")
def forgot_submit(request: Request, email: str = Form(...)):
    key = f"forgot:{auth.client_ip(request)}"
    if auth.is_rate_limited(key):
        return RedirectResponse("/recuperar?sent=1", status_code=303)
    auth.record_failed_attempt(key)
    email = (email or "").strip().lower()
    user = db.get_user_by_email(email)
    if user:  # Si no existe, no lo revelamos (respuesta idéntica).
        token = secrets.token_urlsafe(32)
        db.create_password_reset(user["id"], _hash_token(token), ttl_minutes=60)
        link = f"{config.BASE_URL}/restablecer?token={token}"
        email_adapter.send_email(
            email, "Restablecer tu contraseña de Noesis",
            f"Hola,\n\nPara crear una contraseña nueva, abre este enlace (válido 1 hora):\n"
            f"{link}\n\nSi no lo has pedido tú, ignora este correo.\n\n— Noesis")
    return RedirectResponse("/recuperar?sent=1", status_code=303)


@app.get("/restablecer", response_class=HTMLResponse)
def reset_page(request: Request, token: str = "", error: str = ""):
    return TEMPLATES.TemplateResponse(request, "reset.html",
                                      {"token": token, "error": error})


@app.post("/restablecer")
def reset_submit(request: Request, token: str = Form(...), password: str = Form(...)):
    if len(password) < 12 or len(password) > 1024:
        return RedirectResponse(f"/restablecer?token={token}&error=password",
                                status_code=303)
    row = db.use_password_reset(_hash_token(token))
    if not row:
        return RedirectResponse("/restablecer?error=token", status_code=303)
    db.set_password(row["user_id"], auth.hash_password(password))
    return RedirectResponse("/login?error=reset_ok", status_code=303)


def main() -> None:
    import os
    import uvicorn
    # En local: 127.0.0.1:8000. En producción el host (Railway/Render) inyecta
    # PORT y necesita escuchar en 0.0.0.0.
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("noesis.web.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
