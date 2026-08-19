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

from noesis import banking, config, db, migrations, nlu, verifactu, verifactu_client
from noesis.adapters import extraction
from noesis.web import auth, chat, reports, scheduler, whatsapp
from tests.fixtures import TINY_JPEG, TINY_PNG

TEST_PASSWORD = "password-segura-123"  # pragma: allowlist secret
ISSUER_NIF = "A12345678"  # pragma: allowlist secret
CLIENT_NIF = "B12345678"  # pragma: allowlist secret
PRODUCER_NIF = "B87654321"  # pragma: allowlist secret
ALTERNATIVE_NIF = "A99999999"  # pragma: allowlist secret
SUPPLIER_NIF = "B22222222"  # pragma: allowlist secret
TEST_IBAN = "ES9121000418450200051332"  # pragma: allowlist secret


class HistoricalInvoiceMigrationTestCase(unittest.TestCase):
    def test_schema_33_backfills_issued_invoice_and_restores_immutability(self):
        tempdir = tempfile.TemporaryDirectory()
        old_path = config.DB_PATH
        old_url = config.DATABASE_URL
        config.DATABASE_URL = ""
        config.DB_PATH = Path(tempdir.name) / "migration-32.db"
        try:
            migrations.upgrade(32)
            now = datetime.now().isoformat(timespec="seconds")
            with db.get_conn() as conn:
                business = conn.execute(
                    "INSERT INTO businesses "
                    "(name, owner_email, sector, created_at) VALUES (?, ?, ?, ?) "
                    "RETURNING id",
                    ("Histórico", "historico@example.com", "Servicios", now),
                ).fetchone()
                client = conn.execute(
                    "INSERT INTO clients "
                    "(business_id, name, nif, address, created_at) "
                    "VALUES (?, ?, ?, ?, ?) RETURNING id",
                    (
                        business["id"], "Cliente", CLIENT_NIF,
                        "Calle Cliente 1", now,
                    ),
                ).fetchone()
                invoice = conn.execute(
                    "INSERT INTO invoices "
                    "(business_id, number, client_id, concept, base, vat_rate, "
                    "vat_amount, irpf_rate, irpf_amount, total, status, issued_at, "
                    "issuer_name, issuer_nif, issuer_address, recipient_name, "
                    "recipient_nif, recipient_address, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "RETURNING id",
                    (
                        business["id"], "2026/0001", client["id"], "Servicio",
                        100, 21, 21, 0, 0, 121, "emitida", now, "Histórico",
                        ISSUER_NIF, "Calle Negocio 1", "Cliente", CLIENT_NIF,
                        "Calle Cliente 1", now,
                    ),
                ).fetchone()

            self.assertEqual(migrations.upgrade(), migrations.LATEST_VERSION)
            with db.get_conn() as conn:
                migrated = conn.execute(
                    "SELECT series_id FROM invoices WHERE id=?",
                    (invoice["id"],),
                ).fetchone()
                line_count = conn.execute(
                    "SELECT COUNT(*) AS total FROM invoice_lines WHERE invoice_id=?",
                    (invoice["id"],),
                ).fetchone()["total"]
            self.assertIsNotNone(migrated["series_id"])
            self.assertEqual(line_count, 1)
            with self.assertRaises(db.IntegrityError):
                with db.get_conn() as conn:
                    conn.execute(
                        "UPDATE invoices SET concept='Alteración' WHERE id=?",
                        (invoice["id"],),
                    )
        finally:
            config.DB_PATH = old_path
            config.DATABASE_URL = old_url
            tempdir.cleanup()

    def test_schema_46_adds_stripe_event_order_without_changing_access(self):
        tempdir = tempfile.TemporaryDirectory()
        old_path = config.DB_PATH
        old_url = config.DATABASE_URL
        config.DATABASE_URL = ""
        config.DB_PATH = Path(tempdir.name) / "migration-45.db"
        try:
            migrations.upgrade(45)
            business = db.create_business("Suscripcion historica", "old@example.com")
            db.set_subscription(business["id"], "active", plan="pro")

            self.assertEqual(migrations.upgrade(46), 46)
            migrated = db.get_business(business["id"])
            self.assertEqual(migrated["subscription_status"], "active")
            self.assertEqual(migrated["plan"], "pro")
            self.assertEqual(migrated["stripe_event_created_at"], 0)
            self.assertEqual(migrated["stripe_event_priority"], 0)
            self.assertIsNone(migrated["stripe_event_id"])
        finally:
            config.DB_PATH = old_path
            config.DATABASE_URL = old_url
            tempdir.cleanup()


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
            business["id"], nif=ISSUER_NIF, address="Calle Principal 1"  # pragma: allowlist secret
        )
        client = db.add_client(
            "Cliente Fiscal", nif=CLIENT_NIF, address="Calle Cliente 2",  # pragma: allowlist secret
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
        self.assertEqual(first["recipient_nif"], CLIENT_NIF)  # pragma: allowlist secret
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

    def test_demo_historical_issue_is_atomic_and_remains_immutable(self):
        business, client = self.make_business("Factura Demo Histórica")
        draft = db.add_invoice(
            client["id"], "Servicio histórico", 100,
            business_id=business["id"],
        )

        issued = db.issue_invoice(
            draft["id"], business["id"], payment_term_days=10,
            _issued_at_override="2026-01-10",
        )

        self.assertEqual(issued["issued_at"], "2026-01-10T12:00:00")
        self.assertEqual(issued["due_date"], "2026-01-20")
        with self.assertRaises(db.IntegrityError):
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE invoices SET due_date=? WHERE id=? AND business_id=?",
                    ("2026-02-01", issued["id"], business["id"]),
                )

    def test_database_freezes_issued_invoice_and_number_is_unique_per_business(self):
        business, client = self.make_business("Factura Inmutable")
        issued = db.issue_invoice(
            db.add_invoice(
                client["id"], "Servicio cerrado", 100,
                business_id=business["id"],
            )["id"],
            business["id"],
        )
        with self.assertRaises(db.IntegrityError):
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE invoices SET total=1 WHERE id=? AND business_id=?",
                    (issued["id"], business["id"]),
                )
        with self.assertRaises(db.IntegrityError):
            with db.get_conn() as conn:
                conn.execute(
                    "DELETE FROM invoices WHERE id=? AND business_id=?",
                    (issued["id"], business["id"]),
                )

        other = db.add_invoice(
            client["id"], "Otro servicio", 50, business_id=business["id"]
        )
        with self.assertRaises(db.IntegrityError):
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE invoices SET number=?, status='enviada' "
                    "WHERE id=? AND business_id=?",
                    (issued["number"], other["id"], business["id"]),
                )

        db.mark_reminder_sent(issued["id"], business["id"])
        self.assertEqual(
            db.get_invoice(issued["id"], business["id"])["reminders_sent"], 1
        )

    def test_invoice_sequence_is_correlative_and_isolated_per_business(self):
        business_a, client_a = self.make_business("Numeracion A")
        business_b, client_b = self.make_business("Numeracion B")
        first_a = db.issue_invoice(
            db.add_invoice(
                client_a["id"], "Primera", 10, business_id=business_a["id"]
            )["id"],
            business_a["id"],
        )
        second_a = db.issue_invoice(
            db.add_invoice(
                client_a["id"], "Segunda", 20, business_id=business_a["id"]
            )["id"],
            business_a["id"],
        )
        first_b = db.issue_invoice(
            db.add_invoice(
                client_b["id"], "Primera", 30, business_id=business_b["id"]
            )["id"],
            business_b["id"],
        )

        year = date.today().year
        self.assertEqual(first_a["number"], f"{year}/0001")
        self.assertEqual(second_a["number"], f"{year}/0002")
        self.assertEqual(first_b["number"], f"{year}/0001")

    def test_professional_invoice_lines_draft_edit_and_series_are_consistent(self):
        business, client = self.make_business("Factura Profesional")
        draft = db.add_invoice(
            client["id"],
            "Material y mano de obra",
            None,
            business_id=business["id"],
            lines=[
                {
                    "description": "Instalación",
                    "quantity": 2,
                    "unit_price": 50,
                    "discount_rate": 10,
                    "vat_rate": 21,
                },
                {
                    "description": "Material reducido",
                    "quantity": 1,
                    "unit_price": 20,
                    "vat_rate": 10,
                },
            ],
            irpf_rate=7,
            operation_date=date.today().isoformat(),
            payment_method="Transferencia a 15 días",
            notes="Trabajo terminado y revisado.",
        )
        self.assertEqual(draft["base"], 110)
        self.assertEqual(draft["vat_amount"], 20.9)
        self.assertEqual(draft["irpf_amount"], 7.7)
        self.assertEqual(draft["total"], 123.2)
        self.assertEqual(draft["vat_rate"], -1)
        self.assertEqual(len(draft["lines"]), 2)

        edited = db.update_invoice_draft(
            draft["id"],
            business["id"],
            client_id=client["id"],
            lines=[{
                "description": "Servicio final",
                "quantity": 3,
                "unit_price": 40,
                "vat_rate": 21,
            }],
            irpf_rate=0,
            notes="Versión aprobada por el cliente.",
        )
        self.assertEqual(edited["base"], 120)
        self.assertEqual(len(edited["lines"]), 1)
        issued = db.issue_invoice(edited["id"], business["id"])
        self.assertRegex(issued["number"], rf"^{date.today().year}/0001$")

        with self.assertRaises(ValueError):
            db.update_invoice_draft(
                issued["id"], business["id"], client_id=client["id"],
                lines=[{"description": "Alterada", "quantity": 1,
                        "unit_price": 1, "vat_rate": 21}],
            )
        with self.assertRaises(db.IntegrityError):
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE invoice_lines SET unit_price=1 "
                    "WHERE invoice_id=? AND business_id=?",
                    (issued["id"], business["id"]),
                )

    def test_simplified_and_rectifying_invoices_use_separate_legal_series(self):
        business, client = self.make_business("Series Separadas")
        anonymous = db.add_client("Cliente mostrador", business_id=business["id"])
        simplified = db.issue_invoice(
            db.add_invoice(
                anonymous["id"], "Reparación menor", 100,
                invoice_type="F2", business_id=business["id"],
            )["id"],
            business["id"],
        )
        self.assertEqual(simplified["number"], f"T{date.today().year}/0001")
        self.assertFalse(simplified.get("recipient_nif"))

        too_large = db.add_invoice(
            anonymous["id"], "Servicio superior al límite", 400,
            invoice_type="F2", business_id=business["id"],
        )
        with self.assertRaisesRegex(ValueError, "400"):
            db.issue_invoice(too_large["id"], business["id"])

        original = db.issue_invoice(
            db.add_invoice(
                client["id"], "Trabajo original", 200,
                business_id=business["id"],
            )["id"],
            business["id"],
        )
        rectifying = db.create_rectifying_invoice(
            original["id"], business["id"], concept="Corrección",
            base=-20, invoice_type="R1", reason="Error material",
        )
        rectifying = db.issue_invoice(rectifying["id"], business["id"])
        self.assertEqual(rectifying["number"], f"R{date.today().year}/0001")

    def test_rectifying_draft_is_unique_editable_and_cause_matches_original(self):
        business, client = self.make_business("Rectificativa Segura")
        original = db.issue_invoice(
            db.add_invoice(
                client["id"], "Instalación original", 200,
                business_id=business["id"],
            )["id"],
            business["id"],
        )
        draft = db.create_rectifying_invoice(
            original["id"], business["id"], concept="Corrección inicial",
            base=-20, invoice_type="R1", reason="Importe duplicado",
        )
        with self.assertRaisesRegex(ValueError, "Ya existe"):
            db.create_rectifying_invoice(
                original["id"], business["id"], concept="Otra corrección",
                base=-10, invoice_type="R1", reason="Segundo borrador",
            )
        with self.assertRaisesRegex(ValueError, "sustitución"):
            db.update_rectifying_invoice_draft(
                draft["id"], business["id"], concept="Corrección",
                base=-25, invoice_type="R1", rectification_type="S",
                reason="Cambio de modalidad",
            )
        with self.assertRaisesRegex(ValueError, "R5"):
            db.update_rectifying_invoice_draft(
                draft["id"], business["id"], concept="Corrección",
                base=-25, invoice_type="R5", reason="Causa incompatible",
            )
        edited = db.update_rectifying_invoice_draft(
            draft["id"], business["id"], concept="Corrección final",
            base=-25, vat_rate=21, invoice_type="R1",
            reason="Importe duplicado confirmado",
        )
        self.assertEqual(edited["base"], -25)
        self.assertEqual(edited["rectification_reason"], "Importe duplicado confirmado")
        listed = {item["id"]: item for item in db.list_invoices(business["id"])}
        self.assertEqual(listed[draft["id"]]["rectified_number"], original["number"])
        self.assertEqual(
            listed[original["id"]]["pending_rectification_id"], draft["id"]
        )

        simplified = db.issue_invoice(
            db.add_invoice(
                client["id"], "Servicio menor", 100, invoice_type="F2",
                business_id=business["id"],
            )["id"],
            business["id"],
        )
        with self.assertRaisesRegex(ValueError, "R5"):
            db.create_rectifying_invoice(
                simplified["id"], business["id"], concept="Corrección",
                base=-10, invoice_type="R1", reason="Error simplificado",
            )
        simplified_draft = db.create_rectifying_invoice(
            simplified["id"], business["id"], concept="Corrección",
            base=-10, invoice_type="R5", reason="Error simplificado",
        )
        self.assertEqual(simplified_draft["invoice_type"], "R5")

    def test_recurring_invoices_prepare_once_and_require_opt_in_to_issue(self):
        business, client = self.make_business("Facturas Programadas")
        db.set_trial(business["id"], days=14)
        today = date.today()
        schedule = db.add_recurring_invoice(
            business["id"], client["id"], name="Mantenimiento mensual",
            cadence="monthly", next_run_on=today.isoformat(),
            lines=[{
                "description": "Mantenimiento",
                "quantity": 1,
                "unit_price": 80,
                "vat_rate": 21,
            }],
        )
        generated = db.process_due_recurring_invoices(today=today)
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0]["status"], "borrador")
        self.assertIsNone(generated[0]["number"])
        self.assertEqual(db.process_due_recurring_invoices(today=today), [])
        refreshed = db.get_recurring_invoice(schedule["id"], business["id"])
        self.assertGreater(refreshed["next_run_on"], today.isoformat())
        with db.get_conn() as conn:
            runs = conn.execute(
                "SELECT * FROM recurring_invoice_runs WHERE business_id=?",
                (business["id"],),
            ).fetchall()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["status"], "completed")

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

    def test_month_billing_separates_cash_flow_from_invoice_cohort(self):
        business, client = self.make_business("Cohortes de cobro")
        this_month = date.today().strftime("%Y-%m")
        previous_month = (date.today().replace(day=1) - timedelta(days=1)).strftime(
            "%Y-%m"
        )
        old_invoice = db.issue_invoice(
            db.add_invoice(
                client["id"], "Trabajo anterior", 100,
                business_id=business["id"],
            )["id"],
            business["id"],
            _issued_at_override=f"{previous_month}-15T10:00:00",
        )
        current_invoice = db.issue_invoice(
            db.add_invoice(
                client["id"], "Trabajo actual", 100,
                business_id=business["id"],
            )["id"],
            business["id"],
            _issued_at_override=f"{this_month}-02T10:00:00",
        )
        db.add_invoice_payment(
            old_invoice["id"], 121, business_id=business["id"],
            paid_at=f"{this_month}-03T10:00:00",
        )
        db.add_invoice_payment(
            current_invoice["id"], 40, business_id=business["id"],
            paid_at=f"{this_month}-04T10:00:00",
        )

        month = db.month_billing(this_month, business_id=business["id"])

        self.assertEqual(month["invoiced"], 121)
        self.assertEqual(month["collected"], 161)
        self.assertEqual(month["invoiced_collected"], 40)
        self.assertEqual(month["pending"], 81)

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
                "apply_stripe_subscription_event",
                side_effect=[RuntimeError("fallo transitorio"), {"applied": True}],
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

    def test_stripe_checkout_never_activates_without_paid_evidence(self):
        from noesis.web.routers import webhooks

        business, _ = self.make_business("Stripe pendiente")
        db.set_subscription(business["id"], "canceled", plan="autonomo")
        webhooks._apply_stripe_event({
            "id": "evt_checkout_pending",
            "created": 100,
            "type": "checkout.session.completed",
            "data": {"object": {
                "metadata": {
                    "business_id": str(business["id"]),
                    "plan": "autonomo",
                },
                "customer": "cus_pending",
                "subscription": "sub_pending",
                "payment_status": "paid",
            }},
        })

        updated = db.get_business(business["id"])
        self.assertEqual(updated["subscription_status"], "pending")
        self.assertEqual(updated["stripe_customer_id"], "cus_pending")
        self.assertEqual(updated["stripe_subscription_id"], "sub_pending")
        self.assertFalse(db.subscription_allows_access(updated))

    def test_stripe_checkout_never_grants_an_upgrade_before_confirmation(self):
        from noesis.adapters import billing
        from noesis.web.routers import webhooks

        business, _ = self.make_business("Stripe upgrade pendiente")
        db.set_subscription(business["id"], "active", plan="autonomo")
        webhooks._apply_stripe_event({
            "id": "evt_checkout_upgrade",
            "created": 120,
            "type": "checkout.session.completed",
            "data": {"object": {
                "metadata": {
                    "business_id": str(business["id"]),
                    "plan": "premium",
                },
                "customer": "cus_upgrade",
                "subscription": "sub_upgrade",
                "payment_status": "paid",
            }},
        })

        updated = db.get_business(business["id"])
        self.assertEqual(updated["subscription_status"], "active")
        self.assertEqual(updated["plan"], "autonomo")
        self.assertFalse(
            billing.has_entitlement(updated, billing.ENTITLEMENT_PROJECTS)
        )

    def test_stripe_subscription_price_governs_portal_plan_changes(self):
        from noesis.adapters import billing
        from noesis.web.routers import webhooks

        business, _ = self.make_business("Stripe cambio portal")
        db.set_subscription(business["id"], "active", plan="premium")
        with (
            patch.object(billing.config, "STRIPE_PRICE_AUTONOMO", "price_auto"),
            patch.object(billing.config, "STRIPE_PRICE_PREMIUM", "price_premium"),
        ):
            webhooks._apply_stripe_event({
                "id": "evt_portal_downgrade",
                "created": 140,
                "type": "customer.subscription.updated",
                "data": {"object": {
                    "id": "sub_portal",
                    "customer": "cus_portal",
                    "status": "active",
                    # La metadata de Stripe puede conservar el plan original;
                    # el precio vigente es la evidencia comercial autoritativa.
                    "metadata": {
                        "business_id": str(business["id"]),
                        "plan": "premium",
                    },
                    "items": {"data": [{"price": {"id": "price_auto"}}]},
                }},
            })

        updated = db.get_business(business["id"])
        self.assertEqual(updated["plan"], "autonomo")
        self.assertFalse(
            billing.has_entitlement(updated, billing.ENTITLEMENT_PROJECTS)
        )

    def test_stripe_unknown_incomplete_and_paused_never_become_trial(self):
        from noesis.web.routers import webhooks

        for offset, stripe_status in enumerate(("incomplete", "paused", "new_state")):
            with self.subTest(status=stripe_status):
                business, _ = self.make_business(f"Stripe {stripe_status}")
                db.set_subscription(business["id"], "canceled", plan="autonomo")
                webhooks._apply_stripe_event({
                    "id": f"evt_status_{offset}",
                    "created": 200 + offset,
                    "type": "customer.subscription.updated",
                    "data": {"object": {
                        "id": f"sub_status_{offset}",
                        "customer": f"cus_status_{offset}",
                        "status": stripe_status,
                        "metadata": {
                            "business_id": str(business["id"]),
                            "plan": "autonomo",
                        },
                    }},
                })
                expected = stripe_status if stripe_status != "new_state" else "unknown"
                updated = db.get_business(business["id"])
                self.assertEqual(updated["subscription_status"], expected)
                self.assertFalse(db.subscription_allows_access(updated))

    def test_stripe_out_of_order_events_cannot_undo_a_newer_payment(self):
        from noesis.web.routers import webhooks

        business, _ = self.make_business("Stripe desordenado")
        db.set_subscription(business["id"], "canceled", plan="pro")
        subscription = {
            "subscription": "sub_ordered",
            "customer": "cus_ordered",
            "metadata": {"business_id": str(business["id"]), "plan": "pro"},
        }
        webhooks._apply_stripe_event({
            "id": "evt_paid_new",
            "created": 500,
            "type": "invoice.paid",
            "data": {"object": subscription},
        })
        webhooks._apply_stripe_event({
            "id": "evt_failed_old",
            "created": 400,
            "type": "invoice.payment_failed",
            "data": {"object": subscription},
        })
        webhooks._apply_stripe_event({
            "id": "evt_checkout_old",
            "created": 300,
            "type": "checkout.session.completed",
            "data": {"object": {
                **subscription, "client_reference_id": str(business["id"])
            }},
        })

        updated = db.get_business(business["id"])
        self.assertEqual(updated["subscription_status"], "active")
        self.assertEqual(updated["stripe_event_id"], "evt_paid_new")

    def test_stripe_checkout_cannot_downgrade_concurrent_active_subscription(self):
        business, _ = self.make_business("Stripe concurrente")
        db.apply_stripe_subscription_event(
            business["id"], status="active", event_created_at=100,
            event_priority=40, event_id="evt_subscription_active",
            plan="autonomo", customer_id="cus_concurrent",
            subscription_id="sub_concurrent", allow_subscription_change=True,
        )

        result = db.apply_stripe_subscription_event(
            business["id"], status="pending", event_created_at=101,
            event_priority=10, event_id="evt_checkout_later",
            customer_id="cus_concurrent", subscription_id="sub_concurrent",
            allow_subscription_change=True,
        )

        self.assertTrue(result["applied"])
        self.assertEqual(result["business"]["subscription_status"], "active")
        self.assertEqual(db.get_business(business["id"])["plan"], "autonomo")

    def test_stripe_one_time_invoice_and_old_subscription_are_ignored(self):
        from noesis.web.routers import webhooks

        business, _ = self.make_business("Stripe aislado")
        db.apply_stripe_subscription_event(
            business["id"], status="active", event_created_at=100,
            event_priority=60, event_id="evt_current", plan="pro",
            customer_id="cus_isolated", subscription_id="sub_current",
            allow_subscription_change=True,
        )
        webhooks._apply_stripe_event({
            "id": "evt_one_time",
            "created": 200,
            "type": "invoice.payment_failed",
            "data": {"object": {"customer": "cus_isolated"}},
        })
        webhooks._apply_stripe_event({
            "id": "evt_old_subscription",
            "created": 300,
            "type": "invoice.payment_failed",
            "data": {"object": {
                "customer": "cus_isolated", "subscription": "sub_old"
            }},
        })

        updated = db.get_business(business["id"])
        self.assertEqual(updated["subscription_status"], "active")
        self.assertEqual(updated["stripe_event_id"], "evt_current")

    def test_paid_plan_entitlements_are_enforced_in_server_and_brain(self):
        from starlette.testclient import TestClient
        from noesis import tools
        from noesis.web import server

        business, _ = self.make_business("Plan autonomo")
        db.create_user(
            "plan-autonomo@example.com", auth.hash_password(TEST_PASSWORD),
            business["id"],
        )
        db.set_subscription(business["id"], "active", plan="autonomo")

        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                client.post("/login", data={
                    "email": "plan-autonomo@example.com",
                    "password": TEST_PASSWORD,
                })
                basic = client.get(f"/api/{business['id']}/clients")
                projects = client.get(f"/api/{business['id']}/projects")
                workers = client.get(f"/api/{business['id']}/workers")
                analysis = client.get(f"/api/{business['id']}/analysis")
                project_page = client.get(
                    f"/b/{business['id']}/proyectos", follow_redirects=False
                )
                home = client.get(f"/b/{business['id']}/resumen")

        self.assertEqual(basic.status_code, 200)
        for response in (projects, workers, analysis):
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["code"], "plan_upgrade_required")
            self.assertEqual(response.json()["required_plan"], "pro")
        self.assertEqual(project_page.status_code, 303)
        self.assertIn("status=upgrade", project_page.headers["location"])
        self.assertNotIn("> Proyectos</a>", home.text)
        self.assertNotIn("> Equipo</a>", home.text)
        self.assertNotIn(">Análisis</a>", home.text)

        blocked_tool = json.loads(
            tools.run_tool("crear_proyecto", {
                "nombre": "No crear", "presupuesto": 1000,
            }, business["id"])
        )
        self.assertEqual(blocked_tool["code"], "plan_upgrade_required")
        self.assertEqual(db.list_projects(business["id"]), [])

    def test_business_plan_and_trial_keep_the_complete_sold_workflow(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        for suffix, status, plan in (
            ("pro", "active", "pro"),
            ("trial", "trial", "trial"),
        ):
            with self.subTest(account=suffix):
                business, _ = self.make_business(f"Plan {suffix}")
                email = f"plan-{suffix}@example.com"
                db.create_user(email, auth.hash_password(TEST_PASSWORD), business["id"])
                db.set_subscription(business["id"], status, plan=plan)
                with patch.object(server, "start_scheduler", lambda: None):
                    with TestClient(server.app) as client:
                        client.post("/login", data={
                            "email": email, "password": TEST_PASSWORD,
                        })
                        self.assertEqual(
                            client.get(f"/api/{business['id']}/projects").status_code,
                            200,
                        )
                        self.assertEqual(
                            client.get(f"/api/{business['id']}/workers").status_code,
                            200,
                        )
                        self.assertEqual(
                            client.get(f"/api/{business['id']}/analysis").status_code,
                            200,
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
        gestoria = db.create_gestoria_account(
            "baja@gestoria.com", auth.hash_password(TEST_PASSWORD),
            "GestorÃ­a baja",
        )
        invitation = db.create_gestoria_invitation(
            business["id"], gestoria["email"], auth.hash_token("baja-invite"),
            (datetime.now() + timedelta(days=1)).isoformat(timespec="seconds"),
        )
        self.assertIsNotNone(
            db.accept_gestoria_invitation(invitation["id"], gestoria["id"])
        )
        db.claim_scheduled_run(f"gestoria:{business['id']}:2026-06")

        self.assertTrue(db.delete_business_cascade(business["id"]))

        self.assertIsNone(db.get_business(business["id"]))
        self.assertEqual(db.list_gestoria_businesses(gestoria["id"]), [])
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
            config.WHATSAPP_APP_SECRET = "secret"  # pragma: allowlist secret
            config.IS_PRODUCTION = True
            signature = "sha256=" + hmac.new(
                b"secret", payload, hashlib.sha256  # pragma: allowlist secret
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

    def test_whatsapp_outbox_never_sends_for_inactive_subscription(self):
        business, _ = self.make_business("WhatsApp pausado")
        point = datetime(2026, 6, 30, 10, 0, 0)
        message = whatsapp.queue_text(
            "34600111222", "No debe salir", business_id=business["id"], now=point
        )
        db.set_subscription(business["id"], "canceled", plan="tranquilidad")

        with patch.object(whatsapp, "_post_to_meta") as post:
            processed = whatsapp.process_outbox(now=point)

        post.assert_not_called()
        self.assertEqual(processed[0]["status"], "failed")
        blocked = db.get_whatsapp_message(message["id"], business["id"])
        self.assertEqual(blocked["status"], "failed")
        self.assertIn("modo consulta", blocked["last_error"])

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

    def test_whatsapp_inbound_explains_read_only_without_running_the_brain(self):
        business, _ = self.make_business("WhatsApp consulta")
        db.set_whatsapp_status(
            business["id"], "conectado", phone="34600111222"
        )
        db.set_subscription(business["id"], "canceled", plan="tranquilidad")
        payload = {
            "id": "wamid.readonly",
            "from": "34600111222",
            "text": "crea una factura de 100 euros",
        }

        with (
            patch.object(chat, "handle") as handle,
            patch.object(whatsapp, "send", return_value=True) as send,
        ):
            result = whatsapp.handle_inbound(payload)

        handle.assert_not_called()
        self.assertTrue(result["results"][0]["subscription_required"])
        self.assertIn("modo consulta", send.call_args.args[1])
        self.assertIsNone(send.call_args.kwargs["business_id"])

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

    def test_web_chat_issues_the_draft_it_told_you_to_issue(self):
        # El mensaje que confirma el borrador sugiere «emitir factura N». Esa
        # orden solo la entendía WhatsApp, así que en la web el borrador se
        # quedaba sin emitir siguiendo una instrucción del propio producto.
        self.assertEqual(
            nlu.parse("emitir factura 2"), ("enviar_factura", {"factura_id": 2})
        )
        self.assertEqual(
            nlu.parse("emitir y enviar factura 7"),
            ("enviar_factura", {"factura_id": 7}),
        )
        # Crear una factura nueva no puede confundirse con emitir una existente.
        self.assertEqual(
            nlu.parse("factura a Juan por reparación 95 euros")[0], "crear_factura"
        )

        business, _ = self.make_business()
        chat.handle(business["id"], "factura a Juan por reparación 100 euros")
        invoice = db.list_invoices(business["id"])[0]
        db.update_client(
            invoice["client_id"], business_id=business["id"],
            nif="87654321X", address="Calle Mayor 1, Valencia",
        )

        reply = chat.handle(business["id"], f"emitir factura {invoice['id']}")
        issued = db.get_invoice(invoice["id"], business["id"])
        self.assertEqual(issued["status"], "enviada")
        self.assertTrue(issued["number"])
        self.assertIn(issued["number"], reply["reply"])

    def test_issue_order_without_tax_data_explains_itself_without_jargon(self):
        business, _ = self.make_business()
        chat.handle(business["id"], "factura a Juan por reparación 100 euros")
        invoice = db.list_invoices(business["id"])[0]

        reply = chat.handle(business["id"], f"emitir factura {invoice['id']}")["reply"]
        # Se explica qué falta y no se filtra el nombre interno de la herramienta.
        self.assertIn("Antes de emitir completa", reply)
        self.assertNotIn("enviar_factura", reply)
        self.assertEqual(
            db.get_invoice(invoice["id"], business["id"])["status"], "borrador"
        )

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

        sale_tool, sale_args = nlu.parse(
            "ticket de venta a Marta por reparación 121 euros"
        )
        self.assertEqual(sale_tool, "crear_factura")
        self.assertEqual(sale_args["tipo_factura"], "F2")
        self.assertTrue(sale_args["importe_incluye_iva"])
        # Un ticket sin indicar que es una venta conserva el flujo de gasto.
        self.assertEqual(nlu.parse("ticket de 12 euros")[0], "registrar_gasto")
        self.assertEqual(
            nlu.parse("factura el trabajo 42"),
            ("preparar_factura_trabajo", {"trabajo_id": 42}),
        )
        ca_tool, ca_args = nlu.parse(
            "tiquet de venda a Marta per reparació 121 euros"
        )
        self.assertEqual(ca_tool, "crear_factura")
        self.assertEqual(ca_args["cliente"], "Marta")
        self.assertEqual(ca_args["concepto"], "reparació")
        self.assertEqual(
            nlu.parse("factura el treball 42"),
            ("preparar_factura_trabajo", {"trabajo_id": 42}),
        )

    def test_client_reference_reuses_unique_habitual_and_rejects_ambiguity(self):
        business, _ = self.make_business("Clientes habituales")
        habitual = db.add_client("Marta López", business_id=business["id"])
        result = chat.handle(
            business["id"], "factura a Marta por revisión 100 euros"
        )
        self.assertEqual(result["source"], "local")
        invoice = db.list_invoices(business["id"])[0]
        self.assertEqual(invoice["client_id"], habitual["id"])

        db.add_client("Marta García", business_id=business["id"])
        before = len(db.list_clients(business["id"]))
        ambiguous = chat.handle(
            business["id"], "factura a Marta por revisión 80 euros"
        )
        self.assertIn("varios clientes", ambiguous["reply"])
        self.assertEqual(len(db.list_clients(business["id"])), before)

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
            "owner@example.com", auth.hash_password(TEST_PASSWORD),
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
            business["id"], nif=CLIENT_NIF, address="Calle Taller 1"  # pragma: allowlist secret
        )
        client = db.add_client(
            "Hotel Costa", nif=ISSUER_NIF, address="Avenida Mar 4",  # pragma: allowlist secret
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

    def test_private_calendar_feed_is_subscribable_isolated_and_revocable(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, own_client = self.make_business("Agenda privada")
        other, other_client = self.make_business("Agenda ajena")
        scheduled = (date.today() + timedelta(days=2)).isoformat() + "T09:30:00"
        db.add_job(
            own_client["id"], "Revisar caldera", scheduled_for=scheduled,
            business_id=business["id"],
        )
        db.add_job(
            other_client["id"], "Secreto de otro negocio", scheduled_for=scheduled,
            business_id=other["id"],
        )
        db.create_user(
            "agenda@example.com", auth.hash_password(TEST_PASSWORD),
            business["id"],
        )

        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                login = client.post("/login", data={
                    "email": "agenda@example.com",
                    "password": TEST_PASSWORD,  # pragma: allowlist secret
                }, follow_redirects=False)
                self.assertEqual(login.status_code, 303)
                created = client.post(
                    f"/b/{business['id']}/calendar-feed",
                    data={"action": "create"}, follow_redirects=False,
                )
                self.assertEqual(created.status_code, 303)
                token = db.get_business(business["id"])["calendar_token"]
                self.assertGreaterEqual(len(token), 32)

                feed = client.get(f"/cal/{token}.ics")
                self.assertEqual(feed.status_code, 200)
                self.assertTrue(feed.headers["content-type"].startswith("text/calendar"))
                self.assertIn("BEGIN:VCALENDAR", feed.text)
                self.assertIn("Revisar caldera", feed.text)
                self.assertNotIn("Secreto de otro negocio", feed.text)
                agenda = client.get(f"/b/{business['id']}/agenda")
                self.assertIn(f"/cal/{token}.ics", agenda.text)

                rotated = client.post(
                    f"/b/{business['id']}/calendar-feed",
                    data={"action": "rotate"}, follow_redirects=False,
                )
                self.assertEqual(rotated.status_code, 303)
                new_token = db.get_business(business["id"])["calendar_token"]
                self.assertNotEqual(new_token, token)
                self.assertEqual(client.get(f"/cal/{token}.ics").status_code, 404)
                self.assertEqual(client.get(f"/cal/{new_token}.ics").status_code, 200)

    def test_bank_csv_suggests_but_requires_confirmation_and_deduplicates(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, client = self.make_business("Banco controlado")
        other, _ = self.make_business("Banco ajeno")
        invoice = db.add_invoice(
            client["id"], "Reparación", 100, business_id=business["id"]
        )
        invoice = db.issue_invoice(invoice["id"], business["id"])
        csv_data = (
            "Fecha;Importe;Concepto;Ordenante;Referencia\n"
            f"17/07/2026;121,00;Pago {invoice['number']};{client['name']};{invoice['number']}\n"
            "17/07/2026;-25,50;Compra material;Proveedor;REC-2\n"
            "17/07/2026;-25,50;Compra material;Proveedor;REC-2\n"
        ).encode("utf-8")
        db.create_user(
            "banco@example.com", auth.hash_password(TEST_PASSWORD),
            business["id"],
        )
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as http:
                login = http.post("/login", data={
                    "email": "banco@example.com",
                    "password": TEST_PASSWORD,  # pragma: allowlist secret
                }, follow_redirects=False)
                self.assertEqual(login.status_code, 303)
                imported = http.post(
                    f"/b/{business['id']}/bank-import",
                    files={"file": ("extracto.csv", csv_data, "text/csv")},
                    follow_redirects=False,
                )
                self.assertEqual(imported.status_code, 303)
                self.assertIn("bank_imported=3", imported.headers["location"])
                page = http.get(f"/b/{business['id']}/cobros")
                self.assertIn("Extracto bancario", page.text)
                self.assertIn(invoice["number"], page.text)
        movements = db.list_bank_transactions(business["id"])
        incoming = next(item for item in movements if item["amount"] > 0)
        outgoing = next(item for item in movements if item["amount"] < 0)
        self.assertEqual(len([item for item in movements if item["amount"] < 0]), 2)
        self.assertEqual(incoming["status"], "suggested")
        self.assertEqual(incoming["suggested_invoice_id"], invoice["id"])
        self.assertEqual(outgoing["status"], "imported")
        self.assertEqual(db.list_bank_transactions(other["id"]), [])

        duplicate = banking.import_csv(business["id"], csv_data)
        self.assertEqual(duplicate["created"], 0)
        self.assertEqual(duplicate["duplicates"], 3)
        with self.assertRaises(ValueError):
            db.confirm_bank_transaction(incoming["id"], other["id"])

        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as http:
                http.post("/login", data={
                    "email": "banco@example.com",
                    "password": TEST_PASSWORD,
                })
                response = http.post(
                    f"/api/{business['id']}/bank-transactions/{incoming['id']}/confirm",
                    json={},
                )
                self.assertEqual(response.status_code, 200)
                confirmed = response.json()["transaction"]
        self.assertEqual(confirmed["status"], "confirmed")
        self.assertEqual(
            db.get_invoice(invoice["id"], business["id"])["status"], "cobrada"
        )
        self.assertEqual(
            len(db.list_invoice_payments(invoice["id"], business["id"])), 1
        )
        db.confirm_bank_transaction(incoming["id"], business["id"])
        self.assertEqual(
            len(db.list_invoice_payments(invoice["id"], business["id"])), 1
        )

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
        db.update_branding(
            business["id"], template="editorial", brand_color="#7a1f4b",
            document_footer="Gracias por confiar en nosotros.",
            quote_terms="Materiales incluidos según descripción.",
            default_quote_validity_days=45,
        )
        biz = db.get_business(business["id"])
        self.assertEqual(biz["invoice_template"], "editorial")
        self.assertEqual(db.business_brand_color(biz), "#7a1f4b")
        self.assertEqual(biz["default_quote_validity_days"], 45)
        with self.assertRaises(ValueError):
            db.update_branding(business["id"], template="rara")
        with self.assertRaises(ValueError):
            db.update_branding(business["id"], brand_color="rojo")
        with self.assertRaises(ValueError):
            db.update_branding(business["id"], default_quote_validity_days=13)
        self.assertEqual(db.business_initials("Reformas Garcia"), "RG")
        # El portal expone color e iniciales del negocio que atiende, aislado.
        view = db.client_portal_view(business["id"], client["id"])
        self.assertEqual(view["business"]["brand_color"], "#7a1f4b")
        self.assertIn("Materiales incluidos", view["business"]["quote_terms"])
        self.assertTrue(view["business"]["initials"])

        quote = db.add_quote(
            client["id"], "Instalación completa", 1200,
            notes="Incluye montaje y puesta en marcha.", business_id=business["id"],
        )
        self.assertEqual(quote["valid_until"], (date.today() + timedelta(days=45)).isoformat())
        from noesis.web.invoice_pdf import build_quote_pdf
        pdf = build_quote_pdf(quote["id"], business["id"])
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 2_000)

    def test_footer_image_is_versioned_and_frozen_when_invoice_is_issued(self):
        import base64

        business, client = self.make_business("Marca congelada")
        footer = base64.b64encode(TINY_PNG).decode("ascii")
        db.update_branding(
            business["id"], template="editorial", brand_color="#7a1f4b",
            footer_image_data=footer, footer_image_mime="image/png",
            footer_image_width=75, footer_image_alignment="right",
            footer_image_scope="all",
        )
        draft = db.add_invoice(
            client["id"], "Trabajo con distintivo", 100,
            business_id=business["id"],
        )
        issued = db.issue_invoice(draft["id"], business["id"])
        frozen = db.get_invoice_document_profile(issued["id"], business["id"])
        self.assertIsNotNone(frozen)
        self.assertEqual(frozen["brand_color"], "#7a1f4b")
        self.assertEqual(frozen["footer_image_data"], footer)
        self.assertEqual(frozen["footer_image_width"], 75)
        self.assertEqual(frozen["footer_image_alignment"], "right")

        db.update_branding(
            business["id"], brand_color="#14463b", clear_footer_image=True,
            footer_image_width=25, footer_image_alignment="left",
            footer_image_scope="invoices",
        )
        current = db.get_business(business["id"])
        still_frozen = db.get_invoice_document_profile(issued["id"], business["id"])
        self.assertIsNone(current["footer_image_data"])
        self.assertEqual(current["brand_color"], "#14463b")
        self.assertEqual(still_frozen["brand_color"], "#7a1f4b")
        self.assertEqual(still_frozen["footer_image_data"], footer)

        from noesis.web.invoice_pdf import build_invoice_pdf
        pdf = build_invoice_pdf(issued["id"], business["id"])
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 2_000)

    def test_document_profile_reference_is_tenant_scoped(self):
        business_a, client_a = self.make_business("Perfil A")
        business_b, _ = self.make_business("Perfil B")
        db.update_branding(business_b["id"], brand_color="#7a1f4b")
        with db.get_conn() as conn:
            foreign_profile = conn.execute(
                "SELECT id FROM document_profiles WHERE business_id=?",
                (business_b["id"],),
            ).fetchone()["id"]
        invoice = db.add_invoice(
            client_a["id"], "Aislamiento visual", 80,
            business_id=business_a["id"],
        )
        with self.assertRaises(db.IntegrityError):
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE invoices SET document_profile_id=? "
                    "WHERE id=? AND business_id=?",
                    (foreign_profile, invoice["id"], business_a["id"]),
                )

    def test_branding_http_sanitizes_images_and_exposes_pdf_preview(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, _ = self.make_business("Vista de marca")
        user = db.create_user(
            "marca@example.com", auth.hash_password(TEST_PASSWORD), business["id"]
        )
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                client.post("/login", data={
                    "email": user["email"], "password": TEST_PASSWORD,
                })
                response = client.post(
                    f"/b/{business['id']}/branding",
                    data={
                        "template": "minimal", "brand_color": "#2e8b74",
                        "document_footer": "Proyecto financiado.",
                        "quote_terms": "Condiciones de ejemplo.",
                        "default_quote_validity_days": "30",
                        "footer_image_width": "50",
                        "footer_image_alignment": "center",
                        "footer_image_scope": "all",
                    },
                    files={
                        "logo": ("logo.png", TINY_PNG, "image/png"),
                        "footer_image": ("ayuda.png", TINY_PNG, "image/png"),
                    },
                    follow_redirects=False,
                )
                self.assertEqual(response.status_code, 303)
                self.assertIn("ok=marca", response.headers["location"])
                saved = db.get_business(business["id"])
                self.assertEqual(saved["logo_mime"], "image/png")
                self.assertEqual(saved["footer_image_mime"], "image/png")
                self.assertEqual(saved["footer_image_width"], 50)
                self.assertEqual(saved["footer_image_scope"], "all")
                page = client.get(f"/b/{business['id']}/ajustes")
                self.assertIn("Las emitidas no cambian", page.text)
                self.assertIn("Imagen o distintivo", page.text)
                preview = client.get(
                    f"/api/{business['id']}/branding/preview.pdf"
                )
                self.assertEqual(preview.status_code, 200)
                self.assertTrue(preview.content.startswith(b"%PDF"))

                rejected = client.post(
                    f"/b/{business['id']}/branding",
                    data={
                        "template": "minimal", "brand_color": "#2e8b74",
                        "default_quote_validity_days": "30",
                        "footer_image_width": "50",
                        "footer_image_alignment": "center",
                        "footer_image_scope": "all",
                    },
                    files={
                        "footer_image": ("falsa.png", b"no-es-imagen", "image/png"),
                    },
                    follow_redirects=False,
                )
                self.assertEqual(rejected.status_code, 303)
                self.assertIn("error=marca", rejected.headers["location"])

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
            auth.hash_password(TEST_PASSWORD),
            business["id"],
        )
        response = client.post(
            "/login",
            data={"email": email, "password": TEST_PASSWORD},
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
            TINY_JPEG,
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
                    files={"file": ("ticket.jpg", TINY_JPEG, "image/jpeg")},
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
                    files={"file": ("ticket.png", TINY_PNG, "image/png")},
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
            auth.hash_password(TEST_PASSWORD),
            business["id"],
        )
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                login = client.post(
                    "/login",
                    data={
                        "email": "recordatorios@example.com",
                        "password": TEST_PASSWORD,
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
                self.assertIn("Ayuda avanzada de Noesis", page.text)
                self.assertNotIn("Yo vigilo que todo siga funcionando", page.text)
                self.assertNotIn("Calendario externo", page.text)
                self.assertNotIn("IA privada", page.text)
                self.assertEqual(
                    client.get(f"/api/{business['id']}/integrations").status_code,
                    404,
                )

                requested = client.post(
                    f"/api/{business['id']}/integrations/banking",
                    json={"action": "request"},
                )
                self.assertEqual(requested.status_code, 400)
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
                self.assertEqual(disconnected.json(), {"ok": True})

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


class SubscriptionReadOnlyHttpTestCase(BackendTestCase):
    def test_stripe_annual_checkout_uses_the_annual_price(self):
        from noesis.adapters import billing

        provider = billing.StripeBillingProvider("sk_test_example")
        business = {"id": 42, "owner_email": "pago@example.com"}
        with patch.object(
            config, "STRIPE_PRICE_PRO_ANNUAL", "price_pro_annual"
        ), patch.object(
            provider, "_post", return_value={"url": "https://checkout.example/year"}
        ) as post:
            url = provider.checkout_url(
                business, "pro", "https://noesis.test/ok",
                "https://noesis.test/cancel", "annual",
            )

        self.assertEqual(url, "https://checkout.example/year")
        payload = post.call_args.args[1]
        self.assertEqual(payload["line_items[0][price]"], "price_pro_annual")
        self.assertEqual(payload["automatic_tax[enabled]"], "true")
        self.assertEqual(payload["tax_id_collection[enabled]"], "true")
        self.assertEqual(payload["billing_address_collection"], "required")
        self.assertEqual(payload["metadata[billing_period]"], "annual")
        self.assertEqual(
            payload["subscription_data[metadata][billing_period]"], "annual"
        )

    def test_stripe_portal_uses_scoped_flows_for_billing_actions(self):
        from noesis.adapters import billing

        provider = billing.StripeBillingProvider("sk_test_example")
        business = {
            "id": 42,
            "stripe_customer_id": "cus_current",
            "stripe_subscription_id": "sub_current",
        }
        snapshot = {
            "id": "sub_current",
            "items": {"data": [{"id": "si_current", "price": {"id": "old"}}]},
        }
        with (
            patch.object(config, "STRIPE_PRICE_PRO_ANNUAL", "price_pro_annual"),
            patch.object(provider, "subscription_snapshot", return_value=snapshot),
            patch.object(
                provider, "_managed_portal_configuration",
                return_value="bpc_noesis",
            ),
            patch.object(
                provider, "_post", return_value={"url": "https://billing.example/flow"},
            ) as post,
        ):
            payment_url = provider.portal_url(
                business, "https://noesis.test/subscription", action="payment_method",
            )
            payment_payload = post.call_args.args[1]
            cancel_url = provider.portal_url(
                business, "https://noesis.test/subscription", action="cancel",
            )
            cancel_payload = post.call_args.args[1]
            change_url = provider.portal_url(
                business, "https://noesis.test/subscription", action="change",
                plan="pro", billing_period="annual",
            )
            change_payload = post.call_args.args[1]

        self.assertEqual(payment_url, "https://billing.example/flow")
        self.assertEqual(cancel_url, "https://billing.example/flow")
        self.assertEqual(change_url, "https://billing.example/flow")
        self.assertEqual(payment_payload["flow_data[type]"], "payment_method_update")
        self.assertEqual(cancel_payload["flow_data[type]"], "subscription_cancel")
        self.assertEqual(
            cancel_payload["flow_data[subscription_cancel][subscription]"],
            "sub_current",
        )
        self.assertEqual(
            change_payload["flow_data[type]"], "subscription_update_confirm",
        )
        self.assertEqual(
            change_payload[
                "flow_data[subscription_update_confirm][items][0][price]"
            ],
            "price_pro_annual",
        )
        self.assertEqual(
            change_payload[
                "flow_data[subscription_update_confirm][items][0][id]"
            ],
            "si_current",
        )
        self.assertEqual(
            change_payload["flow_data[after_completion][type]"], "redirect",
        )
        self.assertEqual(payment_payload["configuration"], "bpc_noesis")
        self.assertEqual(cancel_payload["configuration"], "bpc_noesis")
        self.assertEqual(change_payload["configuration"], "bpc_noesis")

    def test_stripe_builds_managed_portal_with_every_configured_price(self):
        from noesis.adapters import billing

        provider = billing.StripeBillingProvider("sk_test_example")
        prices = {
            "price_autonomo_month": "prod_autonomo",
            "price_pro_month": "prod_pro",
            "price_premium_month": "prod_premium",
            "price_autonomo_year": "prod_autonomo",
            "price_pro_year": "prod_pro",
            "price_premium_year": "prod_premium",
        }

        def stripe_get(path):
            if path.startswith("billing_portal/configurations?"):
                return {"data": []}
            price_id = path.rsplit("/", 1)[-1]
            return {"id": price_id, "product": prices[price_id]}

        with (
            patch.multiple(
                config,
                STRIPE_PRICE_AUTONOMO="price_autonomo_month",
                STRIPE_PRICE_PRO="price_pro_month",
                STRIPE_PRICE_PREMIUM="price_premium_month",
                STRIPE_PRICE_AUTONOMO_ANNUAL="price_autonomo_year",
                STRIPE_PRICE_PRO_ANNUAL="price_pro_year",
                STRIPE_PRICE_PREMIUM_ANNUAL="price_premium_year",
            ),
            patch.object(provider, "_get", side_effect=stripe_get),
            patch.object(
                provider, "_post", return_value={"id": "bpc_noesis"},
            ) as post,
        ):
            configuration_id = provider._managed_portal_configuration(
                "https://noesis.test/b/42/suscripcion"
            )

        self.assertEqual(configuration_id, "bpc_noesis")
        post.assert_called_once()
        path, payload = post.call_args.args
        self.assertEqual(path, "billing_portal/configurations")
        self.assertEqual(payload["features[payment_method_update][enabled]"], "true")
        self.assertEqual(payload["features[subscription_cancel][mode]"], "at_period_end")
        self.assertEqual(payload["features[subscription_update][enabled]"], "true")
        self.assertEqual(
            payload["features[subscription_update][products][0][prices][]"],
            ["price_autonomo_month", "price_autonomo_year"],
        )
        self.assertEqual(
            payload["features[subscription_update][products][2][prices][]"],
            ["price_premium_month", "price_premium_year"],
        )
        self.assertEqual(payload["metadata[noesis_portal]"], "noesis-v1")

    def test_stripe_reuses_the_active_managed_portal_configuration(self):
        from noesis.adapters import billing

        provider = billing.StripeBillingProvider("sk_test_example")
        with (
            patch.multiple(
                config,
                STRIPE_PRICE_AUTONOMO="price_autonomo",
                STRIPE_PRICE_PRO="price_pro",
                STRIPE_PRICE_PREMIUM="price_premium",
                STRIPE_PRICE_AUTONOMO_ANNUAL="price_autonomo_year",
                STRIPE_PRICE_PRO_ANNUAL="price_pro_year",
                STRIPE_PRICE_PREMIUM_ANNUAL="price_premium_year",
            ),
            patch.object(provider, "_get", return_value={"data": [{
                "id": "bpc_existing",
                "active": True,
                "metadata": {"noesis_portal": "noesis-v1"},
                "features": {
                    "payment_method_update": {"enabled": True},
                    "subscription_cancel": {"enabled": True},
                    "subscription_update": {
                        "enabled": True,
                        "products": [{"prices": [
                            "price_autonomo", "price_pro", "price_premium",
                            "price_autonomo_year", "price_pro_year",
                            "price_premium_year",
                        ]}],
                    },
                },
            }]}),
            patch.object(provider, "_post") as post,
        ):
            configuration_id = provider._managed_portal_configuration(
                "https://noesis.test/b/42/suscripcion"
            )

        self.assertEqual(configuration_id, "bpc_existing")
        post.assert_not_called()

    def test_checkout_return_reconciles_authoritative_active_subscription(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, _ = self.make_business("Stripe reconciliado")
        db.create_user(
            "reconcile@example.com", auth.hash_password(TEST_PASSWORD),
            business["id"],
        )
        db.set_subscription(
            business["id"], "pending", plan="trial",
            customer_id="cus_reconcile", subscription_id="sub_reconcile",
        )
        snapshot = {
            "id": "sub_reconcile",
            "customer": "cus_reconcile",
            "status": "active",
            "metadata": {"business_id": str(business["id"])},
            "items": {"data": [{"price": {"id": "price_autonomo"}}]},
        }
        provider = MagicMock()
        provider.subscription_snapshot.return_value = snapshot
        wrong_business = {
            **snapshot,
            "metadata": {"business_id": str(business["id"] + 1)},
        }

        with (
            patch.object(server, "start_scheduler", lambda: None),
            patch.object(config, "STRIPE_PRICE_AUTONOMO", "price_autonomo"),
            patch.object(
                server.billing_adapter, "get_provider", return_value=provider
            ),
            TestClient(server.app) as client,
        ):
            self.assertIsNone(
                server.billing_adapter.subscription_evidence(
                    business, wrong_business,
                )
            )
            client.post("/login", data={
                "email": "reconcile@example.com", "password": TEST_PASSWORD,
            })
            page = client.get(
                f"/b/{business['id']}/suscripcion?status=checkout_return"
            )

        self.assertEqual(page.status_code, 200)
        self.assertIn("subscription-success", page.text)
        updated = db.get_business(business["id"])
        self.assertEqual(updated["subscription_status"], "active")
        self.assertEqual(updated["plan"], "autonomo")
        self.assertIn('class="plan selected-plan"', page.text)
        provider.subscription_snapshot.assert_called_once()

    def test_subscription_page_shows_human_dates_and_a_finished_trial(self):
        """La cabecera no puede ensenar una marca ISO ni decir "En prueba" a
        quien ya esta en modo consulta: el estado sigue siendo 'trial' hasta que
        alguien contrata, y la caducidad solo se ve comparando la fecha."""
        from starlette.testclient import TestClient
        from noesis.web import server

        business, _ = self.make_business("Prueba caducada")
        db.create_user(
            "prueba-caducada@example.com", auth.hash_password(TEST_PASSWORD),
            business["id"],
        )
        with (
            patch.object(server, "start_scheduler", lambda: None),
            TestClient(server.app) as client,
        ):
            client.post("/login", data={
                "email": "prueba-caducada@example.com",
                "password": TEST_PASSWORD,
            })
            db.set_trial(business["id"], days=20)
            vigente = client.get(f"/b/{business['id']}/suscripcion")
            db.set_trial(business["id"], days=-30)
            caducada = client.get(f"/b/{business['id']}/suscripcion")

        self.assertEqual(vigente.status_code, 200)
        self.assertEqual(caducada.status_code, 200)
        # Ninguna de las dos ensena la marca ISO interna.
        self.assertNotIn("T00:00:00", vigente.text)
        self.assertNotIn("T00:00:00", caducada.text)
        # Prueba vigente: se anuncia como tal y con fecha legible.
        futura = (date.today() + timedelta(days=20)).strftime("%d/%m/%Y")
        self.assertIn("En prueba", vigente.text)
        self.assertIn(futura, vigente.text)
        # Prueba vencida: deja de decir "En prueba" y se marca en rojo.
        pasada = (date.today() - timedelta(days=30)).strftime("%d/%m/%Y")
        self.assertIn("Prueba terminada", caducada.text)
        self.assertIn(pasada, caducada.text)
        self.assertNotIn("En prueba", caducada.text)
        self.assertIn("sub-state trial expired", caducada.text)
        # Y el producto coincide: sin acceso de escritura.
        self.assertFalse(
            db.subscription_allows_access(db.get_business(business["id"]))
        )

    def test_active_subscription_is_managed_without_a_second_checkout(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, _ = self.make_business("Stripe plan actual")
        db.create_user(
            "current-plan@example.com", auth.hash_password(TEST_PASSWORD),
            business["id"],
        )
        db.set_subscription(
            business["id"], "active", plan="autonomo",
            customer_id="cus_current", subscription_id="sub_current",
        )
        provider = MagicMock()
        provider.portal_url.return_value = "https://billing.example/current"

        with (
            patch.object(server, "start_scheduler", lambda: None),
            patch.object(
                server.billing_adapter, "get_provider", return_value=provider,
            ),
            TestClient(server.app) as client,
        ):
            client.post("/login", data={
                "email": "current-plan@example.com",
                "password": TEST_PASSWORD,
            })
            page = client.get(f"/b/{business['id']}/suscripcion")
            db.set_subscription(
                business["id"], "active", plan="premium",
                customer_id="cus_current", subscription_id="sub_current",
            )
            premium_page = client.get(f"/b/{business['id']}/suscripcion")
            change = client.post(
                f"/b/{business['id']}/suscripcion/checkout",
                data={"plan": "pro", "billing_period": "annual"},
                follow_redirects=False,
            )

        self.assertEqual(page.status_code, 200)
        self.assertIn("Plan actual", page.text)
        self.assertIn("Gestionar plan", page.text)
        self.assertIn("Mejorar a Negocio", page.text)
        self.assertIn("Mejorar a Premium", page.text)
        self.assertIn("Cambiar tarjeta", page.text)
        self.assertIn("Cancelar suscripción", page.text)
        self.assertEqual(page.text.count("data-stripe-portal-form"), 6)
        self.assertIn('name="action" value="change"', page.text)
        self.assertNotIn("Activar plan Aut", page.text)
        self.assertNotIn("/suscripcion/checkout", page.text)
        self.assertEqual(premium_page.text.count("Incluido en tu plan"), 2)
        self.assertNotIn("Mejorar a ", premium_page.text)
        self.assertEqual(change.status_code, 303)
        self.assertEqual(change.headers["location"], "https://billing.example/current")
        provider.portal_url.assert_called_once_with(
            db.get_business(business["id"]),
            f"{config.BASE_URL}/b/{business['id']}/suscripcion",
            action="change", plan="pro", billing_period="annual",
        )
        provider.checkout_url.assert_not_called()

    def test_subscription_portal_routes_only_supported_actions(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, _ = self.make_business("Stripe acciones portal")
        db.create_user(
            "portal-actions@example.com", auth.hash_password(TEST_PASSWORD),
            business["id"],
        )
        db.set_subscription(
            business["id"], "active", plan="pro",
            customer_id="cus_actions", subscription_id="sub_actions",
        )
        provider = MagicMock()
        provider.portal_url.return_value = "https://billing.example/cancel"

        with (
            patch.object(server, "start_scheduler", lambda: None),
            patch.object(
                server.billing_adapter, "get_provider", return_value=provider,
            ),
            TestClient(server.app) as client,
        ):
            client.post("/login", data={
                "email": "portal-actions@example.com",
                "password": TEST_PASSWORD,
            })
            cancel = client.post(
                f"/b/{business['id']}/suscripcion/portal",
                data={"action": "cancel"}, follow_redirects=False,
            )
            invalid = client.post(
                f"/b/{business['id']}/suscripcion/portal",
                data={"action": "delete_everything"}, follow_redirects=False,
            )

        self.assertEqual(cancel.status_code, 303)
        self.assertEqual(cancel.headers["location"], "https://billing.example/cancel")
        self.assertEqual(invalid.status_code, 303)
        self.assertTrue(invalid.headers["location"].endswith("status=invalid"))
        provider.portal_url.assert_called_once_with(
            db.get_business(business["id"]),
            f"{config.BASE_URL}/b/{business['id']}/suscripcion",
            action="cancel", plan="", billing_period="monthly",
        )

    def test_every_subscription_button_opens_one_scoped_portal_flow(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, _ = self.make_business("Stripe recorrido completo")
        db.create_user(
            "portal-e2e@example.com", auth.hash_password(TEST_PASSWORD),
            business["id"],
        )
        db.set_subscription(
            business["id"], "active", plan="autonomo",
            customer_id="cus_e2e", subscription_id="sub_e2e",
        )
        provider = MagicMock()
        provider.portal_url.side_effect = lambda *_args, **kwargs: (
            f"https://billing.example/{kwargs['action']}"
        )
        # Los seis formularios que ve Autonomo: gestión superior, tarjeta,
        # gestión desde su tarjeta actual, dos mejoras y cancelación.
        actions = (
            ({"action": "manage"}, "manage"),
            ({"action": "payment_method"}, "payment_method"),
            ({"action": "manage"}, "manage"),
            ({
                "action": "change", "plan": "pro",
                "billing_period": "monthly",
            }, "change"),
            ({
                "action": "change", "plan": "premium",
                "billing_period": "annual",
            }, "change"),
            ({"action": "cancel"}, "cancel"),
        )

        with (
            patch.object(server, "start_scheduler", lambda: None),
            patch.object(
                server.billing_adapter, "get_provider", return_value=provider,
            ),
            TestClient(server.app) as client,
        ):
            client.post("/login", data={
                "email": "portal-e2e@example.com",
                "password": TEST_PASSWORD,
            })
            responses = [
                client.post(
                    f"/b/{business['id']}/suscripcion/portal",
                    data=data,
                    headers={"sec-fetch-site": "same-origin"},
                    follow_redirects=False,
                )
                for data, _action in actions
            ]

        self.assertEqual([response.status_code for response in responses], [303] * 6)
        self.assertEqual(
            [response.headers["location"] for response in responses],
            [f"https://billing.example/{action}" for _data, action in actions],
        )
        self.assertEqual(provider.portal_url.call_count, 6)
        monthly_change = provider.portal_url.call_args_list[3]
        annual_change = provider.portal_url.call_args_list[4]
        self.assertEqual(monthly_change.kwargs, {
            "action": "change", "plan": "pro", "billing_period": "monthly",
        })
        self.assertEqual(annual_change.kwargs, {
            "action": "change", "plan": "premium", "billing_period": "annual",
        })

    def test_subscription_portal_failure_returns_to_a_visible_error(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, _ = self.make_business("Stripe portal caido")
        db.create_user(
            "portal-failure@example.com", auth.hash_password(TEST_PASSWORD),
            business["id"],
        )
        db.set_subscription(
            business["id"], "active", plan="autonomo",
            customer_id="cus_failure", subscription_id="sub_failure",
        )
        provider = MagicMock()
        provider.portal_url.return_value = None

        with (
            patch.object(server, "start_scheduler", lambda: None),
            patch.object(
                server.billing_adapter, "get_provider", return_value=provider,
            ),
            TestClient(server.app) as client,
        ):
            client.post("/login", data={
                "email": "portal-failure@example.com",
                "password": TEST_PASSWORD,
            })
            response = client.post(
                f"/b/{business['id']}/suscripcion/portal",
                data={"action": "manage"}, follow_redirects=False,
            )
            page = client.get(response.headers["location"])

        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.headers["location"].endswith(
            "?status=noportal#gestion-suscripcion"
        ))
        self.assertEqual(page.status_code, 200)
        self.assertIn('id="gestion-suscripcion"', page.text)
        self.assertIn("No he podido abrir", page.text)
        self.assertEqual(
            db.count_product_events(
                business["id"], "subscription_portal_failed",
            ),
            1,
        )

    def test_public_and_account_pricing_share_the_current_catalog(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, _ = self.make_business("Precios actuales")
        db.create_user(
            "precios@example.com",
            auth.hash_password(TEST_PASSWORD),
            business["id"],
        )

        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                public_page = client.get("/precios")
                self.assertEqual(public_page.status_code, 200)
                self.assertIn("Recepcionista 24/7", public_page.text)
                self.assertIn("Beta con acceso preferente", public_page.text)
                self.assertIn("1 mes gratis", public_page.text)
                self.assertIn('data-annual="319"', public_page.text)
                # Con el registro abierto los planes llevan al alta normal.
                self.assertIn(
                    "/onboarding?intent=trial&plan=autonomo", public_page.text
                )
                # Con el registro cerrado llevan al formulario de solicitud, y en
                # ambos casos se conserva el plan que miraba el visitante. El
                # indicador es un global de plantilla fijado al arrancar, así que
                # se sustituye ahí y no en la configuración.
                from noesis.web.deps import TEMPLATES

                with patch.dict(
                    TEMPLATES.env.globals, {"public_signup_available": False}
                ):
                    closed_page = client.get("/precios")
                self.assertIn("/solicitar-acceso?plan=autonomo", closed_page.text)
                self.assertNotIn("/onboarding?intent=", closed_page.text)
                for route in ("/", "/equipo", "/preguntas", "/contacto"):
                    page = client.get(route)
                    self.assertEqual(page.status_code, 200, route)
                    self.assertIn('href="/equipo"', page.text)
                # Producto se fusionó con la portada; su enlace antiguo sigue vivo.
                retired = client.get("/producto", follow_redirects=False)
                self.assertEqual(retired.status_code, 301)
                self.assertEqual(retired.headers["location"], "/#como-funciona")
                team_page = client.get("/equipo")
                self.assertIn("Un equipo pequeño", team_page.text)
                self.assertNotIn("4,9", team_page.text)
                home_page = client.get("/")
                self.assertIn("Taller García", home_page.text)
                self.assertIn("product-home-preview", home_page.text)
                self.assertIn("data-product-demo", home_page.text)
                self.assertNotIn("Inicio de Noesis", home_page.text)
                self.assertNotIn("Empresa de ejemplo", home_page.text)
                self.assertNotIn("Vista de ejemplo basada", home_page.text)
                self.assertIn("hero-impact", home_page.text)
                self.assertIn("Parte de hoy", home_page.text)
                self.assertIn("Puesta en marcha", home_page.text)
                self.assertIn("6 de 6 pasos listos", home_page.text)
                self.assertIn("Beneficio este mes", home_page.text)
                self.assertIn("Noesis está trabajando", home_page.text)
                self.assertIn("Cómo va el dinero", home_page.text)
                self.assertIn("data-demo-crumb", home_page.text)
                self.assertIn("Conectar WhatsApp", home_page.text)
                self.assertIn("demo-home-chart", home_page.text)
                self.assertIn("chart.umd.min.js", home_page.text)
                # 10 apartados del menú + 11 subapartados (Caja/Análisis/Ingresos/
                # Costes, Facturas/Presupuestos/Cobros/Impuestos, Clientes/CRM/Productos).
                self.assertEqual(home_page.text.count("data-demo-tab="), 21)
                self.assertIn("data-demo-subnav", home_page.text)
                self.assertIn("IVA · Modelo 303", home_page.text)
                self.assertIn("page-note", home_page.text)
                annual_signup = client.get(
                    "/onboarding?plan=autonomo&billing=annual"
                )
                self.assertEqual(annual_signup.status_code, 200)
                self.assertIn('data-annual="319" selected', annual_signup.text)
                self.assertIn('name="billing" value="annual"', annual_signup.text)
                self.assertIn('id="signup-annual-offer"', annual_signup.text)
                self.assertIn('id="signup-annual-before"', annual_signup.text)
                self.assertIn('name="sector" required maxlength="80"', annual_signup.text)
                self.assertNotIn('<select name="sector"', annual_signup.text)

                login = client.post(
                    "/login",
                    data={
                        "email": "precios@example.com",
                        "password": TEST_PASSWORD,
                    },
                    follow_redirects=False,
                )
                self.assertEqual(login.status_code, 303)
                account_page = client.get(f"/b/{business['id']}/suscripcion")
                self.assertEqual(account_page.status_code, 200)

                provider = MagicMock()
                provider.checkout_url.return_value = "https://checkout.example/annual"
                with patch.object(
                    server.billing_adapter, "get_provider", return_value=provider
                ):
                    checkout = client.post(
                        f"/b/{business['id']}/suscripcion/checkout",
                        data={"plan": "pro", "billing_period": "annual"},
                        follow_redirects=False,
                    )
                self.assertEqual(checkout.status_code, 303)
                self.assertEqual(
                    checkout.headers["location"], "https://checkout.example/annual"
                )
                self.assertEqual(provider.checkout_url.call_args.args[-1], "annual")

        for page in (public_page.text, account_page.text):
            self.assertIn('data-monthly="29"', page)
            self.assertIn('data-monthly="49"', page)
            self.assertIn('data-monthly="99"', page)
            self.assertGreaterEqual(page.count("+ IVA/mes"), 3)
            self.assertNotIn("39 €", page)
            self.assertNotIn("79 €", page)

    def test_inactive_account_can_read_but_cannot_change_the_business(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, existing_client = self.make_business("Solo consulta")
        db.create_user(
            "consulta@example.com",
            auth.hash_password(TEST_PASSWORD),
            business["id"],
        )
        db.set_subscription(business["id"], "past_due", plan="tranquilidad")

        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                login = client.post(
                    "/login",
                    data={
                        "email": "consulta@example.com",
                        "password": TEST_PASSWORD,
                    },
                    follow_redirects=False,
                )
                self.assertEqual(login.status_code, 303)
                panel = client.get(f"/b/{business['id']}/clientes")
                self.assertEqual(panel.status_code, 200)
                self.assertIn("Modo consulta", panel.text)
                self.assertEqual(
                    client.get(f"/api/{business['id']}/clients").status_code, 200
                )
                self.assertEqual(
                    client.get(f"/api/{business['id']}/plan").status_code, 200
                )
                self.assertEqual(db.list_recommendations(business["id"]), [])

                blocked = client.post(
                    f"/api/{business['id']}/clients", json={"name": "No crear"}
                )
                self.assertEqual(blocked.status_code, 402)
                self.assertEqual(blocked.json()["code"], "subscription_required")
                self.assertIsNone(db.find_client("No crear", business["id"]))
                link = client.get(
                    f"/api/{business['id']}/clients/{existing_client['id']}/portal-link"
                )
                self.assertEqual(link.status_code, 402)
                self.assertEqual(link.json()["code"], "subscription_required")

                subscription = client.get(f"/b/{business['id']}/suscripcion")
                self.assertEqual(subscription.status_code, 200)
                self.assertIn('data-monthly="49"', subscription.text)
                self.assertIn('data-monthly="99"', subscription.text)


class GoogleOAuthHttpTestCase(BackendTestCase):
    def test_google_login_and_signup_keep_the_same_account_flow(self):
        from urllib.parse import parse_qs, urlparse

        from starlette.testclient import TestClient
        from noesis.web import server
        from noesis.web.routers import account

        with patch.object(config, "GOOGLE_OAUTH_CLIENT_ID", "google-client"), patch.object(
            config, "GOOGLE_OAUTH_CLIENT_SECRET", "google-secret"
        ), patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                self.assertNotIn("Continuar con Google", client.get("/").text)
                self.assertIn("Continuar con Google", client.get("/login").text)
                self.assertIn("Continuar con Google", client.get("/onboarding").text)
                start = client.get(
                    "/auth/google?flow=signup&plan=pro&billing=annual&intent=subscribe",
                    follow_redirects=False,
                )
                self.assertEqual(start.status_code, 303)
                parsed = urlparse(start.headers["location"])
                self.assertEqual(parsed.netloc, "accounts.google.com")
                state = parse_qs(parsed.query)["state"][0]

                with patch.object(account, "_google_profile", return_value={
                    "email": "google@example.com", "name": "David García",
                }):
                    callback = client.get(
                        f"/auth/google/callback?code=one-time-code&state={state}",
                        follow_redirects=False,
                    )
                self.assertEqual(callback.status_code, 303)
                self.assertIn(
                    "/onboarding/google?plan=pro&billing=annual&intent=subscribe",
                    callback.headers["location"],
                )

                complete = client.get(callback.headers["location"])
                self.assertEqual(complete.status_code, 200)
                self.assertIn("google@example.com", complete.text)
                self.assertIn("signup-annual-offer-static", complete.text)
                self.assertIn('name="sector" required maxlength="80"', complete.text)
                created = client.post(
                    "/onboarding/google",
                    data={
                        "name": "Taller Google",
                        "sector": "Restauración de patrimonio",
                        "acepto": "1", "plan": "pro", "billing": "annual",
                        "intent": "subscribe",
                    },
                    follow_redirects=False,
                )
                self.assertEqual(created.status_code, 303)
                self.assertIn("/onboarding/setup/", created.headers["location"])
                user = db.get_user_by_email("google@example.com")
                self.assertIsNotNone(user)
                self.assertEqual(
                    db.get_business(user["business_id"])["sector"],
                    "Restauración de patrimonio",
                )

                second_start = client.get("/auth/google", follow_redirects=False)
                second_state = parse_qs(urlparse(second_start.headers["location"]).query)["state"][0]
                with patch.object(account, "_google_profile", return_value={
                    "email": "google@example.com", "name": "David García",
                }):
                    signed_in = client.get(
                        f"/auth/google/callback?code=another-code&state={second_state}",
                        follow_redirects=False,
                    )
                self.assertEqual(signed_in.status_code, 303)
                self.assertEqual(
                    signed_in.headers["location"],
                    f"/onboarding/setup/{user['business_id']}",
                )


class VisualContractTestCase(unittest.TestCase):
    """Fija los detalles móviles que hacen que el piloto parezca terminado."""

    def test_demo_badge_and_assistant_mobile_controls_are_readable(self):
        web = Path(__file__).parents[1] / "src" / "noesis" / "web"
        base = (web / "templates" / "base.html").read_text(encoding="utf-8")
        assistant = (web / "templates" / "asistente.html").read_text(
            encoding="utf-8"
        )
        css = (web / "static" / "app.css").read_text(encoding="utf-8")

        self.assertIn('class="bn-create locked demo"', base)
        self.assertIn('aria-hidden="true">Demo</span>', base)
        self.assertNotIn("â€“", base)
        self.assertIn(".replace(/_(.+?)_/g,'<em>$1</em>')", assistant)
        self.assertIn(".chat-wrap > .chips { flex-wrap:wrap;", css)
        self.assertIn("flex:1 1 145px; white-space:normal;", css)


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
                self.assertEqual(accepted["decision_source"], "client_portal")
                self.assertEqual(len(accepted["decision_ip_hash"]), 64)
                self.assertTrue(accepted["invoice_id"])
                self.assertEqual(
                    db.get_invoice(accepted["invoice_id"], business_a["id"])["status"],
                    "borrador",
                )
                pdf = client.get(
                    f"/p/{token_a}/quotes/{quote_a['id']}/pdf"
                )
                self.assertEqual(pdf.status_code, 200)
                self.assertTrue(pdf.content.startswith(b"%PDF"))
                blocked_pdf = client.get(
                    f"/p/{token_a}/quotes/{quote_b['id']}/pdf"
                )
                self.assertEqual(blocked_pdf.status_code, 404)

    def test_portal_stays_visible_but_cannot_mutate_in_read_only_mode(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, client_ref = self.make_business("Portal consulta")
        quote = self._quote(business["id"], client_ref["id"])
        token = db.get_or_create_portal_token(business["id"], client_ref["id"])
        db.set_subscription(business["id"], "canceled", plan="tranquilidad")

        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                self.assertEqual(client.get(f"/p/{token}").status_code, 200)
                blocked = client.post(
                    f"/p/{token}/quotes/{quote['id']}/accept",
                    follow_redirects=False,
                )

        self.assertEqual(blocked.status_code, 303)
        self.assertIn("ok=readonly", blocked.headers["location"])
        self.assertEqual(
            db.get_quote(quote["id"], business["id"])["status"], "enviado"
        )

    def test_portal_formats_internal_dates_for_people(self):
        from starlette.testclient import TestClient
        from noesis.web import server
        from noesis.web.deps import _human_date

        business, client_ref = self.make_business("Portal fechas")
        quote = self._quote(business["id"], client_ref["id"])
        draft = db.add_invoice(
            client_ref["id"], "Revisión anual", 100,
            business_id=business["id"],
        )
        invoice = db.issue_invoice(draft["id"], business["id"])
        token = db.get_or_create_portal_token(business["id"], client_ref["id"])

        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                page = client.get(f"/p/{token}")

        self.assertEqual(page.status_code, 200)
        self.assertIn(f"Válido hasta el {_human_date(quote['valid_until'])}", page.text)
        self.assertIn(f"Vence el {_human_date(invoice['due_date'])}", page.text)
        self.assertNotIn("T00:00:00", page.text)
        self.assertEqual(_human_date("2026-09-06T00:00:00"), "06/09/2026")

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
            business_a["id"], iban=TEST_IBAN
        )
        token = db.get_or_create_portal_token(
            business_a["id"], client_a["id"]
        )
        db.create_user(
            "cobros-api@example.com",
            auth.hash_password(TEST_PASSWORD),
            business_a["id"],
        )

        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                login = client.post(
                    "/login",
                    data={
                        "email": "cobros-api@example.com",
                        "password": TEST_PASSWORD,
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
                health = client.get("/health").json()
                ready = client.get("/ready").json()
                self.assertEqual(health["status"], "ok")
                self.assertEqual(health["release"], config.RELEASE_ID)
                self.assertEqual(ready["status"], "ready")
                self.assertEqual(ready["release"], config.RELEASE_ID)
                self.assertEqual(ready["schema"], migrations.LATEST_VERSION)
                signup = client.post(
                    "/onboarding/signup",
                    data={
                        "name": "Clima Piloto",
                        "email": "piloto@example.com",
                        "password": TEST_PASSWORD,
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
                with db.get_conn() as conn:
                    legal_event = conn.execute(
                        "SELECT event_data FROM product_events "
                        "WHERE business_id=? AND event_name='legal_accepted'",
                        (created_user["business_id"],),
                    ).fetchone()
                self.assertEqual(
                    json.loads(legal_event["event_data"])["version"],
                    config.LEGAL_DOCUMENT_VERSION,
                )
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
                self.assertIn("/onboarding/preferences/", profile.headers["location"])
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

    def test_public_signup_closes_safely_without_legal_readiness(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        with (
            patch.object(server, "start_scheduler", lambda: None),
            patch.object(config, "IS_PRODUCTION", True),
            patch.object(config, "SECRET_KEY", "x" * 64),
            patch.object(config, "ADMIN_REQUIRE_GOOGLE_OAUTH", False),
            patch.object(config, "PUBLIC_SIGNUP_ENABLED", False),
            patch.object(config, "GOOGLE_OAUTH_CLIENT_ID", "test-client"),
            patch.object(config, "GOOGLE_OAUTH_CLIENT_SECRET", "test-secret"),
        ):
            with TestClient(server.app) as client:
                # Con el alta cerrada no se enseña una pantalla intermedia: se
                # lleva directamente al formulario de solicitud.
                page = client.get("/onboarding", follow_redirects=False)
                self.assertEqual(page.status_code, 303)
                self.assertEqual(page.headers["location"], "/solicitar-acceso")
                form = client.get("/solicitar-acceso")
                self.assertEqual(form.status_code, 200)
                self.assertNotIn("Crear cuenta y configurarla", form.text)
                # Lo que de verdad protege es que el envío siga rechazándose.
                attempt = client.post(
                    "/onboarding/signup",
                    data={
                        "name": "No debe crearse",
                        "email": "cerrado@example.com",
                        "password": TEST_PASSWORD,
                        "sector": "Fontanería",
                        "acepto": "1",
                    },
                )
                self.assertEqual(attempt.status_code, 503)
                self.assertIsNone(db.get_user_by_email("cerrado@example.com"))
                google = client.get(
                    "/auth/google?flow=signup", follow_redirects=False
                )
                self.assertEqual(google.status_code, 303)
                self.assertEqual(google.headers["location"], "/onboarding")

    def test_public_legal_pages_do_not_expose_template_placeholders(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                for route in (
                    "/privacidad", "/aviso-legal", "/terminos",
                    "/encargado-tratamiento",
                ):
                    page = client.get(route)
                    self.assertEqual(page.status_code, 200, route)
                    self.assertNotIn("[Razón social", page.text, route)
                    self.assertNotIn("[NIF", page.text, route)
                    self.assertNotIn("[Dirección", page.text, route)
                    self.assertNotIn("Borrador inicial", page.text, route)

    def test_subscribe_onboarding_configures_operations_before_checkout(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                missing_sector = client.post(
                    "/onboarding/signup",
                    data={
                        "name": "Negocio sin actividad",
                        "email": "sinsector@example.com",
                        "password": TEST_PASSWORD,
                        "sector": "   ",
                        "acepto": "1",
                    },
                    follow_redirects=False,
                )
                self.assertEqual(missing_sector.status_code, 303)
                self.assertIn("error=sector", missing_sector.headers["location"])
                self.assertIsNone(db.get_user_by_email("sinsector@example.com"))

                signup = client.post(
                    "/onboarding/signup",
                    data={
                        "name": "Negocio Completo",
                        "email": "completo@example.com",
                        "password": TEST_PASSWORD,
                        "sector": "Instalación de placas solares",
                        "acepto": "1",
                        "plan": "pro",
                        "billing": "annual",
                        "intent": "subscribe",
                    },
                    follow_redirects=False,
                )
                self.assertEqual(signup.status_code, 303)
                user = db.get_user_by_email("completo@example.com")
                business_id = user["business_id"]
                started = db.get_business(business_id)
                self.assertTrue(started["onboarding_started"])
                self.assertFalse(started["onboarding_done"])
                self.assertEqual(started["onboarding_stage"], 2)
                self.assertEqual(started["onboarding_plan"], "pro")
                self.assertEqual(started["onboarding_billing"], "annual")
                self.assertEqual(
                    db.onboarding_destination(business_id),
                    f"/onboarding/setup/{business_id}",
                )
                with self.assertRaises(ValueError):
                    db.finish_onboarding(business_id, whatsapp_choice="later")
                setup_page = client.get(signup.headers["location"])
                self.assertIn(
                    'value="Instalación de placas solares"', setup_page.text
                )

                profile = client.post(
                    signup.headers["location"],
                    data={
                        "sector": "Instalación de placas solares",
                        "team_size": "2-5",
                        "primary_goal": "facturar",
                        "province": "Valencia",
                        "ai_mode": "enabled",
                        "explanation_level": "detallado",
                    },
                    follow_redirects=False,
                )
                self.assertEqual(profile.status_code, 303)
                self.assertEqual(
                    profile.headers["location"],
                    f"/onboarding/preferences/{business_id}",
                )
                self.assertEqual(
                    db.get_business(business_id)["onboarding_stage"], 3
                )
                self.assertEqual(
                    db.onboarding_destination(business_id),
                    f"/onboarding/preferences/{business_id}",
                )

                preferences_page = client.get(profile.headers["location"])
                self.assertEqual(preferences_page.status_code, 200)
                self.assertIn("onboarding-operations-card", preferences_page.text)
                preferences = client.post(
                    profile.headers["location"],
                    data={
                        "nif": CLIENT_NIF,
                        "address": "Calle Mayor, 1, Valencia",
                        "default_vat": "21",
                        "default_irpf": "15",
                        "default_payment_term_days": "30",
                        "invoice_template": "editorial",
                        "brand_color": "#2e8b74",
                        "document_footer": "Programa financiado por la ayuda piloto.",
                        "quote_terms": "Validez de 30 dias.",
                        "footer_image_width": "75",
                        "footer_image_alignment": "right",
                        "footer_image_scope": "all",
                        "payment_iban": TEST_IBAN,
                        "payment_bizum": "600111222",
                        "payment_note": "Indica el numero de factura.",
                        "payment_reminders_enabled": "1",
                        "payment_reminder_days": "3,10",
                        "brief_manana": "1",
                        "cierre_tarde": "1",
                        "hora_tarde": "20",
                        "resumen_semanal": "1",
                        "aviso_fiscal": "1",
                        "gestoria_name": "Gestoria Piloto",
                        "gestoria_email": "gestoria@example.com",
                        "gestoria_cadence": "mensual",
                    },
                    files={
                        "logo": ("logo.png", TINY_PNG, "image/png"),
                        "footer_image": ("ayuda.png", TINY_PNG, "image/png"),
                    },
                    follow_redirects=False,
                )
                self.assertEqual(preferences.status_code, 303)
                self.assertEqual(
                    preferences.headers["location"],
                    f"/onboarding/whatsapp/{business_id}",
                )

                configured = db.get_business(business_id)
                self.assertEqual(
                    configured["sector"], "Instalación de placas solares"
                )
                self.assertEqual(configured["default_payment_term_days"], 30)
                self.assertEqual(configured["invoice_template"], "editorial")
                self.assertEqual(configured["brand_color"], "#2e8b74")
                self.assertEqual(configured["footer_image_width"], 75)
                self.assertEqual(configured["footer_image_alignment"], "right")
                self.assertEqual(configured["footer_image_scope"], "all")
                self.assertTrue(configured["logo_data"])
                self.assertTrue(configured["footer_image_data"])
                self.assertEqual(configured["payment_reminder_days"], "3,10")
                self.assertEqual(configured["gestoria_cadence"], "mensual")
                self.assertEqual(configured["onboarding_stage"], 4)
                self.assertFalse(configured["onboarding_done"])
                self.assertEqual(
                    db.onboarding_destination(business_id),
                    f"/onboarding/whatsapp/{business_id}",
                )
                reports = db.resolve_whatsapp_reports(
                    configured["whatsapp_reports"]
                )
                self.assertTrue(reports["brief_manana"])
                self.assertEqual(reports["hora_tarde"], 20)

                customer = db.add_client(
                    "Cliente Piloto", address="Calle Cliente, 2",
                    nif="12345678Z", business_id=business_id,
                )
                invoice = db.add_invoice(
                    customer["id"], "Mantenimiento", 100,
                    business_id=business_id,
                )
                issued = db.issue_invoice(invoice["id"], business_id)
                self.assertEqual(
                    issued["due_date"],
                    (date.today() + timedelta(days=30)).isoformat(),
                )

                whatsapp_step = client.get(preferences.headers["location"])
                self.assertEqual(whatsapp_step.status_code, 200)
                self.assertIn("Así queda Negocio Completo", whatsapp_step.text)
                self.assertIn("Negocio · Anual", whatsapp_step.text)
                pending = client.post(
                    f"/onboarding/whatsapp/{business_id}/connect",
                    data={"action": "check"},
                    follow_redirects=False,
                )
                self.assertIn("status=pending", pending.headers["location"])
                self.assertFalse(db.get_business(business_id)["onboarding_done"])
                finished = client.post(
                    f"/onboarding/whatsapp/{business_id}/connect",
                    data={"action": "later"},
                    follow_redirects=False,
                )
                self.assertEqual(finished.status_code, 303)
                self.assertIn("/suscripcion?", finished.headers["location"])
                self.assertIn("status=ready", finished.headers["location"])
                self.assertIn("plan=pro", finished.headers["location"])
                self.assertIn("billing=annual", finished.headers["location"])
                completed = db.get_business(business_id)
                self.assertTrue(completed["onboarding_done"])
                self.assertEqual(completed["onboarding_stage"], 5)
                self.assertEqual(
                    completed["whatsapp_onboarding_choice"], "later"
                )
                payment_page = client.get(finished.headers["location"])
                self.assertEqual(payment_page.status_code, 200)
                self.assertIn("subscription-ready", payment_page.text)


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
            "equipo@example.com", auth.hash_password(TEST_PASSWORD),
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
                        "password": TEST_PASSWORD,
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
            auth.hash_password(TEST_PASSWORD),
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
                        "password": TEST_PASSWORD,
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


class ProfessionalInvoicingHttpTestCase(unittest.TestCase):
    setUp = BackendTestCase.setUp
    tearDown = BackendTestCase.tearDown
    make_business = BackendTestCase.make_business

    def test_invoice_screen_and_professional_endpoints_complete_the_draft_flow(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, client_record = self.make_business("Facturacion HTTP")
        db.update_client(
            client_record["id"], business["id"], email="fiscal@example.com"
        )
        db.create_user(
            "facturacion-http@example.com",
            auth.hash_password(TEST_PASSWORD), business["id"],
        )
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                login = client.post(
                    "/login", data={
                        "email": "facturacion-http@example.com",
                        "password": TEST_PASSWORD,
                    }, follow_redirects=False,
                )
                self.assertEqual(login.status_code, 303)
                page = client.get(f"/b/{business['id']}/facturas")
                self.assertEqual(page.status_code, 200)
                self.assertIn("Series de numeraci", page.text)
                created = client.post(
                    f"/api/{business['id']}/invoices", json={
                        "client_id": client_record["id"],
                        "concept": "Servicio web", "lines": [
                            {"description": "Servicio web", "quantity": 2,
                             "unit_price": 40, "vat_rate": 21},
                            {"description": "Material", "quantity": 1,
                             "unit_price": 10, "vat_rate": 10},
                        ],
                    },
                )
                self.assertEqual(created.status_code, 200, created.text)
                invoice = created.json()
                edited = client.patch(
                    f"/api/{business['id']}/invoices/{invoice['id']}",
                    json={
                        "client_id": client_record["id"],
                        "lines": invoice["lines"], "irpf_rate": 0,
                        "notes": "Revisada antes de emitir.",
                    },
                )
                self.assertEqual(edited.status_code, 200, edited.text)
                series = client.post(
                    f"/api/{business['id']}/invoice-series", json={
                        "code": "OBRAS", "name": "Obras",
                        "document_type": "invoice",
                        "prefix_template": "OBR-{YYYY}/", "padding": 4,
                    },
                )
                self.assertEqual(series.status_code, 201, series.text)
                recurring = client.post(
                    f"/api/{business['id']}/recurring-invoices", json={
                        "client_id": client_record["id"],
                        "name": "Mantenimiento mensual", "cadence": "monthly",
                        "next_run_on": (date.today() + timedelta(days=2)).isoformat(),
                        "lines": [{"description": "Mantenimiento", "quantity": 1,
                                   "unit_price": 50, "vat_rate": 21}],
                        "auto_issue": False,
                    },
                )
                self.assertEqual(recurring.status_code, 201, recurring.text)
                issued = client.post(
                    f"/api/{business['id']}/invoices/{invoice['id']}/send",
                    json={},
                )
                self.assertEqual(issued.status_code, 200, issued.text)
                rectified = client.post(
                    f"/api/{business['id']}/invoices/{invoice['id']}/rectify",
                    json={
                        "invoice_type": "R1", "rectification_type": "I",
                        "reason": "Importe de material incorrecto",
                        "concept": "Corrección de material", "base": -10,
                        "vat_rate": 21, "irpf_rate": 0,
                    },
                )
                self.assertEqual(rectified.status_code, 200, rectified.text)
                correction = rectified.json()
                revised = client.patch(
                    f"/api/{business['id']}/invoices/{correction['id']}/rectification",
                    json={
                        "invoice_type": "R1", "rectification_type": "I",
                        "reason": "Importe de material revisado",
                        "concept": "Corrección final de material", "base": -12,
                        "vat_rate": 21, "irpf_rate": 0,
                    },
                )
                self.assertEqual(revised.status_code, 200, revised.text)
                self.assertEqual(revised.json()["base"], -12)
                invoices = client.get(f"/api/{business['id']}/invoices").json()
                original_row = next(row for row in invoices if row["id"] == invoice["id"])
                self.assertEqual(
                    original_row["pending_rectification_id"], correction["id"]
                )
                delivered = client.post(
                    f"/api/{business['id']}/invoices/{invoice['id']}/deliver",
                    json={"channel": "auto"},
                )
                self.assertEqual(delivered.status_code, 200, delivered.text)
                self.assertEqual(delivered.json()["channel"], "email")
                self.assertTrue(delivered.json()["queued"])
                history = client.get(
                    f"/api/{business['id']}/invoices/{invoice['id']}/history"
                )
                self.assertEqual(history.status_code, 200)
                self.assertEqual(history.json()[0]["event_type"], "emision")


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
        config.VERIFACTU_PRODUCER_NIF = PRODUCER_NIF  # pragma: allowlist secret
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
        self.assertEqual(
            [event["event_type"] for event in db.list_invoice_events(business["id"])],
            ["emision"],
        )

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
        events_after = db.list_invoice_events(business["id"])
        self.assertEqual(events_after[:-1], events_before)
        self.assertEqual(events_after[-1]["event_type"], "cobro")

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
            "3C464DAF61ACB827C65FDA19F352A4E3BDC2C640E9E9FC4CC058073F38F12F60",  # pragma: allowlist secret
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
                "3C464DAF61ACB827C65FDA19F352A4E3BDC2C640E9E9FC4CC058073F38F12F60"  # pragma: allowlist secret
            ),
            generated_at="2024-01-01T19:20:35+01:00",
        )
        self.assertEqual(
            digest,
            "F7B94CFD8924EDFF273501B01EE5153E4CE8F259766F88CF6ACB8935802A2B97",  # pragma: allowlist secret
        )

    def test_cancellation_hash_uses_the_official_fields_and_order(self):
        payload = verifactu.cancellation_hash_input(
            issuer_nif=ISSUER_NIF, invoice_number="2026/0001",
            issue_date="20-07-2026", previous_hash="ABC123",
            generated_at="2026-07-20T12:30:00+02:00",
        )
        self.assertEqual(
            payload,
            f"IDEmisorFacturaAnulada={ISSUER_NIF}&"
            "NumSerieFacturaAnulada=2026/0001&"
            "FechaExpedicionFacturaAnulada=20-07-2026&"
            "Huella=ABC123&"
            "FechaHoraHusoGenRegistro=2026-07-20T12:30:00+02:00",
        )
        self.assertEqual(
            verifactu.cancellation_record_hash(
                issuer_nif=ISSUER_NIF, invoice_number="2026/0001",
                issue_date="20-07-2026", previous_hash="ABC123",
                generated_at="2026-07-20T12:30:00+02:00",
            ),
            hashlib.sha256(payload.encode("utf-8")).hexdigest().upper(),
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

    def test_inactive_subscription_never_stops_fiscal_remittance(self):
        business, client = self._enabled_business("Verifactu Suscripcion")
        invoice = self._issue(business, client)
        db.set_subscription(business["id"], "canceled", plan="tranquilidad")
        result = verifactu_client.SubmissionResult(
            status="aceptado",
            csv="CSV-SIN-SUSCRIPCION",
            wait_seconds=0,
            error_code=None,
            error_description=None,
            global_status="Correcto",
            raw_response="<Respuesta>correcta</Respuesta>",
        )
        with (
            patch.object(verifactu_client, "is_enabled", return_value=True),
            patch.object(
                verifactu_client, "submit_records", return_value=result
            ) as submit,
        ):
            self.assertEqual(scheduler.process_verifactu_outbox(), 1)

        submit.assert_called_once()
        queued = db.get_verifactu_outbox(invoice["id"], business["id"])
        self.assertEqual(queued["status"], "aceptado")
        self.assertEqual(queued["aeat_csv"], "CSV-SIN-SUSCRIPCION")

    def test_tampered_chain_is_never_sent_to_aeat(self):
        business, client = self._enabled_business("Verifactu Bloqueo Seguro")
        invoice = self._issue(business, client)
        record = db.get_invoice_record(invoice["id"], business["id"])
        with db.get_conn() as conn:
            conn.execute("DROP TRIGGER invoice_records_append_only_update")
            conn.execute(
                "UPDATE invoice_records SET invoice_total=999 WHERE id=?",
                (record["id"],),
            )

        with (
            patch.object(verifactu_client, "is_enabled", return_value=True),
            patch.object(verifactu_client, "submit_records") as submit,
        ):
            self.assertEqual(scheduler.process_verifactu_outbox(), 0)

        submit.assert_not_called()
        queued = db.get_verifactu_outbox(invoice["id"], business["id"])
        self.assertEqual(queued["status"], "pendiente")
        self.assertIn("integridad", queued["last_error"])
        self.assertEqual(
            [event["event_type"] for event in db.list_invoice_events(business["id"])],
            ["alta", "anomalia"],
        )

    def test_new_record_requires_a_valid_existing_chain(self):
        business, client = self._enabled_business("Verifactu Cadena Previa")
        first = self._issue(business, client)
        record = db.get_invoice_record(first["id"], business["id"])
        with db.get_conn() as conn:
            conn.execute("DROP TRIGGER invoice_records_append_only_update")
            conn.execute(
                "UPDATE invoice_records SET invoice_total=999 WHERE id=?",
                (record["id"],),
            )
        draft = db.add_invoice(
            client["id"], "Segundo servicio", 200,
            business_id=business["id"],
        )

        with self.assertRaisesRegex(ValueError, "cadena Veri\\*Factu"):
            db.issue_invoice(draft["id"], business["id"])
        untouched = db.get_invoice(draft["id"], business["id"])
        self.assertEqual(untouched["status"], "borrador")
        self.assertIsNone(untouched["number"])

    def test_fiscal_identity_is_locked_after_first_verifactu_record(self):
        business, client = self._enabled_business("Verifactu Identidad")
        self._issue(business, client)

        with self.assertRaisesRegex(ValueError, "NIF no puede cambiarse"):
            db.update_fiscal(business["id"], nif=ALTERNATIVE_NIF)
        self.assertEqual(db.get_business(business["id"])["nif"], ISSUER_NIF)

    def test_clock_rollback_blocks_a_new_fiscal_record(self):
        business, client = self._enabled_business("Verifactu Reloj")
        self._issue(business, client)
        draft = db.add_invoice(
            client["id"], "Servicio posterior", 50,
            business_id=business["id"],
        )

        with (
            patch.object(
                verifactu,
                "generated_at_with_timezone",
                return_value="2020-01-01T00:00:00+01:00",
            ),
            self.assertRaisesRegex(ValueError, "reloj del sistema"),
        ):
            db.issue_invoice(draft["id"], business["id"])
        self.assertEqual(
            db.get_invoice(draft["id"], business["id"])["status"], "borrador"
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

    def test_soap_fault_is_retryable_and_duplicate_acceptance_is_idempotent(self):
        fault = b"""<?xml version="1.0"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
 <soapenv:Body><soapenv:Fault><faultcode>soapenv:Server</faultcode>
 <faultstring>Servicio temporalmente no disponible</faultstring>
 </soapenv:Fault></soapenv:Body></soapenv:Envelope>"""
        with self.assertRaises(verifactu_client.VerifactuTransportError):
            verifactu_client.parse_response(fault)

        duplicate = b"""<?xml version="1.0"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
 <soapenv:Body><RespuestaRegFactuSistemaFacturacion>
  <EstadoEnvio>Incorrecto</EstadoEnvio>
  <RespuestaLinea><EstadoRegistro>Incorrecto</EstadoRegistro>
   <CodigoErrorRegistro>3000</CodigoErrorRegistro>
   <DescripcionErrorRegistro>Registro duplicado</DescripcionErrorRegistro>
   <RegistroDuplicado><EstadoRegistroDuplicado>Correcta</EstadoRegistroDuplicado>
   </RegistroDuplicado>
  </RespuestaLinea>
 </RespuestaRegFactuSistemaFacturacion></soapenv:Body>
</soapenv:Envelope>"""
        result = verifactu_client.parse_response(duplicate)
        self.assertEqual(result.status, "aceptado")
        self.assertEqual(result.error_code, "3000")

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

    def test_mixed_vat_and_simplified_invoice_generate_the_expected_aeat_xml(self):
        business, client = self._enabled_business("Verifactu IVA Mixto")
        mixed = db.add_invoice(
            client["id"], "Servicios combinados", None,
            business_id=business["id"],
            lines=[
                {"description": "Servicio", "quantity": 1,
                 "unit_price": 100, "vat_rate": 21},
                {"description": "Material", "quantity": 2,
                 "unit_price": 25, "vat_rate": 10},
            ],
            operation_date=date.today().isoformat(),
        )
        mixed = db.issue_invoice(mixed["id"], business["id"])
        anonymous = db.add_client("Cliente mostrador", business_id=business["id"])
        simplified = db.issue_invoice(
            db.add_invoice(
                anonymous["id"], "Servicio menor", 50,
                invoice_type="F2", business_id=business["id"],
            )["id"],
            business["id"],
        )

        xml = db.export_verifactu_xml(business["id"])
        root = ET.fromstring(xml)
        ns = {"sum": verifactu.NS_LR, "sum1": verifactu.NS_INFO}
        altas = root.findall("sum:RegistroFactura/sum1:RegistroAlta", ns)
        mixed_xml = next(
            item for item in altas
            if item.find("sum1:IDFactura/sum1:NumSerieFactura", ns).text
            == mixed["number"]
        )
        self.assertEqual(
            len(mixed_xml.findall("sum1:Desglose/sum1:DetalleDesglose", ns)),
            2,
        )
        self.assertEqual(
            mixed_xml.find("sum1:FechaOperacion", ns).text,
            date.today().strftime("%d-%m-%Y"),
        )
        simplified_xml = next(
            item for item in altas
            if item.find("sum1:IDFactura/sum1:NumSerieFactura", ns).text
            == simplified["number"]
        )
        self.assertEqual(simplified_xml.find("sum1:TipoFactura", ns).text, "F2")
        self.assertIsNone(simplified_xml.find("sum1:Destinatarios", ns))

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

    def test_accepted_record_can_be_cancelled_without_altering_the_invoice(self):
        business, client = self._enabled_business("Verifactu Anulacion")
        original = self._issue(business, client, "Registro erróneo", 100)
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE verifactu_outbox SET status='aceptado' "
                "WHERE invoice_id=? AND business_id=?",
                (original["id"], business["id"]),
            )
        cancellation = db.create_invoice_cancellation_record(
            original["id"], business["id"],
            reason="La operación nunca llegó a realizarse.",
        )
        self.assertEqual(cancellation["record_type"], "anulacion")
        self.assertEqual(cancellation["invoice_number"], original["number"])
        self.assertTrue(db.verify_invoice_record_chain(business["id"])["valid"])
        self.assertEqual(
            db.get_invoice(original["id"], business["id"])["total"],
            original["total"],
        )
        with self.assertRaises(db.IntegrityError):
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE invoice_cancellation_records SET reason='cambio' "
                    "WHERE id=?", (cancellation["id"],),
                )
        with self.assertRaisesRegex(ValueError, "anulado"):
            db.create_rectifying_invoice(
                original["id"], business["id"], concept="Corrección",
                base=-10, reason="Ya anulado", invoice_type="R1",
            )

        xml = db.export_verifactu_xml(business["id"])
        root = ET.fromstring(xml)
        ns = {"sum": verifactu.NS_LR, "sum1": verifactu.NS_INFO}
        node = root.find("sum:RegistroFactura/sum1:RegistroAnulacion", ns)
        self.assertIsNotNone(node)
        self.assertEqual(
            node.find(
                "sum1:IDFactura/sum1:NumSerieFacturaAnulada", ns
            ).text,
            original["number"],
        )

        following = self._issue(business, client, "Trabajo posterior", 50)
        following_record = db.get_invoice_record(following["id"], business["id"])
        self.assertEqual(following_record["previous_hash"], cancellation["record_hash"])
        self.assertTrue(db.verify_invoice_record_chain(business["id"])["valid"])

    def test_cancellation_uses_the_durable_aeat_outbox(self):
        business, client = self._enabled_business("Verifactu Cola Anulacion")
        invoice = self._issue(business, client)
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE verifactu_outbox SET status='aceptado' "
                "WHERE invoice_id=? AND business_id=?",
                (invoice["id"], business["id"]),
            )
        db.create_invoice_cancellation_record(
            invoice["id"], business["id"], reason="Factura emitida por error.",
        )
        result = verifactu_client.SubmissionResult(
            status="aceptado", csv="CSV-ANULACION-1", wait_seconds=0,
            error_code=None, error_description=None, global_status="Correcto",
            raw_response="<Respuesta>anulada</Respuesta>",
        )
        with (
            patch.object(verifactu_client, "is_enabled", return_value=True),
            patch.object(
                verifactu_client, "submit_records", return_value=result
            ) as submit,
        ):
            self.assertEqual(scheduler.process_verifactu_outbox(), 1)
        self.assertEqual(submit.call_args.args[1][0]["record_type"], "anulacion")
        queued = db.get_verifactu_cancellation_outbox(
            invoice["id"], business["id"]
        )
        self.assertEqual(queued["status"], "aceptado")
        self.assertEqual(queued["aeat_csv"], "CSV-ANULACION-1")

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

    def test_rectifying_pdf_handles_long_legal_description(self):
        from noesis.web.invoice_pdf import build_invoice_pdf

        business, client = self._enabled_business("Verifactu PDF Rectificativa")
        original = self._issue(business, client)
        rectifying = db.create_rectifying_invoice(
            original["id"],
            business["id"],
            concept="Corrección detallada de materiales y horas " * 8,
            base=-25,
            vat_rate=21,
            irpf_rate=0,
            invoice_type="R1",
            reason="Error material detectado tras la emisión.",
        )
        issued = db.issue_invoice(rectifying["id"], business["id"])

        pdf = build_invoice_pdf(issued["id"], business["id"])
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 3500)

    def test_export_endpoint_is_tenant_scoped(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, client_record = self._enabled_business("Verifactu HTTP")
        other_business, _ = self._enabled_business("Verifactu HTTP Ajeno")
        self._issue(business, client_record)
        user = db.create_user(
            "verifactu@example.com",
            auth.hash_password(TEST_PASSWORD),
            business["id"],
        )
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                login = client.post(
                    "/login",
                    data={
                        "email": user["email"],
                        "password": TEST_PASSWORD,
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
                         return_value=TINY_JPEG),
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
            patch.object(whatsapp, "_download_media", return_value=TINY_PNG),
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

    def test_sale_ticket_reuses_client_requires_issue_confirmation_and_feeds_numbers(self):
        business, _ = self._connected_business("Ticket WhatsApp")
        habitual = db.add_client(
            "Marta López", phone="611223344", business_id=business["id"]
        )
        replies = []
        with patch.object(
            whatsapp, "send",
            side_effect=lambda phone, text, **kw: replies.append(text),
        ):
            whatsapp.handle_inbound({
                "from": "34600111222", "id": "wamid-ticket-1",
                "text": "ticket de venta a Marta por reparación 121 euros",
            })
            invoice = db.list_invoices(business["id"])[0]
            self.assertEqual(invoice["client_id"], habitual["id"])
            self.assertEqual(invoice["invoice_type"], "F2")
            self.assertEqual(invoice["base"], 100.0)
            self.assertEqual(invoice["total"], 121.0)
            self.assertEqual(invoice["status"], "borrador")

            whatsapp.handle_inbound({
                "from": "34600111222", "id": "wamid-ticket-2",
                "text": f"emitir factura {invoice['id']}",
            })
            self.assertEqual(
                db.get_invoice(invoice["id"], business["id"])["status"],
                "borrador",
            )
            self.assertIn("¿Confirmas?", replies[-1])

            whatsapp.handle_inbound({
                "from": "34600111222", "id": "wamid-ticket-3", "text": "sí",
            })

        issued = db.get_invoice(invoice["id"], business["id"])
        self.assertEqual(issued["status"], "enviada")
        self.assertTrue(issued["number"].startswith("T"))
        self.assertIn("PDF preparado", replies[-1])
        self.assertEqual(db.month_billing(business_id=business["id"])["invoiced"], 121.0)
        today = date.today().isoformat()
        self.assertEqual(
            [item["id"] for item in db.gestoria_invoices_in(
                business["id"], today, today
            )],
            [issued["id"]],
        )
        quarter = (date.today().month - 1) // 3 + 1
        fiscal = db.tax_quarter(date.today().year, quarter, business["id"])
        self.assertEqual(fiscal["n_facturas"], 1)
        self.assertEqual(fiscal["iva_repercutido"], 21.0)
        self.assertEqual(
            next(c for c in db.client_stats(business["id"])
                 if c["id"] == habitual["id"])["facturado"],
            121.0,
        )

    def test_confirmed_whatsapp_invoice_delivery_queues_pdf_email_once(self):
        business, client = self._connected_business("Entrega WhatsApp")
        db.update_client(
            client["id"], business["id"], email="cliente@example.com"
        )
        invoice = db.add_invoice(
            client["id"], "Revisión anual", 100, business_id=business["id"]
        )
        replies = []
        with patch.object(
            whatsapp, "send",
            side_effect=lambda phone, text, **kw: replies.append(text),
        ):
            whatsapp.handle_inbound({
                "from": "34600111222", "id": "wamid-deliver-1",
                "text": f"emitir y enviar factura {invoice['id']}",
            })
            self.assertEqual(db.list_email_messages(business["id"]), [])
            whatsapp.handle_inbound({
                "from": "34600111222", "id": "wamid-deliver-2", "text": "sí",
            })
        messages = db.list_email_messages(business["id"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["entity_type"], "invoice")
        self.assertEqual(messages[0]["entity_id"], invoice["id"])
        self.assertIn("entrega preparada", replies[-1])

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

    def test_whatsapp_pdf_caption_links_the_right_project_and_client(self):
        from fpdf import FPDF
        from noesis.documents import repo as docrepo

        business, client = self._connected_business("PDF contextual")
        project = db.add_project(
            "Instalación Hotel Mar", 8000, client_id=client["id"],
            business_id=business["id"],
        )
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("helvetica", size=12)
        pdf.multi_cell(0, 8, "TICKET SIMPLIFICADA\nTOTAL 35,20 EUR")
        replies = []
        with (
            patch.object(whatsapp, "_download_media",
                         return_value=bytes(pdf.output())),
            patch.object(whatsapp, "send",
                         side_effect=lambda phone, text, **kw: replies.append(text)),
        ):
            whatsapp.handle_inbound({
                "from": "34600111222", "id": "wamid-pdf-context-1",
                "media_document_id": "media-context",
                "media_document_mime": "application/pdf",
                "media_document_filename": "ticket-material.pdf",
                "caption": "Material de Instalación Hotel Mar",
            })
        document = docrepo.list_for_business(business["id"])[0]
        self.assertEqual(document["project_id"], project["id"])
        self.assertEqual(document["client_id"], client["id"])
        self.assertIn("Lo he asociado a Instalación Hotel Mar", replies[-1])

    def test_pdf_received_invoice_is_classified_and_confirmed_by_whatsapp(self):
        business, _ = self._connected_business("Factura PDF")
        replies = []
        classification = {
            "kind": "factura_recibida", "confidence": 94,
            "reason": "El negocio figura como receptor.", "method": "ia",
        }
        draft = {
            "number": "P-44", "issued_on": "2026-07-01", "due_on": None,
            "supplier": "Ferretería Sol", "supplier_nif": SUPPLIER_NIF,
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
        ten_days_ago = (datetime.now() - timedelta(days=10)).isoformat(
            timespec="seconds"
        )
        with patch.object(db, "_now", return_value=ten_days_ago):
            db.issue_invoice(invoice["id"], business["id"])
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

    def test_professional_account_only_sees_explicitly_invited_businesses(self):
        first, _ = self.make_business("Gestoría Cartera Uno")
        second, _ = self.make_business("Gestoría Cartera Dos")
        foreign, _ = self.make_business("Gestoría Fuera")
        account = db.create_gestoria_account(
            "equipo@gestoria.com", auth.hash_password(TEST_PASSWORD),
            "Gestoría de prueba",
        )
        for business in (first, second):
            raw = f"invite-{business['id']}"
            invitation = db.create_gestoria_invitation(
                business["id"], account["email"], auth.hash_token(raw),
                (datetime.now() + timedelta(days=1)).isoformat(timespec="seconds"),
            )
            self.assertIsNotNone(
                db.accept_gestoria_invitation(invitation["id"], account["id"])
            )
        self.assertEqual(
            {item["id"] for item in db.list_gestoria_businesses(account["id"])},
            {first["id"], second["id"]},
        )
        self.assertFalse(db.gestoria_account_can_access(
            account["id"], foreign["id"]
        ))
        self.assertTrue(db.revoke_gestoria_access(first["id"], account["id"]))
        self.assertFalse(db.gestoria_account_can_access(
            account["id"], first["id"]
        ))

    def test_fiscal_profile_is_explicit_and_isolated_per_business(self):
        first, _ = self.make_business("Perfil fiscal propio")
        foreign, _ = self.make_business("Perfil fiscal ajeno")
        account = db.create_gestoria_account(
            "fiscal@gestoria.com", auth.hash_password(TEST_PASSWORD),
            "Gestoría Fiscal",
        )
        invitation = db.create_gestoria_invitation(
            first["id"], account["email"], auth.hash_token("fiscal-profile"),
            (datetime.now() + timedelta(days=1)).isoformat(timespec="seconds"),
        )
        db.accept_gestoria_invitation(invitation["id"], account["id"])
        self.assertEqual(
            db.get_gestoria_fiscal_profile(first["id"])["taxpayer_type"],
            "sin_configurar",
        )
        saved = db.update_gestoria_fiscal_profile(
            first["id"], account["id"], taxpayer_type="autonomo",
            income_tax_regime="estimacion_directa", vat_regime="general",
            filing_cadence="trimestral", obligations=["303", "130", "347"],
            notes="Estimación directa simplificada.",
        )
        self.assertEqual(saved["obligations"], ["130", "303", "347"])
        with self.assertRaises(ValueError):
            db.update_gestoria_fiscal_profile(
                foreign["id"], account["id"], taxpayer_type="sociedad",
                income_tax_regime="sociedades", vat_regime="general",
                filing_cadence="trimestral", obligations=["200"],
            )

    def test_workspace_includes_received_invoice_in_tax_preview(self):
        from noesis import gestoria_workspace

        business, client = self.make_business("Fiscal completo")
        invoice = db.add_invoice(
            client["id"], "Servicio", 100, business_id=business["id"]
        )
        db.issue_invoice(invoice["id"], business["id"])
        supplier = db.add_supplier(
            "Proveedor Fiscal", nif="B12345678", business_id=business["id"]
        )
        today = date.today()
        db.add_received_invoice(
            121, supplier_id=supplier["id"], base=100, vat_rate=21,
            vat_amount=21, issued_on=today.isoformat(),
            business_id=business["id"],
        )
        quarter = (today.month - 1) // 3 + 1
        data = gestoria_workspace.workspace(
            business["id"], year=today.year, quarter=quarter
        )
        self.assertEqual(data["period"]["output_vat"], 21.0)
        self.assertEqual(data["period"]["input_vat"], 21.0)
        self.assertEqual(data["period"]["vat_result"], 0.0)
        fiscal = db.tax_quarter(today.year, quarter, business["id"])
        self.assertEqual(fiscal["n_facturas_recibidas"], 1)
        self.assertEqual(fiscal["iva_soportado"], 21.0)

    def test_owner_document_archive_reuses_periods_and_private_preview(self):
        from starlette.testclient import TestClient
        from noesis.documents import service as docservice
        from noesis.web import server

        business, _ = self.make_business("Archivo titular")
        foreign, _ = self.make_business("Archivo ajeno")
        own_doc = docservice.upload(
            business["id"], "ticket-propio.jpg", TINY_JPEG,
            kind="ticket", run_ocr=False,
        )
        foreign_doc = docservice.upload(
            foreign["id"], "ticket-ajeno.jpg", TINY_JPEG,
            kind="ticket", run_ocr=False,
        )
        db.create_user(
            "archivo@example.com", auth.hash_password(TEST_PASSWORD), business["id"]
        )
        today = date.today()
        quarter = (today.month - 1) // 3 + 1
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                login = client.post(
                    "/login",
                    data={"email": "archivo@example.com", "password": TEST_PASSWORD},
                    follow_redirects=False,
                )
                self.assertEqual(login.status_code, 303)
                page = client.get(f"/b/{business['id']}/documentos")
                self.assertEqual(page.status_code, 200)
                self.assertIn("Documentos por período", page.text)
                archive = client.get(
                    f"/api/{business['id']}/document-archive"
                    f"?year={today.year}&quarter={quarter}&view=tickets"
                )
                self.assertEqual(archive.status_code, 200, archive.text)
                payload = archive.json()
                self.assertEqual(payload["document_counts"]["tickets"], 1)
                self.assertEqual(payload["documents"][0]["id"], own_doc["id"])
                preview = client.get(
                    f"/api/{business['id']}/documents/{own_doc['id']}/preview"
                )
                self.assertEqual(preview.status_code, 200)
                self.assertIn("no-store", preview.headers["cache-control"])
                blocked = client.get(
                    f"/api/{foreign['id']}/documents/{foreign_doc['id']}/preview"
                )
                self.assertEqual(blocked.status_code, 403)

    def test_professional_portfolio_accepts_two_clients_without_mixing_them(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        first, _ = self.make_business("Cartera Web Uno")
        second, _ = self.make_business("Cartera Web Dos")
        tokens = []
        for business in (first, second):
            raw = f"token-web-{business['id']}"
            db.create_gestoria_invitation(
                business["id"], "cartera@gestoria.com", auth.hash_token(raw),
                (datetime.now() + timedelta(days=1)).isoformat(timespec="seconds"),
            )
            tokens.append(raw)
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                created = client.post(
                    f"/gestoria/accept/{tokens[0]}",
                    data={"firm_name": "Gestoría Web", "password": TEST_PASSWORD},
                    follow_redirects=False,
                )
                self.assertEqual(created.status_code, 303)
                accepted = client.post(
                    f"/gestoria/accept/{tokens[1]}",
                    data={"password": TEST_PASSWORD}, follow_redirects=False,
                )
                self.assertEqual(accepted.status_code, 303)
                portfolio = client.get("/gestoria")
                self.assertEqual(portfolio.status_code, 200)
                self.assertIn("Cartera Web Uno", portfolio.text)
                self.assertIn("Cartera Web Dos", portfolio.text)

    def test_professional_client_workspace_previews_only_own_documents(self):
        from starlette.testclient import TestClient
        from noesis.documents import service as docservice
        from noesis.web import server

        business, _ = self.make_business("Gestoría documentos")
        foreign, _ = self.make_business("Gestoría documento ajeno")
        own_doc = docservice.upload(
            business["id"], "ticket-propio.jpg", TINY_JPEG,
            kind="ticket", run_ocr=False,
        )
        foreign_doc = docservice.upload(
            foreign["id"], "ticket-ajeno.jpg", TINY_JPEG,
            kind="ticket", run_ocr=False,
        )
        raw = "gestoria-doc-preview"
        db.create_gestoria_invitation(
            business["id"], "docs@gestoria.com", auth.hash_token(raw),
            (datetime.now() + timedelta(days=1)).isoformat(timespec="seconds"),
        )
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                accepted = client.post(
                    f"/gestoria/accept/{raw}",
                    data={"firm_name": "Gestoría Docs", "password": TEST_PASSWORD},
                    follow_redirects=False,
                )
                self.assertEqual(accepted.status_code, 303)
                page = client.get(
                    f"/gestoria/cliente/{business['id']}?section=documentos"
                    f"&view=tickets&doc={own_doc['id']}"
                )
                self.assertEqual(page.status_code, 200)
                self.assertIn("ticket-propio.jpg", page.text)
                self.assertIn("Documentos y movimientos", page.text)
                self.assertNotIn("Primera lectura fiscal", page.text)
                fiscal_page = client.get(
                    f"/gestoria/cliente/{business['id']}?section=impuestos"
                )
                self.assertEqual(fiscal_page.status_code, 200)
                self.assertIn("Primera lectura fiscal", fiscal_page.text)
                self.assertNotIn("Documentos y movimientos", fiscal_page.text)
                saved_profile = client.post(
                    f"/gestoria/cliente/{business['id']}/perfil-fiscal",
                    data={"year": "2026", "quarter": "2"},
                    follow_redirects=False,
                )
                self.assertEqual(saved_profile.status_code, 303)
                self.assertIn(
                    "section=impuestos&year=2026&quarter=2",
                    saved_profile.headers["location"],
                )
                requested = client.post(
                    f"/gestoria/cliente/{business['id']}/solicitud",
                    data={
                        "message": "Falta el justificante.",
                        "year": "2026", "quarter": "2",
                    },
                    follow_redirects=False,
                )
                self.assertEqual(requested.status_code, 303)
                self.assertIn(
                    "section=solicitudes&year=2026&quarter=2",
                    requested.headers["location"],
                )
                preview = client.get(
                    f"/gestoria/cliente/{business['id']}/documento/{own_doc['id']}/preview"
                )
                self.assertEqual(preview.status_code, 200)
                denied = client.get(
                    f"/gestoria/cliente/{foreign['id']}/documento/{foreign_doc['id']}/preview"
                )
                self.assertEqual(denied.status_code, 403)

    def test_document_context_never_accepts_foreign_client_or_project(self):
        from noesis.documents import repo as docrepo, service as docservice

        business, client = self.make_business("Contexto propio")
        foreign, foreign_client = self.make_business("Contexto ajeno")
        project = db.add_project(
            "Reforma Avenida", 5000, client_id=client["id"],
            business_id=business["id"],
        )
        foreign_project = db.add_project(
            "Reforma Avenida", 3000, client_id=foreign_client["id"],
            business_id=foreign["id"],
        )
        foreign_invoice = db.add_invoice(
            foreign_client["id"], "Trabajo ajeno", 100,
            business_id=foreign["id"],
        )
        with self.assertRaises(docservice.UploadError):
            docservice.upload(
                business["id"], "factura-ajena.jpg", TINY_JPEG,
                invoice_id=foreign_invoice["id"], run_ocr=False,
            )
        document = docservice.upload(
            business["id"], "ticket.jpg", TINY_JPEG,
            run_ocr=False,
        )
        associated = docservice.associate_context(
            business["id"], document["id"], "Para Reforma Avenida"
        )["document"]
        self.assertEqual(associated["project_id"], project["id"])
        self.assertEqual(associated["client_id"], client["id"])
        with self.assertRaises(ValueError):
            docrepo.set_context(
                document["id"], business["id"],
                client_id=foreign_client["id"],
            )
        with self.assertRaises(ValueError):
            docrepo.set_context(
                document["id"], business["id"],
                project_id=foreign_project["id"],
            )

    def test_digital_pdf_is_read_locally_with_bounded_amount_detection(self):
        from fpdf import FPDF
        from noesis.documents import service as docservice

        business, _ = self.make_business("PDF local")
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("helvetica", size=12)
        pdf.multi_cell(0, 8, "TICKET SIMPLIFICADA\nMaterial eléctrico\nTOTAL 48,40 EUR")
        document = docservice.upload(
            business["id"], "compra.pdf", bytes(pdf.output()),
            run_ocr=True, auto_classify=True,
        )
        self.assertIn("TOTAL 48,40", document["ocr_text"])
        self.assertEqual(document["ocr_amount"], 48.4)
        self.assertEqual(document["classification"]["kind"], "ticket")

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
            business["id"], "ticket.jpg", TINY_JPEG,
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
            auth.hash_password(TEST_PASSWORD),
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
                    "password": TEST_PASSWORD,
                }, follow_redirects=False)
                self.assertEqual(login.status_code, 303)
                sent = client.post(
                    f"/b/{business['id']}/gestoria/send-now",
                    follow_redirects=False,
                )
                self.assertEqual(sent.status_code, 303)
                self.assertIn("gestoria", sent.headers["location"])

    def test_scheduler_notifies_once_per_period(self):
        business, _ = self.make_business("Gestoría Job")
        db.update_gestoria_settings(
            business["id"], email="g@gestoria.com", cadence="mensual"
        )
        off_business, _ = self.make_business("Gestoría Off")
        first_of_month = datetime(2026, 7, 2, 9, 30)
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
        emails = db.list_email_messages(business["id"])
        self.assertEqual([item["to_email"] for item in emails], ["g@gestoria.com"])

    def test_email_outbox_is_idempotent_retries_and_is_rgpd_safe(self):
        from noesis.adapters import email as email_adapter

        business, _ = self.make_business("Correo durable")
        first = db.enqueue_email_message(
            business_id=business["id"], to_email="cliente@example.com",
            subject="Tu factura", text_body="Contenido",
            idempotency_key=f"test:{business['id']}:factura-1",
        )
        duplicate = db.enqueue_email_message(
            business_id=business["id"], to_email="cliente@example.com",
            subject="Tu factura", text_body="Contenido",
            idempotency_key=f"test:{business['id']}:factura-1",
        )
        self.assertEqual(first["id"], duplicate["id"])
        self.assertEqual(len(db.list_email_messages(business["id"])), 1)

        with (
            patch.object(email_adapter, "available", return_value=True),
            patch.object(email_adapter, "send_email", return_value=False),
        ):
            self.assertEqual(scheduler.process_email_outbox(limit=1), 0)
        retrying = db.get_email_message(first["id"])
        self.assertEqual(retrying["status"], "retrying")
        self.assertEqual(retrying["attempts"], 1)

        with db.get_conn() as conn:
            conn.execute(
                "UPDATE email_outbox SET next_attempt_at=? WHERE id=?",
                ("2000-01-01T00:00:00", first["id"]),
            )
        with (
            patch.object(email_adapter, "available", return_value=True),
            patch.object(email_adapter, "send_email", return_value=True) as send,
        ):
            self.assertEqual(scheduler.process_email_outbox(limit=1), 1)
        self.assertEqual(db.get_email_message(first["id"])["status"], "sent")
        self.assertEqual(send.call_count, 1)
        self.assertEqual(len(db.export_business_data(business["id"])["email_outbox"]), 1)

        disposable, _ = self.make_business("Correo borrable")
        db.enqueue_email_message(
            business_id=disposable["id"], to_email="otro@example.com",
            subject="Aviso", text_body="Contenido",
        )
        self.assertTrue(db.delete_business_cascade(disposable["id"]))
        self.assertEqual(db.list_email_messages(disposable["id"]), [])

    def test_invoice_email_is_sent_with_a_generated_pdf_and_audited(self):
        from noesis.adapters import email as email_adapter

        business, client = self.make_business("Correo con factura")
        invoice = db.issue_invoice(
            db.add_invoice(
                client["id"], "Servicio facturado", 100,
                business_id=business["id"],
            )["id"],
            business["id"],
        )
        db.enqueue_email_message(
            business_id=business["id"], to_email="cliente@example.com",
            subject="Factura", text_body="Adjunta",
            idempotency_key=f"invoice-email:{invoice['id']}",
            entity_type="invoice", entity_id=invoice["id"],
        )
        with (
            patch.object(email_adapter, "available", return_value=True),
            patch.object(email_adapter, "send_email", return_value=True) as send,
        ):
            self.assertEqual(scheduler.process_email_outbox(limit=1), 1)
        attachments = send.call_args.kwargs["attachments"]
        self.assertEqual(len(attachments), 1)
        self.assertTrue(attachments[0][0].endswith(".pdf"))
        self.assertTrue(attachments[0][1].startswith(b"%PDF"))
        self.assertEqual(attachments[0][2:], ("application", "pdf"))
        self.assertEqual(
            [event["event_type"] for event in db.list_invoice_events(
                business["id"], invoice_id=invoice["id"]
            )],
            ["emision", "entrega_enviada"],
        )


class AdminCommandCenterTestCase(unittest.TestCase):
    setUp = BackendTestCase.setUp
    tearDown = BackendTestCase.tearDown
    make_business = BackendTestCase.make_business

    def test_admin_records_observed_cost_without_overwriting_history(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, _ = self.make_business("Dirección CFO")
        admin = db.create_user(
            "cfo-admin@example.com", auth.hash_password(TEST_PASSWORD), business["id"]
        )
        period = date.today().strftime("%Y-%m")
        with (
            patch.object(config, "ADMIN_EMAIL", "cfo-admin@example.com"),
            patch.object(config, "ADMIN_REQUIRE_GOOGLE_OAUTH", False),
            patch.object(server, "start_scheduler", lambda: None),
        ):
            with TestClient(server.app) as client:
                client.post("/login", data={
                    "email": "cfo-admin@example.com", "password": TEST_PASSWORD,
                })
                saved = client.post(
                    "/admin/costes",
                    data={
                        "period": period, "category": "hosting",
                        "amount_eur": "24.50", "source": "actual",
                        "note": "Factura Railway agosto",
                    },
                    follow_redirects=False,
                )
                self.assertEqual(saved.status_code, 303)
                page = client.get("/admin")
                self.assertEqual(page.status_code, 200, page.text)
                self.assertIn("Factura Railway agosto", page.text)
                self.assertIn("Margen observado", page.text)
        ledger = db.platform_cost_summary(period)
        self.assertEqual(ledger["observed_total"], 24.5)
        event = next(
            item for item in db.list_security_events()
            if item["event_type"] == "admin.platform_cost_recorded"
        )
        self.assertEqual(event["actor_user_id"], admin["id"])

    def test_owner_opens_and_revokes_scoped_support_window(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, _ = self.make_business("Cuenta con soporte")
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE businesses SET owner_email=? WHERE id=?",
                ("support-owner@example.com", business["id"]),
            )
        owner = db.create_user(
            "support-owner@example.com", auth.hash_password(TEST_PASSWORD),
            business["id"],
        )
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                client.post("/login", data={
                    "email": "support-owner@example.com", "password": TEST_PASSWORD,
                })
                response = client.post(
                    f"/b/{business['id']}/support-access",
                    data={
                        "purpose": "Revisar la configuración de documentos",
                        "scopes": ["configuration", "document_metadata"],
                        "duration_hours": "1", "consent": "yes",
                    },
                    follow_redirects=False,
                )
                self.assertEqual(response.status_code, 303)
                grant = db.active_support_grant(business["id"])
                self.assertEqual(
                    grant["scopes"], ["configuration", "document_metadata"]
                )
                revoked = client.post(
                    f"/b/{business['id']}/support-access/revoke",
                    follow_redirects=False,
                )
                self.assertEqual(revoked.status_code, 303)
        self.assertIsNone(db.active_support_grant(business["id"]))
        events = [event["event_type"] for event in db.list_security_events()]
        self.assertIn("support.access_granted", events)
        self.assertIn("support.access_revoked", events)
        self.assertEqual(owner["business_id"], business["id"])

    def test_support_snapshot_is_admin_only_private_and_audited(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        admin_business, _ = self.make_business("Dirección Noesis")
        target, _ = self.make_business("Cuenta diagnosticada")
        db.add_client(
            "CLIENTE-SECRETO-NO-MOSTRAR", phone="699999999",
            business_id=target["id"],
        )
        admin = db.create_user(
            "founder-support@example.com", auth.hash_password(TEST_PASSWORD),
            admin_business["id"],
        )
        owner = db.create_user(
            "ordinary@example.com", auth.hash_password(TEST_PASSWORD), target["id"]
        )
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE businesses SET owner_email=? WHERE id=?",
                ("ordinary@example.com", target["id"]),
            )
        grant = db.create_support_grant(
            target["id"], owner["id"], purpose="Revisar una integración bloqueada",
            scopes=["integrations"], duration_hours=4,
        )
        self.assertEqual(grant["scopes"], ["integrations"])
        with (
            patch.object(config, "ADMIN_EMAIL", "founder-support@example.com"),
            patch.object(config, "ADMIN_REQUIRE_GOOGLE_OAUTH", False),
            patch.object(server, "start_scheduler", lambda: None),
        ):
            with TestClient(server.app) as client:
                client.post("/login", data={
                    "email": "founder-support@example.com",
                    "password": TEST_PASSWORD,
                })
                page = client.get(f"/admin/cuentas/{target['id']}")
                self.assertEqual(page.status_code, 200, page.text)
                self.assertIn("Cuenta diagnosticada", page.text)
                self.assertIn("Ventana temporal abierta", page.text)
                self.assertIn("Diagnóstico de integraciones", page.text)
                self.assertNotIn("CLIENTE-SECRETO-NO-MOSTRAR", page.text)
                client.post("/logout")
                client.post("/login", data={
                    "email": "ordinary@example.com", "password": TEST_PASSWORD,
                })
                blocked = client.get(
                    f"/admin/cuentas/{target['id']}", follow_redirects=False
                )
        self.assertEqual(blocked.status_code, 303)
        self.assertEqual(blocked.headers["location"], "/login")
        event = next(
            item for item in db.list_security_events()
            if item["event_type"] == "admin.support_snapshot_viewed"
        )
        self.assertEqual(event["actor_user_id"], admin["id"])
        self.assertEqual(event["subject_business_id"], target["id"])
        self.assertEqual(event["metadata"], {"mode": "read_only"})
        self.assertTrue(db.revoke_support_grant(target["id"], owner["id"]))
        self.assertIsNone(db.active_support_grant(target["id"]))
        with self.assertRaises(ValueError):
            db.create_support_grant(
                admin_business["id"], owner["id"], purpose="Intento fuera de cuenta",
                scopes=["configuration"], duration_hours=1,
            )
        same_business_non_owner = db.create_user(
            "employee@example.com", auth.hash_password(TEST_PASSWORD), target["id"]
        )
        with self.assertRaises(ValueError):
            db.create_support_grant(
                target["id"], same_business_non_owner["id"],
                purpose="Intento sin permiso del titular",
                scopes=["configuration"], duration_hours=1,
            )

    def test_admin_corrects_only_authorized_document_metadata_and_audits_it(self):
        from starlette.testclient import TestClient
        from noesis.documents import repo as document_repo
        from noesis.web import server

        admin_business, _ = self.make_business("Dirección de soporte")
        target, original_client = self.make_business("Cuenta con documento")
        admin = db.create_user(
            "support-admin@example.com", auth.hash_password(TEST_PASSWORD),
            admin_business["id"],
        )
        owner = db.create_user(
            "document-owner@example.com", auth.hash_password(TEST_PASSWORD),
            target["id"],
        )
        with db.get_conn() as conn:
            conn.execute("UPDATE users SET is_admin=1 WHERE id=?", (admin["id"],))
            conn.execute(
                "UPDATE businesses SET owner_email=? WHERE id=?",
                (owner["email"], target["id"]),
            )
        corrected_client = db.add_client(
            "Cliente correcto", business_id=target["id"]
        )
        project = db.add_project(
            "Proyecto correcto", 1200, client_id=corrected_client["id"],
            business_id=target["id"],
        )
        document = document_repo.add(
            target["id"], filename="archivo-a-revisar.pdf",
            stored_name="support-document.pdf", mime="application/pdf", size=10,
            kind="documento", client_id=original_client["id"],
            doc_status="pendiente_revisar",
        )
        document_repo.set_review(
            document["id"], target["id"], review_note="Nota original"
        )
        grant = db.create_support_grant(
            target["id"], owner["id"],
            purpose="Corregir la organización de este documento",
            scopes=["document_metadata"], duration_hours=1,
        )

        with (
            patch.object(config, "ADMIN_EMAIL", "support-admin@example.com"),
            patch.object(config, "ADMIN_REQUIRE_GOOGLE_OAUTH", False),
            patch.object(server, "start_scheduler", lambda: None),
        ):
            with TestClient(server.app) as client:
                client.post("/login", data={
                    "email": "support-admin@example.com", "password": TEST_PASSWORD,
                })
                page = client.get(f"/admin/cuentas/{target['id']}")
                self.assertEqual(page.status_code, 200, page.text)
                self.assertIn("archivo-a-revisar.pdf", page.text)
                response = client.post(
                    f"/admin/cuentas/{target['id']}/documentos/{document['id']}/metadatos",
                    data={
                        "kind": "ticket", "doc_status": "revisado",
                        "client_id": "", "project_id": str(project["id"]),
                        "review_note": "Clasificación confirmada por el titular",
                    },
                    follow_redirects=False,
                )
                self.assertEqual(response.status_code, 303)
                self.assertEqual(
                    response.headers["location"],
                    f"/admin/cuentas/{target['id']}#document-metadata",
                )

        saved = document_repo.get(document["id"], target["id"])
        self.assertEqual(saved["kind"], "ticket")
        self.assertEqual(saved["doc_status"], "revisado")
        self.assertEqual(saved["client_id"], corrected_client["id"])
        self.assertEqual(saved["project_id"], project["id"])
        event = next(
            item for item in reversed(db.list_security_events())
            if item["event_type"] == "admin.support_document_metadata_updated"
        )
        self.assertEqual(event["actor_user_id"], admin["id"])
        self.assertEqual(event["subject_business_id"], target["id"])
        self.assertEqual(event["metadata"]["grant_id"], grant["id"])
        self.assertEqual(event["metadata"]["before_kind"], "documento")
        self.assertEqual(event["metadata"]["after_kind"], "ticket")
        self.assertNotIn("Clasificación confirmada", json.dumps(event["metadata"]))

    def test_support_document_correction_fails_closed_without_scope_or_for_issued_invoice(self):
        from noesis.documents import repo as document_repo

        admin_business, _ = self.make_business("Administración segura")
        target, target_client = self.make_business("Cuenta protegida")
        other_business, other_client = self.make_business("Otra cuenta")
        admin = db.create_user(
            "closed-support@example.com", auth.hash_password(TEST_PASSWORD),
            admin_business["id"],
        )
        owner = db.create_user(
            "protected-owner@example.com", auth.hash_password(TEST_PASSWORD),
            target["id"],
        )
        with db.get_conn() as conn:
            conn.execute("UPDATE users SET is_admin=1 WHERE id=?", (admin["id"],))
            conn.execute(
                "UPDATE businesses SET owner_email=? WHERE id=?",
                (owner["email"], target["id"]),
            )
        document = document_repo.add(
            target["id"], filename="privado.pdf", stored_name="private.pdf",
            mime="application/pdf", size=10, kind="documento",
        )
        with self.assertRaises(PermissionError):
            db.admin_update_document_metadata(
                target["id"], document["id"], actor_user_id=admin["id"],
                kind="ticket", doc_status="revisado", client_id=None,
                project_id=None, review_note=None,
            )

        db.create_support_grant(
            target["id"], owner["id"], purpose="Revisar documento protegido",
            scopes=["document_metadata"], duration_hours=1,
        )
        with self.assertRaisesRegex(ValueError, "no pertenece"):
            db.admin_update_document_metadata(
                target["id"], document["id"], actor_user_id=admin["id"],
                kind="ticket", doc_status="revisado",
                client_id=other_client["id"], project_id=None, review_note=None,
            )

        invoice = db.add_invoice(
            target_client["id"], "Trabajo emitido", 100,
            business_id=target["id"],
        )
        issued = db.issue_invoice(invoice["id"], target["id"])
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE documents SET invoice_id=? WHERE id=? AND business_id=?",
                (issued["id"], document["id"], target["id"]),
            )
        with self.assertRaisesRegex(ValueError, "factura emitida"):
            db.admin_update_document_metadata(
                target["id"], document["id"], actor_user_id=admin["id"],
                kind="ticket", doc_status="revisado", client_id=None,
                project_id=None, review_note=None,
            )
        unchanged = document_repo.get(document["id"], target["id"])
        self.assertEqual(unchanged["kind"], "documento")
        self.assertIsNotNone(other_business)

    def test_admin_corrects_only_safe_configuration_with_owner_scope(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        admin_business, _ = self.make_business("Administración de configuración")
        target, target_client = self.make_business("Nombre anterior")
        admin = db.create_user(
            "config-admin@example.com", auth.hash_password(TEST_PASSWORD),
            admin_business["id"],
        )
        owner = db.create_user(
            "config-owner@example.com", auth.hash_password(TEST_PASSWORD),
            target["id"],
        )
        with db.get_conn() as conn:
            conn.execute("UPDATE users SET is_admin=1 WHERE id=?", (admin["id"],))
            conn.execute(
                "UPDATE businesses SET owner_email=?, payment_iban=?, plan=?, "
                "subscription_status=? WHERE id=?",
                (
                    owner["email"], TEST_IBAN, "premium", "active", target["id"],
                ),
            )
        original = db.get_business(target["id"])
        issued = db.issue_invoice(
            db.add_invoice(
                target_client["id"], "Trabajo anterior", 100,
                business_id=target["id"],
            )["id"],
            target["id"],
        )
        grant = db.create_support_grant(
            target["id"], owner["id"],
            purpose="Corregir idioma y apariencia documental",
            scopes=["configuration"], duration_hours=1,
        )

        with (
            patch.object(config, "ADMIN_EMAIL", "config-admin@example.com"),
            patch.object(config, "ADMIN_REQUIRE_GOOGLE_OAUTH", False),
            patch.object(server, "start_scheduler", lambda: None),
        ):
            with TestClient(server.app) as client:
                client.post("/login", data={
                    "email": "config-admin@example.com", "password": TEST_PASSWORD,
                })
                page = client.get(f"/admin/cuentas/{target['id']}")
                self.assertEqual(page.status_code, 200, page.text)
                self.assertIn("Corregir perfil y apariencia", page.text)
                self.assertNotIn("payment_iban", page.text)
                response = client.post(
                    f"/admin/cuentas/{target['id']}/configuracion-segura",
                    data={
                        "name": "Taller corregido", "sector": "Climatización",
                        "team_size": "2-5", "province": "Tarragona",
                        "primary_goal": "control", "language": "ca",
                        "explanation_level": "detallado",
                        "invoice_template": "editorial", "brand_color": "#2e8b74",
                        "document_footer": "Pie privado del titular",
                        "quote_terms": "Condiciones privadas del presupuesto",
                        "default_quote_validity_days": "45",
                    },
                    follow_redirects=False,
                )
                self.assertEqual(response.status_code, 303)
                self.assertEqual(
                    response.headers["location"],
                    f"/admin/cuentas/{target['id']}#safe-configuration",
                )

        saved = db.get_business(target["id"])
        self.assertEqual(saved["name"], "Taller corregido")
        self.assertEqual(saved["language"], "ca")
        self.assertEqual(saved["invoice_template"], "editorial")
        self.assertEqual(saved["default_quote_validity_days"], 45)
        frozen_invoice = db.get_invoice(issued["id"], target["id"])
        self.assertEqual(frozen_invoice["issuer_name"], "Nombre anterior")
        for protected in (
            "owner_email", "nif", "address", "default_vat", "default_irpf",
            "payment_iban", "plan", "subscription_status",
        ):
            self.assertEqual(saved[protected], original[protected], protected)
        event = next(
            item for item in reversed(db.list_security_events())
            if item["event_type"] == "admin.support_configuration_updated"
        )
        serialized = json.dumps(event["metadata"], ensure_ascii=False)
        self.assertEqual(event["actor_user_id"], admin["id"])
        self.assertEqual(event["metadata"]["grant_id"], grant["id"])
        self.assertIn("language", event["metadata"]["changed_fields"])
        self.assertNotIn("Taller corregido", serialized)
        self.assertNotIn("Pie privado", serialized)
        self.assertNotIn(TEST_IBAN, serialized)

    def test_support_configuration_fails_closed_for_wrong_scope_expiry_and_non_admin(self):
        target, _ = self.make_business("Configuración cerrada")
        owner = db.create_user(
            "closed-config-owner@example.com", auth.hash_password(TEST_PASSWORD),
            target["id"],
        )
        outsider = db.create_user(
            "not-admin@example.com", auth.hash_password(TEST_PASSWORD), target["id"]
        )
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE businesses SET owner_email=? WHERE id=?",
                (owner["email"], target["id"]),
            )

        def update(actor_user_id: int):
            return db.admin_update_safe_business_configuration(
                target["id"], actor_user_id=actor_user_id,
                name="Configuración nueva", sector="Servicios", team_size="solo",
                province="Barcelona", primary_goal="control", language="es",
                explanation_level="claro", invoice_template="clasica",
                brand_color="#14463b", document_footer="", quote_terms="",
                default_quote_validity_days=30,
            )

        db.create_support_grant(
            target["id"], owner["id"], purpose="Revisar solo documentos",
            scopes=["document_metadata"], duration_hours=1,
        )
        with self.assertRaises(PermissionError):
            update(outsider["id"])

        with db.get_conn() as conn:
            conn.execute("UPDATE users SET is_admin=1 WHERE id=?", (outsider["id"],))
        with self.assertRaises(PermissionError):
            update(outsider["id"])

        grant = db.create_support_grant(
            target["id"], owner["id"], purpose="Revisar configuración temporal",
            scopes=["configuration"], duration_hours=1,
        )
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE support_access_grants SET expires_at=? WHERE id=?",
                ((datetime.now() - timedelta(minutes=1)).isoformat(timespec="seconds"),
                 grant["id"]),
            )
        with self.assertRaises(PermissionError):
            update(outsider["id"])
        self.assertEqual(db.get_business(target["id"])["name"], "Configuración cerrada")
        self.assertIsNone(db.active_support_grant(target["id"]))

    def test_admin_registers_and_activates_business_whatsapp_without_secrets(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        admin_business, _ = self.make_business("Dirección multicanal")
        target, _ = self.make_business("Cuenta con WhatsApp comercial")
        admin = db.create_user(
            "whatsapp-admin@example.com", auth.hash_password(TEST_PASSWORD),
            admin_business["id"],
        )
        with (
            patch.object(config, "ADMIN_EMAIL", "whatsapp-admin@example.com"),
            patch.object(config, "ADMIN_REQUIRE_GOOGLE_OAUTH", False),
            patch.object(server, "start_scheduler", lambda: None),
        ):
            with TestClient(server.app) as client:
                client.post("/login", data={
                    "email": "whatsapp-admin@example.com",
                    "password": TEST_PASSWORD,
                })
                created = client.post(
                    f"/admin/cuentas/{target['id']}/whatsapp-business",
                    data={
                        "waba_id": "123 456",
                        "phone_number_id": "654 321",
                        "display_phone": "+34 600 123 456",
                        "verified_name": "Taller Exemple",
                        "access_token": "no-debe-aceptarse",
                    },
                    follow_redirects=False,
                )
                self.assertEqual(created.status_code, 303)
                connection = db.list_whatsapp_connections(target["id"])[0]
                self.assertEqual(connection["status"], "pending")
                self.assertFalse(connection["receptionist_enabled"])
                self.assertEqual(connection["waba_id"], "123456")
                self.assertNotIn("token", connection)

                activated = client.post(
                    f"/admin/cuentas/{target['id']}/whatsapp-business/"
                    f"{connection['id']}",
                    data={"status": "active", "receptionist_enabled": "1"},
                    follow_redirects=False,
                )
                self.assertEqual(activated.status_code, 303)
                connection = db.get_whatsapp_connection(
                    connection["id"], target["id"]
                )
                self.assertEqual(connection["status"], "active")
                self.assertTrue(connection["receptionist_enabled"])

                page = client.get(f"/admin/cuentas/{target['id']}")
                self.assertEqual(page.status_code, 200, page.text)
                self.assertIn("Taller Exemple", page.text)
                self.assertNotIn("no-debe-aceptarse", page.text)

        events = {
            item["event_type"]: item for item in db.list_security_events()
        }
        self.assertEqual(
            events["admin.whatsapp_connection_registered"]["actor_user_id"],
            admin["id"],
        )
        self.assertEqual(
            events["admin.whatsapp_connection_updated"]["subject_business_id"],
            target["id"],
        )

    def test_missing_required_google_blocks_admin_not_the_whole_service(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, _ = self.make_business("Admin bloqueado")
        db.create_user(
            "blocked-admin@example.com", auth.hash_password(TEST_PASSWORD),
            business["id"],
        )
        with (
            patch.object(config, "IS_PRODUCTION", True),
            patch.object(config, "SECRET_KEY", "x" * 64),
            patch.object(config, "ADMIN_EMAIL", "blocked-admin@example.com"),
            patch.object(config, "ADMIN_REQUIRE_GOOGLE_OAUTH", True),
            patch.object(config, "GOOGLE_OAUTH_CLIENT_ID", ""),
            patch.object(config, "GOOGLE_OAUTH_CLIENT_SECRET", ""),
            patch.object(server, "start_scheduler", lambda: None),
        ):
            with TestClient(server.app) as client:
                self.assertEqual(client.get("/health").status_code, 200)
                client.post("/login", data={
                    "email": "blocked-admin@example.com",
                    "password": TEST_PASSWORD,
                })
                admin = client.get("/admin", follow_redirects=False)
        self.assertEqual(admin.status_code, 303)
        self.assertEqual(admin.headers["location"], "/login")

    def test_admin_sees_internal_readiness_instead_of_the_customer(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, _ = self.make_business("Admin servicios")
        db.create_user(
            "founder@example.com", auth.hash_password(TEST_PASSWORD),
            business["id"],
        )
        with (
            patch.object(config, "ADMIN_EMAIL", "founder@example.com"),
            patch.object(server, "start_scheduler", lambda: None),
        ):
            with TestClient(server.app) as client:
                client.post("/login", data={
                    "email": "founder@example.com",
                    "password": TEST_PASSWORD,
                })
                page = client.get("/admin")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Servicios e integraciones", page.text)
        self.assertIn("Google", page.text)
        self.assertIn("Esta información es interna", page.text)

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
            billing.PLAN_PRICES, {"autonomo": 29, "pro": 49, "premium": 99}
        )
        self.assertEqual(
            billing.PLAN_ANNUAL_PRICES,
            {"autonomo": 319, "pro": 539, "premium": 1089},
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
        period = date.today().strftime("%Y-%m")
        db.add_platform_cost(
            period, "hosting", 20, source="actual", note="Factura hosting"
        )
        db.add_platform_cost(
            period, "hosting", -2, source="adjustment",
            note="Abono aplicado a la factura",
        )
        db.add_platform_cost(
            period, "support", 100, source="forecast", note="Previsión soporte"
        )
        data = db.admin_overview()
        self.assertIn("marketing", data["dept_reports"])
        charts = data["charts"]
        self.assertEqual(len(charts["funnel"]), len(charts["funnel_labels"]))
        labels = charts["funnel_labels"]
        self.assertEqual(charts["funnel"][labels.index("Checkout")], 1)
        self.assertEqual(charts["funnel"][labels.index("De pago")], 1)
        self.assertEqual(data["mrr"], 99)
        self.assertEqual(data["finanzas"]["observed_costs"], 18)
        self.assertEqual(data["finanzas"]["observed_contribution"], 81)
        self.assertEqual(data["finanzas"]["observed_margin_pct"], 81.8)
        self.assertEqual(data["finanzas"]["observed_cost_per_active_account"], 18)
        self.assertEqual(data["finanzas"]["cost_ledger"]["forecast_total"], 100)
        with self.assertRaises(ValueError):
            db.add_platform_cost(
                "agosto", "hosting", 20, source="actual"
            )
        with self.assertRaises(ValueError):
            db.add_platform_cost(
                period, "hosting", -20, source="actual", note="Coste imposible"
            )
        with self.assertRaises(db.IntegrityError):
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE platform_cost_entries SET amount_eur=999 WHERE period=?",
                    (period,),
                )

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
        with patch.object(config, "VERIFACTU_PRODUCER_NIF", PRODUCER_NIF):  # pragma: allowlist secret
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
