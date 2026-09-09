"""Guardias del canal central, los números de negocio y el equipo de campo."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noesis import config, db
from noesis.web import whatsapp


class WhatsappMultichannelTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_db_path = config.DB_PATH
        self.old_docs_path = config.DOCS_PATH
        self.old_database_url = config.DATABASE_URL
        config.DATABASE_URL = ""
        config.DB_PATH = Path(self.tempdir.name) / "test.db"
        config.DOCS_PATH = Path(self.tempdir.name) / "uploads"
        db.init_db()

    def tearDown(self):
        config.DB_PATH = self.old_db_path
        config.DOCS_PATH = self.old_docs_path
        config.DATABASE_URL = self.old_database_url
        self.tempdir.cleanup()

    def business(self, name: str) -> dict:
        return db.create_business(name, f"{name.lower()}@example.com")

    @staticmethod
    def payload(
        message_id: str, recipient_id: str, sender: str, text: str,
        waba_id: str = "waba-1",
    ) -> dict:
        return {
            "entry": [{
                "id": waba_id,
                "changes": [{"value": {
                    "metadata": {
                        "phone_number_id": recipient_id,
                        "display_phone_number": "+34 900 000 000",
                    },
                    "contacts": [{
                        "wa_id": sender, "profile": {"name": "Juan Cliente"}
                    }],
                    "messages": [{
                        "id": message_id, "from": sender, "type": "text",
                        "text": {"body": text},
                    }],
                }}],
            }]
        }

    def test_same_sender_is_isolated_by_recipient_business_number(self):
        business_a = self.business("NegocioA")
        business_b = self.business("NegocioB")
        connection_a = db.create_whatsapp_connection(
            business_a["id"], waba_id="1001", phone_number_id="2001",
            status="active", receptionist_enabled=True,
        )
        connection_b = db.create_whatsapp_connection(
            business_b["id"], waba_id="1002", phone_number_id="2002",
            status="active", receptionist_enabled=True,
        )
        with patch.object(whatsapp, "send", return_value=True):
            whatsapp.handle_inbound(self.payload(
                "wamid.a", "2001", "34600111222", "Necesito presupuesto", "1001"
            ))
            whatsapp.handle_inbound(self.payload(
                "wamid.b", "2002", "34600111222", "Tengo una avería", "1002"
            ))

        inbox_a = db.list_whatsapp_inbox(business_a["id"])
        inbox_b = db.list_whatsapp_inbox(business_b["id"])
        self.assertEqual([item["meta_message_id"] for item in inbox_a], ["wamid.a"])
        self.assertEqual([item["meta_message_id"] for item in inbox_b], ["wamid.b"])
        self.assertNotEqual(inbox_a[0]["contact_id"], inbox_b[0]["contact_id"])
        self.assertEqual(connection_a["business_id"], business_a["id"])
        self.assertEqual(connection_b["business_id"], business_b["id"])

    def test_unknown_recipient_is_ignored_without_creating_data(self):
        business = self.business("Receptor")
        with patch.object(whatsapp, "send", return_value=True) as sender:
            result = whatsapp.handle_inbound(
                self.payload("wamid.unknown", "999999", "34600111222", "Hola")
            )
        self.assertTrue(result["results"][0]["ignored"])
        self.assertEqual(db.list_whatsapp_inbox(business["id"]), [])
        sender.assert_not_called()

    def test_worker_cost_waits_for_owner_and_margin_is_private(self):
        business = self.business("Equipo")
        client = db.add_client("Cliente", business_id=business["id"])
        project = db.add_project(
            "Instalación", 8000, client_id=client["id"], business_id=business["id"]
        )
        worker = db.create_worker(
            business["id"], "Marta", phone="600111222",
            can_submit_costs=True, can_view_assigned_budget=False,
        )
        job = db.add_job(
            client["id"], "Montaje", project_id=project["id"],
            worker_id=worker["id"], business_id=business["id"],
        )

        private = whatsapp._try_worker_clock("600111222", f"MARGEN #{job['id']}")
        self.assertIn("no muestra márgenes", private["reply"])
        submitted = whatsapp._try_worker_clock(
            "600111222", f"COSTE #{job['id']} 25,40 material eléctrico"
        )
        submission_id = submitted["submission_id"]
        with db.get_conn() as conn:
            before = conn.execute(
                "SELECT COUNT(*) AS total FROM job_materials WHERE business_id=?",
                (business["id"],),
            ).fetchone()["total"]
        self.assertEqual(before, 0)

        db.resolve_worker_submission(
            submission_id, business["id"], decision="accepted"
        )
        db.resolve_worker_submission(
            submission_id, business["id"], decision="accepted"
        )
        with db.get_conn() as conn:
            after = conn.execute(
                "SELECT COUNT(*) AS total FROM job_materials WHERE business_id=?",
                (business["id"],),
            ).fetchone()["total"]
        self.assertEqual(after, 1)

    def test_outbound_uses_the_business_phone_number_id(self):
        business = self.business("Saliente")
        connection = db.create_whatsapp_connection(
            business["id"], waba_id="3001", phone_number_id="4001",
            status="active", receptionist_enabled=True,
        )
        message = whatsapp.queue_text(
            "34600111222", "Respuesta", business_id=business["id"],
            connection_id=connection["id"],
        )
        with patch.object(whatsapp, "_post_to_meta", return_value="wamid.sent") as post:
            result = whatsapp.process_outbox(only_ids=[message["id"]], limit=1)
        self.assertEqual(result[0]["status"], "sent")
        self.assertEqual(post.call_args.args[1], "4001")

    def test_link_explains_the_worker_clash_and_keeps_the_code_alive(self):
        # El titular escribe desde un móvil que ya está de alta en Equipo. El
        # mensaje tiene que decir qué pasa y dónde se arregla, y el código no
        # puede quemarse por un choque que no depende del código.
        business = self.business("Titular")
        worker = db.create_worker(business["id"], "Marta")
        db.bind_worker_phone(business["id"], worker["access_code"], "600111222")

        enlace = whatsapp.start_link(business["id"])
        respuesta = whatsapp._try_link("34600111222", f"BYNOESIS {enlace['code']}")
        self.assertIn("Marta", respuesta)
        self.assertIn("Equipo", respuesta)
        self.assertEqual(
            db.get_business(business["id"])["whatsapp_status"], "no_conectado"
        )

        # Quitado el teléfono de la ficha, el mismo código sigue valiendo.
        db.update_worker(worker["id"], business["id"], phone="")
        conectado = whatsapp._try_link("34600111222", f"BYNOESIS {enlace['code']}")
        self.assertIn("WhatsApp conectado", conectado)
        self.assertEqual(
            db.get_business(business["id"])["whatsapp_status"], "conectado"
        )

    def test_link_points_to_the_business_that_already_holds_the_phone(self):
        primero = self.business("Primero")
        segundo = self.business("Segundo")
        db.set_whatsapp_status(primero["id"], "conectado", phone="600111222")

        enlace = whatsapp.start_link(segundo["id"])
        respuesta = whatsapp._try_link("34600111222", f"BYNOESIS {enlace['code']}")
        self.assertIn("Primero", respuesta)
        self.assertEqual(
            db.get_business(segundo["id"])["whatsapp_status"], "no_conectado"
        )

    def test_central_phone_cannot_mix_owner_and_worker_identities(self):
        owner_business = self.business("Titular")
        team_business = self.business("Empresa")
        db.set_whatsapp_status(
            owner_business["id"], "conectado", phone="600111222"
        )
        worker = db.create_worker(team_business["id"], "Marta")
        with self.assertRaisesRegex(ValueError, "identidad"):
            db.bind_worker_phone(
                team_business["id"], worker["access_code"], "600111222"
            )

        other_worker = db.create_worker(
            team_business["id"], "Pau", phone="600333444"
        )
        with self.assertRaisesRegex(ValueError, "identifica a un trabajador"):
            db.set_whatsapp_status(
                owner_business["id"], "conectado", phone="600333444"
            )
        self.assertEqual(
            db.central_whatsapp_identity("600333444")["worker"]["id"],
            other_worker["id"],
        )


if __name__ == "__main__":
    unittest.main()
