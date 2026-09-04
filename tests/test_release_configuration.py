"""Configuración de publicación alineada con el proveedor efectivo de correo."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from noesis import config
from noesis.web.routers.pages import _legal_context


class EffectiveMailProviderTestCase(TestCase):
    def test_brevo_ignores_unused_smtp_metadata(self):
        with patch.multiple(
            config, BREVO_API_KEY="test-api", SMTP_HOST="smtp.example.com",
            SMTP_PROVIDER_NAME="", SMTP_PROVIDER_REGION="", COMPAT_AI_BASE_URL="",
            BACKUP_S3_ENDPOINT="", BACKUP_S3_BUCKET="", BACKUP_S3_ACCESS_KEY="",
            BACKUP_S3_SECRET_KEY="",
        ):
            self.assertTrue(config.legal_provider_context_ready())
            with patch.multiple(config, SMTP_PROVIDER_NAME="Proveedor antiguo", SMTP_PROVIDER_REGION="Antigua"):
                context = _legal_context(SimpleNamespace(session={}))
            self.assertEqual(context["smtp_provider_name"], "Brevo")
            self.assertEqual(context["smtp_provider_region"], "")

    def test_smtp_without_brevo_requires_identification(self):
        with patch.multiple(
            config, BREVO_API_KEY="", SMTP_HOST="smtp.example.com",
            SMTP_PROVIDER_NAME="", SMTP_PROVIDER_REGION="", COMPAT_AI_BASE_URL="",
            BACKUP_S3_ENDPOINT="", BACKUP_S3_BUCKET="", BACKUP_S3_ACCESS_KEY="",
            BACKUP_S3_SECRET_KEY="",
        ):
            self.assertFalse(config.legal_provider_context_ready())
            with patch.multiple(config, SMTP_PROVIDER_NAME="Correo prueba", SMTP_PROVIDER_REGION="UE"):
                self.assertTrue(config.legal_provider_context_ready())
                context = _legal_context(SimpleNamespace(session={}))
            self.assertEqual(context["smtp_provider_name"], "Correo prueba")
            self.assertEqual(context["smtp_provider_region"], "UE")
