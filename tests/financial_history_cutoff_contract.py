"""Contrato1.9C compartido; fixtures sintéticos, jamás proveedor o importación."""

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import hashlib
from pathlib import Path
import time
from unittest.mock import patch
from uuid import uuid4

from noesis import config, db, migrations
from noesis.bank_capture.service import BankCapture
from noesis.core.persistence import FinancialSession
from noesis.documents import repo as documents, storage
from noesis.economic_events.service import EconomicEvents
from noesis.financial_history.cutoff import EpochUnavailable, HistoryCutoff
from noesis.financial_history.cut_scope import guarded_columns
from noesis.financial_history.fence import HistoricalFenceActive, assert_writable, external_guard
from noesis.financial_history.repository import HistoryRepository
from noesis.financial_history.service import HistoryDiagnostics
from noesis.financial_operations.contracts import (
    AccessDenied,
    ConflictError,
    EntryIdentity,
    Principal,
)
from noesis.financial_operations.service import FinancialOperations
from noesis.invoice_capture.service import InvoiceCapture
from noesis.payment_capture.service import PaymentCapture
from noesis.purchasing_capture import ExpenseCapture, SupplierInvoiceCapture
from tests.borrowed_writers_contract import BorrowedWritersContract
from tests.financial_history_inventory_contract import HistoryInventoryContract


class HistoryCutoffContract:
    seed = BorrowedWritersContract.seed
    draft = BorrowedWritersContract.draft
    issued = BorrowedWritersContract.issued
    document = BorrowedWritersContract.document
    movement = BorrowedWritersContract.movement
    schedule = BorrowedWritersContract.schedule
    empty_database = HistoryInventoryContract.empty_database

    def unchanged(self):
        result = HistoryInventoryContract.unchanged(self)
        with db.get_conn() as conn:
            rows = conn.execute_exact(
                "SELECT * FROM document_sequences WHERE business_id=? ORDER BY kind,year", (self.bid,)
            ).fetchall()
            result['document_sequences'] = repr([dict(row) for row in rows])
        return result

    def setup_cut(self):
        self.seed()
        self.user = db.create_user(uuid4().hex + "@example.test", "fixture", self.bid)
        self.principal = Principal(self.user["id"], 0)
        self.cut = HistoryCutoff(self.bid, page_size=8)
        self.epoch_uuid = str(uuid4())

    def open(self, **kwargs):
        return self.cut.open(
            self.principal,
            self.epoch_uuid,
            repository_version="fixture-code",
            environment_identity="synthetic-local",
            **kwargs,
        )

    def inventory(self, uid=None):
        return self.cut.inventory(
            self.principal,
            self.epoch_uuid,
            uid or uuid4(),
            repository_version="fixture-code",
            environment_identity="synthetic-local",
        )

    def approved(self, service, request):
        identity = (
            EntryIdentity.imported(request.parameters["batch"], request.parameters["row"])
            if request.command_type.value == "bank_transaction.import"
            else EntryIdentity.web_api(uuid4())
        )
        op = service.prepare(self.principal, identity, request)
        return service.authorize(
            self.principal,
            op.operation_uuid,
            channel=identity.namespace,
            approved_hash=request.request_hash,
            approved_revision=request.expected_revision,
        )

    def prepared_captures(self):
        invoice = InvoiceCapture(self.bid)
        original = invoice.execute(
            self.principal,
            self.approved(
                invoice, invoice.review(self.principal, self.draft()["id"])
            ).operation_uuid,
        )
        iid = original.result["invoice_id"]
        invoice_op = self.approved(invoice, invoice.review(self.principal, self.draft()["id"]))
        payment = PaymentCapture(self.bid)
        payment_op = self.approved(payment, payment.review(self.principal, iid, amount="1.00"))
        bank = BankCapture(self.bid)
        request = bank.review_import(
            self.principal,
            batch_uuid=uuid4(),
            row_key="1",
            account_scope="fixture",
            statement_hash=hashlib.sha256(b"fixture").hexdigest(),
            booked_on=date.today().isoformat(),
            amount="2.00",
        )
        bank_op = self.approved(bank, request)
        received, expense = SupplierInvoiceCapture(self.bid), ExpenseCapture(self.bid)
        received_op = self.approved(
            received, received.review_confirm(self.principal, total="121.00")
        )
        expense_op = self.approved(
            expense, expense.review_confirm(self.principal, amount="12.10", concept="Material")
        )
        return [
            (invoice, invoice_op),
            (payment, payment_op),
            (bank, bank_op),
            (received, received_op),
            (expense, expense_op),
        ], original

    def test_open_only_control_metadata_t0_aware_flags_off(self):
        self.draft()
        self.document()
        self.movement()
        before = self.unchanged()
        epoch = self.open()
        self.assertEqual(self.unchanged(), before)
        self.assertEqual(epoch["state"], "fenced")
        self.assertEqual(epoch["generation"], 1)
        self.assertEqual(epoch["t0"], epoch["opened_at"])
        self.assertIsNotNone(datetime.fromisoformat(str(epoch["t0"])).utcoffset())
        self.assertFalse(any(before["flags"]))

    def test_exact_retry_conflict_and_only_one_active(self):
        epoch = self.open()
        self.assertEqual(self.open(), epoch)
        with self.assertRaises(ConflictError):
            self.cut.open(
                self.principal,
                uuid4(),
                repository_version="fixture-code",
                environment_identity="synthetic-local",
            )
        with self.assertRaises(ConflictError):
            self.cut.open(
                self.principal,
                self.epoch_uuid,
                repository_version="changed-code",
                environment_identity="synthetic-local",
            )
        self.assertEqual(self.open()["t0"], epoch["t0"])

    def test_release_explicit_no_reactivation_generation_monotonic(self):
        first = self.open()
        self.inventory()
        second = self.cut.release(self.principal, self.epoch_uuid, reason="manual_end")
        self.assertEqual(second["state"], "released")
        self.assertEqual(self.open()["state"], "released")
        with self.assertRaises(EpochUnavailable):
            self.inventory()
        self.epoch_uuid = str(uuid4())
        current = self.open()
        self.assertEqual(current["generation"], first["generation"] + 1)
        self.assertGreater(
            datetime.fromisoformat(str(current["t0"])), datetime.fromisoformat(str(first["t0"]))
        )

    def test_certifiable_inventory_separate_immutable_diagnostic(self):
        self.open()
        result = self.inventory()
        self.assertEqual(result["mode"], "certifiable_inventory")
        self.assertTrue(result["certifiable"])

        self.assertTrue(result["boundary_current"])
        self.assertFalse(result["eligible_for_import"])
        with db.get_conn() as conn:
            base = conn.execute(
                "SELECT * FROM financial_history_manifests WHERE business_id=? AND manifest_uuid=?",
                (self.bid, str(result["manifest_uuid"])),
            ).fetchone()
        self.assertEqual(base["mode"], "diagnostic")
        self.assertFalse(base["certifiable"])
        self.assertEqual(base["source_set_hash"], result["source_set_hash"])
        with self.assertRaises(Exception), db.get_conn() as conn:
            conn.execute(
                "UPDATE financial_history_cut_manifests SET eligible_for_import=TRUE WHERE business_id=?",
                (self.bid,),
            )

    def test_two_scans_same_semantic_hash_writer_rejection_other_business(self):
        self.draft()
        self.document()
        self.open()
        first = self.inventory()
        with self.assertRaises(HistoricalFenceActive):
            self.draft()
        other = db.create_business("Otro", uuid4().hex + "@example.test")
        db.add_expense("Otro", "1.00", business_id=other["id"])
        second = self.inventory()
        self.assertEqual(first["source_set_hash"], second["source_set_hash"])
        self.assertEqual(first["plan_hash"], second["plan_hash"])

    def test_invalidated_still_fenced_and_manifest_revoked_hash_preserved(self):
        self.open()
        result = self.inventory()
        self.cut.invalidate(self.principal, self.epoch_uuid, reason="manual_abort")
        with self.assertRaises(HistoricalFenceActive):
            self.draft()
        with self.assertRaises(EpochUnavailable):
            self.inventory()
        with db.get_conn() as conn:
            after = conn.execute(
                "SELECT * FROM financial_history_cut_manifests WHERE business_id=? AND manifest_uuid=?",
                (self.bid, str(result["manifest_uuid"])),
            ).fetchone()
        self.assertFalse(after["boundary_current"])
        self.assertFalse(after["certifiable"])
        self.assertEqual(after["source_set_hash"], result["source_set_hash"])
        self.assertEqual(after["plan_hash"], result["plan_hash"])
        self.cut.release(self.principal, self.epoch_uuid, reason="safe_abort_end")
        self.draft()

    def test_release_preserves_manifest_and_old_boundary_never_current(self):
        self.open()
        first = self.inventory()
        self.cut.release(self.principal, self.epoch_uuid, reason="manual_end")
        self.draft()
        with db.get_conn() as conn:
            after = conn.execute(
                "SELECT * FROM financial_history_cut_manifests WHERE business_id=? AND manifest_uuid=?",
                (self.bid, str(first["manifest_uuid"])),
            ).fetchone()
        self.assertFalse(after["boundary_current"])
        self.assertFalse(after["certifiable"])
        self.assertEqual(after["source_set_hash"], first["source_set_hash"])
        self.assertEqual(after["plan_hash"], first["plan_hash"])

    def test_crash_after_open_during_scan_and_after_freeze_no_cleanup(self):
        epoch = self.open()
        self.draft_before_crash = epoch["t0"]
        with patch.object(HistoryRepository, "insert_sources", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.inventory(uuid4())
        self.assertEqual(self.open()["t0"], epoch["t0"])
        with self.assertRaises(HistoricalFenceActive):
            self.draft()
        uid = uuid4()
        frozen = self.inventory(uid)
        self.assertEqual(self.inventory(uid), frozen)
        self.assertTrue(self.cut.read(self.principal, self.epoch_uuid)["fence_enabled"])

    def test_partial_resume_same_manifest_after_crash(self):
        self.draft()
        self.open()
        uid = uuid4()
        original = HistoryRepository.insert_sources
        called = 0

        def crash(repo, sources):
            nonlocal called
            called += 1
            if called == 2:
                raise KeyboardInterrupt
            return original(repo, sources)

        with patch.object(HistoryRepository, "insert_sources", crash):
            with self.assertRaises(KeyboardInterrupt):
                self.inventory(uid)
        result = self.inventory(uid)
        self.assertTrue(result["certifiable"])
        self.assertEqual(result["manifest_uuid"], self.inventory(uid)["manifest_uuid"])

    def test_invalidation_before_freeze_aborts_without_rewriting_inventory(self):
        self.open()
        uid = uuid4()
        original = HistoryRepository.insert_sources
        called = False

        def abort(repo, sources):
            nonlocal called
            result = original(repo, sources)
            called = True
            return result

        # Invalidate between page transactions, not while holding the page gate.
        from noesis.financial_history.cutoff import _CutInventory

        original_reader = _CutInventory._reader

        class Reader:
            def __init__(inner, reader):
                inner.reader = reader

            def page(inner, *args, **kwargs):
                return inner.reader.page(*args, **kwargs)

        with (
            patch.object(HistoryRepository, "insert_sources", abort),
            patch.object(_CutInventory, "_reader", lambda x, s: Reader(original_reader(x, s))),
        ):
            # Simular crash y posteriormente decisión explícita, conservando page1.
            with patch.object(HistoryRepository, "record_result", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    self.inventory(uid)
        self.assertTrue(called)
        self.cut.invalidate(self.principal, self.epoch_uuid, reason="operator_abort")
        with self.assertRaises(EpochUnavailable):
            self.inventory(uid)
        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM financial_history_cut_manifests WHERE business_id=? AND manifest_uuid=?",
                (self.bid, str(uid)),
            ).fetchone()
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM financial_history_items WHERE business_id=? AND manifest_uuid=?",
                (self.bid, str(uid)),
            ).fetchone()["n"]
        self.assertEqual(row["status"], "aborted")
        self.assertEqual(row["result"], "BLOCKED")
        self.assertFalse(row["certifiable"])
        self.assertGreater(count, 0)

    def test_ttl_attention_never_releases(self):
        with patch(
            "noesis.financial_history.cutoff.stamp",
            return_value=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        ):
            self.open()
        state = self.cut.read(self.principal, self.epoch_uuid)
        self.assertTrue(state["attention_required"])
        self.assertTrue(state["fence_enabled"])
        with self.assertRaises(HistoricalFenceActive):
            self.draft()

    def test_permissions_idor_other_operator_revoked_and_forged_uuid(self):
        self.open()
        other = db.create_user(uuid4().hex + "@example.test", "fixture", self.bid)
        for method in ("read", "invalidate", "release"):
            with self.subTest(method=method), self.assertRaises(AccessDenied):
                getattr(self.cut, method)(
                    Principal(other["id"], 0),
                    self.epoch_uuid,
                    **({} if method == "read" else {"reason": "manual"}),
                )
        with self.assertRaises(AccessDenied):
            self.cut.read(self.principal, uuid4())
        with self.assertRaises(AccessDenied):
            self.cut.release(
                replace(self.principal, session_version=1), self.epoch_uuid, reason="manual"
            )
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE users SET is_active=FALSE WHERE business_id=? AND id=?",
                (self.bid, self.user["id"]),
            )
        with self.assertRaises(AccessDenied):
            self.cut.release(self.principal, self.epoch_uuid, reason="manual")
        with self.assertRaises(HistoricalFenceActive):
            self.draft()

    def test_cross_tenant_epoch_no_authority(self):
        self.open()
        other = db.create_business("Otro", uuid4().hex + "@example.test")
        db.set_trial(other["id"], days=14)
        user = db.create_user(uuid4().hex + "@example.test", "fixture", other["id"])
        with self.assertRaises(AccessDenied):
            HistoryCutoff(other["id"]).release(
                Principal(user["id"], 0), self.epoch_uuid, reason="manual"
            )
        with self.assertRaises(AccessDenied):
            self.cut.read(Principal(user["id"], 0), self.epoch_uuid)
        with db.get_conn() as conn:
            assert_writable(conn, other["id"])

    def test_missing_environment_urls_credentials_and_flags_rejected(self):
        for env in (None, "", "postgresql://secret@host/db", "https://prod", "name with spaces"):
            with self.subTest(env=env), self.assertRaises(ValueError):
                self.cut.open(
                    self.principal,
                    self.epoch_uuid,
                    repository_version="fixture",
                    environment_identity=env,
                )
        with patch.object(config, "FINANCIAL_CORE_ENABLED", True), self.assertRaises(AccessDenied):
            self.open()

    def test_five_captures_preapproved_block_before_any_effect_flags_off(self):
        operations, _ = self.prepared_captures()
        before = self.unchanged()
        self.open()
        for capture, operation in operations:
            with (
                self.subTest(capture=type(capture).__name__),
                self.assertRaises(HistoricalFenceActive),
            ):
                capture.execute(self.principal, operation.operation_uuid)
            self.assertEqual(self.unchanged(), before)
        for capture, operation in operations:
            current = FinancialOperations(self.bid).recover(
                self.principal, operation.operation_uuid
            )
            self.assertEqual(current.state.value, "approved")

    def test_prepared_operation_cannot_authorize_or_execute_under_fence(self):
        capture = InvoiceCapture(self.bid)
        request = capture.review(self.principal, self.draft()["id"])
        identity = EntryIdentity.web_api(uuid4())
        op = capture.prepare(self.principal, identity, request)
        before = self.unchanged()
        self.open()
        with self.assertRaises(HistoricalFenceActive):
            capture.authorize(
                self.principal,
                op.operation_uuid,
                channel=identity.namespace,
                approved_hash=request.request_hash,
                approved_revision=request.expected_revision,
            )
        with self.assertRaises(HistoricalFenceActive):
            capture.execute(self.principal, op.operation_uuid)
        self.assertEqual(self.unchanged(), before)
        self.assertEqual(
            FinancialOperations(self.bid).recover(self.principal, op.operation_uuid).state.value,
            "prepared",
        )

    def test_direct_live_ee_append_cannot_bypass_gate_counter(self):
        _, original = self.prepared_captures()
        with db.get_conn() as conn:
            event = (
                EconomicEvents(FinancialSession(conn), self.bid)
                .read(self.principal, original.result["event_uuid"])
                .event
            )
        before = self.unchanged()
        self.open()
        with self.assertRaises(HistoricalFenceActive), db.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            EconomicEvents(FinancialSession(conn), self.bid).append(self.principal, event)
        self.assertEqual(self.unchanged(), before)

    def test_legacy_sources_drafts_payment_bank_purchase_and_documents_block(self):
        invoice = self.issued()
        draft = self.draft()
        movement = self.movement()
        document = self.document()
        supplier = db.add_supplier("Proveedor", business_id=self.bid)
        received = db.add_received_invoice("121", supplier_id=supplier["id"], business_id=self.bid)
        expense = db.add_expense("Material", "10", business_id=self.bid)
        before = self.unchanged()
        self.open()
        actions = [
            lambda: self.draft(),
            lambda: db.issue_invoice(draft["id"], self.bid),
            lambda: db.add_invoice_payment(invoice["id"], "1", business_id=self.bid),
            lambda: self.movement(),
            lambda: db.ignore_bank_transaction(movement, self.bid),
            lambda: db.add_received_invoice("10", business_id=self.bid),
            lambda: db.set_received_invoice_status(received["id"], "pagada", business_id=self.bid),
            lambda: db.delete_received_invoice(received["id"], self.bid),
            lambda: db.add_expense("Otro", "1", business_id=self.bid),
            lambda: db.delete_expense(expense["id"], self.bid),
            lambda: documents.delete(document, self.bid),
            lambda: documents.set_review(document, self.bid, doc_status="revisado"),
            lambda: documents.confirm_classification(document, self.bid, "ticket"),
            lambda: self.document(),
            lambda: db.add_supplier("Otro", business_id=self.bid),
        ]
        for action in actions:
            with self.assertRaises(HistoricalFenceActive):
                action()
            self.assertEqual(self.unchanged(), before)

    def test_direct_sql_critical_tables_and_counter_unchanged(self):
        invoice = self.draft()
        movement = self.movement()
        doc = self.document()
        supplier = db.add_supplier("Proveedor", business_id=self.bid)
        received = db.add_received_invoice("121", supplier_id=supplier["id"], business_id=self.bid)
        expense = db.add_expense("Material", "10", business_id=self.bid)
        before = self.unchanged()
        self.open()
        statements = [
            ("UPDATE invoices SET total=0 WHERE business_id=?", (self.bid,)),
            ("DELETE FROM invoice_lines WHERE business_id=?", (self.bid,)),
            ("UPDATE bank_transactions SET amount=0 WHERE business_id=?", (self.bid,)),
            ("UPDATE received_invoices SET total=0 WHERE business_id=?", (self.bid,)),
            ("UPDATE expenses SET amount=0 WHERE business_id=?", (self.bid,)),
            ("UPDATE suppliers SET name=? WHERE business_id=?", ("Otro", self.bid)),
            ("UPDATE documents SET stored_name=? WHERE business_id=?", ("replace.pdf", self.bid)),
            (
                "UPDATE document_classifications SET confirmed_kind=? WHERE business_id=?",
                ("ticket", self.bid),
            ),
            (
                "INSERT INTO economic_event_sequences (business_id,last_sequence) VALUES (?,1)",
                (self.bid,),
            ),
            (
                "INSERT INTO document_sequences (business_id,kind,year,last_number) VALUES (?,'invoice',2026,2)",
                (self.bid,),
            ),
        ]
        for sql, args in statements:
            with (
                self.subTest(sql=sql),
                self.assertRaises(HistoricalFenceActive),
                db.get_conn() as conn,
            ):
                conn.execute(sql, args)
        self.assertEqual(self.unchanged(), before)
        self.assertTrue(all((invoice, movement, doc, received, expense)))

    def test_sql_guard_catalog_covers_every_table_three_operations(self):
        with db.get_conn() as conn:
            if conn.dialect == "sqlite":
                names = {
                    r["name"]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='trigger'"
                    ).fetchall()
                }
            else:
                names = {
                    r["trigger_name"]
                    for r in conn.execute(
                        "SELECT trigger_name FROM information_schema.triggers WHERE trigger_schema=current_schema()"
                    ).fetchall()
                }
        for table in guarded_columns():
            for action in ("insert", "update", "delete"):
                self.assertIn(f"aaa_history_fence_{table}_{action}", names)

    def test_nonfinancial_preferences_messages_reminders_and_quote_counter_allowed(self):
        invoice = self.issued()
        self.open()
        db.update_panel_layout(self.bid, [], [])
        db.mark_reminder_sent(invoice["id"], self.bid)
        with db.get_conn() as conn:
            conn.execute(
                "INSERT INTO document_sequences (business_id,kind,year,last_number) VALUES (?,'quote',2026,1)",
                (self.bid,),
            )
            conn.execute("UPDATE businesses SET language=? WHERE id=?", ("es", self.bid))
        self.assertTrue(self.cut.read(self.principal, self.epoch_uuid)["fence_enabled"])

    def test_business_delete_retains_epoch_and_empty_schema_legacy_delete(self):
        self.open()
        with self.assertRaises((ValueError, HistoricalFenceActive)):
            db.delete_business_cascade(self.bid)
        with self.assertRaises(Exception), db.get_conn() as conn:
            conn.execute("DELETE FROM businesses WHERE id=?", (self.bid,))
        self.cut.release(self.principal, self.epoch_uuid, reason="manual_end")
        with self.assertRaisesRegex(ValueError, "evidencia"):
            db.delete_business_cascade(self.bid)

    def test_migration_cycles_and_no_change_to_70(self):
        from noesis.financial_history.cut_schema import TABLES

        for start in (0, 70):
            with self.subTest(start=start), self.empty_database(start):
                self.assertEqual(migrations.upgrade(71), 71)
                with db.get_conn() as conn:
                    sql = (
                        "SELECT name AS name FROM sqlite_master WHERE type='table'"
                        if conn.dialect == "sqlite"
                        else "SELECT table_name AS name FROM information_schema.tables WHERE table_schema=current_schema()"
                    )
                    before = {r["name"] for r in conn.execute(sql).fetchall()}
                self.assertEqual(migrations.downgrade(70), 70)
                with db.get_conn() as conn:
                    after = {r["name"] for r in conn.execute(sql).fetchall()}
                self.assertEqual(before - after, set(TABLES))
                self.assertEqual(migrations.upgrade(71), 71)

    def test_downgrade_with_epoch_even_released_blocked(self):
        self.open()
        self.cut.release(self.principal, self.epoch_uuid, reason="manual_end")
        with self.assertRaisesRegex(ValueError, "evidencia"):
            migrations.downgrade(70)
        self.assertEqual(migrations.current_version(), migrations.LATEST_VERSION)

    def test_diagnostic_cannot_promote_sql_or_attach_to_epoch(self):
        diagnostic = HistoryDiagnostics(self.bid).run(
            self.principal,
            uuid4(),
            repository_version="fixture-code",
            environment_identity="synthetic-local",
        )
        self.open()
        with self.assertRaises(ConflictError):
            self.inventory(diagnostic["manifest_uuid"])
        self.assertEqual(self.cut.read(self.principal, self.epoch_uuid)["state"], "fenced")
        for update in (
            "mode='certifiable_inventory'",
            "certifiable=TRUE",
            "eligible_for_import=TRUE",
        ):
            with self.assertRaises(Exception), db.get_conn() as conn:
                conn.execute(
                    f"UPDATE financial_history_manifests SET {update} WHERE business_id=? AND manifest_uuid=?",
                    (self.bid, str(diagnostic["manifest_uuid"])),
                )

    def test_sql_epoch_identity_state_and_evidence_immutable(self):
        self.open()
        self.inventory()
        for table, update in [
            ("financial_history_epochs", "t0=opened_at,generation=generation+1"),
            ("financial_history_control", "fence_enabled=FALSE"),
            ("financial_history_cut_manifests", "t0=started_at"),
            ("financial_history_epoch_audit", "reason='changed'"),
        ]:
            with self.assertRaises(Exception), db.get_conn() as conn:
                conn.execute(f"UPDATE {table} SET {update} WHERE business_id=?", (self.bid,))
            with self.assertRaises(Exception), db.get_conn() as conn:
                conn.execute(f"DELETE FROM {table} WHERE business_id=?", (self.bid,))

    def test_filesystem_delete_and_client_cascade_no_partial_effects(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp, patch.object(config, "DOCS_PATH", Path(tmp)):
            name = storage.save(self.bid, "fixture.pdf", b"fixture")
            documents.add(
                self.bid,
                filename="fixture.pdf",
                stored_name=name,
                mime="application/pdf",
                size=7,
                client_id=self.client["id"],
            )
            before = self.unchanged()
            self.open()
            with self.assertRaises(HistoricalFenceActive):
                storage.delete(self.bid, name)
            with self.assertRaises(HistoricalFenceActive):
                db.delete_client_cascade(self.client["id"], self.bid)
            self.assertEqual(storage.read(self.bid, name), b"fixture")
            self.assertEqual(self.unchanged(), before)

    def test_external_dispatch_guard_prevents_provider_call_under_fence(self):
        self.open()
        with patch("noesis.verifactu_client.submit_records") as provider:
            with self.assertRaises(HistoricalFenceActive), external_guard(self.bid):
                provider({}, [])
            provider.assert_not_called()

    def test_recurring_scheduler_fenced_business_skipped_other_generates(self):
        self.schedule(auto_issue=False)
        other = db.create_business("Otro", uuid4().hex + "@example.test")
        db.set_trial(other["id"], days=14)
        client = db.add_client("Otro cliente", business_id=other["id"])
        db.add_recurring_invoice(
            other["id"],
            client["id"],
            name="Fixture",
            cadence="monthly",
            next_run_on=date.today().isoformat(),
            auto_issue=False,
            lines=[{"description": "Fixture", "quantity": 1, "unit_price": 10, "vat_rate": 21}],
        )
        self.open()
        before = self.unchanged()
        result = db.process_due_recurring_invoices(today=date.today())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["business_id"], other["id"])
        self.assertEqual(self.unchanged(), before)

    def test_fence_check_indexed_bounded_overhead(self):
        with db.get_conn() as conn:
            prefix = "EXPLAIN QUERY PLAN " if conn.dialect == "sqlite" else "EXPLAIN "
            plan = conn.execute(
                prefix + "SELECT fence_enabled FROM financial_history_control WHERE business_id=?",
                (self.bid,),
            ).fetchall()
            # Planner puede escoger sequential en tabla vacía; PK/index único existe.
            if conn.dialect == "sqlite":
                self.assertIn("PRIMARY KEY", str(plan).upper())
            start = time.perf_counter()
            for _ in range(100):
                assert_writable(conn, self.bid)
            elapsed = time.perf_counter() - start
        print(
            f"QA1.9C fence_check dialect={conn.dialect} iterations=100 elapsed_ms={elapsed * 1000:.3f}"
        )
        self.assertLess(elapsed, 10)

    def test_all_source_tables_real_rows_direct_insert_update_delete_fail_closed(self):
        db.update_verifactu_mode(self.bid, True)
        operations, original = self.prepared_captures()
        results = [
            service.execute(self.principal, operation.operation_uuid)
            for service, operation in operations
        ]
        bank = BankCapture(self.bid)
        transaction = results[2].result["bank_transaction_id"]
        db.suggest_bank_transaction(transaction, self.bid, original.result["invoice_id"])
        match = self.approved(bank, bank.review_match(self.principal, transaction))
        bank.execute(self.principal, match.operation_uuid)
        rectified = db.create_rectifying_invoice(
            original.result["invoice_id"],
            self.bid,
            concept="Rectificar",
            base="-1",
            invoice_type="R1",
            reason="Fixture",
        )
        invoice = InvoiceCapture(self.bid)
        invoice.execute(
            self.principal,
            self.approved(invoice, invoice.review(self.principal, rectified["id"])).operation_uuid,
        )
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE verifactu_outbox SET status='aceptado' WHERE business_id=? AND invoice_id=?",
                (self.bid, original.result["invoice_id"]),
            )
        db.create_invoice_cancellation_record(
            original.result["invoice_id"], self.bid, reason="Fixture"
        )
        self.document()
        self.schedule(auto_issue=False)
        db.process_due_recurring_invoices(today=date.today())
        db.add_supplier("Fixture", business_id=self.bid)
        other = db.create_business("Otro", uuid4().hex + "@example.test")
        with db.get_conn() as conn:
            rows = {
                table: conn.execute_exact(
                    f"SELECT * FROM {table} WHERE business_id=? LIMIT 1", (self.bid,)
                ).fetchone()
                for table in guarded_columns()
            }
        self.assertEqual({table for table, row in rows.items() if not row}, set())
        before = self.unchanged()
        self.open()
        for table, row in rows.items():
            for action in ("insert", "update", "delete"):
                with (
                    self.subTest(table=table, action=action),
                    self.assertRaises(HistoricalFenceActive),
                    db.get_conn() as conn,
                ):
                    if action == "insert":
                        conn.execute(
                            f"INSERT INTO {table} ({','.join(row)}) VALUES ({','.join('?' for _ in row)})",
                            tuple(row.values()),
                        )
                    elif action == "update":
                        conn.execute(
                            f"UPDATE {table} SET business_id=? WHERE business_id=?",
                            (other["id"], self.bid),
                        )
                    else:
                        conn.execute(f"DELETE FROM {table} WHERE business_id=?", (self.bid,))
        self.assertEqual(self.unchanged(), before)

    def test_response_already_sent_is_transport_and_new_dispatch_is_blocked(self):
        db.update_verifactu_mode(self.bid, True)
        invoice = self.issued()
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE verifactu_outbox SET status='enviado',attempts=1,sent_at=? WHERE business_id=?",
                (datetime.now().isoformat(), self.bid),
            )
            outbox = conn.execute(
                "SELECT * FROM verifactu_outbox WHERE business_id=?", (self.bid,)
            ).fetchone()
        self.open()
        first = self.inventory()
        db.mark_verifactu_result(
            outbox["id"],
            status="aceptado",
            csv="fixture",
            global_status="correcto",
            error_code=None,
            error_description=None,
            response="fixture response",
            wait_seconds=0,
            completed_at=datetime.now().isoformat(),
        )
        second = self.inventory()
        self.assertEqual(first["source_set_hash"], second["source_set_hash"])
        self.assertEqual(first["plan_hash"], second["plan_hash"])
        self.assertTrue(second["certifiable"])
        with self.assertRaises(HistoricalFenceActive), db.get_conn() as conn:
            conn.execute(
                "UPDATE verifactu_outbox SET attempts=attempts+1,status='enviado' WHERE business_id=?",
                (self.bid,),
            )
        with self.assertRaises(HistoricalFenceActive), db.get_conn() as conn:
            conn.execute(
                "INSERT INTO invoice_events (business_id,invoice_id,event_type,created_at) VALUES (?,?,'remision',?)",
                (self.bid, invoice["id"], datetime.now().isoformat()),
            )

    def test_scope_drift_invalidates_but_keeps_fence_and_hashes(self):
        from noesis.financial_history.readers import RawReader

        self.draft()
        self.open()
        original = RawReader.page
        reads = 0

        def corrupted(reader, kind, after=None):
            nonlocal reads
            sources = original(reader, kind, after)
            if kind == "invoice" and sources:
                reads += 1
                if reads > 1:
                    source = sources[0]
                    sources = (
                        replace(
                            source,
                            fields=dict(source.fields)
                            | {"concept_hash": hashlib.sha256(b"drift fixture").hexdigest()},
                        ),
                        *sources[1:],
                    )
            return sources

        with patch.object(RawReader, "page", corrupted):
            result = self.inventory()
        self.assertFalse(result["certifiable"])
        self.assertFalse(result["boundary_current"])
        self.assertEqual(result["result"], "BLOCKED")
        self.assertEqual(self.cut.read(self.principal, self.epoch_uuid)["state"], "invalidated")
        with self.assertRaises(HistoricalFenceActive):
            self.draft()

    def test_logging_audit_minimal_no_source_payload(self):
        with self.assertLogs("noesis.financial_history", level="INFO") as logs:
            self.open()
            self.inventory()
            with self.assertRaises(HistoricalFenceActive):
                self.draft()
            self.cut.invalidate(self.principal, self.epoch_uuid, reason="manual_abort")
            self.cut.release(self.principal, self.epoch_uuid, reason="manual_end")
        text = " ".join(logs.output)
        for action in ("opened", "T0", "manifest_frozen", "blocked", "invalidated", "released"):
            self.assertIn(action, text)
        self.assertNotIn("Servicio", text)
        with db.get_conn() as conn:
            actions = [
                row["action"]
                for row in conn.execute(
                    "SELECT action FROM financial_history_epoch_audit WHERE business_id=?",
                    (self.bid,),
                ).fetchall()
            ]
        self.assertEqual(set(actions), {"opened", "manifest_frozen", "invalidated", "released"})

    def test_revision_bump_columns_cannot_escape_hash_guard(self):
        movement = self.movement()
        received = db.add_received_invoice("10", business_id=self.bid)
        self.open()
        for sql, params in [
            (
                "UPDATE bank_transactions SET match_score=1 WHERE business_id=? AND id=?",
                (self.bid, movement),
            ),
            (
                "UPDATE received_invoices SET note=? WHERE business_id=? AND id=?",
                ("fixture", self.bid, received["id"]),
            ),
        ]:
            with self.assertRaises(HistoricalFenceActive), db.get_conn() as conn:
                conn.execute(sql, params)

    def test_reader_error_invalidates_without_auto_release(self):
        self.open()
        from noesis.financial_history.readers import RawReader

        with patch.object(RawReader, "page", side_effect=ValueError("invalid source fixture")):
            with self.assertRaises(ValueError):
                self.inventory()
        state = self.cut.read(self.principal, self.epoch_uuid)
        self.assertEqual(state["state"], "invalidated")
        self.assertTrue(state["fence_enabled"])

    def test_sql_release_revokes_stored_boundary_without_hash_rewrite(self):
        self.open()
        manifest = self.inventory()
        now = datetime.now(timezone.utc).isoformat()
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE financial_history_epochs SET state='released',fence_enabled=FALSE,released_at=?,released_by=?,release_reason='manual_sql',updated_at=? WHERE business_id=? AND epoch_uuid=?",
                (now, self.user["id"], now, self.bid, self.epoch_uuid),
            )
            cut = conn.execute(
                "SELECT * FROM financial_history_cut_manifests WHERE business_id=? AND manifest_uuid=?",
                (self.bid, str(manifest["manifest_uuid"])),
            ).fetchone()
            control = conn.execute(
                "SELECT * FROM financial_history_control WHERE business_id=?", (self.bid,)
            ).fetchone()
        self.assertFalse(cut["certifiable"])
        self.assertFalse(cut["boundary_current"])
        self.assertFalse(control["fence_enabled"])
        self.assertEqual(cut["source_set_hash"], manifest["source_set_hash"])

    def test_identical_logical_epoch_uuid_generation_in_two_tenants(self):
        first = self.open()
        other = db.create_business("Otro", uuid4().hex + "@example.test")
        db.set_trial(other["id"], days=14)
        user = db.create_user(uuid4().hex + "@example.test", "fixture", other["id"])
        other_cut = HistoryCutoff(other["id"])
        second = other_cut.open(
            Principal(user["id"], 0),
            self.epoch_uuid,
            repository_version="fixture-code",
            environment_identity="synthetic-local",
        )
        self.assertEqual(str(first["epoch_uuid"]), str(second["epoch_uuid"]))
        self.assertEqual(first["generation"], second["generation"])
        other_cut.release(Principal(user["id"], 0), self.epoch_uuid, reason="manual_end")
        db.add_expense("Otro", "1", business_id=other["id"])
        with self.assertRaises(HistoricalFenceActive):
            self.draft()

    def test_freeze_metadata_does_not_scan_sources_or_aggregate_under_gate(self):
        for _ in range(70):
            db.add_expense("Fixture", "1", business_id=self.bid)
        self.open()
        original = HistoryRepository.freeze

        def freeze(repo, values):
            with (
                patch.object(
                    HistoryRepository,
                    "source_set_hash",
                    side_effect=AssertionError("scan in freeze"),
                ),
                patch.object(
                    HistoryRepository,
                    "ordered_sources",
                    side_effect=AssertionError("page in freeze"),
                ),
            ):
                return original(repo, values)

        with patch.object(HistoryRepository, "freeze", freeze):
            result = self.inventory()
        self.assertTrue(result["certifiable"])

    def test_epoch_between_claim_and_attempt_skips_worker_without_provider(self):
        from noesis.web import scheduler

        db.update_verifactu_mode(self.bid, True)
        self.issued()
        original = db.claim_next_verifactu_submission
        opened = False

        def claim(**kwargs):
            nonlocal opened
            row = original(**kwargs)
            if row and row["business_id"] == self.bid and not opened:
                self.open()
                opened = True
            return row

        with (
            patch("noesis.verifactu_client.is_enabled", return_value=True),
            patch("noesis.verifactu_client.submit_records") as provider,
            patch.object(db, "claim_next_verifactu_submission", claim),
        ):
            self.assertEqual(scheduler.process_verifactu_outbox(limit=1), 0)
            provider.assert_not_called()
        self.assertTrue(opened)
        self.assertTrue(self.cut.read(self.principal, self.epoch_uuid)["boundary_current"])
