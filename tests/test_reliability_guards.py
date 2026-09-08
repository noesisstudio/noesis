"""Regresiones sin red ni credenciales: diagnóstico y extracción conservadora."""
import json
import unittest
import os
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import MagicMock, patch

from noesis import config, integration_check
from noesis.adapters import extraction


class ReliabilityGuardsTestCase(unittest.TestCase):
    def test_scheduler_shutdown_waits_and_can_be_repeated(self):
        from noesis.web import scheduler

        active = MagicMock()
        active.running = True
        with patch.object(scheduler, "_scheduler", active):
            scheduler.stop_scheduler()
            self.assertIsNone(scheduler._scheduler)
            scheduler.stop_scheduler()
        active.shutdown.assert_called_once_with(wait=True)

    def test_lifespan_stops_jobs_before_closing_database_even_on_error(self):
        import asyncio
        from noesis.web import server

        calls = []
        async def exercise():
            async with server.lifespan(server.app):
                raise RuntimeError("simulated shutdown")

        with (
            patch.object(server, "_startup"),
            patch.object(server, "stop_scheduler", side_effect=lambda: calls.append("jobs")),
            patch.object(server.db, "close_pool", side_effect=lambda: calls.append("database")),
            self.assertRaises(RuntimeError),
        ):
            asyncio.run(exercise())
        self.assertEqual(calls, ["jobs", "database"])

    def test_backup_infrastructure_is_private_and_upload_only(self):
        root = Path(__file__).resolve().parents[1]
        template = json.loads((root / "infra/backups/aws-s3.json").read_text(encoding="utf-8"))
        resources = template["Resources"]
        bucket = resources["BackupBucket"]
        self.assertEqual(bucket["DeletionPolicy"], "Retain")
        self.assertTrue(all(bucket["Properties"]["PublicAccessBlockConfiguration"].values()))
        self.assertTrue(bucket["Properties"]["ObjectLockEnabled"])
        self.assertNotIn("Default", template["Parameters"]["RetentionDays"])
        policy = resources["BackupWriter"]["Properties"]["Policies"][0]["PolicyDocument"]
        self.assertEqual(policy["Statement"][0]["Action"], "s3:PutObject")
        self.assertFalse(any(r["Type"] == "AWS::IAM::AccessKey" for r in resources.values()))

    def test_whatsapp_checker_normalizes_number_and_does_not_load_disabled_env(self):
        from scripts import check_whatsapp

        with (
            patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1",
                                    "WHATSAPP_TOKEN": " test-token\n",
                                    "WHATSAPP_PHONE_ID": " 12345\n",
                                    "META_GRAPH_VERSION": " v23.0\n"}),
            patch.object(check_whatsapp.Path, "read_text") as read,
            patch.object(check_whatsapp, "revisar_token", return_value="app"),
            patch.object(check_whatsapp, "revisar_numero") as number,
            patch.object(check_whatsapp, "revisar_suscripcion"),
            patch.object(check_whatsapp, "revisar_plantillas"),
            patch.object(check_whatsapp, "revisar_webhook"),
            patch.object(check_whatsapp, "revisar_firma"),
            patch("builtins.print"),
        ):
            self.assertEqual(check_whatsapp.main([]), 0)
        read.assert_not_called()
        number.assert_called_once_with("test-token", "v23.0", "12345")

    def test_multiple_extraction_does_not_return_first_amount(self):
        payload = json.dumps([{"total": 121}, {"total": 242}])
        response = SimpleNamespace(content=[SimpleNamespace(type="text", text=payload)])
        client = MagicMock()
        client.messages.create.return_value = response
        with (
            patch.object(config, "ANTHROPIC_API_KEY", "test-only"),
            patch.object(extraction.anthropic, "Anthropic", return_value=client),
        ):
            self.assertIsNone(extraction.extract_invoice(b"%PDF-test", "application/pdf"))
            self.assertIsNone(extraction.extract_expense(b"test", "image/jpeg"))
            classified = extraction.classify_document(b"%PDF-test", "application/pdf", "varias.pdf")
        self.assertTrue(classified["multiple_documents"])
        self.assertEqual(classified["kind"], "documento")
        self.assertIn("por separado", classified["reason"])

    def test_read_only_checker_has_explicit_user_agent(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = b'{}'
        with patch.object(integration_check, "urlopen", return_value=response) as get:
            integration_check._json_get("https://example.test", {"api-key": "test-only"})
        request = get.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertIn("Bynoesis", request.get_header("User-agent"))
        self.assertIsNone(request.data)
