from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from noesis import config, integration_check
from noesis.adapters import transcription


class IntegrationCheckTestCase(unittest.TestCase):
    def test_railway_requirements_include_private_ocr_runtime(self):
        requirements = (
            Path(__file__).resolve().parents[1] / "requirements.txt"
        ).read_text(encoding="utf-8").lower()

        for dependency in ("pypdf>", "pypdfium2>", "pytesseract>"):
            self.assertIn(dependency, requirements)

    def _stripe_config(self):
        return patch.multiple(
            config,
            STRIPE_SECRET_KEY="sk_test_example",  # pragma: allowlist secret
            STRIPE_WEBHOOK_SECRET="whsec_example",  # pragma: allowlist secret
            STRIPE_PRICE_AUTONOMO="price_auto_month",
            STRIPE_PRICE_PRO="price_pro_month",
            STRIPE_PRICE_PREMIUM="price_premium_month",
            STRIPE_PRICE_AUTONOMO_ANNUAL="price_auto_year",
            STRIPE_PRICE_PRO_ANNUAL="price_pro_year",
            STRIPE_PRICE_PREMIUM_ANNUAL="price_premium_year",
        )

    def test_ocr_requires_pdf_and_three_languages(self):
        with (
            patch.object(integration_check.ocr, "available", return_value=True),
            patch.object(integration_check.pdf_ocr, "available", return_value=True),
            patch.object(
                integration_check.ocr,
                "installed_languages",
                return_value=("cat", "spa"),
            ),
        ):
            result = integration_check._check_ocr()

        self.assertEqual(result.status, "blocker")
        self.assertIn("eng", result.summary)

    def test_brevo_checks_key_and_active_sender_without_sending(self):
        responses = [
            {"companyName": "Noesis"},
            {"senders": [{"email": "no-reply@bynoesis.com", "active": True}]},
        ]
        with (
            patch.object(config, "BREVO_API_KEY", "brevo-key"),
            patch.object(config, "SMTP_FROM", "Noesis <no-reply@bynoesis.com>"),
            patch.object(integration_check, "_json_get", side_effect=responses) as get,
        ):
            result = integration_check._check_brevo(network=True)

        self.assertEqual(result.status, "ok")
        self.assertEqual(get.call_count, 2)

    def test_google_requires_web_client_id_format(self):
        with (
            patch.object(config, "GOOGLE_OAUTH_CLIENT_ID", "client-wrong"),
            patch.object(config, "GOOGLE_OAUTH_CLIENT_SECRET", "secret"),
        ):
            result = integration_check._check_google(network=False)

        self.assertEqual(result.status, "blocker")

    def test_stripe_validates_the_six_prices_read_only(self):
        expected = {
            "price_auto_month": (2_900, "month"),
            "price_pro_month": (4_900, "month"),
            "price_premium_month": (9_900, "month"),
            "price_auto_year": (31_900, "year"),
            "price_pro_year": (53_900, "year"),
            "price_premium_year": (108_900, "year"),
        }

        def price_response(url, _headers):
            price_id = url.rsplit("/", 1)[-1]
            amount, interval = expected[price_id]
            return {
                "active": True,
                "currency": "eur",
                "unit_amount": amount,
                "recurring": {"interval": interval, "interval_count": 1},
                "tax_behavior": "exclusive",
                "livemode": False,
            }

        with self._stripe_config(), patch.object(
            integration_check, "_json_get", side_effect=price_response
        ) as get:
            result = integration_check._check_stripe(network=True)

        self.assertEqual(result.status, "ok")
        self.assertEqual(get.call_count, 6)

    def test_stripe_rejects_unspecified_tax_behavior(self):
        def price_response(_url, _headers):
            return {
                "active": True,
                "currency": "eur",
                "unit_amount": 2_900,
                "recurring": {"interval": "month", "interval_count": 1},
                "tax_behavior": "unspecified",
                "livemode": False,
            }

        with self._stripe_config(), patch.object(
            integration_check, "_json_get", side_effect=price_response
        ):
            result = integration_check._check_stripe(network=True)

        self.assertEqual(result.status, "blocker")
        self.assertIn("tax_behavior", result.summary)

    def test_groq_checks_that_the_whisper_model_exists(self):
        with (
            patch.object(config, "GROQ_API_KEY", "groq-key"),
            patch.object(config, "GROQ_WHISPER_MODEL", "whisper-model"),
            patch.object(
                integration_check,
                "_json_get",
                return_value={"data": [{"id": "whisper-model"}]},
            ),
        ):
            result = integration_check._check_groq(network=True)

        self.assertEqual(result.status, "ok")

    def test_backup_configuration_requires_https(self):
        with patch.multiple(
            config,
            BACKUP_S3_ENDPOINT="http://storage.example",
            BACKUP_S3_BUCKET="noesis",
            BACKUP_S3_ACCESS_KEY="access",
            BACKUP_S3_SECRET_KEY="secret",  # pragma: allowlist secret
        ):
            result = integration_check._check_backups()

        self.assertEqual(result.status, "blocker")

    def test_report_never_contains_credentials(self):
        exposed = "credential-that-must-not-appear"
        with (
            patch.object(config, "BREVO_API_KEY", exposed),
            patch.object(config, "SMTP_FROM", "Noesis <no-reply@bynoesis.com>"),
            patch.object(
                integration_check,
                "_json_get",
                side_effect=RuntimeError("HTTP 401"),
            ),
            patch.object(integration_check.ocr, "available", return_value=False),
            patch.object(integration_check.pdf_ocr, "available", return_value=False),
            patch.object(
                integration_check.ocr, "installed_languages", return_value=()
            ),
        ):
            report = integration_check.collect_checks(network=True)

        self.assertNotIn(exposed, json.dumps(report))


class MultilingualTranscriptionTestCase(unittest.TestCase):
    def _response(self):
        response = MagicMock()
        response.read.return_value = b'{"text":"feina acabada"}'
        return response

    def test_groq_auto_detects_language_by_default(self):
        with (
            patch.object(config, "GROQ_API_KEY", "key"),
            patch.object(config, "WHISPER_LANGUAGE", ""),
            patch("urllib.request.urlopen", return_value=self._response()) as request,
        ):
            transcription.GroqWhisperProvider().transcribe(b"audio", "nota.ogg")

        body = request.call_args.args[0].data
        self.assertNotIn(b'name="language"', body)

    def test_groq_accepts_an_explicit_language_hint(self):
        with (
            patch.object(config, "GROQ_API_KEY", "key"),
            patch.object(config, "WHISPER_LANGUAGE", "ca"),
            patch("urllib.request.urlopen", return_value=self._response()) as request,
        ):
            transcription.GroqWhisperProvider().transcribe(b"audio", "nota.ogg")

        body = request.call_args.args[0].data
        self.assertIn(b'name="language"', body)
        self.assertIn(b"\r\n\r\nca\r\n", body)


if __name__ == "__main__":
    unittest.main()
