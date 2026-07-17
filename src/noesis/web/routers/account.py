"""Rutas de cuenta, onboarding, ajustes y suscripcion."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from ... import config, db, verifactu_client
from ...adapters import billing as billing_adapter
from ...adapters import email as email_adapter
from .. import auth, whatsapp
from ..deps import TEMPLATES, _read_json

router = APIRouter()

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


def _start_session(request: Request, user: dict) -> None:
    request.session.clear()
    request.session["uid"] = user["id"]
    request.session["bid"] = user["business_id"]
    request.session["sv"] = user.get("session_version", 0)


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
@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    return TEMPLATES.TemplateResponse(request, "login.html", {
        "error": error,
        "google_oauth_available": config.google_oauth_available(),
    })


@router.post("/login")
def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    key = f"login:{auth.client_ip(request)}"
    if auth.is_rate_limited(key):
        return RedirectResponse("/login?error=throttle", status_code=303)
    user = db.get_user_by_email((email or "").strip().lower())
    if not user or not auth.verify_password(password, user["password_hash"]):
        auth.record_failed_attempt(key)
        return RedirectResponse("/login?error=1", status_code=303)
    auth.clear_attempts(key)
    _start_session(request, user)
    return RedirectResponse(f"/b/{user['business_id']}/resumen", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/auth/google")
def google_start(request: Request, flow: str = "login", plan: str = "",
                 billing: str = "monthly", intent: str = "trial"):
    """Empieza OAuth con state de un solo uso y no filtra el secreto al cliente."""
    flow = "signup" if flow == "signup" else "login"
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
        _start_session(request, user)
        return RedirectResponse(f"/b/{user['business_id']}/resumen", status_code=303)
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
@router.get("/onboarding", response_class=HTMLResponse)
def onboarding(request: Request, error: str = "", plan: str = "",
               billing: str = "monthly", intent: str = "trial"):
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
    request.session.clear()
    request.session["uid"] = user["id"]
    request.session["bid"] = biz["id"]
    request.session["sv"] = user.get("session_version", 0)
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
        "version": "2026-06-30",
        "documents": ["terminos", "privacidad", "encargado-tratamiento"],
        "ip": auth.client_ip(request),
    }))
    return RedirectResponse(f"/onboarding/setup/{biz['id']}", status_code=303)


@router.get("/onboarding/google", response_class=HTMLResponse)
def onboarding_google(request: Request, error: str = "", plan: str = "",
                      billing: str = "monthly", intent: str = "trial"):
    """Completa los datos de negocio tras verificar el correo con Google."""
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
        _start_session(request, existing)
        return RedirectResponse(f"/b/{existing['business_id']}/resumen", status_code=303)
    try:
        biz, user = db.create_account(
            (name or "").strip(), email, auth.hash_password(secrets.token_urlsafe(48)),
            sector, trial_days=config.TRIAL_DAYS,
        )
    except (ValueError, *db.IntegrityError):
        return RedirectResponse(f"/onboarding/google{error_query}email", status_code=303)
    _start_session(request, user)
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
        "version": "2026-06-30",
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
            "signup_intent": request.session.get("signup_intent", "trial"),
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
            "signup_intent": request.session.get("signup_intent", "trial"),
        },
    )


@router.post("/onboarding/preferences/{business_id}")
def onboarding_preferences_submit(
    request: Request,
    business_id: int,
    nif: str = Form(""),
    address: str = Form(""),
    default_vat: float = Form(21),
    default_irpf: float = Form(0),
    default_payment_term_days: int = Form(15),
    invoice_template: str = Form("clasica"),
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
    except ValueError:
        return RedirectResponse(
            f"/onboarding/preferences/{business_id}?error=preferences",
            status_code=303,
        )
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
def onboarding_whatsapp(request: Request, business_id: int):
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
    return TEMPLATES.TemplateResponse(request, "whatsapp_connect.html",
                                      {
                                          "business": biz,
                                          "wa": link,
                                          "signup_intent": request.session.get(
                                              "signup_intent", "trial"
                                          ),
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


@router.post("/onboarding/whatsapp/{business_id}/connect")
def onboarding_whatsapp_connect(request: Request, business_id: int):
    # La vinculación real solo ocurre al recibir el código desde ese WhatsApp.
    user = auth.current_user(request)
    if not user or user["business_id"] != business_id:
        return RedirectResponse("/login", status_code=303)
    business = db.get_business(business_id)
    if not db.subscription_allows_access(business):
        return RedirectResponse(
            f"/b/{business_id}/suscripcion?status=readonly", status_code=303
        )
    if not business or business.get("whatsapp_status") != "conectado":
        db.set_whatsapp_status(business_id, "no_conectado")
    db.finish_onboarding(business_id)
    db.record_product_event(
        business_id,
        "onboarding_completed",
        f"whatsapp={business.get('whatsapp_status') if business else 'unknown'}",
    )
    plan, billing_period, intent = _signup_selection(
        str(request.session.get("signup_plan") or "autonomo"),
        str(request.session.get("signup_billing") or "monthly"),
        str(request.session.get("signup_intent") or "trial"),
    )
    if intent == "subscribe":
        query = urlparse.urlencode({
            "status": "ready", "plan": plan, "billing": billing_period,
        })
        return RedirectResponse(
            f"/b/{business_id}/suscripcion?{query}", status_code=303
        )
    return RedirectResponse(f"/b/{business_id}/resumen", status_code=303)




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
def subscription_portal(request: Request, business_id: int):
    biz = db.get_business(business_id)
    url = billing_adapter.get_provider().portal_url(
        biz, f"{config.BASE_URL}/b/{business_id}/suscripcion")
    if not url:
        return RedirectResponse(f"/b/{business_id}/suscripcion?status=noportal",
                                status_code=303)
    return RedirectResponse(url, status_code=303)






# ===================================================== RESET DE CONTRASEÑA == #
import secrets  # noqa: E402


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.get("/recuperar", response_class=HTMLResponse)
def forgot_page(request: Request, sent: str = ""):
    return TEMPLATES.TemplateResponse(request, "forgot.html", {"sent": sent})


@router.post("/recuperar")
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
        email_adapter.queue_email(
            email, "Restablecer tu contraseña de Noesis",
            f"Hola,\n\nPara crear una contraseña nueva, abre este enlace (válido 1 hora):\n"
            f"{link}\n\nSi no lo has pedido tú, ignora este correo.\n\n— Noesis",
            business_id=user["business_id"],
            idempotency_key=f"password-reset:{user['id']}:{_hash_token(token)[:20]}",
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
    row = db.use_password_reset(_hash_token(token))
    if not row:
        return RedirectResponse("/restablecer?error=token", status_code=303)
    db.set_password(row["user_id"], auth.hash_password(password))
    return RedirectResponse("/login?error=reset_ok", status_code=303)
