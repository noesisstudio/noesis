from __future__ import annotations

import hashlib
import hmac
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from noesis import config, db, nlu
from noesis.web import auth, chat, reports, whatsapp


class BackendTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        self.original_backup_dir = config.BACKUP_DIR
        config.DB_PATH = Path(self.tempdir.name) / "test.db"
        config.BACKUP_DIR = Path(self.tempdir.name) / "backups"
        db.init_db()

    def tearDown(self):
        config.DB_PATH = self.original_db_path
        config.BACKUP_DIR = self.original_backup_dir
        self.tempdir.cleanup()

    def make_business(self, name="Taller Seguro"):
        business = db.create_business(name, f"{name.lower().replace(' ', '')}@example.com")
        db.update_fiscal(
            business["id"], nif="A12345678", address="Calle Principal 1"
        )
        client = db.add_client(
            "Cliente Fiscal", nif="B12345678", address="Calle Cliente 2",
            business_id=business["id"],
        )
        return business, client

    def test_environment_booleans_are_explicit(self):
        with patch.dict(os.environ, {"NOESIS_TEST_BOOL": "false"}):
            self.assertFalse(config.env_bool("NOESIS_TEST_BOOL"))
        with patch.dict(os.environ, {"NOESIS_TEST_BOOL": "1"}):
            self.assertTrue(config.env_bool("NOESIS_TEST_BOOL"))
        with patch.dict(os.environ, {"NOESIS_TEST_BOOL": "quizas"}):
            with self.assertRaises(ValueError):
                config.env_bool("NOESIS_TEST_BOOL")

    def test_client_update_never_leaks_another_business(self):
        business_a, _ = self.make_business("Negocio A")
        business_b, _ = self.make_business("Negocio B")
        private = db.add_client(
            "Cliente privado", phone="699999999", business_id=business_b["id"]
        )

        result = db.update_client(private["id"], business_a["id"], name="Ataque")

        self.assertIsNone(result)
        self.assertEqual(
            db.get_client(private["id"], business_b["id"])["name"],
            "Cliente privado",
        )

    def test_invoice_issue_is_idempotent_and_immutable(self):
        business, client = self.make_business()
        invoice = db.add_invoice(
            client["id"], "Reparación", 100, business_id=business["id"]
        )

        first = db.issue_invoice(invoice["id"], business["id"])
        second = db.issue_invoice(invoice["id"], business["id"])

        self.assertEqual(first["number"], second["number"])
        self.assertEqual(first["recipient_nif"], "B12345678")
        self.assertFalse(db.delete_invoice(invoice["id"], business["id"]))
        self.assertEqual(
            db.mark_invoice_paid(invoice["id"], business["id"])["status"],
            "cobrada",
        )
        self.assertIsNone(db.mark_invoice_paid(invoice["id"], business["id"]))

    def test_quote_acceptance_is_idempotent(self):
        business, client = self.make_business()
        quote = db.add_quote(
            client["id"], "Instalación", 500, business_id=business["id"]
        )
        db.mark_quote_sent(quote["id"], business["id"])

        first = db.accept_quote(quote["id"], business["id"])
        second = db.accept_quote(quote["id"], business["id"])

        self.assertEqual(first["invoice"]["id"], second["invoice"]["id"])
        self.assertEqual(len(db.list_invoices(business["id"])), 1)

    def test_webhook_events_are_processed_once(self):
        self.assertTrue(db.claim_webhook_event("whatsapp", "wamid.1"))
        self.assertFalse(db.claim_webhook_event("whatsapp", "wamid.1"))

    def test_whatsapp_signature(self):
        payload = b'{"entry":[]}'
        old_secret, old_production = config.WHATSAPP_APP_SECRET, config.IS_PRODUCTION
        try:
            config.WHATSAPP_APP_SECRET = "secret"
            config.IS_PRODUCTION = True
            signature = "sha256=" + hmac.new(
                b"secret", payload, hashlib.sha256
            ).hexdigest()
            self.assertTrue(whatsapp.verify_signature(payload, signature))
            self.assertFalse(whatsapp.verify_signature(payload, "sha256=bad"))
        finally:
            config.WHATSAPP_APP_SECRET = old_secret
            config.IS_PRODUCTION = old_production

    def test_nlu_understands_tomorrow_morning_and_vat_included(self):
        parsed = nlu.parse_date("mañana por la mañana")
        self.assertIsNotNone(parsed)
        self.assertTrue(parsed.endswith("T09:00"))

        business, _ = self.make_business()
        result = chat.handle(
            business["id"],
            "factura a Juan por reparación 121 euros IVA incluido",
        )
        self.assertEqual(result["source"], "local")
        invoice = db.list_invoices(business["id"])[0]
        self.assertEqual(invoice["base"], 100.0)
        self.assertEqual(invoice["total"], 121.0)

    def test_invalid_tax_quarter_and_csv_formula(self):
        business, _ = self.make_business()
        with self.assertRaises(ValueError):
            db.tax_quarter(date.today().year, 5, business["id"])
        db.add_expense(
            "=CMD()", 10, category="@riesgo", business_id=business["id"]
        )
        csv_text = reports.costs_csv(business["id"])
        self.assertIn("'=CMD()", csv_text)
        self.assertIn("'@riesgo", csv_text)

    def test_password_change_revokes_existing_session_version(self):
        business, _ = self.make_business()
        user = db.create_user(
            "owner@example.com", auth.hash_password("password-segura-123"),
            business["id"],
        )
        old_version = user["session_version"]
        db.set_password(user["id"], auth.hash_password("password-nueva-456"))
        self.assertGreater(db.get_user(user["id"])["session_version"], old_version)


if __name__ == "__main__":
    unittest.main()
