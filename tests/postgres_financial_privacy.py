"""Matriz E PostgreSQL real: esquema sintético y login runtime sin claves."""

from concurrent.futures import ThreadPoolExecutor
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from noesis import config, db, migrations
from noesis.financial_operations.contracts import Principal
from noesis.financial_operations.contracts import AccessDenied, StateError
from noesis.financial_privacy.contracts import digest
from noesis.financial_privacy.export import FinancialEvidenceExporter, verify_export
from tests.test_financial_privacy import PrivacyContract
from tests.postgres_financial_activation_handoff import HandoffPostgres


class PrivacyPostgres(PrivacyContract, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        HandoffPostgres.setUpClass.__func__(cls)
        db.close_pool()
        with patch.object(config, "DATABASE_URL", cls.admin_scoped):
            migrations.upgrade(78)
            with db.get_conn() as conn:
                from noesis.financial_privacy.schema import TABLES, RESTORED
                for table in TABLES + (RESTORED,):
                    conn.execute("GRANT SELECT,INSERT,UPDATE,DELETE ON " + table + " TO " + cls.role)
            db.close_pool()

    tearDownClass = classmethod(HandoffPostgres.tearDownClass.__func__)
    seed = HandoffPostgres.seed

    def setUp(self):
        self.setup_privacy()

    def test_snapshot_wholly_before_concurrent_writer_without_gate(self):
        started, done = threading.Event(), threading.Event()
        def checkpoint(point, session):
            if point == "snapshot_started":
                started.set()
                if not done.wait(15):
                    raise RuntimeError("Writer no progresó durante snapshot de lectura.")
        def writer():
            if not started.wait(15):
                raise RuntimeError("Snapshot no comenzó.")
            with db.get_conn() as conn:
                conn.execute("INSERT INTO expenses(business_id,concept,amount,vat_rate,spent_on,created_at) VALUES (?,'Writer concurrente',1,21,'2026-10-07','2026-10-07')", (self.bid,))
            done.set()
        with ThreadPoolExecutor(2) as pool:
            future = pool.submit(writer)
            value = self.exporter.export(self.principal, uuid4(), checkpoint=checkpoint)
            future.result(timeout=20)
        self.assertEqual(value["manifest"]["sections"]["expenses"]["count"], 0)
        self.assertTrue(verify_export(value))
        later = self.exporter.export(self.principal, uuid4())
        self.assertEqual(later["manifest"]["sections"]["expenses"]["count"], 1)

    def test_two_exports_same_uuid_share_final_manifest(self):
        barrier, uid = threading.Barrier(2), uuid4()
        def checkpoint(point, session):
            if point == "snapshot_started":
                barrier.wait(15)
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(self.exporter.export, self.principal, uid, checkpoint=checkpoint) for _ in range(2)]
            results = [f.result(timeout=30) for f in futures]
        self.assertEqual(results[0], results[1])

    def test_two_closure_applies_one_exact_receipt(self):
        plan, authority = self.authorized()
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(self.close.apply, self.principal, plan["plan_uuid"], authorization_uuid=authority["authorization_uuid"]) for _ in range(2)]
            results = [f.result(timeout=30) for f in futures]
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(self.rows("financial_closure_receipts")), 1)

    def test_other_business_progress_during_export(self):
        other = db.create_business("Otro sintético", "parallel@example.test")
        user = db.create_user(uuid4().hex + "@example.test", "fixture", other["id"])
        done = threading.Event()
        def checkpoint(point, session):
            if point == "snapshot_started":
                with ThreadPoolExecutor(1) as pool:
                    future = pool.submit(FinancialEvidenceExporter(other["id"], code_version="fixture").export,
                                         Principal(user["id"], 0), uuid4())
                    self.assertTrue(verify_export(future.result(timeout=20)))
                done.set()
        self.exporter.export(self.principal, uuid4(), checkpoint=checkpoint)
        self.assertTrue(done.is_set())

    def run_crash(self, point, action, **arguments):
        args = dict(business_id=self.bid, user_id=self.user["id"], session_version=0,
                    crash_point=point, action=action, **arguments)
        env = dict(os.environ, DATABASE_URL=self.runtime_url, NOESIS_DATABASE_URL=self.runtime_url,
                   NOESIS_SECRET=config.SECRET_KEY)
        from noesis.financial_history.service import FLAGS
        env.update({"NOESIS_" + flag: "false" for flag in FLAGS})
        child = subprocess.run([sys.executable, "-m", "tests.financial_privacy_worker", json.dumps(args)],
                               cwd=Path(__file__).parents[1], env=env, capture_output=True, text=True, timeout=45)
        self.assertEqual(child.returncode, 17, child.stderr)
        self.assertEqual(child.stdout, "")

    def test_real_process_crashes_plan_and_authority_rollback(self):
        policy = self.policy()
        request = db.create_privacy_request(self.bid, requester_user_id=self.user["id"], request_type="account_closure", retention_required=True)
        self.exporter.export(self.principal, uuid4(), "account_closure")
        uid = str(uuid4())
        for point in ("before_plan", "after_inventory"):
            self.run_crash(point, "plan", plan_uuid=uid, privacy_request_id=request["id"], policy_uuid=policy["policy_uuid"])
            self.assertEqual(self.rows("financial_closure_plans"), [])
            self.assertEqual(self.rows("financial_retention_inventories"), [])
        plan = self.close.plan(self.principal, uid, privacy_request_id=request["id"], policy_uuid=policy["policy_uuid"])
        self.run_crash("after_authorization", "authorize", plan_uuid=uid, approved_hash=digest(plan))
        self.assertEqual(self.rows("financial_closure_authorizations"), [])

    def test_real_process_crashes_minimization_precommit_and_postcommit(self):
        plan, authority = self.authorized()
        args = dict(plan_uuid=plan["plan_uuid"], authorization_uuid=authority["authorization_uuid"])
        for point in ("before_minimization", "during_minimization", "before_commit"):
            self.run_crash(point, "apply", **args)
            self.assertEqual(self.rows("financial_closure_receipts"), [])
            self.assertTrue(db.get_user(self.user["id"])["is_active"])
        self.run_crash("after_commit", "apply", **args)
        receipt = self.close.apply(self.principal, plan["plan_uuid"], authorization_uuid=authority["authorization_uuid"])
        self.assertEqual(receipt, json.loads(self.rows("financial_closure_receipts")[0]["body_canonical"]))
        self.assertEqual(len(self.rows("financial_privacy_tombstones")), 1)

    def test_two_plans_and_one_formal_authority(self):
        policy = self.policy()
        request = db.create_privacy_request(self.bid, requester_user_id=self.user["id"], request_type="account_closure", retention_required=True)
        self.exporter.export(self.principal, uuid4(), "account_closure")
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(self.close.plan, self.principal, uuid4(), privacy_request_id=request["id"], policy_uuid=policy["policy_uuid"]) for _ in range(2)]
            plans = [future.result(timeout=30) for future in futures]
        def authorize(plan):
            try:
                return self.close.authorize(self.principal, plan["plan_uuid"], approved_hash=digest(plan))
            except StateError:
                return None
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(authorize, plans))
        self.assertEqual(sum(r is not None for r in results), 1)

    def concurrent_snapshot(self, writer):
        started, done = threading.Event(), threading.Event()
        def write():
            self.assertTrue(started.wait(15))
            try:
                writer()
            finally:
                done.set()
        def checkpoint(point, session):
            if point == "snapshot_started":
                started.set()
                self.assertTrue(done.wait(20))
        with ThreadPoolExecutor(2) as pool:
            future = pool.submit(write)
            value = self.exporter.export(self.principal, uuid4(), checkpoint=checkpoint)
            future.result(timeout=30)
        self.assertTrue(verify_export(value))
        return value

    def test_export_vs_invoice_is_wholly_before(self):
        invoice = self.draft()
        value = self.concurrent_snapshot(lambda: db.issue_invoice(invoice["id"], self.bid))
        self.assertEqual(value["sections"]["invoices"][0]["status"], "borrador")
        self.assertEqual(value["sections"]["invoice_records"], [])

    def test_export_vs_payment_is_wholly_before(self):
        invoice = self.issued()
        value = self.concurrent_snapshot(lambda: db.add_invoice_payment(invoice["id"], "1.00", business_id=self.bid))
        self.assertEqual(value["sections"]["invoice_payments"], [])
        self.assertEqual(value["sections"]["invoices"][0]["status"], "enviada")

    def test_export_vs_pause_preserves_one_d_snapshot(self):
        from noesis.financial_activation.handoff import FinancialActivation
        self.cut()
        self.api = FinancialActivation(self.bid, code_version="fixture")
        self.enable()
        request = self.approved_request(action="pause", pause_reason="operator_request")
        value = self.concurrent_snapshot(lambda: self.api.advance(self.principal, request.body["request_uuid"], "paused"))
        self.assertEqual(value["sections"]["financial_activation_control"][0]["state"], "enabled")
        self.assertEqual(self.rows("financial_activation_control")[0]["state"], "paused")

    def test_export_vs_closure_revalidates_session_and_denies(self):
        plan, authority = self.authorized()
        with self.assertRaises(AccessDenied):
            self.concurrent_snapshot(lambda: self.close.apply(self.principal, plan["plan_uuid"], authorization_uuid=authority["authorization_uuid"]))
        self.assertEqual(len(self.rows("financial_export_manifests")), 1)

    def test_closure_vs_write_and_duplicate_privacy_request(self):
        plan, authority = self.authorized()
        def write():
            try:
                db.add_expense("Intercalada", 1, business_id=self.bid)
            except StateError:
                return "denied"
            return "unexpected"
        with ThreadPoolExecutor(3) as pool:
            closed = pool.submit(self.close.apply, self.principal, plan["plan_uuid"], authorization_uuid=authority["authorization_uuid"])
            writer = pool.submit(write)
            duplicate = pool.submit(db.create_privacy_request, self.bid, requester_user_id=self.user["id"], request_type="account_closure", retention_required=True)
            self.assertEqual(writer.result(timeout=30), "denied")
            self.assertEqual(closed.result(timeout=30)["final_state"], "closed_restricted")
            self.assertEqual(duplicate.result(timeout=30)["request_type"], "account_closure")

    def test_closure_vs_resume_is_denied_without_d_mutation(self):
        from noesis.financial_activation.handoff import FinancialActivation
        self.cut()
        self.api = FinancialActivation(self.bid, code_version="fixture")
        self.enable()
        pause = self.approved_request(action="pause", pause_reason="operator_request")
        self.api.advance(self.principal, pause.body["request_uuid"], "paused")
        resume = self.approved_request(action="resume")
        plan, authority = self.authorized()
        before = self.rows("financial_activation_transitions")
        def advance():
            try:
                self.api.advance(self.principal, resume.body["request_uuid"], "enabled")
            except (StateError, AccessDenied):
                return "denied"
            return "unexpected"
        with ThreadPoolExecutor(2) as pool:
            closed = pool.submit(self.close.apply, self.principal, plan["plan_uuid"], authorization_uuid=authority["authorization_uuid"])
            resumed = pool.submit(advance)
            self.assertEqual(resumed.result(timeout=30), "denied")
            self.assertEqual(closed.result(timeout=30)["final_state"], "closed_restricted")
        self.assertEqual(before, self.rows("financial_activation_transitions"))

    def test_admin_restore_verifier_d_unchanged_and_synthetic_old_copy(self):
        from noesis.web import backups
        from noesis.core.persistence import FinancialSession
        from noesis.financial_privacy.restore import prepare_restored_database
        temp = tempfile.TemporaryDirectory(prefix="noesis-e-pg-old-synthetic-")
        self.addCleanup(temp.cleanup)
        db.close_pool()
        with patch.object(config, "DATABASE_URL", self.admin_scoped), patch.object(config, "BACKUP_DIR", Path(temp.name)):
            with db.get_conn() as c:
                c.execute("DROP TABLE phase14_marker")
                definition = c.execute_exact("SELECT pg_get_functiondef('noesis_execution_context()'::regprocedure) AS d").fetchone()["d"]
            path, counts = backups._create_postgres_backup()
            db.close_pool()
        self.applied()
        def checked_restore(session, bundle):
            result = prepare_restored_database(session, bundle)
            self.assertFalse(session.execute("SELECT is_active FROM users WHERE id=?", (self.user["id"],)).fetchone()["is_active"])
            from noesis.financial_privacy.repository import assert_open
            with self.assertRaises(StateError):
                assert_open(session, self.bid)
            return result
        db.close_pool()
        with patch.object(config, "DATABASE_URL", self.admin_scoped), patch.object(backups, "prepare_restored_database", checked_restore, create=True):
            # La importación local del verificador usa el módulo restore.
            with patch("noesis.financial_privacy.restore.prepare_restored_database", checked_restore):
                backups._verify_postgres_backup(path, counts)
            with db.get_conn() as c:
                self.assertEqual(definition, c.execute_exact("SELECT pg_get_functiondef('noesis_execution_context()'::regprocedure) AS d").fetchone()["d"])
                self.assertIsInstance(FinancialSession(c), FinancialSession)
            db.close_pool()


if __name__ == "__main__":
    unittest.main()
