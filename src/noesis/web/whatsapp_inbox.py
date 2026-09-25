"""Acuse durable y consumidor del motor WhatsApp existente, sin repetir escrituras."""
import hashlib
import json
import logging

from .. import config, db
from . import whatsapp

log = logging.getLogger(__name__)


def _key(*parts: str) -> str:
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()


def _business(payload: dict) -> int | None:
    recipient = payload.get("recipient_phone_id")
    if recipient and recipient != str(whatsapp._PHONE_ID or "").strip():
        connection = db.get_whatsapp_connection_by_phone_number_id(recipient)
        return connection["business_id"] if connection else None
    phone = payload.get("from") or ""
    owner = db.get_business_by_phone(phone) if phone else None
    worker = db.get_worker_by_phone(phone) if phone and not owner else None
    return owner["id"] if owner else worker["business_id"] if worker else None


def accept(payload: dict) -> dict:
    """Solo llamar tras comprobar firma y tamaño en el router."""
    events = []
    for message in whatsapp._extract_messages(payload):
        if not message.get("id"):
            raise ValueError("Mensaje sin identificador; no se acepta sin deduplicación.")
        item = {**message, "from": message["phone"]}
        recipient = item.get("recipient_phone_id", "")
        events.append({"business_id": _business(item),
                       "event_key": _key("message", recipient, item["id"]),
                       "conversation_key": _key("conversation", recipient, item["from"]),
                       "payload": item})
    for status in whatsapp._extract_statuses(payload):
        item = {**status, "message_id": status["id"]}
        events.append({"event_key": _key("status", status["id"], status["status"], status.get("timestamp", "")),
                       "conversation_key": _key("status", status["id"]), "payload": item})
    return {"status": "queued", "accepted": db.enqueue_whatsapp_inbound(events)}


def process(limit: int = 25) -> int:
    if not config.WHATSAPP_INBOX_ENABLED:
        return 0
    count = 0
    for _ in range(max(0, min(limit, 100))):
        row = db.claim_whatsapp_inbound()
        if not row:
            break
        try:
            payload = json.loads(row["payload"])
            if row["business_id"] is not None and _business(payload) != row["business_id"]:
                db.finish_whatsapp_inbound(row["id"], error_code="routing_changed")
                continue
            whatsapp.handle_inbound(payload)
        except Exception:  # noqa: BLE001 - efectos inciertos: revisión, nunca reejecución automática
            db.finish_whatsapp_inbound(row["id"], error_code="processing_failed")
            log.warning("Entrada WhatsApp requiere revisión id=%s", row["id"])
        else:
            db.finish_whatsapp_inbound(row["id"])
        count += 1
    return count
