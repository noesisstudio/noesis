"""Productores y concurrencia real en PostgreSQL local descartable."""

from concurrent.futures import ThreadPoolExecutor
import threading
import unittest
from unittest.mock import patch

from noesis import db
from noesis.financial_operations.contracts import StateError
from tests.invoice_capture_contract import InvoiceCaptureContract
from tests.postgres_financial_operations import FinancialOperationsPostgres


class InvoiceCapturePostgres(InvoiceCaptureContract, unittest.TestCase):
    setUpClass = classmethod(FinancialOperationsPostgres.setUpClass.__func__)
    tearDownClass = classmethod(FinancialOperationsPostgres.tearDownClass.__func__)

    def setUp(self):
        self.setup_capture()

    def race(self, actions):
        barrier = threading.Barrier(len(actions))
        def worker(action):
            barrier.wait(timeout=15)
            try:
                return action()
            except StateError as exc:
                return str(exc)
        with ThreadPoolExecutor(max_workers=len(actions)) as pool:
            jobs = [pool.submit(worker, action) for action in actions]
            return [job.result(timeout=30) for job in jobs]

    def test_same_operation_two_connections_one_effect(self):
        op = self.approve(self.draft()["id"])
        results = self.race([lambda: self.capture.execute(self.principal, op.operation_uuid)] * 2)
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.counts(), {"invoice_records": 1, "invoice_events": 1, "verifactu_outbox": 1, "economic_events": 1, "invoice_economic_coverage": 1})

    def test_captured_fiscal_records_xml_equal_phase14_golden(self):
        from tests.fiscal_parity import scenario
        from tests.fixtures_phase14_fiscal import REFERENCE

        with self.migration_scope():
            def captured_issue(invoice_id, business_id):
                op = self.approve(invoice_id)
                self.capture.execute(self.principal, op.operation_uuid)
                return db.get_invoice(invoice_id, business_id)

            with patch.object(db, "issue_invoice", side_effect=captured_issue):
                actual = scenario(db, self.bid, self.client["id"])
            for observed, expected in zip(actual[:-1], REFERENCE["result"][:-1], strict=True):
                self.assertEqual(observed["invoice"]["number"], expected["invoice"]["number"])
                for key in ("record_hash", "previous_hash", "qr_url", "breakdown_json", "vat_total", "invoice_total",
                            "invoice_type", "rectification_type", "producer_name", "producer_nif", "system_id", "system_version"):
                    self.assertEqual(observed["record"][key], expected["record"][key], key)
            self.assertEqual(actual[-1]["xml"], REFERENCE["result"][-1]["xml"])

    def test_same_invoice_two_operations_one_primary(self):
        iid = self.draft()["id"]
        ops = [self.approve(iid) for _ in range(2)]
        results = self.race([lambda op=op: self.capture.execute(self.principal, op.operation_uuid) for op in ops])
        self.assertEqual(sum(isinstance(r, str) for r in results), 1)
        self.assertEqual(self.counts()["economic_events"], 1)

    def test_same_different_series_legacy_and_captured_chain_no_forks(self):
        other = db.add_invoice_series(self.bid, code="B", name="Otra", document_type="invoice", prefix_template="B{YYYY}/")
        ops = [self.approve(self.draft(series_id=other["id"])["id"]) if i % 2 else self.approve(self.draft()["id"]) for i in range(6)]
        legacy = self.draft()["id"]
        results = self.race([lambda op=op: self.capture.execute(self.principal, op.operation_uuid) for op in ops] + [lambda: db.issue_invoice(legacy, self.bid)])
        self.assertFalse(any(isinstance(r, str) for r in results))
        records = db.list_invoice_records(self.bid)
        self.assertEqual(len(records), 7)
        self.assertEqual(self.counts()["economic_events"], 6)
        hashes = {record["record_hash"] for record in records}
        previous = [record["previous_hash"] for record in records if record["previous_hash"]]
        self.assertEqual(len(set(previous)), 6)
        self.assertTrue(set(previous) <= hashes)
        self.assertEqual(sum(record["previous_hash"] is None for record in records), 1)
        self.assertEqual(len({record["invoice_number"] for record in records}), 7)


if __name__ == "__main__":
    unittest.main()
