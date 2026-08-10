"""Canal comercial de WhatsApp conectado a cada negocio."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ... import db
from .. import whatsapp
from ..deps import _read_json

router = APIRouter()


@router.get("/api/{business_id}/whatsapp-business")
def api_whatsapp_business(business_id: int):
    connections = db.list_whatsapp_connections(business_id)
    return {
        "connections": connections,
        "inbox": db.list_whatsapp_inbox(business_id, limit=50),
        "principle": (
            "El número del negocio atiende a sus clientes; el número central de "
            "Noesis queda reservado al titular y al equipo."
        ),
    }


@router.post("/api/{business_id}/whatsapp-business/{connection_id}/receptionist")
async def api_whatsapp_receptionist(
    business_id: int, connection_id: int, request: Request
):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    enabled = body.get("enabled")
    if not isinstance(enabled, bool):
        return JSONResponse(
            {"error": "El estado de recepción no es válido."}, status_code=400
        )
    current = db.get_whatsapp_connection(connection_id, business_id)
    if not current:
        return JSONResponse({"error": "Conexión no encontrada."}, status_code=404)
    if enabled and current.get("status") != "active":
        return JSONResponse(
            {"error": "Meta debe validar el número antes de activar la recepción."},
            status_code=409,
        )
    return db.update_whatsapp_connection(
        connection_id, business_id, receptionist_enabled=enabled
    )


@router.get("/api/{business_id}/whatsapp-business/inbox")
def api_whatsapp_business_inbox(business_id: int, limit: int = 100):
    return {"items": db.list_whatsapp_inbox(business_id, limit=limit)}


@router.post("/api/{business_id}/whatsapp-business/conversations/{conversation_id}/reply")
async def api_whatsapp_business_reply(
    business_id: int, conversation_id: int, request: Request
):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    text = str(body.get("text") or "").strip()
    if not text or len(text) > 2000:
        return JSONResponse(
            {"error": "Escribe una respuesta de hasta 2.000 caracteres."},
            status_code=400,
        )
    conversation = db.get_whatsapp_conversation(conversation_id, business_id)
    if not conversation:
        return JSONResponse({"error": "Conversación no encontrada."}, status_code=404)
    if conversation.get("consent_status") != "active":
        return JSONResponse(
            {"error": "Este contacto ha pedido no recibir mensajes."}, status_code=409
        )
    try:
        window_open = datetime.fromisoformat(
            str(conversation.get("last_inbound_at") or "")
        ) >= datetime.now() - timedelta(hours=24)
    except ValueError:
        window_open = False
    if not window_open:
        return JSONResponse(
            {"error": (
                "Han pasado más de 24 horas desde el último mensaje. "
                "Para reabrir la conversación debe usarse una plantilla aprobada."
            )},
            status_code=409,
        )
    message = whatsapp.queue_text(
        conversation["wa_id"], text, business_id=business_id,
        connection_id=conversation["connection_id"],
    )
    db.update_whatsapp_conversation(
        conversation_id, business_id, status="resolved", human_handoff=False,
        summary=f"Respondido desde el panel: {text}",
    )
    return {"ok": True, "message_id": message["id"], "status": message["status"]}


@router.post("/api/{business_id}/whatsapp-business/conversations/{conversation_id}/resolve")
def api_whatsapp_business_resolve(business_id: int, conversation_id: int):
    conversation = db.update_whatsapp_conversation(
        conversation_id, business_id, status="resolved", human_handoff=False
    )
    if not conversation:
        return JSONResponse({"error": "Conversación no encontrada."}, status_code=404)
    return conversation
