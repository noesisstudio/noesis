from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from noesis import config, readiness


class ReadinessTestCase(unittest.TestCase):
    def test_report_never_contains_secret_values(self):
        secret = "secreto-super-largo-que-no-debe-aparecer"
        with (
            patch.dict(os.environ, {
                "WHATSAPP_TOKEN": secret,
                "NOESIS_WHATSAPP_NUMBER": "+34123456789",
            }, clear=True),
            patch.object(config, "SECRET_KEY", secret),
            patch.object(config, "IS_PRODUCTION", False),
            patch.object(config, "BASE_URL", "https://app.example"),
            patch.object(config, "DATABASE_URL", "postgresql://oculta"),
            patch.object(config, "ANTHROPIC_API_KEY", secret),
            patch.object(config, "LOCAL_AI_BASE_URL", ""),
            patch.object(config, "LOCAL_AI_MODEL", ""),
            patch.object(config, "COMPAT_AI_BASE_URL", ""),
            patch.object(config, "COMPAT_AI_MODEL", ""),
            patch.object(config, "COMPAT_AI_API_KEY", ""),
            patch.object(config, "COMPAT_AI_LEGAL_NAME", ""),
            patch.object(config, "COMPAT_AI_REGION", ""),
        ):
            report = readiness.collect_readiness(check_database=False)

        serialized = json.dumps(report, ensure_ascii=False)
        self.assertNotIn(secret, serialized)
        whatsapp = [
            item for item in report["checks"] if item["area"] == "whatsapp"
        ][0]
        self.assertEqual(whatsapp["status"], "blocker")

    def test_missing_optional_services_are_warnings_not_fake_readiness(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(config, "SECRET_KEY", "x" * 40),
            patch.object(config, "IS_PRODUCTION", False),
            patch.object(config, "BASE_URL", "https://app.example"),
            patch.object(config, "DATABASE_URL", "postgresql://oculta"),
            patch.object(config, "ANTHROPIC_API_KEY", ""),
            patch.object(config, "LOCAL_AI_BASE_URL", ""),
            patch.object(config, "LOCAL_AI_MODEL", ""),
            patch.object(config, "COMPAT_AI_BASE_URL", ""),
            patch.object(config, "COMPAT_AI_MODEL", ""),
            patch.object(config, "COMPAT_AI_API_KEY", ""),
            patch.object(config, "COMPAT_AI_LEGAL_NAME", ""),
            patch.object(config, "COMPAT_AI_REGION", ""),
            patch.object(config, "ADMIN_EMAIL", ""),
        ):
            report = readiness.collect_readiness(check_database=False)

        self.assertTrue(report["ready"])
        self.assertEqual(report["counts"]["blocker"], 0)
        self.assertGreater(report["counts"]["warning"], 0)

    def test_external_compatible_provider_requires_https_and_legal_identity(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(config, "SECRET_KEY", "x" * 40),
            patch.object(config, "IS_PRODUCTION", False),
            patch.object(config, "BASE_URL", "https://app.example"),
            patch.object(config, "DATABASE_URL", "postgresql://oculta"),
            patch.object(config, "ANTHROPIC_API_KEY", ""),
            patch.object(config, "LOCAL_AI_BASE_URL", ""),
            patch.object(config, "LOCAL_AI_MODEL", ""),
            patch.object(config, "COMPAT_AI_BASE_URL", "http://api.example/v1"),
            patch.object(config, "COMPAT_AI_MODEL", "modelo"),
            patch.object(config, "COMPAT_AI_API_KEY", "secreta"),
            patch.object(config, "COMPAT_AI_LEGAL_NAME", "Proveedor, SL"),
            patch.object(config, "COMPAT_AI_REGION", "UE"),
            patch.object(config, "ADMIN_EMAIL", "admin@example.com"),
        ):
            report = readiness.collect_readiness(check_database=False)

        ai_checks = [item for item in report["checks"] if item["area"] == "ia"]
        self.assertTrue(any(item["status"] == "blocker" for item in ai_checks))
        self.assertTrue(any("HTTPS" in item["action"] for item in ai_checks))

    def test_required_admin_oauth_is_a_blocker_when_credentials_are_missing(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(config, "ADMIN_REQUIRE_GOOGLE_OAUTH", True),
            patch.object(config, "GOOGLE_OAUTH_CLIENT_ID", ""),
            patch.object(config, "GOOGLE_OAUTH_CLIENT_SECRET", ""),
        ):
            report = readiness.collect_readiness(check_database=False)
        google = next(
            item for item in report["checks"] if item["area"] == "google"
        )
        self.assertEqual(google["status"], "blocker")

    def test_production_blocks_wrong_domain_and_missing_legal_identity(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(config, "IS_PRODUCTION", True),
            patch.object(config, "BASE_URL", "https://app.bynoesis.com"),
            patch.object(config, "CANONICAL_PUBLIC_HOST", "bynoesis.com"),
            patch.object(config, "LEGAL_NAME", ""),
            patch.object(config, "LEGAL_NIF", ""),
            patch.object(config, "LEGAL_ADDRESS", ""),
            patch.object(config, "LEGAL_EMAIL", ""),
            patch.object(config, "PUBLIC_SIGNUP_ENABLED", False),
            patch.object(config, "ADMIN_REQUIRE_GOOGLE_OAUTH", False),
        ):
            report = readiness.collect_readiness(check_database=False)

        by_area = {item["area"]: item for item in report["checks"]}
        self.assertEqual(by_area["dominio"]["status"], "blocker")
        self.assertEqual(by_area["legal"]["status"], "blocker")
        self.assertEqual(by_area["alta pública"]["status"], "warning")
        self.assertFalse(report["ready"])

    def test_open_production_requires_operational_services(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(config, "IS_PRODUCTION", True),
            patch.object(config, "PUBLIC_SIGNUP_ENABLED", True),
            patch.object(config, "ADMIN_REQUIRE_GOOGLE_OAUTH", False),
            patch.object(config, "ANTHROPIC_API_KEY", ""),
        ):
            report = readiness.collect_readiness(check_database=False)

        by_area = {item["area"]: item for item in report["checks"]}
        for area in (
            "copias", "whatsapp", "correo", "stripe", "audio",
            "lectura de imágenes", "seguridad documental",
        ):
            self.assertEqual(by_area[area]["status"], "blocker", area)


if __name__ == "__main__":
    unittest.main()
