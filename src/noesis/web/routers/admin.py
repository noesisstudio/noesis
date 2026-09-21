"""Rutas de administracion interna."""

from __future__ import annotations

import logging
import secrets
from datetime import date, datetime, timezone

from fastapi import APIRouter, Form, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import (
    FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response,
)

from ... import config, db, economics, economics_docs, readiness, security_center
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
    privacy_requests = db.list_privacy_requests()
    return TEMPLATES.TemplateResponse(request, "admin.html", {
        "data": data,
        "hoy": date.today().isoformat(),
        "admin_as_of": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
        "mi_negocio": user["business_id"],
        "access_requests": requests_list,
        "access_pending": sum(1 for r in requests_list if r["status"] == "nueva"),
        "privacy_requests": privacy_requests,
        "privacy_pending": sum(
            1 for row in privacy_requests
            if row["status"] in db.PRIVACY_REQUEST_OPEN_STATUSES
        ),
        "visits": db.page_views_summary(30),
        "public_interactions": db.public_interactions_summary(30),
        "invite": request.session.pop("last_invite", None),
        "whatsapp_identity": request.session.pop("whatsapp_identity", None),
        "admin_error": request.session.pop("admin_error", None),
        "admin_success": request.session.pop("admin_success", None),
    })


@router.post("/admin/privacidad/{privacy_request_id}/estado")
def admin_update_privacy_request(
    request: Request,
    privacy_request_id: int,
    status: str = Form(...),
    resolution_note: str = Form(...),
):
    """Documenta el seguimiento; nunca borra datos desde este control."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    user = auth.current_user(request)
    try:
        updated = db.update_privacy_request(
            privacy_request_id,
            status=status,
            resolution_note=resolution_note,
        )
    except (ValueError, *db.IntegrityError) as exc:
        request.session["admin_error"] = str(exc)
        return RedirectResponse("/admin#privacidad", status_code=303)
    if not updated:
        return Response("Solicitud no encontrada.", status_code=404)
    db.record_security_event(
        "privacy.request_status_updated",
        severity="warning",
        area="privacy",
        actor_user_id=user["id"],
        subject_business_id=updated["business_id"],
        request_id=getattr(request.state, "request_id", None),
        metadata={
            "privacy_request_id": updated["id"],
            "status": updated["status"],
        },
    )
    request.session["admin_success"] = (
        f"Solicitud #{updated['id']} actualizada."
    )
    return RedirectResponse("/admin#privacidad", status_code=303)


@router.post("/admin/whatsapp/identidad")
def admin_whatsapp_identity(request: Request, telefono: str = Form(...)):
    """Consulta quién ocupa un teléfono en el número central de Bynoesis.

    Cuentas solo enseña el teléfono del titular. Cuando una vinculación falla
    porque el número ya está en una ficha de Equipo, esa ficha no se ve desde
    ningún sitio del panel; esta consulta la saca.
    """
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    user = auth.current_user(request)
    identidad = db.whatsapp_identity_rows(telefono)
    if not identidad["valid"]:
        request.session["admin_error"] = (
            "Ese teléfono no deja nueve dígitos; revísalo."
        )
        return RedirectResponse("/admin#identidad-whatsapp", status_code=303)
    db.record_security_event(
        "admin.whatsapp_identity_viewed",
        area="admin",
        actor_user_id=user["id"],
        subject_business_id=user["business_id"],
        request_id=getattr(request.state, "request_id", None),
        metadata={"phone_norm": identidad["norm"], "mode": "read_only"},
    )
    request.session["whatsapp_identity"] = identidad
    return RedirectResponse("/admin#identidad-whatsapp", status_code=303)


@router.post("/admin/whatsapp/identidad/liberar")
def admin_whatsapp_identity_release(request: Request, telefono: str = Form(...)):
    """Libera el número: lo quita de las fichas y desconecta los canales."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    user = auth.current_user(request)
    try:
        identidad = db.free_whatsapp_phone(telefono)
    except ValueError as exc:
        request.session["admin_error"] = str(exc)
        return RedirectResponse("/admin#identidad-whatsapp", status_code=303)
    db.record_security_event(
        "admin.whatsapp_identity_released",
        severity="warning",
        area="admin",
        actor_user_id=user["id"],
        subject_business_id=user["business_id"],
        request_id=getattr(request.state, "request_id", None),
        metadata={
            "phone_norm": identidad["norm"],
            "workers": [row["id"] for row in identidad["workers"]],
            "businesses": [row["id"] for row in identidad["businesses"]],
        },
    )
    request.session["whatsapp_identity"] = db.whatsapp_identity_rows(telefono)
    request.session["admin_success"] = (
        f"{identidad['norm']} queda libre. Genera un código en Ajustes y "
        "envíalo por WhatsApp."
    )
    return RedirectResponse("/admin#identidad-whatsapp", status_code=303)


@router.get("/admin/value-ledger", response_class=JSONResponse)
def admin_value_ledger(request: Request, business_id: int | None = None):
    """Auditoría interna mínima, oculta por defecto y siempre de solo lectura."""
    if not _is_admin(request):
        return Response("No autorizado.", status_code=403)
    if not config.VALUE_LEDGER_ADMIN_ENABLED:
        return Response("No encontrado.", status_code=404)
    from ... import value_ledger
    user = auth.current_user(request)
    try:
        snapshot = value_ledger.admin_snapshot(business_id)
    except ValueError as exc:
        return Response(str(exc), status_code=404)
    db.record_security_event(
        "admin.value_ledger_viewed",
        area="admin",
        actor_user_id=user["id"],
        subject_business_id=business_id or user["business_id"],
        request_id=getattr(request.state, "request_id", None),
        metadata={"mode": "read_only", "scope": "business" if business_id else "weekly"},
    )
    return JSONResponse(jsonable_encoder(snapshot))


@router.get("/admin/cuentas/{business_id}", response_class=HTMLResponse)
def admin_account_support(request: Request, business_id: int, month: str | None = None):
    """Diagnóstico técnico y correcciones autorizadas de alcance mínimo."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    snapshot = db.admin_support_snapshot(business_id)
    if not snapshot:
        return Response("Cuenta no encontrada.", status_code=404)
    try:
        api_usage = db.admin_api_usage(business_id, month)
    except ValueError as exc:
        return Response(str(exc), status_code=400)
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
    cost_control = db.account_cost_control(api_usage["month"])
    account_cost = next(
        (row for row in cost_control["rows"] if row["id"] == business_id), None
    )
    return TEMPLATES.TemplateResponse(request, "admin_account.html", {
        "snapshot": snapshot,
        "api_usage": api_usage,
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
        "cost_control": cost_control,
        "account_cost": account_cost,
        "admin_error": request.session.pop("admin_error", None),
        "admin_success": request.session.pop("admin_success", None),
    })


@router.get("/admin/cuentas/{business_id}/consumo", response_class=JSONResponse)
def admin_account_usage(request: Request, business_id: int, month: str | None = None):
    """Lectura auditada; ninguna clave externa viaja al navegador."""
    if not _is_admin(request):
        return Response("No autorizado.", status_code=403)
    if not db.get_business(business_id):
        return Response("Cuenta no encontrada.", status_code=404)
    try:
        usage = db.admin_api_usage(business_id, month)
    except ValueError as exc:
        return Response(str(exc), status_code=400)
    user = auth.current_user(request)
    db.record_security_event(
        "admin.api_usage_viewed", area="admin", actor_user_id=user["id"],
        subject_business_id=business_id, metadata={"month": usage["month"]},
    )
    return JSONResponse(jsonable_encoder(usage), headers={"Cache-Control": "no-store"})


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


@router.post("/admin/cuentas/{business_id}/correos/{message_id}/reintentar")
def admin_retry_failed_email(
    request: Request, business_id: int, message_id: int
):
    """Reabre un único correo agotado; el scheduler conserva el envío durable."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    user = auth.current_user(request)
    try:
        result = db.requeue_failed_email_message(business_id, message_id)
        if not result:
            raise ValueError("Ese correo no pertenece a esta cuenta.")
        db.record_security_event(
            "admin.email_delivery_requeued",
            area="support",
            actor_user_id=user["id"],
            subject_business_id=business_id,
            request_id=getattr(request.state, "request_id", None),
            metadata={
                "outbox_id": result["id"],
                "previous_attempts": result["previous_attempts"],
            },
        )
        request.session["admin_success"] = (
            "Correo devuelto a la cola. El sistema volverá a intentarlo sin "
            "duplicar el envío."
        )
    except ValueError as exc:
        request.session["admin_error"] = str(exc)
    return RedirectResponse(
        f"/admin/cuentas/{business_id}#entregas", status_code=303
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


def _delete_requests(request: Request, **selector) -> RedirectResponse:
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    deleted = db.delete_access_requests(**selector)
    user = auth.current_user(request)
    db.record_security_event(
        "admin.access_requests_deleted", area="admin", severity="warning",
        actor_user_id=user["id"], subject_business_id=user["business_id"],
        request_id=getattr(request.state, "request_id", None),
        metadata={"deleted": deleted},
    )
    request.session["admin_success"] = (
        f"Eliminada(s) {deleted} solicitud(es) y sus avisos por correo."
        if deleted else "No había solicitudes que eliminar."
    )
    return RedirectResponse("/admin#solicitudes", status_code=303)


@router.post("/admin/solicitudes/eliminar-descartadas")
def admin_delete_discarded_requests(request: Request):
    """Borra de verdad las solicitudes descartadas (pruebas internas)."""
    return _delete_requests(request, status="descartada")


@router.post("/admin/solicitudes/{request_id}/eliminar")
def admin_delete_request(request: Request, request_id: int):
    return _delete_requests(request, request_id=request_id)


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


def _economia_overrides(request: Request) -> dict:
    """Lee las palancas de la URL. `economics` ya las acota: aquí solo se pasan."""
    return {key: request.query_params.get(key) for key in economics.LEVERS}


def _economia_contexto(request: Request) -> dict:
    control = db.account_cost_control()
    observed = {
        "paying_accounts": control.get("paying_accounts"),
        # El catálogo mensual no acredita el ingreso de contratos anuales.
        "mrr": None,
        "observed_cost_eur": (control.get("observed_cost_eur")
                              if control.get("has_observed_data") else None),
    }
    saved = db.economy_assumptions()
    report = economics.build_report(_economia_overrides(request), observed, saved)
    return {"report": report, "timeline": db.economy_timeline(12),
            "control": control, "saved": saved,
            "grupos": economics.form_groups(report["assumptions"]),
            "audit": db.economy_assumptions_audit()}


@router.get("/admin/economia", response_class=HTMLResponse)
def admin_economia(request: Request):
    """Panel económico: el modelo con los datos reales, sin abrir ninguna hoja."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    user = auth.current_user(request)
    db.record_security_event(
        "admin.economia_viewed", area="admin", actor_user_id=user["id"],
        subject_business_id=user["business_id"],
        request_id=getattr(request.state, "request_id", None),
    )
    contexto = _economia_contexto(request)
    return TEMPLATES.TemplateResponse(request, "admin_economia.html", {
        "report": contexto["report"],
        "timeline": contexto["timeline"],
        "control": contexto["control"],
        "grupos": contexto["grupos"],
        "audit": contexto["audit"],
        "tocados": len(contexto["saved"]),
        "levers": economics.LEVERS,
        "admin_error": request.session.pop("admin_error", None),
        "admin_success": request.session.pop("admin_success", None),
        "admin_as_of": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
    })


@router.get("/admin/economia/datos", response_class=JSONResponse)
def admin_economia_datos(request: Request):
    """Recalcula el modelo al mover una palanca.

    El cálculo vuelve al servidor a propósito. Duplicarlo en JavaScript daría una
    página más rápida y dos modelos que se separarían al primer cambio, que es
    justo el fallo que este trabajo venía a corregir.
    """
    if not _is_admin(request):
        return JSONResponse({"error": "no autorizado"}, status_code=403)
    report = _economia_contexto(request)["report"]
    rampa = report["rampa"]
    return JSONResponse(jsonable_encoder({
        "medias": report["medias"],
        "equilibrios": report["equilibrios"],
        "capacidad": report["capacidad"],
        "cabe_en_horas": report["cabe_en_horas"],
        "estructura": report["estructura"],
        "vida_media": report["vida_media"],
        "ltv_caja": report["ltv_caja"],
        "ltv_cac": report["ltv_cac"],
        "payback": report["payback"],
        "planes": report["planes"],
        "rampa": {
            "financiable": rampa["financiable"],
            "financiacion_adicional": rampa["financiacion_adicional"],
            "mes_positivo": rampa["mes_positivo"],
            "mes_ahogo": rampa["mes_ahogo"],
            "caja_minima": rampa["caja_minima"],
            "cuentas_final": rampa["cuentas_final"],
            "salida_mensual": rampa["salida_mensual"],
            "filas": [{"mes": f["mes"], "caja": f["caja"], "horas": f["horas"],
                       "cuentas": f["cuentas"], "altas": f["altas"],
                       "objetivo": f["objetivo"], "frenado": f["frenado"],
                       "resultado": f["resultado"]} for f in rampa["filas"]],
        },
        "caja_inicial": report["assumptions"]["caja_inicial"],
        "horas_mes": report["assumptions"]["horas_mes"],
        "impagos": report["assumptions"]["impagos"],
    }))


@router.post("/admin/economia/supuestos")
async def admin_economia_guardar(request: Request):
    """Guarda los costes y supuestos que el founder escribe en la página.

    Se guarda solo lo que se desvía del valor de fábrica; volver a la cifra
    original borra la fila. Un campo mal escrito se ignora y conserva el valor
    anterior en vez de tumbar el guardado entero.
    """
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    user = auth.current_user(request)
    formulario = await request.form()
    cambios: dict = {}
    for key, spec in economics.EDITABLE.items():
        if key not in formulario:
            continue
        cambios[key] = (formulario.getlist(key) if spec["tipo"] == "plan"
                        else formulario.get(key))
    guardados = db.save_economy_assumptions(cambios, user_id=user["id"])
    db.record_security_event(
        "admin.economia_assumptions_saved", area="admin", actor_user_id=user["id"],
        subject_business_id=user["business_id"],
        request_id=getattr(request.state, "request_id", None),
        metadata={"claves": sorted(guardados)},
    )
    if "mix" in cambios and economics.coerce("mix", cambios["mix"]) is None:
        request.session["admin_error"] = (
            "La mezcla de planes debe sumar 100 %. Se conserva la mezcla anterior; "
            "los demás valores válidos se han guardado."
        )
    else:
        request.session["admin_success"] = (
            f"Guardados {len(guardados)} supuesto(s) cambiados respecto al valor "
            "de fábrica." if guardados else
            "Todo vuelve a estar en los valores de fábrica.")
    return RedirectResponse("/admin/economia#supuestos", status_code=303)


@router.post("/admin/economia/restaurar")
def admin_economia_restaurar(request: Request):
    """Devuelve todos los supuestos a los valores de fábrica."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    user = auth.current_user(request)
    borrados = db.reset_economy_assumptions()
    db.record_security_event(
        "admin.economia_assumptions_reset", area="admin", actor_user_id=user["id"],
        subject_business_id=user["business_id"],
        request_id=getattr(request.state, "request_id", None),
        metadata={"borrados": borrados},
    )
    request.session["admin_success"] = (
        f"Restaurados {borrados} supuesto(s) a los valores de fábrica."
        if borrados else "No había nada cambiado que restaurar.")
    return RedirectResponse("/admin/economia#supuestos", status_code=303)


def _economia_descarga(request: Request, kind: str) -> Response:
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    user = auth.current_user(request)
    contexto = _economia_contexto(request)
    db.record_security_event(
        f"admin.economia_{kind}_downloaded", area="admin", actor_user_id=user["id"],
        subject_business_id=user["business_id"],
        request_id=getattr(request.state, "request_id", None),
    )
    hoy = date.today().isoformat()
    if kind == "docx":
        blob = economics_docs.summary_docx(contexto["report"], contexto["timeline"])
        media = ("application/vnd.openxmlformats-officedocument"
                 ".wordprocessingml.document")
    else:
        blob = economics_docs.summary_xlsx(contexto["report"], contexto["timeline"])
        media = ("application/vnd.openxmlformats-officedocument"
                 ".spreadsheetml.sheet")
    return Response(
        content=blob, media_type=media,
        headers={
            "Content-Disposition":
                f'attachment; filename="Bynoesis-resumen-economico-{hoy}.{kind}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/admin/economia/resumen.docx")
def admin_economia_docx(request: Request):
    """Word de dos páginas con lo esencial, generado con los datos de hoy."""
    return _economia_descarga(request, "docx")


@router.get("/admin/economia/resumen.xlsx")
def admin_economia_xlsx(request: Request):
    """Excel de dos hojas con las mismas cifras y formato de número."""
    return _economia_descarga(request, "xlsx")


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
            "Tu acceso a Bynoesis ya está listo",
            "\n".join([
                f"Hola, {solicitud['name']}:",
                "",
                "Ya tienes tu cuenta de Bynoesis preparada. Elige tu contraseña aquí:",
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
