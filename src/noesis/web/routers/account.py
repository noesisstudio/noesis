"""Rutas de cuenta, onboarding, ajustes y suscripcion."""

from __future__ import annotations

import hmac
import base64
import json
import logging
import secrets
import time
from datetime import datetime
from io import BytesIO
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError

from ... import config, db
from ...adapters import billing as billing_adapter
from ...adapters import email as email_adapter
from ...documents import validation as document_validation
from .. import auth, whatsapp
from ..deps import TEMPLATES, _read_json

router = APIRouter()
log = logging.getLogger("uvicorn.error")

_BRAND_UPLOAD_BYTES = 3_000_000


async def _sanitized_brand_image(
    upload: UploadFile | None, *, footer: bool = False,
) -> tuple[str | None, str | None]:
    """Valida bytes reales, elimina metadatos y limita dimensiones antes de guardar."""
    if upload is None or not upload.filename:
        return None, None
    mime_to_ext = {
        "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
    }
    ext = mime_to_ext.get(upload.content_type or "")
    if not ext:
        raise ValueError("Usa una imagen PNG, JPG o WebP.")
    raw = await upload.read(_BRAND_UPLOAD_BYTES + 1)
    if not raw or len(raw) > _BRAND_UPLOAD_BYTES:
        raise ValueError("La imagen no puede superar 3 MB.")
    document_validation.validate(f"marca{ext}", raw)
    try:
        with Image.open(BytesIO(raw)) as source:
            image = ImageOps.exif_transpose(source)
            image.thumbnail((1800, 600) if footer else (600, 600))
            has_alpha = image.mode in {"RGBA", "LA"} or "transparency" in image.info
            clean = image.convert("RGBA" if has_alpha else "RGB")
            output = BytesIO()
            clean.save(output, format="PNG", optimize=True)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("No se ha podido preparar esa imagen.") from exc
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    limit = db.MAX_FOOTER_IMAGE_B64 if footer else db.MAX_LOGO_B64
    if len(encoded) > limit:
        label = "pie" if footer else "logo"
        raise ValueError(f"La imagen del {label} sigue siendo demasiado grande.")
    return encoded, "image/png"

_GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleOAuthError(RuntimeError):
    """La identidad de Google no se pudo verificar con seguridad."""


def _google_redirect_uri() -> str:
    return f"{config.BASE_URL}/auth/google/callback"


def _signup_selection(
    plan: str = "", billing: str = "monthly", intent: str = "trial"
) -> tuple[str, str, str]:
    return (
        plan if plan in billing_adapter.PLAN_PRICES else "autonomo",
        billing if billing in {"monthly", "annual"} else "monthly",
        intent if intent in {"trial", "subscribe"} else "trial",
    )


def _google_return_path(flow: str, error: str = "", plan: str = "",
                        billing: str = "monthly", intent: str = "trial") -> str:
    target = "/onboarding" if flow == "signup" else "/login"
    query: dict[str, str] = {}
    if error:
        query["error"] = error
    if flow == "signup":
        plan, billing, intent = _signup_selection(plan, billing, intent)
        query.update({"plan": plan, "billing": billing, "intent": intent})
    return target + (f"?{urlparse.urlencode(query)}" if query else "")


def _start_session(request: Request, user: dict, *, auth_provider: str = "password") -> None:
    request.session.clear()
    request.session["uid"] = user["id"]
    request.session["bid"] = user["business_id"]
    request.session["sv"] = user.get("session_version", 0)
    request.session["seen"] = int(time.time())
    request.session["auth_provider"] = auth_provider


def _google_profile(code: str) -> dict:
    """Intercambia un código de un solo uso y pide el perfil OIDC verificado."""
    payload = urlparse.urlencode({
        "code": code,
        "client_id": config.GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": config.GOOGLE_OAUTH_CLIENT_SECRET,
        "redirect_uri": _google_redirect_uri(),
        "grant_type": "authorization_code",
    }).encode("utf-8")
    try:
        token_request = urlrequest.Request(
            _GOOGLE_TOKEN_URL, data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urlrequest.urlopen(token_request, timeout=10) as response:
            token = json.loads(response.read().decode("utf-8"))
        access_token = str(token.get("access_token") or "")
        if not access_token:
            raise GoogleOAuthError("Google no entregó un acceso válido.")
        profile_request = urlrequest.Request(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        with urlrequest.urlopen(profile_request, timeout=10) as response:
            profile = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, KeyError, json.JSONDecodeError, urlerror.URLError,
            urlerror.HTTPError) as exc:
        raise GoogleOAuthError("No se pudo verificar la identidad con Google.") from exc
    verified = profile.get("email_verified")
    email = str(profile.get("email") or "").strip().lower()
    if not profile.get("sub") or verified not in {True, "true"} or not auth.valid_email(email):
        raise GoogleOAuthError("Google no confirmó un correo válido.")
    return {
        "email": email,
        "name": str(profile.get("name") or "").strip()[:160],
    }

# ================================================================ AUTH ====== #
def _account_destination(business_id: int, user: dict | None = None) -> str:
    """Cada identidad entra por donde trabaja.

    Administracion no usa Bynoesis para llevar un negocio: entra a gestionar los de
    los demas. Aterrizar en un panel con Trabajos, Clientes y Facturas la obliga a
    buscar la puerta de su propio trabajo, y a completar un alta que no le sirve.
    Su panel de negocio sigue existiendo y accesible desde el propio /admin.
    """
    if user and (
        bool(user.get("is_admin")) or config.is_admin_email(user.get("email"))
    ):
        return "/admin"
    return db.onboarding_destination(business_id) or f"/b/{business_id}/resumen"


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    return TEMPLATES.TemplateResponse(request, "login.html", {
        "error": error,
        "google_oauth_available": config.google_oauth_available(),
    })


@router.post("/login")
def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    email = (email or "").strip().lower()
    keys = (
        f"login-ip:{auth.client_ip(request)}",
        f"login-account:{email}",
    )
    if any(auth.is_rate_limited(key) for key in keys):
        return RedirectResponse("/login?error=throttle", status_code=303)
    user = db.get_user_by_email(email)
    if not user or not auth.verify_password(password, user["password_hash"]):
        for key in keys:
            auth.record_failed_attempt(key)
        return RedirectResponse("/login?error=1", status_code=303)
    for key in keys:
        auth.clear_attempts(key)
    if not db.user_can_sign_in(user):
        # Se avisa despues de comprobar la contrasena: asi el mensaje no revela
        # que una cuenta existe a quien solo esta probando correos.
        return RedirectResponse("/login?error=suspended", status_code=303)
    _start_session(request, user)
    return RedirectResponse(
        _account_destination(user["business_id"], user), status_code=303
    )


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    response = RedirectResponse("/login", status_code=303)
    response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage"'
    return response


@router.get("/auth/google")
def google_start(request: Request, flow: str = "login", plan: str = "",
                 billing: str = "monthly", intent: str = "trial"):
    """Empieza OAuth con state de un solo uso y no filtra el secreto al cliente."""
    flow = "signup" if flow == "signup" else "login"
    if flow == "signup" and not config.public_signup_available():
        return RedirectResponse("/onboarding", status_code=303)
    plan, billing, intent = _signup_selection(plan, billing, intent)
    if not config.google_oauth_available():
        return RedirectResponse(
            _google_return_path(
                flow, "google_unavailable", plan, billing, intent
            ), status_code=303
        )
    key = f"google-oauth:{auth.client_ip(request)}"
    if auth.is_rate_limited(key):
        return RedirectResponse(
            _google_return_path(flow, "throttle", plan, billing, intent), status_code=303
        )
    state = secrets.token_urlsafe(32)
    request.session["google_oauth_state"] = state
    request.session["google_oauth_flow"] = flow
    request.session["google_oauth_plan"] = plan
    request.session["google_oauth_billing"] = billing
    request.session["google_oauth_intent"] = intent
    query = urlparse.urlencode({
        "client_id": config.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": _google_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    })
    return RedirectResponse(f"{_GOOGLE_AUTHORIZE_URL}?{query}", status_code=303)


@router.get("/auth/google/callback")
def google_callback(request: Request, code: str = "", state: str = "",
                    error: str = ""):
    flow = str(request.session.pop("google_oauth_flow", "login"))
    plan = str(request.session.pop("google_oauth_plan", ""))
    billing = str(request.session.pop("google_oauth_billing", "monthly"))
    intent = str(request.session.pop("google_oauth_intent", "trial"))
    expected_state = str(request.session.pop("google_oauth_state", ""))
    if error or not code:
        return RedirectResponse(
            _google_return_path(
                flow, "google_cancelled", plan, billing, intent
            ), status_code=303
        )
    if not expected_state or not state or not hmac.compare_digest(expected_state, state):
        auth.record_failed_attempt(f"google-oauth:{auth.client_ip(request)}")
        return RedirectResponse(
            _google_return_path(flow, "google_failed", plan, billing, intent), status_code=303
        )
    try:
        profile = _google_profile(code)
    except GoogleOAuthError:
        auth.record_failed_attempt(f"google-oauth:{auth.client_ip(request)}")
        return RedirectResponse(
            _google_return_path(flow, "google_failed", plan, billing, intent), status_code=303
        )
    auth.clear_attempts(f"google-oauth:{auth.client_ip(request)}")
    user = db.get_user_by_email(profile["email"])
    if user:
        if not db.user_can_sign_in(user):
            return RedirectResponse("/login?error=suspended", status_code=303)
        _start_session(request, user, auth_provider="google")
        return RedirectResponse(
        _account_destination(user["business_id"], user), status_code=303
    )
    request.session["google_signup"] = profile
    request.session["signup_plan"] = plan
    request.session["signup_billing"] = billing
    request.session["signup_intent"] = intent
    query = urlparse.urlencode({
        "plan": plan, "billing": billing, "intent": intent,
    })
    return RedirectResponse(f"/onboarding/google?{query}", status_code=303)




# ================================================================ RGPD ====== #
def _json_download(data: dict, filename: str) -> Response:
    return Response(content=json.dumps(data, ensure_ascii=False, indent=2, default=str),
                    media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/api/{business_id}/export")
def api_export_account(business_id: int):
    """Portabilidad RGPD: descarga TODOS los datos de la cuenta en JSON."""
    return _json_download(db.export_business_data(business_id),
                          "noesis_datos_cuenta.json")


@router.get("/api/{business_id}/clients/{client_id}/export")
def api_export_client(business_id: int, client_id: int):
    data = db.export_client_data(client_id, business_id)
    if data is None:
        return JSONResponse({"error": "Cliente no encontrado."}, status_code=404)
    return _json_download(data, f"noesis_cliente_{client_id}.json")


@router.delete("/api/{business_id}/clients/{client_id}/erase")
def api_erase_client(business_id: int, client_id: int):
    """Borra datos prescindibles y conserva lo sujeto a obligación fiscal."""
    ok = db.delete_client_cascade(client_id, business_id)
    if not ok:
        return JSONResponse({"error": "Cliente no encontrado."}, status_code=404)
    return {"ok": True}


@router.post("/b/{business_id}/account/delete")
def delete_account(request: Request, business_id: int, confirm: str = Form(""),
                   password: str = Form("")):
    """Borra si es posible o registra una baja sujeta a conservación legal."""
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
        privacy_request = db.create_privacy_request(
            business_id,
            requester_user_id=user["id"],
            request_type="account_closure",
            retention_required=True,
        )
        try:
            db.record_security_event(
                "privacy.account_closure_requested",
                severity="warning",
                area="privacy",
                actor_user_id=user["id"],
                subject_business_id=business_id,
                request_id=getattr(request.state, "request_id", None),
                metadata={
                    "privacy_request_id": privacy_request["id"],
                    "retention_required": True,
                },
            )
        except db.DatabaseError:
            log.exception(
                "No se pudo auditar la solicitud de privacidad %s.",
                privacy_request["id"],
            )
        business = db.get_business(business_id) or {}
        inbox = config.LEGAL_EMAIL or config.ADMIN_EMAIL
        if inbox:
            try:
                email_adapter.queue_email(
                    inbox,
                    f"Solicitud de baja RGPD #{privacy_request['id']}",
                    "\n".join([
                        "Se ha registrado una solicitud de baja con conservación legal.",
                        f"Solicitud: #{privacy_request['id']}",
                        f"Negocio: {business.get('name') or business_id}",
                        f"Cuenta interna: {business_id}",
                        "",
                        "Revísala en el panel interno. Registrar la solicitud no borra",
                        "documentos ni resuelve por sí solo los plazos de conservación.",
                    ]),
                    business_id=business_id,
                    idempotency_key=(
                        f"privacy-request-admin:{privacy_request['id']}"
                    ),
                )
            except (ValueError, *db.DatabaseError):
                log.exception(
                    "No se pudo encolar el aviso interno de privacidad %s.",
                    privacy_request["id"],
                )
        try:
            email_adapter.queue_email(
                user["email"],
                "Hemos registrado tu solicitud de baja · Bynoesis",
                "\n".join([
                    "Hemos registrado tu solicitud de baja.",
                    f"Referencia: #{privacy_request['id']}",
                    "",
                    "Tu cuenta seguirá accesible mientras separamos la información que",
                    "puede borrarse de la que debemos conservar por una obligación legal.",
                    "Te comunicaremos la resolución por correo.",
                    "",
                    f"Contacto de privacidad: {config.LEGAL_EMAIL or config.PUBLIC_CONTACT_EMAIL}",
                ]),
                business_id=business_id,
                idempotency_key=f"privacy-request-user:{privacy_request['id']}",
            )
        except (ValueError, *db.DatabaseError):
            log.exception(
                "No se pudo encolar la confirmación de privacidad %s.",
                privacy_request["id"],
            )
        return RedirectResponse(
            f"/b/{business_id}/ajustes?ok=baja-solicitada#baja-cuenta",
            status_code=303,
        )
    try:
        db.record_security_event(
            "privacy.account_deleted",
            severity="warning",
            area="privacy",
            actor_user_id=user["id"],
            subject_business_id=business_id,
            request_id=getattr(request.state, "request_id", None),
            metadata={"retention_required": False},
        )
    except db.DatabaseError:
        log.exception("La cuenta se borró, pero no se pudo auditar la baja.")
    request.session.clear()
    return RedirectResponse("/?bye=1", status_code=303)




# ================================================= SOLICITUD DE ACCESO ===== #
_REQUEST_ERRORS = {
    "name": "Dinos tu nombre para saber con quién hablamos.",
    "email": "Ese correo no parece válido. Revísalo, por favor.",
    "consent": "Necesitamos tu permiso para guardar tus datos y responderte.",
    "throttle": "Ya hemos recibido tu solicitud. Te escribimos en menos de 24 horas.",
    "sector": "Cuéntanos a qué se dedica tu negocio.",
    "business_name": "Dinos el nombre de la gestoría o despacho.",
    "error": "No hemos podido registrar la solicitud. Inténtalo de nuevo.",
}


@router.get("/solicitar-acceso", response_class=HTMLResponse)
def access_request_form(
    request: Request, error: str = "", enviado: str = "", plan: str = "",
    repetida: str = "", perfil: str = "",
):
    """Formulario público: el alta la aprueba el equipo, no el visitante."""
    return TEMPLATES.TemplateResponse(request, "solicitar_acceso.html", {
        "site_active": "solicitar",
        "error": _REQUEST_ERRORS.get(error, ""),
        "sent": bool(enviado),
        "repeated": bool(repetida),
        "plan_catalog": billing_adapter.PLANS,
        "selected_plan": plan if plan in billing_adapter.PLAN_PRICES else "",
        "selected_profile": "gestoria" if perfil == "gestoria" else "negocio",
    })


@router.post("/solicitar-acceso")
def access_request_submit(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    business_name: str = Form(""),
    sector: str = Form(""),
    phone: str = Form(""),
    message: str = Form(""),
    plan: str = Form(""),
    perfil: str = Form(""),
    acepto: str = Form(""),
    # Campo señuelo: invisible para personas, irresistible para robots de spam.
    # No puede llamarse como un campo real o el autorrelleno del navegador lo
    # completaría solo y descartaríamos solicitudes de personas.
    nsx_check: str = Form(""),
):
    name, email = (name or "").strip(), (email or "").strip().lower()
    is_gestoria = perfil == "gestoria"
    request_kind = "gestoría" if is_gestoria else "acceso"
    profile_query = "&perfil=gestoria" if is_gestoria else ""
    if is_gestoria:
        sector = "Gestoría y asesoría"
    if nsx_check.strip():
        # Un robot lo ha rellenado: se responde como si todo hubiera ido bien para
        # no enseñarle qué le delató. Se deja rastro porque un falso positivo aquí
        # significa perder una solicitud real sin que nadie se entere.
        log.warning(
            "Solicitud descartada por el señuelo antispam (ip=%s).",
            auth.client_ip(request),
        )
        return RedirectResponse(
            f"/solicitar-acceso?enviado=1{profile_query}", status_code=303
        )
    if not name:
        return RedirectResponse(
            f"/solicitar-acceso?error=name{profile_query}", status_code=303
        )
    if not auth.valid_email(email):
        return RedirectResponse(
            f"/solicitar-acceso?error=email{profile_query}", status_code=303
        )
    if is_gestoria and not (business_name or "").strip():
        return RedirectResponse(
            f"/solicitar-acceso?error=business_name{profile_query}", status_code=303
        )
    if not (sector or "").strip():
        return RedirectResponse(
            f"/solicitar-acceso?error=sector{profile_query}", status_code=303
        )
    if not acepto:
        return RedirectResponse(
            f"/solicitar-acceso?error=consent{profile_query}", status_code=303
        )

    # Un mismo correo repitiendo el envío suele ser una persona impaciente, no un
    # ataque: se le agradece y se le dice que ya la tenemos, sin pintarlo de error.
    today = datetime.now().strftime("%Y-%m-%d")
    if db.count_access_requests_since(email, today) >= 3:
        return RedirectResponse(
            f"/solicitar-acceso?enviado=1&repetida=1{profile_query}",
            status_code=303,
        )
    # El corte por IP sí frena envíos masivos desde el mismo sitio.
    ip_key = f"access-request:{auth.client_ip(request)}"
    if auth.is_rate_limited(ip_key):
        return RedirectResponse(
            f"/solicitar-acceso?error=throttle{profile_query}", status_code=303
        )

    try:
        created = db.create_access_request(
            name, email, business_name=business_name, sector=sector,
            phone=phone, message=message,
            plan_interest=plan if plan in billing_adapter.PLAN_PRICES else "",
        )
    except (ValueError, *db.IntegrityError):
        return RedirectResponse(
            f"/solicitar-acceso?error=error{profile_query}", status_code=303
        )
    auth.record_failed_attempt(ip_key)

    # Los correos se encolan, no se envían aquí: hablar con SMTP durante la
    # petición deja al visitante esperando ante una pantalla en blanco si el
    # servidor de correo tarda. El scheduler los envía y reintenta después.
    inbox = (
        config.ACCESS_REQUESTS_EMAIL
        or config.ADMIN_EMAIL
        or config.PUBLIC_CONTACT_EMAIL
    )
    if inbox:
        try:
            email_adapter.queue_email(
                inbox,
                f"Nueva solicitud de {request_kind}: {created['name']}",
                "\n".join([
                    f"Nombre: {created['name']}",
                    f"Correo: {created['email']}",
                    f"Teléfono: {created['phone'] or '—'}",
                    f"A qué se dedica: {created['sector'] or '—'}",
                    f"Negocio: {created['business_name'] or '—'}",
                    f"Plan que miraba: {created['plan_interest'] or '—'}",
                    "",
                    f"Mensaje: {created['message'] or '—'}",
                    "",
                    f"Darle de alta: {config.BASE_URL}/admin#solicitudes",
                ]),
                idempotency_key=f"access-request-notice:{created['id']}",
            )
        except Exception:  # noqa: BLE001
            log.exception("No se pudo avisar de la solicitud %s.", created["id"])
    try:
        email_adapter.queue_email(
            created["email"],
            "Hemos recibido tu solicitud · Bynoesis",
            "\n".join([
                f"Hola, {created['name']}:",
                "",
                "Hemos recibido tu solicitud de acceso a Bynoesis. La revisamos y te",
                "escribimos en menos de 24 horas laborables con tu acceso y una fecha",
                "para ponerlo en marcha juntos.",
                "",
                "Si prefieres que hablemos antes, puedes reservar una llamada aquí:",
                f"{config.BASE_URL}/contacto",
                "",
                "Un saludo,",
                "El equipo de Bynoesis",
            ]),
            idempotency_key=f"access-request-confirmation:{created['id']}",
        )
    except Exception:  # noqa: BLE001
        log.exception("No se pudo confirmar la solicitud %s.", created["id"])
    return RedirectResponse(
        f"/solicitar-acceso?enviado=1{profile_query}", status_code=303
    )


# =========================================================== ONBOARDING ===== #
@router.get("/onboarding", response_class=HTMLResponse)
def onboarding(request: Request, error: str = "", plan: str = "",
               billing: str = "monthly", intent: str = "trial"):
    if not config.public_signup_available():
        # Con el alta cerrada no se enseña una pantalla intermedia: se lleva
        # directamente al formulario, conservando el plan que venía mirando.
        target = "/solicitar-acceso"
        if plan in billing_adapter.PLAN_PRICES:
            target += f"?plan={plan}"
        return RedirectResponse(target, status_code=303)
    selected_plan, selected_billing, selected_intent = _signup_selection(
        plan, billing, intent
    )
    return TEMPLATES.TemplateResponse(request, "onboarding.html", {
        "error": error,
        "selected_plan": selected_plan,
        "selected_billing": selected_billing,
        "selected_intent": selected_intent,
        "plan_catalog": billing_adapter.PLANS,
        "annual_prices": billing_adapter.PLAN_ANNUAL_PRICES,
        "google_oauth_available": config.google_oauth_available(),
    })


@router.post("/onboarding/signup")
def onboarding_signup(request: Request, name: str = Form(...),
                      email: str = Form(...), password: str = Form(...),
                      sector: str = Form(""), acepto: str = Form(""),
                      plan: str = Form("autonomo"), billing: str = Form("monthly"),
                      intent: str = Form("trial")):
    if not config.public_signup_available():
        return TEMPLATES.TemplateResponse(
            request, "registro-cerrado.html",
            {"contact_email": config.PUBLIC_CONTACT_EMAIL},
            status_code=503,
        )
    plan, billing, intent = _signup_selection(plan, billing, intent)
    onboarding_query = (
        f"&plan={plan}&billing={billing}&intent={intent}"
    )
    key = f"signup:{auth.client_ip(request)}"
    if auth.is_rate_limited(key):
        return RedirectResponse(f"/onboarding?error=throttle{onboarding_query}", status_code=303)
    email = (email or "").strip().lower()
    name = (name or "").strip()
    sector = (sector or "").strip()[:80]
    if not name:
        return RedirectResponse(f"/onboarding?error=name{onboarding_query}", status_code=303)
    if not sector:
        return RedirectResponse(f"/onboarding?error=sector{onboarding_query}", status_code=303)
    if not acepto:
        return RedirectResponse(f"/onboarding?error=consent{onboarding_query}", status_code=303)
    if not auth.valid_email(email):
        return RedirectResponse(f"/onboarding?error=email_format{onboarding_query}", status_code=303)
    if len(password) < 12 or len(password) > 1024:
        auth.record_failed_attempt(key)
        return RedirectResponse(f"/onboarding?error=password{onboarding_query}", status_code=303)
    if db.get_user_by_email(email):
        return RedirectResponse(f"/onboarding?error=email{onboarding_query}", status_code=303)
    try:
        biz, user = db.create_account(
            name, email, auth.hash_password(password), sector,
            trial_days=config.TRIAL_DAYS,
        )
    except (ValueError, *db.IntegrityError):
        auth.record_failed_attempt(key)
        return RedirectResponse(f"/onboarding?error=email{onboarding_query}", status_code=303)
    auth.clear_attempts(key)
    _start_session(request, user)
    db.start_onboarding(biz["id"], plan=plan, billing=billing, intent=intent)
    request.session["signup_plan"] = plan
    request.session["signup_billing"] = billing
    request.session["signup_intent"] = intent
    db.record_product_event(biz["id"], "account_created")
    db.record_product_event(
        biz["id"], "plan_interest",
        json.dumps({"plan": plan, "billing_period": billing, "intent": intent},
                   separators=(",", ":")),
    )
    # Evidencia de consentimiento: quién aceptó qué versión, cuándo y desde dónde.
    db.record_product_event(biz["id"], "legal_accepted", json.dumps({
        "version": config.LEGAL_DOCUMENT_VERSION,
        "documents": ["terminos", "privacidad", "encargado-tratamiento"],
        "ip": auth.client_ip(request),
    }))
    return RedirectResponse(f"/onboarding/setup/{biz['id']}", status_code=303)


@router.get("/onboarding/google", response_class=HTMLResponse)
def onboarding_google(request: Request, error: str = "", plan: str = "",
                      billing: str = "monthly", intent: str = "trial"):
    """Completa los datos de negocio tras verificar el correo con Google."""
    if not config.public_signup_available():
        return TEMPLATES.TemplateResponse(
            request, "registro-cerrado.html",
            {"contact_email": config.PUBLIC_CONTACT_EMAIL},
            status_code=503,
        )
    profile = request.session.get("google_signup")
    if not isinstance(profile, dict) or not auth.valid_email(str(profile.get("email") or "")):
        return RedirectResponse("/onboarding", status_code=303)
    selected_plan, selected_billing, selected_intent = _signup_selection(
        plan, billing, intent
    )
    return TEMPLATES.TemplateResponse(request, "onboarding_google.html", {
        "error": error,
        "google_profile": profile,
        "selected_plan": selected_plan,
        "selected_billing": selected_billing,
        "selected_intent": selected_intent,
        "plan_catalog": billing_adapter.PLANS,
        "annual_prices": billing_adapter.PLAN_ANNUAL_PRICES,
    })


@router.post("/onboarding/google")
def onboarding_google_submit(request: Request, name: str = Form(...),
                             sector: str = Form(""), acepto: str = Form(""),
                             plan: str = Form("autonomo"),
                             billing: str = Form("monthly"),
                             intent: str = Form("trial")):
    if not config.public_signup_available():
        return TEMPLATES.TemplateResponse(
            request, "registro-cerrado.html",
            {"contact_email": config.PUBLIC_CONTACT_EMAIL},
            status_code=503,
        )
    profile = request.session.get("google_signup")
    email = str(profile.get("email") or "").strip().lower() if isinstance(profile, dict) else ""
    plan, billing, intent = _signup_selection(plan, billing, intent)
    query = f"?plan={plan}&billing={billing}&intent={intent}"
    error_query = f"{query}{'&' if query else '?'}error="
    if not auth.valid_email(email):
        return RedirectResponse(f"/onboarding{query}", status_code=303)
    if not (name or "").strip():
        return RedirectResponse(f"/onboarding/google{error_query}name", status_code=303)
    sector = (sector or "").strip()[:80]
    if not sector:
        return RedirectResponse(f"/onboarding/google{error_query}sector", status_code=303)
    if not acepto:
        return RedirectResponse(f"/onboarding/google{error_query}consent", status_code=303)
    existing = db.get_user_by_email(email)
    if existing:
        if not db.user_can_sign_in(existing):
            return RedirectResponse("/login?error=suspended", status_code=303)
        _start_session(request, existing, auth_provider="google")
        return RedirectResponse(
            _account_destination(existing["business_id"], existing), status_code=303
        )
    try:
        biz, user = db.create_account(
            (name or "").strip(), email, auth.hash_password(secrets.token_urlsafe(48)),
            sector, trial_days=config.TRIAL_DAYS,
        )
    except (ValueError, *db.IntegrityError):
        return RedirectResponse(f"/onboarding/google{error_query}email", status_code=303)
    _start_session(request, user, auth_provider="google")
    db.start_onboarding(biz["id"], plan=plan, billing=billing, intent=intent)
    request.session.pop("google_signup", None)
    request.session["signup_plan"] = plan
    request.session["signup_billing"] = billing
    request.session["signup_intent"] = intent
    db.record_product_event(biz["id"], "account_created_google")
    db.record_product_event(
        biz["id"], "plan_interest",
        json.dumps({
            "plan": plan, "billing_period": billing, "intent": intent,
        }, separators=(",", ":")),
    )
    db.record_product_event(biz["id"], "legal_accepted", json.dumps({
        "version": config.LEGAL_DOCUMENT_VERSION,
        "documents": ["terminos", "privacidad", "encargado-tratamiento"],
        "ip": auth.client_ip(request),
        "signup_method": "google",
    }))
    return RedirectResponse(f"/onboarding/setup/{biz['id']}", status_code=303)


@router.get("/onboarding/setup/{business_id}", response_class=HTMLResponse)
def onboarding_setup(request: Request, business_id: int, error: str = ""):
    user = auth.current_user(request)
    if not user or user["business_id"] != business_id:
        return RedirectResponse("/login", status_code=303)
    biz = db.get_business(business_id)
    if not biz:
        return RedirectResponse("/onboarding", status_code=303)
    return TEMPLATES.TemplateResponse(
        request, "onboarding_setup.html", {
            "business": biz,
            "error": error,
            "ai_credits": db.ai_credit_status(business_id),
            "signup_intent": biz.get("onboarding_intent") or "trial",
        }
    )


@router.post("/onboarding/setup/{business_id}")
def onboarding_setup_submit(
    request: Request,
    business_id: int,
    sector: str = Form(...),
    team_size: str = Form(...),
    primary_goal: str = Form(...),
    province: str = Form(""),
    ai_mode: str = Form("enabled"),
    explanation_level: str = Form("claro"),
):
    user = auth.current_user(request)
    if not user or user["business_id"] != business_id:
        return RedirectResponse("/login", status_code=303)
    if not db.subscription_allows_access(db.get_business(business_id)):
        return RedirectResponse(
            f"/b/{business_id}/suscripcion?status=readonly", status_code=303
        )
    try:
        if ai_mode not in {"enabled", "disabled"}:
            raise ValueError("El modo de IA no es válido.")
        db.update_business_profile(
            business_id,
            sector=sector,
            team_size=team_size,
            primary_goal=primary_goal,
            province=province,
        )
        db.update_integration_setting(business_id, "ai_external", ai_mode)
        db.update_explanation_level(business_id, explanation_level)
    except ValueError:
        return RedirectResponse(
            f"/onboarding/setup/{business_id}?error=profile", status_code=303
        )
    db.record_product_event(
        business_id,
        "business_profile_completed",
        f"team_size={team_size};goal={primary_goal}",
    )
    db.record_product_event(
        business_id,
        "ai_onboarding_decision",
        json.dumps({
            "mode": ai_mode,
            "version": "2026-07-14",
            "local_first": True,
        }, separators=(",", ":")),
    )
    db.complete_onboarding_step(business_id, "profile")
    return RedirectResponse(
        f"/onboarding/preferences/{business_id}", status_code=303
    )


@router.get("/onboarding/preferences/{business_id}", response_class=HTMLResponse)
def onboarding_preferences(request: Request, business_id: int, error: str = ""):
    user = auth.current_user(request)
    if not user or user["business_id"] != business_id:
        return RedirectResponse("/login", status_code=303)
    business = db.get_business(business_id)
    if not business:
        return RedirectResponse("/onboarding", status_code=303)
    return TEMPLATES.TemplateResponse(
        request, "onboarding_preferences.html", {
            "business": business,
            "error": error,
            "wa_reports": db.resolve_whatsapp_reports(
                business.get("whatsapp_reports")
            ),
            "signup_intent": business.get("onboarding_intent") or "trial",
        },
    )


@router.post("/onboarding/preferences/{business_id}")
async def onboarding_preferences_submit(
    request: Request,
    business_id: int,
    nif: str = Form(""),
    address: str = Form(""),
    default_vat: float = Form(21),
    default_irpf: float = Form(0),
    default_payment_term_days: int = Form(15),
    invoice_template: str = Form("clasica"),
    brand_color: str = Form("#14463b"),
    document_footer: str = Form(""),
    quote_terms: str = Form(""),
    footer_image_width: int = Form(100),
    footer_image_alignment: str = Form("center"),
    footer_image_scope: str = Form("invoices"),
    payment_iban: str = Form(""),
    payment_bizum: str = Form(""),
    payment_note: str = Form(""),
    payment_reminders_enabled: str = Form(""),
    payment_reminder_days: str = Form("3,7,15"),
    brief_manana: str = Form(""),
    cierre_tarde: str = Form(""),
    hora_tarde: int = Form(19),
    resumen_semanal: str = Form(""),
    aviso_fiscal: str = Form(""),
    gestoria_name: str = Form(""),
    gestoria_email: str = Form(""),
    gestoria_cadence: str = Form("off"),
    logo: UploadFile = File(None),
    footer_image: UploadFile = File(None),
):
    user = auth.current_user(request)
    if not user or user["business_id"] != business_id:
        return RedirectResponse("/login", status_code=303)
    if not db.subscription_allows_access(db.get_business(business_id)):
        return RedirectResponse(
            f"/b/{business_id}/suscripcion?status=readonly", status_code=303
        )
    on = {"1", "true", "on", "si", "sí"}
    try:
        logo_data, logo_mime = await _sanitized_brand_image(logo)
        footer_data, footer_mime = await _sanitized_brand_image(
            footer_image, footer=True
        )
        if gestoria_cadence not in db.GESTORIA_CADENCES:
            raise ValueError("La cadencia de gestoría no es válida.")
        if gestoria_cadence != "off" and not auth.valid_email(
            gestoria_email.strip().lower()
        ):
            raise ValueError("La gestoría necesita un email válido.")
        db.update_onboarding_preferences(
            business_id,
            nif=nif,
            address=address,
            default_vat=default_vat,
            default_irpf=default_irpf,
            default_payment_term_days=default_payment_term_days,
            invoice_template=invoice_template,
            payment_iban=payment_iban,
            payment_bizum=payment_bizum,
            payment_note=payment_note,
            payment_reminders_enabled=payment_reminders_enabled in on,
            payment_reminder_days=payment_reminder_days,
            whatsapp_reports={
                "brief_manana": brief_manana in on,
                "cierre_tarde": cierre_tarde in on,
                "hora_tarde": hora_tarde,
                "resumen_semanal": resumen_semanal in on,
                "aviso_fiscal": aviso_fiscal in on,
            },
        )
        db.update_gestoria_settings(
            business_id,
            name=gestoria_name,
            email=gestoria_email,
            cadence=gestoria_cadence,
        )
        db.update_branding(
            business_id,
            template=invoice_template,
            brand_color=brand_color,
            logo_data=logo_data,
            logo_mime=logo_mime,
            document_footer=document_footer,
            quote_terms=quote_terms,
            footer_image_data=footer_data,
            footer_image_mime=footer_mime,
            footer_image_width=footer_image_width,
            footer_image_alignment=footer_image_alignment,
            footer_image_scope=footer_image_scope,
        )
    except ValueError:
        return RedirectResponse(
            f"/onboarding/preferences/{business_id}?error=preferences",
            status_code=303,
        )
    db.complete_onboarding_step(business_id, "preferences")
    db.record_product_event(
        business_id, "operational_preferences_completed",
        json.dumps({
            "invoice_term_days": default_payment_term_days,
            "payment_reminders": payment_reminders_enabled in on,
            "gestoria": gestoria_cadence,
        }, separators=(",", ":")),
    )
    return RedirectResponse(
        f"/onboarding/whatsapp/{business_id}", status_code=303
    )


@router.get("/onboarding/whatsapp/{business_id}", response_class=HTMLResponse)
def onboarding_whatsapp(
    request: Request, business_id: int, status: str = "",
):
    # Aislamiento: solo el dueño de ESTE negocio puede ver su onboarding.
    user = auth.current_user(request)
    if not user or user["business_id"] != business_id:
        return RedirectResponse("/login", status_code=303)
    biz = db.get_business(business_id)
    if not db.subscription_allows_access(biz):
        return RedirectResponse(
            f"/b/{business_id}/suscripcion?status=readonly", status_code=303
        )
    link = whatsapp.start_link(business_id)
    plan, billing_period, intent = _signup_selection(
        str(biz.get("onboarding_plan") or "autonomo"),
        str(biz.get("onboarding_billing") or "monthly"),
        str(biz.get("onboarding_intent") or "trial"),
    )
    return TEMPLATES.TemplateResponse(request, "whatsapp_connect.html", {
        "business": biz,
        "wa": link,
        "status": status,
        "signup_intent": intent,
        "selected_plan": plan,
        "selected_plan_label": billing_adapter.PLANS[plan]["name"],
        "selected_billing": billing_period,
        "wa_reports": db.resolve_whatsapp_reports(biz.get("whatsapp_reports")),
    })


@router.post("/b/{business_id}/fiscal")
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


@router.post("/b/{business_id}/payment-details")
def update_payment_details(business_id: int, payment_iban: str = Form(""),
                           payment_bizum: str = Form(""), payment_note: str = Form(""),
                           default_payment_term_days: int = Form(15)):
    try:
        db.update_payment_details(business_id, iban=payment_iban,
                                  bizum=payment_bizum, note=payment_note,
                                  default_payment_term_days=default_payment_term_days)
    except ValueError:
        return RedirectResponse(
            f"/b/{business_id}/ajustes?error=cobro#cobro", status_code=303
        )
    db.record_product_event(business_id, "payment_details_updated")
    return RedirectResponse(f"/b/{business_id}/ajustes#cobro", status_code=303)


@router.post("/b/{business_id}/payment-reminders")
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


@router.post("/b/{business_id}/whatsapp-phone")
def expect_whatsapp_phone(business_id: int, phone: str = Form("")):
    """Alternativa al código: el titular escribe su móvil y confirma desde él."""
    target = f"/b/{business_id}/ajustes"
    if not whatsapp.recipient_phone(phone):
        return RedirectResponse(f"{target}?error=wa-phone#whatsapp-conexion", status_code=303)
    if db.whatsapp_phone_conflict(phone, business_id):
        return RedirectResponse(f"{target}?error=wa-phone-used#whatsapp-conexion", status_code=303)
    db.expect_whatsapp_phone(business_id, phone.strip())
    db.record_product_event(business_id, "whatsapp_phone_expected")
    return RedirectResponse(f"{target}?ok=wa-phone#whatsapp-conexion", status_code=303)


@router.post("/b/{business_id}/whatsapp-reports")
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


@router.post("/api/{business_id}/integrations/{integration_key}")
async def api_update_integration(
    business_id: int, integration_key: str, request: Request
):
    try:
        body = await _read_json(request)
        action = str(body.get("action") or "").strip().lower()
        if integration_key == "whatsapp":
            if action != "disconnect":
                raise ValueError("WhatsApp se conecta con el código seguro.")
            db.disconnect_whatsapp(business_id)
            db.record_product_event(business_id, "whatsapp_disconnected")
        else:
            if integration_key != "ai_external":
                raise ValueError("Esta preferencia se gestiona desde su apartado propio.")
            allowed_actions = {"enable": "enabled", "disable": "disabled"}
            if action not in allowed_actions:
                raise ValueError("La acción de integración no es válida.")
            setting = db.update_integration_setting(
                business_id, integration_key, allowed_actions[action]
            )
            db.record_product_event(
                business_id, "integration_preference_updated",
                f"{integration_key}:{setting['mode']}",
            )
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"ok": True}


@router.post("/b/{business_id}/clockin-policy")
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


@router.post("/b/{business_id}/verifactu")
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


@router.post("/b/{business_id}/branding")
async def update_branding(business_id: int, template: str = Form("clasica"),
                          brand_color: str = Form(""), remove_logo: str = Form(""),
                          document_footer: str = Form(""),
                          quote_terms: str = Form(""),
                          default_quote_validity_days: int = Form(30),
                          footer_image_width: int = Form(100),
                          footer_image_alignment: str = Form("center"),
                          footer_image_scope: str = Form("invoices"),
                          remove_footer_image: str = Form(""),
                          logo: UploadFile = File(None),
                          footer_image: UploadFile = File(None)):
    """Identidad documental saneada y versionada para facturas futuras."""
    clear_logo = bool(remove_logo)
    clear_footer = bool(remove_footer_image)
    try:
        logo_data, logo_mime = (
            (None, None) if clear_logo else await _sanitized_brand_image(logo)
        )
        footer_data, footer_mime = (
            (None, None) if clear_footer
            else await _sanitized_brand_image(footer_image, footer=True)
        )
        db.update_branding(business_id, template=template, brand_color=brand_color,
                           logo_data=logo_data, logo_mime=logo_mime,
                           clear_logo=clear_logo,
                           document_footer=document_footer, quote_terms=quote_terms,
                           default_quote_validity_days=default_quote_validity_days,
                           footer_image_data=footer_data,
                           footer_image_mime=footer_mime,
                           clear_footer_image=clear_footer,
                           footer_image_width=footer_image_width,
                           footer_image_alignment=footer_image_alignment,
                           footer_image_scope=footer_image_scope)
    except ValueError:
        return RedirectResponse(
            f"/b/{business_id}/ajustes?error=marca#marca-documental", status_code=303)
    db.record_product_event(business_id, "document_branding_updated")
    return RedirectResponse(
        f"/b/{business_id}/ajustes?ok=marca#marca-documental", status_code=303
    )


@router.get("/api/{business_id}/branding/preview.pdf")
def branding_preview_pdf(business_id: int):
    """Vista previa explícita; no crea, numera ni emite una factura."""
    from ..invoice_pdf import build_brand_preview_pdf

    data = build_brand_preview_pdf(business_id)
    if data is None:
        return JSONResponse({"error": "Negocio no encontrado."}, status_code=404)
    return Response(
        data, media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="vista_previa_factura.pdf"'},
    )


@router.post("/b/{business_id}/support-access")
def create_support_access(
    request: Request,
    business_id: int,
    purpose: str = Form(""),
    scopes: list[str] = Form([]),
    duration_hours: int = Form(4),
    consent: str = Form(""),
):
    user = auth.current_user(request)
    if not user or user.get("business_id") != business_id:
        return RedirectResponse("/login", status_code=303)
    try:
        if consent != "yes":
            raise ValueError("Debes confirmar expresamente el acceso temporal.")
        db.create_support_grant(
            business_id, user["id"], purpose=purpose, scopes=scopes,
            duration_hours=duration_hours,
        )
        request.session["support_notice"] = "Acceso temporal autorizado."
    except ValueError as exc:
        request.session["support_error"] = str(exc)
    return RedirectResponse(f"/b/{business_id}/ajustes#soporte", status_code=303)


@router.post("/b/{business_id}/support-access/revoke")
def revoke_support_access(request: Request, business_id: int):
    user = auth.current_user(request)
    if not user or user.get("business_id") != business_id:
        return RedirectResponse("/login", status_code=303)
    try:
        db.revoke_support_grant(business_id, user["id"])
        request.session["support_notice"] = "Acceso de soporte revocado."
    except ValueError as exc:
        request.session["support_error"] = str(exc)
    return RedirectResponse(f"/b/{business_id}/ajustes#soporte", status_code=303)


@router.post("/onboarding/whatsapp/{business_id}/connect")
def onboarding_whatsapp_connect(
    request: Request, business_id: int, action: str = Form("later"),
):
    # La vinculación real solo ocurre al recibir el código desde ese WhatsApp.
    user = auth.current_user(request)
    if not user or user["business_id"] != business_id:
        return RedirectResponse("/login", status_code=303)
    business = db.get_business(business_id)
    if not db.subscription_allows_access(business):
        return RedirectResponse(
            f"/b/{business_id}/suscripcion?status=readonly", status_code=303
        )
    connected = bool(business and business.get("whatsapp_status") == "conectado")
    if action == "check" and not connected:
        return RedirectResponse(
            f"/onboarding/whatsapp/{business_id}?status=pending", status_code=303
        )
    if action not in {"check", "later"}:
        return RedirectResponse(
            f"/onboarding/whatsapp/{business_id}?status=invalid", status_code=303
        )
    choice = "connected" if connected else "later"
    try:
        db.finish_onboarding(business_id, whatsapp_choice=choice)
    except ValueError:
        return RedirectResponse(
            db.onboarding_destination(business_id)
            or f"/onboarding/setup/{business_id}",
            status_code=303,
        )
    business = db.get_business(business_id)
    db.record_product_event(
        business_id,
        "onboarding_completed",
        f"whatsapp={choice}",
    )
    plan, billing_period, intent = _signup_selection(
        str(business.get("onboarding_plan") or "autonomo"),
        str(business.get("onboarding_billing") or "monthly"),
        str(business.get("onboarding_intent") or "trial"),
    )
    if intent == "subscribe":
        query = urlparse.urlencode({
            "status": "ready", "plan": plan, "billing": billing_period,
        })
        return RedirectResponse(
            f"/b/{business_id}/suscripcion?{query}", status_code=303
        )
    return RedirectResponse(
        f"/b/{business_id}/resumen?welcome=1#puesta-en-marcha", status_code=303
    )




# ============================================================ SUSCRIPCIÓN === #
@router.post("/b/{business_id}/suscripcion/checkout")
def subscription_checkout(request: Request, business_id: int,
                          plan: str = Form("autonomo"),
                          billing_period: str = Form("monthly")):
    if plan not in billing_adapter.PLAN_PRICES:
        return RedirectResponse(
            f"/b/{business_id}/suscripcion?status=invalid", status_code=303
        )
    if billing_period not in {"monthly", "annual"}:
        return RedirectResponse(
            f"/b/{business_id}/suscripcion?status=invalid", status_code=303
        )
    biz = db.get_business(business_id)
    if biz and biz.get("subscription_status") in {"active", "trialing"}:
        # Una cuenta suscrita nunca abre un segundo Checkout. Los cambios de
        # nivel, periodicidad, tarjeta o cancelacion se hacen sobre la misma
        # suscripcion en el portal de Stripe.
        db.record_product_event(
            business_id, "subscription_change_requested",
            f"plan={plan};billing_period={billing_period}",
        )
        url = billing_adapter.get_provider().portal_url(
            biz, f"{config.BASE_URL}/b/{business_id}/suscripcion",
            action="change", plan=plan, billing_period=billing_period,
        )
        if not url:
            db.record_product_event(
                business_id, "subscription_portal_failed",
                f"action=change;plan={plan};billing_period={billing_period}",
            )
            return RedirectResponse(
                f"/b/{business_id}/suscripcion?status=noportal"
                "#gestion-suscripcion",
                status_code=303,
            )
        return RedirectResponse(url, status_code=303)
    db.record_product_event(
        business_id, "checkout_started",
        f"plan={plan};billing_period={billing_period}",
    )
    provider = billing_adapter.get_provider()
    base = f"{config.BASE_URL}/b/{business_id}/suscripcion"
    success_query = urlparse.urlencode({
        "status": "checkout_return", "plan": plan,
        "billing": billing_period,
    })
    cancel_query = urlparse.urlencode({
        "status": "cancel", "plan": plan, "billing": billing_period,
    })
    url = provider.checkout_url(
        biz, plan, f"{base}?{success_query}", f"{base}?{cancel_query}",
        billing_period,
    )
    if not url:
        # Sin Stripe configurado: deja constancia de la intención (alta manual).
        manual_query = urlparse.urlencode({
            "status": "manual", "plan": plan, "billing": billing_period,
        })
        return RedirectResponse(f"{base}?{manual_query}", status_code=303)
    return RedirectResponse(url, status_code=303)


@router.post("/b/{business_id}/suscripcion/portal")
def subscription_portal(
    request: Request, business_id: int, action: str = Form("manage"),
    plan: str = Form(""), billing_period: str = Form("monthly"),
):
    if action not in {"manage", "payment_method", "change", "cancel"}:
        return RedirectResponse(
            f"/b/{business_id}/suscripcion?status=invalid", status_code=303,
        )
    if action == "change" and (
        plan not in billing_adapter.PLAN_PRICES
        or billing_period not in {"monthly", "annual"}
    ):
        return RedirectResponse(
            f"/b/{business_id}/suscripcion?status=invalid", status_code=303,
        )
    biz = db.get_business(business_id)
    if not biz or biz.get("subscription_status") not in {"active", "trialing"}:
        return RedirectResponse(
            f"/b/{business_id}/suscripcion?status=noportal", status_code=303,
        )
    db.record_product_event(
        business_id, "subscription_portal_requested",
        f"action={action};plan={plan or '-'};billing_period={billing_period}",
    )
    url = billing_adapter.get_provider().portal_url(
        biz, f"{config.BASE_URL}/b/{business_id}/suscripcion",
        action=action, plan=plan, billing_period=billing_period,
    )
    if not url:
        db.record_product_event(
            business_id, "subscription_portal_failed",
            f"action={action};plan={plan or '-'};billing_period={billing_period}",
        )
        return RedirectResponse(
            f"/b/{business_id}/suscripcion?status=noportal"
            "#gestion-suscripcion",
            status_code=303,
        )
    return RedirectResponse(url, status_code=303)






# ===================================================== RESET DE CONTRASEÑA == #


@router.get("/recuperar", response_class=HTMLResponse)
def forgot_page(request: Request, sent: str = ""):
    return TEMPLATES.TemplateResponse(request, "forgot.html", {"sent": sent})


@router.post("/recuperar")
def forgot_submit(request: Request, email: str = Form(...)):
    email = (email or "").strip().lower()
    keys = (
        f"forgot-ip:{auth.client_ip(request)}",
        f"forgot-account:{email}",
    )
    if any(auth.is_rate_limited(key) for key in keys):
        return RedirectResponse("/recuperar?sent=1", status_code=303)
    for key in keys:
        auth.record_failed_attempt(key)
    user = db.get_user_by_email(email)
    if user:  # Si no existe, no lo revelamos (respuesta idéntica).
        token = secrets.token_urlsafe(32)
        token_hash = auth.hash_token(token)
        db.create_password_reset(user["id"], token_hash, ttl_minutes=60)
        link = f"{config.BASE_URL}/restablecer?token={token}"
        email_adapter.queue_email(
            email, "Restablecer tu contraseña de Bynoesis",
            f"Hola,\n\nPara crear una contraseña nueva, abre este enlace (válido 1 hora):\n"
            f"{link}\n\nSi no lo has pedido tú, ignora este correo.\n\n— Bynoesis",
            business_id=user["business_id"],
            idempotency_key=f"password-reset:{user['id']}:{token_hash[:20]}",
        )
        db.record_security_event(
            "account.password_reset_requested",
            area="authentication",
            subject_business_id=user["business_id"],
            request_id=getattr(request.state, "request_id", None),
            metadata={"user_id": user["id"]},
        )
    return RedirectResponse("/recuperar?sent=1", status_code=303)


@router.get("/restablecer", response_class=HTMLResponse)
def reset_page(request: Request, token: str = "", error: str = ""):
    return TEMPLATES.TemplateResponse(request, "reset.html",
                                      {"token": token, "error": error})


@router.post("/restablecer")
def reset_submit(request: Request, token: str = Form(...), password: str = Form(...)):
    if len(password) < 12 or len(password) > 1024:
        return RedirectResponse(f"/restablecer?token={token}&error=password",
                                status_code=303)
    result = db.reset_user_password(
        auth.hash_token(token), auth.hash_password(password)
    )
    if not result:
        return RedirectResponse("/restablecer?error=token", status_code=303)
    request.session.clear()
    db.record_security_event(
        "account.password_reset_completed",
        area="authentication",
        subject_business_id=result["business_id"],
        request_id=getattr(request.state, "request_id", None),
        metadata={"user_id": result["user_id"]},
    )
    return RedirectResponse("/login?error=reset_ok", status_code=303)
