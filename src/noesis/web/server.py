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

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.concurrency import run_in_threadpool

from .. import config, db, verifactu_client
from ..adapters import billing as billing_adapter
from ..adapters import email as email_adapter
from ..tools import run_tool
from . import auth, backups, chat, reports, whatsapp
from .deps import HERE, TEMPLATES, _read_json, auth_guard
from .routers import admin, assistant, clients, documents, finance, gestoria, invoicing, pages, portal, team, webhooks
from .scheduler import start_scheduler


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
app.middleware("http")(auth_guard)


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
app.include_router(pages.router)
app.include_router(webhooks.router)


# ====================================================== PORTALES PUBLICOS === #
app.include_router(portal.router)


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


# ================================================================= API ====== #
app.include_router(finance.router)
app.include_router(team.router)
app.include_router(clients.router)
app.include_router(invoicing.router)


app.include_router(assistant.router)


# =========================================================== DOCUMENTOS ===== #
app.include_router(documents.router)


app.include_router(gestoria.router)


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
# Rutas incluidas en routers.webhooks.


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




# ========================================================= ADMIN (fundador) = #
app.include_router(admin.router)


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
