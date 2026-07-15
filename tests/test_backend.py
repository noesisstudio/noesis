from __future__ import annotations

import hashlib
import hmac
import inspect
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree as ET

from noesis import config, db, migrations, nlu, verifactu, verifactu_client
from noesis.adapters import extraction
from noesis.web import auth, chat, reports, scheduler, whatsapp


class BackendTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        self.original_backup_dir = config.BACKUP_DIR
        self.original_docs_path = config.DOCS_PATH
        self.original_database_url = config.DATABASE_URL
        config.DATABASE_URL = ""
        config.DB_PATH = Path(self.tempdir.name) / "test.db"
        config.BACKUP_DIR = Path(self.tempdir.name) / "backups"
        config.DOCS_PATH = Path(self.tempdir.name) / "uploads"
        db.init_db()

    def tearDown(self):
        config.DB_PATH = self.original_db_path
        config.BACKUP_DIR = self.original_backup_dir
        config.DOCS_PATH = self.original_docs_path
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

    def test_partial_payment_migration_backfills_paid_invoices(self):
        business, client = self.make_business()
        invoice = db.issue_invoice(
            db.add_invoice(
                client["id"], "Cobro anterior", 100,
                business_id=business["id"],
            )["id"],
            business["id"],
        )
        db.mark_invoice_paid(invoice["id"], business["id"])

        self.assertEqual(migrations.downgrade(10), 10)
        self.assertEqual(migrations.upgrade(), migrations.LATEST_VERSION)

        payments = db.list_invoice_payments(invoice["id"], business["id"])
        self.assertEqual(len(payments), 1)
        self.assertEqual(payments[0]["amount"], 121)
        self.assertEqual(payments[0]["method"], "registro_anterior")

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
        again = db.mark_invoice_paid(invoice["id"], business["id"])
        self.assertEqual(again["payment_status"], "pagada")
        self.assertEqual(
            len(db.list_invoice_payments(invoice["id"], business["id"])), 1
        )

    def test_tax_amounts_use_commercial_cent_rounding(self):
        business, client = self.make_business()

        invoice = db.add_invoice(
            client["id"], "Importe pequeño", 0.50, business_id=business["id"]
        )
        quote = db.add_quote(
            client["id"], "Presupuesto pequeño", 0.50,
            business_id=business["id"],
        )

        self.assertEqual(invoice["vat_amount"], 0.11)
        self.assertEqual(invoice["total"], 0.61)
        self.assertEqual(quote["vat_amount"], 0.11)
        self.assertEqual(quote["total"], 0.61)

    def test_partial_payments_derive_state_and_reject_overpayment(self):
        business, client = self.make_business()
        invoice = db.add_invoice(
            client["id"], "Instalación por fases", 100,
            business_id=business["id"],
        )
        invoice = db.issue_invoice(invoice["id"], business["id"])

        payment = db.add_invoice_payment(
            invoice["id"], 40, method="transferencia", note="Anticipo",
            business_id=business["id"],
        )
        partial = db.get_invoice(invoice["id"], business["id"])

        self.assertEqual(payment["amount"], 40)
        self.assertEqual(partial["status"], "parcial")
        self.assertEqual(partial["payment_status"], "parcial")
        self.assertEqual(partial["paid_amount"], 40)
        self.assertEqual(partial["remaining_amount"], 81)
        with self.assertRaises(ValueError):
            db.add_invoice_payment(
                invoice["id"], 81.01, business_id=business["id"]
            )

        db.add_invoice_payment(
            invoice["id"], 81, method="bizum", business_id=business["id"]
        )
        paid = db.get_invoice(invoice["id"], business["id"])
        self.assertEqual(paid["status"], "cobrada")
        self.assertEqual(paid["payment_status"], "pagada")
        self.assertEqual(paid["remaining_amount"], 0)

    def test_partial_payments_are_isolated_and_feed_cash_metrics(self):
        business_a, client_a = self.make_business("Cobros A")
        business_b, client_b = self.make_business("Cobros B")
        invoice_a = db.issue_invoice(
            db.add_invoice(
                client_a["id"], "Servicio A", 100,
                business_id=business_a["id"],
            )["id"],
            business_a["id"],
        )
        invoice_b = db.issue_invoice(
            db.add_invoice(
                client_b["id"], "Servicio B", 200,
                business_id=business_b["id"],
            )["id"],
            business_b["id"],
        )

        with self.assertRaises(ValueError):
            db.add_invoice_payment(
                invoice_b["id"], 10, business_id=business_a["id"]
            )
        self.assertEqual(
            db.list_invoice_payments(invoice_b["id"], business_a["id"]), []
        )
        self.assertIsNone(
            db.invoice_paid_amount(invoice_b["id"], business_a["id"])
        )

        db.add_invoice_payment(
            invoice_a["id"], 40, method="tarjeta",
            business_id=business_a["id"],
        )
        pending = db.pending_payments(business_a["id"])
        month = db.month_billing(business_id=business_a["id"])
        analysis = db.financial_analysis(business_a["id"])

        self.assertEqual(pending[0]["invoice_total"], 121)
        self.assertEqual(pending[0]["total"], 81)
        self.assertEqual(month["collected"], 40)
        self.assertEqual(month["pending"], 81)
        self.assertEqual(analysis["collected"], 40)
        self.assertEqual(analysis["pending"], 81)
        self.assertEqual(db.invoice_paid_amount(invoice_b["id"], business_b["id"]), 0)

        exported = db.export_business_data(business_a["id"])
        client_export = db.export_client_data(client_a["id"], business_a["id"])
        self.assertEqual(len(exported["invoice_payments"]), 1)
        self.assertEqual(len(client_export["invoice_payments"]), 1)

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
        db.complete_webhook_event("whatsapp", "wamid.1")
        self.assertFalse(db.claim_webhook_event("whatsapp", "wamid.1"))

    def test_failed_whatsapp_event_can_be_retried(self):
        business, _ = self.make_business()
        db.set_whatsapp_status(business["id"], "conectado", phone="600111222")
        payload = {
            "id": "wamid.retry-inbound",
            "from": "34600111222",
            "text": "resumen",
        }
        with (
            patch.object(
                chat,
                "handle",
                side_effect=[
                    RuntimeError("fallo transitorio"),
                    {"reply": "Recuperado"},
                ],
            ) as handle,
            patch.object(whatsapp, "send", return_value=True),
        ):
            with self.assertRaises(RuntimeError):
                whatsapp.handle_inbound(payload)
            failed = db.webhook_event("whatsapp", payload["id"])
            retried = whatsapp.handle_inbound(payload)
            duplicate = whatsapp.handle_inbound(payload)

        self.assertEqual(failed["status"], "failed")
        self.assertEqual(retried["processed"], 1)
        self.assertTrue(duplicate["results"][0]["duplicate"])
        self.assertEqual(handle.call_count, 2)
        self.assertEqual(
            db.webhook_event("whatsapp", payload["id"])["status"], "done"
        )

    def test_failed_stripe_event_returns_500_and_can_be_retried(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, _ = self.make_business("Stripe recuperable")
        event = {
            "id": "evt_retry",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "metadata": {
                        "business_id": str(business["id"]),
                        "plan": "autonomo",
                    },
                    "customer": "cus_retry",
                    "subscription": "sub_retry",
                }
            },
        }
        with (
            patch.object(server, "start_scheduler", lambda: None),
            patch.object(
                server.billing_adapter, "verify_webhook", return_value=event
            ),
            patch.object(
                db,
                "set_subscription",
                side_effect=[RuntimeError("fallo transitorio"), None],
            ) as update,
            TestClient(server.app) as client,
        ):
            failed = client.post("/webhook/stripe", content=b"{}")
            retried = client.post("/webhook/stripe", content=b"{}")
            duplicate = client.post("/webhook/stripe", content=b"{}")

        self.assertEqual(failed.status_code, 500)
        self.assertEqual(retried.status_code, 200)
        self.assertTrue(duplicate.json()["duplicate"])
        self.assertEqual(update.call_count, 2)
        self.assertEqual(
            db.webhook_event("stripe", event["id"])["status"], "done"
        )

    def test_account_delete_cleans_dependencies_before_files(self):
        from noesis.documents import repo, service, storage

        business, client = self.make_business("Baja completa")
        document = service.upload(
            business["id"], "ticket.pdf", b"%PDF-review", run_ocr=False
        )
        file_path = storage.path_for(
            business["id"], document["stored_name"]
        )
        quote = db.add_quote(
            client["id"], "Presupuesto", 100, business_id=business["id"]
        )
        db.mark_quote_sent(quote["id"], business["id"])
        db.create_whatsapp_link(
            "hash-baja",
            business["id"],
            (datetime.now() + timedelta(hours=1)).isoformat(),
        )
        db.set_pending_action(
            business["id"], "600111222", "chat_action", {"text": "resumen"}
        )
        db.enqueue_whatsapp_message(
            business_id=business["id"],
            to_phone="34600111222",
            message_type="text",
            text_body="Pendiente",
        )
        db.claim_scheduled_run(f"gestoria:{business['id']}:2026-06")

        self.assertTrue(db.delete_business_cascade(business["id"]))

        self.assertIsNone(db.get_business(business["id"]))
        self.assertIsNone(repo.get(document["id"], business["id"]))
        self.assertFalse(file_path.exists())
        with db.get_conn() as conn:
            remaining_runs = conn.execute(
                "SELECT COUNT(*) AS total FROM scheduled_job_runs "
                "WHERE run_key LIKE ?",
                (f"gestoria:{business['id']}:%",),
            ).fetchone()["total"]
        self.assertEqual(remaining_runs, 0)

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
        handle.assert_called_once_with(
            business["id"], "resumen", channel="whatsapp",
            actor_phone="34600111222",
        )
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
        self.assertEqual(nlu.parse("¿cómo van mis proyectos?")[0], "ver_proyectos")
        self.assertEqual(
            nlu.parse("¿qué documentos tengo pendientes de revisar?")[0],
            "ver_documentos_pendientes",
        )
        self.assertEqual(
            nlu.parse("¿qué puedes hacer sin preguntarme?")[0],
            "ver_control_noesis",
        )
        tool, args = nlu.parse(
            "crea proyecto reforma del baño de 8000 euros"
        )
        self.assertEqual(tool, "crear_proyecto")
        self.assertEqual(args["presupuesto"], 8000)

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


class ExpenseExtractionAdapterTestCase(unittest.TestCase):
    def test_claude_vision_result_is_parsed_and_validated(self):
        create = MagicMock(return_value=SimpleNamespace(content=[
            SimpleNamespace(
                type="text",
                text=(
                    '```json\n{"concept":"Material eléctrico","amount":121.0,'
                    '"vat_rate":21,"date":"2026-07-02",'
                    '"supplier":"Suministros Norte"}\n```'
                ),
            )
        ]))
        client = SimpleNamespace(messages=SimpleNamespace(create=create))
        with (
            patch.object(config, "ANTHROPIC_API_KEY", "test-key"),
            patch.object(extraction.anthropic, "Anthropic", return_value=client),
        ):
            result = extraction.extract_expense(b"foto-ticket", "image/jpeg")

        self.assertEqual(result["concept"], "Material eléctrico")
        self.assertEqual(result["amount"], 121)
        self.assertEqual(result["vat_rate"], 21)
        self.assertEqual(result["date"], "2026-07-02")
        self.assertEqual(result["supplier"], "Suministros Norte")
        self.assertEqual(create.call_args.kwargs["model"], config.FALLBACK_MODEL)

    def test_extraction_without_key_is_free_fallback(self):
        with (
            patch.object(config, "ANTHROPIC_API_KEY", ""),
            patch.object(extraction.anthropic, "Anthropic") as client,
        ):
            self.assertIsNone(
                extraction.extract_expense(b"foto-ticket", "image/jpeg")
            )
        client.assert_not_called()


class ExpensePhotoHttpTestCase(unittest.TestCase):
    setUp = BackendTestCase.setUp
    tearDown = BackendTestCase.tearDown
    make_business = BackendTestCase.make_business

    def _login(self, client, business):
        email = f"foto-{business['id']}@example.com"
        db.create_user(
            email,
            auth.hash_password("password-segura-123"),
            business["id"],
        )
        response = client.post(
            "/login",
            data={"email": email, "password": "password-segura-123"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)

    def test_photo_returns_draft_and_confirmation_links_document(self):
        from starlette.testclient import TestClient
        from noesis.documents import repo as docrepo, service as docservice
        from noesis.web import server

        business_a, _ = self.make_business("Fotos A")
        business_b, _ = self.make_business("Fotos B")
        foreign_doc = docservice.upload(
            business_b["id"],
            "ajeno.jpg",
            b"\xff\xd8\xff\xe0ajeno",
            kind="ticket",
            run_ocr=False,
        )
        extracted = {
            "concept": "Compra de cable",
            "amount": 121.0,
            "vat_rate": 21,
            "date": "2026-07-02",
            "supplier": "Almacén eléctrico",
        }

        with (
            patch.object(server, "start_scheduler", lambda: None),
            patch.object(extraction, "extract_expense", return_value=extracted),
        ):
            with TestClient(server.app) as client:
                self._login(client, business_a)
                uploaded = client.post(
                    f"/api/{business_a['id']}/expenses/from-photo",
                    files={"file": ("ticket.jpg", b"\xff\xd8\xff\xe0ticket", "image/jpeg")},
                )
                self.assertEqual(uploaded.status_code, 201)
                payload = uploaded.json()
                self.assertTrue(payload["extracted"])
                self.assertEqual(payload["draft"]["amount"], 121)
                self.assertEqual(db.list_expenses(business_a["id"]), [])

                document_id = payload["draft"]["document_id"]
                document = docrepo.get(document_id, business_a["id"])
                self.assertIsNone(document["expense_id"])

                isolated = client.post(
                    f"/api/{business_a['id']}/expenses",
                    json={
                        "concept": "Intento cruzado",
                        "amount": 20,
                        "document_id": foreign_doc["id"],
                    },
                )
                self.assertEqual(isolated.status_code, 400)
                self.assertEqual(db.list_expenses(business_a["id"]), [])
                self.assertEqual(
                    client.post(
                        f"/api/{business_b['id']}/expenses/from-photo",
                        files={"file": ("ticket.jpg", b"foto", "image/jpeg")},
                    ).status_code,
                    403,
                )

                confirmed = client.post(
                    f"/api/{business_a['id']}/expenses",
                    json=payload["draft"],
                )
                self.assertEqual(confirmed.status_code, 200)
                expense = confirmed.json()
                self.assertEqual(expense["amount"], 121)
                self.assertEqual(expense["spent_on"], "2026-07-02")
                self.assertEqual(
                    docrepo.get(document_id, business_a["id"])["expense_id"],
                    expense["id"],
                )

                duplicate = client.post(
                    f"/api/{business_a['id']}/expenses",
                    json=payload["draft"],
                )
                self.assertEqual(duplicate.status_code, 400)
                self.assertEqual(len(db.list_expenses(business_a["id"])), 1)

        with self.assertRaises(db.IntegrityError):
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE documents SET expense_id=? "
                    "WHERE id=? AND business_id=?",
                    (expense["id"], foreign_doc["id"], business_b["id"]),
                )

    def test_photo_fallback_and_upload_limit_never_create_expense(self):
        from starlette.testclient import TestClient
        from noesis.documents import repo as docrepo
        from noesis.web import server

        business, _ = self.make_business("Fotos manual")
        with (
            patch.object(server, "start_scheduler", lambda: None),
            patch.object(extraction, "extract_expense", return_value=None),
        ):
            with TestClient(server.app) as client:
                self._login(client, business)
                manual = client.post(
                    f"/api/{business['id']}/expenses/from-photo",
                    files={"file": ("ticket.png", b"\x89PNG\r\nfoto", "image/png")},
                )
                self.assertEqual(manual.status_code, 201)
                self.assertFalse(manual.json()["extracted"])
                self.assertIsNone(manual.json()["draft"]["amount"])
                self.assertEqual(db.list_expenses(business["id"]), [])

                documents_before = len(docrepo.list_for_business(business["id"]))
                not_image = client.post(
                    f"/api/{business['id']}/expenses/from-photo",
                    files={"file": ("ticket.pdf", b"%PDF-1.4", "application/pdf")},
                )
                self.assertEqual(not_image.status_code, 400)
                self.assertEqual(
                    len(docrepo.list_for_business(business["id"])),
                    documents_before,
                )
                with patch.object(config, "MAX_UPLOAD_MB", 1):
                    too_large = client.post(
                        f"/api/{business['id']}/expenses/from-photo",
                        files={
                            "file": (
                                "grande.jpg",
                                b"x" * (1024 * 1024 + 1),
                                "image/jpeg",
                            )
                        },
                    )
                self.assertEqual(too_large.status_code, 413)
                self.assertEqual(
                    len(docrepo.list_for_business(business["id"])),
                    documents_before,
                )
                self.assertEqual(db.list_expenses(business["id"]), [])


class PaymentReminderTestCase(unittest.TestCase):
    setUp = BackendTestCase.setUp
    tearDown = BackendTestCase.tearDown
    make_business = BackendTestCase.make_business

    def _issued_invoice(self, business, client, base=100):
        db.update_client(
            client["id"], business["id"], phone="600111222"
        )
        invoice = db.add_invoice(
            client["id"], "Servicio pendiente", base,
            business_id=business["id"],
        )
        return db.issue_invoice(invoice["id"], business["id"])

    @staticmethod
    def _reminder_time(invoice, days):
        due = date.fromisoformat(invoice["due_date"][:10])
        return datetime.combine(
            due + timedelta(days=days), datetime.min.time()
        ).replace(hour=9)

    def test_reminders_use_remaining_and_are_idempotent_per_step(self):
        business, client = self.make_business("Recordatorios A")
        other_business, other_client = self.make_business("Recordatorios B")
        invoice = self._issued_invoice(business, client)
        self._issued_invoice(other_business, other_client)
        db.add_invoice_payment(
            invoice["id"], 40, method="transferencia",
            business_id=business["id"],
        )
        db.update_payment_reminder_settings(
            business["id"], enabled=True, days="3,7,15"
        )
        point = self._reminder_time(invoice, 3)

        with (
            patch.object(whatsapp, "_TOKEN", ""),
            patch.object(whatsapp, "_PHONE_ID", ""),
        ):
            self.assertEqual(scheduler.send_payment_reminders(now=point), 0)
        self.assertEqual(db.list_whatsapp_messages(business["id"]), [])

        with (
            patch.object(whatsapp, "_TOKEN", "token"),
            patch.object(whatsapp, "_PHONE_ID", "phone-id"),
        ):
            self.assertEqual(scheduler.send_payment_reminders(now=point), 1)
            self.assertEqual(
                scheduler.send_payment_reminders(now=point + timedelta(days=1)),
                0,
            )
            self.assertEqual(
                scheduler.send_payment_reminders(now=point + timedelta(days=4)),
                1,
            )

        messages = list(reversed(db.list_whatsapp_messages(business["id"])))
        self.assertEqual(len(messages), 2)
        self.assertEqual(
            [message["idempotency_key"].rsplit(":", 1)[1] for message in messages],
            ["3", "7"],
        )
        params = json.loads(messages[0]["template_params"])
        self.assertEqual(messages[0]["status"], "queued")
        self.assertEqual(messages[0]["to_phone"], "34600111222")
        self.assertEqual(
            messages[0]["template_name"],
            config.WHATSAPP_TEMPLATE_PAYMENT_REMINDER,
        )
        self.assertEqual(params[3], "81,00 €")
        self.assertTrue(params[4].startswith(f"{config.BASE_URL}/p/"))
        self.assertEqual(
            db.list_whatsapp_messages(other_business["id"]), []
        )
        self.assertIsNone(
            db.get_whatsapp_message_by_idempotency_key(
                messages[0]["idempotency_key"], other_business["id"]
            )
        )
        events = [
            event for event in db.export_business_data(business["id"])[
                "product_events"
            ]
            if event["event_name"] == "payment_reminder_queued"
        ]
        self.assertEqual(
            [json.loads(event["event_data"])["step"] for event in events],
            [3, 7],
        )

    def test_first_late_run_uses_highest_step_and_respects_opt_out(self):
        business, client = self.make_business("Cadencia A")
        opt_out, opt_out_client = self.make_business("Cadencia B")
        no_phone, no_phone_client = self.make_business("Cadencia C")
        paid_business, paid_client = self.make_business("Cadencia D")
        invoice = self._issued_invoice(business, client)
        self._issued_invoice(opt_out, opt_out_client)
        no_phone_invoice = db.issue_invoice(
            db.add_invoice(
                no_phone_client["id"], "Sin teléfono", 100,
                business_id=no_phone["id"],
            )["id"],
            no_phone["id"],
        )
        db.update_payment_reminder_settings(
            business["id"], enabled=True, days=[3, 7, 15]
        )
        db.update_payment_reminder_settings(
            no_phone["id"], enabled=True, days="3,7,15"
        )
        paid_invoice = self._issued_invoice(paid_business, paid_client)
        db.update_payment_reminder_settings(
            paid_business["id"], enabled=True, days="3,7,15"
        )
        db.mark_invoice_paid(paid_invoice["id"], paid_business["id"])

        with (
            patch.object(whatsapp, "_TOKEN", "token"),
            patch.object(whatsapp, "_PHONE_ID", "phone-id"),
        ):
            queued = scheduler.send_payment_reminders(
                now=self._reminder_time(invoice, 10)
            )

        self.assertEqual(queued, 1)
        message = db.list_whatsapp_messages(business["id"])[0]
        self.assertTrue(message["idempotency_key"].endswith(":7"))
        self.assertEqual(db.list_whatsapp_messages(opt_out["id"]), [])
        self.assertEqual(db.list_whatsapp_messages(no_phone["id"]), [])
        self.assertEqual(db.list_whatsapp_messages(paid_business["id"]), [])
        self.assertEqual(
            db.get_invoice(no_phone_invoice["id"], no_phone["id"])[
                "reminders_sent"
            ],
            0,
        )

    def test_settings_are_validated_and_visible_in_ajustes(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, _ = self.make_business("Ajustes recordatorios")
        db.create_user(
            "recordatorios@example.com",
            auth.hash_password("password-segura-123"),
            business["id"],
        )
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                login = client.post(
                    "/login",
                    data={
                        "email": "recordatorios@example.com",
                        "password": "password-segura-123",
                    },
                    follow_redirects=False,
                )
                self.assertEqual(login.status_code, 303)
                saved = client.post(
                    f"/b/{business['id']}/payment-reminders",
                    data={
                        "payment_reminders_enabled": "1",
                        "payment_reminder_days": "2,5,10",
                    },
                    follow_redirects=False,
                )
                self.assertEqual(saved.status_code, 303)
                settings = db.get_business(business["id"])
                self.assertTrue(settings["payment_reminders_enabled"])
                self.assertEqual(settings["payment_reminder_days"], "2,5,10")

                invalid = client.post(
                    f"/b/{business['id']}/payment-reminders",
                    data={
                        "payment_reminders_enabled": "1",
                        "payment_reminder_days": "0,200",
                    },
                    follow_redirects=False,
                )
                self.assertIn("error=recordatorios", invalid.headers["location"])
                self.assertEqual(
                    db.get_business(business["id"])["payment_reminder_days"],
                    "2,5,10",
                )
                page = client.get(f"/b/{business['id']}/ajustes")
                self.assertEqual(page.status_code, 200)
                self.assertIn("Recordatorios de cobro", page.text)
                self.assertIn("Centro de control de Noesis", page.text)
                self.assertIn("Noesis nunca mueve dinero", page.text)
                self.assertIn("Yo vigilo que todo siga funcionando", page.text)
                self.assertIn("Calendario externo", page.text)

                requested = client.post(
                    f"/api/{business['id']}/integrations/banking",
                    json={"action": "request"},
                )
                self.assertEqual(requested.status_code, 200)
                self.assertEqual(requested.json()["item"]["state"], "requested")
                invalid_enable = client.post(
                    f"/api/{business['id']}/integrations/banking",
                    json={"action": "enable"},
                )
                self.assertEqual(invalid_enable.status_code, 400)

                db.set_whatsapp_status(
                    business["id"], "conectado", phone="600111222"
                )
                queued = db.enqueue_whatsapp_message(
                    business_id=business["id"], to_phone="34600111222",
                    message_type="text", text_body="Pendiente",
                )
                disconnected = client.post(
                    f"/api/{business['id']}/integrations/whatsapp",
                    json={"action": "disconnect"},
                )
                self.assertEqual(disconnected.status_code, 200)
                self.assertIsNone(db.get_business(business["id"])["whatsapp_phone"])
                cancelled = db.get_whatsapp_message(
                    queued["id"], business["id"]
                )
                self.assertEqual(cancelled["status"], "failed")
                self.assertIn("Cancelado", cancelled["last_error"])
                self.assertEqual(
                    disconnected.json()["health"]["whatsapp"].get("failed", 0),
                    0,
                )

                permission = client.post(
                    f"/api/{business['id']}/assistant/permissions",
                    json={
                        "action_key": "payment_reminders",
                        "mode": "blocked",
                    },
                )
                self.assertEqual(permission.status_code, 200)
                self.assertEqual(permission.json()["mode"], "blocked")
                unsafe = client.post(
                    f"/api/{business['id']}/assistant/permissions",
                    json={"action_key": "bank_transfer", "mode": "automatic"},
                )
                self.assertEqual(unsafe.status_code, 400)


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

    def test_payment_api_is_isolated_and_portal_shows_remaining_amount(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business_a, client_a = self.make_business("API Cobros A")
        business_b, client_b = self.make_business("API Cobros B")
        invoice_a = db.issue_invoice(
            db.add_invoice(
                client_a["id"], "Anticipo API", 100,
                business_id=business_a["id"],
            )["id"],
            business_a["id"],
        )
        invoice_b = db.issue_invoice(
            db.add_invoice(
                client_b["id"], "Factura ajena", 100,
                business_id=business_b["id"],
            )["id"],
            business_b["id"],
        )
        db.update_payment_details(
            business_a["id"], iban="ES9121000418450200051332"
        )
        token = db.get_or_create_portal_token(
            business_a["id"], client_a["id"]
        )
        db.create_user(
            "cobros-api@example.com",
            auth.hash_password("password-segura-123"),
            business_a["id"],
        )

        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                login = client.post(
                    "/login",
                    data={
                        "email": "cobros-api@example.com",
                        "password": "password-segura-123",
                    },
                    follow_redirects=False,
                )
                self.assertEqual(login.status_code, 303)
                created = client.post(
                    f"/api/{business_a['id']}/invoices/{invoice_a['id']}/payments",
                    json={"amount": 40, "method": "transferencia"},
                )
                self.assertEqual(created.status_code, 201)
                self.assertEqual(created.json()["amount"], 40)
                listed = client.get(
                    f"/api/{business_a['id']}/invoices/{invoice_a['id']}/payments"
                )
                self.assertEqual(len(listed.json()), 1)
                self.assertEqual(
                    client.get(
                        f"/api/{business_a['id']}/invoices/"
                        f"{invoice_b['id']}/payments"
                    ).status_code,
                    404,
                )
                self.assertEqual(
                    client.post(
                        f"/api/{business_b['id']}/invoices/"
                        f"{invoice_b['id']}/payments",
                        json={"amount": 10},
                    ).status_code,
                    403,
                )
                invalid = client.post(
                    f"/api/{business_a['id']}/invoices/{invoice_a['id']}/payments",
                    json={"amount": 0},
                )
                self.assertEqual(invalid.status_code, 400)

                portal = client.get(f"/p/{token}")
                self.assertEqual(portal.status_code, 200)
                self.assertIn("Importe pendiente", portal.text)
                self.assertIn("81,00", portal.text)
        self.assertEqual(
            db.list_invoice_payments(invoice_b["id"], business_b["id"]), []
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
                setup_page = client.get(setup_url)
                self.assertEqual(setup_page.status_code, 200)
                self.assertIn("Experiencia completa", setup_page.text)
                created_user = db.get_user_by_email("piloto@example.com")
                self.assertEqual(
                    db.integration_setting(
                        created_user["business_id"], "ai_external"
                    )["mode"],
                    "disabled",
                )

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
                self.assertEqual(
                    db.integration_setting(
                        created_user["business_id"], "ai_external"
                    )["mode"],
                    "enabled",
                )

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

    def test_team_productivity_ranks_by_sales_and_isolates_tenants(self):
        business, client = self.make_business("Rendimiento Equipo")
        ana = db.create_worker(business["id"], "Ana")
        bruno = db.create_worker(business["id"], "Bruno")
        hecho = db.add_job(
            client["id"], "Instalación", price_estimate=300,
            business_id=business["id"],
        )
        menor = db.add_job(
            client["id"], "Revisión", price_estimate=100,
            business_id=business["id"],
        )
        cancelado = db.add_job(
            client["id"], "Cancelado", price_estimate=999,
            business_id=business["id"],
        )
        db.assign_job_worker(hecho["id"], ana["id"], business["id"])
        db.assign_job_worker(menor["id"], bruno["id"], business["id"])
        db.assign_job_worker(cancelado["id"], ana["id"], business["id"])
        db.update_job_status(hecho["id"], "hecho", business["id"])
        db.update_job_status(menor["id"], "hecho", business["id"])
        db.update_job_status(cancelado["id"], "cancelado", business["id"])

        data = db.team_productivity(business["id"], days=30)
        self.assertEqual(data["days"], 30)
        self.assertEqual(
            [item["name"] for item in data["items"]], ["Ana", "Bruno"]
        )
        top = data["items"][0]
        self.assertEqual(top["ventas"], 300.0)
        self.assertEqual(top["jobs_hechos"], 1)
        # El trabajo cancelado no cuenta ni como asignado ni como venta.
        self.assertEqual(top["jobs_asignados"], 1)
        self.assertEqual(top["horas"], 0.0)
        self.assertIsNone(top["eur_hora"])
        self.assertEqual(data["items"][1]["ventas"], 100.0)

        other, _ = self.make_business("Negocio Aislado")
        self.assertEqual(db.team_productivity(other["id"])["items"], [])

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

    def test_worker_whatsapp_shows_plan_updates_task_and_clocks_job(self):
        business, client = self.make_business("Parte WhatsApp")
        worker = db.create_worker(business["id"], "Sara")
        db.bind_worker_phone(
            business["id"], worker["access_code"], "+34 611 555 444"
        )
        project = db.add_project(
            "Reforma cocina", 4000, client_id=client["id"],
            business_id=business["id"],
        )
        job = db.add_job(
            client["id"], "Instalar tubería",
            scheduled_for=f"{date.today().isoformat()}T08:30",
            project_id=project["id"], worker_id=worker["id"],
            business_id=business["id"],
        )
        task = db.add_project_task(
            project["id"], "Probar presión", worker_id=worker["id"],
            job_id=job["id"], business_id=business["id"],
        )

        plan = whatsapp._try_worker_clock("611555444", "HOY")
        self.assertIn("Instalar tubería", plan["reply"])
        self.assertIn("Probar presión", plan["reply"])
        entered = whatsapp._try_worker_clock(
            "611555444", f"ENTRADA #{job['id']}"
        )
        self.assertTrue(entered["clocked"])
        self.assertEqual(
            db.worker_open_shift(worker["id"], business["id"])["job_id"],
            job["id"],
        )
        done = whatsapp._try_worker_clock(
            "611555444", f"HECHO T{task['id']}"
        )
        self.assertTrue(done["task_updated"])
        self.assertEqual(
            db.get_project_task(task["id"], business["id"])["status"], "hecha"
        )
        exited = whatsapp._try_worker_clock("611555444", "SALIDA")
        self.assertTrue(exited["clocked"])


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

    def test_worker_sees_project_tasks_and_can_complete_only_their_own(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, client_record = self.make_business("Equipo con proyectos")
        other_business, other_client = self.make_business("Proyecto ajeno")
        worker = db.create_worker(business["id"], "Nora")
        other_worker = db.create_worker(other_business["id"], "Otro")
        project = db.add_project(
            "Instalación Hotel", 5000, client_id=client_record["id"],
            business_id=business["id"],
        )
        job = db.add_job(
            client_record["id"], "Montar colector",
            scheduled_for=f"{date.today().isoformat()}T09:00",
            project_id=project["id"], worker_id=worker["id"],
            business_id=business["id"],
        )
        task = db.add_project_task(
            project["id"], "Comprobar presión", business_id=business["id"],
            worker_id=worker["id"], job_id=job["id"], kind="checklist",
        )
        foreign_project = db.add_project(
            "Ajeno", 100, client_id=other_client["id"],
            business_id=other_business["id"],
        )
        foreign_task = db.add_project_task(
            foreign_project["id"], "No visible", business_id=other_business["id"],
            worker_id=other_worker["id"],
        )
        token = db.get_or_create_worker_token(business["id"], worker["id"])

        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                page = client.get(f"/t/{token}")
                self.assertEqual(page.status_code, 200)
                self.assertIn("Instalación Hotel", page.text)
                self.assertIn("Comprobar presión", page.text)
                self.assertNotIn("No visible", page.text)
                updated = client.post(
                    f"/t/{token}/tasks/{task['id']}", json={"status": "hecha"}
                )
                self.assertEqual(updated.status_code, 200)
                blocked = client.post(
                    f"/t/{token}/tasks/{foreign_task['id']}",
                    json={"status": "hecha"},
                )
                self.assertEqual(blocked.status_code, 404)
        self.assertEqual(
            db.get_project_task(task["id"], business["id"])["status"], "hecha"
        )

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


class VerifactuTestCase(unittest.TestCase):
    make_business = BackendTestCase.make_business

    def setUp(self):
        BackendTestCase.setUp(self)
        self.original_producer_nif = config.VERIFACTU_PRODUCER_NIF
        self.original_verifactu_transport = (
            config.VERIFACTU_CERT_PATH,
            config.VERIFACTU_KEY_PATH,
            config.VERIFACTU_AEAT_ENV,
        )
        config.VERIFACTU_PRODUCER_NIF = "B87654321"
        config.VERIFACTU_CERT_PATH = ""
        config.VERIFACTU_KEY_PATH = ""
        config.VERIFACTU_AEAT_ENV = ""

    def tearDown(self):
        config.VERIFACTU_PRODUCER_NIF = self.original_producer_nif
        (
            config.VERIFACTU_CERT_PATH,
            config.VERIFACTU_KEY_PATH,
            config.VERIFACTU_AEAT_ENV,
        ) = self.original_verifactu_transport
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

    def test_partial_payment_never_changes_verifactu_records(self):
        business, client = self._enabled_business("Verifactu con anticipo")
        invoice = self._issue(business, client)
        record_before = db.get_invoice_record(invoice["id"], business["id"])
        events_before = db.list_invoice_events(business["id"])

        db.add_invoice_payment(
            invoice["id"], 40, method="transferencia",
            business_id=business["id"],
        )

        self.assertEqual(
            db.get_invoice_record(invoice["id"], business["id"]),
            record_before,
        )
        self.assertEqual(db.list_invoice_events(business["id"]), events_before)

    def test_official_hash_example_and_qr_parameters(self):
        # Vector 6.1 de la especificación AEAT v0.1.2:
        # Veri-Factu_especificaciones_huella_hash_registros.pdf.
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

    def test_official_hash_example_with_previous_record(self):
        # Vector 6.2 de la especificación AEAT v0.1.2.
        digest = verifactu.invoice_record_hash(
            issuer_nif="89890001K",
            invoice_number="12345679/G34",
            issue_date="01-01-2024",
            invoice_type="F1",
            vat_total="12.35",
            invoice_total="123.45",
            previous_hash=(
                "3C464DAF61ACB827C65FDA19F352A4E3BDC2C640E9E9FC4CC058073F38F12F60"
            ),
            generated_at="2024-01-01T19:20:35+01:00",
        )
        self.assertEqual(
            digest,
            "F7B94CFD8924EDFF273501B01EE5153E4CE8F259766F88CF6ACB8935802A2B97",
        )

    def test_transport_is_disabled_without_certificate(self):
        business, client = self._enabled_business("Verifactu Sin Certificado")
        invoice = self._issue(business, client)
        queued = db.get_verifactu_outbox(invoice["id"], business["id"])
        self.assertEqual(queued["status"], "pendiente")

        with patch.object(verifactu_client, "submit_records") as submit:
            self.assertEqual(scheduler.process_verifactu_outbox(), 0)
        submit.assert_not_called()
        self.assertEqual(
            db.get_invoice(invoice["id"], business["id"])["status"], "enviada"
        )

    def test_outbox_accepts_response_and_stores_csv(self):
        business, client = self._enabled_business("Verifactu Aceptada")
        invoice = self._issue(business, client)
        result = verifactu_client.SubmissionResult(
            status="aceptado",
            csv="CSV-AEAT-001",
            wait_seconds=0,
            error_code=None,
            error_description=None,
            global_status="Correcto",
            raw_response="<Respuesta>correcta</Respuesta>",
        )
        with (
            patch.object(verifactu_client, "is_enabled", return_value=True),
            patch.object(verifactu_client, "submit_records", return_value=result),
        ):
            self.assertEqual(scheduler.process_verifactu_outbox(), 1)

        queued = db.get_verifactu_outbox(invoice["id"], business["id"])
        self.assertEqual(queued["status"], "aceptado")
        self.assertEqual(queued["aeat_csv"], "CSV-AEAT-001")
        self.assertIsNone(
            db.get_verifactu_outbox(invoice["id"], business["id"] + 999)
        )
        self.assertEqual(
            [event["event_type"] for event in db.list_invoice_events(business["id"])],
            ["alta", "remision", "aceptacion"],
        )
        visible = db.list_invoices(business["id"])[0]
        self.assertEqual(visible["verifactu_status"], "aceptado")
        self.assertEqual(visible["verifactu_csv"], "CSV-AEAT-001")

    def test_rejected_record_is_not_resent_identically(self):
        business, client = self._enabled_business("Verifactu Rechazada")
        invoice = self._issue(business, client)
        result = verifactu_client.SubmissionResult(
            status="rechazado",
            csv=None,
            wait_seconds=0,
            error_code="1104",
            error_description="Huella incorrecta",
            global_status="Incorrecto",
            raw_response="<Respuesta>rechazada</Respuesta>",
        )
        with (
            patch.object(verifactu_client, "is_enabled", return_value=True),
            patch.object(
                verifactu_client, "submit_records", return_value=result
            ) as submit,
        ):
            self.assertEqual(scheduler.process_verifactu_outbox(), 1)
            self.assertEqual(scheduler.process_verifactu_outbox(), 0)
        self.assertEqual(submit.call_count, 1)
        queued = db.get_verifactu_outbox(invoice["id"], business["id"])
        self.assertEqual(queued["status"], "rechazado")
        self.assertEqual(queued["aeat_error_code"], "1104")
        self.assertIn(
            "rechazo",
            [event["event_type"] for event in db.list_invoice_events(business["id"])],
        )

    def test_transport_errors_use_exponential_backoff(self):
        business, client = self._enabled_business("Verifactu Reintento")
        invoice = self._issue(business, client)
        with (
            patch.object(verifactu_client, "is_enabled", return_value=True),
            patch.object(
                verifactu_client,
                "submit_records",
                side_effect=verifactu_client.VerifactuTransportError(
                    "AEAT temporalmente no disponible"
                ),
            ) as submit,
            patch.object(config, "VERIFACTU_RETRY_BASE_SECONDS", 30),
            patch.object(config, "VERIFACTU_RETRY_MAX_SECONDS", 3600),
        ):
            first_start = datetime.now()
            self.assertEqual(scheduler.process_verifactu_outbox(), 0)
            first = db.get_verifactu_outbox(invoice["id"], business["id"])
            first_delay = (
                datetime.fromisoformat(first["next_attempt_at"]) - first_start
            ).total_seconds()
            self.assertEqual(first["status"], "pendiente")
            self.assertEqual(first["attempts"], 1)
            self.assertGreaterEqual(first_delay, 29)

            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE verifactu_outbox SET next_attempt_at=? "
                    "WHERE id=? AND business_id=?",
                    ("2000-01-01T00:00:00", first["id"], business["id"]),
                )
            second_start = datetime.now()
            self.assertEqual(scheduler.process_verifactu_outbox(), 0)
            second = db.get_verifactu_outbox(invoice["id"], business["id"])
            second_delay = (
                datetime.fromisoformat(second["next_attempt_at"]) - second_start
            ).total_seconds()

        self.assertEqual(submit.call_count, 2)
        self.assertEqual(second["attempts"], 2)
        self.assertGreaterEqual(second_delay, 59)
        self.assertIn("temporalmente", second["last_error"])

    def test_aeat_wait_postpones_the_rest_of_the_queue(self):
        business, client = self._enabled_business("Verifactu Espera")
        first = self._issue(business, client, "Primera", 100)
        second = self._issue(business, client, "Segunda", 200)
        result = verifactu_client.SubmissionResult(
            status="aceptado",
            csv="CSV-ESPERA",
            wait_seconds=120,
            error_code=None,
            error_description=None,
            global_status="Correcto",
            raw_response="<Respuesta>espera</Respuesta>",
        )
        with (
            patch.object(verifactu_client, "is_enabled", return_value=True),
            patch.object(
                verifactu_client, "submit_records", return_value=result
            ) as submit,
        ):
            self.assertEqual(scheduler.process_verifactu_outbox(limit=25), 1)
            self.assertEqual(scheduler.process_verifactu_outbox(limit=25), 0)
        self.assertEqual(submit.call_count, 1)
        self.assertEqual(
            db.get_verifactu_outbox(first["id"], business["id"])["status"],
            "aceptado",
        )
        waiting = db.get_verifactu_outbox(second["id"], business["id"])
        self.assertEqual(waiting["status"], "pendiente")
        self.assertGreater(waiting["next_attempt_at"], waiting["created_at"])

    def test_soap_response_parser_maps_official_states(self):
        payload = b"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:r="https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/RespuestaSuministro.xsd">
 <soapenv:Body><r:RespuestaRegFactuSistemaFacturacion>
  <r:CSV>CSV-123</r:CSV><r:TiempoEsperaEnvio>60</r:TiempoEsperaEnvio>
  <r:EstadoEnvio>ParcialmenteCorrecto</r:EstadoEnvio>
  <r:RespuestaLinea><r:EstadoRegistro>AceptadoConErrores</r:EstadoRegistro>
   <r:CodigoErrorRegistro>2000</r:CodigoErrorRegistro>
   <r:DescripcionErrorRegistro>Aviso admisible</r:DescripcionErrorRegistro>
  </r:RespuestaLinea>
 </r:RespuestaRegFactuSistemaFacturacion></soapenv:Body>
</soapenv:Envelope>"""
        result = verifactu_client.parse_response(payload)
        self.assertEqual(result.status, "aceptado_con_errores")
        self.assertEqual(result.csv, "CSV-123")
        self.assertEqual(result.wait_seconds, 60)
        self.assertEqual(result.error_code, "2000")

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
                invoices_page = client.get(f"/b/{business['id']}/facturas")
                settings_page = client.get(f"/b/{business['id']}/ajustes")
                self.assertEqual(invoices_page.status_code, 200)
                self.assertEqual(settings_page.status_code, 200)
                self.assertIn("Veri*Factu", invoices_page.text)
                self.assertIn("Remisión AEAT desactivada", settings_page.text)
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


class PendingActionTestCase(unittest.TestCase):
    setUp = BackendTestCase.setUp
    tearDown = BackendTestCase.tearDown
    make_business = BackendTestCase.make_business

    def test_pending_actions_replace_expire_and_isolate(self):
        business, _ = self.make_business("Pendientes A")
        other, _ = self.make_business("Pendientes B")
        db.set_pending_action(
            business["id"], "34600111222", "gasto", {"amount": 10}
        )
        db.set_pending_action(
            business["id"], "34600111222", "gasto", {"amount": 20}
        )
        pending = db.get_pending_action(business["id"], "34600111222")
        self.assertEqual(json.loads(pending["payload"])["amount"], 20)
        # Aislamiento: otro negocio no ve la pendiente de ese teléfono.
        self.assertIsNone(db.get_pending_action(other["id"], "34600111222"))
        # Caducidad: una pendiente vencida se purga al leerla.
        db.set_pending_action(
            business["id"], "34600111222", "gasto", {"amount": 30},
            ttl_minutes=-1,
        )
        self.assertIsNone(db.get_pending_action(business["id"], "34600111222"))
        # Borrado explícito.
        db.set_pending_action(business["id"], "34600111222", "gasto", {})
        db.clear_pending_action(business["id"], "34600111222")
        self.assertIsNone(db.get_pending_action(business["id"], "34600111222"))


class WhatsappMediaTestCase(unittest.TestCase):
    setUp = BackendTestCase.setUp
    tearDown = BackendTestCase.tearDown
    make_business = BackendTestCase.make_business

    def _connected_business(self, name, phone="600111222"):
        business, client = self.make_business(name)
        db.set_whatsapp_status(business["id"], "conectado", phone=phone)
        return db.get_business(business["id"]), client

    def test_photo_creates_draft_and_yes_confirms_once(self):
        from noesis.adapters import extraction

        business, _ = self._connected_business("Fotos WhatsApp")
        extracted = {
            "concept": "Material eléctrico", "amount": 43.20,
            "vat_rate": 21, "date": "2026-07-02", "supplier": "Ferretería",
        }
        replies = []
        with (
            patch.object(whatsapp, "_download_media",
                         return_value=b"\xff\xd8\xff\xe0foto"),
            patch.object(extraction, "extract_expense",
                         return_value=extracted),
            patch.object(whatsapp, "send",
                         side_effect=lambda phone, text, **kw:
                         replies.append(text)),
        ):
            result = whatsapp.handle_inbound({
                "from": "34600111222", "id": "wamid-foto-1",
                "image_id": "media-1", "image_mime": "image/jpeg",
            })
            self.assertTrue(result["results"][0]["ingested"])
            self.assertIn("¿Lo apunto como gasto?", replies[-1])
            # El gasto NO existe aún: solo hay borrador pendiente.
            self.assertEqual(db.list_expenses(business["id"]), [])

            whatsapp.handle_inbound({
                "from": "34600111222", "id": "wamid-foto-2", "text": "SÍ",
            })
        expenses = db.list_expenses(business["id"])
        self.assertEqual(len(expenses), 1)
        self.assertEqual(expenses[0]["amount"], 43.20)
        self.assertIn("Apuntado ✅", replies[-1])
        # La pendiente se consumió: repetir SÍ no duplica.
        with patch.object(whatsapp, "send",
                          side_effect=lambda phone, text, **kw:
                          replies.append(text)):
            whatsapp.handle_inbound({
                "from": "34600111222", "id": "wamid-foto-3", "text": "sí",
            })
        self.assertEqual(len(db.list_expenses(business["id"])), 1)

    def test_photo_no_discards_and_unknown_phone_gets_invite(self):
        from noesis.adapters import extraction

        business, _ = self._connected_business("Fotos No")
        replies = []
        with (
            patch.object(whatsapp, "_download_media", return_value=b"foto"),
            patch.object(extraction, "extract_expense", return_value={
                "concept": "x", "amount": 10, "vat_rate": None,
                "date": None, "supplier": None,
            }),
            patch.object(whatsapp, "send",
                         side_effect=lambda phone, text, **kw:
                         replies.append(text)),
        ):
            whatsapp.handle_inbound({
                "from": "34600111222", "id": "wamid-no-1",
                "image_id": "media-2", "image_mime": "image/png",
            })
            whatsapp.handle_inbound({
                "from": "34600111222", "id": "wamid-no-2", "text": "no",
            })
            self.assertIn("Descartado", replies[-1])
            self.assertEqual(db.list_expenses(business["id"]), [])
            # Teléfono desconocido con foto: invitación, jamás ingesta.
            whatsapp.handle_inbound({
                "from": "34999888777", "id": "wamid-no-3",
                "image_id": "media-3", "image_mime": "image/jpeg",
            })
            self.assertIn("no está dado de alta", replies[-1])

    def test_voice_money_order_requires_confirmation(self):
        business, _ = self._connected_business("Voz Dinero")
        replies = []
        handled = []
        with (
            patch.object(whatsapp, "_audio_to_text",
                         return_value="hazle una factura a Carlos de 100"),
            patch.object(whatsapp.chat, "handle",
                         side_effect=lambda bid, text, **kwargs:
                         handled.append(text) or {"reply": "hecho"}),
            patch.object(whatsapp, "send",
                         side_effect=lambda phone, text, **kw:
                         replies.append(text)),
        ):
            whatsapp.handle_inbound({
                "from": "34600111222", "id": "wamid-voz-1",
                "audio_id": "audio-1",
            })
            # No se ejecuta: se pide confirmación.
            self.assertEqual(handled, [])
            self.assertIn("¿Lo hago?", replies[-1])
            whatsapp.handle_inbound({
                "from": "34600111222", "id": "wamid-voz-2", "text": "vale",
            })
            self.assertEqual(
                handled, ["hazle una factura a Carlos de 100"]
            )

    def test_pdf_document_is_saved_to_papers(self):
        business, _ = self._connected_business("PDFs WhatsApp")
        from noesis.documents import repo as docrepo

        replies = []
        with (
            patch.object(whatsapp, "_download_media",
                         return_value=b"%PDF-1.4 contenido"),
            patch.object(whatsapp, "send",
                         side_effect=lambda phone, text, **kw:
                         replies.append(text)),
        ):
            result = whatsapp.handle_inbound({
                "from": "34600111222", "id": "wamid-pdf-1",
                "media_document_id": "media-4",
                "media_document_mime": "application/pdf",
                "media_document_filename": "factura-luz.pdf",
            })
        self.assertTrue(result["results"][0]["ingested"])
        docs = docrepo.list_for_business(business["id"])
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["filename"], "factura-luz.pdf")
        self.assertIn("papeles", replies[-1])

    def test_pdf_received_invoice_is_classified_and_confirmed_by_whatsapp(self):
        business, _ = self._connected_business("Factura PDF")
        replies = []
        classification = {
            "kind": "factura_recibida", "confidence": 94,
            "reason": "El negocio figura como receptor.", "method": "ia",
        }
        draft = {
            "number": "P-44", "issued_on": "2026-07-01", "due_on": None,
            "supplier": "Ferretería Sol", "supplier_nif": "B22222222",
            "customer": business["name"], "customer_nif": None,
            "base": 100, "vat_rate": 21, "vat_amount": 21,
            "irpf_amount": 0, "total": 121, "confidence": 92,
        }
        with (
            patch.object(whatsapp, "_download_media", return_value=b"%PDF-1.4 factura"),
            patch.object(extraction, "classify_document", return_value=classification),
            patch.object(extraction, "extract_invoice", return_value=draft),
            patch.object(whatsapp, "send",
                         side_effect=lambda phone, text, **kw: replies.append(text)),
        ):
            whatsapp.handle_inbound({
                "from": "34600111222", "id": "wamid-pdf-smart-1",
                "media_document_id": "media-smart",
                "media_document_mime": "application/pdf",
                "media_document_filename": "proveedor.pdf",
            })
            pending = db.get_pending_action(business["id"], "34600111222")
            self.assertEqual(pending["kind"], "factura_recibida")
            self.assertIn("¿La registro?", replies[-1])
            whatsapp.handle_inbound({
                "from": "34600111222", "id": "wamid-pdf-smart-2", "text": "sí",
            })
        received = db.list_received_invoices(business["id"])
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["total"], 121)
        self.assertIn("Hecho", replies[-1])


class WhatsappReportsTestCase(unittest.TestCase):
    setUp = BackendTestCase.setUp
    tearDown = BackendTestCase.tearDown
    make_business = BackendTestCase.make_business

    def test_report_prefs_resolve_tolerantly(self):
        prefs = db.resolve_whatsapp_reports(None)
        self.assertTrue(prefs["cierre_tarde"])
        self.assertEqual(prefs["hora_tarde"], 19)
        broken = db.resolve_whatsapp_reports("{json roto")
        self.assertEqual(broken, db.WHATSAPP_REPORT_DEFAULTS)
        custom = db.resolve_whatsapp_reports(
            '{"hora_tarde": 20, "brief_manana": false, "desconocida": 1}'
        )
        self.assertEqual(custom["hora_tarde"], 20)
        self.assertFalse(custom["brief_manana"])
        out_of_range = db.resolve_whatsapp_reports('{"hora_tarde": 3}')
        self.assertEqual(out_of_range["hora_tarde"], 19)

    def test_daily_closing_respects_hour_prefs_and_idempotency(self):
        business, _ = self.make_business("Cierre A")
        db.set_whatsapp_status(business["id"], "conectado", phone="600111222")
        db.update_whatsapp_reports(business["id"], {"hora_tarde": 19})
        opted_out, _ = self.make_business("Cierre B")
        db.set_whatsapp_status(opted_out["id"], "conectado", phone="600333444")
        db.update_whatsapp_reports(opted_out["id"], {"cierre_tarde": False})

        at_19 = datetime.now().replace(hour=19, minute=5)
        with (
            patch.object(whatsapp, "_TOKEN", "token"),
            patch.object(whatsapp, "_PHONE_ID", "phone-id"),
            patch.object(whatsapp, "_post_to_meta", return_value="wamid-x"),
        ):
            self.assertEqual(scheduler.send_daily_closings(now=at_19), 1)
            # Idempotente dentro del mismo día.
            self.assertEqual(scheduler.send_daily_closings(now=at_19), 0)
            # A otra hora no toca.
            at_18 = at_19.replace(hour=18)
            self.assertEqual(scheduler.send_daily_closings(now=at_18), 0)
        messages = db.list_whatsapp_messages(business["id"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            messages[0]["template_name"], config.WHATSAPP_TEMPLATE_DAILY_CLOSING
        )
        self.assertEqual(db.list_whatsapp_messages(opted_out["id"]), [])

    def test_global_search_finds_and_isolates(self):
        business, client = self.make_business("Buscador Uno")
        other, other_client = self.make_business("Buscador Dos")
        invoice = db.add_invoice(
            client["id"], "Cambio de caldera", 350, business_id=business["id"]
        )
        db.issue_invoice(invoice["id"], business["id"])
        db.add_job(client["id"], "Revisar caldera del ático",
                   business_id=business["id"])
        db.add_invoice(other_client["id"], "Caldera ajena", 100,
                       business_id=other["id"])

        results = db.global_search(business["id"], "caldera")
        self.assertEqual(len(results["invoices"]), 1)
        self.assertEqual(results["invoices"][0]["concept"], "Cambio de caldera")
        self.assertEqual(len(results["jobs"]), 1)
        # Nada del otro negocio se cuela.
        concepts = [i["concept"] for i in results["invoices"]]
        self.assertNotIn("Caldera ajena", concepts)
        # Por nombre de cliente también encuentra.
        by_client = db.global_search(business["id"], "cliente fiscal")
        self.assertTrue(by_client["clients"])
        # Consultas cortas no buscan.
        self.assertEqual(db.global_search(business["id"], "c"),
                         {"clients": [], "invoices": [], "quotes": [],
                          "jobs": []})

    def test_founder_digest_claims_week_and_lists_admins(self):
        business, _ = self.make_business("Digest Semanal")
        user = db.create_user(
            "founder-digest@example.com", auth.hash_password("clave-larga-123"),
            business["id"],
        )
        with db.get_conn() as conn:
            conn.execute("UPDATE users SET is_admin=1 WHERE id=?", (user["id"],))
        self.assertIn("founder-digest@example.com", db.list_admin_emails())
        self.assertTrue(scheduler.send_founder_digest())
        # La misma semana no se repite.
        self.assertFalse(scheduler.send_founder_digest())

    def test_cash_forecast_and_collection_proposal_flow(self):
        business, client = self.make_business("Piloto Cobros")
        db.set_whatsapp_status(business["id"], "conectado", phone="600111222")
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE clients SET phone='600999888' WHERE id=?",
                (client["id"],),
            )
        invoice = db.add_invoice(
            client["id"], "Trabajo vencido", 200, business_id=business["id"]
        )
        db.issue_invoice(invoice["id"], business["id"])
        ten_days_ago = (datetime.now() - timedelta(days=10)).isoformat(
            timespec="seconds"
        )
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE invoices SET issued_at=? WHERE id=?",
                (ten_days_ago, invoice["id"]),
            )
        db.add_expense("Material", 90, business_id=business["id"])

        forecast = db.cash_forecast(business["id"])
        self.assertEqual(forecast["n_facturas"], 1)
        self.assertGreater(forecast["entra"], 0)
        self.assertGreater(forecast["sale"], 0)
        self.assertEqual(
            forecast["neto"],
            round(forecast["entra"] - forecast["sale"]
                  - forecast["iva_reserva"], 2),
        )

        with (
            patch.object(whatsapp, "_TOKEN", "token"),
            patch.object(whatsapp, "_PHONE_ID", "phone-id"),
            patch.object(whatsapp, "_post_to_meta", return_value="wamid-c"),
        ):
            self.assertEqual(scheduler.send_collection_proposals(), 1)
            # Idempotente: mismo día no vuelve a proponer.
            self.assertEqual(scheduler.send_collection_proposals(), 0)
            pending = db.get_pending_action(business["id"], "600111222")
            self.assertEqual(pending["kind"], "reclamar")
            reply = whatsapp._execute_pending(
                db.get_business(business["id"]), "600111222", pending
            )
            self.assertIn("Hecho", reply)
        templates = [
            message.get("template_name")
            for message in db.list_whatsapp_messages(business["id"])
        ]
        self.assertIn(config.WHATSAPP_TEMPLATE_PAYMENT_ALERT, templates)
        self.assertIn(config.WHATSAPP_TEMPLATE_PAYMENT_REMINDER, templates)
        # La acción confirmada queda consumida.
        self.assertIsNone(db.get_pending_action(business["id"], "600111222"))

    def test_quarterly_tax_notice_targets_previous_quarter(self):
        business, _ = self.make_business("Fiscal A")
        db.set_whatsapp_status(business["id"], "conectado", phone="600111222")
        july_first = datetime(2026, 7, 1, 10, 0)
        with (
            patch.object(whatsapp, "_TOKEN", "token"),
            patch.object(whatsapp, "_PHONE_ID", "phone-id"),
            patch.object(whatsapp, "_post_to_meta", return_value="wamid-y"),
        ):
            self.assertEqual(
                scheduler.send_quarterly_tax_notices(now=july_first), 1
            )
            self.assertEqual(
                scheduler.send_quarterly_tax_notices(now=july_first), 0
            )
            # Fuera de los meses de cierre no hace nada.
            self.assertEqual(
                scheduler.send_quarterly_tax_notices(
                    now=datetime(2026, 8, 1, 10, 0)
                ),
                0,
            )
        message = db.list_whatsapp_messages(business["id"])[0]
        params = json.loads(message["template_params"])
        self.assertIn("2T 2026", params[0])


class TranscriptionChainTestCase(unittest.TestCase):
    def test_groq_preferred_when_key_is_set(self):
        from noesis.adapters import transcription

        with patch.object(config, "GROQ_API_KEY", "clave"):
            provider = transcription.get_transcriber()
            self.assertIsInstance(provider, transcription.GroqWhisperProvider)
            self.assertTrue(transcription.available())

    def test_groq_provider_parses_response(self):
        from noesis.adapters import transcription

        response = MagicMock()
        response.read.return_value = json.dumps(
            {"text": " factura a Carlos de 100 "}
        ).encode()
        with (
            patch.object(config, "GROQ_API_KEY", "clave"),
            patch("urllib.request.urlopen", return_value=response),
        ):
            text = transcription.GroqWhisperProvider().transcribe(
                b"audio", "voz.ogg"
            )
        self.assertEqual(text, "factura a Carlos de 100")


class GestoriaTestCase(unittest.TestCase):
    setUp = BackendTestCase.setUp
    tearDown = BackendTestCase.tearDown
    make_business = BackendTestCase.make_business

    def test_settings_validation_and_token_lifecycle(self):
        business, _ = self.make_business("Gestoría A")
        with self.assertRaises(ValueError):
            db.update_gestoria_settings(
                business["id"], cadence="semanal", email="a@b.com"
            )
        with self.assertRaises(ValueError):
            db.update_gestoria_settings(business["id"], cadence="mensual")
        updated = db.update_gestoria_settings(
            business["id"], name="Gestoría García",
            email="Clientes@Gestoria.com", cadence="mensual",
        )
        self.assertEqual(updated["gestoria_email"], "clientes@gestoria.com")
        self.assertEqual(
            db.automation_decision(business["id"], "send_gestoria")["mode"],
            "rules",
        )
        db.update_automation_permission(
            business["id"], "send_gestoria", "confirm"
        )
        db.update_gestoria_settings(
            business["id"], name="Nuevo nombre",
            email="clientes@gestoria.com", cadence="mensual",
        )
        self.assertEqual(
            db.automation_decision(business["id"], "send_gestoria")["mode"],
            "confirm",
        )
        token = updated["gestoria_token"]
        self.assertTrue(token)
        # El token es estable mientras no se revoque.
        self.assertEqual(db.get_or_create_gestoria_token(business["id"]), token)
        resolved = db.resolve_gestoria_token(token)
        self.assertEqual(resolved["id"], business["id"])
        db.revoke_gestoria_token(business["id"])
        self.assertIsNone(db.resolve_gestoria_token(token))

    def test_periods_and_ranges(self):
        business, _ = self.make_business("Gestoría Periodos")
        self.assertEqual(db.gestoria_periods(business["id"]), [])
        db.update_gestoria_settings(
            business["id"], email="g@g.com", cadence="mensual"
        )
        periods = db.gestoria_periods(business["id"])
        self.assertEqual(len(periods), 8)
        previous_month = (date.today().replace(day=1) - timedelta(days=1))
        self.assertEqual(periods[0]["label"], f"{previous_month:%Y-%m}")
        # Rangos: mes y trimestre.
        self.assertEqual(
            db.gestoria_period_range("2026-06"), ("2026-06-01", "2026-06-30")
        )
        self.assertEqual(
            db.gestoria_period_range("2026-T2"), ("2026-04-01", "2026-06-30")
        )
        with self.assertRaises(ValueError):
            db.gestoria_period_range("2026-13")
        with self.assertRaises(ValueError):
            db.gestoria_period_range("../../etc")

    def test_package_contains_invoices_expenses_and_receipts(self):
        import zipfile as zipfile_module
        from noesis.documents import service as docservice
        from noesis.web import gestoria

        business, client = self.make_business("Gestoría Paquete")
        other, _ = self.make_business("Gestoría Ajena")
        invoice = db.add_invoice(
            client["id"], "Reparación", 500, business_id=business["id"]
        )
        db.issue_invoice(invoice["id"], business["id"])
        document = docservice.upload(
            business["id"], "ticket.jpg", b"\xff\xd8\xff\xe0foto",
            kind="ticket", run_ocr=False,
        )
        db.add_expense(
            "Material", 60.5, vat_rate=21, document_id=document["id"],
            business_id=business["id"],
        )
        label = f"{date.today():%Y-%m}"
        data, meta = gestoria.build_package(business["id"], label)
        self.assertEqual(meta["invoices"], 1)
        self.assertEqual(meta["expenses"], 1)
        names = zipfile_module.ZipFile(BytesIO(data)).namelist()
        self.assertIn("01-ingresos/facturas.csv", names)
        self.assertIn("02-gastos/gastos.csv", names)
        self.assertIn("00-resumen/resumen.pdf", names)
        self.assertIn("MANIFIESTO.json", names)
        self.assertEqual(
            len([n for n in names if n.startswith("01-ingresos/facturas/")]), 1
        )
        self.assertEqual(
            len([n for n in names if n.startswith("02-gastos/justificantes/")]), 1
        )
        deliveries = db.list_gestoria_deliveries(business["id"])
        self.assertEqual(deliveries[0]["version"], 1)
        self.assertEqual(deliveries[0]["manifest"]["counts"]["expenses"], 1)
        _same_data, same_meta = gestoria.build_package(business["id"], label)
        self.assertEqual(same_meta["version"], 1)
        db.add_expense("Peaje", 5, business_id=business["id"])
        _changed_data, changed_meta = gestoria.build_package(
            business["id"], label
        )
        self.assertEqual(changed_meta["version"], 2)
        # El paquete del negocio vacío no arrastra nada del otro.
        empty, empty_meta = gestoria.build_package(other["id"], label)
        self.assertEqual(empty_meta["invoices"], 0)
        empty_names = zipfile_module.ZipFile(BytesIO(empty)).namelist()
        self.assertEqual(
            [n for n in empty_names
             if n.startswith("02-gastos/justificantes/")], []
        )

    def test_public_portal_and_send_now(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, _ = self.make_business("Gestoría Portal")
        db.update_gestoria_settings(
            business["id"], email="g@gestoria.com", cadence="mensual"
        )
        token = db.get_business(business["id"])["gestoria_token"]
        db.create_user(
            "gestoria-owner@example.com",
            auth.hash_password("password-segura-123"),
            business["id"],
        )
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                page = client.get(f"/g/{token}")
                self.assertEqual(page.status_code, 200)
                self.assertIn("Gestoría Portal", page.text)
                self.assertEqual(client.get("/g/token-falso").status_code, 404)
                label = f"{date.today():%Y-%m}"
                package = client.get(f"/g/{token}/paquete/{label}")
                self.assertEqual(package.status_code, 200)
                self.assertEqual(
                    package.headers["content-type"], "application/zip"
                )
                bad = client.get(f"/g/{token}/paquete/2026-99")
                self.assertEqual(bad.status_code, 404)

                login = client.post("/login", data={
                    "email": "gestoria-owner@example.com",
                    "password": "password-segura-123",
                }, follow_redirects=False)
                self.assertEqual(login.status_code, 303)
                sent = client.post(
                    f"/b/{business['id']}/gestoria/send-now",
                    follow_redirects=False,
                )
                self.assertEqual(sent.status_code, 303)
                self.assertIn("gestoria", sent.headers["location"])

    def test_scheduler_notifies_once_per_period(self):
        from noesis.adapters import email as email_adapter

        business, _ = self.make_business("Gestoría Job")
        db.update_gestoria_settings(
            business["id"], email="g@gestoria.com", cadence="mensual"
        )
        off_business, _ = self.make_business("Gestoría Off")
        first_of_month = datetime(2026, 7, 2, 9, 30)
        emails = []
        with (
            patch.object(email_adapter, "available", return_value=True),
            patch.object(email_adapter, "send_email",
                         side_effect=lambda to, subject, body, **kw:
                         emails.append(to) or True),
        ):
            self.assertEqual(
                scheduler.send_gestoria_packages(now=first_of_month), 1
            )
            self.assertEqual(
                scheduler.send_gestoria_packages(now=first_of_month), 0
            )
            # Pasado el día 5 no se dispara.
            self.assertEqual(
                scheduler.send_gestoria_packages(
                    now=datetime(2026, 7, 9, 9, 30)
                ),
                0,
            )
        self.assertEqual(emails, ["g@gestoria.com"])


class AdminCommandCenterTestCase(unittest.TestCase):
    setUp = BackendTestCase.setUp
    tearDown = BackendTestCase.tearDown
    make_business = BackendTestCase.make_business

    def test_overview_includes_contact_activity_and_ai_usage(self):
        business, client = self.make_business("Admin Uno")
        db.set_whatsapp_status(business["id"], "conectado", phone="600111222")
        invoice = db.add_invoice(
            client["id"], "Trabajo", 200, business_id=business["id"]
        )
        db.issue_invoice(invoice["id"], business["id"])
        db.add_invoice_payment(invoice["id"], 100, business_id=business["id"])
        db.record_product_event(
            business["id"], "ai_usage",
            json.dumps({"model": "haiku", "in": 900, "out": 120}),
        )
        db.record_product_event(
            business["id"], "media_ingested",
            json.dumps({"type": "image", "extracted": True}),
        )
        data = db.admin_overview()
        row = next(
            b for b in data["businesses"] if b["id"] == business["id"]
        )
        self.assertEqual(row["whatsapp_phone"], "600111222")
        self.assertEqual(row["cobrado"], 100)
        self.assertEqual(row["last_activity"], date.today().isoformat())
        self.assertEqual(row["days_inactive"], 0)
        self.assertEqual(row["ai"]["calls"], 1)
        self.assertEqual(row["ai"]["input"], 900)
        self.assertEqual(row["ai"]["extractions"], 1)
        self.assertEqual(data["ai_usage"]["total"]["output"], 120)
        self.assertIn("alerts", data)
        self.assertIn("en_riesgo", data)

    def test_overview_marketing_funnel_and_plan_catalog(self):
        from noesis.adapters import billing

        self.assertEqual(
            billing.PLAN_PRICES, {"autonomo": 29, "pro": 39, "premium": 79}
        )
        business, _ = self.make_business("Admin Embudo")
        db.record_product_event(
            business["id"], "checkout_started", "plan=premium"
        )
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE businesses SET subscription_status='active', "
                "plan='premium' WHERE id=?",
                (business["id"],),
            )
        data = db.admin_overview()
        self.assertIn("marketing", data["dept_reports"])
        charts = data["charts"]
        self.assertEqual(len(charts["funnel"]), len(charts["funnel_labels"]))
        labels = charts["funnel_labels"]
        self.assertEqual(charts["funnel"][labels.index("Checkout")], 1)
        self.assertEqual(charts["funnel"][labels.index("De pago")], 1)
        self.assertEqual(data["mrr"], 79)

    def test_alerts_flag_failed_whatsapp_and_broken_backup(self):
        business, _ = self.make_business("Admin Alarmas")
        # Sin nada roto: como mucho avisa de que no hay copia todavía.
        baseline = db.admin_alerts()
        self.assertTrue(all(a["area"] == "Backups" for a in baseline))
        # Un mensaje agotado dispara alarma roja de WhatsApp.
        message = whatsapp.queue_text(
            "34600111222", "hola", business_id=business["id"]
        )
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE whatsapp_outbox SET status='failed' WHERE id=?",
                (message["id"],),
            )
        # Suscripción impagada dispara alarma de cobro.
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE businesses SET subscription_status='past_due' "
                "WHERE id=?",
                (business["id"],),
            )
        areas = {(a["area"], a["level"]) for a in db.admin_alerts()}
        self.assertIn(("WhatsApp", "rojo"), areas)
        self.assertIn(("Cobro", "ambar"), areas)

    def test_admin_flags_verifactu_due_and_exhausted_queue(self):
        business, client = self.make_business("Admin Verifactu")
        with patch.object(config, "VERIFACTU_PRODUCER_NIF", "B87654321"):
            db.update_verifactu_mode(business["id"], True)
            first = db.add_invoice(
                client["id"], "Registro vencido", 100,
                business_id=business["id"],
            )
            first = db.issue_invoice(first["id"], business["id"])
            second = db.add_invoice(
                client["id"], "Registro agotado", 120,
                business_id=business["id"],
            )
            second = db.issue_invoice(second["id"], business["id"])
        now = datetime(2026, 7, 13, 12, 0, 0).isoformat(timespec="seconds")
        old = datetime(2026, 7, 11, 12, 0, 0).isoformat(timespec="seconds")
        due = db.get_verifactu_outbox(first["id"], business["id"])
        exhausted = db.get_verifactu_outbox(second["id"], business["id"])
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE verifactu_outbox SET next_attempt_at=?, attempts=1 "
                "WHERE id=?",
                (old, due["id"]),
            )
            conn.execute(
                "UPDATE verifactu_outbox SET next_attempt_at=?, "
                "attempts=max_attempts WHERE id=?",
                (old, exhausted["id"]),
            )

        health = db.verifactu_queue_health(now=now)

        self.assertEqual(health["pendiente"], 2)
        self.assertEqual(health["vencidas"], 1)
        self.assertEqual(health["agotado"], 1)
        self.assertEqual(health["oldest_pending_days"], 2)
        affected = health["affected_businesses"][0]
        self.assertEqual(affected["name"], "Admin Verifactu")
        self.assertEqual(affected["vencidas"], 1)
        self.assertEqual(affected["agotadas"], 1)
        overview = db.admin_overview()
        self.assertEqual(overview["verifactu_queue"]["vencidas"], 1)
        areas = {(a["area"], a["level"]) for a in overview["alerts"]}
        self.assertIn(("Veri*Factu", "rojo"), areas)

    def test_agent_records_token_usage(self):
        from noesis import agent as agent_module

        business, _ = self.make_business("Admin Tokens")
        response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="hola")],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=321, output_tokens=45),
        )
        create = MagicMock(return_value=response)
        fake_client = SimpleNamespace(
            messages=SimpleNamespace(create=create)
        )
        with (
            patch.object(config, "ANTHROPIC_API_KEY", "clave-test"),
            patch.object(
                agent_module.anthropic, "Anthropic", return_value=fake_client
            ),
        ):
            noesis_agent = agent_module.NoesisAgent(
                business["id"], model=config.FALLBACK_MODEL
            )
            self.assertEqual(noesis_agent.send("hola"), "hola")
        usage = db.ai_usage_summary()
        entry = usage["per_business"][business["id"]]
        self.assertEqual(entry["calls"], 1)
        self.assertEqual(entry["input"], 321)
        self.assertEqual(entry["output"], 45)
        self.assertEqual(entry["providers"], {"anthropic": 1})
        self.assertAlmostEqual(entry["estimated_cost_usd"], 0.000546)

    def test_local_agent_uses_tools_without_external_credits(self):
        from noesis import agent as agent_module
        from noesis.adapters import ai as ai_adapter

        business, _ = self.make_business("IA Privada")
        first = {
            "choices": [{"message": {
                "content": "",
                "tool_calls": [{
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "listar_clientes", "arguments": "{}"},
                }],
            }}],
            "usage": {"prompt_tokens": 40, "completion_tokens": 10},
        }
        second = {
            "choices": [{"message": {
                "content": "Tienes un cliente y ya lo tengo localizado."
            }}],
            "usage": {"prompt_tokens": 60, "completion_tokens": 12},
        }
        with (
            patch.object(config, "LOCAL_AI_BASE_URL", "http://127.0.0.1:11434"),
            patch.object(config, "LOCAL_AI_MODEL", "modelo-local"),
            patch.object(ai_adapter, "local_chat", side_effect=[first, second]) as call,
        ):
            local_agent = agent_module.LocalNoesisAgent(business["id"])
            reply = local_agent.send("¿Qué clientes tengo?")

        self.assertIn("un cliente", reply)
        self.assertEqual(call.call_count, 2)
        second_messages = call.call_args_list[1].kwargs["messages"]
        self.assertTrue(any(
            item.get("role") == "tool" for item in second_messages
        ))
        self.assertEqual(db.ai_credit_status(business["id"])["used"], 0)
        usage = db.ai_usage_summary()["per_business"][business["id"]]
        self.assertEqual(usage["calls"], 2)
        self.assertEqual(usage["input"], 100)

    def test_local_ai_adapter_uses_openai_compatible_contract(self):
        from noesis.adapters import ai as ai_adapter

        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Todo en orden."}}]
        }).encode("utf-8")
        with (
            patch.object(config, "LOCAL_AI_BASE_URL", "http://ia-privada:11434"),
            patch.object(config, "LOCAL_AI_MODEL", "modelo-local"),
            patch.object(config, "LOCAL_AI_API_KEY", "clave-interna"),
            patch.object(
                ai_adapter.urllib.request, "urlopen", return_value=response
            ) as urlopen,
        ):
            result = ai_adapter.local_chat(
                system="Eres Noesis.",
                messages=[{"role": "user", "content": "Ayúdame."}],
                tools=[{
                    "name": "listar_clientes",
                    "description": "Lista clientes.",
                    "input_schema": {"type": "object", "properties": {}},
                }],
            )

        self.assertEqual(
            result["choices"][0]["message"]["content"], "Todo en orden."
        )
        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "http://ia-privada:11434/v1/chat/completions",
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer clave-interna")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "modelo-local")
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(
            payload["tools"][0]["function"]["name"], "listar_clientes"
        )

    def test_compatible_ai_adapter_uses_configured_endpoint_and_price(self):
        from noesis import agent as agent_module
        from noesis.adapters import ai as ai_adapter

        business, _ = self.make_business("IA Compatible")
        response = {
            "choices": [{"message": {"content": "Todo controlado."}}],
            "usage": {"prompt_tokens": 8_000, "completion_tokens": 1_200},
        }
        with (
            patch.object(config, "COMPAT_AI_BASE_URL", "https://api.example/v1"),
            patch.object(config, "COMPAT_AI_MODEL", "modelo-abierto"),
            patch.object(config, "COMPAT_AI_API_KEY", "clave-compatible"),
            patch.object(config, "COMPAT_AI_PROVIDER", "proveedor-test"),
            patch.object(config, "COMPAT_AI_LEGAL_NAME", "Proveedor Test, SL"),
            patch.object(config, "COMPAT_AI_REGION", "UE"),
            patch.object(config, "COMPAT_AI_INPUT_USD_PER_MTOK", 0.29),
            patch.object(config, "COMPAT_AI_OUTPUT_USD_PER_MTOK", 0.59),
            patch.object(ai_adapter, "external_chat", return_value=response),
        ):
            compatible = agent_module.CompatibleNoesisAgent(business["id"])
            reply = compatible.send("¿Cómo va mi negocio?")

        self.assertEqual(reply, "Todo controlado.")
        usage = db.ai_usage_summary()["per_business"][business["id"]]
        self.assertEqual(usage["providers"], {"proveedor-test": 1})
        self.assertAlmostEqual(usage["estimated_cost_usd"], 0.003028)

    def test_chat_uses_one_external_credit_per_advanced_message(self):
        from noesis import agent as agent_module
        from noesis.adapters import billing

        business, _ = self.make_business("IA con límite")
        db.update_integration_setting(business["id"], "ai_external", "enabled")
        fake_agent = MagicMock()
        fake_agent.send.return_value = "Respuesta avanzada."
        chat._agents.pop(business["id"], None)
        chat._local_agents.pop(business["id"], None)

        with (
            patch.object(config, "LOCAL_AI_BASE_URL", ""),
            patch.object(config, "LOCAL_AI_MODEL", ""),
            patch.object(config, "ANTHROPIC_API_KEY", "clave-test"),
            patch.object(nlu, "parse", return_value=None),
            patch.object(agent_module, "NoesisAgent", return_value=fake_agent),
            patch.dict(billing.PLANS["autonomo"], {"credits": 1}),
        ):
            first = chat._handle(business["id"], "Consulta compleja singular")
            second = chat._handle(business["id"], "Otra consulta compleja singular")

        self.assertEqual(first["source"], "ia")
        self.assertEqual(first["reply"], "Respuesta avanzada.")
        self.assertEqual(second["source"], "local")
        self.assertIn("consultas avanzadas", second["reply"])
        fake_agent.send.assert_called_once()
        self.assertEqual(db.ai_credit_status(business["id"])["used"], 1)

    def test_chat_prefers_compatible_provider_and_falls_back_without_double_credit(self):
        from noesis import agent as agent_module

        business, _ = self.make_business("IA doble respaldo")
        db.update_integration_setting(business["id"], "ai_external", "enabled")
        compatible = MagicMock()
        compatible.send.side_effect = RuntimeError("caída compatible")
        anthropic_agent = MagicMock()
        anthropic_agent.send.return_value = "Respuesta de respaldo."
        chat._agents.pop(business["id"], None)
        chat._local_agents.pop(business["id"], None)
        chat._compatible_agents.pop(business["id"], None)

        with (
            patch.object(config, "LOCAL_AI_BASE_URL", ""),
            patch.object(config, "LOCAL_AI_MODEL", ""),
            patch.object(config, "COMPAT_AI_BASE_URL", "https://api.example/v1"),
            patch.object(config, "COMPAT_AI_MODEL", "modelo-abierto"),
            patch.object(config, "COMPAT_AI_API_KEY", "clave-compatible"),
            patch.object(config, "COMPAT_AI_PROVIDER", "proveedor-test"),
            patch.object(config, "COMPAT_AI_LEGAL_NAME", "Proveedor Test, SL"),
            patch.object(config, "COMPAT_AI_REGION", "UE"),
            patch.object(config, "ANTHROPIC_API_KEY", "clave-test"),
            patch.object(nlu, "parse", return_value=None),
            patch.object(
                agent_module, "CompatibleNoesisAgent", return_value=compatible
            ),
            patch.object(
                agent_module, "NoesisAgent", return_value=anthropic_agent
            ),
        ):
            result = chat._handle(
                business["id"], "Consulta compleja con respaldo"
            )

        self.assertEqual(result["source"], "ia")
        self.assertEqual(result["reply"], "Respuesta de respaldo.")
        compatible.send.assert_called_once()
        anthropic_agent.send.assert_called_once()
        self.assertEqual(db.ai_credit_status(business["id"])["used"], 1)

    def test_chat_does_not_fallback_after_possible_partial_write(self):
        from noesis import agent as agent_module

        business, _ = self.make_business("IA sin duplicados")
        db.update_integration_setting(business["id"], "ai_external", "enabled")
        compatible = MagicMock()
        compatible.send.side_effect = agent_module.PartialAgentExecutionError(
            "posible escritura"
        )
        anthropic_agent = MagicMock()
        chat._agents.pop(business["id"], None)
        chat._local_agents.pop(business["id"], None)
        chat._compatible_agents.pop(business["id"], None)

        with (
            patch.object(config, "LOCAL_AI_BASE_URL", ""),
            patch.object(config, "LOCAL_AI_MODEL", ""),
            patch.object(config, "COMPAT_AI_BASE_URL", "https://api.example/v1"),
            patch.object(config, "COMPAT_AI_MODEL", "modelo-abierto"),
            patch.object(config, "COMPAT_AI_API_KEY", "clave-compatible"),
            patch.object(config, "COMPAT_AI_PROVIDER", "proveedor-test"),
            patch.object(config, "COMPAT_AI_LEGAL_NAME", "Proveedor Test, SL"),
            patch.object(config, "COMPAT_AI_REGION", "UE"),
            patch.object(config, "ANTHROPIC_API_KEY", "clave-test"),
            patch.object(nlu, "parse", return_value=None),
            patch.object(
                agent_module, "CompatibleNoesisAgent", return_value=compatible
            ),
            patch.object(
                agent_module, "NoesisAgent", return_value=anthropic_agent
            ),
        ):
            result = chat._handle(
                business["id"], "Crea un proyecto y dime cómo queda"
            )

        self.assertEqual(result["source"], "local")
        self.assertIn("no la voy a repetir", result["reply"])
        anthropic_agent.send.assert_not_called()
        self.assertEqual(db.ai_credit_status(business["id"])["used"], 1)

    def test_external_ai_credit_limit_is_atomic_and_isolated(self):
        from noesis.adapters import billing

        business, _ = self.make_business("Créditos A")
        other, _ = self.make_business("Créditos B")
        with patch.dict(billing.PLANS["autonomo"], {"credits": 2}):
            with ThreadPoolExecutor(max_workers=6) as pool:
                claims = list(pool.map(
                    lambda _index: db.claim_ai_credit(business["id"]),
                    range(6),
                ))
            other_first = db.claim_ai_credit(other["id"])

            self.assertEqual(sum(item["allowed"] for item in claims), 2)
            self.assertTrue(all(
                item["remaining"] == 0
                for item in claims if not item["allowed"]
            ))
            self.assertTrue(other_first["allowed"])
            self.assertEqual(db.ai_credit_status(business["id"])["used"], 2)
            self.assertEqual(db.ai_credit_status(other["id"])["used"], 1)


if __name__ == "__main__":
    unittest.main()
