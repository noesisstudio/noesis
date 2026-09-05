"""Capa interna de redacción y comunicaciones de Bynoesis.

Convierte hechos ya guardados en mensajes profesionales sin usar un LLM. La capa
no inventa destinatarios, importes ni fechas y nunca envía en el mismo paso en el
que redacta: por WhatsApp deja una acción pendiente que el titular confirma con
SÍ/NO. Los envíos se vuelven a validar contra la base de datos al confirmarse.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
import json
import re

from . import config, db, nlu


@dataclass(frozen=True)
class CommunicationDraft:
    """Borrador trazable construido únicamente con datos del negocio."""

    intent: str
    channel: str
    recipient_name: str
    recipient_address: str
    subject: str
    body: str
    client_id: int | None = None
    entity_id: int | None = None
    template_name: str | None = None
    template_params: tuple[str, ...] = ()

    def pending_payload(self) -> dict:
        payload = asdict(self)
        payload["template_params"] = list(self.template_params)
        return payload


_WRITE_MARKERS = (
    "prepara un mensaje", "prepara el mensaje", "prepara un correo",
    "mensaje para", "correo para", "email para",
    "prepara un recordatorio", "prepara recordatorio", "recordatorio para",
    "seguimiento para", "missatge per", "correu per",
    "prepara un recordatori", "recordatori per",
)
_SEND_MARKERS = (
    "envia", "envía", "enviar", "manda", "mándale", "mandale", "mandar",
    "escribele", "escríbele", "envia-li", "envia'l", "send",
)


def _eur(number) -> str:
    return (
        f"{(number or 0):,.2f} €"
        .replace(",", "X").replace(".", ",").replace("X", ".")
    )


def _text_key(text: str) -> str:
    normalized = nlu._norm(text)
    return " ".join(re.findall(r"[a-z0-9]+", normalized))


def _contains_phrase(text: str, phrase: str) -> bool:
    return f" {_text_key(phrase)} " in f" {_text_key(text)} "


def _language(business: dict) -> str:
    return business.get("language") if business.get("language") in {"es", "ca", "en"} else "es"


def _find_client(business_id: int, text: str) -> dict | None:
    matches = [
        client for client in db.list_clients(business_id)
        if client.get("name") and _contains_phrase(text, client["name"])
    ]
    matches.sort(key=lambda item: len(item.get("name") or ""), reverse=True)
    return matches[0] if matches else None


def _requested_channel(text: str, client: dict | None, *, default: str) -> str:
    norm = nlu._norm(text)
    if any(word in norm for word in ("correo", "email", "mail", "correu")):
        return "email"
    if "whatsapp" in norm or "whats" in norm:
        return "whatsapp_template"
    if default == "whatsapp_template" and client and client.get("phone"):
        return default
    if client and client.get("email"):
        return "email"
    return default


def _portal_url(business_id: int, client_id: int) -> str:
    token = db.get_or_create_portal_token(business_id, client_id)
    return f"{config.BASE_URL}/p/{token}" if token else config.BASE_URL


def _format_when(value: str, language: str) -> str:
    if not value:
        return ""
    try:
        point = datetime.fromisoformat(value)
    except ValueError:
        return value.replace("T", " ")
    if language == "ca":
        return point.strftime("%d/%m/%Y a les %H:%M")
    if language == "en":
        return point.strftime("%d/%m/%Y at %H:%M")
    return point.strftime("%d/%m/%Y a las %H:%M")


def _payment_draft(
    business: dict, client: dict, invoice: dict, requested_channel: str
) -> CommunicationDraft:
    language = _language(business)
    name = client.get("name") or "cliente"
    business_name = business.get("name") or "Tu proveedor"
    number = invoice.get("number") or str(invoice["id"])
    amount = _eur(invoice.get("remaining_amount") or invoice.get("total"))
    portal = _portal_url(business["id"], client["id"])
    if language == "ca":
        subject = f"Recordatori de la factura {number}"
        body = (
            f"Hola {name},\n\nEt recordem que la factura {number} per {amount} "
            f"continua pendent de pagament. Pots consultar-la i fer el pagament "
            f"aquí: {portal}\n\nSi ja ho has gestionat, ignora aquest missatge.\n\n"
            f"Gràcies,\n{business_name}"
        )
    elif language == "en":
        subject = f"Reminder for invoice {number}"
        body = (
            f"Hello {name},\n\nThis is a reminder that invoice {number} for "
            f"{amount} is still pending. You can view it and pay here: {portal}"
            f"\n\nIf you have already paid it, please ignore this message.\n\n"
            f"Thank you,\n{business_name}"
        )
    else:
        subject = f"Recordatorio de la factura {number}"
        body = (
            f"Hola {name},\n\nTe recordamos que la factura {number} por {amount} "
            f"sigue pendiente de pago. Puedes consultarla y pagarla aquí: {portal}"
            f"\n\nSi ya la has gestionado, ignora este mensaje.\n\n"
            f"Gracias,\n{business_name}"
        )
    channel = requested_channel
    address = client.get("email") if channel == "email" else client.get("phone")
    return CommunicationDraft(
        intent="payment_reminder",
        channel=channel,
        recipient_name=name,
        recipient_address=address or "",
        subject=subject,
        body=body,
        client_id=client["id"],
        entity_id=invoice["id"],
        template_name=(
            config.WHATSAPP_TEMPLATE_PAYMENT_REMINDER
            if channel == "whatsapp_template" else None
        ),
        template_params=(name, business_name, number, amount, portal),
    )


def _quote_draft(
    business: dict, client: dict, quote: dict, requested_channel: str
) -> CommunicationDraft:
    language = _language(business)
    name = client.get("name") or "cliente"
    business_name = business.get("name") or "Tu proveedor"
    number = quote.get("number") or str(quote["id"])
    amount = _eur(quote.get("total"))
    portal = _portal_url(business["id"], client["id"])
    if language == "ca":
        subject = f"Seguiment del pressupost {number}"
        body = (
            f"Hola {name},\n\nVolia saber si has pogut revisar el pressupost "
            f"{number} per {amount}. El tens disponible aquí: {portal}\n\n"
            "Si tens cap dubte o vols ajustar algun punt, digues-m'ho i ho revisem."
            f"\n\nGràcies,\n{business_name}"
        )
    elif language == "en":
        subject = f"Follow-up on quote {number}"
        body = (
            f"Hello {name},\n\nI wanted to check whether you had a chance to "
            f"review quote {number} for {amount}. You can view it here: {portal}"
            "\n\nIf you have any questions or would like to adjust anything, let me know."
            f"\n\nThank you,\n{business_name}"
        )
    else:
        subject = f"Seguimiento del presupuesto {number}"
        body = (
            f"Hola {name},\n\nQuería saber si has podido revisar el presupuesto "
            f"{number} por {amount}. Lo tienes disponible aquí: {portal}\n\n"
            "Si tienes alguna duda o quieres ajustar algún punto, dímelo y lo revisamos."
            f"\n\nGracias,\n{business_name}"
        )
    channel = requested_channel
    address = client.get("email") if channel == "email" else client.get("phone")
    return CommunicationDraft(
        intent="quote_followup",
        channel=channel,
        recipient_name=name,
        recipient_address=address or "",
        subject=subject,
        body=body,
        client_id=client["id"],
        entity_id=quote["id"],
        template_name=(
            config.WHATSAPP_TEMPLATE_QUOTE_FOLLOWUP
            if channel == "whatsapp_template" else None
        ),
        template_params=(name, business_name, number, amount, portal),
    )


def _appointment_draft(
    business: dict, client: dict, job: dict, requested_channel: str
) -> CommunicationDraft:
    language = _language(business)
    name = client.get("name") or "cliente"
    business_name = business.get("name") or "Tu proveedor"
    when = _format_when(job.get("scheduled_for") or "", language)
    description = job.get("description") or "Trabajo"
    zone = job.get("zone") or client.get("zone") or ""
    place = f" ({zone})" if zone else ""
    if language == "ca":
        subject = f"Confirmació de la cita del {when}"
        body = (
            f"Hola {name},\n\nEt confirmem la cita del {when}{place} per a "
            f"{description}. Si necessites canviar l'hora, respon a aquest missatge."
            f"\n\nGràcies,\n{business_name}"
        )
    elif language == "en":
        subject = f"Appointment confirmation for {when}"
        body = (
            f"Hello {name},\n\nYour appointment is confirmed for {when}{place} "
            f"for {description}. If you need to change the time, reply to this message."
            f"\n\nThank you,\n{business_name}"
        )
    else:
        subject = f"Confirmación de cita del {when}"
        body = (
            f"Hola {name},\n\nTe confirmamos la cita del {when}{place} para "
            f"{description}. Si necesitas cambiar la hora, responde a este mensaje."
            f"\n\nGracias,\n{business_name}"
        )
    channel = requested_channel
    address = client.get("email") if channel == "email" else client.get("phone")
    return CommunicationDraft(
        intent="appointment_reminder",
        channel=channel,
        recipient_name=name,
        recipient_address=address or "",
        subject=subject,
        body=body,
        client_id=client["id"],
        entity_id=job["id"],
        template_name=(
            config.WHATSAPP_TEMPLATE_APPOINTMENT_REMINDER
            if channel == "whatsapp_template" else None
        ),
        template_params=(name, business_name, when, description),
    )


def _gestoria_draft(business: dict) -> CommunicationDraft | None:
    email = business.get("gestoria_email")
    if not email:
        return None
    language = _language(business)
    business_name = business.get("name") or "El negocio"
    gestoria_name = business.get("gestoria_name") or "gestoría"
    token = db.get_or_create_gestoria_token(business["id"])
    portal = f"{config.BASE_URL}/g/{token}" if token else config.BASE_URL
    if language == "ca":
        subject = f"Documentació disponible · {business_name}"
        body = (
            f"Hola {gestoria_name},\n\nLa documentació de {business_name} està "
            f"ordenada i disponible al portal privat: {portal}\n\nSi falta algun "
            "document, podeu sol·licitar-lo des del mateix portal.\n\nGràcies."
        )
    elif language == "en":
        subject = f"Documents available · {business_name}"
        body = (
            f"Hello {gestoria_name},\n\nThe documents for {business_name} are "
            f"organized and available in the private portal: {portal}\n\nIf anything "
            "is missing, you can request it from the same portal.\n\nThank you."
        )
    else:
        subject = f"Documentación disponible · {business_name}"
        body = (
            f"Hola {gestoria_name},\n\nLa documentación de {business_name} está "
            f"ordenada y disponible en el portal privado: {portal}\n\nSi falta algún "
            "documento, podéis solicitarlo desde el mismo portal.\n\nGracias."
        )
    return CommunicationDraft(
        intent="gestoria_email",
        channel="email",
        recipient_name=gestoria_name,
        recipient_address=email,
        subject=subject,
        body=body,
    )


def _custom_detail(text: str) -> str:
    patterns = (
        r"(?:diciendo|para decirle|dient|per dir-li|saying)\s+que\s+(.+)$",
        r"(?:dile|digues-li|tell (?:him|her|them))\s+(.+)$",
        r":\s*(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1).strip().strip(". ")[:800]
    return ""


def _custom_draft(
    business: dict, client: dict, detail: str, *, channel: str
) -> CommunicationDraft:
    language = _language(business)
    name = client.get("name") or "cliente"
    business_name = business.get("name") or "Tu proveedor"
    sentence = detail[:1].upper() + detail[1:]
    if not sentence.endswith((".", "!", "?")):
        sentence += "."
    if language == "ca":
        subject = f"Missatge de {business_name}"
        body = f"Hola {name},\n\n{sentence}\n\nGràcies,\n{business_name}"
    elif language == "en":
        subject = f"Message from {business_name}"
        body = f"Hello {name},\n\n{sentence}\n\nThank you,\n{business_name}"
    else:
        subject = f"Mensaje de {business_name}"
        body = f"Hola {name},\n\n{sentence}\n\nGracias,\n{business_name}"
    return CommunicationDraft(
        intent="custom_email",
        channel=channel,
        recipient_name=name,
        recipient_address=client.get("email") or "",
        subject=subject,
        body=body,
        client_id=client["id"],
    )


def _select_single(items: list[dict], text: str) -> dict | None:
    by_number = [
        item for item in items
        if item.get("number") and str(item["number"]).lower() in text.lower()
    ]
    if len(by_number) == 1:
        return by_number[0]
    return items[0] if len(items) == 1 else None


def _build_draft(business_id: int, text: str) -> tuple[CommunicationDraft | None, str | None]:
    business = db.get_business(business_id)
    if not business:
        return None, "No encuentro el negocio."
    norm = nlu._norm(text)
    client = _find_client(business_id, text)

    if "gestor" in norm and any(word in norm for word in ("correo", "email", "document", "papel", "envia")):
        draft = _gestoria_draft(business)
        return (draft, None) if draft else (
            None,
            "Me falta el correo de tu gestoría. Guárdalo en Ajustes y te preparo el envío.",
        )

    if any(word in norm for word in (
        "cobro", "cobrar", "cobrament", "pagament pendent", "debe", "deu",
        "impagad", "factura pendiente", "factura pendent",
    )):
        invoices = db.pending_payments(business_id)
        if client:
            invoices = [item for item in invoices if item.get("client_id") == client["id"]]
        invoice = _select_single(invoices, text)
        if not invoice:
            return None, (
                "Dime el cliente o el número de factura que quieres reclamar; "
                "no voy a elegir una deuda por ti."
            )
        client = db.get_client(invoice.get("client_id"), business_id)
        if not client:
            return None, "Esa factura no tiene un cliente válido asociado."
        requested = _requested_channel(text, client, default="whatsapp_template")
        return _payment_draft(business, client, invoice, requested), None

    if any(word in norm for word in ("presupuest", "pressupost")) and any(
        word in norm for word in ("segu", "record", "mensaje", "missatge", "correo", "correu", "envia")
    ):
        quotes = db.list_quotes(business_id, status="enviado")
        if client:
            quotes = [item for item in quotes if item.get("client_id") == client["id"]]
        quote = _select_single(quotes, text)
        if not quote:
            return None, (
                "Dime el cliente o el número del presupuesto enviado; "
                "no voy a escoger uno sin estar segura."
            )
        client = db.get_client(quote.get("client_id"), business_id)
        if not client:
            return None, "Ese presupuesto no tiene un cliente válido asociado."
        requested = _requested_channel(text, client, default="whatsapp_template")
        return _quote_draft(business, client, quote, requested), None

    if any(word in norm for word in ("cita", "visita", "trabajo", "feina")) and any(
        word in norm for word in ("confirm", "record", "mensaje", "correo", "envia")
    ):
        end = (date.today() + timedelta(days=90)).isoformat()
        jobs = db.jobs_between(date.today().isoformat(), end, business_id)
        if client:
            jobs = [item for item in jobs if item.get("client_id") == client["id"]]
        job = _select_single(jobs, text)
        if not job:
            return None, (
                "Dime el cliente de la cita. Si tiene varias próximas, dime también "
                "el día para no confirmar la equivocada."
            )
        client = db.get_client(job.get("client_id"), business_id)
        if not client:
            return None, "Esa cita no tiene un cliente válido asociado."
        requested = _requested_channel(text, client, default="whatsapp_template")
        return _appointment_draft(business, client, job, requested), None

    if client:
        detail = _custom_detail(text)
        if not detail:
            return None, f"¿Qué quieres decirle exactamente a {client['name']}?"
        requested = _requested_channel(text, client, default="draft_only")
        if requested != "email":
            requested = "draft_only"
        return _custom_draft(business, client, detail, channel=requested), None
    return None, "Dime a qué cliente escribimos y qué necesitas comunicarle."


def handles(text: str) -> bool:
    """Detecta peticiones de redacción sin capturar órdenes operativas normales."""
    norm = nlu._norm(text)
    communication_words = (
        "mensaje", "missatge", "correo", "correu", "email", "whatsapp",
        "recordatorio", "recordatori",
    )
    structured_communication = (
        ("gestor" in norm and "document" in norm)
        or ("presupuest" in norm and "segu" in norm)
        or ("pressupost" in norm and "segu" in norm)
        or (any(word in norm for word in ("cita", "visita")) and "confirm" in norm)
    )
    if any(marker in norm for marker in _WRITE_MARKERS):
        return True
    write_requested = any(word in norm for word in ("redact", "escrib", "escriu"))
    if write_requested:
        operational_words = (
            "factura", "presupuest", "pressupost", "gasto", "despesa",
            "trabajo", "feina", "proyecto", "projecte",
        )
        return (
            any(word in norm for word in communication_words)
            or structured_communication
            or not any(word in norm for word in operational_words)
        )
    send_requested = any(marker in norm for marker in _SEND_MARKERS)
    if not send_requested:
        return False
    return any(word in norm for word in communication_words) or structured_communication


def prepare_response(
    business_id: int,
    text: str,
    *,
    channel: str,
    actor_phone: str | None = None,
) -> dict | None:
    """Redacta y, si procede, deja un envío pendiente de confirmación."""
    if not handles(text):
        return None
    draft, error = _build_draft(business_id, text)
    if error:
        return {"reply": error, "source": "local_internal"}
    if not draft:
        return None
    send_requested = any(marker in nlu._norm(text) for marker in _SEND_MARKERS)
    preview = f"**{draft.subject}**\n\n{draft.body}"
    can_send = draft.channel in {"email", "whatsapp_template"} and bool(
        draft.recipient_address
    )
    if send_requested and channel == "whatsapp" and actor_phone and can_send:
        db.set_pending_action(
            business_id,
            actor_phone,
            "send_communication",
            draft.pending_payload(),
            ttl_minutes=120,
        )
        return {
            "reply": (
                f"He preparado este mensaje para **{draft.recipient_name}**:\n\n"
                f"{preview}\n\n**Todavía no lo he enviado.** Responde SÍ para "
                "enviarlo o NO para descartarlo."
            ),
            "source": "local_internal",
            "draft": draft.pending_payload(),
        }
    note = "No lo he enviado."
    if send_requested and channel != "whatsapp":
        note += " Para enviarlo con control, pídemelo por tu WhatsApp y confirma con SÍ."
    elif send_requested and not can_send:
        note += " Falta un canal válido del destinatario."
    elif draft.channel == "draft_only":
        note += " El cliente no tiene email y un WhatsApp proactivo necesita una plantilla aprobada."
    return {
        "reply": (
            f"Borrador para **{draft.recipient_name}**:\n\n{preview}\n\n{note}"
        ),
        "source": "local_internal",
        "draft": draft.pending_payload(),
    }


def deliver_confirmed(business_id: int, payload: dict) -> str:
    """Revalida el borrador y lo entrega usando los adaptadores existentes."""
    from .adapters import email as email_adapter
    from .web import whatsapp

    business = db.get_business(business_id)
    if not business:
        return "No encuentro el negocio. No he enviado nada."
    intent = str(payload.get("intent") or "")
    channel = str(payload.get("channel") or "")
    client_id = payload.get("client_id")
    entity_id = payload.get("entity_id")
    client = db.get_client(client_id, business_id) if client_id else None

    if intent == "payment_reminder":
        invoice = db.get_invoice(entity_id, business_id)
        if not invoice or invoice.get("status") == "cobrada" or not client:
            return "La factura ya no está pendiente o el cliente no es válido. No he enviado nada."
        draft = _payment_draft(business, client, invoice, channel)
    elif intent == "quote_followup":
        quote = db.get_quote(entity_id, business_id)
        if not quote or quote.get("status") != "enviado" or not client:
            return "El presupuesto ya no está enviado o el cliente no es válido. No he enviado nada."
        draft = _quote_draft(business, client, quote, channel)
    elif intent == "appointment_reminder":
        job = db.get_job(entity_id, business_id)
        if not job or not job.get("scheduled_for") or not client:
            return "La cita ya no es válida. No he enviado nada."
        draft = _appointment_draft(business, client, job, channel)
    elif intent == "custom_email":
        detail_body = str(payload.get("body") or "").strip()
        if not client or not client.get("email") or not detail_body:
            return "El cliente no tiene un email válido. No he enviado nada."
        draft = CommunicationDraft(
            intent=intent,
            channel="email",
            recipient_name=client.get("name") or "cliente",
            recipient_address=client["email"],
            subject=str(payload.get("subject") or "Mensaje")[:180],
            body=detail_body[:4000],
            client_id=client["id"],
        )
    elif intent == "gestoria_email":
        draft = _gestoria_draft(business)
        if not draft:
            return "Tu gestoría no tiene un email válido. No he enviado nada."
    else:
        return "Ese borrador ya no es válido. No he enviado nada."

    delivered = False
    queued = False
    if draft.channel == "email":
        delivered = email_adapter.queue_email(
            draft.recipient_address, draft.subject, draft.body,
            business_id=business_id,
            idempotency_key=(
                f"internal-email:{business_id}:{draft.intent}:"
                f"{draft.entity_id or draft.client_id or 0}:{date.today().isoformat()}"
            ),
        )
        queued = delivered
    elif draft.channel == "whatsapp_template" and draft.template_name:
        key = (
            f"internal:{draft.intent}:{business_id}:"
            f"{draft.entity_id or draft.client_id or 0}:{date.today().isoformat()}"
        )
        delivered = whatsapp.send_template(
            whatsapp.recipient_phone(draft.recipient_address),
            draft.template_name,
            list(draft.template_params),
            business_id=business_id,
            idempotency_key=key,
        )
    if not delivered:
        return (
            "No he podido entregarlo por el canal configurado. El borrador sigue "
            "pendiente: responde SÍ para reintentar o NO para descartarlo."
        )
    db.record_product_event(
        business_id,
        "internal_communication_sent",
        json.dumps(
            {"intent": draft.intent, "channel": draft.channel},
            separators=(",", ":"),
        ),
    )
    if queued:
        return f"Preparado para enviar a {draft.recipient_name} ✅"
    return f"Enviado a {draft.recipient_name} ✅"
