"""C PostgreSQL real localhost/noesis_ci; nunca datos reales ni provider I/O."""

from concurrent.futures import ThreadPoolExecutor
import threading
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from urllib.parse import quote
from uuid import uuid4

from noesis import config, db
from noesis.core.locks import lock_business
from noesis.financial_operations.contracts import EntryIdentity, StateError, ConflictError
from tests import postgres_financial_operations as pg
from tests.fiscal_cancellation_contract import FiscalCancellationContract
from tests.test_fiscal_cancellation_migrations import migration_cycle


class FiscalCancellationPostgres(FiscalCancellationContract, unittest.TestCase):
    setUpClass = classmethod(pg.FinancialOperationsPostgres.setUpClass.__func__)
    tearDownClass = classmethod(pg.FinancialOperationsPostgres.tearDownClass.__func__)

    def setUp(self):
        db.close_pool()
        self.setup_cancellation()

    def race(self, actions):
        barrier = threading.Barrier(len(actions))

        def run(action):
            barrier.wait(timeout=10)
            try:
                return action()
            except (StateError, ConflictError) as exc:
                return exc

        with ThreadPoolExecutor(max_workers=len(actions)) as pool:
            return list(pool.map(run, actions))

    def processes(self, operations, point=None):
        env = dict(os.environ, DATABASE_URL=self.scoped_url, NOESIS_DATABASE_URL=self.scoped_url)
        children = [subprocess.Popen([sys.executable, "-m", "tests.fiscal_cancellation_worker", json.dumps({
            "business_id": self.bid, "user_id": self.user["id"], "operation_uuid": op.operation_uuid,
            "point": point})], cwd=Path(__file__).parents[1], env=env, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for op in operations]
        try:
            for child in children:
                self.assertEqual(child.stdout.readline().strip(), "READY")
            for child in children:
                child.stdin.write("go\n")
                child.stdin.flush()
            return [(child.returncode, output.strip(), error) for child in children
                    for output, error in [child.communicate(timeout=30)]]
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate()

    def test_real_processes_same_operation_exact_result(self):
        op = self.authorized()
        results = self.processes([op, op])
        for code, _, error in results:
            self.assertEqual(code, 0, error)
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(len(self.rows("invoice_cancellation_records")), 1)

    def test_real_process_crashes_roll_back_and_postcommit_recovers(self):
        op = self.authorized()
        before = self.state(include_operations=True)
        for point in ("before_writer", "after_record", "after_outbox", "after_coverage", "after_event", "before_result"):
            with self.subTest(point=point):
                code, _, error = self.processes([op], point)[0]
                self.assertEqual(code, 17, error)
                self.assertEqual(before, self.state(include_operations=True))
        self.assertEqual(self.processes([op], "after_commit")[0][0], 17)
        done = self.cancel.execute(self.principal, op.operation_uuid)
        self.assertEqual(done.state.value, "committed")
        self.assertEqual(len(self.rows("invoice_cancellation_records")), 1)

    def test_configuration_change_serializes_then_blocks_approved_context(self):
        op = self.authorized()
        started = threading.Event()

        def mutate():
            with db.get_conn() as conn:
                started.set()
                lock_business(conn, self.bid)
                conn.execute("UPDATE businesses SET nif='A12345679' WHERE id=?", (self.bid,))  # pragma: allowlist secret

        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.cancel.operations._transaction(self.principal):
                future = pool.submit(mutate)
                self.assertTrue(started.wait(5))
                self.assertFalse(future.done())
            future.result(timeout=10)
        with self.assertRaises(StateError):
            self.cancel.execute(self.principal, op.operation_uuid)

    def test_concurrent_execute_same_operation_one_record_one_result(self):
        op = self.authorized()
        results = self.race([lambda: self.cancel.execute(self.principal, op.operation_uuid)] * 2)
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(self.rows("invoice_cancellation_records")), 1)
        self.assertEqual(len(self.rows("invoice_fiscal_cancellation_coverage")), 1)

    def test_two_distinct_operations_one_cancellation_other_blocked(self):
        op, req, identity = self.prepared()
        second = self.cancel.prepare(self.principal, EntryIdentity.web_api(uuid4()), req)
        for candidate in (op, second):
            self.cancel.authorize(self.principal, candidate.operation_uuid, channel=identity.namespace,
                                  approved_hash=req.request_hash, approved_revision=req.expected_revision)
        results = self.race([lambda: self.cancel.execute(self.principal, op.operation_uuid),
                             lambda: self.cancel.execute(self.principal, second.operation_uuid)])
        self.assertEqual(sum(isinstance(r, StateError) for r in results), 1)
        self.assertEqual(len(self.rows("invoice_cancellation_records")), 1)

    def test_cancel_against_rectification_serializes_chain_without_deadlock(self):
        op = self.authorized()
        draft = db.create_rectifying_invoice(op.request.target_id, self.bid, concept="Corrección",
                                            base="-1.00", invoice_type="R1", reason="Precio incorrecto")
        rectify = self.approve(draft["id"])
        results = self.race([lambda: self.cancel.execute(self.principal, op.operation_uuid),
                             lambda: self.capture.execute(self.principal, rectify.operation_uuid)])
        # Si rectificación gana, cambia la cadena aprobada y cancel aborta; si
        # cancel gana, el writer de rectificativas rechaza el original anulado.
        self.assertEqual(sum(isinstance(r, StateError) for r in results), 1)
        self.assertTrue(db.verify_invoice_record_chain(self.bid)["valid"])

    def test_source_change_waits_for_gate_then_resolution_stales(self):
        op = self.authorized()
        started, done = threading.Event(), threading.Event()

        def mutate():
            with db.get_conn() as conn:
                started.set()
                lock_business(conn, self.bid)
                conn.execute("UPDATE invoices SET status='cobrada' WHERE business_id=? AND id=?",
                             (self.bid, op.request.target_id))
            done.set()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.cancel.operations._transaction(self.principal):
                future = pool.submit(mutate)
                self.assertTrue(started.wait(5))
                self.assertFalse(done.wait(0.2))
            future.result(timeout=10)
        with self.assertRaises(ConflictError):
            self.cancel.execute(self.principal, op.operation_uuid)

    def test_other_business_progresses_while_this_gate_is_held(self):
        other = type(self)()
        other.setup_cancellation()
        self.addCleanup(other.doCleanups)
        op = other.authorized()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.cancel.operations._transaction(self.principal):
                result = pool.submit(other.cancel.execute, other.principal, op.operation_uuid).result(timeout=15)
                self.assertEqual(result.state.value, "committed")

    def test_empty_migration76_cycle_on_separate_schema(self):
        name = "fiscal_cancel_cycle_" + uuid4().hex
        with db.get_conn() as conn:
            conn.execute("CREATE SCHEMA " + name)
        url = self.original_url + ("&" if "?" in self.original_url else "?") + "options=" + quote("-csearch_path=" + name)
        db.close_pool()
        try:
            with patch.object(config, "DATABASE_URL", url):
                migration_cycle(self)
                db.close_pool()
        finally:
            with db.get_conn() as conn:
                conn.execute("DROP SCHEMA " + name + " CASCADE")


if __name__ == "__main__":
    unittest.main()
