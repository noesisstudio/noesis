"""Rutas de administracion interna."""

from __future__ import annotations

import logging
import secrets
from datetime import date

from fastapi import APIRouter, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from ... import config, db, readiness, security_center
from ...adapters import billing as billing_adapter
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
        "hoy": date.today().isoformat(),
        "access_requests": requests_list,
        "access_pending": sum(1 for r in requests_list if r["status"] == "nueva"),
        "visits": db.page_views_summary(30),
        "invite": request.session.pop("last_invite", None),
        "admin_error": request.session.pop("admin_error", None),
    })


@router.get("/admin/cuentas/{business_id}", response_class=HTMLResponse)
def admin_account_support(request: Request, business_id: int):
    """Diagnóstico técnico y correcciones autorizadas de alcance mínimo."""
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
    document_support = db.admin_support_document_metadata(business_id)
    if document_support:
        db.record_security_event(
            "admin.support_document_metadata_viewed",
            area="support",
            actor_user_id=user["id"],
            subject_business_id=business_id,
            request_id=getattr(request.state, "request_id", None),
            metadata={
                "grant_id": document_support["grant_id"],
                "item_count": len(document_support["documents"]),
            },
        )
    configuration_support = db.admin_support_configuration(business_id)
    if configuration_support:
        db.record_security_event(
            "admin.support_configuration_viewed",
            area="support",
            actor_user_id=user["id"],
            subject_business_id=business_id,
            request_id=getattr(request.state, "request_id", None),
            metadata={"grant_id": configuration_support["grant_id"]},
        )
    trial_ends = str((snapshot.get("business") or {}).get("trial_ends_at") or "")
    return TEMPLATES.TemplateResponse(request, "admin_account.html", {
        "snapshot": snapshot,
        "trial_expired": bool(trial_ends) and trial_ends < date.today().isoformat(),
        "delivery_failures": db.admin_support_delivery_failures(business_id),
        "subscription_blocked": not db.subscription_allows_access(
            db.get_business(business_id)
        ),
        "business_users": db.list_business_users(business_id),
        "gestoria_access": db.list_gestoria_access_for_business(business_id),
        "entitlement_labels": billing_adapter.ENTITLEMENT_LABELS,
        "current_entitlements": billing_adapter.entitlements_for(
            db.get_business(business_id)
        ),
        "whatsapp_connections": db.list_whatsapp_connections(business_id),
        "document_support": document_support,
        "configuration_support": configuration_support,
        "admin_error": request.session.pop("admin_error", None),
        "admin_success": request.session.pop("admin_success", None),
    })


@router.post("/admin/cuentas/{business_id}/configuracion-segura")
def admin_correct_safe_configuration(
    request: Request,
    business_id: int,
    name: str = Form(...),
    sector: str = Form(...),
    team_size: str = Form(...),
    province: str = Form(""),
    primary_goal: str = Form(...),
    language: str = Form(...),
    explanation_level: str = Form(...),
    invoice_template: str = Form(...),
    brand_color: str = Form(""),
    document_footer: str = Form(""),
    quote_terms: str = Form(""),
    default_quote_validity_days: int = Form(...),
):
    """Corrige perfil y apariencia, nunca fiscalidad, cobros o integraciones."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    user = auth.current_user(request)
    try:
        result = db.admin_update_safe_business_configuration(
            business_id,
            actor_user_id=user["id"],
            name=name,
            sector=sector,
            team_size=team_size,
            province=province,
            primary_goal=primary_goal,
            language=language,
            explanation_level=explanation_level,
            invoice_template=invoice_template,
            brand_color=brand_color,
            document_footer=document_footer,
            quote_terms=quote_terms,
            default_quote_validity_days=default_quote_validity_days,
            request_id=getattr(request.state, "request_id", None),
        )
        request.session["admin_success"] = (
            "Configuración corregida y auditada."
            if result["changed_fields"]
            else "La cuenta ya tenía esa configuración; no se ha modificado."
        )
    except (PermissionError, ValueError) as exc:
        request.session["admin_error"] = str(exc)
    return RedirectResponse(
        f"/admin/cuentas/{business_id}#safe-configuration", status_code=303
    )


@router.post("/admin/cuentas/{business_id}/documentos/{document_id}/metadatos")
def admin_correct_document_metadata(
    request: Request,
    business_id: int,
    document_id: int,
    kind: str = Form(...),
    doc_status: str = Form(...),
    client_id: str = Form(""),
    project_id: str = Form(""),
    review_note: str = Form(""),
):
    """Corrige solo organización documental si el titular la autorizó."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    user = auth.current_user(request)

    def _optional_int(value: str) -> int | None:
        return int(value) if str(value or "").strip() else None

    try:
        result = db.admin_update_document_metadata(
            business_id,
            document_id,
            actor_user_id=user["id"],
            kind=kind,
            doc_status=doc_status,
            client_id=_optional_int(client_id),
            project_id=_optional_int(project_id),
            review_note=review_note,
            request_id=getattr(request.state, "request_id", None),
        )
        request.session["admin_success"] = (
            "Organización del documento corregida y auditada."
            if result["changed_fields"]
            else "El documento ya tenía esa organización; no se ha modificado."
        )
    except (PermissionError, ValueError) as exc:
        request.session["admin_error"] = str(exc)
    return RedirectResponse(
        f"/admin/cuentas/{business_id}#document-metadata", status_code=303
    )


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


@router.post("/admin/cuentas/{business_id}/suscripcion")
def admin_account_subscription(
    request: Request,
    business_id: int,
    action: str = Form(...),
    plan: str = Form("pro"),
    trial_days: str = Form("14"),
    volver: str = Form(""),
):
    """Habilita o deshabilita una cuenta desde administracion.

    Cubre el caso real del propietario: activar a un piloto sin pasar por Stripe,
    devolver a modo consulta o ampliar una prueba vencida. No toca datos del
    negocio ni suplanta a nadie: solo mueve el estado de la suscripcion, y cada
    cambio queda en la bitacora encadenada.
    """
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    user = auth.current_user(request)
    business = db.get_business(business_id)
    if not business:
        request.session["admin_error"] = "Esa cuenta no existe."
        return RedirectResponse("/admin#cuentas", status_code=303)
    # Se vuelve a donde estabas: el panel de gestion o la ficha de la cuenta.
    target = (
        "/admin#gestion" if volver == "admin"
        else f"/admin/cuentas/{business_id}#suscripcion"
    )
    try:
        if action == "activar":
            if plan not in {"autonomo", "pro", "premium"}:
                raise ValueError("Ese plan no existe.")
            db.set_subscription(business_id, "active", plan=plan)
            detail = {"action": "activar", "plan": plan}
        elif action == "desactivar":
            db.set_subscription(business_id, "canceled")
            detail = {"action": "desactivar"}
        elif action == "ampliar_prueba":
            days = int(str(trial_days).strip() or "14")
            if not 1 <= days <= 365:
                raise ValueError("La prueba debe durar entre 1 y 365 dias.")
            db.set_trial(business_id, days=days)
            detail = {"action": "ampliar_prueba", "days": days}
        else:
            raise ValueError("Accion no reconocida.")
    except ValueError as exc:
        request.session["admin_error"] = str(exc)
        return RedirectResponse(target, status_code=303)
    db.record_security_event(
        "admin.subscription_changed", area="admin",
        actor_user_id=user["id"], subject_business_id=business_id,
        request_id=getattr(request.state, "request_id", None),
        metadata=detail,
    )
    return RedirectResponse(target, status_code=303)


@router.post("/admin/cuentas/{business_id}/usuarios/{user_id}/acceso")
def admin_user_access(
    request: Request,
    business_id: int,
    user_id: int,
    action: str = Form(...),
    note: str = Form(""),
):
    """Suspende o restaura el acceso de una persona concreta.

    Es la palanca proporcionada: retirar a quien ya no debe entrar sin apagar la
    cuenta entera del negocio. No borra datos y es reversible.
    """
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    actor = auth.current_user(request)
    target = f"/admin/cuentas/{business_id}#acceso"
    victim = db.get_user(user_id)
    if not victim or int(victim.get("business_id") or 0) != business_id:
        request.session["admin_error"] = "Esa persona no pertenece a esta cuenta."
        return RedirectResponse(target, status_code=303)
    active = action == "restaurar"
    try:
        db.set_user_access(
            user_id, active=active, actor_user_id=actor["id"], note=note,
        )
    except db.AccessControlError as exc:
        request.session["admin_error"] = str(exc)
        return RedirectResponse(target, status_code=303)
    db.record_security_event(
        "admin.user_access_restored" if active else "admin.user_access_suspended",
        area="admin",
        severity="info" if active else "warning",
        actor_user_id=actor["id"],
        subject_business_id=business_id,
        request_id=getattr(request.state, "request_id", None),
        metadata={"user_id": user_id, "note": " ".join(str(note or "").split())[:300]},
    )
    request.session["admin_success"] = (
        "Acceso restaurado." if active else
        "Acceso suspendido. Sus sesiones abiertas se han cerrado."
    )
    return RedirectResponse(target, status_code=303)


@router.post("/admin/cuentas/{business_id}/gestoria/{account_id}/revocar")
def admin_revoke_gestoria(request: Request, business_id: int, account_id: int):
    """Corta el acceso de una gestoria a los datos de un cliente.

    La via normal es que lo revoque el titular desde su panel: la relacion es
    suya. Esto existe como medida de seguridad —una credencial profesional
    comprometida no puede esperar— y por eso queda registrado con su motivo.
    """
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    actor = auth.current_user(request)
    target = f"/admin/cuentas/{business_id}#acceso"
    if not db.revoke_gestoria_access(business_id, account_id):
        request.session["admin_error"] = "Ese acceso ya no estaba activo."
        return RedirectResponse(target, status_code=303)
    db.record_security_event(
        "admin.gestoria_access_revoked", area="admin", severity="warning",
        actor_user_id=actor["id"], subject_business_id=business_id,
        request_id=getattr(request.state, "request_id", None),
        metadata={"gestoria_account_id": account_id},
    )
    request.session["admin_success"] = "Acceso de la gestoria revocado."
    return RedirectResponse(target, status_code=303)


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
    db.start_onboarding(biz["id"])

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
