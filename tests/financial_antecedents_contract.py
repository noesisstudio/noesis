"""Aceptación B común: fuentes/operaciones/importación sintéticas reales."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import date
from decimal import localcontext
from uuid import uuid4
from unittest.mock import patch

from noesis import config, db, migrations
from noesis.core.persistence import FinancialSession
from noesis.financial_antecedents.contracts import (
    AntecedentRef,
    ResolutionRequest,
    Purpose as P,
    Reason as R,
    Permission,
    digest,
)
from noesis.financial_antecedents.resolver import AntecedentResolver
from noesis.financial_antecedents.schema import TABLE
from noesis.financial_operations.contracts import AccessDenied, ConflictError, Principal
from noesis.financial_history.importer import HistoryImporter
from noesis.financial_history.reconciliation import HistoryReconciliation
from noesis.financial_history.service import FLAGS
from noesis.financial_history.reconciliation_verifier import storage_hash
from noesis.invoice_capture.service import InvoiceCapture
from noesis.payment_capture.service import PaymentCapture
from noesis.bank_capture.service import BankCapture
from noesis.purchasing_capture import SupplierInvoiceCapture, ExpenseCapture
from tests.financial_history_import_contract import HistoryImportContract
from tests.financial_history_reconciliation_contract import HistoryReconciliationContract
from tests.payment_bank_capture_contract import PaymentBankCaptureContract
from tests.financial_readiness_contract import ReadinessContract


class AntecedentsContract:
    seed = HistoryImportContract.seed
    draft = HistoryImportContract.draft
    exact_storage = HistoryImportContract.exact_storage
    sources = HistoryImportContract.sources
    corruption = HistoryReconciliationContract.corruption
    approve = PaymentBankCaptureContract.approve
    captured = PaymentBankCaptureContract.captured
    approved = PaymentBankCaptureContract.approved
    payment = PaymentBankCaptureContract.payment
    imported = PaymentBankCaptureContract.imported

    def setup_antecedents(self):
        ReadinessContract.setup_readiness(self)
        self.capture, self.pay, self.bank = (
            InvoiceCapture(self.bid),
            PaymentCapture(self.bid),
            BankCapture(self.bid),
        )
        self.supplier, self.expense = SupplierInvoiceCapture(self.bid), ExpenseCapture(self.bid)
        db.update_verifactu_mode(self.bid, True)

    def event_ref(self, uid):
        with db.get_conn() as c:
            row = c.execute(
                "SELECT source_type,source_id,source_revision FROM economic_events WHERE business_id=? AND event_uuid=?",
                (self.bid, str(uid)),
            ).fetchone()
        return AntecedentRef(row["source_type"], row["source_id"], row["source_revision"], str(uid))

    def invoice_ref(self):
        return self.event_ref(self.captured().result["event_uuid"])

    @contextmanager
    def tx(self):
        with db.get_conn() as c:
            if c.dialect == "sqlite":
                c.execute("BEGIN IMMEDIATE")
            else:
                c.execute("SELECT 1")
            yield c, AntecedentResolver(FinancialSession(c), self.bid)

    def resolve(self, ref, purpose=P.CUSTOMER_PAYMENT, *, uid=None, bank=None, persist=False):
        request = ResolutionRequest(ref, purpose, bank)
        with self.tx() as (_, resolver):
            return (
                resolver.persist_resolution(self.principal, uid or uuid4(), request)
                if persist
                else resolver.resolve(self.principal, request)
            )

    def snapshot(self):
        with db.get_conn() as c:
            if c.dialect == "postgres":
                tables = [
                    r["table_name"]
                    for r in c.execute(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() AND table_type='BASE TABLE'"
                    ).fetchall()
                ]
            else:
                tables = [
                    r["name"]
                    for r in c.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    ).fetchall()
                ]
            value = {
                t: sorted(storage_hash(r) for r in c.execute_exact("SELECT * FROM " + t).fetchall())
                for t in tables
                if t != TABLE
            }
        value["flags"] = [getattr(config, f) for f in FLAGS]
        return value

    def assert_blocked(self, result, reason):
        self.assertEqual(result["outcome"], "blocked", result)
        self.assertIn(reason.value, result["reasons"])

    def historical(self):
        db.update_verifactu_mode(self.bid, False)
        self.sources(expense_unknown=True)
        importer = HistoryImporter(self.bid)
        epoch, manifest, batch, rec = (str(uuid4()) for _ in range(4))
        importer.open(
            self.principal, epoch, repository_version="fixture", environment_identity="synthetic"
        )
        importer.inventory(
            self.principal,
            epoch,
            manifest,
            repository_version="fixture",
            environment_identity="synthetic",
        )
        importer.prepare(self.principal, manifest, batch)
        importer.run(self.principal, batch)
        result = HistoryReconciliation(self.bid).reconcile(
            self.principal, epoch, manifest, batch, rec
        )
        self.assertEqual(result["result"], "PASS")
        with db.get_conn() as c:
            event = c.execute(
                "SELECT event_uuid FROM economic_events WHERE business_id=? AND source_type='expense'",
                (self.bid,),
            ).fetchone()
        return self.event_ref(event["event_uuid"])

    def test_live_invoice_resolved_and_exact_remaining_no_effect(self):
        ref = self.invoice_ref()
        before = self.snapshot()
        result = self.resolve(ref)
        self.assertEqual(result["outcome"], "resolved", result)
        self.assertEqual(
            (result["origin"], result["quality"], result["remaining"]),
            ("live", "verified_fact", "121.00"),
        )
        self.assertEqual(before, self.snapshot())

    def test_historical_original_import_e_pass_inspect_resolved_no_promotion(self):
        ref = self.historical()
        before = self.snapshot()
        result = self.resolve(ref, P.INSPECT, persist=True)
        self.assertEqual(result["result"]["outcome"], "resolved", result)
        self.assertEqual(result["result"]["quality"], "observed_state")
        self.assertEqual(result["result"]["origin"], "historical")
        self.assertEqual(before, self.snapshot())

    def test_historical_observed_cannot_void_unknown_preserved(self):
        result = self.resolve(self.historical(), P.EXPENSE_VOID)
        self.assert_blocked(result, R.OBSERVED_INSUFFICIENT)
        self.assertEqual(result["proof"]["economic_date"]["state"], "unknown")

    def test_partial_payment_exact_remaining_from_verified_events(self):
        ref = self.invoice_ref()
        self.payment(ref.source_id, "10.01")
        result = self.resolve(ref)
        self.assertEqual(result["outcome"], "resolved", result)
        self.assertEqual(result["remaining"], "110.99")

    def test_full_payment_exact_zero_not_null(self):
        ref = self.invoice_ref()
        self.payment(ref.source_id, "121.00")
        result = self.resolve(ref)
        self.assertEqual(result["outcome"], "resolved", result)
        self.assertEqual(result["remaining"], "0.00")

    def test_bank_match_evidence_only_no_payment_event_or_match(self):
        ref = self.invoice_ref()
        bank = self.event_ref(self.imported().result["event_uuid"])
        before = self.snapshot()
        result = self.resolve(ref, P.BANK_MATCH, bank=bank, persist=True)
        self.assertEqual(result["result"]["outcome"], "resolved", result)
        self.assertEqual(before, self.snapshot())

    def test_bank_match_missing_movement_blocked(self):
        self.assert_blocked(self.resolve(self.invoice_ref(), P.BANK_MATCH), R.DEPENDENCY_INVALID)

    def test_supplier_complete_state_resolves_correct_and_void(self):
        request = self.supplier.review_confirm(
            self.principal,
            total="121",
            base="100",
            vat_amount="21",
            irpf_amount="0",
            number="REC-1",
            issued_on=date.today().isoformat(),
        )
        op = self.approved(self.supplier, request)
        ref = self.event_ref(
            self.supplier.execute(self.principal, op.operation_uuid).result["event_uuid"]
        )
        for purpose in (P.SUPPLIER_CORRECT, P.SUPPLIER_VOID):
            self.assertEqual(self.resolve(ref, purpose)["outcome"], "resolved")

    def test_supplier_unknown_components_not_inferred(self):
        op = self.approved(self.supplier, self.supplier.review_confirm(self.principal, total="121"))
        ref = self.event_ref(
            self.supplier.execute(self.principal, op.operation_uuid).result["event_uuid"]
        )
        result = self.resolve(ref, P.SUPPLIER_VOID)
        self.assert_blocked(result, R.NOT_VERIFIED)
        self.assertEqual(result["proof"]["state_components"]["state"], "unknown")

    def test_expense_complete_can_resolve_void_without_voiding(self):
        op = self.approved(
            self.expense,
            self.expense.review_confirm(
                self.principal,
                concept="Material",
                amount="12.10",
                vat_amount="2.10",
                spent_on=date.today().isoformat(),
            ),
        )
        ref = self.event_ref(
            self.expense.execute(self.principal, op.operation_uuid).result["event_uuid"]
        )
        before = self.snapshot()
        self.assertEqual(self.resolve(ref, P.EXPENSE_VOID)["outcome"], "resolved")
        self.assertEqual(before, self.snapshot())

    def test_catalog_versions_unknown_purposes_reasons_float_rejected(self):
        for values in (("invoice", True, 1), ("invoice", 1, 1.0), ("unknown", 1, 1)):
            with self.assertRaises((ValueError, TypeError)):
                AntecedentRef(*values)
        ref = AntecedentRef("invoice", 1, 1)
        for purpose in ("supplier_payment.made", "generic", None):
            with self.assertRaises((ValueError, TypeError)):
                ResolutionRequest(ref, purpose)
        for version in (True, 2):
            with self.assertRaises(ValueError):
                ResolutionRequest(ref, P.RECTIFY, request_version=version)
        with self.assertRaises(ValueError):
            R("invented")
        with self.assertRaises(TypeError):
            digest({"amount": 1.0})

    def test_missing_event_legacy_invoice_unsupported(self):
        invoice = db.issue_invoice(self.draft()["id"], self.bid)
        self.assert_blocked(self.resolve(AntecedentRef("invoice", invoice["id"], 1)), R.UNSUPPORTED)

    def test_registro_anterior_not_payment(self):
        ref = self.invoice_ref()
        done = self.payment(ref.source_id)
        with self.corruption("invoice_payments") as c:
            c.execute(
                "UPDATE invoice_payments SET method='registro_anterior' WHERE business_id=? AND id=?",
                (self.bid, done.result["payment_id"]),
            )
        self.assert_blocked(self.resolve(ref), R.PAYMENT_HISTORY_INCOMPLETE)

    def test_no_event_binary_expense_is_not_verified(self):
        expense = db.add_expense("Legacy", "12.10", business_id=self.bid)
        result = self.resolve(AntecedentRef("expense", expense["id"], 1), P.EXPENSE_VOID)
        self.assert_blocked(result, R.EVENT_MISSING)
        self.assertIsNone(result["amount"])

    def test_wrong_purpose(self):
        self.assert_blocked(self.resolve(self.invoice_ref(), P.EXPENSE_VOID), R.PURPOSE_NOT_ALLOWED)

    def test_revision_drift_is_blocked(self):
        ref = self.invoice_ref()
        self.assert_blocked(self.resolve(replace(ref, revision=ref.revision + 1)), R.SOURCE_CHANGED)

    def test_same_uuid_same_context_retry_returns_original(self):
        ref, uid = self.invoice_ref(), uuid4()
        first = self.resolve(ref, uid=uid, persist=True)
        self.assertEqual(first, self.resolve(ref, uid=uid, persist=True))
        self.assertEqual(first["result"], self.resolve(ref))

    def test_same_uuid_other_purpose_conflicts(self):
        ref, uid = self.invoice_ref(), uuid4()
        self.resolve(ref, uid=uid, persist=True)
        with self.assertRaises(ConflictError):
            self.resolve(ref, P.RECTIFY, uid=uid, persist=True)

    def test_stored_resolution_revalidates_then_new_payment_stales(self):
        ref = self.invoice_ref()
        saved = self.resolve(ref, persist=True)
        with self.tx() as (_, resolver):
            self.assertEqual(saved, resolver.verify_resolution(self.principal, saved))
        self.payment(ref.source_id)
        with self.tx() as (_, resolver), self.assertRaises(ConflictError):
            resolver.verify_resolution(self.principal, saved)

    def test_no_commit_rollback_outer_transaction(self):
        ref, uid = self.invoice_ref(), uuid4()
        with self.assertRaises(RuntimeError):
            with self.tx() as (_, resolver):
                resolver.persist_resolution(
                    self.principal, uid, ResolutionRequest(ref, P.CUSTOMER_PAYMENT)
                )
                raise RuntimeError("rollback")
        with db.get_conn() as c:
            self.assertIsNone(
                c.execute(
                    f"SELECT 1 FROM {TABLE} WHERE business_id=? AND resolution_uuid=?",
                    (self.bid, str(uid)),
                ).fetchone()
            )

    def test_final_sql_update_delete_guards_and_retention(self):
        ref = self.invoice_ref()
        saved = self.resolve(ref, persist=True)
        for mutation in (
            "UPDATE " + TABLE + " SET source_hash='" + "a" * 64 + "'",
            "DELETE FROM " + TABLE,
        ):
            with self.assertRaises(Exception), db.get_conn() as c:
                c.execute(
                    mutation + " WHERE business_id=? AND resolution_uuid=?",
                    (self.bid, saved["resolution_uuid"]),
                )
        with self.assertRaisesRegex(ValueError, "antecedentes"):
            migrations.downgrade(74)
        with self.assertRaisesRegex(ValueError, "conserv"):
            db.delete_business_cascade(self.bid)

    def test_current_actor_tenant_session_permissions(self):
        ref = self.invoice_ref()
        saved = self.resolve(ref, persist=True)
        with self.tx() as (_, resolver):
            for principal in (Principal(self.principal.user_id, 999), Principal(999999, 0)):
                with self.assertRaises(AccessDenied):
                    resolver.resolve(principal, ResolutionRequest(ref, P.CUSTOMER_PAYMENT))
            for permission in (
                "financial.authorize",
                "historical.record",
                "historical_unknown",
                "financial.mandate",
            ):
                with self.assertRaises(AccessDenied):
                    resolver.resolve(
                        self.principal,
                        ResolutionRequest(ref, P.CUSTOMER_PAYMENT),
                        permission=permission,
                    )
            with self.assertRaises(AccessDenied):
                resolver.read(
                    self.principal, saved["resolution_uuid"], permission=Permission.RESOLVE
                )

    def test_wrong_tenant_refs_and_unknown_refs_uniform(self):
        ref = self.invoice_ref()
        other = db.create_business("Ajeno", uuid4().hex + "@example.test")
        for bid in (other["id"], self.bid):
            with self.tx() as (c, _), self.assertRaises(AccessDenied):
                AntecedentResolver(FinancialSession(c), bid).resolve(
                    self.principal,
                    ResolutionRequest(replace(ref, source_id=999999), P.CUSTOMER_PAYMENT),
                )
        for uid in (uuid4(),):
            with self.assertRaises(AccessDenied):
                self.resolve(replace(ref, event_uuid=str(uid)))

    def test_no_financial_provider_history_or_activation_effects(self):
        ref = self.invoice_ref()
        before = self.snapshot()
        with (
            patch("urllib.request.urlopen", side_effect=AssertionError("provider")),
            patch(
                "noesis.economic_events.service.EconomicEvents.append",
                side_effect=AssertionError("EE"),
            ),
            patch(
                "noesis.financial_operations.service.FinancialOperations.execute",
                side_effect=AssertionError("Operation"),
            ),
            patch(
                "noesis.financial_history.reconciliation.HistoryReconciliation.reconcile",
                side_effect=AssertionError("E write"),
            ),
        ):
            self.resolve(ref, persist=True)
        self.assertEqual(before, self.snapshot())

    def test_hash_order_determinism_and_precision_context(self):
        ref = self.invoice_ref()
        first = self.resolve(ref)
        self.assertEqual(first, self.resolve(ref))
        with localcontext() as ctx:
            ctx.prec = 2
            self.assertEqual(first, self.resolve(ref))
        self.assertEqual(digest({"b": 2, "a": 1}), digest({"a": 1, "b": 2}))
        self.assertNotEqual(digest({"a": 1}), digest({"a": 2}))

    def test_missing_previous_payment_event_or_coverage_blocked(self):
        ref = self.invoice_ref()
        paid = self.payment(ref.source_id)
        with self.corruption("payment_economic_coverage") as c:
            c.execute(
                "DELETE FROM payment_economic_coverage WHERE business_id=? AND payment_id=?",
                (self.bid, paid.result["payment_id"]),
            )
        self.assert_blocked(self.resolve(ref), R.PAYMENT_HISTORY_INCOMPLETE)

    def test_false_paid_status_no_payment_not_satisfied(self):
        ref = self.invoice_ref()
        with self.corruption("invoices") as c:
            c.execute(
                "UPDATE invoices SET status='cobrada' WHERE business_id=? AND id=?",
                (self.bid, ref.source_id),
            )
        self.assert_blocked(self.resolve(ref), R.PAYMENT_HISTORY_INCOMPLETE)

    def test_corrupt_event_content_detected(self):
        ref = self.invoice_ref()
        with self.corruption("economic_events") as c:
            c.execute(
                "UPDATE economic_events SET content_hash=? WHERE business_id=? AND event_uuid=?",
                ("a" * 64, self.bid, ref.event_uuid),
            )
        self.assert_blocked(self.resolve(ref), R.EVENT_INVALID)

    def test_wrong_operation_detected(self):
        ref = self.invoice_ref()
        with self.corruption("financial_operations") as c:
            c.execute(
                "UPDATE financial_operations SET state='prepared' WHERE business_id=?", (self.bid,)
            )
        self.assert_blocked(self.resolve(ref), R.OPERATION_INVALID)

    def test_wrong_authorization_detected(self):
        ref = self.invoice_ref()
        with self.corruption("financial_authorizations") as c:
            c.execute(
                "UPDATE financial_authorizations SET approved_request_hash=? WHERE business_id=?",
                ("a" * 64, self.bid),
            )
        self.assert_blocked(self.resolve(ref), R.AUTHORIZATION_INVALID)

    def test_missing_coverage_detected(self):
        ref = self.invoice_ref()
        with self.corruption("invoice_economic_coverage") as c:
            c.execute("DELETE FROM invoice_economic_coverage WHERE business_id=?", (self.bid,))
        self.assert_blocked(self.resolve(ref), R.COVERAGE_INCOMPLETE)

    def test_missing_dependency_detected(self):
        ref = self.invoice_ref()
        paid = self.payment(ref.source_id)
        with self.corruption("economic_event_links") as c:
            c.execute(
                "DELETE FROM economic_event_links WHERE business_id=? AND event_uuid=?",
                (self.bid, paid.result["event_uuid"]),
            )
        self.assert_blocked(self.resolve(ref), R.DEPENDENCY_INVALID)

    def test_historical_proof_corruption_not_repaired(self):
        ref = self.historical()
        with self.corruption("financial_history_import_items") as c:
            c.execute(
                "UPDATE financial_history_import_items SET identity_hash=? WHERE business_id=? AND event_uuid=?",
                ("a" * 64, self.bid, ref.event_uuid),
            )
        self.assert_blocked(self.resolve(ref, P.INSPECT), R.HISTORICAL_INVALID)

    def test_fiscal_cancel_resolves_only_evidence_no_cancellation(self):
        ref = self.invoice_ref()
        before = self.snapshot()
        self.assertEqual(self.resolve(ref, P.FISCAL_CANCEL)["outcome"], "resolved")
        self.assertEqual(before, self.snapshot())

    def test_rectification_requires_exact_original(self):
        ref = self.invoice_ref()
        self.assertEqual(self.resolve(ref, P.RECTIFY)["outcome"], "resolved")
        self.assert_blocked(self.resolve(replace(ref, revision=1), P.RECTIFY), R.SOURCE_CHANGED)

    def test_blocked_resolution_can_be_durable_and_retried(self):
        legacy = db.add_expense("Sin evidencia", "12.10", business_id=self.bid)
        ref, uid = AntecedentRef("expense", legacy["id"], 1), uuid4()
        before = self.snapshot()
        saved = self.resolve(ref, P.EXPENSE_VOID, uid=uid, persist=True)
        self.assertEqual(saved["result"]["outcome"], "blocked")
        self.assertEqual(saved, self.resolve(ref, P.EXPENSE_VOID, uid=uid, persist=True))
        self.assertEqual(before, self.snapshot())

    def test_extra_dependency_not_silently_accepted(self):
        ref = self.invoice_ref()
        with self.corruption("economic_event_links") as c:
            c.execute(
                "INSERT INTO economic_event_links (business_id,event_uuid,target_event_uuid,relation_type,recorded_at) VALUES (?,?,?,'rectifies','2026-10-06T00:00:00+00:00')",
                (self.bid, ref.event_uuid, ref.event_uuid),
            )
        self.assert_blocked(self.resolve(ref), R.DEPENDENCY_INVALID)

    def test_historical_invoice_v2_not_alternative_path(self):
        ref = self.invoice_ref()
        with self.corruption("economic_events") as c:
            c.execute(
                "UPDATE economic_events SET origin='historical' WHERE business_id=? AND event_uuid=?",
                (self.bid, ref.event_uuid),
            )
        self.assert_blocked(self.resolve(ref), R.UNSUPPORTED)

    def test_stored_read_rejects_content_hash_corruption(self):
        saved = self.resolve(self.invoice_ref(), persist=True)
        with self.corruption(TABLE) as c:
            c.execute(
                f"UPDATE {TABLE} SET content_hash=? WHERE business_id=? AND resolution_uuid=?",
                ("a" * 64, self.bid, saved["resolution_uuid"]),
            )
        with self.tx() as (_, resolver), self.assertRaises(ConflictError):
            resolver.read(self.principal, saved["resolution_uuid"])

    def test_direct_sql_invalid_origin_quality_purpose_and_proof_rejected(self):
        saved = self.resolve(self.invoice_ref(), persist=True)
        with db.get_conn() as c:
            original = dict(
                c.execute_exact(
                    f"SELECT * FROM {TABLE} WHERE business_id=? AND resolution_uuid=?",
                    (self.bid, saved["resolution_uuid"]),
                ).fetchone()
            )
        cases = (
            {"origin": "other"},
            {"origin": "historical"},
            {"quality": "observed_state"},
            {"quality": "generic"},
            {"purpose": "generic"},
            {"event_uuid": None},
            {"known_unknown_canonical": "{}"},
            {"event_content_hash": "b" * 64},
            {"business_id": 999999},
        )
        for change in cases:
            with self.subTest(change=change), self.assertRaises(Exception), db.get_conn() as c:
                row = original | change | {"resolution_uuid": str(uuid4())}
                c.execute_exact(
                    f"INSERT INTO {TABLE} ("
                    + ",".join(row)
                    + ") VALUES ("
                    + ",".join("?" for _ in row)
                    + ")",
                    tuple(row.values()),
                )

    def test_fiscal_evidence_missing_remains_blocked(self):
        ref = self.invoice_ref()
        with self.corruption("invoice_records") as c:
            c.execute(
                "UPDATE invoice_records SET record_hash=? WHERE business_id=? AND invoice_id=?",
                ("a" * 64, self.bid, ref.source_id),
            )
        self.assert_blocked(self.resolve(ref, P.FISCAL_CANCEL), R.FISCAL_INCOMPLETE)

    def test_null_relevant_source_money_cannot_gain_certainty(self):
        request = self.supplier.review_confirm(
            self.principal,
            total="121",
            base="100",
            vat_amount="21",
            irpf_amount="0",
            number="REC1",
            issued_on=date.today().isoformat(),
        )
        result = self.supplier.execute(
            self.principal, self.approved(self.supplier, request).operation_uuid
        )
        ref = self.event_ref(result.result["event_uuid"])
        with self.corruption("received_invoices") as c:
            c.execute(
                "UPDATE received_invoices SET base=NULL WHERE business_id=? AND id=?",
                (self.bid, ref.source_id),
            )
        self.assert_blocked(self.resolve(ref, P.SUPPLIER_VOID), R.SOURCE_CHANGED)

    def test_orphan_payment_event_cannot_disappear_from_balance(self):
        ref = self.invoice_ref()
        paid = self.payment(ref.source_id)
        with self.corruption("payment_economic_coverage") as c:
            c.execute(
                "DELETE FROM payment_economic_coverage WHERE business_id=? AND payment_id=?",
                (self.bid, paid.result["payment_id"]),
            )
        with self.corruption("invoice_payments") as c:
            c.execute(
                "DELETE FROM invoice_payments WHERE business_id=? AND id=?",
                (self.bid, paid.result["payment_id"]),
            )
        with self.corruption("invoices") as c:
            c.execute(
                "UPDATE invoices SET status='enviada',paid_at=NULL WHERE business_id=? AND id=?",
                (self.bid, ref.source_id),
            )
        self.assert_blocked(self.resolve(ref), R.PAYMENT_HISTORY_INCOMPLETE)

    def test_fiscal_mode_change_invalidates_stored_context(self):
        saved = self.resolve(self.invoice_ref(), persist=True)
        db.update_verifactu_mode(self.bid, False)
        with self.tx() as (_, resolver), self.assertRaises(ConflictError):
            resolver.verify_resolution(self.principal, saved)

    def test_historical_e_hash_corruption_blocked(self):
        ref = self.historical()
        with self.corruption("financial_history_reconciliations") as c:
            c.execute(
                "UPDATE financial_history_reconciliations SET result_hash=? WHERE business_id=?",
                ("a" * 64, self.bid),
            )
        self.assert_blocked(self.resolve(ref, P.INSPECT), R.HISTORICAL_INVALID)

    def test_supplier_corrected_chain_resolves_new_revision_only(self):
        request = self.supplier.review_confirm(
            self.principal,
            total="121",
            base="100",
            vat_amount="21",
            irpf_amount="0",
            number="REC1",
            issued_on=date.today().isoformat(),
        )
        first = self.supplier.execute(
            self.principal, self.approved(self.supplier, request).operation_uuid
        )
        old = self.event_ref(first.result["event_uuid"])
        request = self.supplier.review_correct(
            self.principal,
            old.source_id,
            reason="Corrección",
            total="242",
            base="200",
            vat_amount="42",
        )
        next_op = self.supplier.execute(
            self.principal, self.approved(self.supplier, request).operation_uuid
        )
        ref = self.event_ref(next_op.result["event_uuid"])
        self.assertEqual(self.resolve(ref, P.SUPPLIER_VOID)["outcome"], "resolved")
        self.assert_blocked(self.resolve(old, P.SUPPLIER_VOID), R.SOURCE_CHANGED)
