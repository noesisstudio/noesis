"""Servidor web de Bynoesis (FastAPI) — app multipágina.

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
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .. import config, db
from ..adapters import billing as billing_adapter  # noqa: F401 -- compatibilidad de tests/integraciones
from .deps import HERE, TEMPLATES, auth_guard
from .routers import (
    account,
    admin,
    assistant,
    clients,
    documents,
    finance,
    gestoria,
    gestoria_portal,
    invoicing,
    pages,
    portal,
    projects,
    team,
    webhooks,
    whatsapp_business,
)
from .scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: "FastAPI"):
    # Arranque de la app (sustituye al obsoleto @app.on_event("startup")).
    _startup()
    try:
        yield
    finally:
        try:
            # No cerrar conexiones mientras una tarea aún las está utilizando.
            stop_scheduler()
        finally:
            db.close_pool()


app = FastAPI(
    title="Bynoesis",
    version="0.3.0",
    lifespan=lifespan,
    docs_url=None if config.IS_PRODUCTION else "/docs",
    redoc_url=None if config.IS_PRODUCTION else "/redoc",
    openapi_url=None if config.IS_PRODUCTION else "/openapi.json",
)
class _CachedStaticFiles(StaticFiles):
    """Estáticos cacheables: las plantillas los piden con `?v=` y ese sello cambia
    en cada despliegue, así que el navegador puede guardarlos sin miedo a
    quedarse con una versión vieja."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable"
            if config.IS_PRODUCTION
            else "no-cache"
        )
        return response


app.mount(
    "/static", _CachedStaticFiles(directory=str(HERE / "static")), name="static"
)


# --- Guardia de seguridad: protege /b/ y /api/ y comprueba que el usuario sea
#     dueño del negocio que pide (aislamiento entre clientes). Se define ANTES de
#     añadir SessionMiddleware para que éste quede por fuera y la sesión exista aquí.
app.middleware("http")(auth_guard)


if config.ALLOWED_HOSTS != ["*"]:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=config.ALLOWED_HOSTS,
        www_redirect=False,
    )


app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY,
                   max_age=60 * 60 * 24 * 14,        # 14 días
                   same_site="lax",
                   https_only=(config.HTTPS_ONLY or config.IS_PRODUCTION),
                   session_cookie=(
                       "__Host-noesis_session"
                       if config.IS_PRODUCTION else "noesis_session"
                   ))


_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_request_log = logging.getLogger("noesis.request")

# Zonas que no se cuentan: el panel del cliente, la API, los portales por token y
# los estáticos. Solo interesa la web pública, y nunca la actividad de un cliente
# dentro de su cuenta.
_NO_CONTAR = ("/b/", "/api/", "/admin", "/gestoria", "/p/", "/g/", "/t/", "/static/",
              "/webhook/", "/health", "/ready", "/favicon.ico", "/robots.txt",
              "/sitemap.xml", "/llms.txt", "/sw.js",
              # Las mismas rutas que robots.txt esconde de los buscadores: no
              # describen interés por la web, sino uso de una cuenta existente.
              "/login", "/logout", "/onboarding", "/recuperar", "/restablecer")


def _count_public_view(request: Request, status: int) -> None:
    """Suma una visita pública al recuento agregado.

    Sin cookies, sin IP y sin navegador: solo la página, el día y el dominio de
    procedencia. Al no identificar a nadie no necesita consentimiento, y por eso
    tampoco puede reconstruirse el recorrido de una persona concreta.
    """
    if request.method != "GET" or status >= 400:
        return
    ruta = request.url.path
    if ruta != "/gestorias" and ruta.startswith(_NO_CONTAR):
        return
    procedencia = ""
    referer = request.headers.get("referer") or ""
    if referer:
        try:
            host = urlsplit(referer).hostname or ""
        except ValueError:
            host = ""
        # El propio sitio no es una procedencia: solo interesa quién nos trae gente.
        if host and host.lower() not in config.ALLOWED_HOSTS:
            procedencia = host.lower()
    try:
        db.record_page_view(ruta, procedencia)
    except Exception:  # noqa: BLE001
        # Medir nunca puede tumbar una página: es información, no funcionalidad.
        _request_log.warning(json.dumps(
            {"event": "page_view_not_counted"}, separators=(",", ":")
        ))


@app.middleware("http")
async def request_observability(request: Request, call_next):
    """Correlaciona incidencias sin registrar URLs con tokens ni datos personales."""
    supplied = request.headers.get("x-request-id", "")
    request_id = supplied if _REQUEST_ID_RE.fullmatch(supplied) else uuid.uuid4().hex
    request.state.request_id = request_id
    started = time.perf_counter()
    status = 500
    try:
        declared = request.headers.get("content-length")
        if declared:
            try:
                declared_size = int(declared)
            except ValueError:
                status = 400
                response = JSONResponse(
                    {"error": "Content-Length inválido."}, status_code=400
                )
                response.headers["X-Request-ID"] = request_id
                return response
            if declared_size < 0:
                status = 400
                response = JSONResponse(
                    {"error": "Content-Length inválido."}, status_code=400
                )
                response.headers["X-Request-ID"] = request_id
                return response
            if declared_size > config.MAX_REQUEST_BYTES:
                status = 413
                response = JSONResponse(
                    {"error": "La petición supera el tamaño permitido."}, status_code=413
                )
                response.headers["X-Request-ID"] = request_id
                return response
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        _count_public_view(request, status)
        return response
    except Exception:
        # No adjuntar el traceback aquí: excepciones de proveedores o BD pueden
        # contener datos del cliente. El request ID conserva la correlación.
        _request_log.error(json.dumps({
            "event": "http_request_failed",
            "request_id": request_id,
            "method": request.method,
        }, separators=(",", ":")))
        raise
    finally:
        if config.LOG_REQUESTS or status >= 500:
            route = request.scope.get("route")
            route_name = getattr(route, "path", None) or "unmatched"
            _request_log.info(json.dumps({
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "route": route_name,
                "status": status,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }, separators=(",", ":")))


@app.middleware("http")
async def canonical_public_host(request: Request, call_next):
    """Envía el alias público al único origen que firma enlaces y callbacks."""
    base_host = (urlsplit(config.BASE_URL).hostname or "").lower()
    request_host = (request.url.hostname or "").lower()
    if (
        config.IS_PRODUCTION
        and base_host == config.CANONICAL_PUBLIC_HOST
        and request_host == config.PUBLIC_HOST_ALIAS
    ):
        location = f"{config.BASE_URL}{request.url.path}"
        if request.url.query:
            location += f"?{request.url.query}"
        return RedirectResponse(location, status_code=308)
    return await call_next(request)


# Zonas con sesión o tokens de cliente: sin caché y sin terceros en la CSP.
_PRIVATE_ZONES = ("/b/", "/api/", "/admin", "/gestoria", "/p/", "/g/", "/t/")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), geolocation=(self), payment=()"
        if request.url.path.startswith("/t/")
        else "camera=(), geolocation=(), payment=()"
    )
    # robots.txt evita malgastar rastreo en datos y portales, pero no garantiza por
    # sí solo que una URL conocida desaparezca del índice. Toda ruta que no forma
    # parte del sitio público recibe además una orden HTTP explícita de no indexar.
    # Los estáticos quedan fuera: Google debe poder usar el logo y la imagen social.
    # llms.txt tampoco lo lleva: existe para que los asistentes sigan sus enlaces.
    path = request.url.path
    if (
        path not in pages.INDEXABLE_PATHS
        and not path.startswith("/static/")
        and path not in {"/favicon.ico", "/robots.txt", "/sitemap.xml", "/llms.txt"}
    ):
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    # Excepciones: calendario consentido en Contacto y, si está configurado, Google
    # Analytics en la web pública. El script de Google solo lo inserta
    # public-analytics.js tras aceptar el aviso; la CSP únicamente lo permite. Las
    # zonas con datos de clientes nunca abren la política a Google.
    frame_source = "https://cal.com" if path == "/contacto" else "'none'"
    private_zone = path != "/gestorias" and path.startswith(_PRIVATE_ZONES)
    ga_script, ga_connect, ga_img = "", "", ""
    if config.GA_MEASUREMENT_ID and not private_zone:
        ga_script = " https://*.googletagmanager.com"
        ga_connect = (" https://*.google-analytics.com https://*.analytics.google.com"
                      " https://*.googletagmanager.com")
        ga_img = " https://*.google-analytics.com https://*.googletagmanager.com"
    response.headers["Content-Security-Policy"] = (
        f"default-src 'self'; img-src 'self' data:{ga_img}; font-src 'self'; "
        f"style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'{ga_script}; "
        f"connect-src 'self'{ga_connect}; object-src 'none'; frame-src {frame_source}; "
        "frame-ancestors 'none'; base-uri 'self'; "
        "form-action 'self' https://checkout.stripe.com"
    )
    if config.IS_PRODUCTION:
        response.headers["Content-Security-Policy-Report-Only"] = (
            f"default-src 'self'; img-src 'self' data:{ga_img}; font-src 'self'; "
            f"style-src 'self'; script-src 'self'{ga_script}; connect-src 'self'{ga_connect}; "
            f"object-src 'none'; frame-src {frame_source}; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self' https://checkout.stripe.com"
        )
    if config.HTTPS_ONLY or config.IS_PRODUCTION:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    if request.url.path.startswith(_PRIVATE_ZONES):
        response.headers["Cache-Control"] = "no-store"
    if request.url.path.startswith(("/gestoria", "/p/", "/g/", "/t/")):
        response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _startup() -> None:
    import logging
    log = logging.getLogger("uvicorn.error")
    if config.IS_PRODUCTION and (
        config.SECRET_KEY == "dev-secret-cambiar-en-produccion"  # pragma: allowlist secret
        or len(config.SECRET_KEY) < 32
    ):
        raise RuntimeError(
            "NOESIS_SECRET es obligatoria en producción y debe tener al menos 32 caracteres."
        )
    if config.ADMIN_REQUIRE_GOOGLE_OAUTH and not config.google_oauth_available():
        # El panel ya falla cerrado en ``routers.admin._is_admin``: sin un inicio
        # real de Google ninguna sesión puede entrar. Mantener disponible el resto
        # del SaaS evita que una credencial administrativa pendiente tumbe a todos
        # los autónomos durante un despliegue.
        log.error(
            "El panel admin permanece bloqueado: exige Google OAuth y faltan "
            "sus credenciales. El resto del servicio puede arrancar."
        )
    if config.CLAMAV_REQUIRED and not config.CLAMAV_HOST:
        raise RuntimeError(
            "El antivirus es obligatorio, pero NOESIS_CLAMAV_HOST no esta configurado."
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
    if config.INBOUND_EMAIL_ENABLED:
        from ..documents import inbound_email
        if not inbound_email.configured():
            log.error(
                "El buzón documental permanece apagado: se activó la prueba, "
                "pero faltan las credenciales IMAP. El resto del SaaS puede arrancar."
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
        from .. import demo
        try:
            demo.seed_showcase(force=True)
        except Exception:  # noqa: BLE001 - una demo nunca tumba el SaaS real.
            log.exception("No se pudo preparar la demo comercial.")
    start_scheduler()


# ============================================================== PÁGINAS ===== #
app.include_router(pages.router)
app.include_router(webhooks.router)


# ====================================================== PORTALES PUBLICOS === #
app.include_router(portal.router)


# ================================================================ AUTH ====== #
app.include_router(account.router)


# ================================================================= API ====== #
app.include_router(finance.router)
app.include_router(team.router)
app.include_router(clients.router)
app.include_router(invoicing.router)
app.include_router(projects.router)
app.include_router(whatsapp_business.router)


app.include_router(assistant.router)


# =========================================================== DOCUMENTOS ===== #
app.include_router(documents.router)


app.include_router(gestoria.router)
app.include_router(gestoria_portal.router)


# ============================================================== WEBHOOK ===== #
# Rutas incluidas en routers.webhooks.


# ========================================================= ADMIN (fundador) = #
app.include_router(admin.router)


@app.exception_handler(404)
async def pagina_no_encontrada(request: Request, exc):
    """Una dirección mal escrita no debe enseñar el error crudo del servidor.

    La API sigue respondiendo JSON: quien la consume espera datos, no una
    página. Solo se pinta la página en las rutas de navegación.
    """
    ruta = request.url.path
    if ruta.startswith(("/api/", "/webhook/")):
        return JSONResponse({"error": "no encontrado"}, status_code=404)
    return TEMPLATES.TemplateResponse(request, "404.html", {}, status_code=404)



def main() -> None:
    import uvicorn
    # En local: 127.0.0.1:8000. En producción el host (Railway/Render) inyecta
    # PORT y necesita escuchar en 0.0.0.0.
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "noesis.web.server:app",
        host=host,
        port=port,
        reload=False,
        access_log=not config.IS_PRODUCTION,
    )


if __name__ == "__main__":
    main()
