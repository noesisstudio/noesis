from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noesis import config, db, internal_brain
from noesis.adapters import email as email_adapter
from noesis.web import auth, chat, whatsapp


class InternalBrainTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        self.original_database_url = config.DATABASE_URL
        config.DATABASE_URL = ""
        config.DB_PATH = Path(self.tempdir.name) / "test.db"
        db.init_db()
        self.business = db.create_business("Fontanería Norte", "owner@example.com")
        db.update_fiscal(
            self.business["id"], nif="A12345678", address="Calle Norte 1"
        )
        self.client = db.add_client(
            "Ana Pérez",
            phone="600111222",
            email="ana@example.com",
            nif="B12345678",
            address="Calle Cliente 2",
            zone="Badalona",
            business_id=self.business["id"],
        )

    def tearDown(self):
        config.DB_PATH = self.original_db_path
        config.DATABASE_URL = self.original_database_url
        self.tempdir.cleanup()

    def _pending_invoice(self):
        draft = db.add_invoice(
            self.client["id"],
            "Cambio de grifo",
            100,
            business_id=self.business["id"],
        )
        return db.issue_invoice(draft["id"], self.business["id"])

    def test_payment_message_is_local_and_waits_for_owner_confirmation(self):
        invoice = self._pending_invoice()

        result = chat.handle(
            self.business["id"],
            "Envía un recordatorio de cobro a Ana Pérez",
            channel="whatsapp",
            actor_phone="699000111",
        )

        self.assertEqual(result["source"], "local_internal")
        self.assertIn(invoice["number"], result["reply"])
        self.assertIn("121,00 €", result["reply"])
        self.assertIn("Todavía no lo he enviado", result["reply"])
        pending = db.get_pending_action(self.business["id"], "699000111")
        self.assertEqual(pending["kind"], "send_communication")
        payload = json.loads(pending["payload"])
        self.assertEqual(payload["entity_id"], invoice["id"])
        self.assertEqual(payload["client_id"], self.client["id"])

    def test_confirmed_payment_message_uses_existing_durable_template(self):
        invoice = self._pending_invoice()
        chat.handle(
            self.business["id"],
            "Mándale el recordatorio de cobro a Ana Pérez",
            channel="whatsapp",
            actor_phone="699000111",
        )
        pending = db.get_pending_action(self.business["id"], "699000111")

        with patch.object(whatsapp, "send_template", return_value=True) as send:
            reply = whatsapp._execute_pending(
                db.get_business(self.business["id"]), "699000111", pending
            )

        self.assertIn("Enviado a Ana Pérez", reply)
        self.assertEqual(send.call_args.args[0], "34600111222")
        self.assertEqual(
            send.call_args.args[1], config.WHATSAPP_TEMPLATE_PAYMENT_REMINDER
        )
        self.assertIn(invoice["number"], send.call_args.args[2])
        self.assertIsNone(
            db.get_pending_action(self.business["id"], "699000111")
        )

    def test_quote_and_appointment_use_real_entities_not_generated_values(self):
        quote = db.add_quote(
            self.client["id"],
            "Instalación de termo",
            800,
            business_id=self.business["id"],
        )
        quote = db.mark_quote_sent(quote["id"], self.business["id"])
        when = (date.today() + timedelta(days=2)).isoformat() + "T10:30"
        job = db.add_job(
            self.client["id"],
            "Revisar instalación",
            when,
            business_id=self.business["id"],
        )

        quote_result = chat.handle(
            self.business["id"],
            "Redacta un seguimiento del presupuesto para Ana Pérez",
        )
        appointment_result = chat.handle(
            self.business["id"],
            "Prepara un recordatorio de la cita de Ana Pérez",
        )

        self.assertEqual(quote_result["source"], "local_internal")
        self.assertIn(quote["number"], quote_result["reply"])
        self.assertIn("968,00 €", quote_result["reply"])
        self.assertEqual(appointment_result["source"], "local_internal")
        self.assertIn("Revisar instalación", appointment_result["reply"])
        self.assertEqual(appointment_result["draft"]["entity_id"], job["id"])

    def test_custom_email_is_redacted_then_sent_only_after_yes(self):
        result = chat.handle(
            self.business["id"],
            "Envía un correo a Ana Pérez diciendo que llegaré diez minutos tarde",
            channel="whatsapp",
            actor_phone="699000111",
        )
        pending = db.get_pending_action(self.business["id"], "699000111")
        self.assertIn("diez minutos tarde", result["reply"])
        self.assertIsNotNone(pending)

        with patch.object(email_adapter, "send_email", return_value=True) as send:
            reply = whatsapp._execute_pending(
                db.get_business(self.business["id"]), "699000111", pending
            )

        self.assertIn("Enviado a Ana Pérez", reply)
        self.assertEqual(send.call_args.args[0], "ana@example.com")
        self.assertIn("diez minutos tarde", send.call_args.args[2])

    def test_failed_delivery_keeps_confirmation_for_safe_retry(self):
        chat.handle(
            self.business["id"],
            "Envía un correo a Ana Pérez diciendo que llegaré diez minutos tarde",
            channel="whatsapp",
            actor_phone="699000111",
        )
        pending = db.get_pending_action(self.business["id"], "699000111")

        with patch.object(email_adapter, "send_email", return_value=False):
            reply = whatsapp._execute_pending(
                db.get_business(self.business["id"]), "699000111", pending
            )

        self.assertIn("SÍ para reintentar", reply)
        self.assertIsNotNone(
            db.get_pending_action(self.business["id"], "699000111")
        )

    def test_web_can_draft_but_never_sends_or_creates_confirmation(self):
        self._pending_invoice()

        result = chat.handle(
            self.business["id"],
            "Envía un recordatorio de cobro a Ana Pérez",
            channel="web",
        )

        self.assertEqual(result["source"], "local_internal")
        self.assertIn("pídemelo por tu WhatsApp", result["reply"])
        self.assertIsNone(
            db.get_pending_action(self.business["id"], "699000111")
        )

    def test_ambiguous_or_foreign_data_is_never_selected(self):
        other = db.create_business("Otro negocio", "other@example.com")
        db.update_fiscal(other["id"], nif="A87654321", address="Calle Otra 1")
        foreign_client = db.add_client(
            "Cliente Privado", phone="611222333", nif="B87654321",
            address="Calle Privada 2", business_id=other["id"]
        )
        foreign_invoice = db.add_invoice(
            foreign_client["id"], "Trabajo privado", 900, business_id=other["id"]
        )
        db.issue_invoice(foreign_invoice["id"], other["id"])

        result = chat.handle(
            self.business["id"], "Redacta un recordatorio de cobro"
        )

        self.assertEqual(result["source"], "local_internal")
        self.assertIn("Dime el cliente", result["reply"])
        self.assertNotIn("Cliente Privado", result["reply"])
        self.assertNotIn("1.089,00", result["reply"])

    def test_catalan_preference_applies_to_internal_writing(self):
        self._pending_invoice()
        db.update_language(self.business["id"], "ca")

        result = internal_brain.prepare_response(
            self.business["id"],
            "Redacta un recordatori de cobrament per a Ana Pérez",
            channel="web",
        )

        self.assertIsNotNone(result)
        self.assertIn("Et recordem", result["reply"])
        self.assertIn("Gràcies", result["reply"])

    def test_generic_invoice_send_is_not_hijacked_by_the_composer(self):
        self.assertFalse(internal_brain.handles("Envía la factura 12 al cliente"))
        self.assertFalse(internal_brain.handles("Redacta una factura para Ana"))
        self.assertTrue(internal_brain.handles("Escribe a Ana que llegaré tarde"))
        self.assertTrue(
            internal_brain.handles(
                "Envía un mensaje de recordatorio de cobro a Ana Pérez"
            )
        )

    def test_authenticated_web_chat_returns_internal_draft(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        db.create_user(
            "brain-owner@example.com",
            auth.hash_password("password-segura-123"),
            self.business["id"],
        )
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                login = client.post(
                    "/login",
                    data={
                        "email": "brain-owner@example.com",
                        "password": "password-segura-123",
                    },
                    follow_redirects=False,
                )
                self.assertEqual(login.status_code, 303)
                response = client.post(
                    f"/api/{self.business['id']}/chat",
                    json={
                        "message": (
                            "Redacta un correo a Ana Pérez diciendo que llegaré "
                            "diez minutos tarde"
                        )
                    },
                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source"], "local_internal")
        self.assertIn("No lo he enviado", response.json()["reply"])


if __name__ == "__main__":
    unittest.main()
