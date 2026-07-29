"""Adaptador de email (solo stdlib).

Dos vías de salida, por este orden:

1. **API HTTPS** (Brevo) si hay `BREVO_API_KEY`. Es la única que funciona en
   plataformas como Railway, que bloquean la salida a los puertos de SMTP para
   evitar que se usen sus servidores para enviar spam.
2. **SMTP** clásico si está configurado.

Si no hay ninguna —como en local— NO falla: registra el contenido en el log para
poder probar el flujo (por ejemplo, el enlace de recuperar contraseña). Mismo
patrón que el resto de adaptadores: se activa con variables de entorno y degrada
con elegancia.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage

from .. import config, db

log = logging.getLogger("noesis.email")

# "Noesis <info@bynoesis.com>" -> ("Noesis", "info@bynoesis.com")
_REMITENTE = re.compile(r"^\s*(?P<nombre>.*?)\s*<(?P<correo>[^>]+)>\s*$")


def _api_available() -> bool:
    return bool(config.BREVO_API_KEY)


def available() -> bool:
    return _api_available() or bool(
        config.SMTP_HOST and config.SMTP_USER and config.SMTP_PASS
    )


def _sender() -> dict:
    """Separa nombre y dirección del remitente configurado."""
    bruto = (config.SMTP_FROM or "").strip()
    coincidencia = _REMITENTE.match(bruto)
    if coincidencia:
        return {
            "name": coincidencia.group("nombre") or "Noesis",
            "email": coincidencia.group("correo"),
        }
    return {"name": "Noesis", "email": bruto or config.SMTP_USER}


def _send_via_api(
    to: str, subject: str, body: str, html: str | None = None,
    attachments: list[tuple[str, bytes, str, str]] | None = None,
) -> bool:
    """Entrega por HTTPS, adjuntos incluidos (van codificados en el cuerpo)."""
    carga = {
        "sender": _sender(),
        "to": [{"email": to}],
        "subject": subject,
        "textContent": body,
    }
    if html:
        carga["htmlContent"] = html
    if attachments:
        carga["attachment"] = [
            {"name": nombre, "content": base64.b64encode(datos).decode("ascii")}
            for nombre, datos, _maintype, _subtype in attachments
        ]
    peticion = urllib.request.Request(
        config.BREVO_API_URL,
        data=json.dumps(carga).encode("utf-8"),
        headers={
            "api-key": config.BREVO_API_KEY,
            "content-type": "application/json",
            "accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            peticion, timeout=config.BREVO_TIMEOUT_SECONDS
        ) as respuesta:
            return 200 <= respuesta.status < 300
    except urllib.error.HTTPError as exc:
        # El cuerpo explica el motivo (clave inválida, remitente sin verificar…).
        detalle = exc.read().decode(errors="replace")[:500]
        log.error("Fallo enviando email a %s: %s %s", to, exc.code, detalle)
        return False
    except Exception as exc:  # noqa: BLE001
        log.error("Fallo enviando email a %s: %s", to, exc)
        return False


def send_email(
    to: str,
    subject: str,
    body: str,
    html: str | None = None,
    attachments: list[tuple[str, bytes, str, str]] | None = None,
) -> bool:
    """Envía un email. Devuelve True si salió; False si solo se registró en log
    (sin proveedor configurado o ante un fallo de envío)."""
    if not available():
        if config.IS_PRODUCTION:
            log.error(
                "No hay proveedor de correo configurado: no se pudo enviar "
                "'%s' a %s.", subject, to,
            )
        else:
            log.warning("[EMAIL local sin proveedor] Para: %s | Asunto: %s\n%s",
                        to, subject, body)
        return False
    if _api_available():
        return _send_via_api(to, subject, body, html, attachments)
    msg = EmailMessage()
    msg["From"] = config.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
    for filename, payload, maintype, subtype in attachments or []:
        msg.add_attachment(
            payload, maintype=maintype, subtype=subtype, filename=filename
        )
    return _send_msg(msg)


def queue_email(
    to: str,
    subject: str,
    body: str,
    html: str | None = None,
    *,
    business_id: int | None = None,
    idempotency_key: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> bool:
    """Persiste el correo antes de enviarlo; el scheduler se ocupa de SMTP."""
    db.enqueue_email_message(
        business_id=business_id,
        to_email=to,
        subject=subject,
        text_body=body,
        html_body=html,
        idempotency_key=idempotency_key,
        entity_type=entity_type,
        entity_id=entity_id,
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
    """Envía por SMTP eligiendo el modo de cifrado según el puerto.

    El 465 exige TLS desde el primer byte (SSL implícito); el 587 empieza en
    claro y sube a TLS con STARTTLS. Usar el modo equivocado no da un error
    inmediato: la conexión se queda esperando hasta agotar el tiempo límite.
    """
    ctx = ssl.create_default_context()
    try:
        if int(config.SMTP_PORT) == 465:
            with smtplib.SMTP_SSL(
                config.SMTP_HOST, config.SMTP_PORT, timeout=15, context=ctx
            ) as s:
                s.login(config.SMTP_USER, config.SMTP_PASS)
                s.send_message(msg)
        else:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as s:
                s.starttls(context=ctx)
                s.login(config.SMTP_USER, config.SMTP_PASS)
                s.send_message(msg)
        return True
    except Exception as e:  # noqa: BLE001
        log.error("Fallo enviando email a %s: %s", msg["To"], e)
        return False
