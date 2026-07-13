"""Rutas de gestoria."""

from __future__ import annotations

import json

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse

from ... import db
from ..deps import _read_json

router = APIRouter()

@router.get("/api/{business_id}/gestoria/requests")
def api_gestoria_requests(business_id: int, status: str = ""):
    try:
        return db.list_gestoria_requests(business_id, status=status or None)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/api/{business_id}/gestoria/requests")
async def api_add_gestoria_request(business_id: int, request: Request):
    """El autónomo anota algo para su gestoría desde la app."""
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    try:
        return db.add_gestoria_request(
            body.get("message"), requested_by="autonomo",
            document_id=body.get("document_id") or None,
            business_id=business_id)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/api/{business_id}/gestoria/requests/{request_id}/reply")
async def api_reply_gestoria_request(business_id: int, request_id: int,
                                     request: Request):
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    try:
        return db.reply_gestoria_request(
            request_id, body.get("reply"), business_id=business_id,
            document_id=body.get("document_id") or None,
            close=bool(body.get("close")))
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


# ------------------------------------------------- Pérdidas y ganancias ---


@router.post("/b/{business_id}/gestoria")
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


@router.post("/b/{business_id}/gestoria/send-now")
def gestoria_send_now(business_id: int):
    from .. import gestoria as gestoria_service
    business = db.get_business(business_id)
    if not business or (business.get("gestoria_cadence") or "off") == "off":
        return RedirectResponse(
            f"/b/{business_id}/ajustes?error=gestoria#gestoria",
            status_code=303,
        )
    label = gestoria_service.previous_label(business["gestoria_cadence"])
    package = gestoria_service.build_package(business_id, label)
    if not package:
        return RedirectResponse(
            f"/b/{business_id}/ajustes?error=gestoria#gestoria",
            status_code=303,
        )
    _data, meta = package
    emailed = gestoria_service.notify_gestoria(business, label)
    if emailed:
        db.mark_gestoria_delivery(business_id, label, "notified")
    db.record_assistant_action(
        business_id,
        "send_gestoria",
        f"Preparé el paquete {label} v{meta['version']} y "
        + ("avisé a tu gestoría." if emailed else "dejé listo su enlace."),
        status="executed",
        target_type="gestoria_delivery",
        payload={"label": label, "version": meta["version"],
                 "emailed": bool(emailed)},
        requested_by="user",
        approved_by="autónomo desde Ajustes",
    )
    db.record_product_event(
        business_id, "gestoria_send_now",
        json.dumps({"label": label, "emailed": bool(emailed)},
                   separators=(",", ":")),
    )
    ok = "gestoria-enviado" if emailed else "gestoria-enlace"
    return RedirectResponse(
        f"/b/{business_id}/ajustes?ok={ok}#gestoria", status_code=303
    )
