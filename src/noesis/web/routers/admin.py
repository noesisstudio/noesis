"""Rutas de administracion interna."""

from __future__ import annotations

import logging
import secrets

from fastapi import APIRouter, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from ... import config, db, readiness, security_center
from ...adapters import email as email_adapter
from .. import auth, backups
from ..deps import TEMPLATES

router = APIRouter()
log = logging.getLogger("uvicorn.error")

# ========================================================= ADMIN (fundador) = #
def _is_admin(request: Request) -> bool:
    user = auth.current_user(request)
    if not user:
        return False
    allowed = bool(user.get("is_admin")) or config.is_admin_email(user["email"])
    if not allowed:
        return False
    if config.ADMIN_REQUIRE_GOOGLE_OAUTH:
        return request.session.get("auth_provider") == "google"
    return True


@router.get("/admin", response_class=HTMLResponse)
def admin_panel(request: Request):
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    user = auth.current_user(request)
    db.record_security_event(
        "admin.panel_viewed",
        area="admin",
        actor_user_id=user["id"],
        subject_business_id=user["business_id"],
        request_id=getattr(request.state, "request_id", None),
    )
    data = db.admin_overview()
    data["backup"] = backups.admin_backup_status()
    data["readiness"] = readiness.collect_readiness(check_database=False)
    data["security"] = security_center.build_security_report()
    requests_list = db.list_access_requests()
    return TEMPLATES.TemplateResponse(request, "admin.html", {
        "data": data,
        "access_requests": requests_list,
        "access_pending": sum(1 for r in requests_list if r["status"] == "nueva"),
        "visits": db.page_views_summary(30),
        "invite": request.session.pop("last_invite", None),
        "admin_error": request.session.pop("admin_error", None),
    })


@router.get("/admin/cuentas/{business_id}", response_class=HTMLResponse)
def admin_account_support(request: Request, business_id: int):
    """Diagnóstico técnico de una cuenta, deliberadamente de solo lectura."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    snapshot = db.admin_support_snapshot(business_id)
    if not snapshot:
        return Response("Cuenta no encontrada.", status_code=404)
    user = auth.current_user(request)
    db.record_security_event(
        "admin.support_snapshot_viewed",
        area="admin",
        actor_user_id=user["id"],
        subject_business_id=business_id,
        request_id=getattr(request.state, "request_id", None),
        metadata={"mode": "read_only"},
    )
    return TEMPLATES.TemplateResponse(request, "admin_account.html", {
        "snapshot": snapshot,
        "whatsapp_connections": db.list_whatsapp_connections(business_id),
        "admin_error": request.session.pop("admin_error", None),
    })


@router.post("/admin/cuentas/{business_id}/whatsapp-business")
def admin_add_whatsapp_business(
    request: Request,
    business_id: int,
    waba_id: str = Form(...),
    phone_number_id: str = Form(...),
    display_phone: str = Form(""),
    verified_name: str = Form(""),
):
    """Alta técnica pendiente; nunca acepta tokens ni secretos por formulario."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    user = auth.current_user(request)
    try:
        connection = db.create_whatsapp_connection(
            business_id, waba_id=waba_id, phone_number_id=phone_number_id,
            display_phone=display_phone, verified_name=verified_name,
            status="pending", receptionist_enabled=False,
        )
        db.record_security_event(
            "admin.whatsapp_connection_registered", area="admin",
            actor_user_id=user["id"], subject_business_id=business_id,
            request_id=getattr(request.state, "request_id", None),
            metadata={"connection_id": connection["id"], "status": "pending"},
        )
    except ValueError as exc:
        request.session["admin_error"] = str(exc)
    return RedirectResponse(f"/admin/cuentas/{business_id}#whatsapp", status_code=303)


@router.post("/admin/cuentas/{business_id}/whatsapp-business/{connection_id}")
def admin_update_whatsapp_business(
    request: Request,
    business_id: int,
    connection_id: int,
    status: str = Form(...),
    receptionist_enabled: str = Form(""),
):
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    user = auth.current_user(request)
    try:
        connection = db.update_whatsapp_connection(
            connection_id, business_id, status=status,
            receptionist_enabled=(receptionist_enabled == "1" and status == "active"),
        )
        if not connection:
            raise ValueError("Conexión no encontrada.")
        db.record_security_event(
            "admin.whatsapp_connection_updated", area="admin",
            actor_user_id=user["id"], subject_business_id=business_id,
            request_id=getattr(request.state, "request_id", None),
            metadata={
                "connection_id": connection_id, "status": status,
                "receptionist_enabled": bool(connection["receptionist_enabled"]),
            },
        )
    except ValueError as exc:
        request.session["admin_error"] = str(exc)
    return RedirectResponse(f"/admin/cuentas/{business_id}#whatsapp", status_code=303)


@router.post("/admin/solicitudes/{request_id}/estado")
def admin_request_status(request: Request, request_id: int, status: str = Form(...)):
    """Marca una solicitud como contactada o descartada."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    try:
        db.update_access_request(request_id, status=status)
    except ValueError as exc:
        request.session["admin_error"] = str(exc)
    return RedirectResponse("/admin#solicitudes", status_code=303)


@router.post("/admin/costes")
def admin_add_cost(
    request: Request,
    period: str = Form(...),
    category: str = Form(...),
    amount_eur: str = Form(...),
    source: str = Form("actual"),
    note: str = Form(""),
):
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    user = auth.current_user(request)
    try:
        entry = db.add_platform_cost(
            period, category, amount_eur, source=source, note=note,
            created_by_user_id=user["id"],
        )
        db.record_security_event(
            "admin.platform_cost_recorded", area="admin",
            actor_user_id=user["id"], subject_business_id=user["business_id"],
            request_id=getattr(request.state, "request_id", None),
            metadata={"entry_id": entry["id"], "period": period,
                      "category": category, "source": source},
        )
    except ValueError as exc:
        request.session["admin_error"] = str(exc)
    return RedirectResponse("/admin#finanzas", status_code=303)


@router.post("/admin/solicitudes/{request_id}/alta")
def admin_request_approve(request: Request, request_id: int):
    """Crea la cuenta del solicitante y devuelve su enlace de invitación.

    La contraseña la elige el propio titular con el enlace: aquí nunca se fija
    ninguna, de modo que el equipo no llega a conocerla.
    """
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    solicitud = db.get_access_request(request_id)
    if not solicitud:
        request.session["admin_error"] = "Esa solicitud ya no existe."
        return RedirectResponse("/admin#solicitudes", status_code=303)
    if solicitud["status"] == "alta":
        request.session["admin_error"] = "Esa solicitud ya tiene cuenta creada."
        return RedirectResponse("/admin#solicitudes", status_code=303)
    if db.get_user_by_email(solicitud["email"]):
        request.session["admin_error"] = (
            f"Ya existe una cuenta con {solicitud['email']}."
        )
        return RedirectResponse("/admin#solicitudes", status_code=303)

    business_name = solicitud["business_name"] or solicitud["name"]
    # Contraseña imposible de adivinar y que nadie usará: el alta se completa
    # siempre por el enlace de invitación.
    placeholder = auth.hash_password(secrets.token_urlsafe(32))
    try:
        biz, user = db.create_account(
            business_name, solicitud["email"], placeholder,
            solicitud["sector"] or "", trial_days=config.TRIAL_DAYS,
        )
    except (ValueError, *db.IntegrityError) as exc:
        request.session["admin_error"] = f"No se pudo crear la cuenta: {exc}"
        return RedirectResponse("/admin#solicitudes", status_code=303)

    token = secrets.token_urlsafe(32)
    db.create_password_reset(
        user["id"], auth.hash_token(token), ttl_minutes=config.INVITE_TTL_MINUTES
    )
    invite_url = f"{config.BASE_URL}/restablecer?token={token}"
    db.update_access_request(request_id, status="alta", business_id=biz["id"])
    db.record_product_event(biz["id"], "account_created_by_admin")

    try:
        # Se encola en vez de enviarse aquí: el enlace ya se enseña en pantalla,
        # así que no hay motivo para dejar al fundador esperando a SMTP.
        email_adapter.queue_email(
            solicitud["email"],
            "Tu acceso a Noesis ya está listo",
            "\n".join([
                f"Hola, {solicitud['name']}:",
                "",
                "Ya tienes tu cuenta de Noesis preparada. Elige tu contraseña aquí:",
                invite_url,
                "",
                f"El enlace caduca en {config.INVITE_TTL_MINUTES // 1440} días.",
                "Tus 14 días de prueba empiezan hoy.",
                "",
                "Cualquier duda, respóndenos a este correo.",
            ]),
            business_id=biz["id"],
            idempotency_key=f"access-invite:{request_id}",
        )
    except Exception:  # noqa: BLE001
        log.exception("No se pudo enviar la invitación de la solicitud %s.", request_id)

    # Se muestra una sola vez para poder enviarlo por WhatsApp si el correo falla.
    request.session["last_invite"] = {
        "name": solicitud["name"], "email": solicitud["email"], "url": invite_url,
    }
    return RedirectResponse("/admin#solicitudes", status_code=303)


@router.get("/admin/backups/latest")
def admin_download_latest_backup(request: Request):
    if not _is_admin(request):
        return Response("No autorizado.", status_code=403)
    path = backups.latest_verified_backup()
    if not path:
        return Response("No hay ninguna copia verificada disponible.", status_code=404)
    user = auth.current_user(request)
    db.record_security_event(
        "admin.backup_downloaded",
        severity="warning",
        area="admin",
        actor_user_id=user["id"],
        subject_business_id=user["business_id"],
        request_id=getattr(request.state, "request_id", None),
        metadata={"storage": "postgres" if config.DATABASE_URL else "sqlite"},
    )
    media_type = (
        "application/gzip"
        if path.name.endswith((".gz", ".dump"))
        else "application/vnd.sqlite3"
    )
    return FileResponse(path, media_type=media_type, filename=path.name)
