from __future__ import annotations

import hashlib
import hmac
import inspect
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

from noesis import config, db, migrations, nlu, verifactu
from noesis.web import auth, chat, reports, scheduler, whatsapp


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

    def test_whatsapp_outbox_retries_with_backoff_and_traces_send(self):
        business, _ = self.make_business()
        point = datetime(2026, 6, 30, 10, 0, 0)
        message = whatsapp.queue_text(
            "34600111222",
            "Respuesta dentro de la ventana",
            business_id=business["id"],
            now=point,
        )

        with patch.object(
            whatsapp,
            "_post_to_meta",
            side_effect=[
                RuntimeError("Meta temporalmente no disponible"),
                "wamid.retry",
            ],
        ) as post:
            first = whatsapp.process_outbox(now=point)
            self.assertEqual(first[0]["status"], "retrying")
            retried = db.get_whatsapp_message(message["id"], business["id"])
            self.assertEqual(retried["attempts"], 1)
            self.assertEqual(retried["status"], "retrying")
            self.assertIn("temporalmente", retried["last_error"])

            self.assertEqual(
                whatsapp.process_outbox(now=point + timedelta(seconds=29)), []
            )
            second = whatsapp.process_outbox(
                now=point + timedelta(seconds=30)
            )

        self.assertEqual(post.call_count, 2)
        self.assertEqual(second[0]["status"], "sent")
        sent = db.get_whatsapp_message(message["id"], business["id"])
        self.assertEqual(sent["attempts"], 2)
        self.assertEqual(sent["status"], "sent")
        self.assertEqual(sent["meta_message_id"], "wamid.retry")
        self.assertIsNotNone(sent["sent_at"])

    def test_whatsapp_delivery_webhooks_are_idempotent_and_monotonic(self):
        business, _ = self.make_business()
        point = datetime(2026, 6, 30, 11, 0, 0)
        message = whatsapp.queue_text(
            "34600111222", "Hola", business_id=business["id"], now=point
        )
        with patch.object(whatsapp, "_post_to_meta", return_value="wamid.status"):
            whatsapp.process_outbox(now=point)

        delivered = {
            "message_id": "wamid.status",
            "status": "delivered",
            "timestamp": "1782817260",
        }
        first = whatsapp.handle_inbound(delivered)
        duplicate = whatsapp.handle_inbound(delivered)
        read = whatsapp.handle_inbound({
            "message_id": "wamid.status",
            "status": "read",
            "timestamp": "1782817320",
        })

        self.assertTrue(first["results"][0]["updated"])
        self.assertTrue(duplicate["results"][0]["duplicate"])
        self.assertTrue(read["results"][0]["updated"])
        traced = db.get_whatsapp_message(message["id"], business["id"])
        self.assertEqual(traced["status"], "read")
        self.assertIsNotNone(traced["delivered_at"])
        self.assertIsNotNone(traced["read_at"])

    def test_whatsapp_duplicate_inbound_does_not_repeat_effects(self):
        business, _ = self.make_business()
        db.set_whatsapp_status(business["id"], "conectado", phone="600111222")
        payload = {
            "id": "wamid.inbound",
            "from": "34600111222",
            "text": "resumen",
        }
        with (
            patch.object(chat, "handle", return_value={"reply": "Todo bien"}) as handle,
            patch.object(whatsapp, "send", return_value=True) as send,
        ):
            first = whatsapp.handle_inbound(payload)
            duplicate = whatsapp.handle_inbound(payload)

        self.assertEqual(first["processed"], 1)
        self.assertTrue(duplicate["results"][0]["duplicate"])
        handle.assert_called_once_with(business["id"], "resumen")
        send.assert_called_once()

    def test_whatsapp_proactives_use_approved_template_and_stable_key(self):
        business, _ = self.make_business()
        db.set_whatsapp_status(business["id"], "conectado", phone="600111222")
        with (
            patch.object(scheduler, "daily_summary_text", return_value="Tu resumen"),
            patch.object(whatsapp, "send_template", return_value=True) as template,
            patch.object(whatsapp, "send") as free_text,
        ):
            scheduler.send_daily_summaries()

        free_text.assert_not_called()
        args, kwargs = template.call_args
        self.assertEqual(args[1], config.WHATSAPP_TEMPLATE_DAILY_SUMMARY)
        self.assertEqual(args[2], ["Tu resumen"])
        self.assertEqual(kwargs["business_id"], business["id"])
        self.assertIn(f":{business['id']}", kwargs["idempotency_key"])

    def test_whatsapp_outbox_is_idempotent_and_isolated_by_business(self):
        business_a, _ = self.make_business("Negocio A")
        business_b, _ = self.make_business("Negocio B")
        first = whatsapp.queue_template(
            "34600111222",
            config.WHATSAPP_TEMPLATE_DAILY_SUMMARY,
            ["Resumen"],
            business_id=business_a["id"],
            idempotency_key=f"daily:2026-06-30:{business_a['id']}",
        )
        repeated = whatsapp.queue_template(
            "34600111222",
            config.WHATSAPP_TEMPLATE_DAILY_SUMMARY,
            ["Resumen"],
            business_id=business_a["id"],
            idempotency_key=f"daily:2026-06-30:{business_a['id']}",
        )

        self.assertEqual(first["id"], repeated["id"])
        self.assertIsNone(db.get_whatsapp_message(first["id"], business_b["id"]))
        self.assertEqual(
            db.get_whatsapp_message(first["id"], business_a["id"])["message_type"],
            "template",
        )
        with self.assertRaises(ValueError):
            whatsapp.queue_template(
                "34600999888",
                config.WHATSAPP_TEMPLATE_DAILY_SUMMARY,
                ["Otro resumen"],
                business_id=business_b["id"],
                idempotency_key=f"daily:2026-06-30:{business_a['id']}",
            )

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
                        "acepto": "1",
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


class WorkerDataTestCase(unittest.TestCase):
    setUp = BackendTestCase.setUp
    tearDown = BackendTestCase.tearDown
    make_business = BackendTestCase.make_business

    def test_workers_assignment_and_tenant_isolation(self):
        business_a, client_a = self.make_business("Equipo A")
        business_b, client_b = self.make_business("Equipo B")
        worker_a = db.create_worker(
            business_a["id"], "Ana", phone="600 111 222", color="#14463b"
        )
        worker_b = db.create_worker(
            business_b["id"], "Bruno", phone="600 333 444"
        )
        job_a = db.add_job(
            client_a["id"], "Trabajo A", business_id=business_a["id"]
        )
        job_b = db.add_job(
            client_b["id"], "Trabajo B", business_id=business_b["id"]
        )

        self.assertEqual(
            [worker["id"] for worker in db.list_workers(business_a["id"])],
            [worker_a["id"]],
        )
        self.assertIsNone(
            db.update_worker(worker_b["id"], business_a["id"], name="Cruce")
        )
        updated = db.update_worker(
            worker_a["id"], business_a["id"], name="Ana Ruiz"
        )
        self.assertEqual(updated["name"], "Ana Ruiz")
        self.assertFalse(
            db.set_worker_active(
                worker_a["id"], business_a["id"], False
            )["active"]
        )
        self.assertTrue(
            db.set_worker_active(
                worker_a["id"], business_a["id"], True
            )["active"]
        )
        assigned = db.assign_job_worker(
            job_a["id"], worker_a["id"], business_a["id"]
        )
        self.assertEqual(assigned["worker_id"], worker_a["id"])
        self.assertEqual(assigned["worker_name"], "Ana Ruiz")
        self.assertIsNone(
            db.assign_job_worker(job_b["id"], worker_a["id"], business_a["id"])
        )
        with self.assertRaises(ValueError):
            db.assign_job_worker(
                job_a["id"], worker_b["id"], business_a["id"]
            )
        with self.assertRaises(db.IntegrityError):
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE jobs SET worker_id=? WHERE id=? AND business_id=?",
                    (worker_b["id"], job_a["id"], business_a["id"]),
                )

    def test_clocking_gps_rules_tokens_and_phone_binding(self):
        business, client = self.make_business("Fichajes")
        worker = db.create_worker(business["id"], "Lucía", pin="2468")
        other = db.create_worker(business["id"], "Mario")
        job = db.add_job(
            client["id"], "Instalación", business_id=business["id"]
        )
        db.assign_job_worker(job["id"], worker["id"], business["id"])

        bound = db.bind_worker_phone(
            business["id"], worker["access_code"], "+34 611 222 333"
        )
        self.assertEqual(bound["phone_norm"], "611222333")
        self.assertEqual(db.get_worker_by_phone("611 222 333")["id"], worker["id"])

        token = db.get_or_create_worker_token(business["id"], worker["id"])
        resolved = db.resolve_worker_token(token)
        self.assertEqual(resolved["worker"]["id"], worker["id"])
        self.assertEqual(resolved["business"]["id"], business["id"])

        entered = db.clock_worker(
            business["id"], worker["id"], "entrada", "web",
            job_id=job["id"], lat=41.3874, lng=2.1686, accuracy=12,
        )
        self.assertEqual(entered["lat"], 41.3874)
        with self.assertRaises(ValueError):
            db.clock_worker(
                business["id"], worker["id"], "entrada", "web"
            )
        with self.assertRaises(ValueError):
            db.clock_worker(
                business["id"], other["id"], "entrada", "web",
                job_id=job["id"],
            )
        exited = db.clock_worker(
            business["id"], worker["id"], "salida", "web"
        )
        self.assertIsNone(exited["lat"])
        with self.assertRaises(ValueError):
            db.clock_worker(
                business["id"], worker["id"], "entrada", "web", lat=91, lng=0
            )
        summary = {
            item["id"]: item for item in db.clockins_today(business["id"])
        }
        self.assertEqual(summary[worker["id"]]["last_action"], "salida")
        self.assertEqual(summary[worker["id"]]["last_location"]["lng"], 2.1686)


class WorkerPortalHttpTestCase(unittest.TestCase):
    setUp = BackendTestCase.setUp
    tearDown = BackendTestCase.tearDown
    make_business = BackendTestCase.make_business

    def _job_for(self, business, client, worker, description="Servicio"):
        job = db.add_job(
            client["id"], description,
            scheduled_for=f"{date.today().isoformat()}T09:00",
            business_id=business["id"],
        )
        db.assign_job_worker(job["id"], worker["id"], business["id"])
        return job

    def test_worker_token_clocks_only_its_worker_with_optional_gps(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business_a, client_a = self.make_business("Portal Equipo A")
        business_b, client_b = self.make_business("Portal Equipo B")
        worker_a = db.create_worker(business_a["id"], "Ana")
        worker_b = db.create_worker(business_b["id"], "Bruno")
        job_a = self._job_for(business_a, client_a, worker_a, "Trabajo propio")
        job_b = self._job_for(business_b, client_b, worker_b, "Trabajo ajeno")
        token = db.get_or_create_worker_token(business_a["id"], worker_a["id"])

        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                page = client.get(f"/t/{token}")
                self.assertEqual(page.status_code, 200)
                self.assertIn("Al fichar se guarda tu ubicación", page.text)
                self.assertIn("Trabajo propio", page.text)
                self.assertNotIn("Trabajo ajeno", page.text)

                blocked = client.post(
                    f"/t/{token}/clock",
                    json={"action": "entrada", "job_id": job_b["id"]},
                )
                self.assertEqual(blocked.status_code, 400)

                entered = client.post(
                    f"/t/{token}/clock",
                    json={
                        "action": "entrada", "job_id": job_a["id"],
                        "lat": 40.4168, "lng": -3.7038, "accuracy": 9,
                    },
                )
                self.assertEqual(entered.status_code, 200)
                exited = client.post(
                    f"/t/{token}/clock", json={"action": "salida"}
                )
                self.assertEqual(exited.status_code, 200)

        with db.get_conn() as conn:
            rows_a = conn.execute(
                "SELECT * FROM worker_clockins WHERE business_id=? AND worker_id=? "
                "ORDER BY id",
                (business_a["id"], worker_a["id"]),
            ).fetchall()
            rows_b = conn.execute(
                "SELECT * FROM worker_clockins WHERE business_id=?",
                (business_b["id"],),
            ).fetchall()
        self.assertEqual(len(rows_a), 2)
        self.assertEqual(rows_a[0]["lat"], 40.4168)
        self.assertIsNone(rows_a[1]["lat"])
        self.assertEqual(rows_b, [])

    def test_worker_pin_and_durable_send_day(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, client_record = self.make_business("Empresa PIN")
        other_business, _ = self.make_business("Empresa ajena")
        other_worker = db.create_worker(other_business["id"], "Ajeno")
        worker = db.create_worker(
            business["id"], "Sara", phone="+34 622 333 444", pin="1357"
        )
        self._job_for(business, client_record, worker, "Revisión")
        token = db.get_or_create_worker_token(business["id"], worker["id"])
        db.create_user(
            "equipo@example.com", auth.hash_password("password-segura-123"),
            business["id"],
        )

        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                locked = client.post(
                    f"/t/{token}/clock", json={"action": "entrada"}
                )
                self.assertEqual(locked.status_code, 403)
                self.assertEqual(
                    client.post(f"/t/{token}/pin", json={"pin": "0000"}).status_code,
                    401,
                )
                self.assertEqual(
                    client.post(f"/t/{token}/pin", json={"pin": "1357"}).status_code,
                    200,
                )
                self.assertEqual(
                    client.post(
                        f"/t/{token}/clock", json={"action": "entrada"}
                    ).status_code,
                    200,
                )

                login = client.post(
                    "/login",
                    data={
                        "email": "equipo@example.com",
                        "password": "password-segura-123",
                    },
                    follow_redirects=False,
                )
                self.assertEqual(login.status_code, 303)
                self.assertEqual(
                    client.get(
                        f"/api/{other_business['id']}/workers"
                    ).status_code,
                    403,
                )
                self.assertEqual(
                    client.get(
                        f"/api/{business['id']}/workers/{other_worker['id']}/link"
                    ).status_code,
                    404,
                )
                queued = client.post(
                    f"/api/{business['id']}/workers/{worker['id']}/send-day",
                    json={},
                )
                self.assertEqual(queued.status_code, 200)

        outbox = db.list_whatsapp_messages(business["id"])
        self.assertEqual(len(outbox), 1)
        self.assertEqual(outbox[0]["status"], "queued")
        self.assertIn("Revisión", outbox[0]["text_body"])


class LegalClockinTestCase(unittest.TestCase):
    setUp = BackendTestCase.setUp
    tearDown = BackendTestCase.tearDown
    make_business = BackendTestCase.make_business

    def _worker_with_user(self, name="Jornada Legal"):
        business, client = self.make_business(name)
        worker = db.create_worker(business["id"], "Laura Legal")
        user = db.create_user(
            f"{name.lower().replace(' ', '')}@example.com",
            auth.hash_password("password-segura-123"),
            business["id"],
        )
        return business, client, worker, user

    def test_clockin_chain_is_sealed_and_append_only(self):
        business, _client, worker, _user = self._worker_with_user()
        day = date.today().isoformat()
        moments = [
            f"{day}T08:00:00", f"{day}T10:00:00",
            f"{day}T10:30:00", f"{day}T12:00:00",
        ]
        with patch("noesis.db._now", side_effect=moments):
            db.clock_worker(business["id"], worker["id"], "entrada", "web")
            db.clock_worker(business["id"], worker["id"], "pausa", "web")
            db.clock_worker(business["id"], worker["id"], "reanudar", "web")
            db.clock_worker(business["id"], worker["id"], "salida", "web")

        with db.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM worker_clockins WHERE business_id=? "
                "AND worker_id=? ORDER BY id",
                (business["id"], worker["id"]),
            ).fetchall()
        self.assertEqual([row["action"] for row in rows],
                         ["entrada", "pausa", "reanudar", "salida"])
        self.assertIsNone(rows[0]["prev_seal"])
        self.assertEqual(rows[1]["prev_seal"], rows[0]["seal"])
        self.assertEqual(rows[3]["prev_seal"], rows[2]["seal"])
        self.assertTrue(
            db.verify_clockin_chain(business["id"], worker["id"])["valid"]
        )
        with self.assertRaises(db.IntegrityError):
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE worker_clockins SET at=? WHERE id=?",
                    (f"{day}T09:00:00", rows[0]["id"]),
                )
        with self.assertRaises(db.IntegrityError):
            with db.get_conn() as conn:
                conn.execute(
                    "DELETE FROM worker_clockins WHERE id=?", (rows[0]["id"],)
                )

    def test_chain_verification_detects_external_tampering(self):
        business, _client, worker, _user = self._worker_with_user("Cadena")
        clockin = db.clock_worker(
            business["id"], worker["id"], "entrada", "web", lat=40, lng=-3
        )
        with db.get_conn() as conn:
            conn.execute("DROP TRIGGER worker_clockins_append_only_update")
            conn.execute(
                "UPDATE worker_clockins SET lat=? WHERE id=?",
                (41, clockin["id"]),
            )
        result = db.verify_clockin_chain(business["id"], worker["id"])
        self.assertFalse(result["valid"])
        self.assertEqual(result["broken_at"], clockin["id"])

    def test_correction_and_annulment_leave_audit_trail(self):
        business, _client, worker, user = self._worker_with_user("Correcciones")
        day = date.today().isoformat()
        with patch("noesis.db._now", return_value=f"{day}T08:00:00"):
            original = db.clock_worker(
                business["id"], worker["id"], "entrada", "web"
            )
        correction = db.correct_worker_clockin(
            business["id"], worker["id"], original["id"], user["id"],
            new_at=f"{day}T08:15:00", reason="Olvidó fichar al llegar",
        )
        self.assertEqual(correction["old_at"], f"{day}T08:00:00")
        self.assertEqual(correction["new_at"], f"{day}T08:15:00")
        with db.get_conn() as conn:
            stored = conn.execute(
                "SELECT * FROM worker_clockins WHERE id=?", (original["id"],)
            ).fetchone()
        self.assertEqual(stored["at"], original["at"])
        self.assertEqual(stored["seal"], original["seal"])
        self.assertTrue(
            db.verify_clockin_chain(business["id"], worker["id"])["valid"]
        )
        annulment = db.correct_worker_clockin(
            business["id"], worker["id"], original["id"], user["id"],
            new_at=None, reason="Fichaje duplicado",
        )
        self.assertEqual(annulment["status"], "anulado")
        trail = db.clockin_corrections(
            business["id"], worker["id"], original["id"]
        )
        self.assertEqual(len(trail), 2)
        self.assertTrue(
            db.worker_clockin_history(
                worker["id"], business["id"],
                from_day=day, to_day=day,
            )[0]["annulled"]
        )
        with self.assertRaises(db.IntegrityError):
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE worker_clockin_corrections SET reason='cambiado' "
                    "WHERE id=?",
                    (correction["id"],),
                )

    def test_pauses_are_discounted_from_worked_hours(self):
        business, _client, worker, _user = self._worker_with_user("Pausas")
        day = (date.today() - timedelta(days=1)).isoformat()
        moments = [
            f"{day}T08:00:00", f"{day}T10:00:00",
            f"{day}T10:30:00", f"{day}T12:00:00",
        ]
        with patch("noesis.db._now", side_effect=moments):
            for action in ("entrada", "pausa", "reanudar", "salida"):
                db.clock_worker(
                    business["id"], worker["id"], action, "web"
                )
        report = db.clockin_report_data(
            business["id"], worker["id"], day, day
        )
        self.assertEqual(report["days"][0]["hours"], 3.5)

    def test_verifiable_report_contains_seals_and_integrity(self):
        from noesis.web.work_reports import build_clockin_csv, build_clockin_pdf

        business, _client, worker, _user = self._worker_with_user("Informes")
        day = date.today().isoformat()
        moments = [f"{day}T08:00:00", f"{day}T16:00:00"]
        with patch("noesis.db._now", side_effect=moments):
            db.clock_worker(business["id"], worker["id"], "entrada", "web")
            db.clock_worker(business["id"], worker["id"], "salida", "web")
        data = db.clockin_report_data(
            business["id"], worker["id"], day, day
        )
        csv_payload = build_clockin_csv(data).decode("utf-8-sig")
        pdf_payload = build_clockin_pdf(data)
        self.assertIn("sello_sha256", csv_payload)
        self.assertIn("VALIDA", csv_payload)
        self.assertIn(data["days"][0]["events"][0]["seal"], csv_payload)
        self.assertTrue(pdf_payload.startswith(b"%PDF"))
        self.assertGreater(len(pdf_payload), 1500)

    def test_worker_acknowledgement_is_scoped_and_recorded(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, _client, worker, _user = self._worker_with_user("Acuse")
        token = db.get_or_create_worker_token(business["id"], worker["id"])
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                response = client.post(f"/t/{token}/ack")
                self.assertEqual(response.status_code, 200)
                page = client.get(f"/t/{token}")
                self.assertIn("Información recibida", page.text)
        with db.get_conn() as conn:
            event = conn.execute(
                "SELECT * FROM product_events WHERE business_id=? "
                "AND event_name='fichaje_info_ack'",
                (business["id"],),
            ).fetchone()
        self.assertIsNotNone(event)
        self.assertIn(str(worker["id"]), event["event_data"])

    def test_correction_and_report_endpoints_are_tenant_scoped(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, _client, worker, user = self._worker_with_user("HTTP Legal")
        other_business, _ = self.make_business("HTTP Ajeno")
        other_worker = db.create_worker(other_business["id"], "Persona ajena")
        day = date.today().isoformat()
        with patch("noesis.db._now", return_value=f"{day}T08:00:00"):
            clockin = db.clock_worker(
                business["id"], worker["id"], "entrada", "web"
            )
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                login = client.post(
                    "/login",
                    data={
                        "email": user["email"],
                        "password": "password-segura-123",
                    },
                    follow_redirects=False,
                )
                self.assertEqual(login.status_code, 303)
                corrected = client.post(
                    f"/api/{business['id']}/workers/{worker['id']}/"
                    f"clockins/{clockin['id']}/correct",
                    json={
                        "new_at": f"{day}T08:05:00",
                        "reason": "Ajuste solicitado por la trabajadora",
                    },
                )
                self.assertEqual(corrected.status_code, 200)
                blocked = client.post(
                    f"/api/{business['id']}/workers/{other_worker['id']}/"
                    f"clockins/{clockin['id']}/correct",
                    json={"new_at": None, "reason": "Cruce"},
                )
                self.assertEqual(blocked.status_code, 404)
                csv_report = client.get(
                    f"/api/{business['id']}/workers/{worker['id']}/report"
                    f"?from={day}&to={day}&format=csv"
                )
                pdf_report = client.get(
                    f"/api/{business['id']}/workers/{worker['id']}/report"
                    f"?from={day}&to={day}&format=pdf"
                )
                self.assertEqual(csv_report.status_code, 200)
                self.assertTrue(csv_report.headers["content-type"].startswith("text/csv"))
                self.assertEqual(pdf_report.status_code, 200)
                self.assertEqual(pdf_report.headers["content-type"], "application/pdf")
                forbidden = client.get(
                    f"/api/{other_business['id']}/workers/{other_worker['id']}/report"
                )
                self.assertEqual(forbidden.status_code, 403)


class VerifactuPhase1TestCase(unittest.TestCase):
    make_business = BackendTestCase.make_business

    def setUp(self):
        BackendTestCase.setUp(self)
        self.original_producer_nif = config.VERIFACTU_PRODUCER_NIF
        config.VERIFACTU_PRODUCER_NIF = "B87654321"

    def tearDown(self):
        config.VERIFACTU_PRODUCER_NIF = self.original_producer_nif
        BackendTestCase.tearDown(self)

    def _enabled_business(self, name="Verifactu Legal"):
        business, client = self.make_business(name)
        business = db.update_verifactu_mode(business["id"], True)
        return business, client

    def _issue(self, business, client, concept="Servicio", base=100):
        invoice = db.add_invoice(
            client["id"], concept, base, business_id=business["id"]
        )
        return db.issue_invoice(invoice["id"], business["id"])

    def test_mode_is_disabled_by_default(self):
        business, client = self.make_business("Verifactu Desactivado")
        invoice = self._issue(business, client)
        self.assertFalse(db.get_business(business["id"])["verifactu_enabled"])
        self.assertIsNone(db.get_invoice_record(invoice["id"], business["id"]))
        self.assertEqual(db.list_invoice_events(business["id"]), [])

    def test_official_hash_example_and_qr_parameters(self):
        digest = verifactu.invoice_record_hash(
            issuer_nif="89890001K",
            invoice_number="12345678/G33",
            issue_date="01-01-2024",
            invoice_type="F1",
            vat_total="12.35",
            invoice_total="123.45",
            previous_hash=None,
            generated_at="2024-01-01T19:20:30+01:00",
        )
        self.assertEqual(
            digest,
            "3C464DAF61ACB827C65FDA19F352A4E3BDC2C640E9E9FC4CC058073F38F12F60",
        )
        with patch.object(
            config,
            "VERIFACTU_QR_BASE_URL",
            "https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR",
        ):
            url = verifactu.qr_url(
                issuer_nif="89890001K",
                invoice_number="12345678&G33",
                issue_date="2024-01-01",
                total="241.40",
            )
        self.assertEqual(
            url,
            "https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR"
            "?nif=89890001K&numserie=12345678%26G33"
            "&fecha=01-01-2024&importe=241.4",
        )

    def test_records_are_chained_scoped_and_append_only(self):
        business, client = self._enabled_business()
        other_business, other_client = self._enabled_business("Verifactu Ajeno")
        first = self._issue(business, client, "Primera", 100)
        second = self._issue(business, client, "Segunda", 200)
        self._issue(other_business, other_client, "Ajena", 50)

        records = db.list_invoice_records(business["id"])
        self.assertEqual(len(records), 2)
        self.assertIsNone(records[0]["previous_hash"])
        self.assertEqual(records[1]["previous_hash"], records[0]["record_hash"])
        self.assertTrue(db.verify_invoice_record_chain(business["id"])["valid"])
        self.assertIsNone(
            db.get_invoice_record(first["id"], other_business["id"])
        )
        self.assertIsNotNone(db.get_invoice_record(second["id"], business["id"]))
        with self.assertRaises(db.IntegrityError):
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE invoice_records SET invoice_total=1 WHERE id=?",
                    (records[0]["id"],),
                )
        with self.assertRaises(db.IntegrityError):
            with db.get_conn() as conn:
                conn.execute(
                    "DELETE FROM invoice_records WHERE id=?", (records[0]["id"],)
                )
        events = db.list_invoice_events(business["id"])
        self.assertEqual([event["event_type"] for event in events], ["alta", "alta"])
        with self.assertRaises(db.IntegrityError):
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE invoice_events SET details='alterado' WHERE id=?",
                    (events[0]["id"],),
                )

    def test_chain_verification_detects_tampering(self):
        business, client = self._enabled_business("Verifactu Manipulacion")
        invoice = self._issue(business, client)
        record = db.get_invoice_record(invoice["id"], business["id"])
        with db.get_conn() as conn:
            conn.execute("DROP TRIGGER invoice_records_append_only_update")
            conn.execute(
                "UPDATE invoice_records SET invoice_total=? WHERE id=?",
                (999, record["id"]),
            )
        result = db.verify_invoice_record_chain(business["id"])
        self.assertFalse(result["valid"])
        self.assertEqual(result["broken_at"], record["id"])

    def test_rectifying_invoice_keeps_original_and_exports_reference(self):
        business, client = self._enabled_business("Verifactu Rectifica")
        original = self._issue(business, client, "Instalación", 500)
        rectifying = db.create_rectifying_invoice(
            original["id"],
            business["id"],
            concept="Corrección de instalación",
            base=-100,
            vat_rate=21,
            irpf_rate=0,
            invoice_type="R1",
            reason="Error en la medición",
        )
        issued = db.issue_invoice(rectifying["id"], business["id"])
        self.assertEqual(issued["invoice_type"], "R1")
        self.assertEqual(issued["rectifies_invoice_id"], original["id"])
        self.assertEqual(
            db.get_invoice(original["id"], business["id"])["total"],
            original["total"],
        )
        record = db.get_invoice_record(issued["id"], business["id"])
        self.assertEqual(record["rectified_invoice_number"], original["number"])
        xml = db.export_verifactu_xml(business["id"])
        root = ET.fromstring(xml)
        ns = {"sum": verifactu.NS_LR, "sum1": verifactu.NS_INFO}
        rectified_number = root.find(
            ".//sum1:FacturasRectificadas/"
            "sum1:IDFacturaRectificada/sum1:NumSerieFactura",
            ns,
        )
        self.assertEqual(rectified_number.text, original["number"])
        self.assertIn(
            "rectificacion",
            [event["event_type"] for event in db.list_invoice_events(business["id"])],
        )

    def test_qr_png_pdf_and_aeat_xml_are_generated(self):
        from PIL import Image
        from noesis.web.invoice_pdf import build_invoice_pdf

        business, client = self._enabled_business("Verifactu Documentos")
        invoice = self._issue(business, client)
        record = db.get_invoice_record(invoice["id"], business["id"])
        png = verifactu.qr_png(record["qr_url"])
        image = Image.open(BytesIO(png))
        self.assertEqual(image.format, "PNG")
        self.assertEqual(image.width, image.height)
        self.assertGreater(image.width, 100)

        pdf = build_invoice_pdf(invoice["id"], business["id"])
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 3000)

        xml = db.export_verifactu_xml(business["id"])
        root = ET.fromstring(xml)
        self.assertEqual(
            root.tag, f"{{{verifactu.NS_LR}}}RegFactuSistemaFacturacion"
        )
        ns = {"sum": verifactu.NS_LR, "sum1": verifactu.NS_INFO}
        alta = root.find("sum:RegistroFactura/sum1:RegistroAlta", ns)
        self.assertIsNotNone(alta)
        self.assertEqual(alta.find("sum1:IDVersion", ns).text, "1.0")
        self.assertEqual(
            alta.find("sum1:Huella", ns).text, record["record_hash"]
        )
        self.assertEqual(
            db.list_invoice_events(business["id"])[-1]["event_type"],
            "exportacion",
        )

    def test_export_endpoint_is_tenant_scoped(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, client_record = self._enabled_business("Verifactu HTTP")
        other_business, _ = self._enabled_business("Verifactu HTTP Ajeno")
        self._issue(business, client_record)
        user = db.create_user(
            "verifactu@example.com",
            auth.hash_password("password-segura-123"),
            business["id"],
        )
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                login = client.post(
                    "/login",
                    data={
                        "email": user["email"],
                        "password": "password-segura-123",
                    },
                    follow_redirects=False,
                )
                self.assertEqual(login.status_code, 303)
                exported = client.get(
                    f"/api/{business['id']}/verifactu/export.xml"
                )
                self.assertEqual(exported.status_code, 200)
                self.assertTrue(
                    exported.headers["content-type"].startswith("application/xml")
                )
                forbidden = client.get(
                    f"/api/{other_business['id']}/verifactu/export.xml"
                )
                self.assertEqual(forbidden.status_code, 403)


if __name__ == "__main__":
    unittest.main()
