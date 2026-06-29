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
import time

from .. import db
from . import chat

log = logging.getLogger("uvicorn.error")

# Número de WhatsApp Business de Noesis (el único). Se pone cuando Meta lo apruebe.
NOESIS_NUMBER = os.getenv("NOESIS_WHATSAPP_NUMBER", "")
_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")

# Códigos de vinculación pendientes: code -> (business_id, timestamp). En memoria;
# la verificación ocurre a los pocos minutos del onboarding.
_PENDING: dict[str, tuple[int, float]] = {}
_CODE_TTL = 1800  # 30 min


# ----------------------------------------------------------- Onboarding exprés --
def start_link(business_id: int) -> dict:
    """Genera un código de vinculación y el enlace wa.me para enviarlo."""
    code = secrets.token_hex(3).upper()  # 6 caracteres
    _PENDING[code] = (business_id, time.time())
    text = f"NOESIS {code}"
    number = NOESIS_NUMBER or "TUNUMERO"
    link = f"https://wa.me/{number}?text={text.replace(' ', '%20')}"
    return {"code": code, "link": link, "number": NOESIS_NUMBER}


def _try_link(from_phone: str, text: str) -> str | None:
    """Si el texto es 'NOESIS <code>' válido, liga el teléfono a su negocio."""
    parts = (text or "").strip().split()
    if len(parts) == 2 and parts[0].upper() == "NOESIS":
        code = parts[1].upper()
        entry = _PENDING.get(code)
        if entry and time.time() - entry[1] < _CODE_TTL:
            business_id = entry[0]
            db.set_whatsapp_status(business_id, "conectado", phone=from_phone)
            _PENDING.pop(code, None)
            biz = db.get_business(business_id) or {}
            return (f"WhatsApp conectado a {biz.get('name', 'tu negocio')}. "
                    "Ya puedes pedirme cosas: «¿qué tengo hoy?», «factura a Juan 95€»…")
        return ("Ese código no es válido o ha caducado. Genera uno nuevo desde "
                "Ajustes en la web.")
    return None


# ------------------------------------------------------------------- Entrantes --
def _extract_messages(payload: dict) -> list[tuple[str, str]]:
    """Saca (telefono, texto) del payload. Soporta el formato de Meta Cloud API y
    un formato simple {from, text} para pruebas."""
    out: list[tuple[str, str]] = []
    if not isinstance(payload, dict):
        return out
    if payload.get("from") and payload.get("text") is not None:  # formato de prueba
        out.append((str(payload["from"]), str(payload["text"])))
        return out
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            for msg in value.get("messages", []) or []:
                phone = msg.get("from", "")
                body = (msg.get("text", {}) or {}).get("body", "")
                if phone:
                    out.append((phone, body))
    return out


def handle_inbound(payload: dict) -> dict:
    """Procesa los mensajes entrantes: vincula por código o enruta al cerebro."""
    results = []
    for phone, text in _extract_messages(payload):
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
        results.append({"phone": phone, "business_id": biz["id"]})
    return {"processed": len(results), "results": results}


def send(to: str, text: str) -> bool:
    """Envía un mensaje por WhatsApp. Real cuando hay token; si no, solo log."""
    if not (_TOKEN and _PHONE_ID):
        log.info("[whatsapp:simulado] -> %s: %s", to, text[:80])
        return False
    import urllib.request
    import json as _json
    url = f"https://graph.facebook.com/v20.0/{_PHONE_ID}/messages"
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
