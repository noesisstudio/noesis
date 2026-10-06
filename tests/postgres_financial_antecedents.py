"""B sobre PostgreSQL localhost/noesis_ci; fixtures descartables, nunca QA real."""

from concurrent.futures import ThreadPoolExecutor
import threading
import unittest
from unittest.mock import patch
from urllib.parse import quote
from uuid import uuid4

from noesis import config, db
from noesis.core.locks import lock_business
from noesis.financial_antecedents.contracts import Permission, ResolutionRequest, Purpose
from noesis.financial_operations.contracts import ConflictError
from tests import postgres_financial_operations as pg
from tests.financial_antecedents_contract import AntecedentsContract
from tests.test_financial_antecedents_migrations import migration_cycle


class AntecedentsPostgres(AntecedentsContract, unittest.TestCase):
    setUpClass = classmethod(pg.FinancialOperationsPostgres.setUpClass.__func__)
    tearDownClass = classmethod(pg.FinancialOperationsPostgres.tearDownClass.__func__)

    def setUp(self):
        # Las pruebas de downgrade cambian tipos físicos: no reutilizar planes
        # preparados de conexiones que sobrevivieron a la migración sintética.
        db.close_pool()
        self.setup_antecedents()

    def test_concurrent_same_uuid_returns_one_exact_resolution(self):
        ref, uid = self.invoice_ref(), uuid4()
        barrier = threading.Barrier(2)

        def run(_):
            barrier.wait(timeout=10)
            return self.resolve(ref, uid=uid, persist=True)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, range(2)))
        self.assertEqual(results[0], results[1])

    def test_concurrent_two_uuid_same_antecedent_same_context(self):
        ref = self.invoice_ref()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.resolve(ref, persist=True), range(2)))
        self.assertNotEqual(results[0]["resolution_uuid"], results[1]["resolution_uuid"])
        self.assertEqual(results[0]["result"], results[1]["result"])

    def test_source_change_serializes_then_stored_resolution_stales(self):
        ref = self.invoice_ref()
        started, done = threading.Event(), threading.Event()

        def mutate():
            with db.get_conn() as c:
                started.set()
                lock_business(c, self.bid)
                c.execute(
                    "UPDATE invoices SET status='cobrada' WHERE business_id=? AND id=?",
                    (self.bid, ref.source_id),
                )
            done.set()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.tx() as (_, resolver):
                saved = resolver.persist_resolution(
                    self.principal, uuid4(), ResolutionRequest(ref, Purpose.CUSTOMER_PAYMENT)
                )
                future = pool.submit(mutate)
                self.assertTrue(started.wait(5))
                self.assertFalse(done.wait(0.2))
            future.result(timeout=10)
        with self.tx() as (_, resolver), self.assertRaises(ConflictError):
            resolver.verify_resolution(self.principal, saved)

    def test_event_link_corruption_between_transactions_invalidates_resolution(self):
        ref = self.invoice_ref()
        saved = self.resolve(ref, persist=True)
        with self.corruption("economic_event_links") as c:
            c.execute(
                "INSERT INTO economic_event_links (business_id,event_uuid,target_event_uuid,relation_type,recorded_at) VALUES (?,?,?,'rectifies','2026-10-06T00:00:00+00:00')",
                (self.bid, ref.event_uuid, ref.event_uuid),
            )
        with self.tx() as (_, resolver), self.assertRaises(ConflictError):
            resolver.verify_resolution(self.principal, saved)

    def test_other_business_resolver_progresses_while_gate_held(self):
        other = type(self)()
        other.setup_antecedents()
        self.addCleanup(other.doCleanups)
        other_ref = other.invoice_ref()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.tx() as (_, resolver):
                resolver._access(self.principal, Permission.RESOLVE)
                result = pool.submit(lambda: other.resolve(other_ref, persist=True)).result(
                    timeout=10
                )
                self.assertEqual(result["result"]["outcome"], "resolved")

    def test_migration75_cycle_on_separate_empty_schema(self):
        name = "antecedent_cycle_" + uuid4().hex
        with db.get_conn() as c:
            c.execute("CREATE SCHEMA " + name)
        url = (
            self.original_url
            + ("&" if "?" in self.original_url else "?")
            + "options="
            + quote("-csearch_path=" + name)
        )
        db.close_pool()
        try:
            with patch.object(config, "DATABASE_URL", url):
                migration_cycle(self)
                db.close_pool()
        finally:
            with db.get_conn() as c:
                c.execute("DROP SCHEMA " + name + " CASCADE")


if __name__ == "__main__":
    unittest.main()
