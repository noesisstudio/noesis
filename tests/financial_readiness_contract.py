"""Aceptación A compartida: fixtures descartables y snapshot de todas las tablas."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import patch

from noesis import config, db, migrations
from noesis.core.persistence import FinancialSession
from noesis.financial_activation.contracts import (
    Capability as C,
    CapabilityResult as CR,
    HistoryContext,
    Policy,
    Profile,
    Reason as R,
    capability_proof,
    canonical,
    future_ready_candidate,
)
from noesis.financial_activation.evaluator import FinancialReadinessEvaluator
from noesis.financial_activation.schema import TABLES
from noesis.financial_history.reconciliation import HistoryReconciliation
from noesis.financial_history.reconciliation_verifier import storage_hash
from noesis.financial_history.service import FLAGS
from noesis.financial_operations.contracts import AccessDenied, ConflictError, Principal
from tests.financial_history_import_contract import HistoryImportContract

NOW = datetime(2026, 10, 5, 18, tzinfo=timezone.utc)


class ReadinessContract:
    seed = HistoryImportContract.seed
    draft = HistoryImportContract.draft
    issued = HistoryImportContract.issued
    approved = HistoryImportContract.approved
    empty_database = HistoryImportContract.empty_database

    def setup_readiness(self):
        self.seed()
        self.user = db.create_user(uuid4().hex + "@example.test", "fixture", self.bid)
        self.principal = Principal(self.user["id"], 0)
        flags = patch.multiple(config, **dict.fromkeys(FLAGS, False))
        flags.start()
        self.addCleanup(flags.stop)
        self.reference = None

    def cut(self):
        from noesis.financial_history.importer import HistoryImporter

        imp = HistoryImporter(self.bid)
        epoch, manifest, batch, rec = (str(uuid4()) for _ in range(4))
        imp.open(
            self.principal, epoch, repository_version="fixture", environment_identity="synthetic"
        )
        imp.inventory(
            self.principal,
            epoch,
            manifest,
            repository_version="fixture",
            environment_identity="synthetic",
        )
        imp.prepare(self.principal, manifest, batch)
        imp.run(self.principal, batch)
        result = HistoryReconciliation(self.bid).reconcile(
            self.principal, epoch, manifest, batch, rec
        )
        self.reference = HistoryContext(epoch, manifest, batch, rec)
        return result

    def evaluate(self, profile=None, uid=None, **kwargs):
        with db.get_conn() as conn:
            if conn.dialect == "sqlite":
                conn.execute("BEGIN IMMEDIATE")
            return FinancialReadinessEvaluator(FinancialSession(conn), self.bid).evaluate(
                kwargs.pop("principal", self.principal),
                uid or uuid4(),
                profile or Profile((C.WEB,)),
                history=kwargs.pop("history", self.reference),
                code_version="fixture",
                now=kwargs.pop("now", NOW),
                **kwargs,
            )

    def snapshot(self):
        with db.get_conn() as conn:
            if conn.dialect == "postgres":
                names = [
                    r["table_name"]
                    for r in conn.execute(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() AND table_type='BASE TABLE'"
                    ).fetchall()
                ]
            else:
                names = [
                    r["name"]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    ).fetchall()
                ]
            result = {
                t: sorted(
                    storage_hash(r) for r in conn.execute_exact("SELECT * FROM " + t).fetchall()
                )
                for t in names
                if t not in TABLES
            }
        result["flags"] = [getattr(config, f) for f in FLAGS]
        return result

    def proof(self, result, capability):
        return next(p for p in result["capabilities"] if p["capability"] == capability.value)

    def test_empty_minimum_fully_eligible_without_any_financial_side_effect(self):
        self.assertEqual(self.cut()["result"], "PASS")
        before = self.snapshot()
        result = self.evaluate()
        self.assertEqual(result["outcome"], "fully_eligible")
        self.assertTrue(result["context"]["empty"])
        self.assertEqual(before, self.snapshot())
        with db.get_conn() as c:
            control = c.execute(
                "SELECT * FROM financial_activation_control WHERE business_id=?", (self.bid,)
            ).fetchone()
            self.assertEqual(control["state"], "off")
            self.assertFalse(control["ever_enabled"])
            self.assertEqual(control["activation_generation"], 0)
            self.assertTrue(
                c.execute(
                    "SELECT fence_enabled FROM financial_history_control WHERE business_id=?",
                    (self.bid,),
                ).fetchone()["fence_enabled"]
            )

    def test_no_provider_event_operation_or_history_write_api(self):
        self.cut()
        before = self.snapshot()
        with (
            patch("urllib.request.urlopen", side_effect=AssertionError("red")),
            patch("smtplib.SMTP", side_effect=AssertionError("correo")),
            patch(
                "noesis.economic_events.service.EconomicEvents.append",
                side_effect=AssertionError("evento"),
            ),
            patch(
                "noesis.financial_operations.service.FinancialOperations.execute",
                side_effect=AssertionError("operación"),
            ),
            patch(
                "noesis.financial_history.reconciliation.HistoryReconciliation.reconcile",
                side_effect=AssertionError("E write"),
            ),
        ):
            self.evaluate(Profile((C.WHATSAPP, C.EMAIL, C.EXPENSE_CONFIRM)))
        self.assertEqual(before, self.snapshot())

    def test_baja_with_readiness_retains_evidence_before_deleting_sources(self):
        self.evaluate()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "evidencia"):
            db.delete_business_cascade(self.bid)
        self.assertEqual(before, self.snapshot())

    def test_reconciliation_missing_even_empty_never_fully(self):
        result = self.evaluate()
        self.assertEqual(result["outcome"], "blocked")
        self.assertIn(R.RECONCILIATION_MISSING.value, result["reasons"])

    def test_unknown_reconciliation_and_different_context(self):
        self.cut()
        result = self.evaluate(history=replace(self.reference, reconciliation_uuid=str(uuid4())))
        self.assertIn(R.RECONCILIATION_MISSING.value, result["reasons"])
        old = self.reference
        from noesis.financial_history.importer import HistoryImporter

        batch, rec = str(uuid4()), str(uuid4())
        imp = HistoryImporter(self.bid)
        imp.prepare(self.principal, old.manifest_uuid, batch)
        imp.run(self.principal, batch)
        HistoryReconciliation(self.bid).reconcile(
            self.principal, old.epoch_uuid, old.manifest_uuid, batch, rec
        )
        result = self.evaluate(history=replace(old, reconciliation_uuid=rec))
        self.assertIn(R.CONTEXT_CHANGED.value, result["reasons"])

    def test_history_c_and_blocked_reconciliation_cannot_hide_by_profile(self):
        db.add_expense("Material", "12.10", business_id=self.bid)
        self.assertEqual(self.cut()["result"], "BLOCKED")
        before = self.snapshot()
        for profile in (Profile((C.WEB,)), Profile((C.EXPENSE_CONFIRM,)), Profile((C.EMAIL,))):
            result = self.evaluate(profile)
            self.assertEqual(result["outcome"], "blocked")
            self.assertIn(R.HISTORY_PENDING.value, result["reasons"])
            self.assertIn(R.RECONCILIATION_BLOCKED.value, result["reasons"])
        self.assertEqual(before, self.snapshot())

    def test_registro_anterior_d_never_verified_payment(self):
        invoice = self.issued()
        db.add_invoice_payment(
            invoice["id"], "1.00", method="registro_anterior", business_id=self.bid
        )
        self.cut()
        result = self.evaluate(Profile((C.CUSTOMER_PAYMENT_RECORD,)))
        self.assertEqual(result["outcome"], "blocked")
        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT classification FROM financial_history_items WHERE business_id=? AND manifest_uuid=? AND source_type='invoice_payment'",
                (self.bid, self.reference.manifest_uuid),
            ).fetchone()
            self.assertEqual(row["classification"], "D")

    def test_invoice_historical_remains_unsupported(self):
        self.issued()
        self.cut()
        result = self.evaluate(Profile((C.INVOICE_ISSUE,)))
        self.assertIn(
            R.UNSUPPORTED_HISTORICAL_INVOICE.value, self.proof(result, C.INVOICE_ISSUE)["reasons"]
        )

    def test_exact_profile_dependencies_and_fiscal_cancel(self):
        db.update_verifactu_mode(self.bid, True)
        self.cut()
        result = self.evaluate(Profile((C.INVOICE_ISSUE,)))
        self.assertIn(
            C.FISCAL_CANCEL.value, result["context"]["dependencies"][C.INVOICE_ISSUE.value]
        )
        self.assertEqual(self.proof(result, C.FISCAL_CANCEL)["result"], "blocked")
        self.assertIn(
            R.FISCAL_CAPABILITY_INCOMPLETE.value, self.proof(result, C.INVOICE_ISSUE)["reasons"]
        )
        self.assertNotEqual(result["outcome"], "fully_eligible")

    def test_partial_requires_new_smaller_profile_no_ready(self):
        self.cut()
        result = self.evaluate(Profile((C.WEB, C.EXPENSE_CONFIRM)))
        self.assertEqual(result["outcome"], "partially_eligible")
        self.assertFalse(
            future_ready_candidate(
                result["outcome"], expires_at=NOW + timedelta(minutes=5), now=NOW
            )
        )
        self.assertEqual(result["profile"]["capabilities"], [C.WEB.value, C.EXPENSE_CONFIRM.value])
        self.assertEqual(self.evaluate(Profile((C.WEB,)))["outcome"], "fully_eligible")

    def test_privacy_export_and_provider_are_not_stubbed(self):
        self.cut()
        result = self.evaluate(Profile((C.EXPENSE_CONFIRM, C.WHATSAPP, C.EMAIL, C.BANK_IMPORT)))
        for r in (R.PRIVACY_NOT_READY, R.EXPORT_NOT_READY):
            self.assertIn(r.value, self.proof(result, C.EXPENSE_CONFIRM)["reasons"])
        self.assertIn(R.PROVIDER_PREFLIGHT_MISSING.value, self.proof(result, C.WHATSAPP)["reasons"])
        self.assertIn(
            R.BANK_EVIDENCE_UNVALIDATED.value, self.proof(result, C.BANK_IMPORT)["reasons"]
        )

    def test_not_applicable_has_fiscal_evidence_not_missing_function(self):
        self.cut()
        result = self.evaluate(Profile((C.AEAT,)))
        proof = self.proof(result, C.AEAT)
        self.assertEqual(proof["result"], "not_applicable")
        self.assertFalse(proof["evidence"]["verifactu_enabled"])
        for c, r, e in (
            (C.AEAT, [R.PROVIDER_PREFLIGHT_MISSING], {}),
            (C.WHATSAPP, [R.FISCAL_PROVIDER_NOT_APPLICABLE], proof["evidence"]),
            (
                C.AEAT,
                [R.FISCAL_PROVIDER_NOT_APPLICABLE],
                {"verifactu_enabled": True, "configuration_hash": "a" * 64},
            ),
        ):
            with self.assertRaises(ValueError):
                capability_proof(c, CR.NOT_APPLICABLE, r, {}, e)

    def test_stale_session_wrong_permission_and_tenant(self):
        before = self.snapshot()
        with self.assertRaises(AccessDenied):
            self.evaluate(principal=Principal(self.user["id"], 1))
        with self.assertRaises(AccessDenied):
            self.evaluate(permission="financial.authorize")
        other = db.create_business("Otro")
        stranger = db.create_user(uuid4().hex + "@example.test", "fixture", other["id"])
        with self.assertRaises(AccessDenied):
            self.evaluate(principal=Principal(stranger["id"], 0))
        # La creación del fixture ajeno está fuera del snapshot de la evaluación.
        self.assertEqual(before["financial_operations"], self.snapshot()["financial_operations"])

    def test_idempotent_and_deterministic_without_clock_or_evaluation_uuid(self):
        self.cut()
        uid = uuid4()
        first = self.evaluate(uid=uid)
        self.assertEqual(first, self.evaluate(uid=uid, now=NOW + timedelta(seconds=30)))
        next_result = self.evaluate(uid=uuid4(), now=NOW + timedelta(seconds=60))
        self.assertEqual(first["content_hash"], next_result["content_hash"])
        self.assertNotEqual(first["created_at"], next_result["created_at"])
        reordered = self.evaluate(Profile((C.EXPENSE_CONFIRM, C.WEB)))
        self.assertEqual(
            reordered["content_hash"],
            self.evaluate(Profile((C.WEB, C.EXPENSE_CONFIRM)))["content_hash"],
        )

    def test_same_uuid_different_profile_or_config_conflicts(self):
        self.cut()
        uid = uuid4()
        original = self.evaluate(uid=uid)
        with self.assertRaises(ConflictError):
            self.evaluate(Profile((C.EMAIL,)), uid)
        with db.get_conn() as c:
            c.execute("UPDATE businesses SET name='Cambio' WHERE id=?", (self.bid,))
        with self.assertRaises(ConflictError):
            self.evaluate(uid=uid)
        changed = self.evaluate()
        self.assertNotEqual(
            original["context"]["configuration_hash"], changed["context"]["configuration_hash"]
        )
        self.assertNotEqual(original["content_hash"], changed["content_hash"])

    def test_draft_alone_is_empty_but_not_an_issued_antecedent(self):
        self.draft()
        result = self.evaluate()
        self.assertTrue(result["context"]["empty"])
        self.assertEqual(result["context"]["counts"]["invoice"], 1)
        self.assertEqual(result["outcome"], "blocked")  # E sigue siendo obligatoria.

    def test_uncertain_dispatch_cannot_hide_behind_empty_history(self):
        self.cut()
        with db.get_conn() as c:
            c.execute(
                "INSERT INTO email_outbox (business_id,to_email,subject,text_body,next_attempt_at,created_at,updated_at) VALUES (?,'fixture@example.test','Prueba','Sintético',?,?,?)",
                (self.bid, NOW.isoformat(), NOW.isoformat(), NOW.isoformat()),
            )
        before = self.snapshot()
        result = self.evaluate()
        self.assertFalse(result["context"]["empty"])
        self.assertIn("uncertain_dispatch", result["context"]["economic_kinds"])
        self.assertIn(R.HISTORY_PENDING.value, result["reasons"])
        self.assertEqual(result["outcome"], "blocked")
        self.assertEqual(before, self.snapshot())

    def test_prepared_live_operation_prevents_empty_proof(self):
        from noesis.financial_operations.contracts import (
            CommandType,
            EntryIdentity,
            FinancialRequest,
        )
        from noesis.financial_operations.service import FinancialOperations

        request = FinancialRequest(
            CommandType.INVOICE_FISCAL_CANCEL, None, "10.00", "2026-10-05", None, "Fixture", {}
        )
        FinancialOperations(self.bid).prepare(
            self.principal, EntryIdentity.web_api(uuid4()), request
        )
        before = self.snapshot()
        result = self.evaluate()
        self.assertFalse(result["context"]["empty"])
        self.assertIn("pending_live_operation", result["context"]["economic_kinds"])
        self.assertEqual(result["outcome"], "blocked")
        self.assertEqual(before, self.snapshot())

    def test_expiry_preserves_evidence_and_fence(self):
        self.cut()
        result = self.evaluate(policy=Policy(ttl_seconds=1))
        before = self.snapshot()
        self.assertFalse(
            future_ready_candidate(
                result["outcome"],
                expires_at=NOW + timedelta(seconds=1),
                now=NOW + timedelta(seconds=1),
            )
        )
        with db.get_conn() as c:
            reread = FinancialReadinessEvaluator(FinancialSession(c), self.bid).read(
                self.principal, result["evaluation_uuid"]
            )
        self.assertEqual(reread, result)
        self.assertEqual(before, self.snapshot())

    def test_final_sql_immutable_control_cannot_enable_or_lose_evidence(self):
        self.cut()
        result = self.evaluate()
        statements = (
            (
                "UPDATE financial_readiness_evaluations SET result='blocked' WHERE business_id=?",
                (self.bid,),
            ),
            ("DELETE FROM financial_readiness_evaluations WHERE business_id=?", (self.bid,)),
            (
                "UPDATE financial_readiness_capabilities SET result='eligible' WHERE business_id=?",
                (self.bid,),
            ),
            ("DELETE FROM financial_readiness_capabilities WHERE business_id=?", (self.bid,)),
            (
                "UPDATE financial_activation_control SET state='enabled',control_revision=control_revision+1 WHERE business_id=?",
                (self.bid,),
            ),
            (
                "UPDATE financial_activation_control SET ever_enabled=TRUE,control_revision=control_revision+1 WHERE business_id=?",
                (self.bid,),
            ),
            (
                "UPDATE financial_activation_control SET activation_generation=1,control_revision=control_revision+1 WHERE business_id=?",
                (self.bid,),
            ),
            (
                "INSERT INTO financial_readiness_capabilities SELECT business_id,evaluation_uuid,'invoice.issue',result,reasons_canonical,dependency_canonical,evidence_canonical,proof_canonical,proof_hash FROM financial_readiness_capabilities WHERE business_id=? AND capability='channel.web_financial'",
                (self.bid,),
            ),
        )
        for sql, args in statements:
            with self.assertRaises(Exception):
                with db.get_conn() as conn:
                    conn.execute(sql, args)
        with self.assertRaises(ValueError):
            migrations.downgrade(73)
        with db.get_conn() as c:
            self.assertEqual(
                FinancialReadinessEvaluator(FinancialSession(c), self.bid).read(
                    self.principal, result["evaluation_uuid"]
                ),
                result,
            )

    def test_cross_tenant_sql_link_rejected(self):
        self.cut()
        result = self.evaluate()
        other = db.create_business("Otro")
        with self.assertRaises(Exception):
            with db.get_conn() as c:
                c.execute(
                    "UPDATE financial_activation_control SET business_id=?,control_revision=control_revision+1 WHERE business_id=?",
                    (other["id"], self.bid),
                )
        with self.assertRaises(AccessDenied):
            with db.get_conn() as c:
                FinancialReadinessEvaluator(FinancialSession(c), other["id"]).read(
                    self.principal, result["evaluation_uuid"]
                )

    def test_flags_off_and_no_flag_can_be_used_as_permission(self):
        self.cut()
        for flag in FLAGS:
            with patch.object(config, flag, True), self.assertRaises(AccessDenied):
                self.evaluate()
        self.assertFalse(any(getattr(config, f) for f in FLAGS))

    def test_volume_policy_and_no_relaxation(self):
        self.draft()
        self.cut()
        result = self.evaluate(policy=Policy(max_items=1))
        self.assertEqual(result["outcome"], "blocked")
        self.assertIn(R.VOLUME_OUTSIDE_POLICY.value, result["reasons"])
        for kwargs in ({"max_items": 65}, {"ttl_seconds": 301}, {"policy_version": True}):
            with self.assertRaises(ValueError):
                Policy(**kwargs)

    def test_contract_closed_unknown_version_float_and_duplicates(self):
        for caps, version in (
            (("quote.accepted",), 1),
            (("supplier_payment.made",), 1),
            ((C.WEB,), 2),
            ((C.WEB, C.WEB), 1),
        ):
            with self.assertRaises(ValueError):
                Profile(caps, version)
        with self.assertRaises(TypeError):
            canonical({"amount": 1.2})
        self.assertEqual(len(C), 15)

    def test_source_drift_detected_without_writing_history(self):
        self.cut()
        with db.get_conn() as c:
            # Corrupción privilegiada solo en fixture descartable: simula drift.
            if c.dialect == "postgres":
                c.execute("ALTER TABLE suppliers DISABLE TRIGGER USER")
                triggers = []
            else:
                triggers = c.execute(
                    "SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name='suppliers'"
                ).fetchall()
                for trigger in triggers:
                    c.execute('DROP TRIGGER "' + trigger["name"] + '"')
            c.execute(
                "INSERT INTO suppliers (business_id,name,created_at) VALUES (?,'Nuevo',?)",
                (self.bid, NOW.isoformat()),
            )
            if c.dialect == "postgres":
                c.execute("ALTER TABLE suppliers ENABLE TRIGGER USER")
            else:
                for trigger in triggers:
                    c.execute(trigger["sql"])
        before = self.snapshot()
        result = self.evaluate()
        self.assertEqual(result["outcome"], "blocked")
        self.assertTrue({R.SOURCE_DRIFT.value, R.BOUNDARY_INVALID.value} & set(result["reasons"]))
        self.assertEqual(before, self.snapshot())

    def test_invalidated_boundary_stays_fenced(self):
        self.cut()
        from noesis.financial_history.cutoff import HistoryCutoff

        HistoryCutoff(self.bid).invalidate(
            self.principal, self.reference.epoch_uuid, reason="fixture"
        )
        result = self.evaluate()
        self.assertIn(R.BOUNDARY_INVALID.value, result["reasons"])

    def test_borrowed_transaction_rolls_back_only_new_tables(self):
        self.cut()
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with db.get_conn() as c:
                if c.dialect == "sqlite":
                    c.execute("BEGIN IMMEDIATE")
                FinancialReadinessEvaluator(FinancialSession(c), self.bid).evaluate(
                    self.principal,
                    uuid4(),
                    Profile((C.WEB,)),
                    history=self.reference,
                    code_version="fixture",
                )
                raise RuntimeError("rollback")
        with db.get_conn() as c:
            self.assertEqual(
                c.execute(
                    "SELECT COUNT(*) AS n FROM financial_readiness_evaluations WHERE business_id=?",
                    (self.bid,),
                ).fetchone()["n"],
                0,
            )
        self.assertEqual(before, self.snapshot())
