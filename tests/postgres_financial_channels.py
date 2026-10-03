import unittest
from concurrent.futures import ThreadPoolExecutor
import threading
from unittest.mock import patch
from uuid import uuid4
from noesis import db
from noesis.core.locks import lock_business, lock_key
from noesis.financial_operations.contracts import EntryIdentity, OperationState
from noesis.financial_operations.repository import OperationsRepository
from noesis.purchasing_capture import ExpenseCapture
from tests.financial_channels_contract import ChannelsContract
from tests.postgres_financial_operations import FinancialOperationsPostgres


class FinancialChannelsPostgres(ChannelsContract, unittest.TestCase):
    setUpClass = classmethod(FinancialOperationsPostgres.setUpClass.__func__)
    tearDownClass = classmethod(FinancialOperationsPostgres.tearDownClass.__func__)

    def setUp(self):
        self.setup_channels()

    def locked_reprepare_authorize(self, *, distinct=False, rollback=False):
        ctx, p = self.propose()
        capture = ExpenseCapture(self.bid)
        op = capture.operations.recover(self.principal, p["operation_uuid"])
        identity = EntryIdentity.web_api(uuid4()) if distinct else ctx.identity
        if distinct:
            capture.prepare(self.principal, identity, op.request)
        business_held, gate_contended, release = (threading.Event() for _ in range(3))
        operation_before_gate = threading.Event()
        original_prepare = OperationsRepository.prepare

        def at_gate(session, bid):
            if threading.current_thread().name.startswith("reprepare"):
                # La otra conexión ya posee el gate: demostrar contención real.
                acquired = session.execute("SELECT pg_try_advisory_xact_lock(?) AS acquired",
                    (lock_key("financial-writer", bid),)).fetchone()["acquired"]
                self.assertFalse(acquired)
                gate_contended.set()
            lock_business(session, bid)

        def prepared(repo, *args):
            if threading.current_thread().name.startswith("reprepare"):
                operation_before_gate.set()
            return original_prepare(repo, *args)

        def hold(session, operation, stage):
            if stage == "lock":
                business_held.set()
                if not release.wait(10):
                    raise RuntimeError("barrera agotada")
            elif rollback:
                raise RuntimeError("rollback deliberado")

        def authorize():
            service = ExpenseCapture(self.bid)
            service.operations._channel_guard = hold
            return service.authorize(self.principal, op.operation_uuid, channel="web_api",
                approved_hash=op.request.request_hash, approved_revision=op.request.expected_revision)

        with patch("noesis.financial_operations.service.lock_business", side_effect=at_gate), \
                patch.object(OperationsRepository, "prepare", prepared), \
                ThreadPoolExecutor(max_workers=1, thread_name_prefix="authorize") as authorizer, \
                ThreadPoolExecutor(max_workers=1, thread_name_prefix="reprepare") as preparer:
            t2 = authorizer.submit(authorize)
            try:
                self.assertTrue(business_held.wait(10))
                t1 = preparer.submit(capture.prepare, self.principal, identity, op.request)
                self.assertTrue(gate_contended.wait(10))
                self.assertFalse(operation_before_gate.is_set())
            finally:
                release.set()
            if rollback:
                with self.assertRaisesRegex(RuntimeError, "rollback deliberado"):
                    t2.result(timeout=15)
            else:
                self.assertEqual(t2.result(timeout=15).state, OperationState.APPROVED)
            rechecked = t1.result(timeout=15)
        self.assertTrue(operation_before_gate.is_set())
        if rollback:
            self.assertEqual(rechecked.state, OperationState.PREPARED)
            self.confirm(self.ctx(), p)
        else:
            self.assertEqual(rechecked.state, OperationState.PREPARED if distinct else OperationState.APPROVED)
            done = capture.execute(self.principal, op.operation_uuid)
            self.assertEqual(capture.execute(self.principal, op.operation_uuid).result, done.result)
        self.assertEqual(self.count("expenses"), 1)
        self.assertEqual(self.count("financial_authorizations"), 1)
        self.assertEqual(self.count("economic_events"), 1)
        with db.get_conn() as conn:
            self.assertTrue(conn.execute("SELECT pg_try_advisory_xact_lock(?) AS acquired",
                (lock_key("financial-writer", self.bid),)).fetchone()["acquired"])

    def test_reprepare_authorize_same_operation_business_before_row(self):
        self.locked_reprepare_authorize()

    def test_prepare_authorize_distinct_operations_same_business(self):
        self.locked_reprepare_authorize(distinct=True)

    def test_reprepare_after_authorization_rollback_releases_locks(self):
        self.locked_reprepare_authorize(rollback=True)
