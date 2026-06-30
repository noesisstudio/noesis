from __future__ import annotations

import hashlib
import hmac
import inspect
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from noesis import config, db, migrations, nlu
from noesis.web import auth, chat, reports, whatsapp


class BackendTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        self.original_backup_dir = config.BACKUP_DIR
        self.original_database_url = config.DATABASE_URL
        config.DATABASE_URL = ""
        config.DB_PATH = Path(self.tempdir.name) / "test.db"
        config.BACKUP_DIR = Path(self.tempdir.name) / "backups"
        db.init_db()

    def tearDown(self):
        config.DB_PATH = self.original_db_path
        config.BACKUP_DIR = self.original_backup_dir
        config.DATABASE_URL = self.original_database_url
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

    def test_business_id_is_required_and_foreign_keys_block_cross_tenant_writes(self):
        business_a, client_a = self.make_business("Negocio A")
        business_b, client_b = self.make_business("Negocio B")

        scoped_functions = (
            db.get_client, db.find_client, db.list_clients, db.get_job,
            db.jobs_for_date, db.get_invoice, db.list_invoices,
            db.pending_payments, db.list_expenses, db.month_billing,
            db.get_quote, db.list_quotes, db.tax_quarter,
        )
        for function in scoped_functions:
            with self.subTest(function=function.__name__):
                parameter = inspect.signature(function).parameters["business_id"]
                self.assertIs(parameter.default, inspect.Parameter.empty)

        self.assertIsNone(db.get_client(client_b["id"], business_a["id"]))
        with self.assertRaises(ValueError):
            db.add_job(
                client_b["id"], "Cruce por API", business_id=business_a["id"]
            )

        with self.assertRaises(db.IntegrityError):
            with db.get_conn() as conn:
                conn.execute(
                    "INSERT INTO jobs "
                    "(business_id, client_id, description, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (business_a["id"], client_b["id"], "Cruce", "2026-06-30"),
                )

        own_job = db.add_job(
            client_a["id"], "Trabajo propio", business_id=business_a["id"]
        )
        with self.assertRaises(db.IntegrityError):
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE jobs SET client_id=? WHERE id=? AND business_id=?",
                    (client_b["id"], own_job["id"], business_a["id"]),
                )
        self.assertEqual(
            db.get_job(own_job["id"], business_a["id"])["client_id"],
            client_a["id"],
        )
        self.assertIsNone(db.get_job(own_job["id"], business_b["id"]))

    def test_versioned_migrations_can_move_down_and_up(self):
        self.assertEqual(migrations.current_version(), migrations.LATEST_VERSION)
        self.assertEqual(migrations.downgrade(1), 1)
        self.assertEqual(migrations.current_version(), 1)
        self.assertEqual(migrations.upgrade(), migrations.LATEST_VERSION)

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

    def test_nlu_extended_synonyms_stay_local(self):
        # Más formas naturales que el cerebro local resuelve gratis (sin IA).
        self.assertEqual(nlu.parse("compré 30 de tornillos")[0], "registrar_gasto")
        self.assertEqual(nlu.parse("me he gastado 45 en gasolina")[0], "registrar_gasto")
        self.assertEqual(nlu.parse("¿qué trabajos tengo hoy?")[0], "ver_agenda")
        self.assertEqual(nlu.parse("tengo facturas pendientes de cobrar")[0],
                         "ver_cobros_pendientes")
        self.assertEqual(nlu.parse("¿cómo voy este mes?")[0], "resumen_negocio")

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

    def test_activation_tracks_first_value_and_first_payment(self):
        business = db.create_business("Clima Norte", "clima@example.com", "Climatización")
        first = db.activation_snapshot(business["id"])
        self.assertEqual(first["progress"], 0)
        self.assertFalse(first["activated"])

        db.update_business_profile(
            business["id"], sector="Climatización", team_size="2-5",
            province="Asturias", primary_goal="facturar",
        )
        db.update_fiscal(
            business["id"], nif="B12345678", address="Calle Taller 1"
        )
        client = db.add_client(
            "Hotel Costa", nif="A12345678", address="Avenida Mar 4",
            business_id=business["id"],
        )
        db.add_job(
            client["id"], "Revisión de climatización",
            scheduled_for=date.today().isoformat(), business_id=business["id"],
        )
        invoice = db.add_invoice(
            client["id"], "Mantenimiento", 180, business_id=business["id"]
        )

        activated = db.activation_snapshot(business["id"])
        self.assertTrue(activated["activated"])
        self.assertFalse(activated["outcome_reached"])
        self.assertEqual(activated["progress"], 67)

        db.issue_invoice(invoice["id"], business["id"])
        db.mark_invoice_paid(invoice["id"], business["id"])
        db.set_whatsapp_status(business["id"], "conectado", phone="600123456")
        completed = db.activation_snapshot(business["id"])
        self.assertTrue(completed["outcome_reached"])
        self.assertEqual(completed["progress"], 100)

        db.record_product_event(business["id"], "activation_test")
        exported = db.export_business_data(business["id"])
        self.assertEqual(exported["product_events"][0]["event_name"], "activation_test")

    def test_portal_token_reuse_resolve_and_revoke(self):
        business, client = self.make_business()
        token = db.get_or_create_portal_token(business["id"], client["id"])
        # Mismo enlace mientras esté vigente (el autónomo puede reenviarlo).
        self.assertEqual(
            token, db.get_or_create_portal_token(business["id"], client["id"])
        )
        self.assertEqual(
            db.resolve_portal_token(token),
            {"business_id": business["id"], "client_id": client["id"]},
        )
        self.assertIsNone(db.resolve_portal_token("token-inventado"))
        db.revoke_portal_tokens(client["id"], business["id"])
        self.assertIsNone(db.resolve_portal_token(token))

    def test_unbilled_jobs_detects_clears_and_isolates(self):
        from datetime import timedelta

        business_a, client_a = self.make_business("Negocio A")
        business_b, client_b = self.make_business("Negocio B")
        past = (date.today() - timedelta(days=2)).isoformat()
        db.add_job(client_a["id"], "Cambio de grifo", scheduled_for=past,
                   business_id=business_a["id"])
        db.add_job(client_b["id"], "Trabajo ajeno", scheduled_for=past,
                   business_id=business_b["id"])

        unbilled = db.unbilled_jobs(business_a["id"])
        self.assertEqual(len(unbilled), 1)
        self.assertEqual(unbilled[0]["client_name"], client_a["name"])
        # No filtra trabajos de otro negocio.
        self.assertTrue(all(j["business_id"] == business_a["id"] for j in unbilled))

        # Cancelado no cuenta.
        dead = db.add_job(client_a["id"], "Visita anulada", scheduled_for=past,
                          business_id=business_a["id"])
        db.update_job_status(dead["id"], "cancelado", business_a["id"])
        self.assertEqual(len(db.unbilled_jobs(business_a["id"])), 1)

        # Al facturar a ese cliente, el trabajo deja de aparecer.
        db.add_invoice(client_a["id"], "Cambio de grifo", 120,
                       business_id=business_a["id"])
        self.assertEqual(db.unbilled_jobs(business_a["id"]), [])

    def test_daily_plan_is_prioritised_and_explained(self):
        from datetime import timedelta

        business, client = self.make_business()
        db.add_job(client["id"], "Cambio de grifo",
                   scheduled_for=(date.today() - timedelta(days=3)).isoformat(),
                   business_id=business["id"])
        plan_reply = chat.handle(business["id"], "¿cuál es mi plan de hoy?")
        self.assertEqual(plan_reply["source"], "local")
        self.assertIn("plan para hoy", plan_reply["reply"].lower())
        self.assertIn("Por qué", plan_reply["reply"])  # explica el motivo

        unbilled_reply = chat.handle(business["id"], "¿qué tengo sin facturar?")
        self.assertIn("Cambio de grifo", unbilled_reply["reply"])

    def test_copilot_ledger_records_and_transitions(self):
        from datetime import timedelta

        business, client = self.make_business()
        db.add_job(client["id"], "Cambio de grifo",
                   scheduled_for=(date.today() - timedelta(days=3)).isoformat(),
                   business_id=business["id"])
        # daily_plan registra recomendaciones y devuelve sus ids.
        plan = chat.daily_plan(business["id"])
        actionable = [p for p in plan if p.get("id")]
        self.assertTrue(actionable)
        # Idempotente: regenerar el plan no duplica recomendaciones activas.
        chat.daily_plan(business["id"])
        stats = db.recommendation_stats(business["id"])
        self.assertEqual(stats["total"], len(actionable))
        self.assertEqual(stats["recomendado"], len(actionable))
        # Transición recomendado -> completado.
        rec_id = actionable[0]["id"]
        done = db.set_recommendation_status(rec_id, business["id"], "completado")
        self.assertEqual(done["status"], "completado")
        self.assertEqual(db.recommendation_stats(business["id"])["completado"], 1)
        # Estado inválido y aislamiento entre negocios.
        with self.assertRaises(ValueError):
            db.set_recommendation_status(rec_id, business["id"], "raro")
        other, _ = self.make_business("Otro Negocio")
        self.assertIsNone(
            db.set_recommendation_status(rec_id, other["id"], "descartado"))

    def test_branding_validation_and_portal_exposure(self):
        business, client = self.make_business()
        db.update_branding(business["id"], template="editorial", brand_color="#7a1f4b")
        biz = db.get_business(business["id"])
        self.assertEqual(biz["invoice_template"], "editorial")
        self.assertEqual(db.business_brand_color(biz), "#7a1f4b")
        with self.assertRaises(ValueError):
            db.update_branding(business["id"], template="rara")
        with self.assertRaises(ValueError):
            db.update_branding(business["id"], brand_color="rojo")
        self.assertEqual(db.business_initials("Reformas Garcia"), "RG")
        # El portal expone color e iniciales del negocio que atiende, aislado.
        view = db.client_portal_view(business["id"], client["id"])
        self.assertEqual(view["business"]["brand_color"], "#7a1f4b")
        self.assertTrue(view["business"]["initials"])

    def test_portal_token_never_crosses_clients(self):
        business_a, client_a = self.make_business("Negocio A")
        business_b, client_b = self.make_business("Negocio B")
        # Un token solo se emite para un cliente del propio negocio.
        self.assertIsNone(
            db.get_or_create_portal_token(business_a["id"], client_b["id"])
        )
        token_a = db.get_or_create_portal_token(business_a["id"], client_a["id"])
        ref = db.resolve_portal_token(token_a)
        self.assertEqual(ref["business_id"], business_a["id"])
        self.assertEqual(ref["client_id"], client_a["id"])
        self.assertNotEqual(ref["business_id"], business_b["id"])


class PortalHttpTestCase(BackendTestCase):
    """El portal público (/p/) no debe dejar que un cliente toque documentos de otro."""

    def _quote(self, business_id, client_id):
        quote = db.add_quote(client_id, "Reforma de baño", 1000, business_id=business_id)
        db.mark_quote_sent(quote["id"], business_id)
        return quote

    def test_portal_accept_is_isolated_and_closes_cycle(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business_a, client_a = self.make_business("Negocio A")
        business_b, client_b = self.make_business("Negocio B")
        quote_a = self._quote(business_a["id"], client_a["id"])
        quote_b = self._quote(business_b["id"], client_b["id"])
        token_a = db.get_or_create_portal_token(business_a["id"], client_a["id"])

        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                self.assertEqual(client.get(f"/p/{token_a}").status_code, 200)
                self.assertEqual(client.get("/p/token-malo").status_code, 404)

                # Con el token de A NO se puede aceptar el presupuesto de B.
                blocked = client.post(
                    f"/p/{token_a}/quotes/{quote_b['id']}/accept",
                    follow_redirects=False,
                )
                self.assertEqual(blocked.status_code, 303)
                self.assertIn("nojusto", blocked.headers["location"])
                self.assertEqual(
                    db.get_quote(quote_b["id"], business_b["id"])["status"], "enviado"
                )

                # Aceptar el propio presupuesto cierra el ciclo: crea factura borrador.
                ok = client.post(
                    f"/p/{token_a}/quotes/{quote_a['id']}/accept",
                    follow_redirects=False,
                )
                self.assertEqual(ok.status_code, 303)
                self.assertIn("aceptado", ok.headers["location"])
                accepted = db.get_quote(quote_a["id"], business_a["id"])
                self.assertEqual(accepted["status"], "aceptado")
                self.assertTrue(accepted["invoice_id"])
                self.assertEqual(
                    db.get_invoice(accepted["invoice_id"], business_a["id"])["status"],
                    "borrador",
                )

    def test_saas_health_and_profile_onboarding_flow(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                self.assertEqual(client.get("/health").json()["status"], "ok")
                self.assertEqual(client.get("/ready").json()["status"], "ready")
                signup = client.post(
                    "/onboarding/signup",
                    data={
                        "name": "Clima Piloto",
                        "email": "piloto@example.com",
                        "password": "password-segura-123",
                        "sector": "Climatización",
                    },
                    follow_redirects=False,
                )
                self.assertEqual(signup.status_code, 303)
                setup_url = signup.headers["location"]
                self.assertIn("/onboarding/setup/", setup_url)
                self.assertEqual(client.get(setup_url).status_code, 200)

                profile = client.post(
                    setup_url,
                    data={
                        "sector": "Climatización",
                        "team_size": "2-5",
                        "primary_goal": "facturar",
                        "province": "Valencia",
                    },
                    follow_redirects=False,
                )
                self.assertEqual(profile.status_code, 303)
                self.assertIn("/onboarding/whatsapp/", profile.headers["location"])

                other = db.create_business(
                    "Negocio ajeno", "ajeno@example.com", "Electricidad"
                )
                forbidden = client.get(
                    f"/onboarding/setup/{other['id']}", follow_redirects=False
                )
                self.assertEqual(forbidden.status_code, 303)
                self.assertEqual(forbidden.headers["location"], "/login")

                user = db.get_user_by_email("piloto@example.com")
                db.set_password(user["id"], auth.hash_password("password-cambiada-456"))
                revoked = client.get(setup_url, follow_redirects=False)
                self.assertEqual(revoked.status_code, 303)
                self.assertEqual(revoked.headers["location"], "/login")


if __name__ == "__main__":
    unittest.main()
