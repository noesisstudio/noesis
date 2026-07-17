"""Adaptador de email (solo stdlib).

Envía correos por SMTP si está configurado (SMTP_HOST...). Si no lo está —como en
local o antes de contratar un proveedor— NO falla: registra el contenido en el log
para poder probar el flujo (p. ej. el enlace de reset de contraseña). Mismo patrón
que el resto de adaptadores: se activa con variables de entorno y degrada con
elegancia.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from .. import config, db

log = logging.getLogger("noesis.email")


def available() -> bool:
    return bool(config.SMTP_HOST and config.SMTP_USER and config.SMTP_PASS)


def send_email(to: str, subject: str, body: str, html: str | None = None) -> bool:
    """Envía un email de texto. Devuelve True si salió por SMTP; False si solo se
    registró en log (sin SMTP configurado o ante un fallo de envío)."""
    if not available():
        if config.IS_PRODUCTION:
            log.error(
                "SMTP no está configurado: no se pudo enviar '%s' a %s.",
                subject, to,
            )
        else:
            log.warning("[EMAIL local sin SMTP] Para: %s | Asunto: %s\n%s",
                        to, subject, body)
        return False
    msg = EmailMessage()
    msg["From"] = config.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
    return _send_msg(msg)


def queue_email(
    to: str,
    subject: str,
    body: str,
    html: str | None = None,
    *,
    business_id: int | None = None,
    idempotency_key: str | None = None,
) -> bool:
    """Persiste el correo antes de enviarlo; el scheduler se ocupa de SMTP."""
    db.enqueue_email_message(
        business_id=business_id,
        to_email=to,
        subject=subject,
        text_body=body,
        html_body=html,
        idempotency_key=idempotency_key,
    )
    return True


def send_invoice_email(to: str, biz_name: str, invoice_number: str,
                       total: str, pdf_data: bytes | None = None) -> bool:
    """Envía un email con la factura adjunta en PDF."""
    if not available():
        log.warning("[EMAIL] Factura %s no enviada (sin SMTP): %s", invoice_number, to)
        return False
    subject = f"Factura {invoice_number} — {biz_name}"
    body = (f"Hola,\n\nAdjunto la factura {invoice_number} por {total}.\n\n"
            f"Si tienes alguna duda, responde a este correo.\n\n— {biz_name} vía Noesis")
    html = (f"<div style='font-family:sans-serif;max-width:600px'>"
            f"<p>Hola,</p>"
            f"<p>Adjunto la factura <b>{invoice_number}</b> por <b>{total}</b>.</p>"
            f"<p>Si tienes alguna duda, responde a este correo.</p>"
            f"<p style='color:#666'>— {biz_name} vía Noesis</p></div>")
    msg = EmailMessage()
    msg["From"] = config.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    msg.add_alternative(html, subtype="html")
    if pdf_data:
        msg.add_attachment(pdf_data, maintype="application", subtype="pdf",
                           filename=f"factura_{invoice_number.replace('/', '-')}.pdf")
    return _send_msg(msg)


def send_reminder_email(to: str, biz_name: str, client_name: str,
                        invoice_number: str, total: str, days_late: int) -> bool:
    """Envía un recordatorio de cobro por email."""
    subject = f"Recordatorio: factura {invoice_number} pendiente — {biz_name}"
    body = (f"Hola {client_name},\n\n"
            f"Te recordamos que la factura {invoice_number} por {total} "
            f"lleva {days_late} días pendiente de pago.\n\n"
            f"Si ya lo has gestionado, ignora este mensaje.\n\n— {biz_name} vía Noesis")
    return send_email(to, subject, body)


def _send_msg(msg: EmailMessage) -> bool:
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as s:
            s.starttls(context=ctx)
            s.login(config.SMTP_USER, config.SMTP_PASS)
            s.send_message(msg)
        return True
    except Exception as e:  # noqa: BLE001
        log.error("Fallo enviando email a %s: %s", msg["To"], e)
        return False
