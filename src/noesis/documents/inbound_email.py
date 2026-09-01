"""Entrada documental segura desde un único buzón IMAP/catch-all.

El destinatario opaco decide el negocio. El correo nunca crea gastos, facturas ni
clientes por sí solo: cada adjunto entra por ``documents.service`` y queda pendiente
de revisión. No se persisten remitente, asunto, cuerpo ni el mensaje original.
"""

from __future__ import annotations

import argparse
import hashlib
import imaplib
import json
import logging
import re
import ssl
from email import policy
from email.message import Message
from email.parser import BytesParser
from email.utils import getaddresses
from pathlib import Path

from .. import config, db
from . import service

log = logging.getLogger("noesis.inbound_email")

_ROUTE_TOKEN = re.compile(r"^[a-f0-9]{32}$")
_PERMANENT_REJECTIONS = {
    "message_too_large",
    "route_missing",
    "route_ambiguous",
    "route_unknown",
    "no_attachments",
    "too_many_attachments",
    "attachments_too_large",
}


class InboundEmailError(RuntimeError):
    """Fallo transitorio: el mensaje debe seguir sin leer para reintentarlo."""


def configured() -> bool:
    return bool(
        config.INBOUND_EMAIL_ENABLED
        and config.INBOUND_EMAIL_HOST
        and config.INBOUND_EMAIL_USER
        and config.INBOUND_EMAIL_PASSWORD
        and config.INBOUND_EMAIL_DOMAIN
    )


def route_address(route: dict) -> str:
    return (
        f"{config.INBOUND_EMAIL_PREFIX}.{route['route_token']}"
        f"@{config.INBOUND_EMAIL_DOMAIN}"
    )


def ensure_route(business_id: int, *, rotate: bool = False) -> dict:
    route = (
        db.rotate_inbound_email_route(business_id)
        if rotate else db.ensure_inbound_email_route(business_id)
    )
    return {**route, "address": route_address(route)}


def _header_addresses(message: Message) -> list[str]:
    values: list[str] = []
    # Hostinger puede conservar el sobre en una de estas cabeceras. ``To`` y
    # ``Cc`` sirven en el piloto, pero el token aleatorio y la confirmación siguen
    # siendo las barreras reales frente a mensajes falsificados.
    for header in ("delivered-to", "x-original-to", "envelope-to", "to", "cc"):
        values.extend(message.get_all(header, []))
    return [address.strip().lower() for _name, address in getaddresses(values)]


def _route_tokens(message: Message) -> set[str]:
    suffix = f"@{config.INBOUND_EMAIL_DOMAIN}"
    prefix = f"{config.INBOUND_EMAIL_PREFIX}."
    tokens: set[str] = set()
    for address in _header_addresses(message):
        if not address.endswith(suffix):
            continue
        local = address[:-len(suffix)]
        if not local.startswith(prefix):
            continue
        token = local[len(prefix):]
        if _ROUTE_TOKEN.fullmatch(token):
            tokens.add(token)
    return tokens


def _safe_filename(filename: str | None, index: int) -> str:
    name = re.split(r"[\\/]", str(filename or ""))[-1].strip()
    name = re.sub(r"[\x00-\x1f\x7f]", "_", name)[:180]
    return name or f"adjunto-{index}.bin"


def _attachments(message: Message) -> list[tuple[str, bytes]]:
    attachments: list[tuple[str, bytes]] = []
    for part in message.walk():
        if part.is_multipart():
            continue
        filename = part.get_filename()
        if not filename and part.get_content_disposition() != "attachment":
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        attachments.append((_safe_filename(filename, len(attachments) + 1), payload))
    return attachments


def _reject(code: str) -> dict:
    return {
        "ok": False,
        "status": "rejected",
        "code": code,
        "permanent": code in _PERMANENT_REJECTIONS,
    }


def process_raw_message(raw: bytes) -> dict:
    """Procesa un RFC 822 sin confiar en texto, remitente ni nombre de archivo."""
    if not raw or len(raw) > config.INBOUND_EMAIL_MAX_BYTES:
        return _reject("message_too_large")
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw)
    except (ValueError, TypeError) as exc:
        raise InboundEmailError("No se pudo interpretar el mensaje.") from exc
    tokens = _route_tokens(message)
    if not tokens:
        return _reject("route_missing")
    if len(tokens) != 1:
        return _reject("route_ambiguous")
    route = db.resolve_inbound_email_route(next(iter(tokens)))
    if not route:
        return _reject("route_unknown")
    business_id = int(route["business_id"])
    fingerprint = hashlib.sha256(raw).hexdigest()
    claimed = db.claim_inbound_email_message(business_id, fingerprint)
    if not claimed:
        return {
            "ok": True,
            "status": "duplicate",
            "business_id": business_id,
            "documents": [],
        }

    attachments = _attachments(message)
    if not attachments:
        db.finish_inbound_email_message(
            claimed["id"], business_id, status="rejected",
            attachment_count=0, document_count=0, error_code="no_attachments",
        )
        return {**_reject("no_attachments"), "business_id": business_id}
    if len(attachments) > config.INBOUND_EMAIL_MAX_ATTACHMENTS:
        db.finish_inbound_email_message(
            claimed["id"], business_id, status="rejected",
            attachment_count=len(attachments), document_count=0,
            error_code="too_many_attachments",
        )
        return {**_reject("too_many_attachments"), "business_id": business_id}
    if sum(len(payload) for _name, payload in attachments) > config.INBOUND_EMAIL_MAX_BYTES:
        db.finish_inbound_email_message(
            claimed["id"], business_id, status="rejected",
            attachment_count=len(attachments), document_count=0,
            error_code="attachments_too_large",
        )
        return {**_reject("attachments_too_large"), "business_id": business_id}

    document_ids: list[int] = []
    rejected = 0
    try:
        for filename, payload in attachments:
            try:
                document = service.upload(
                    business_id,
                    filename,
                    payload,
                    note="Recibido por correo. Revisa antes de registrarlo.",
                    auto_classify=True,
                )
            except service.DuplicateDocument as exc:
                document_ids.append(exc.existing_id)
                continue
            except service.TransientUploadError:
                raise
            except service.UploadError:
                rejected += 1
                continue
            document_ids.append(int(document["id"]))
            proposal = document.get("classification") or {}
            if (proposal.get("kind") in {"factura_emitida", "factura_recibida"}
                    or document.get("kind") in {"factura_emitida", "factura_recibida"}):
                # La lectura puede relacionar un cliente existente o proponer uno;
                # nunca confirma contabilidad ni crea el cliente desde aquí.
                service.invoice_draft(business_id, int(document["id"]))
            # En el piloto no se enlazan documentos no fiscales usando el asunto
            # o cuerpo del correo. Podrían ser reenviados o contener nombres de
            # terceros: es preferible que queden pendientes a relacionarlos mal.
    except Exception as exc:  # noqa: BLE001 - se reintenta sin marcar el IMAP
        db.finish_inbound_email_message(
            claimed["id"], business_id, status="failed",
            attachment_count=len(attachments), document_count=len(document_ids),
            error_code=type(exc).__name__,
        )
        raise InboundEmailError("La entrada documental falló de forma transitoria.") from exc

    status = "processed" if not rejected else "partial" if document_ids else "rejected"
    code = "unsupported_attachment" if rejected else None
    db.finish_inbound_email_message(
        claimed["id"], business_id, status=status,
        attachment_count=len(attachments), document_count=len(document_ids),
        error_code=code,
    )
    db.record_product_event(
        business_id,
        "inbound_email_processed",
        json.dumps(
            {
                "attachments": len(attachments),
                "documents": len(document_ids),
                "rejected": rejected,
            },
            separators=(",", ":"),
        ),
    )
    return {
        "ok": bool(document_ids),
        "status": status,
        "business_id": business_id,
        "documents": document_ids,
        "rejected_attachments": rejected,
        "permanent": True,
    }


def poll_mailbox(limit: int | None = None) -> dict:
    """Lee mensajes no vistos. Solo marca los resultados definitivos."""
    if not configured():
        return {"ok": False, "code": "not_configured", "processed": 0}
    maximum = min(limit or config.INBOUND_EMAIL_MAX_MESSAGES,
                  config.INBOUND_EMAIL_MAX_MESSAGES)
    connection: imaplib.IMAP4_SSL | None = None
    processed = failed = 0
    try:
        context = ssl.create_default_context()
        connection = imaplib.IMAP4_SSL(
            config.INBOUND_EMAIL_HOST,
            config.INBOUND_EMAIL_PORT,
            ssl_context=context,
            timeout=20,
        )
        connection.login(config.INBOUND_EMAIL_USER, config.INBOUND_EMAIL_PASSWORD)
        status, _data = connection.select(config.INBOUND_EMAIL_MAILBOX, readonly=False)
        if status != "OK":
            raise InboundEmailError("No se pudo abrir el buzón configurado.")
        status, data = connection.uid("search", None, "UNSEEN")
        if status != "OK":
            raise InboundEmailError("No se pudieron listar los correos pendientes.")
        uids = (data[0] or b"").split()[:maximum]
        for uid in uids:
            status, parts = connection.uid("fetch", uid, "(BODY.PEEK[])")
            raw = next(
                (item[1] for item in parts
                 if isinstance(item, tuple) and isinstance(item[1], bytes)),
                None,
            ) if status == "OK" else None
            if raw is None:
                failed += 1
                continue
            try:
                result = process_raw_message(raw)
            except InboundEmailError:
                failed += 1
                continue
            if result.get("permanent") or result.get("status") == "duplicate":
                connection.uid("store", uid, "+FLAGS", "(\\Seen)")
            processed += 1
        return {"ok": failed == 0, "processed": processed, "failed": failed}
    except (imaplib.IMAP4.error, OSError, ssl.SSLError) as exc:
        raise InboundEmailError("No se pudo leer el buzón IMAP.") from exc
    finally:
        if connection is not None:
            try:
                connection.logout()
            except (imaplib.IMAP4.error, OSError):
                pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prueba segura del buzón documental catch-all de Noesis."
    )
    parser.add_argument("--business-id", type=int)
    parser.add_argument("--create-route", action="store_true")
    parser.add_argument("--rotate-route", action="store_true")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--network", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.create_route or args.rotate_route:
        if not args.business_id:
            parser.error("--business-id es obligatorio para crear o rotar la ruta")
        print(json.dumps(
            ensure_route(args.business_id, rotate=args.rotate_route),
            ensure_ascii=False, default=str,
        ))
        return
    if args.file:
        print(json.dumps(
            process_raw_message(args.file.read_bytes()),
            ensure_ascii=False, default=str,
        ))
        return
    if args.network:
        print(json.dumps(poll_mailbox(args.limit), ensure_ascii=False))
        return
    print(json.dumps({
        "enabled": config.INBOUND_EMAIL_ENABLED,
        "configured": configured(),
        "host": config.INBOUND_EMAIL_HOST,
        "port": config.INBOUND_EMAIL_PORT,
        "domain": config.INBOUND_EMAIL_DOMAIN,
        "mailbox": config.INBOUND_EMAIL_MAILBOX,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
