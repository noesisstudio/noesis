"""Canal WhatsApp: onboarding, entrada idempotente y salida durable.

Hay un único número de Noesis. El teléfono remitente identifica al negocio y los
mensajes salientes se persisten antes de contactar con Meta. Los proactivos usan
plantillas aprobadas; las respuestas a un mensaje entrante pueden usar texto libre
dentro de la ventana de atención de 24 horas.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from .. import config, db
from . import chat

log = logging.getLogger("uvicorn.error")

NOESIS_NUMBER = os.getenv("NOESIS_WHATSAPP_NUMBER", "")
_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")
_CODE_TTL = 1800


# ----------------------------------------------------------- Onboarding exprés --
def start_link(business_id: int) -> dict:
    """Genera un código de vinculación y el enlace wa.me para enviarlo."""
    code = secrets.token_hex(3).upper()
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    expires = (
        datetime.now() + timedelta(seconds=_CODE_TTL)
    ).isoformat(timespec="seconds")
    db.create_whatsapp_link(code_hash, business_id, expires)
    text = f"NOESIS {code}"
    number = NOESIS_NUMBER or "TUNUMERO"
    link = f"https://wa.me/{number}?text={text.replace(' ', '%20')}"
    return {"code": code, "link": link, "number": NOESIS_NUMBER}


def _try_link(from_phone: str, text: str) -> str | None:
    """Si el texto es ``NOESIS <code>``, liga el teléfono al negocio."""
    parts = (text or "").strip().split()
    if len(parts) != 2 or parts[0].upper() != "NOESIS":
        return None
    business_id = db.consume_whatsapp_link(
        hashlib.sha256(parts[1].upper().encode()).hexdigest()
    )
    if not business_id:
        return (
            "Ese código no es válido o ha caducado. Genera uno nuevo desde "
            "Ajustes en la web."
        )
    try:
        db.set_whatsapp_status(business_id, "conectado", phone=from_phone)
        db.finish_onboarding(business_id)
        db.record_product_event(business_id, "whatsapp_connected")
    except Exception:  # noqa: BLE001
        log.exception("No se pudo vincular WhatsApp al negocio %s.", business_id)
        return (
            "Ese teléfono ya está vinculado o no es válido. "
            "Revísalo desde Ajustes."
        )
    business = db.get_business(business_id) or {}
    return (
        f"WhatsApp conectado a {business.get('name', 'tu negocio')}. "
        "Ya puedes pedirme cosas: «¿qué tengo hoy?», «factura a Juan 95 €»…"
    )


def _try_worker_link(from_phone: str, text: str) -> dict | None:
    """Liga ``NOESIS EQUIPO <negocio> <código>`` al teléfono remitente."""
    parts = (text or "").strip().split()
    if len(parts) != 4 or [part.upper() for part in parts[:2]] != [
        "NOESIS", "EQUIPO"
    ]:
        return None
    try:
        business_id = int(parts[2])
    except ValueError:
        return {
            "business_id": None,
            "reply": "El código de equipo no es válido. Pide uno nuevo a tu empresa.",
        }
    try:
        worker = db.bind_worker_phone(business_id, parts[3], from_phone)
    except ValueError as exc:
        return {"business_id": business_id, "reply": str(exc)}
    if not worker:
        return {
            "business_id": business_id,
            "reply": "Ese código de equipo no es válido. Pide uno nuevo a tu empresa.",
        }
    return {
        "business_id": business_id,
        "worker_id": worker["id"],
        "reply": (
            f"Hola, {worker['name']}. Tu WhatsApp ya está vinculado. "
            "Escribe ENTRADA al empezar y SALIDA al terminar."
        ),
    }


def _try_worker_clock(from_phone: str, text: str) -> dict | None:
    worker = db.get_worker_by_phone(from_phone)
    if not worker:
        return None
    action = (text or "").strip().lower()
    if action not in {"entrada", "salida"}:
        if db.get_business_by_phone(from_phone):
            return None
        return {
            "business_id": worker["business_id"],
            "worker_id": worker["id"],
            "reply": "Para fichar escribe ENTRADA o SALIDA.",
            "clocked": False,
        }
    try:
        clockin = db.clock_worker(
            worker["business_id"], worker["id"], action, "whatsapp"
        )
    except ValueError as exc:
        return {
            "business_id": worker["business_id"],
            "worker_id": worker["id"],
            "reply": str(exc),
            "clocked": False,
        }
    hour = str(clockin["at"])[11:16]
    return {
        "business_id": worker["business_id"],
        "worker_id": worker["id"],
        "reply": f"{action.capitalize()} registrada a las {hour}.",
        "clocked": True,
    }


# ------------------------------------------------------------------- Entrantes --
def _extract_messages(payload: dict) -> list[dict]:
    """Extrae mensajes de Meta y admite un formato simple para pruebas."""
    out: list[dict] = []
    if not isinstance(payload, dict):
        return out
    if payload.get("from") and (
        payload.get("text") is not None or payload.get("audio_id")
    ):
        return [{
            "id": str(payload.get("id") or ""),
            "phone": str(payload["from"]),
            "text": str(payload.get("text") or ""),
            "audio_id": payload.get("audio_id"),
        }]
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            for message in value.get("messages", []) or []:
                phone = message.get("from", "")
                if not phone:
                    continue
                out.append({
                    "id": str(message.get("id") or ""),
                    "phone": phone,
                    "text": (message.get("text", {}) or {}).get("body", ""),
                    "audio_id": (message.get("audio", {}) or {}).get("id"),
                })
    return out


def _extract_statuses(payload: dict) -> list[dict]:
    """Extrae estados de entrega de Meta y admite un formato simple en tests."""
    if not isinstance(payload, dict):
        return []
    if payload.get("message_id") and payload.get("status"):
        return [{
            "id": str(payload["message_id"]),
            "status": str(payload["status"]),
            "timestamp": str(payload.get("timestamp") or ""),
            "errors": payload.get("errors") or [],
        }]
    out: list[dict] = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            for status in value.get("statuses", []) or []:
                if status.get("id") and status.get("status"):
                    out.append({
                        "id": str(status["id"]),
                        "status": str(status["status"]),
                        "timestamp": str(status.get("timestamp") or ""),
                        "errors": status.get("errors") or [],
                    })
    return out


def _status_time(raw: str) -> str:
    try:
        return datetime.fromtimestamp(
            int(raw), tz=timezone.utc
        ).replace(tzinfo=None).isoformat(timespec="seconds")
    except (TypeError, ValueError, OSError):
        return datetime.now().isoformat(timespec="seconds")


def _handle_status(status: dict) -> dict:
    message_id = status["id"]
    delivery_status = status["status"]
    # No consumimos el evento hasta poder asociarlo. Así un callback que se
    # adelante al commit de ``mark_whatsapp_sent`` puede volver a entregarse.
    if not db.find_whatsapp_message_by_meta_id(message_id):
        return {
            "id": message_id,
            "status": delivery_status,
            "updated": False,
        }
    event_key = f"{message_id}:{delivery_status}:{status.get('timestamp', '')}"
    if not db.claim_webhook_event("whatsapp_status", event_key):
        return {"id": message_id, "status": delivery_status, "duplicate": True}
    errors = status.get("errors") or []
    error = (
        errors[0].get("message")
        if errors and isinstance(errors[0], dict)
        else None
    )
    updated = db.update_whatsapp_delivery(
        message_id,
        delivery_status,
        _status_time(status.get("timestamp", "")),
        error,
    )
    return {
        "id": message_id,
        "status": delivery_status,
        "updated": bool(updated),
    }


def _download_media(media_id: str) -> bytes | None:
    """Descarga un audio de WhatsApp si el token de Meta está configurado."""
    if not _TOKEN:
        return None
    try:
        metadata_request = urllib.request.Request(
            f"https://graph.facebook.com/{config.META_GRAPH_VERSION}/{media_id}",
            headers={"Authorization": f"Bearer {_TOKEN}"},
        )
        info = json.loads(
            urllib.request.urlopen(metadata_request, timeout=10).read()
        )
        media_request = urllib.request.Request(
            info["url"], headers={"Authorization": f"Bearer {_TOKEN}"}
        )
        data = urllib.request.urlopen(media_request, timeout=20).read(
            config.MAX_AUDIO_BYTES + 1
        )
        return data if len(data) <= config.MAX_AUDIO_BYTES else None
    except Exception as exc:  # noqa: BLE001
        log.warning("Fallo descargando audio %s: %s", media_id, exc)
        return None


def _audio_to_text(audio_id: str) -> str | None:
    """Descarga el audio y lo transcribe con Whisper local."""
    from ..adapters import transcription

    transcriber = transcription.get_transcriber()
    if transcriber is None:
        return None
    data = _download_media(audio_id)
    if not data:
        return None
    try:
        return transcriber.transcribe(data, "voz.ogg")
    except Exception as exc:  # noqa: BLE001
        log.warning("Fallo transcribiendo audio: %s", exc)
        return None


def handle_inbound(payload: dict) -> dict:
    """Procesa mensajes y estados de Meta de forma idempotente."""
    results = [_handle_status(status) for status in _extract_statuses(payload)]
    for message in _extract_messages(payload):
        message_id = message.get("id")
        if message_id and not db.claim_webhook_event("whatsapp", message_id):
            results.append({"id": message_id, "duplicate": True})
            continue
        phone = message["phone"]
        text = message["text"]
        audio_id = message.get("audio_id")

        if audio_id and not text:
            text = _audio_to_text(audio_id) or ""
            if not text:
                business = db.get_business_by_phone(phone)
                send(
                    phone,
                    "He recibido tu nota de voz pero no he podido transcribirla. "
                    "Escríbeme la orden en texto, por favor.",
                    business_id=business["id"] if business else None,
                )
                results.append({
                    "phone": phone, "audio": True, "transcribed": False,
                })
                continue

        worker_link = _try_worker_link(phone, text)
        if worker_link is not None:
            send(
                phone,
                worker_link["reply"],
                business_id=worker_link.get("business_id"),
            )
            results.append({
                "phone": phone,
                "worker_id": worker_link.get("worker_id"),
                "worker_linked": bool(worker_link.get("worker_id")),
            })
            continue

        linked = _try_link(phone, text)
        if linked is not None:
            business = db.get_business_by_phone(phone)
            send(
                phone, linked,
                business_id=business["id"] if business else None,
            )
            results.append({"phone": phone, "linked": True})
            continue

        worker_clock = _try_worker_clock(phone, text)
        if worker_clock is not None:
            send(
                phone,
                worker_clock["reply"],
                business_id=worker_clock["business_id"],
            )
            results.append({
                "phone": phone,
                "business_id": worker_clock["business_id"],
                "worker_id": worker_clock["worker_id"],
                "clocked": worker_clock["clocked"],
            })
            continue

        business = db.get_business_by_phone(phone)
        if not business:
            send(
                phone,
                "Tu número no está dado de alta en Noesis. Regístrate en "
                "bynoesis.com y conecta tu WhatsApp para empezar.",
            )
            results.append({"phone": phone, "known": False})
            continue
        reply = chat.handle(business["id"], text).get("reply", "")
        send(phone, reply, business_id=business["id"])
        results.append({
            "phone": phone,
            "business_id": business["id"],
            "voice": bool(audio_id),
        })
    return {"processed": len(results), "results": results}


# -------------------------------------------------------------------- Salientes --
def _meta_payload(message: dict) -> dict:
    if message["message_type"] == "text":
        return {
            "messaging_product": "whatsapp",
            "to": message["to_phone"],
            "type": "text",
            "text": {"body": message["text_body"]},
        }
    params = json.loads(message.get("template_params") or "[]")
    components = []
    if params:
        components.append({
            "type": "body",
            "parameters": [{"type": "text", "text": value} for value in params],
        })
    return {
        "messaging_product": "whatsapp",
        "to": message["to_phone"],
        "type": "template",
        "template": {
            "name": message["template_name"],
            "language": {"code": message["template_language"]},
            "components": components,
        },
    }


def _post_to_meta(payload: dict) -> str:
    """Realiza un intento y devuelve el wamid asignado por Meta."""
    if not (_TOKEN and _PHONE_ID):
        raise RuntimeError("WhatsApp Cloud API no está configurada.")
    url = (
        f"https://graph.facebook.com/{config.META_GRAPH_VERSION}/"
        f"{_PHONE_ID}/messages"
    )
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        response = json.loads(urllib.request.urlopen(request, timeout=10).read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:1000]
        raise RuntimeError(f"Meta respondió {exc.code}: {detail}") from exc
    messages = response.get("messages") or []
    if not messages or not messages[0].get("id"):
        raise RuntimeError("Meta no devolvió el identificador del mensaje.")
    return str(messages[0]["id"])


def process_outbox(
    *,
    limit: int = 25,
    only_ids: list[int] | None = None,
    now: datetime | None = None,
) -> list[dict]:
    """Procesa mensajes vencidos; los fallos quedan reprogramados con backoff."""
    point = now or datetime.now()
    now_text = point.isoformat(timespec="seconds")
    stale_before = (point - timedelta(minutes=5)).isoformat(timespec="seconds")
    processed: list[dict] = []
    for _ in range(max(1, min(limit, 100))):
        message = db.claim_next_whatsapp_message(
            now=now_text,
            stale_before=stale_before,
            only_ids=only_ids,
        )
        if not message:
            break
        try:
            meta_message_id = _post_to_meta(_meta_payload(message))
            db.mark_whatsapp_sent(message["id"], meta_message_id, now_text)
            processed.append({
                "id": message["id"],
                "status": "sent",
                "meta_message_id": meta_message_id,
            })
        except Exception as exc:  # noqa: BLE001
            delay = min(
                config.WHATSAPP_RETRY_BASE_SECONDS
                * (2 ** max(0, message["attempts"] - 1)),
                config.WHATSAPP_RETRY_MAX_SECONDS,
            )
            next_attempt = (
                point + timedelta(seconds=delay)
            ).isoformat(timespec="seconds")
            updated = db.mark_whatsapp_retry(
                message["id"],
                error=str(exc),
                next_attempt_at=next_attempt,
                updated_at=now_text,
            )
            status = updated["status"] if updated else "retrying"
            log.warning(
                "Fallo enviando WhatsApp outbox=%s intento=%s: %s",
                message["id"], message["attempts"], exc,
            )
            processed.append({
                "id": message["id"],
                "status": status,
                "error": str(exc),
            })
    return processed


def queue_text(
    to: str,
    text: str,
    *,
    business_id: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | None = None,
) -> dict:
    point = now or datetime.now()
    return db.enqueue_whatsapp_message(
        business_id=business_id,
        to_phone=to,
        message_type="text",
        text_body=text,
        idempotency_key=idempotency_key,
        max_attempts=config.WHATSAPP_MAX_ATTEMPTS,
        now=point.isoformat(timespec="seconds"),
    )


def queue_template(
    to: str,
    template_name: str,
    params: list[str] | None = None,
    *,
    business_id: int | None = None,
    language: str | None = None,
    idempotency_key: str | None = None,
    now: datetime | None = None,
) -> dict:
    point = now or datetime.now()
    return db.enqueue_whatsapp_message(
        business_id=business_id,
        to_phone=to,
        message_type="template",
        template_name=template_name,
        template_language=language or config.WHATSAPP_TEMPLATE_LANGUAGE,
        template_params=json.dumps(params or [], ensure_ascii=False),
        idempotency_key=idempotency_key,
        max_attempts=config.WHATSAPP_MAX_ATTEMPTS,
        now=point.isoformat(timespec="seconds"),
    )


def send(
    to: str,
    text: str,
    *,
    business_id: int | None = None,
    idempotency_key: str | None = None,
) -> bool:
    """Encola de forma durable y hace un primer intento inmediato."""
    message = queue_text(
        to,
        text,
        business_id=business_id,
        idempotency_key=idempotency_key,
    )
    process_outbox(only_ids=[message["id"]], limit=1)
    return True


def send_template(
    to: str,
    template_name: str,
    params: list[str] | None = None,
    *,
    business_id: int | None = None,
    language: str | None = None,
    idempotency_key: str | None = None,
) -> bool:
    """Encola una plantilla aprobada, vía obligatoria para proactivos."""
    message = queue_template(
        to,
        template_name,
        params,
        business_id=business_id,
        language=language,
        idempotency_key=idempotency_key,
    )
    process_outbox(only_ids=[message["id"]], limit=1)
    return True


def send_payment_reminder(
    to: str,
    client_name: str,
    amount: str,
    invoice_number: str,
    *,
    business_id: int,
    idempotency_key: str | None = None,
) -> bool:
    """Envía el proactivo de cobro mediante plantilla aprobada por Meta."""
    return send_template(
        to,
        config.WHATSAPP_TEMPLATE_PAYMENT_REMINDER,
        [client_name, invoice_number, amount],
        business_id=business_id,
        idempotency_key=idempotency_key,
    )


def verify_signature(payload: bytes, header: str) -> bool:
    """Verifica que el POST procede de Meta usando el secreto de la aplicación."""
    secret = config.WHATSAPP_APP_SECRET
    if not secret:
        return not config.IS_PRODUCTION
    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return bool(header) and hmac.compare_digest(expected, header)
