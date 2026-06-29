"""WhatsApp: enrutado de mensajes entrantes y onboarding exprés.

Modelo: UN solo número de Noesis. Cada autónomo le escribe desde su móvil y se le
identifica por su teléfono. Así un cliente nuevo se conecta en segundos y solo hace
falta UNA verificación de empresa en Meta (la nuestra), no una por cliente.

Vinculación exprés: el autónomo abre un enlace wa.me con un código prefijado, lo
envía al número de Noesis y su teléfono queda ligado a su cuenta automáticamente.

El envío real (Cloud API de Meta) se activa cuando haya WHATSAPP_TOKEN; mientras,
`send` solo registra en log. Así todo el enrutado se puede probar sin Meta.
"""

from __future__ import annotations

import logging
import os
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta

from .. import db
from .. import config
from . import chat

log = logging.getLogger("uvicorn.error")

# Número de WhatsApp Business de Noesis (el único). Se pone cuando Meta lo apruebe.
NOESIS_NUMBER = os.getenv("NOESIS_WHATSAPP_NUMBER", "")
_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")

_CODE_TTL = 1800  # 30 min


# ----------------------------------------------------------- Onboarding exprés --
def start_link(business_id: int) -> dict:
    """Genera un código de vinculación y el enlace wa.me para enviarlo."""
    code = secrets.token_hex(3).upper()  # 6 caracteres
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
    """Si el texto es 'NOESIS <code>' válido, liga el teléfono a su negocio."""
    parts = (text or "").strip().split()
    if len(parts) == 2 and parts[0].upper() == "NOESIS":
        code = parts[1].upper()
        business_id = db.consume_whatsapp_link(
            hashlib.sha256(code.encode()).hexdigest()
        )
        if business_id:
            try:
                db.set_whatsapp_status(business_id, "conectado", phone=from_phone)
                db.finish_onboarding(business_id)
            except Exception:  # noqa: BLE001
                log.exception("No se pudo vincular WhatsApp al negocio %s.", business_id)
                return (
                    "Ese teléfono ya está vinculado o no es válido. "
                    "Revísalo desde Ajustes."
                )
            biz = db.get_business(business_id) or {}
            return (f"WhatsApp conectado a {biz.get('name', 'tu negocio')}. "
                    "Ya puedes pedirme cosas: «¿qué tengo hoy?», «factura a Juan 95€»…")
        return ("Ese código no es válido o ha caducado. Genera uno nuevo desde "
                "Ajustes en la web.")
    return None


# ------------------------------------------------------------------- Entrantes --
def _extract_messages(payload: dict) -> list[dict]:
    """Saca los mensajes del payload (texto o audio). Soporta el formato de Meta
    Cloud API y uno simple {from, text} para pruebas."""
    out: list[dict] = []
    if not isinstance(payload, dict):
        return out
    if payload.get("from") and (payload.get("text") is not None or payload.get("audio_id")):
        out.append({
            "id": str(payload.get("id") or ""),
            "phone": str(payload["from"]),
            "text": str(payload.get("text") or ""),
            "audio_id": payload.get("audio_id"),
        })
        return out
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            for msg in value.get("messages", []) or []:
                phone = msg.get("from", "")
                if not phone:
                    continue
                text = (msg.get("text", {}) or {}).get("body", "")
                audio_id = (msg.get("audio", {}) or {}).get("id")
                out.append({
                    "id": str(msg.get("id") or ""),
                    "phone": phone, "text": text, "audio_id": audio_id,
                })
    return out


def _download_media(media_id: str) -> bytes | None:
    """Descarga un audio de WhatsApp por su media_id (necesita WHATSAPP_TOKEN)."""
    if not _TOKEN:
        return None
    import json as _json
    import urllib.request
    try:
        meta_req = urllib.request.Request(
            f"https://graph.facebook.com/{config.META_GRAPH_VERSION}/{media_id}",
            headers={"Authorization": f"Bearer {_TOKEN}"})
        info = _json.loads(urllib.request.urlopen(meta_req, timeout=10).read())
        media_req = urllib.request.Request(
            info["url"], headers={"Authorization": f"Bearer {_TOKEN}"})
        data = urllib.request.urlopen(media_req, timeout=20).read(
            config.MAX_AUDIO_BYTES + 1
        )
        return data if len(data) <= config.MAX_AUDIO_BYTES else None
    except Exception as e:  # noqa: BLE001
        log.warning("Fallo descargando audio %s: %s", media_id, e)
        return None


def _audio_to_text(audio_id: str) -> str | None:
    """Descarga el audio y lo transcribe con Whisper local (sin coste por uso)."""
    from ..adapters import transcription
    tr = transcription.get_transcriber()
    if tr is None:
        return None
    data = _download_media(audio_id)
    if not data:
        return None
    try:
        return tr.transcribe(data, "voz.ogg")
    except Exception as e:  # noqa: BLE001
        log.warning("Fallo transcribiendo audio: %s", e)
        return None


def handle_inbound(payload: dict) -> dict:
    """Procesa los mensajes entrantes (texto y notas de voz): vincula por código o
    los enruta al cerebro del negocio que escribe."""
    results = []
    for msg in _extract_messages(payload):
        message_id = msg.get("id")
        if message_id and not db.claim_webhook_event("whatsapp", message_id):
            results.append({"id": message_id, "duplicate": True})
            continue
        phone, text, audio_id = msg["phone"], msg["text"], msg.get("audio_id")

        # Nota de voz: transcribir a texto (Whisper local) antes de procesar.
        if audio_id and not text:
            text = _audio_to_text(audio_id) or ""
            if not text:
                send(phone, "He recibido tu nota de voz pero no he podido transcribirla. "
                            "Escríbeme la orden en texto, por favor.")
                results.append({"phone": phone, "audio": True, "transcribed": False})
                continue

        linked = _try_link(phone, text)
        if linked is not None:
            send(phone, linked)
            results.append({"phone": phone, "linked": True})
            continue
        biz = db.get_business_by_phone(phone)
        if not biz:
            send(phone, "Tu número no está dado de alta en Noesis. Regístrate en "
                        "bynoesis.com y conecta tu WhatsApp para empezar.")
            results.append({"phone": phone, "known": False})
            continue
        reply = chat.handle(biz["id"], text).get("reply", "")
        send(phone, reply)
        results.append({"phone": phone, "business_id": biz["id"], "voice": bool(audio_id)})
    return {"processed": len(results), "results": results}


def send(to: str, text: str) -> bool:
    """Envía un mensaje por WhatsApp. Real cuando hay token; si no, solo log."""
    if not (_TOKEN and _PHONE_ID):
        log.info("[whatsapp:simulado] -> %s: %s", to, text[:80])
        return False
    import urllib.request
    import json as _json
    url = (
        f"https://graph.facebook.com/{config.META_GRAPH_VERSION}/"
        f"{_PHONE_ID}/messages"
    )
    body = _json.dumps({"messaging_product": "whatsapp", "to": to,
                        "type": "text", "text": {"body": text}}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {_TOKEN}", "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("Fallo enviando WhatsApp a %s: %s", to, e)
        return False


def verify_signature(payload: bytes, header: str) -> bool:
    """Verifica que el POST procede de Meta usando el secreto de la aplicación."""
    secret = config.WHATSAPP_APP_SECRET
    if not secret:
        return not config.IS_PRODUCTION
    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return bool(header) and hmac.compare_digest(expected, header)
