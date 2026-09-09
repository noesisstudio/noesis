"""Consumo observado: aislamiento, datos incompletos y fallo no bloqueante."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from noesis import config, db


class AdminWorkspaceTests(unittest.TestCase):
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

    def test_cost_conversion_assumption_is_explicit(self):
        with patch.object(config, "COST_USD_TO_EUR", 0.85):
            self.assertEqual(db.admin_api_usage(self.business)["usd_to_eur_assumption"], 0.85)

    def test_phone_identity_lookup_finds_the_team_card_and_frees_it(self):
        # Cuentas solo enseña el teléfono del titular: una ficha de Equipo con
        # ese número era invisible y bloqueaba la vinculación sin explicación.
        from starlette.testclient import TestClient
        from noesis.web import auth, server

        password = "test-only-password"  # pragma: allowlist secret
        db.create_user("admin@example.com", auth.hash_password(password), self.business)
        worker = db.create_worker(self.business, "Marta", phone="611459476")

        with (patch.object(config, "ADMIN_EMAIL", "admin@example.com"),
              patch.object(config, "ADMIN_REQUIRE_GOOGLE_OAUTH", False),
              patch.object(server, "start_scheduler", lambda: None),
              TestClient(server.app) as client):
            self.assertEqual(
                client.post("/admin/whatsapp/identidad",
                            data={"telefono": "611459476"},
                            follow_redirects=False).status_code, 303)
            client.post("/login",
                        data={"email": "admin@example.com", "password": password})

            # La redirección lleva ya al panel con el resultado de la consulta.
            panel = client.post("/admin/whatsapp/identidad",
                                data={"telefono": "611 459 476"})
            self.assertIn("Marta", panel.text)
            self.assertIn(f"Ficha de Equipo #{worker['id']}", panel.text)

            libre = client.post("/admin/whatsapp/identidad/liberar",
                                data={"telefono": "611459476"})
            self.assertIsNone(
                db.get_worker(worker["id"], self.business)["phone_norm"]
            )
            self.assertIn("queda libre", libre.text)
            self.assertIn("está libre", libre.text)

        eventos = {e["event_type"] for e in db.list_security_events()}
        self.assertIn("admin.whatsapp_identity_viewed", eventos)
        self.assertIn("admin.whatsapp_identity_released", eventos)

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
        self.assertTrue(any(e["event_type"] == "admin.api_usage_viewed"
                            for e in db.list_security_events()))
