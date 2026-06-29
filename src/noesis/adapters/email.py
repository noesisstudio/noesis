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

from .. import config

log = logging.getLogger("noesis.email")


def available() -> bool:
    return bool(config.SMTP_HOST and config.SMTP_USER and config.SMTP_PASS)


def send_email(to: str, subject: str, body: str) -> bool:
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
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as s:
            s.starttls(context=ctx)
            s.login(config.SMTP_USER, config.SMTP_PASS)
            s.send_message(msg)
        return True
    except Exception as e:  # noqa: BLE001
        log.error("Fallo enviando email a %s: %s", to, e)
        return False
