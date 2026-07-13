"""Regresión del cierre de trabajo: campo, conformidad y factura borrador."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from noesis import config, db, migrations


SIGNATURE = "data:image/png;base64,iVBORw0KGgo="


class FieldWorkflowTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_db = config.DB_PATH
        self.old_docs = config.DOCS_PATH
        self.old_url = config.DATABASE_URL
        config.DATABASE_URL = ""
        config.DB_PATH = Path(self.tempdir.name) / "field.db"
        config.DOCS_PATH = Path(self.tempdir.name) / "uploads"
        db.init_db()
        self.business = db.create_business("Instalaciones Norte", "norte@example.com")
        self.other = db.create_business("Negocio ajeno", "otro@example.com")
        self.client = db.add_client("Clara", business_id=self.business["id"])
        self.worker = db.create_worker(self.business["id"], "Mario")
        self.project = db.add_project(
            "Reforma cocina", 2000, client_id=self.client["id"],
            business_id=self.business["id"],
        )
        self.job = db.add_job(
            self.client["id"], "Instalar fregadero",
            scheduled_for=f"{date.today().isoformat()}T09:00",
            price_estimate=300, project_id=self.project["id"],
            worker_id=self.worker["id"], business_id=self.business["id"],
        )

    def tearDown(self):
        config.DB_PATH = self.old_db
        config.DOCS_PATH = self.old_docs
        config.DATABASE_URL = self.old_url
        self.tempdir.cleanup()

    def test_field_cost_completion_and_draft_are_connected(self):
        material = db.add_job_material(
            self.job["id"], "Latiguillo", 2, 12.5,
            worker_id=self.worker["id"], business_id=self.business["id"],
        )
        self.assertEqual(material["total"], 25)
        db.add_job_update(
            self.job["id"], "incidencia", "Faltaba una llave de paso.",
            worker_id=self.worker["id"], business_id=self.business["id"],
        )

        completion = db.complete_job(
            self.job["id"], worker_id=self.worker["id"],
            summary="Instalado y probado.", business_id=self.business["id"],
        )
        self.assertEqual(completion["status"], "pendiente_cliente")
        self.assertIsNotNone(completion["invoice_id"])
        invoice = db.get_invoice(completion["invoice_id"], self.business["id"])
        self.assertEqual(invoice["status"], "borrador")
        self.assertEqual(invoice["base"], 300)
        self.assertEqual(db.get_job(self.job["id"], self.business["id"])["status"], "hecho")

        project = db.get_project(self.project["id"], self.business["id"])
        self.assertEqual(project["field_material_cost"], 25)
        self.assertEqual(project["actual_cost"], 25)
        view = db.job_field_view(self.job["id"], self.business["id"])
        self.assertEqual(view["material_cost"], 25)
        self.assertEqual(len(view["updates"]), 1)

        confirmed = db.confirm_job_completion(
            self.job["id"], self.client["id"], business_id=self.business["id"],
            accepted=True, customer_name="Clara Pérez", signature_data=SIGNATURE,
        )
        self.assertEqual(confirmed["status"], "confirmado")
        self.assertTrue(confirmed["signature_hash"])
        with self.assertRaises(ValueError):
            db.complete_job(
                self.job["id"], worker_id=self.worker["id"],
                business_id=self.business["id"],
            )

    def test_workers_and_clients_cannot_cross_businesses(self):
        foreign_worker = db.create_worker(self.other["id"], "Ajeno")
        with self.assertRaises(ValueError):
            db.add_job_material(
                self.job["id"], "No entra", 1, 1,
                worker_id=foreign_worker["id"], business_id=self.business["id"],
            )
        db.complete_job(
            self.job["id"], worker_id=self.worker["id"],
            business_id=self.business["id"],
        )
        foreign_client = db.add_client("Otro", business_id=self.other["id"])
        with self.assertRaises(ValueError):
            db.confirm_job_completion(
                self.job["id"], foreign_client["id"],
                business_id=self.business["id"], accepted=True,
                customer_name="Otro", signature_data=SIGNATURE,
            )
        self.assertIsNone(db.job_field_view(self.job["id"], self.other["id"]))

    def test_worker_and_client_portals_complete_the_cycle(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        worker_token = db.get_or_create_worker_token(
            self.business["id"], self.worker["id"]
        )
        portal_token = db.get_or_create_portal_token(
            self.business["id"], self.client["id"]
        )
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                page = client.get(f"/t/{worker_token}")
                self.assertEqual(page.status_code, 200)
                self.assertIn("Cerrar trabajo", page.text)
                material = client.post(
                    f"/t/{worker_token}/jobs/{self.job['id']}/materials",
                    json={"description": "Silicona", "quantity": 1, "unit_cost": 8},
                )
                self.assertEqual(material.status_code, 200)
                photo = client.post(
                    f"/t/{worker_token}/jobs/{self.job['id']}/photos",
                    files={"file": ("final.jpg", b"imagen", "image/jpeg")},
                    data={"note": "Resultado final"},
                )
                self.assertEqual(photo.status_code, 200)
                done = client.post(
                    f"/t/{worker_token}/jobs/{self.job['id']}/complete",
                    json={"summary": "Terminado y comprobado."},
                )
                self.assertEqual(done.status_code, 200)

                portal = client.get(f"/p/{portal_token}")
                self.assertEqual(portal.status_code, 200)
                self.assertIn("Trabajos por confirmar", portal.text)
                accepted = client.post(
                    f"/p/{portal_token}/jobs/{self.job['id']}/completion",
                    json={
                        "accepted": True, "customer_name": "Clara Pérez",
                        "signature_data": SIGNATURE,
                    },
                )
                self.assertEqual(accepted.status_code, 200)
        self.assertEqual(
            db.get_job_completion(self.job["id"], self.business["id"])["status"],
            "confirmado",
        )

    def test_migrations_25_to_27_roundtrip(self):
        self.assertEqual(migrations.current_version(), 27)
        self.assertEqual(migrations.downgrade(25), 25)
        with db.get_conn() as conn:
            missing_preferences = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='client_preferences'"
            ).fetchone()
            missing_integrations = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='integration_settings'"
            ).fetchone()
        self.assertIsNone(missing_preferences)
        self.assertIsNone(missing_integrations)
        self.assertEqual(migrations.upgrade(), 27)

    def test_integrations_are_controllable_and_isolated_by_business(self):
        from unittest.mock import patch

        with patch.object(config, "ANTHROPIC_API_KEY", "test-key"):
            self.assertFalse(db.integration_enabled(
                self.business["id"], "ai_external", available=True
            ))
            enabled = db.update_integration_setting(
                self.business["id"], "ai_external", "enabled"
            )
            self.assertEqual(enabled["mode"], "enabled")
            self.assertTrue(db.integration_enabled(
                self.business["id"], "ai_external", available=True
            ))
            saved = db.update_integration_setting(
                self.business["id"], "ai_external", "disabled"
            )
            self.assertEqual(saved["mode"], "disabled")
            self.assertFalse(db.integration_enabled(
                self.business["id"], "ai_external", available=True
            ))
            self.assertFalse(db.integration_enabled(
                self.other["id"], "ai_external", available=True
            ))

        interested = db.update_integration_setting(
            self.business["id"], "banking", "requested"
        )
        self.assertEqual(interested["mode"], "requested")
        catalog = {item["key"]: item for item in db.integration_catalog(
            self.business["id"]
        )}
        self.assertEqual(catalog["banking"]["state"], "requested")
        self.assertEqual(
            db.integration_setting(self.other["id"], "banking"), None
        )

    def test_operational_health_explains_business_queues(self):
        message = db.enqueue_whatsapp_message(
            business_id=self.business["id"], to_phone="34600111222",
            message_type="text", text_body="Hola",
        )
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE whatsapp_outbox SET status='failed', last_error='Meta 500' "
                "WHERE id=? AND business_id=?",
                (message["id"], self.business["id"]),
            )
        health = db.business_operational_health(self.business["id"])
        self.assertEqual(health["level"], "error")
        self.assertEqual(health["whatsapp"]["failed"], 1)
        self.assertIn("classified_month", health["documents"])
        self.assertTrue(any(
            item["area"] == "WhatsApp" for item in health["attention"]
        ))

    def test_confirmed_client_preferences_and_observed_metrics_are_explained(self):
        saved = db.update_client_preferences(
            self.client["id"], self.business["id"],
            preferred_channel="whatsapp", preferred_contact_window="manana",
            payment_terms_days=15, note="Prefiere mensajes breves.",
        )
        self.assertEqual(saved["source"], "manual")
        db.add_job_material(
            self.job["id"], "Pieza", 1, 20, worker_id=self.worker["id"],
            business_id=self.business["id"],
        )
        completion = db.complete_job(
            self.job["id"], worker_id=self.worker["id"],
            business_id=self.business["id"],
        )
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE invoices SET status='enviada', number='2026/0001', issued_at=? "
                "WHERE id=? AND business_id=?",
                (date.today().isoformat(), completion["invoice_id"], self.business["id"]),
            )
        invoice = db.get_invoice(completion["invoice_id"], self.business["id"])
        db.add_invoice_payment(
            invoice["id"], invoice["total"], business_id=self.business["id"]
        )
        insight = db.client_insights(self.business["id"])[0]
        self.assertEqual(insight["preferences"]["preferred_channel"], "whatsapp")
        self.assertEqual(insight["known_direct_cost"], 20)
        self.assertEqual(insight["known_revenue_base"], 300)
        self.assertEqual(insight["known_margin"], 280)
        self.assertEqual(insight["sources"]["preferences"], "Confirmado manualmente")
        self.assertIsNone(
            db.get_client_preferences(self.client["id"], self.other["id"])
        )


if __name__ == "__main__":
    unittest.main()
