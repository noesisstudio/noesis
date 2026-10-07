"""E: fixtures sintéticos, nunca datos reales ni proveedor externo."""

from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from noesis import config, db, migrations
from noesis.core.persistence import FinancialSession
from noesis.financial_activation.contracts import Capability as C, Profile
from noesis.financial_privacy.schema import INVENTORIES, PLANS
from noesis.financial_operations.contracts import AccessDenied, ConflictError, Principal, StateError
from noesis.financial_privacy.contracts import Category, PolicyStatus, RetentionMode, canonical, digest, evidence_value
from noesis.financial_privacy.export import FinancialEvidenceExporter, verify_export
from noesis.financial_privacy.retention import provisional_policy, register_policy, inventory, verify_inventory, readiness_evidence
from noesis.financial_privacy.closure import FinancialClosure
from noesis.financial_privacy.schema import TABLES, POLICIES, AUTHORIZATIONS, RECEIPTS, TOMBSTONES, EXPORTS
from tests.financial_readiness_contract import ReadinessContract
from tests.test_financial_activation_handoff import HandoffSQLite


def synthetic_approved_policy():
    value = provisional_policy(uuid4())
    value.update(status=PolicyStatus.APPROVED.value, reference="synthetic-test-only-not-legal-approval")
    for r in value["rules"]:
        r.update(basis_reference=value["reference"], review_status=PolicyStatus.APPROVED.value, mode=RetentionMode.RETAIN.value)
        if r["category"] == Category.CREDENTIAL:
            r["mode"] = RetentionMode.INVALIDATE.value
        elif r["category"] in (Category.COMMUNICATION, Category.PERSONAL):
            r["mode"] = RetentionMode.MINIMIZE.value
    return value


class PrivacyContract:
    seed = ReadinessContract.seed
    setup_readiness = ReadinessContract.setup_readiness
    cut = ReadinessContract.cut
    draft = ReadinessContract.draft
    issued = ReadinessContract.issued
    approved = ReadinessContract.approved
    fixture_full = HandoffSQLite.fixture_full
    approved_request = HandoffSQLite.approved_request
    enable = HandoffSQLite.enable

    def setup_privacy(self):
        self.setup_readiness()
        self.exporter = FinancialEvidenceExporter(self.bid, code_version="fixture")
        self.close = FinancialClosure(self.bid)

    def session(self):
        return db.get_conn()

    def policy(self, *, approved=True):
        value = synthetic_approved_policy() if approved else provisional_policy(uuid4())
        with db.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            register_policy(FinancialSession(conn), self.bid, self.principal, value, approved_hash=digest(value) if approved else None)
        return value

    def closure_plan(self, *, approved=True):
        policy = self.policy(approved=approved)
        request = db.create_privacy_request(self.bid, requester_user_id=self.user["id"], request_type="account_closure", retention_required=True)
        self.exporter.export(self.principal, uuid4(), "account_closure")
        plan = self.close.plan(self.principal, uuid4(), privacy_request_id=request["id"], policy_uuid=policy["policy_uuid"])
        return plan

    def authorized(self, plan=None):
        plan = plan or self.closure_plan()
        auth = self.close.authorize(self.principal, plan["plan_uuid"], approved_hash=digest(plan))
        return plan, auth

    def applied(self):
        plan, auth = self.authorized()
        return self.close.apply(self.principal, plan["plan_uuid"], authorization_uuid=auth["authorization_uuid"])

    def rows(self, table):
        with db.get_conn() as conn:
            return conn.execute_exact(f"SELECT * FROM {table} WHERE business_id=? ORDER BY 1,2", (self.bid,)).fetchall()

    def test_decimal_and_binary_are_distinct_evidence(self):
        self.assertEqual(evidence_value(Decimal("123456789012345.01")), "123456789012345.01")
        self.assertFalse(evidence_value(0.1)["exact_money"])
        self.assertEqual(evidence_value(0.1)["legacy_binary64"], (0.1).hex())
        for value in (float("nan"), float("inf"), Decimal("NaN")):
            with self.assertRaises(ValueError):
                evidence_value(value)
        with self.assertRaises(TypeError):
            canonical({"nested": [0.1]})
        self.assertIsNone(evidence_value(None))

    def test_export_closed_purpose(self):
        with self.assertRaises(ValueError):
            self.exporter.export(self.principal, uuid4(), "ai_export")

    def test_manifest_unknown_version_extra_missing_and_actor_tampering(self):
        original = self.exporter.export(self.principal, uuid4())
        for edit in (lambda m: m.update(contract_version=2), lambda m: m.update(contract_version=True),
                     lambda m: m.update(extra=True), lambda m: m.pop("purpose"),
                     lambda m: m.update(created_by=self.user["id"] + 100), lambda m: m.update(session_version=True)):
            value = json.loads(canonical(original))
            edit(value["manifest"])
            with self.assertRaises((ValueError, ConflictError)):
                verify_export(value)

    def test_chat_content_excluded_even_from_compatibility_evidence(self):
        marker = "SYNTHETIC-CHAT-CONTENT-NOT-FINANCIAL"
        with db.get_conn() as c:
            c.execute("INSERT INTO assistant_messages(business_id,channel,role,content,created_at) VALUES (?,'web','user',?,?)", (self.bid, marker, db._now()))
        value = self.exporter.export(self.principal, uuid4(), include_legacy=True)
        self.assertNotIn(marker, canonical(value))
        self.assertEqual(value["sections"]["assistant_messages"], [])

    def test_export_501_outbox_rows_without_body_or_truncation(self):
        with db.get_conn() as c:
            for n in range(501):
                c.execute("INSERT INTO email_outbox(business_id,to_email,subject,text_body,idempotency_key,status,next_attempt_at,created_at,updated_at) VALUES (?,'synthetic@example.test','Prueba','SYNTHETIC-BODY-EXCLUDED',?,'queued',?,?,?)", (self.bid, str(uuid4()), db._now(), db._now(), db._now()))
        value = self.exporter.export(self.principal, uuid4(), include_legacy=True)
        self.assertEqual(value["manifest"]["sections"]["email_outbox"]["count"], 501)
        self.assertNotIn("SYNTHETIC-BODY-EXCLUDED", canonical(value))

    def test_inventory_field_allowlist_does_not_grant_table_purge(self):
        policy = self.policy()
        with db.get_conn() as c:
            c.execute("BEGIN IMMEDIATE")
            inv = inventory(FinancialSession(c), self.bid, self.principal, uuid4(), policy["policy_uuid"])
        self.assertEqual(inv["sections"]["clients"]["eligible_fields"], ["phone", "email", "address", "zone"])
        self.assertEqual(inv["sections"]["jobs"]["eligible_fields"], [])
        self.assertEqual(inv["sections"]["jobs"]["other_fields"], "retained_no_action_v1")

    def test_closure_never_deletes_files_and_retains_fiscal_identity(self):
        before = db.get_client(self.client["id"], self.bid)
        with patch.object(Path, "unlink", side_effect=AssertionError("E no borra bytes")):
            receipt = self.applied()
        after = db.get_client(self.client["id"], self.bid)
        self.assertEqual((before["name"], before["nif"]), (after["name"], after["nif"]))
        self.assertEqual(receipt["action_counts"]["clients"]["fields"], ["phone", "email", "address", "zone"])
        self.assertEqual(receipt["action_counts"]["clients"]["document_bytes_deleted"], 0)

    def test_provisional_cannot_be_approved_or_wrong_permission(self):
        from noesis.financial_privacy.contracts import validate_policy
        value = provisional_policy(uuid4())
        boolean = dict(value, version=True)
        with self.assertRaises(ValueError):
            validate_policy(boolean)
        for args in ({"approved_hash": digest(value)}, {"permission": "financial.authorize"}):
            with self.assertRaises(AccessDenied), db.get_conn() as c:
                register_policy(FinancialSession(c), self.bid, self.principal, value, **args)

    def test_e_uses_exact_session_even_for_schema_lookup(self):
        policy = self.policy()
        with patch.object(db, "_normalise_row", side_effect=AssertionError("Cursor financiero no exacto")):
            value = self.exporter.export(self.principal, uuid4())
            with db.get_conn() as c:
                c.execute("BEGIN IMMEDIATE")
                inv = inventory(FinancialSession(c), self.bid, self.principal, uuid4(), policy["policy_uuid"])
        self.assertTrue(verify_export(value))
        self.assertEqual(inv["business_id"], self.bid)

    def test_captured_payment_and_bank_client_strong_subgraph(self):
        from noesis.invoice_capture.service import InvoiceCapture
        from noesis.payment_capture.service import PaymentCapture
        from noesis.bank_capture.service import BankCapture
        from tests.invoice_capture_contract import InvoiceCaptureContract
        from tests.payment_bank_capture_contract import PaymentBankCaptureContract
        self.capture = InvoiceCapture(self.bid)
        self.approve = lambda iid: InvoiceCaptureContract.approve(self, iid)
        self.pay, self.bank = PaymentCapture(self.bid), BankCapture(self.bid)
        own = InvoiceCaptureContract.captured(self).result["invoice_id"]
        paid = PaymentBankCaptureContract.payment(self, own)
        imported = PaymentBankCaptureContract.imported(self, amount="11.00")
        bank_id = imported.result["bank_transaction_id"]
        db.suggest_bank_transaction(bank_id, self.bid, own)
        match = self.approved(self.bank, self.bank.review_match(self.principal, bank_id))
        self.bank.execute(self.principal, match.operation_uuid)
        other = db.add_client("Otro", business_id=self.bid)
        db.add_invoice(other["id"], "Ajeno", 1, business_id=self.bid)
        export = self.exporter.export(self.principal, uuid4(), client_id=self.client["id"])
        events = export["sections"]["economic_events"]
        self.assertEqual({e["event_type"] for e in events}, {"invoice.issued", "customer_payment.received", "bank_transaction.imported", "bank_transaction.matched"})
        self.assertEqual(len(export["sections"]["invoice_payments"]), 2)
        self.assertIn(paid.result["payment_id"], {p["id"] for p in export["sections"]["invoice_payments"]})
        self.assertEqual(len(export["sections"]["bank_transactions"]), 1)
        self.assertTrue(verify_export(export))

    def test_export_deterministic_hash_and_idempotent_manifest(self):
        uid = uuid4()
        a = self.exporter.export(self.principal, uid)
        b = self.exporter.export(self.principal, uid)
        self.assertEqual(canonical(a), canonical(b))
        self.assertTrue(verify_export(a))
        self.assertEqual(len(self.rows(EXPORTS)), 1)
        changed = json.loads(canonical(a))
        changed["sections"]["invoices"].append({"forged": True})
        with self.assertRaises(ConflictError):
            verify_export(changed)

    def test_same_uuid_other_purpose_conflict(self):
        uid = uuid4()
        self.exporter.export(self.principal, uid, "audit")
        with self.assertRaises(ConflictError):
            self.exporter.export(self.principal, uid, "portability")

    def test_same_uuid_changed_source_conflict(self):
        uid = uuid4()
        self.exporter.export(self.principal, uid)
        db.add_expense("Sintético", 10, business_id=self.bid)
        with self.assertRaises(ConflictError):
            self.exporter.export(self.principal, uid)

    def test_other_tenant_principal_rejected(self):
        other = db.create_business("Otro", "other@example.test")
        user = db.create_user(uuid4().hex + "@example.test", "fixture", other["id"])
        with self.assertRaises(AccessDenied):
            self.exporter.export(Principal(user["id"], 0), uuid4())
        with self.assertRaises(AccessDenied):
            self.close.plan(Principal(user["id"], 0), uuid4(), privacy_request_id=1, policy_uuid=uuid4())

    def test_stale_and_missing_principal_rejected(self):
        for principal in (None, Principal(self.user["id"], 99)):
            with self.assertRaises(AccessDenied):
                self.exporter.export(principal, uuid4())

    def test_client_subgraph_excludes_other_client(self):
        other = db.add_client("Otra persona", business_id=self.bid)
        own = db.add_invoice(self.client["id"], "Propio", 10, business_id=self.bid)
        foreign = db.add_invoice(other["id"], "Ajeno", 20, business_id=self.bid)
        result = self.exporter.export(self.principal, uuid4(), client_id=self.client["id"])
        self.assertEqual([r["id"] for r in result["sections"]["invoices"]], [own["id"]])
        self.assertNotIn(foreign["id"], [r["id"] for r in result["sections"]["invoices"]])
        otherbiz = db.create_business("Ajeno", "foreign@example.test")
        foreignclient = db.add_client("Ajeno", business_id=otherbiz["id"])
        self.assertIsNone(self.exporter.export(self.principal, uuid4(), client_id=foreignclient["id"]))

    def test_export_never_truncates_501_bank_rows(self):
        with db.get_conn() as conn:
            for index in range(501):
                conn.execute("INSERT INTO bank_transactions(business_id,import_hash,booked_on,amount,currency,description,status,created_at) VALUES (?,?,?,?,'EUR','Sintético','imported',?)", (self.bid, str(uuid4()), "2026-10-07", "0.10", "2026-10-07T00:00:00+00:00"))
        result = self.exporter.export(self.principal, uuid4())
        self.assertEqual(result["manifest"]["sections"]["bank_transactions"]["count"], 501)
        self.assertTrue(verify_export(result))

    def test_no_export_secret_or_filesystem_path(self):
        secret = "synthetic-sensitive-unique-marker"  # pragma: allowlist secret
        with db.get_conn() as conn:
            conn.execute("UPDATE users SET password_hash=? WHERE id=?", (secret, self.user["id"]))
            conn.execute("UPDATE businesses SET gestoria_token=?,calendar_token=? WHERE id=?", (secret, secret, self.bid))
            conn.execute("INSERT INTO oauth_credentials(business_id,provider,refresh_token,access_token,created_at,updated_at) VALUES (?,'google',?,?,?,?)", (self.bid, secret, secret, db._now(), db._now()))
            conn.execute("INSERT INTO password_resets(user_id,token_hash,expires_at,created_at) VALUES (?,?,?,?)", (self.user["id"], secret, db._now(), db._now()))
        value = self.exporter.export(self.principal, uuid4(), include_legacy=True)
        serialized = canonical(value)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("financial_execution_verifier_key", serialized)
        self.assertNotIn("password_hash", serialized)
        self.assertNotIn("stored_name", serialized)

    def test_default_policy_pending_does_not_clear_privacy(self):
        self.policy(approved=False)
        self.exporter.export(self.principal, uuid4())
        with db.get_conn() as conn:
            e = readiness_evidence(FinancialSession(conn), self.bid)
        self.assertTrue(e["export_ready"])
        self.assertFalse(e["privacy_ready"])

    def test_policy_approval_requires_exact_human_hash(self):
        p = synthetic_approved_policy()
        with db.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            with self.assertRaises(AccessDenied):
                register_policy(FinancialSession(conn), self.bid, self.principal, p)
        self.assertEqual(self.rows(POLICIES), [])

    def test_approved_synthetic_policy_removes_only_e_reasons(self):
        self.policy()
        self.exporter.export(self.principal, uuid4())
        with db.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            from noesis.financial_activation.evaluator import FinancialReadinessEvaluator
            value = FinancialReadinessEvaluator(FinancialSession(conn), self.bid).evaluate(
                self.principal, uuid4(), Profile((C.BANK_IMPORT, C.EMAIL)), code_version="fixture")
        reasons = {r for proof in value["capabilities"] for r in proof["reasons"]}
        self.assertNotIn("PRIVACY_NOT_READY", reasons)
        self.assertNotIn("EXPORT_NOT_READY", reasons)
        self.assertIn("BANK_EVIDENCE_UNVALIDATED", reasons)
        self.assertIn("PROVIDER_PREFLIGHT_MISSING", reasons)

    def test_pending_operations_block_closure(self):
        from noesis.financial_operations.contracts import EntryIdentity
        from noesis.purchasing_capture.service import ExpenseCapture
        service = ExpenseCapture(self.bid)
        request = service.review_confirm(self.principal, concept="Pendiente", amount="10.00")
        service.prepare(self.principal, EntryIdentity.web_api(uuid4()), request)
        plan = self.closure_plan()
        with self.assertRaisesRegex(StateError, "EXECUTABLE_OPERATIONS_PENDING"):
            self.close.authorize(self.principal, plan["plan_uuid"], approved_hash=digest(plan))

    def test_uncertain_dispatch_blocks_closure_without_retry(self):
        db.enqueue_email_message(business_id=self.bid, to_email="fixture@example.test", subject="Sintético", text_body="Sintético")
        with db.get_conn() as conn:
            conn.execute("UPDATE email_outbox SET status='processing',locked_at=? WHERE business_id=?", (db._now(), self.bid))
        before = self.rows("email_outbox")
        plan = self.closure_plan()
        with self.assertRaisesRegex(StateError, "UNCERTAIN_DISPATCH"):
            self.close.authorize(self.principal, plan["plan_uuid"], approved_hash=digest(plan))
        self.assertEqual(before, self.rows("email_outbox"))

    def test_closed_outboxes_cannot_be_claimed(self):
        db.enqueue_email_message(business_id=self.bid, to_email="fixture@example.test", subject="Sintético", text_body="Sintético")
        self.applied()
        self.assertIsNone(db.claim_next_email_message(now="2099-01-01", stale_before="2098-01-01"))

    def test_direct_policy_approval_update_rejected(self):
        value = self.policy(approved=False)
        with self.assertRaises(db.DatabaseError):
            with db.get_conn() as conn:
                conn.execute(f"UPDATE {POLICIES} SET status='approved_for_operation' WHERE business_id=? AND evidence_uuid=?", (self.bid, value["policy_uuid"]))

    def test_apply_without_exact_authority_rejected(self):
        plan = self.closure_plan()
        with self.assertRaises(AccessDenied):
            self.close.apply(self.principal, plan["plan_uuid"], authorization_uuid=uuid4())
        self.assertEqual(self.rows(RECEIPTS), [])

    def test_retained_client_erasure_is_explicitly_blocked(self):
        invoice = db.add_invoice(self.client["id"], "Sintético", 10, business_id=self.bid)
        db.issue_invoice(invoice["id"], business_id=self.bid)
        before = self.rows("clients")
        with self.assertRaises(ValueError):
            db.delete_client_cascade(self.client["id"], self.bid)
        self.assertEqual(before, self.rows("clients"))

    def test_approved_client_minimization_preserves_invoices_and_other_client(self):
        self.policy()
        other = db.add_client("Contacto ajeno", phone="600000001", email="other@example.test", business_id=self.bid)
        db.update_client(self.client["id"], business_id=self.bid, phone="600000002", email="own@example.test")
        invoice = db.add_invoice(self.client["id"], "Sintético", 10, business_id=self.bid)
        db.issue_invoice(invoice["id"], business_id=self.bid)
        before = self.rows("invoice_records")
        self.assertTrue(db.delete_client_cascade(self.client["id"], self.bid, principal=self.principal))
        self.assertEqual(before, self.rows("invoice_records"))
        self.assertIsNone(db.get_client(self.client["id"], self.bid)["phone"])
        self.assertEqual(db.get_client(other["id"], self.bid)["phone"], "600000001")
        self.assertEqual(len(self.rows("financial_client_erasure_receipts")), 1)
        self.assertEqual(len(self.rows(TOMBSTONES)), 1)
        self.assertTrue(db.delete_client_cascade(self.client["id"], self.bid, principal=self.principal))

    def test_before_plan_and_after_inventory_crashes_rollback(self):
        policy = self.policy()
        request = db.create_privacy_request(self.bid, requester_user_id=self.user["id"], request_type="account_closure")
        for point in ("before_plan", "after_inventory"):
            def crash(current, s):
                if current == point:
                    raise RuntimeError("synthetic crash")
            with self.assertRaises(RuntimeError):
                self.close.plan(self.principal, uuid4(), privacy_request_id=request["id"], policy_uuid=policy["policy_uuid"], checkpoint=crash)
            self.assertEqual(self.rows(INVENTORIES), [])
            self.assertEqual(self.rows(PLANS), [])

    def test_after_authority_crash_rolls_back_formal_restriction(self):
        plan = self.closure_plan()
        def crash(point, s):
            raise RuntimeError("synthetic crash")
        with self.assertRaises(RuntimeError):
            self.close.authorize(self.principal, plan["plan_uuid"], approved_hash=digest(plan), checkpoint=crash)
        self.assertEqual(self.rows(AUTHORIZATIONS), [])
        self.assertTrue(db.add_expense("Todavía abierta", 1, business_id=self.bid))

    def test_unknown_policy_version_extra_fields_and_dates_rejected(self):
        from noesis.financial_privacy.contracts import validate_policy
        for mutate in (lambda v: v.update(version=2), lambda v: v.update(extra=True),
                       lambda v: v["rules"][0].update(purge_after="2030-01-01")):
            value = synthetic_approved_policy()
            mutate(value)
            with self.assertRaises(ValueError):
                validate_policy(value)

    def test_unknown_restore_bundle_is_fail_closed(self):
        from noesis.financial_privacy.restore import prepare_restored_database, restore_bundle
        with db.get_conn() as conn:
            s = FinancialSession(conn)
            with self.assertRaises(StateError):
                prepare_restored_database(s, None)
            bundle = restore_bundle(s)
            bundle["signature"] = "0" * 64
            with self.assertRaises(StateError):
                prepare_restored_database(s, bundle)

    def test_inventory_has_counts_hashes_no_personal_copy(self):
        p = self.policy()
        with db.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            value = inventory(FinancialSession(conn), self.bid, self.principal, uuid4(), p["policy_uuid"])
            verify_inventory(FinancialSession(conn), self.bid, value)
        self.assertNotIn(self.business["name"], canonical(value))
        self.assertEqual(value["sections"]["users"]["count"], 1)
        self.assertIsNone(value["sections"]["users"]["approved_purge_date"])

    def test_inventory_stale_after_source_change(self):
        p = self.policy()
        with db.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            value = inventory(FinancialSession(conn), self.bid, self.principal, uuid4(), p["policy_uuid"])
        db.add_expense("Cambió", 10, business_id=self.bid)
        with db.get_conn() as conn:
            with self.assertRaises(ConflictError):
                verify_inventory(FinancialSession(conn), self.bid, value)

    def test_administrative_request_has_no_financial_effect(self):
        db.create_privacy_request(self.bid, requester_user_id=self.user["id"], request_type="account_closure")
        self.assertTrue(db.add_expense("Permitido", 1, business_id=self.bid))
        self.assertEqual(self.rows(AUTHORIZATIONS), [])

    def test_provisional_plan_is_dry_run_and_cannot_authorize(self):
        plan = self.closure_plan(approved=False)
        with self.assertRaises(StateError):
            self.close.authorize(self.principal, plan["plan_uuid"], approved_hash=digest(plan))
        self.assertTrue(db.get_user(self.user["id"])["is_active"])

    def test_plan_same_uuid_is_idempotent(self):
        plan = self.closure_plan()
        self.assertEqual(plan, self.close.plan(self.principal, plan["plan_uuid"], privacy_request_id=plan["privacy_request_id"], policy_uuid=plan["policy_uuid"]))

    def test_closure_wrong_hash_rejected(self):
        plan = self.closure_plan()
        with self.assertRaises(AccessDenied):
            self.close.authorize(self.principal, plan["plan_uuid"], approved_hash="0" * 64)
        self.assertEqual(self.rows(AUTHORIZATIONS), [])

    def test_formal_authorization_blocks_legacy_before_apply(self):
        expense = db.add_expense("Fuente conservada", 1, business_id=self.bid)
        self.authorized()
        with self.assertRaises(StateError):
            db.add_expense("Bloqueado", 1, business_id=self.bid)
        with self.assertRaises(db.DatabaseError):
            with db.get_conn() as conn:
                conn.execute("INSERT INTO expenses(business_id,concept,amount,vat_rate,spent_on,created_at) VALUES (?,'SQL',1,21,'2026-10-07','2026-10-07')", (self.bid,))
        other = db.create_business("Otro destino sintético", uuid4().hex + "@example.test")
        with self.assertRaises(db.DatabaseError), db.get_conn() as conn:
            conn.execute("UPDATE expenses SET business_id=? WHERE business_id=? AND id=?", (other["id"], self.bid, expense["id"]))
        self.assertEqual(len(self.rows("expenses")), 1)

    def test_closure_receipt_tombstone_and_retry(self):
        result = self.applied()
        self.assertEqual(result["final_state"], "closed_restricted")
        self.assertFalse(db.get_user(self.user["id"])["is_active"])
        self.assertEqual(result, self.close.apply(self.principal, result["plan_uuid"], authorization_uuid=result["authorization_uuid"]))
        self.assertEqual(len(self.rows(RECEIPTS)), 1)
        self.assertEqual(len(self.rows(TOMBSTONES)), 1)
        from noesis.financial_privacy.contracts import tombstone_actions
        tomb = json.loads(self.rows(TOMBSTONES)[0]["body_canonical"])
        self.assertEqual(set(tomb), {"version", "business_id", "closure_uuid", "scope", "category", "policy_uuid", "selector_version", "selector", "evidence_hash", "applied_at"})
        self.assertNotIn("actions", tomb)
        self.assertEqual(set(tombstone_actions(tomb)), set(result["actions"]))
        for invalid in ({**tomb, "actions": []}, {**tomb, "category": ["unknown"]}, {**tomb, "category": []}, {**tomb, "version": True}):
            with self.assertRaises(StateError):
                tombstone_actions(invalid)
        self.assertEqual(self.rows(TOMBSTONES)[0]["content_hash"], digest(tomb))

    def test_closed_export_control_plane_is_scoped_read_only(self):
        self.applied()
        with self.assertRaises(AccessDenied):
            self.exporter.export(self.principal, uuid4())
        value = self.exporter.export(Principal(self.user["id"], 1), uuid4(), "audit", closure_read=True)
        self.assertTrue(verify_export(value))
        self.assertEqual(value["sections"]["financial_closure_receipts"][0]["business_id"], self.bid)

    def test_tombstone_replay_before_service_is_idempotent(self):
        self.applied()
        with db.get_conn() as conn:
            conn.execute("UPDATE users SET is_active=TRUE,password_hash='restored-old-value' WHERE id=?", (self.user["id"],))  # pragma: allowlist secret
        db.init_db()
        u = db.get_user(self.user["id"])
        self.assertFalse(u["is_active"])
        self.assertEqual(u["password_hash"], "")
        version = u["session_version"]
        db.init_db()
        self.assertEqual(db.get_user(self.user["id"])["session_version"], version)

    def test_every_e_record_sql_immutable(self):
        self.applied()
        for table in TABLES:
            if not self.rows(table):
                continue
            for query in (f"UPDATE {table} SET content_hash=? WHERE business_id=?", f"DELETE FROM {table} WHERE business_id=?"):
                with self.assertRaises(db.DatabaseError):
                    with db.get_conn() as conn:
                        conn.execute(query, ("0" * 64, self.bid) if query.startswith("UPDATE") else (self.bid,))

    def test_forged_manifest_insert_without_context_rejected(self):
        value = self.exporter.export(self.principal, uuid4())
        row = self.rows(EXPORTS)[0]
        row["evidence_uuid"] = str(uuid4())
        with self.assertRaises(db.DatabaseError):
            with db.get_conn() as conn:
                conn.execute(f"INSERT INTO {EXPORTS}({','.join(row)}) VALUES({','.join('?' for _ in row)})", tuple(row.values()))
        self.assertTrue(verify_export(value))

    def test_evidence_blocks_destructive_downgrade_and_business_delete(self):
        self.policy(approved=False)
        with self.assertRaises(ValueError):
            migrations.downgrade(77)
        with self.assertRaises(ValueError):
            db.delete_business_cascade(self.bid)
        self.assertEqual(migrations.current_version(), 78)

    def test_crash_before_commit_rolls_back_receipt_and_access(self):
        plan, auth = self.authorized()
        def crash(point, s):
            if point == "before_commit":
                raise RuntimeError("synthetic crash")
        with self.assertRaises(RuntimeError):
            self.close.apply(self.principal, plan["plan_uuid"], authorization_uuid=auth["authorization_uuid"], checkpoint=crash)
        self.assertEqual(self.rows(RECEIPTS), [])
        self.assertTrue(db.get_user(self.user["id"])["is_active"])
        self.assertEqual(self.close.apply(self.principal, plan["plan_uuid"], authorization_uuid=auth["authorization_uuid"])["final_state"], "closed_restricted")

    def test_crash_after_commit_retry_returns_exact_receipt(self):
        plan, auth = self.authorized()
        def crash(point, s):
            if point == "after_commit":
                raise RuntimeError("synthetic crash")
        with self.assertRaises(RuntimeError):
            self.close.apply(self.principal, plan["plan_uuid"], authorization_uuid=auth["authorization_uuid"], checkpoint=crash)
        result = self.close.apply(self.principal, plan["plan_uuid"], authorization_uuid=auth["authorization_uuid"])
        self.assertEqual(len(self.rows(RECEIPTS)), 1)
        self.assertEqual(result, json.loads(self.rows(RECEIPTS)[0]["body_canonical"]))

    def test_enabled_requires_explicit_prior_pause_and_preserves_d_receipts(self):
        self.cut()
        from noesis.financial_activation.handoff import FinancialActivation
        self.api = FinancialActivation(self.bid, code_version="fixture")
        self.enable()
        plan = self.closure_plan()
        with self.assertRaisesRegex(StateError, "PAUSE_REQUIRED"):
            self.close.authorize(self.principal, plan["plan_uuid"], approved_hash=digest(plan))
        req = self.approved_request(action="pause", pause_reason="operator_request")
        self.api.advance(self.principal, req.body["request_uuid"], "paused")
        d_before = self.rows("financial_activation_transitions")
        history_before = self.rows("financial_history_reconciliations")
        self.applied()
        self.assertEqual(d_before, self.rows("financial_activation_transitions"))
        self.assertEqual(history_before, self.rows("financial_history_reconciliations"))
        self.assertEqual(self.rows("financial_activation_control")[0]["state"], "paused")
        with self.assertRaises((AccessDenied, StateError)):
            self.api.prepare(self.principal, uuid4(), "resume")


class PrivacySQLite(PrivacyContract, unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="noesis-110e-test-")
        self.addCleanup(temp.cleanup)
        settings = patch.multiple(config, DATABASE_URL="", DB_PATH=Path(temp.name) / "fixture.db")
        settings.start()
        self.addCleanup(settings.stop)
        db.init_db()
        self.setup_privacy()

    def test_restore_older_than_closure_uses_current_suppression_registry(self):
        import sqlite3
        from noesis.financial_privacy.restore import prepare_restored_database, restore_bundle
        temp = tempfile.TemporaryDirectory(prefix="noesis-e-restored-synthetic-")
        self.addCleanup(temp.cleanup)
        target = Path(temp.name) / "old-fixture.db"
        from contextlib import closing
        with closing(sqlite3.connect(config.DB_PATH)) as original, closing(sqlite3.connect(target)) as older:
            original.backup(older)
        receipt = self.applied()
        with db.get_conn() as conn:
            bundle = restore_bundle(FinancialSession(conn))
        with patch.object(config, "DB_PATH", target):
            with db.get_conn() as conn:
                conn.execute("BEGIN IMMEDIATE")
                result = prepare_restored_database(FinancialSession(conn), bundle)
                self.assertEqual(result["result"], "suppression_reapplied_before_service")
            self.assertFalse(db.get_user(self.user["id"])["is_active"])
            with self.assertRaises(StateError):
                db.add_expense("Resucitado", 1, business_id=self.bid)
            with db.get_conn() as conn:
                rows = conn.execute("SELECT * FROM financial_restore_suppressions").fetchall()
            self.assertEqual(str(rows[0]["evidence_uuid"]), receipt["receipt_uuid"])
            db.init_db()
            self.assertFalse(db.get_user(self.user["id"])["is_active"])

    def test_http_exports_require_auth_tenant_and_client_scope(self):
        from starlette.testclient import TestClient
        from noesis.web import auth, server
        password = "Synthetic-local-pass-110e"  # pragma: allowlist secret
        with db.get_conn() as conn:
            conn.execute("UPDATE users SET password_hash=? WHERE id=?", (auth.hash_password(password), self.user["id"]))
        http = TestClient(server.app)
        self.addCleanup(http.close)
        unauthenticated = http.get(f"/api/{self.bid}/export", follow_redirects=False)
        self.assertIn(unauthenticated.status_code, (401, 403, 303, 307))
        http.post("/login", data={"email": self.user["email"], "password": password}, follow_redirects=False)
        other = db.create_business("Otro", "http-other@example.test")
        client = db.add_client("Ajeno", business_id=other["id"])
        self.assertIn(http.get(f"/api/{other['id']}/export", follow_redirects=False).status_code, (403, 404))
        self.assertEqual(http.get(f"/api/{self.bid}/clients/{client['id']}/export").status_code, 404)
        result = http.get(f"/api/{self.bid}/export")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.headers["cache-control"], "no-store")
        self.assertIn("attachment", result.headers["content-disposition"])
        self.assertTrue(verify_export(result.json()["financial_core"]))
        self.assertIn(http.post(f"/b/{other['id']}/account/delete", data={"confirm": "BORRAR", "password": password}, follow_redirects=False).status_code, (403, 404, 307))
        self.assertIsNotNone(db.get_business(other["id"]))
        self.assertEqual(db.list_privacy_requests(business_id=other["id"]), [])


if __name__ == "__main__":
    unittest.main()
