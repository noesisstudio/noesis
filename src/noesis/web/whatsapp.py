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
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from .. import config, db
from ..adapters import billing as billing_adapter
from . import chat

log = logging.getLogger("uvicorn.error")

NOESIS_NUMBER = os.getenv("NOESIS_WHATSAPP_NUMBER", "")
_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")
_CODE_TTL = 1800


class WebhookInProgress(RuntimeError):
    """El mismo evento sigue en curso y debe reintentarse más tarde."""


class MetaRejected(RuntimeError):
    """Meta ha rechazado el mensaje: repetirlo daría exactamente lo mismo.

    Una plantilla que no existe, un destinatario inválido o un número de huecos
    que no cuadra no se arreglan esperando. Reintentarlos seis veces con espera
    creciente solo retrasa una hora la noticia de que algo está mal configurado.
    """


def is_configured() -> bool:
    """La cola proactiva solo se alimenta cuando Meta puede procesarla."""
    return bool(_TOKEN and _PHONE_ID)


def recipient_phone(value: str | None) -> str | None:
    """Normaliza un destinatario para Meta; añade España si faltaba el prefijo."""
    digits = "".join(char for char in (value or "") if char.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 9:
        return f"34{digits}"
    if 10 <= len(digits) <= 15:
        return digits
    return None


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
    business = db.get_business(business_id)
    if not db.subscription_allows_access(business):
        return (
            "Tu cuenta está en modo consulta. Activa un plan desde la web y genera "
            "un código nuevo para conectar WhatsApp."
        )
    try:
        db.set_whatsapp_status(business_id, "conectado", phone=from_phone)
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
    business = db.get_business(business_id)
    if not db.subscription_allows_access(business):
        return {
            "business_id": business_id,
            "subscription_required": True,
            "reply": (
                "La cuenta de tu empresa está en modo consulta. El titular debe "
                "activar Noesis antes de vincular el equipo."
            ),
        }
    if not billing_adapter.has_entitlement(
        business, billing_adapter.ENTITLEMENT_TEAM
    ):
        return {
            "business_id": business_id,
            "subscription_required": True,
            "reply": (
                "El canal de equipo forma parte del plan Negocio. "
                "El titular puede activarlo desde Suscripción."
            ),
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
            "Escribe ENTRADA, PAUSA, REANUDAR o SALIDA."
        ),
    }


def _worker_plan_reply(worker: dict) -> str:
    """Parte operativo breve para el trabajador, sin datos financieros."""
    business_id = worker["business_id"]
    today = datetime.now().strftime("%Y-%m-%d")
    jobs = db.jobs_for_worker(worker["id"], business_id, day=today)
    tasks = db.project_tasks_for_worker(worker["id"], business_id)
    lines = [f"Tu parte de hoy, {worker['name']}:"]
    if jobs:
        lines.append("\nTrabajos:")
        for job in jobs[:8]:
            hour = (
                str(job.get("scheduled_for") or "")[11:16]
                if "T" in str(job.get("scheduled_for") or "") else "sin hora"
            )
            project = (
                f" · {job['project_name']}" if job.get("project_name") else ""
            )
            lines.append(
                f"• #{job['id']} · {hour} · {job.get('client_name') or 'Cliente'}"
                f"{project}: {job['description']}"
            )
    else:
        lines.append("\nNo tienes trabajos asignados hoy.")
    if tasks:
        lines.append("\nTareas pendientes:")
        for task in tasks[:8]:
            state = {
                "en_curso": "en curso", "bloqueada": "bloqueada"
            }.get(task["status"], "pendiente")
            lines.append(
                f"• T{task['id']} · {task['project_name']} · {state}: "
                f"{task['title']}"
            )
        lines.append("Responde HECHO Tn, EMPEZAR Tn o BLOQUEAR Tn.")
    else:
        lines.append("\nNo tienes tareas de proyecto pendientes.")
    if jobs:
        lines.append("Para fichar un trabajo: ENTRADA #n.")
    return "\n".join(lines)


def _try_worker_clock(from_phone: str, text: str) -> dict | None:
    """Fichaje y parte de campo por WhatsApp para una persona vinculada."""
    worker = db.get_worker_by_phone(from_phone)
    if not worker:
        return None
    business = db.get_business(worker["business_id"])
    if not db.subscription_allows_access(business):
        return {
            "business_id": worker["business_id"],
            "worker_id": worker["id"],
            "reply": (
                "La cuenta está en modo consulta. El titular debe activar Noesis "
                "antes de fichar o actualizar trabajos."
            ),
            "clocked": False,
            "subscription_required": True,
        }
    if not billing_adapter.has_entitlement(
        business, billing_adapter.ENTITLEMENT_TEAM
    ):
        return {
            "business_id": worker["business_id"],
            "worker_id": worker["id"],
            "reply": (
                "El canal de equipo no está incluido en el plan actual. "
                "El titular puede activarlo desde Suscripción."
            ),
            "clocked": False,
            "subscription_required": True,
        }
    normalized = (text or "").strip().lower().replace("#", "")
    if normalized in {"hoy", "mis trabajos", "trabajos", "mis tareas", "tareas"}:
        return {
            "business_id": worker["business_id"],
            "worker_id": worker["id"],
            "reply": _worker_plan_reply(worker),
            "clocked": False,
            "plan": True,
        }

    if normalized in {"ayuda", "comandos", "help"}:
        return {
            "business_id": worker["business_id"],
            "worker_id": worker["id"],
            "reply": (
                "Puedes escribir: HOY; ENTRADA #n, PAUSA, REANUDAR o SALIDA; "
                "HECHO Tn; COSTE #n 25,40 material; DUDA #n texto; "
                "BLOQUEO #n texto; o enviar una foto/PDF con #n en el comentario. "
                "Los costes y documentos quedan pendientes de revisión: no cambian "
                "las cuentas sin confirmación del titular."
            ),
            "clocked": False,
        }

    cost_match = re.fullmatch(
        r"coste\s+(?:(?:trabajo\s*)?(\d+)\s+)?"
        r"(\d+(?:[\.,]\d{1,2})?)\s*(?:€|eur)?\s+(.+)",
        normalized,
    )
    if cost_match:
        explicit_job = int(cost_match.group(1)) if cost_match.group(1) else None
        open_shift = db.worker_open_shift(worker["id"], worker["business_id"])
        job_id = explicit_job or (open_shift or {}).get("job_id")
        try:
            submission = db.create_worker_submission(
                worker["business_id"], worker["id"], kind="cost",
                job_id=job_id,
                amount=float(cost_match.group(2).replace(",", ".")),
                description=cost_match.group(3).strip(),
            )
        except ValueError as exc:
            reply = str(exc)
            submission = None
        else:
            reply = (
                f"Coste #{submission['id']} recibido para el trabajo "
                f"#{submission['job_id']}: {_eur(submission['amount'])}. "
                "Queda pendiente de revisión; todavía no afecta al margen ni a "
                "la contabilidad."
            )
        return {
            "business_id": worker["business_id"], "worker_id": worker["id"],
            "reply": reply, "clocked": False,
            "submission_id": submission["id"] if submission else None,
        }

    question_match = re.fullmatch(
        r"(duda|pregunta|bloqueo|nota)\s+"
        r"(?:(?:trabajo\s*)?(\d+)\s+)?(.+)", normalized,
    )
    if question_match:
        explicit_job = int(question_match.group(2)) if question_match.group(2) else None
        open_shift = db.worker_open_shift(worker["id"], worker["business_id"])
        job_id = explicit_job or (open_shift or {}).get("job_id")
        kind = {
            "duda": "question", "pregunta": "question",
            "bloqueo": "blocker", "nota": "note",
        }[question_match.group(1)]
        try:
            submission = db.create_worker_submission(
                worker["business_id"], worker["id"], kind=kind,
                job_id=job_id, description=question_match.group(3).strip(),
            )
        except ValueError as exc:
            reply = str(exc)
            submission = None
        else:
            reply = (
                "Lo he registrado y lo incluiré en el resumen del titular. "
                + ("Lo marcaré como bloqueo prioritario."
                   if kind == "blocker" else
                   "Solo le interrumpiré si requiere una decisión urgente.")
            )
        return {
            "business_id": worker["business_id"], "worker_id": worker["id"],
            "reply": reply, "clocked": False,
            "submission_id": submission["id"] if submission else None,
        }

    margin_match = re.fullmatch(r"margen(?:\s+(?:trabajo\s*)?(\d+))?", normalized)
    if margin_match:
        if not worker.get("can_view_assigned_budget"):
            reply = (
                "Tu perfil no muestra márgenes ni cifras globales del negocio. "
                "Puedes consultar tu trabajo, horas, tareas y costes enviados."
            )
        else:
            explicit_job = int(margin_match.group(1)) if margin_match.group(1) else None
            open_shift = db.worker_open_shift(worker["id"], worker["business_id"])
            job_id = explicit_job or (open_shift or {}).get("job_id")
            job = db.get_job(job_id, worker["business_id"]) if job_id else None
            if not job or not db.worker_can_access_job(
                job["id"], worker["id"], worker["business_id"]
            ):
                reply = "Indica un trabajo asignado: MARGEN #n."
            elif not job.get("project_id"):
                reply = "Ese trabajo no está dentro de un proyecto con presupuesto."
            else:
                project = db.get_project(job["project_id"], worker["business_id"])
                reply = (
                    f"Proyecto {project['name']}: presupuesto {_eur(project['budget'])}; "
                    f"coste registrado {_eur(project['actual_cost'])}; "
                    f"disponible {_eur(max(0, project['margin']))}. "
                    "Es una referencia operativa, no el resultado global del negocio."
                )
        return {
            "business_id": worker["business_id"], "worker_id": worker["id"],
            "reply": reply, "clocked": False,
        }

    task_match = re.fullmatch(
        r"(?:hecho|hecha|empezar|bloquear|bloqueada)\s+t?\s*(\d+)",
        normalized,
    )
    if task_match:
        verb = normalized.split()[0]
        status = {
            "hecho": "hecha", "hecha": "hecha", "empezar": "en_curso",
            "bloquear": "bloqueada", "bloqueada": "bloqueada",
        }[verb]
        try:
            task = db.update_project_task(
                int(task_match.group(1)),
                business_id=worker["business_id"],
                status=status,
                actor_worker_id=worker["id"],
            )
        except ValueError as exc:
            reply = str(exc)
            task = None
        else:
            reply = (
                f"Tarea T{task['id']} actualizada a "
                f"{task['status'].replace('_', ' ')}: {task['title']}."
                if task else "Esa tarea no es tuya o ya no existe."
            )
        return {
            "business_id": worker["business_id"],
            "worker_id": worker["id"],
            "reply": reply,
            "clocked": False,
            "task_updated": bool(task),
        }

    clock_match = re.fullmatch(
        r"(entrada|salida|pausa|reanudar)(?:\s+(?:trabajo\s*)?(\d+))?",
        normalized,
    )
    if clock_match:
        action = clock_match.group(1)
        job_id = int(clock_match.group(2)) if clock_match.group(2) else None
        try:
            clockin = db.clock_worker(
                worker["business_id"], worker["id"], action, "whatsapp",
                job_id=job_id,
            )
        except ValueError as exc:
            return {
                "business_id": worker["business_id"],
                "worker_id": worker["id"],
                "reply": str(exc),
                "clocked": False,
            }
        hour = str(clockin["at"])[11:16]
        linked = (
            f" en el trabajo #{clockin['job_id']}"
            if clockin.get("job_id") else ""
        )
        return {
            "business_id": worker["business_id"],
            "worker_id": worker["id"],
            "reply": f"{action.capitalize()} registrada a las {hour}{linked}.",
            "clocked": True,
        }

    if db.get_business_by_phone(from_phone):
        return None
    return {
        "business_id": worker["business_id"],
        "worker_id": worker["id"],
        "reply": (
            "Escribe HOY para ver tu parte; ENTRADA, PAUSA, REANUDAR o SALIDA "
            "para fichar; y HECHO Tn para cerrar una tarea."
        ),
        "clocked": False,
    }


# ------------------------------------------------------------------- Entrantes --
def _extract_messages(payload: dict) -> list[dict]:
    """Extrae mensajes de Meta y admite un formato simple para pruebas."""
    out: list[dict] = []
    if not isinstance(payload, dict):
        return out
    if payload.get("from") and (
        payload.get("text") is not None
        or payload.get("audio_id")
        or payload.get("image_id")
        or payload.get("media_document_id")
    ):
        return [{
            "id": str(payload.get("id") or ""),
            "phone": str(payload["from"]),
            "text": str(payload.get("text") or ""),
            "audio_id": payload.get("audio_id"),
            "image_id": payload.get("image_id"),
            "image_mime": payload.get("image_mime"),
            "media_document_id": payload.get("media_document_id"),
            "media_document_mime": payload.get("media_document_mime"),
            "media_document_filename": payload.get("media_document_filename"),
            "caption": str(payload.get("caption") or ""),
            "recipient_phone_id": str(payload.get("recipient_phone_id") or ""),
            "recipient_display_phone": str(
                payload.get("recipient_display_phone") or ""
            ),
            "waba_id": str(payload.get("waba_id") or ""),
            "profile_name": str(payload.get("profile_name") or ""),
            "message_type": str(payload.get("message_type") or (
                "audio" if payload.get("audio_id") else
                "image" if payload.get("image_id") else
                "document" if payload.get("media_document_id") else "text"
            )),
        }]
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            metadata = value.get("metadata", {}) or {}
            profiles = {
                str(contact.get("wa_id") or ""): str(
                    (contact.get("profile", {}) or {}).get("name") or ""
                )
                for contact in (value.get("contacts", []) or [])
            }
            for message in value.get("messages", []) or []:
                phone = message.get("from", "")
                if not phone:
                    continue
                image = message.get("image", {}) or {}
                document = message.get("document", {}) or {}
                message_type = str(message.get("type") or "unknown")
                interactive = message.get("interactive", {}) or {}
                interactive_text = (
                    (interactive.get("button_reply", {}) or {}).get("title")
                    or (interactive.get("list_reply", {}) or {}).get("title")
                    or ""
                )
                out.append({
                    "id": str(message.get("id") or ""),
                    "phone": phone,
                    "text": (
                        (message.get("text", {}) or {}).get("body", "")
                        or interactive_text
                    ),
                    "audio_id": (message.get("audio", {}) or {}).get("id"),
                    "image_id": image.get("id"),
                    "image_mime": image.get("mime_type"),
                    "media_document_id": document.get("id"),
                    "media_document_mime": document.get("mime_type"),
                    "media_document_filename": document.get("filename"),
                    "caption": str(
                        image.get("caption") or document.get("caption") or ""
                    ),
                    "recipient_phone_id": str(
                        metadata.get("phone_number_id") or ""
                    ),
                    "recipient_display_phone": str(
                        metadata.get("display_phone_number") or ""
                    ),
                    "waba_id": str(entry.get("id") or ""),
                    "profile_name": profiles.get(str(phone), ""),
                    "message_type": message_type,
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
        event = db.webhook_event("whatsapp_status", event_key) or {}
        if event.get("status") == "processing":
            raise WebhookInProgress(event_key)
        return {"id": message_id, "status": delivery_status, "duplicate": True}
    try:
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
    except Exception as exc:
        db.fail_webhook_event("whatsapp_status", event_key, str(exc))
        raise
    db.complete_webhook_event("whatsapp_status", event_key)
    return {
        "id": message_id,
        "status": delivery_status,
        "updated": bool(updated),
    }


def _trusted_meta_media_url(value: str) -> bool:
    parsed = urllib.parse.urlsplit(value)
    hostname = (parsed.hostname or "").lower()
    trusted_host = any(
        hostname == suffix or hostname.endswith(f".{suffix}")
        for suffix in ("facebook.com", "fbsbx.com", "fbcdn.net")
    )
    return bool(
        parsed.scheme == "https" and trusted_host
        and parsed.username is None and parsed.password is None
    )


class _TrustedMetaRedirect(urllib.request.HTTPRedirectHandler):
    """Nunca sigue un redirect que pueda filtrar el bearer o provocar SSRF."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _trusted_meta_media_url(newurl):
            raise urllib.error.URLError("redirect de media no autorizado")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _download_media(media_id: str, max_bytes: int | None = None) -> bytes | None:
    """Descarga un mèdia de WhatsApp (audio/imagen/PDF) acotado en tamaño."""
    if not _TOKEN or not re.fullmatch(r"[0-9]{1,32}", str(media_id or "")):
        return None
    limit = max_bytes or config.MAX_AUDIO_BYTES
    try:
        opener = urllib.request.build_opener(_TrustedMetaRedirect())
        metadata_request = urllib.request.Request(
            f"https://graph.facebook.com/{config.META_GRAPH_VERSION}/{media_id}",
            headers={"Authorization": f"Bearer {_TOKEN}"},
        )
        metadata_raw = opener.open(metadata_request, timeout=10).read(65_537)
        if len(metadata_raw) > 65_536:
            raise ValueError("respuesta de metadatos demasiado grande")
        info = json.loads(metadata_raw)
        media_url = str(info.get("url") or "")
        if not _trusted_meta_media_url(media_url):
            raise ValueError("Meta devolvió una URL de media no autorizada")
        media_request = urllib.request.Request(
            media_url, headers={"Authorization": f"Bearer {_TOKEN}"}
        )
        data = opener.open(media_request, timeout=20).read(limit + 1)
        return data if len(data) <= limit else None
    except Exception as exc:  # noqa: BLE001
        log.warning("Fallo descargando mèdia %s: %s", media_id, exc)
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


# ------------------------------------- Confirmaciones y mèdia entrante --
_YES_WORDS = {"si", "sí", "ok", "vale", "d'acord", "dacord", "confirmo", "confirmar", "yes", "s", "va"}
_NO_WORDS = {"no", "cancela", "cancelar", "anula", "anular", "n"}
_MONEY_HINTS = ("factur", "gasto", "gastos", "cobr", "pagad", "presupuesto",
                "borra", "elimina", "anula")


def _normalized_word(text: str) -> str:
    return (text or "").strip().strip("!.¡¿?,;").lower()


def _is_yes(text: str) -> bool:
    return _normalized_word(text) in _YES_WORDS


def _is_no(text: str) -> bool:
    return _normalized_word(text) in _NO_WORDS


def _needs_confirmation(text: str) -> bool:
    """Una orden hablada que mueve dinero se confirma antes de ejecutarse."""
    lowered = (text or "").lower()
    return any(hint in lowered for hint in _MONEY_HINTS)


def _prepare_invoice_action(business: dict, phone: str, text: str) -> str | None:
    """Convierte una orden de emisión/entrega en una confirmación verificable."""
    match = re.search(
        r"\b(?:emitir|emite|emetre|emet|envia|enviar)"
        r"(?:\s+(?:y|i)\s+(?:emitir|emite|emetre|emet|envia|enviar))?\s+"
        r"(?:la\s+)?(?:factura|ticket|tiquet)\s+(.+?)\s*$",
        (text or "").strip(), re.I,
    )
    if not match:
        return None
    reference = match.group(1).strip()
    invoice = db.find_invoice_reference(reference, business["id"])
    if not invoice:
        return (
            f"No encuentro la factura «{reference}» en este negocio. "
            "Usa el número de borrador que te mostré, por ejemplo: "
            "«emitir factura 12»."
        )
    deliver = "envi" in (text or "").lower()
    client = db.get_client(invoice["client_id"], business["id"]) or {}
    if invoice.get("status") == "borrador":
        required = [
            (business.get("name"), "nombre fiscal del negocio"),
            (business.get("nif"), "NIF del negocio"),
            (business.get("address"), "domicilio fiscal del negocio"),
            (client.get("name"), "nombre del cliente"),
        ]
        if invoice.get("invoice_type") != "F2":
            required.extend((
                (client.get("nif"), "NIF del cliente"),
                (client.get("address"), "domicilio del cliente"),
            ))
        missing = [label for value, label in required if not str(value or "").strip()]
        if missing:
            return (
                f"El borrador #{invoice['id']} aún no se puede emitir legalmente. "
                "Falta: " + ", ".join(missing) + ". Completa esos datos y vuelve "
                "a pedírmelo; no he cambiado la factura."
            )
    if deliver and not (
        str(client.get("email") or "").strip()
        or recipient_phone(client.get("phone"))
    ):
        return (
            f"Puedo emitir el borrador #{invoice['id']}, pero no entregarlo: "
            f"{client.get('name') or 'el cliente'} no tiene correo ni WhatsApp "
            "válido. Añade un contacto o escribe solo «emitir factura "
            f"{invoice['id']}»."
        )
    if invoice.get("status") != "borrador" and not deliver:
        return (
            f"La factura {invoice.get('number') or invoice['id']} ya está emitida. "
            f"Escribe «enviar factura {invoice.get('number') or invoice['id']}» "
            "si quieres entregarla al cliente."
        )
    db.set_pending_action(
        business["id"], phone, "emitir_factura",
        {"invoice_id": invoice["id"], "deliver": deliver},
    )
    action = "emitir y entregar" if deliver else "emitir"
    recipient = f" a {client.get('name')}" if deliver else ""
    return (
        f"Voy a {action} el borrador #{invoice['id']}{recipient} por "
        f"{_eur(invoice['total'])}. Al emitirlo tendrá número definitivo, el PDF "
        "quedará generado y sus cifras pasarán a ingresos, impuestos, cliente y "
        "gestoría. ¿Confirmas? Responde SÍ o NO."
    )


def _eur(number) -> str:
    return (
        f"{(number or 0):,.2f} €"
        .replace(",", "X").replace(".", ",").replace("X", ".")
    )


def _extraction_budget_ok(business_id: int) -> bool:
    """Tope diario de extracciones IA por negocio para proteger el margen."""
    today = datetime.now().strftime("%Y-%m-%d")
    used = db.count_product_events(business_id, "media_ingested", since=today)
    return used < config.MAX_DAILY_EXTRACTIONS


def _execute_pending(business: dict, phone: str, pending: dict) -> str:
    """Ejecuta el borrador confirmado y devuelve la respuesta para el usuario."""
    try:
        payload = json.loads(pending["payload"])
    except (TypeError, ValueError):
        db.clear_pending_action(business["id"], phone)
        return "No he podido recuperar el borrador. Vuelve a enviármelo."
    kind = pending["kind"]
    if kind != "send_communication":
        db.clear_pending_action(business["id"], phone)
    if kind == "gasto":
        try:
            expense = db.add_expense(
                payload.get("concept") or "Gasto por foto",
                payload.get("amount"),
                vat_rate=payload.get("vat_rate"),
                category="Ticket",
                spent_on=payload.get("date"),
                document_id=payload.get("document_id"),
                business_id=business["id"],
            )
        except ValueError as exc:
            return f"No he podido apuntar el gasto: {exc}"
        return (
            f"Apuntado ✅ Gasto de {_eur(expense['amount'])}"
            f" ({expense['concept']}). El justificante queda guardado"
            " en tus papeles."
        )
    if kind == "factura_recibida":
        from ..documents import service as docservice
        try:
            received = docservice.confirm_received_invoice(
                business["id"], int(payload.get("document_id")),
                total=payload.get("total"),
                supplier_name=payload.get("supplier"),
                supplier_nif=payload.get("supplier_nif"),
                number=payload.get("number"),
                issued_on=payload.get("issued_on"),
                due_on=payload.get("due_on"),
                base=payload.get("base"),
                vat_rate=payload.get("vat_rate"),
                vat_amount=payload.get("vat_amount"),
                irpf_amount=payload.get("irpf_amount"),
                concept=payload.get("concept") or "Factura recibida por WhatsApp",
            )
        except (ValueError, TypeError, docservice.UploadError) as exc:
            return f"No he podido registrar la factura: {exc}"
        return (
            f"Hecho ✅ Factura recibida de "
            f"{payload.get('supplier') or 'proveedor'} por {_eur(received['total'])}. "
            "El original y tu confirmación quedan guardados."
        )
    if kind == "emitir_factura":
        from .. import tools
        invoice_id = int(payload.get("invoice_id"))
        invoice = db.get_invoice(invoice_id, business["id"])
        if not invoice:
            return "No encuentro ese borrador. No he emitido ni enviado nada."
        if invoice.get("status") == "borrador":
            result = json.loads(tools.run_tool(
                "enviar_factura", {"factura_id": invoice_id}, business["id"]
            ))
            if not result.get("ok"):
                return result.get("error") or "No he podido emitir la factura."
        try:
            delivery = tools.prepare_invoice_delivery(
                business["id"], invoice_id,
                channel="auto" if payload.get("deliver") else "none",
            )
        except ValueError as exc:
            return f"La factura está emitida, pero no he podido preparar la entrega: {exc}"
        invoice = delivery["factura"]
        if delivery["queued"]:
            return (
                f"Hecho ✅ Factura {invoice['number']} emitida. PDF generado y "
                f"entrega preparada por {delivery['channel']} a "
                f"{delivery['target']}. Ya cuenta en tus números y en gestoría."
            )
        return (
            f"Hecho ✅ Factura {invoice['number']} emitida y PDF preparado. "
            f"Puedes revisarlo aquí iniciando sesión: {delivery['owner_pdf_url']}"
        )
    if kind == "chat_action":
        return chat.handle(
            business["id"], str(payload.get("text") or ""), channel="whatsapp"
        ).get("reply", "")
    if kind == "reclamar":
        return _execute_collection(business, payload)
    if kind == "send_communication":
        from .. import internal_brain
        result = internal_brain.deliver_confirmed(business["id"], payload)
        if not result.startswith("No he podido entregarlo"):
            db.clear_pending_action(business["id"], phone)
        return result
    return "Ese borrador ya no es válido. Vuelve a enviármelo."


def _execute_collection(business: dict, payload: dict) -> str:
    """El dueño ha dicho SÍ: manda el recordatorio de cobro al cliente."""
    invoice = db.get_invoice(payload.get("invoice_id"), business["id"])
    if not invoice or invoice.get("status") == "cobrada":
        return "Esa factura ya está cobrada o no existe. Nada que reclamar 👌"
    client = (
        db.get_client(invoice.get("client_id"), business["id"])
        if invoice.get("client_id") else None
    )
    if not client:
        return (
            "No encuentro al cliente de esa factura. "
            "Reclámala desde la web (Cobros)."
        )
    token = db.get_or_create_portal_token(business["id"], client["id"])
    portal_url = f"{config.BASE_URL}/p/{token}" if token else config.BASE_URL
    client_phone = recipient_phone(client.get("phone"))
    if not client_phone:
        return (
            f"{client.get('name') or 'El cliente'} no tiene teléfono "
            f"guardado. Este es su enlace de pago para enviárselo tú: "
            f"{portal_url}"
        )
    number = invoice.get("number") or str(invoice["id"])
    amount = _eur(invoice.get("remaining_amount") or invoice.get("total"))
    day = datetime.now().strftime("%Y-%m-%d")
    try:
        queue_payment_reminder(
            client_phone,
            client.get("name") or "cliente",
            business.get("name") or "Tu proveedor",
            number,
            amount,
            portal_url,
            business_id=business["id"],
            idempotency_key=(
                f"collect-confirmed:{business['id']}:{invoice['id']}:{day}"
            ),
        )
    except (db.DatabaseError, ValueError) as exc:
        log.exception("No se pudo encolar el recordatorio confirmado.")
        return f"No he podido enviarlo ({exc}). Inténtalo desde la web."
    db.mark_reminder_sent(invoice["id"], business["id"])
    db.record_product_event(
        business["id"], "collection_confirmed",
        json.dumps({"invoice_id": invoice["id"]}, separators=(",", ":")),
    )
    return (
        f"Hecho ✅ Le he enviado a {client.get('name') or 'tu cliente'} el "
        f"recordatorio de la factura {number} ({amount}) con su enlace de pago."
    )


def _ingest_image(business: dict, phone: str, message: dict) -> dict:
    """Foto entrante → clasificación única + borrador confirmable."""
    from ..adapters import extraction
    from ..documents import service as docservice

    max_bytes = config.MAX_UPLOAD_MB * 1024 * 1024
    data = _download_media(message["image_id"], max_bytes=max_bytes)
    if not data:
        send(
            phone,
            "No he podido descargar la foto (¿demasiado grande?). "
            f"El límite es {config.MAX_UPLOAD_MB} MB.",
            business_id=business["id"],
        )
        return {"phone": phone, "media": "image", "ingested": False}
    mime = message.get("image_mime") or "image/jpeg"
    ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(
        mime
    )
    if not ext:
        send(
            phone,
            "Solo puedo leer fotos JPG, PNG o WEBP.",
            business_id=business["id"],
        )
        return {"phone": phone, "media": "image", "ingested": False}
    try:
        document = docservice.upload(
            business["id"],
            f"whatsapp-documento{ext}",
            data,
            kind="documento",
            note="Recibido por WhatsApp",
            run_ocr=True,
            auto_classify=True,
        )
    except docservice.UploadError as exc:
        send(phone, str(exc), business_id=business["id"])
        return {"phone": phone, "media": "image", "ingested": False}

    classification = document.get("classification") or {}
    context = docservice.associate_context(
        business["id"], document["id"], message.get("caption")
    )
    context_note = (
        f" Lo he asociado a {context['label']}." if context.get("matched")
        else " Hay varias coincidencias: revisa el cliente o proyecto en Documentos."
        if context.get("ambiguous") else ""
    )
    detected_kind = classification.get("kind") or document.get("kind") or "documento"
    if detected_kind in {"factura_recibida", "factura_emitida"}:
        draft = docservice.invoice_draft(business["id"], document["id"])
        if draft and draft.get("direction") == "emitida":
            context = docservice.associate_context(
                business["id"], document["id"], message.get("caption"),
                customer=draft.get("customer"),
                customer_nif=draft.get("customer_nif"),
            )
            if context.get("matched"):
                context_note = f" Lo he asociado a {context['label']}."
        if detected_kind == "factura_recibida" and draft and draft.get("total"):
            payload = {**draft, "document_id": document["id"]}
            db.set_pending_action(business["id"], phone, "factura_recibida", payload)
            send(
                phone,
                f"📄 Parece una factura recibida de "
                f"{draft.get('supplier') or 'un proveedor'} por {_eur(draft['total'])}. "
                "¿La guardo como factura de proveedor? Responde SÍ o NO."
                + context_note,
                business_id=business["id"],
            )
            return {"phone": phone, "media": "image", "ingested": True,
                    "pending": True, "document_id": document["id"],
                    "classification": detected_kind}
        send(
            phone,
            "He guardado la foto. Parece una factura emitida por ti, así que no "
            "la reemitiré ni la meteré en Veri*Factu. Revísala en Documentos para "
            "confirmar que es histórica." + context_note,
            business_id=business["id"],
        )
        return {"phone": phone, "media": "image", "ingested": True,
                "pending": False, "document_id": document["id"],
                "classification": detected_kind}

    if detected_kind in {"contrato", "presupuesto", "albaran", "proveedor"}:
        labels = {"contrato": "un contrato", "presupuesto": "un presupuesto",
                  "albaran": "un albarán", "proveedor": "un documento de proveedor"}
        send(
            phone,
            f"📎 Guardado. Parece {labels[detected_kind]}. Lo he dejado pendiente "
            "de tu confirmación en Documentos." + context_note,
            business_id=business["id"],
        )
        return {"phone": phone, "media": "image", "ingested": True,
                "pending": False, "document_id": document["id"],
                "classification": detected_kind}

    fields = None
    if _extraction_budget_ok(business["id"]):
        fields = extraction.extract_expense(
            data, mime,
            allow_external=db.integration_enabled(
                business["id"], "ai_external",
                available=bool(config.ANTHROPIC_API_KEY),
            ),
        )
    db.record_product_event(
        business["id"], "media_ingested",
        json.dumps({"type": "image", "extracted": bool(fields),
                    "classification": detected_kind},
                   separators=(",", ":")),
    )
    if fields and fields.get("amount"):
        payload = {**fields, "document_id": document["id"]}
        db.set_pending_action(business["id"], phone, "gasto", payload)
        concept = fields.get("concept") or fields.get("supplier") or "ticket"
        detail = f"📄 He leído el ticket: {concept} — {_eur(fields['amount'])}"
        if fields.get("vat_rate") is not None:
            detail += f" (IVA {fields['vat_rate']} %)"
        if fields.get("date"):
            detail += f", del {fields['date']}"
        send(
            phone,
            detail + ". ¿Lo apunto como gasto? Responde SÍ o NO." + context_note,
            business_id=business["id"],
        )
        return {
            "phone": phone, "media": "image", "ingested": True,
            "pending": True, "document_id": document["id"],
        }
    send(
        phone,
        "He guardado la foto en tus papeles, pero no he podido leer el "
        "importe. Dímelo en un mensaje (ej.: «gasto 25,50 ferretería») o "
        "complétalo desde la web." + context_note,
        business_id=business["id"],
    )
    return {
        "phone": phone, "media": "image", "ingested": True,
        "pending": False, "document_id": document["id"],
    }


def _ingest_document(business: dict, phone: str, message: dict) -> dict:
    """PDF entrante → clasificación y, si procede, factura recibida confirmable."""
    from ..documents import service as docservice

    mime = message.get("media_document_mime") or ""
    filename = message.get("media_document_filename") or "documento.pdf"
    if mime != "application/pdf" and not filename.lower().endswith(".pdf"):
        send(
            phone,
            "Por ahora solo acepto documentos en PDF (o fotos del ticket).",
            business_id=business["id"],
        )
        return {"phone": phone, "media": "document", "ingested": False}
    max_bytes = config.MAX_UPLOAD_MB * 1024 * 1024
    data = _download_media(message["media_document_id"], max_bytes=max_bytes)
    if not data:
        send(
            phone,
            "No he podido descargar el documento (¿demasiado grande?). "
            f"El límite es {config.MAX_UPLOAD_MB} MB.",
            business_id=business["id"],
        )
        return {"phone": phone, "media": "document", "ingested": False}
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    try:
        document = docservice.upload(
            business["id"], filename, data,
            kind="documento", note="Recibido por WhatsApp", run_ocr=True,
            auto_classify=True,
        )
    except docservice.UploadError as exc:
        send(phone, str(exc), business_id=business["id"])
        return {"phone": phone, "media": "document", "ingested": False}
    classification = document.get("classification") or {}
    context = docservice.associate_context(
        business["id"], document["id"], message.get("caption")
    )
    context_note = (
        f" Lo he asociado a {context['label']}." if context.get("matched")
        else " Hay varias coincidencias: revisa el cliente o proyecto en Documentos."
        if context.get("ambiguous") else ""
    )
    kind = classification.get("kind") or "documento"
    if kind == "factura_recibida":
        draft = docservice.invoice_draft(business["id"], document["id"])
        if draft and draft.get("total"):
            db.set_pending_action(
                business["id"], phone, "factura_recibida",
                {**draft, "document_id": document["id"]},
            )
            send(
                phone,
                f"📄 He leído «{filename}»: parece una factura recibida de "
                f"{draft.get('supplier') or 'un proveedor'} por {_eur(draft['total'])}. "
                "¿La registro? Responde SÍ o NO." + context_note,
                business_id=business["id"],
            )
            return {"phone": phone, "media": "document", "ingested": True,
                    "pending": True, "document_id": document["id"],
                    "classification": kind}
    labels = {"factura_emitida": "factura emitida histórica", "presupuesto": "presupuesto",
              "contrato": "contrato", "albaran": "albarán", "proveedor": "documento de proveedor"}
    reading = labels.get(kind)
    send(
        phone,
        f"📎 Guardado «{filename}» en tus papeles. "
        + (f"Parece {reading}; confírmalo en Documentos." if reading
           else "No estoy segura del tipo; te lo he dejado pendiente para revisar.")
        + context_note,
        business_id=business["id"],
    )
    return {
        "phone": phone, "media": "document", "ingested": True,
        "document_id": document["id"], "classification": kind,
    }


def _message_job_id(message: dict) -> int | None:
    match = re.search(
        r"(?:#|trabajo\s+)(\d+)\b",
        str(message.get("caption") or message.get("text") or ""),
        re.I,
    )
    return int(match.group(1)) if match else None


def _ingest_worker_media(worker: dict, phone: str, message: dict) -> dict:
    """Guarda un justificante de campo sin convertirlo todavía en gasto."""
    from ..adapters import extraction
    from ..documents import repo as document_repo
    from ..documents import service as docservice

    business_id = worker["business_id"]
    business = db.get_business(business_id)
    if (
        not db.subscription_allows_access(business)
        or not billing_adapter.has_entitlement(
            business, billing_adapter.ENTITLEMENT_TEAM
        )
    ):
        send(
            phone,
            "El canal de equipo no está disponible en el plan actual. "
            "No he guardado el archivo.",
            business_id=None,
        )
        return {
            "phone": phone, "worker_id": worker["id"], "ingested": False,
            "subscription_required": True,
        }
    job_id = _message_job_id(message)
    if job_id is None:
        job_id = (db.worker_open_shift(worker["id"], business_id) or {}).get("job_id")
    if not job_id or not db.worker_can_access_job(job_id, worker["id"], business_id):
        send(
            phone,
            "Indica el trabajo en el comentario, por ejemplo #24. "
            "No guardaré el documento en un expediente equivocado.",
            business_id=business_id,
        )
        return {"phone": phone, "worker_id": worker["id"], "ingested": False}
    job = db.get_job(job_id, business_id)
    if message.get("image_id"):
        media_id = message["image_id"]
        mime = message.get("image_mime") or "image/jpeg"
        extension = {
            "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
        }.get(mime)
        if not extension:
            send(phone, "Solo acepto JPG, PNG, WEBP o PDF.", business_id=business_id)
            return {"phone": phone, "worker_id": worker["id"], "ingested": False}
        filename = f"equipo-trabajo-{job_id}{extension}"
    else:
        media_id = message.get("media_document_id")
        mime = message.get("media_document_mime") or "application/pdf"
        filename = message.get("media_document_filename") or f"trabajo-{job_id}.pdf"
        if mime != "application/pdf" and not filename.lower().endswith(".pdf"):
            send(phone, "Por ahora los documentos deben ser PDF.", business_id=business_id)
            return {"phone": phone, "worker_id": worker["id"], "ingested": False}
    data = _download_media(media_id, max_bytes=config.MAX_UPLOAD_MB * 1024 * 1024)
    if not data:
        send(phone, "No he podido descargar el archivo. Vuelve a enviarlo.",
             business_id=business_id)
        return {"phone": phone, "worker_id": worker["id"], "ingested": False}
    try:
        document = docservice.upload(
            business_id, filename, data, kind="documento",
            note=f"Aportado por {worker['name']} para trabajo #{job_id}",
            run_ocr=True, auto_classify=True,
        )
        document = document_repo.set_context(
            document["id"], business_id, client_id=job.get("client_id"),
            project_id=job.get("project_id"),
        ) or document
    except (docservice.UploadError, ValueError) as exc:
        send(phone, str(exc), business_id=business_id)
        return {"phone": phone, "worker_id": worker["id"], "ingested": False}

    amount = document.get("ocr_amount")
    if message.get("image_id") and not amount and worker.get("can_submit_costs"):
        fields = extraction.extract_expense(
            data, mime,
            allow_external=db.integration_enabled(
                business_id, "ai_external", available=bool(config.ANTHROPIC_API_KEY)
            ),
        )
        amount = (fields or {}).get("amount")
    kind = "cost" if amount and worker.get("can_submit_costs") else "document"
    submission = db.create_worker_submission(
        business_id, worker["id"], kind=kind, job_id=job_id,
        document_id=document["id"], amount=amount,
        description=(
            f"Justificante: {filename}"
            if kind == "document" else
            f"Coste detectado en {filename}"
        ),
    )
    amount_text = f" por {_eur(amount)}" if amount else ""
    send(
        phone,
        f"Documento guardado en el trabajo #{job_id}{amount_text}. "
        "Queda pendiente de revisión y no modifica las cuentas todavía.",
        business_id=business_id,
    )
    return {
        "phone": phone, "worker_id": worker["id"], "ingested": True,
        "document_id": document["id"], "submission_id": submission["id"],
    }


def _ingest_customer_media(
    business: dict, connection: dict, contact: dict, message: dict
) -> dict:
    """Archiva documentos de clientes externos dentro del negocio receptor."""
    from ..documents import repo as document_repo
    from ..documents import service as docservice

    business_id = business["id"]
    if message.get("image_id"):
        media_id = message["image_id"]
        mime = message.get("image_mime") or "image/jpeg"
        extension = {
            "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
        }.get(mime)
        if not extension:
            raise ValueError("El formato de imagen no es compatible.")
        filename = f"cliente-whatsapp{extension}"
    else:
        media_id = message.get("media_document_id")
        mime = message.get("media_document_mime") or "application/pdf"
        filename = message.get("media_document_filename") or "documento-cliente.pdf"
        if mime != "application/pdf" and not filename.lower().endswith(".pdf"):
            raise ValueError("El documento debe ser un PDF.")
    data = _download_media(media_id, max_bytes=config.MAX_UPLOAD_MB * 1024 * 1024)
    if not data:
        raise ValueError("No he podido descargar el archivo; vuelve a enviarlo.")
    document = docservice.upload(
        business_id, filename, data, kind="documento",
        note="Recibido de un cliente por el WhatsApp del negocio",
        run_ocr=True, auto_classify=True,
    )
    if contact.get("client_id"):
        document = document_repo.set_context(
            document["id"], business_id, client_id=contact["client_id"]
        ) or document
    return document


def _handle_business_customer_message(connection: dict, message: dict) -> dict:
    """Recepcionista segura: organiza, acusa recibo y escala sin revelar datos."""
    from ..documents.service import UploadError

    business_id = connection["business_id"]
    business = db.get_business(business_id)
    if not business or not db.subscription_allows_access(business):
        return {"business_id": business_id, "customer_channel": True, "paused": True}
    contact = db.ensure_whatsapp_customer_contact(
        connection["id"], business_id, message["phone"], message.get("profile_name")
    )
    conversation = db.get_or_create_whatsapp_conversation(
        connection["id"], contact["id"], business_id
    )
    text = str(message.get("text") or message.get("caption") or "").strip()
    inbox = db.record_whatsapp_inbox(
        business_id=business_id, connection_id=connection["id"],
        conversation_id=conversation["id"], contact_id=contact["id"],
        meta_message_id=message.get("id") or secrets.token_hex(12),
        sender_phone=message["phone"],
        message_type=message.get("message_type") or "unknown", text_body=text,
    )
    normalized = _normalized_word(text)
    if normalized in {"stop", "baja", "cancelar mensajes"}:
        db.set_whatsapp_contact_consent(contact["id"], business_id, "opted_out")
        db.update_whatsapp_conversation(
            conversation["id"], business_id, status="archived"
        )
        reply = "De acuerdo. No recibirás más respuestas automáticas por este canal."
        send(message["phone"], reply, business_id=business_id,
             connection_id=connection["id"])
        db.finish_whatsapp_inbox(inbox["id"], business_id)
        return {"business_id": business_id, "customer_channel": True,
                "contact_id": contact["id"], "opted_out": True}
    if contact.get("consent_status") in {"opted_out", "blocked"}:
        db.finish_whatsapp_inbox(inbox["id"], business_id, status="ignored")
        return {"business_id": business_id, "customer_channel": True,
                "contact_id": contact["id"], "ignored": True}

    document_id = None
    if message.get("image_id") or message.get("media_document_id"):
        try:
            document = _ingest_customer_media(business, connection, contact, message)
        except (UploadError, ValueError) as exc:
            db.finish_whatsapp_inbox(
                inbox["id"], business_id, status="failed", error=str(exc)
            )
            send(message["phone"], str(exc), business_id=business_id,
                 connection_id=connection["id"])
            return {"business_id": business_id, "customer_channel": True,
                    "contact_id": contact["id"], "ingested": False}
        document_id = document["id"]
        db.update_whatsapp_conversation(
            conversation["id"], business_id, status="waiting_owner",
            summary=f"Documento recibido: {document.get('filename') or 'archivo'}",
        )
        reply = (
            f"He recibido y archivado {document.get('filename') or 'el documento'} "
            f"para {business.get('name')}. El equipo lo revisará antes de usarlo."
        )
    else:
        urgent = bool(re.search(
            r"\b(urgente|fuga|aver[ií]a|sin luz|emergencia|peligro)\b", text, re.I
        ))
        db.update_whatsapp_conversation(
            conversation["id"], business_id,
            status="waiting_owner", human_handoff=urgent,
            summary=text or "Mensaje de cliente pendiente de revisar",
        )
        reply = (
            f"He registrado tu mensaje para {business.get('name')}. "
            + ("Lo he marcado como urgente para que lo revisen cuanto antes."
               if urgent else
               "Queda ordenado en su bandeja y te responderán desde este mismo número.")
        )
    send(message["phone"], reply, business_id=business_id,
         connection_id=connection["id"])
    db.finish_whatsapp_inbox(
        inbox["id"], business_id, document_id=document_id
    )
    return {
        "business_id": business_id, "customer_channel": True,
        "contact_id": contact["id"], "document_id": document_id,
    }


def _finish_inbound_message(
    message_id: str | None, claimed_ids: list[str]
) -> None:
    if not message_id:
        return
    db.complete_webhook_event("whatsapp", message_id)
    claimed_ids.remove(message_id)


def _handle_inbound(payload: dict, claimed_ids: list[str]) -> dict:
    """Procesa mensajes y estados de Meta de forma idempotente."""
    results = [_handle_status(status) for status in _extract_statuses(payload)]
    for message in _extract_messages(payload):
        message_id = message.get("id")
        if message_id and not db.claim_webhook_event("whatsapp", message_id):
            event = db.webhook_event("whatsapp", message_id) or {}
            if event.get("status") == "processing":
                raise WebhookInProgress(message_id)
            results.append({"id": message_id, "duplicate": True})
            continue
        if message_id:
            claimed_ids.append(message_id)
        phone = message["phone"]
        text = message["text"]
        audio_id = message.get("audio_id")
        recipient_id = str(message.get("recipient_phone_id") or "").strip()
        connection = None
        if recipient_id and recipient_id != str(_PHONE_ID or "").strip():
            connection = db.get_whatsapp_connection_by_phone_number_id(recipient_id)
            if not connection:
                results.append({
                    "phone": phone, "recipient_phone_id": recipient_id,
                    "ignored": True, "reason": "unknown_recipient",
                })
                _finish_inbound_message(message_id, claimed_ids)
                continue
            event_waba = str(message.get("waba_id") or "").strip()
            if event_waba and event_waba != str(connection.get("waba_id") or ""):
                results.append({
                    "phone": phone, "recipient_phone_id": recipient_id,
                    "ignored": True, "reason": "waba_mismatch",
                })
                _finish_inbound_message(message_id, claimed_ids)
                continue
            if not connection.get("receptionist_enabled"):
                results.append({
                    "phone": phone, "business_id": connection["business_id"],
                    "ignored": True, "reason": "receptionist_paused",
                })
                _finish_inbound_message(message_id, claimed_ids)
                continue

        if audio_id and not text:
            text = _audio_to_text(audio_id) or ""
            if not text:
                business = (
                    db.get_business(connection["business_id"])
                    if connection else db.get_business_by_phone(phone)
                )
                send(
                    phone,
                    "He recibido tu nota de voz pero no he podido transcribirla. "
                    "Escríbeme la orden en texto, por favor.",
                    business_id=business["id"] if business else None,
                    connection_id=connection["id"] if connection else None,
                )
                results.append({
                    "phone": phone, "audio": True, "transcribed": False,
                })
                _finish_inbound_message(message_id, claimed_ids)
                continue

        message["text"] = text
        if connection:
            results.append(_handle_business_customer_message(connection, message))
            _finish_inbound_message(message_id, claimed_ids)
            continue

        worker_link = _try_worker_link(phone, text)
        if worker_link is not None:
            send(
                phone,
                worker_link["reply"],
                business_id=(
                    None if worker_link.get("subscription_required")
                    else worker_link.get("business_id")
                ),
            )
            results.append({
                "phone": phone,
                "worker_id": worker_link.get("worker_id"),
                "worker_linked": bool(worker_link.get("worker_id")),
            })
            _finish_inbound_message(message_id, claimed_ids)
            continue

        linked = _try_link(phone, text)
        if linked is not None:
            business = db.get_business_by_phone(phone)
            send(
                phone, linked,
                business_id=business["id"] if business else None,
            )
            results.append({"phone": phone, "linked": bool(business)})
            _finish_inbound_message(message_id, claimed_ids)
            continue

        identity = db.central_whatsapp_identity(phone)
        if identity["ambiguous"]:
            send(
                phone,
                "Este teléfono tiene más de una identidad interna vinculada. "
                "Por seguridad no he ejecutado nada. El titular debe corregir la "
                "vinculación desde Equipo o Ajustes.",
            )
            results.append({
                "phone": phone, "ignored": True,
                "reason": "ambiguous_central_identity",
            })
            _finish_inbound_message(message_id, claimed_ids)
            continue

        worker = identity["worker"]
        if worker and (message.get("image_id") or message.get("media_document_id")):
            results.append(_ingest_worker_media(worker, phone, message))
            _finish_inbound_message(message_id, claimed_ids)
            continue

        worker_clock = _try_worker_clock(phone, text)
        if worker_clock is not None:
            send(
                phone,
                worker_clock["reply"],
                business_id=(
                    None if worker_clock.get("subscription_required")
                    else worker_clock["business_id"]
                ),
            )
            results.append({
                "phone": phone,
                "business_id": worker_clock["business_id"],
                "worker_id": worker_clock["worker_id"],
                "clocked": worker_clock["clocked"],
            })
            _finish_inbound_message(message_id, claimed_ids)
            continue

        business = identity["business"]
        if not business:
            send(
                phone,
                "Tu número no está dado de alta en Noesis. Regístrate en "
                "bynoesis.com y conecta tu WhatsApp para empezar.",
            )
            results.append({"phone": phone, "known": False})
            _finish_inbound_message(message_id, claimed_ids)
            continue

        if not db.subscription_allows_access(business):
            send(
                phone,
                "Tu cuenta está en modo consulta. Puedes ver tu panel en la web, "
                "pero necesitas activar un plan para pedirme acciones o enviar documentos.",
                business_id=None,
            )
            results.append({
                "phone": phone,
                "business_id": business["id"],
                "subscription_required": True,
            })
            _finish_inbound_message(message_id, claimed_ids)
            continue

        if message.get("image_id"):
            results.append(_ingest_image(business, phone, message))
            _finish_inbound_message(message_id, claimed_ids)
            continue
        if message.get("media_document_id"):
            results.append(_ingest_document(business, phone, message))
            _finish_inbound_message(message_id, claimed_ids)
            continue

        pending = db.get_pending_action(business["id"], phone)
        if pending and _is_yes(text):
            send(
                phone,
                _execute_pending(business, phone, pending),
                business_id=business["id"],
            )
            results.append({
                "phone": phone, "business_id": business["id"],
                "confirmed": True,
            })
            _finish_inbound_message(message_id, claimed_ids)
            continue
        if pending and _is_no(text):
            db.clear_pending_action(business["id"], phone)
            send(
                phone,
                "Descartado. No he apuntado nada.",
                business_id=business["id"],
            )
            results.append({
                "phone": phone, "business_id": business["id"],
                "confirmed": False,
            })
            _finish_inbound_message(message_id, claimed_ids)
            continue

        invoice_action = _prepare_invoice_action(business, phone, text)
        if invoice_action is not None:
            send(phone, invoice_action, business_id=business["id"])
            results.append({
                "phone": phone, "business_id": business["id"],
                "invoice_action": True,
                "pending": bool(db.get_pending_action(business["id"], phone)),
            })
            _finish_inbound_message(message_id, claimed_ids)
            continue

        if audio_id and text and _needs_confirmation(text):
            # Una nota de voz que mueve dinero nunca se ejecuta sin confirmar.
            db.set_pending_action(
                business["id"], phone, "chat_action", {"text": text}
            )
            send(
                phone,
                f"🎤 Te he entendido: «{text}». ¿Lo hago? Responde SÍ o NO.",
                business_id=business["id"],
            )
            results.append({
                "phone": phone, "business_id": business["id"],
                "voice": True, "pending": True,
            })
            _finish_inbound_message(message_id, claimed_ids)
            continue

        reply = chat.handle(
            business["id"], text, channel="whatsapp", actor_phone=phone
        ).get("reply", "")
        send(phone, reply, business_id=business["id"])
        results.append({
            "phone": phone,
            "business_id": business["id"],
            "voice": bool(audio_id),
        })
        _finish_inbound_message(message_id, claimed_ids)
    return {"processed": len(results), "results": results}


def handle_inbound(payload: dict) -> dict:
    """Procesa y confirma eventos solo cuando todos sus efectos han terminado."""
    claimed_ids: list[str] = []
    try:
        result = _handle_inbound(payload, claimed_ids)
    except Exception as exc:
        for message_id in claimed_ids:
            db.fail_webhook_event("whatsapp", message_id, str(exc))
        raise
    for message_id in claimed_ids:
        db.complete_webhook_event("whatsapp", message_id)
    return result


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


def _post_to_meta(payload: dict, phone_number_id: str | None = None) -> str:
    """Realiza un intento y devuelve el wamid asignado por Meta."""
    target_phone_id = str(phone_number_id or _PHONE_ID).strip()
    if not (_TOKEN and target_phone_id):
        raise RuntimeError("WhatsApp Cloud API no está configurada.")
    url = (
        f"https://graph.facebook.com/{config.META_GRAPH_VERSION}/"
        f"{target_phone_id}/messages"
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
        message = f"Meta respondió {exc.code}: {detail}"
        # 408 y 429 sí merecen otra oportunidad; el resto de los 4xx, no.
        if 400 <= exc.code < 500 and exc.code not in (408, 429):
            raise MetaRejected(message) from exc
        raise RuntimeError(message) from exc
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
        business_id = message.get("business_id")
        if business_id:
            business = db.get_business(business_id)
            if not db.subscription_allows_access(business):
                reason = "Envío cancelado: la cuenta está en modo consulta."
                db.mark_whatsapp_blocked(message["id"], reason, now_text)
                processed.append({
                    "id": message["id"],
                    "status": "failed",
                    "error": reason,
                })
                continue
        try:
            connection_id = message.get("connection_id")
            if connection_id:
                connection = db.get_whatsapp_connection(
                    connection_id, message["business_id"]
                )
                if not connection or connection.get("status") != "active":
                    raise RuntimeError("La conexión empresarial no está activa.")
                if not connection.get("outbound_enabled"):
                    raise RuntimeError("Los envíos de esta conexión están pausados.")
                meta_message_id = _post_to_meta(
                    _meta_payload(message), connection["phone_number_id"]
                )
            else:
                meta_message_id = _post_to_meta(_meta_payload(message))
            db.mark_whatsapp_sent(message["id"], meta_message_id, now_text)
            processed.append({
                "id": message["id"],
                "status": "sent",
                "meta_message_id": meta_message_id,
            })
        except MetaRejected as exc:
            db.mark_whatsapp_blocked(message["id"], str(exc), now_text)
            log.warning(
                "Meta rechazó el envío outbox=%s sin posibilidad de reintento: %s",
                message["id"], exc,
            )
            processed.append({
                "id": message["id"],
                "status": "failed",
                "error": str(exc),
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
    connection_id: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | None = None,
) -> dict:
    point = now or datetime.now()
    return db.enqueue_whatsapp_message(
        business_id=business_id,
        connection_id=connection_id,
        to_phone=to,
        message_type="text",
        text_body=text,
        idempotency_key=idempotency_key,
        max_attempts=config.WHATSAPP_MAX_ATTEMPTS,
        now=point.isoformat(timespec="seconds"),
    )


# Meta rechaza un parametro de plantilla que lleve salto de linea, tabulador o
# mas de cuatro espacios seguidos. El planificador compone resumenes multilinea y
# los pasa como un unico parametro, asi que sin esto los proactivos fallarian
# contra el numero real y agotarian sus reintentos en silencio: las pruebas no lo
# ven porque simulan la respuesta de Meta.
_PARAM_ESPACIOS = re.compile(r" {4,}")
_PARAM_SALTOS = re.compile("[\r\n\t\v\f  ]+")
_PARAM_SEPARADOR = " · "
_PARAM_MAX_CHARS = 1024


def sanitize_template_param(value) -> str:
    """Aplana un valor para que Meta lo acepte, conservando la lectura.

    Los saltos de linea se convierten en un separador visible en vez de
    desaparecer: un resumen del dia sin ninguna marca entre sus puntos se lee
    como un parrafo confuso. Se limpia al encolar y no al enviar, para que lo
    guardado coincida con lo que sale y un reintento no cambie el texto.
    """
    texto = str(value if value is not None else "")
    texto = _PARAM_SALTOS.sub(_PARAM_SEPARADOR, texto)
    texto = _PARAM_ESPACIOS.sub("   ", texto)
    # Separadores pegados aparecen cuando el original traia lineas en blanco.
    doble = _PARAM_SEPARADOR + " " + _PARAM_SEPARADOR.strip() + " "
    while doble in texto:
        texto = texto.replace(doble, _PARAM_SEPARADOR)
    # Meta corta el parámetro en 1024 caracteres: mejor recortar aquí, donde se
    # ve, que dejar que el mensaje salga truncado sin que nadie se entere.
    return texto.strip().strip("·").strip()[:_PARAM_MAX_CHARS]


def queue_template(
    to: str,
    template_name: str,
    params: list[str] | None = None,
    *,
    business_id: int | None = None,
    connection_id: int | None = None,
    language: str | None = None,
    idempotency_key: str | None = None,
    now: datetime | None = None,
) -> dict:
    point = now or datetime.now()
    return db.enqueue_whatsapp_message(
        business_id=business_id,
        connection_id=connection_id,
        to_phone=to,
        message_type="template",
        template_name=template_name,
        template_language=language or config.WHATSAPP_TEMPLATE_LANGUAGE,
        template_params=json.dumps(
            [sanitize_template_param(p) for p in (params or [])],
            ensure_ascii=False,
        ),
        idempotency_key=idempotency_key,
        max_attempts=config.WHATSAPP_MAX_ATTEMPTS,
        now=point.isoformat(timespec="seconds"),
    )


def send(
    to: str,
    text: str,
    *,
    business_id: int | None = None,
    connection_id: int | None = None,
    idempotency_key: str | None = None,
) -> bool:
    """Encola de forma durable y hace un primer intento inmediato."""
    message = queue_text(
        to,
        text,
        business_id=business_id,
        connection_id=connection_id,
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
    connection_id: int | None = None,
    language: str | None = None,
    idempotency_key: str | None = None,
) -> bool:
    """Encola una plantilla aprobada, vía obligatoria para proactivos."""
    message = queue_template(
        to,
        template_name,
        params,
        business_id=business_id,
        connection_id=connection_id,
        language=language,
        idempotency_key=idempotency_key,
    )
    process_outbox(only_ids=[message["id"]], limit=1)
    return True


def queue_payment_reminder(
    to: str,
    client_name: str,
    business_name: str,
    invoice_number: str,
    amount: str,
    portal_url: str,
    *,
    business_id: int,
    idempotency_key: str,
) -> dict:
    """Persiste el recordatorio aprobable por Meta sin enviarlo en línea."""
    return queue_template(
        to,
        config.WHATSAPP_TEMPLATE_PAYMENT_REMINDER,
        [client_name, business_name, invoice_number, amount, portal_url],
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
