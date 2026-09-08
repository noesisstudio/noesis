"""Consumo observado: aislamiento, datos incompletos y fallo no bloqueante."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from noesis import config, db
from noesis.adapters import extraction


class AdminUsageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = patch.multiple(config, DATABASE_URL="",
            DB_PATH=Path(self.temp.name) / "test.db",
            BACKUP_DIR=Path(self.temp.name) / "backups",
            DOCS_PATH=Path(self.temp.name) / "docs")
        self.settings.start()
        db.init_db()
        self.business = db.create_business("Prueba", "test@example.com")["id"]

    def tearDown(self):
        self.settings.stop()
        self.temp.cleanup()

    def test_usage_is_scoped_and_unknown_cost_is_not_zero(self):
        other = db.create_business("Otro", "other@example.com")["id"]
        event = {"provider": "anthropic", "model": "test", "in": 100,
                 "out": 20, "estimated_cost_usd": 0.01, "duration_ms": 10}
        db.record_product_event(self.business, "ai_usage", json.dumps(event))
        db.record_product_event(other, "ai_usage", json.dumps(event))
        db.record_product_event(self.business, "ai_usage", json.dumps({
            **event, "estimated_cost_usd": None, "in": -2, "out": "invalid"}))
        result = db.admin_api_usage(self.business)
        item = result["rows"][0]
        self.assertEqual(item["calls"], 2)
        self.assertEqual(item["input_tokens"], 100)
        self.assertEqual(item["estimated_cost_usd"], 0.01)
        self.assertEqual(item["unpriced_calls"], 1)
        self.assertEqual(result["month"], date.today().strftime("%Y-%m"))
        self.assertEqual(db.admin_api_usage(self.business, "2000-01")["rows"], [])

    def test_invalid_period_is_rejected(self):
        for month in ("2026-13", "all", "2026-01%"):
            with self.assertRaises(ValueError):
                db.admin_api_usage(self.business, month)

    def test_invoice_pages_preserve_scope_and_legacy_list(self):
        client = db.add_client("Cliente", business_id=self.business)
        other = db.create_business("Otro", "other@example.com")["id"]
        foreign = db.add_client("Ajeno", business_id=other)
        for number in range(5):
            db.add_invoice(client["id"], str(number), 10, business_id=self.business)
        db.add_invoice(foreign["id"], "Ajena", 10, business_id=other)
        self.assertEqual(len(db.list_invoices(self.business)), 5)
        first = db.list_invoices(self.business, limit=2)
        second = db.list_invoices(self.business, limit=2, offset=2)
        self.assertFalse({r["id"] for r in first} & {r["id"] for r in second})
        self.assertEqual(len(second), 2)
        self.assertEqual(db.list_invoices(self.business, client_id=foreign["id"]), [])
        self.assertEqual(len(db.list_invoices(self.business, client_id=client["id"])), 5)

    def test_invoice_page_validation(self):
        for kwargs in ({"limit": 0}, {"limit": 201}, {"limit": True},
                       {"offset": 1}, {"limit": 2, "offset": -1}):
            with self.assertRaises(ValueError):
                db.list_invoices(self.business, **kwargs)

    def test_cost_conversion_assumption_is_explicit(self):
        with patch.object(config, "COST_USD_TO_EUR", 0.85):
            self.assertEqual(db.admin_api_usage(self.business)["usd_to_eur_assumption"], 0.85)

    def test_admin_endpoint_authentication_privacy_and_phone(self):
        from starlette.testclient import TestClient
        from noesis.web import auth, server

        password = "test-only-password"  # pragma: allowlist secret
        db.create_user("admin@example.com", auth.hash_password(password), self.business)
        with db.get_conn() as conn:
            conn.execute("UPDATE businesses SET whatsapp_phone=? WHERE id=?",
                         ("+34600000000", self.business))
        endpoint = f"/admin/cuentas/{self.business}/consumo"
        with (patch.object(config, "ADMIN_EMAIL", "admin@example.com"),
              patch.object(config, "ADMIN_REQUIRE_GOOGLE_OAUTH", False),
              patch.object(server, "start_scheduler", lambda: None),
              TestClient(server.app) as client):
            self.assertEqual(client.get(endpoint).status_code, 403)
            client.post("/login", data={"email": "admin@example.com", "password": password})
            response = client.get(endpoint)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertNotIn("+34600000000", response.text)
            self.assertEqual(client.get(endpoint + "?month=wrong").status_code, 400)
            self.assertEqual(client.get("/admin/cuentas/999999/consumo").status_code, 404)
            page = client.get(f"/admin/cuentas/{self.business}")
            self.assertEqual(page.status_code, 200)
            self.assertIn("+34600000000", page.text)
            self.assertIn("Consumo por API y modelo", page.text)
            self.assertIn('data-admin-nav="consumo"', page.text)
            self.assertIn('data-admin-panel="canales"', page.text)
            overview = client.get("/admin")
            self.assertEqual(overview.status_code, 200)
            for section in ("resumen", "cuentas", "captacion", "finanzas", "operaciones", "ingenieria", "privacidad"):
                self.assertIn(f'data-admin-nav="{section}"', overview.text)
            self.assertIn('data-admin-account-search', overview.text)
            self.assertIn(f'/admin/cuentas/{self.business}#entregas', overview.text)
            self.assertIn('Sin costes registrados', overview.text)
            self.assertIn('no es una cohorte', overview.text)
            self.assertNotIn('Embudo de adquisición', overview.text)
            self.assertNotIn('dept-ic', overview.text)
            self.assertIn('Lectura del sistema:', overview.text)
            invoices = f"/api/{self.business}/invoices"
            self.assertEqual(client.get(invoices + "?limit=2").status_code, 200)
            self.assertEqual(client.get(invoices + "?limit=0").status_code, 422)
            self.assertEqual(client.get(invoices + "?offset=1").status_code, 400)
        self.assertTrue(any(e["event_type"] == "admin.api_usage_viewed"
                            for e in db.list_security_events()))

    def test_extraction_usage_records_tokens_without_document_content(self):
        client = MagicMock()
        response = SimpleNamespace(usage=SimpleNamespace(input_tokens=100, output_tokens=20))
        client.messages.create.return_value = response
        with patch.multiple(config, FALLBACK_INPUT_USD_PER_MTOK=3,
                            FALLBACK_OUTPUT_USD_PER_MTOK=15):
            self.assertIs(extraction._message(client, business_id=self.business,
                model="test", messages=[{"text": "private-content"}]), response)
        item = db.admin_api_usage(self.business)["rows"][0]
        self.assertEqual(item["estimated_cost_usd"], 0.0006)
        self.assertEqual(item["input_tokens"], 100)

    def test_telemetry_failure_does_not_break_extraction(self):
        client = MagicMock()
        response = SimpleNamespace(usage=SimpleNamespace(input_tokens=1, output_tokens=1))
        client.messages.create.return_value = response
        with patch.object(db, "record_product_event", side_effect=RuntimeError("test")):
            self.assertIs(extraction._message(client, business_id=self.business,
                                             model="test"), response)

    def test_whatsapp_does_not_promote_low_confidence_invoice(self):
        from noesis.web import whatsapp
        from noesis.documents import service

        document = {"id": 99, "kind": "documento", "classification": {
            "kind": "factura_recibida", "applied_kind": "documento", "confidence": 40}}
        with (patch.object(whatsapp, "_download_media", return_value=b"%PDF-test"),
              patch.object(service, "upload", return_value=document),
              patch.object(service, "associate_context", return_value={}),
              patch.object(service, "invoice_draft") as draft,
              patch.object(whatsapp, "send") as send):
            result = whatsapp._ingest_document({"id": self.business}, "34600000000", {
                "media_document_id": "test", "media_document_mime": "application/pdf"})
        draft.assert_not_called()
        self.assertEqual(result["classification"], "documento")
        self.assertIn("pendiente de revisar", send.call_args.args[1])

    def test_uncertain_photo_is_not_reinterpreted_as_expense(self):
        from noesis.web import whatsapp
        from noesis.documents import service

        document = {"id": 99, "kind": "documento", "classification": {
            "kind": "factura_recibida", "applied_kind": "documento", "confidence": 40}}
        with (patch.object(whatsapp, "_download_media", return_value=b"image"),
              patch.object(service, "upload", return_value=document),
              patch.object(service, "associate_context", return_value={}),
              patch.object(extraction, "extract_expense") as expense,
              patch.object(service, "invoice_draft") as draft,
              patch.object(whatsapp, "send")):
            result = whatsapp._ingest_image({"id": self.business}, "34600000000",
                                            {"image_id": "test"})
        expense.assert_not_called()
        draft.assert_not_called()
        self.assertFalse(result["pending"])

    def test_unreadable_received_invoice_is_not_called_issued(self):
        from noesis.web import whatsapp
        from noesis.documents import service

        document = {"id": 99, "kind": "factura_recibida", "classification": {
            "kind": "factura_recibida", "applied_kind": "factura_recibida"}}
        with (patch.object(whatsapp, "_download_media", return_value=b"image"),
              patch.object(service, "upload", return_value=document),
              patch.object(service, "associate_context", return_value={}),
              patch.object(service, "invoice_draft", return_value=None),
              patch.object(whatsapp, "send") as send):
            result = whatsapp._ingest_image({"id": self.business}, "34600000000",
                                            {"image_id": "test"})
        self.assertFalse(result["pending"])
        self.assertIn("no la he registrado", send.call_args.args[1])
        self.assertNotIn("emitida por ti", send.call_args.args[1])
