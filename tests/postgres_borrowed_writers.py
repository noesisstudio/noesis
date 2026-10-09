"""Transacciones prestadas y carreras reales en PostgreSQL descartable."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import threading
import unittest
import os
import json
import subprocess
import sys
from pathlib import Path

from noesis import db
from noesis.core.locks import lock_business
from noesis.financial_writers import invoices, payments
from noesis.financial_writers.boundary import snapshot
from tests.borrowed_writers_contract import BorrowedWritersContract
from tests.postgres_financial_operations import FinancialOperationsPostgres


class BorrowedWritersPostgres(BorrowedWritersContract, unittest.TestCase):
    schema_target = 75
    setUpClass = classmethod(FinancialOperationsPostgres.setUpClass.__func__)
    tearDownClass = classmethod(FinancialOperationsPostgres.tearDownClass.__func__)

    def setUp(self):
        self.seed()

    def race(self, actions):
        ready = threading.Barrier(len(actions))

        def worker(action):
            ready.wait(timeout=10)
            try:
                return action()
            except ValueError as exc:
                return str(exc)

        with ThreadPoolExecutor(max_workers=len(actions)) as pool:
            return list(pool.map(worker, actions))

    def test_two_connections_issue_once_and_release_after_rollback(self):
        iid = self.draft()["id"]
        with self.assertRaises(RuntimeError):
            with db.get_conn() as conn:
                conn.execute("BEGIN IMMEDIATE")
                invoices.issue_invoice(conn, iid, self.bid)
                raise RuntimeError("Rollback")
        results = self.race([lambda: db.issue_invoice(iid, self.bid)] * 2)
        self.assertEqual(results[0], results[1])
        with db.get_conn() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM invoice_events WHERE business_id=? AND invoice_id=? AND event_type='emision'",
                    (self.bid, iid),
                ).fetchone()["n"],
                1,
            )

    def test_manual_and_bank_compete_without_overpayment(self):
        iid = self.issued()["id"]
        tid = self.movement(iid)
        results = self.race(
            [
                lambda: db.add_invoice_payment(iid, "120", business_id=self.bid),
                lambda: db.confirm_bank_transaction(tid, self.bid),
            ]
        )
        self.assertEqual(sum(isinstance(r, str) for r in results), 1)
        self.assertIn(db.invoice_paid_amount(iid, self.bid), (10, 120))
        self.assertLessEqual(db.invoice_paid_amount(iid, self.bid), 121)

    def test_mutable_read_stales_after_another_connection_commits(self):
        rid = db.add_received_invoice("10", business_id=self.bid)["id"]
        with db.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            old = snapshot(conn, self.bid, "received_invoice", rid)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(
                lambda: db.update_received_invoice(rid, business_id=self.bid, total="11")
            ).result(timeout=10)
        from noesis.financial_writers import purchasing

        with self.assertRaises(ValueError):
            with db.get_conn() as conn:
                conn.execute("BEGIN IMMEDIATE")
                purchasing.update_received_invoice(
                    conn, rid, business_id=self.bid, total="12", expected_revision=old.revision
                )

    def test_counter_source_inversion_uses_common_business_gate(self):
        iid = self.issued()["id"]
        with db.get_conn() as conn:
            conn.execute(
                "INSERT INTO economic_event_sequences (business_id,last_sequence) VALUES (?,0) ON CONFLICT DO NOTHING",
                (self.bid,),
            )

        def source_then_counter():
            with db.get_conn() as conn:
                conn.execute("SET LOCAL lock_timeout='5s'")
                lock_business(conn, self.bid)
                conn.execute(
                    "SELECT id FROM invoices WHERE business_id=? AND id=? FOR UPDATE",
                    (self.bid, iid),
                ).fetchone()
                conn.execute(
                    "SELECT business_id FROM economic_event_sequences WHERE business_id=? FOR UPDATE",
                    (self.bid,),
                ).fetchone()
                return True

        def counter_then_source():
            with db.get_conn() as conn:
                conn.execute("SET LOCAL lock_timeout='5s'")
                lock_business(conn, self.bid)
                conn.execute(
                    "SELECT business_id FROM economic_event_sequences WHERE business_id=? FOR UPDATE",
                    (self.bid,),
                ).fetchone()
                conn.execute(
                    "SELECT id FROM invoices WHERE business_id=? AND id=? FOR SHARE",
                    (self.bid, iid),
                ).fetchone()
                return True

        self.assertEqual(self.race([source_then_counter, counter_then_source]), [True, True])

    def test_two_payments_exact_cent_sum_no_overcollection(self):
        iid = self.issued()["id"]

        def pay():
            with db.get_conn() as conn:
                conn.execute("BEGIN IMMEDIATE")
                return payments.add_invoice_payment(
                    conn, iid, Decimal("100"), business_id=self.bid
                ).legacy_value()

        results = self.race([pay, pay])
        self.assertEqual(sum(isinstance(r, str) for r in results), 1)
        self.assertEqual(db.invoice_paid_amount(iid, self.bid), 100)

    def test_multiple_series_share_fiscal_chain_without_forks(self):
        db.update_verifactu_mode(self.bid, True)
        series = [
            db.add_invoice_series(
                self.bid,
                code=code,
                name=code,
                document_type="invoice",
                prefix_template=code + "{YYYY}/",
            )
            for code in ("A", "B")
        ]
        drafts = [self.draft(series_id=series[i % 2]["id"]) for i in range(6)]
        results = self.race([lambda iid=d["id"]: db.issue_invoice(iid, self.bid) for d in drafts])
        self.assertEqual(len({r["number"] for r in results}), 6)
        with db.get_conn() as conn:
            records = db._fiscal_record_rows(conn, self.bid)
            self.assertTrue(db._verify_invoice_record_rows(records)["valid"])
            self.assertEqual(len(records), 6)
            self.assertEqual(sum(r["previous_hash"] is None for r in records), 1)

    def processes(self, mode, iid):
        env = dict(os.environ, DATABASE_URL=self.scoped_url, NOESIS_DATABASE_URL=self.scoped_url)
        children = [
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "tests.borrowed_writers_worker",
                    json.dumps({"mode": mode, "invoice_id": iid, "business_id": self.bid}),
                ],
                cwd=Path(__file__).parents[1],
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for _ in range(2)
        ]
        try:
            for child in children:
                self.assertEqual(child.stdout.readline().strip(), "READY")
            for child in children:
                child.stdin.write("go\n")
                child.stdin.flush()
            results = []
            for child in children:
                output, error = child.communicate(timeout=30)
                self.assertEqual(child.returncode, 0, error)
                results.append(json.loads(output))
            return results
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate()

    def test_two_processes_issue_once_and_do_not_overcollect(self):
        iid = self.draft()["id"]
        result = self.processes("issue", iid)
        self.assertEqual(result[0], result[1])
        result = self.processes("payment", iid)
        self.assertEqual(sum(bool(r.get("conflict")) for r in result), 1)
        self.assertEqual(db.invoice_paid_amount(iid, self.bid), 100)
