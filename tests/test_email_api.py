"""Pruebas del envío de correo por API.

Railway bloquea la salida a los puertos de SMTP, así que en producción el correo
sale por HTTPS. Estas pruebas fijan el contrato con el proveedor y, sobre todo,
que sin clave se sigue usando SMTP como antes.
"""

from __future__ import annotations

import base64
import json
import unittest
from unittest.mock import patch

from noesis import config
from noesis.adapters import email as email_adapter


class _Respuesta:
    def __init__(self, status: int = 201):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class EmailApiTestCase(unittest.TestCase):
    def setUp(self):
        self.original = {
            name: getattr(config, name)
            for name in ("BREVO_API_KEY", "SMTP_FROM", "SMTP_HOST",
                         "SMTP_USER", "SMTP_PASS", "IS_PRODUCTION")
        }
        config.BREVO_API_KEY = "clave-de-prueba"  # pragma: allowlist secret
        config.SMTP_FROM = "Bynoesis <info@bynoesis.com>"
        config.IS_PRODUCTION = False

    def tearDown(self):
        for name, value in self.original.items():
            setattr(config, name, value)

    def _capturar(self, status: int = 201) -> dict:
        capturado: dict = {}

        def falso_urlopen(peticion, timeout=None):
            capturado["url"] = peticion.full_url
            capturado["cabeceras"] = {
                k.lower(): v for k, v in peticion.headers.items()
            }
            capturado["cuerpo"] = json.loads(peticion.data)
            return _Respuesta(status)

        capturado["patch"] = patch("urllib.request.urlopen", falso_urlopen)
        return capturado

    def test_sends_over_https_with_the_expected_payload(self):
        capturado = self._capturar()
        with capturado["patch"]:
            enviado = email_adapter.send_email(
                "cliente@ejemplo.com", "Asunto", "Cuerpo",
            )

        self.assertTrue(enviado)
        self.assertIn("brevo.com", capturado["url"])
        self.assertEqual(capturado["cabeceras"]["api-key"], config.BREVO_API_KEY)
        cuerpo = capturado["cuerpo"]
        # El remitente se separa en nombre y dirección, como pide la API.
        self.assertEqual(
            cuerpo["sender"], {"name": "Bynoesis", "email": "info@bynoesis.com"}
        )
        self.assertEqual(cuerpo["to"], [{"email": "cliente@ejemplo.com"}])
        self.assertEqual(cuerpo["textContent"], "Cuerpo")

    def test_invoices_travel_with_their_pdf_attached(self):
        pdf = b"%PDF-1.4 contenido"
        capturado = self._capturar()
        with capturado["patch"]:
            email_adapter.send_email(
                "cliente@ejemplo.com", "Tu factura", "Adjunta va",
                attachments=[("F-2026-001.pdf", pdf, "application", "pdf")],
            )

        adjunto = capturado["cuerpo"]["attachment"][0]
        self.assertEqual(adjunto["name"], "F-2026-001.pdf")
        self.assertEqual(base64.b64decode(adjunto["content"]), pdf)

    def test_invoice_helper_uses_the_configured_https_provider(self):
        pdf = b"%PDF-1.4 factura"
        capturado = self._capturar()
        with (
            capturado["patch"],
            patch.object(email_adapter, "_send_msg") as smtp,
        ):
            enviado = email_adapter.send_invoice_email(
                "cliente@ejemplo.com", "Taller", "2026/0042", "121,00 EUR", pdf
            )

        self.assertTrue(enviado)
        smtp.assert_not_called()
        adjunto = capturado["cuerpo"]["attachment"][0]
        self.assertEqual(adjunto["name"], "factura_2026-0042.pdf")
        self.assertEqual(base64.b64decode(adjunto["content"]), pdf)

    def test_a_rejection_is_reported_not_swallowed(self):
        import urllib.error

        def falla(peticion, timeout=None):
            raise urllib.error.HTTPError(
                peticion.full_url, 401, "Unauthorized", {},
                __import__("io").BytesIO(b'{"message":"Key not found"}'),
            )

        with patch("urllib.request.urlopen", falla):
            enviado = email_adapter.send_email("a@b.com", "Asunto", "Cuerpo")

        self.assertFalse(enviado)

    def test_without_api_key_it_falls_back_to_smtp(self):
        config.BREVO_API_KEY = ""
        config.SMTP_HOST = "smtp.ejemplo.com"
        config.SMTP_USER = "info@bynoesis.com"
        config.SMTP_PASS = "clave-smtp"  # pragma: allowlist secret

        with patch.object(email_adapter, "_send_msg", return_value=True) as smtp:
            enviado = email_adapter.send_email("a@b.com", "Asunto", "Cuerpo")

        self.assertTrue(enviado)
        smtp.assert_called_once()

    def test_without_any_provider_it_only_logs(self):
        config.BREVO_API_KEY = ""
        config.SMTP_HOST = ""
        config.SMTP_USER = ""
        config.SMTP_PASS = ""

        self.assertFalse(email_adapter.available())
        with patch.object(email_adapter, "_send_msg") as smtp:
            enviado = email_adapter.send_email("a@b.com", "Asunto", "Cuerpo")

        self.assertFalse(enviado)
        smtp.assert_not_called()


if __name__ == "__main__":
    unittest.main()
