"""Contrato económico y carreras de conexiones/procesos PostgreSQL reales."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest

from tests.economic_persistence_contract import EconomicPersistenceContract
from tests.postgres_financial_operations import FinancialOperationsPostgres


class EconomicPersistencePostgres(EconomicPersistenceContract, unittest.TestCase):
    setUpClass = classmethod(FinancialOperationsPostgres.setUpClass.__func__)
    tearDownClass = classmethod(FinancialOperationsPostgres.tearDownClass.__func__)

    def setUp(self):
        self.seed()

    def test_concurrent_connections_unique_monotonic_sequences(self):
        events = [self.make_event(revision=i + 1) for i in range(8)]
        ops = [self.operation(event) for event in events]
        start = threading.Barrier(4)

        def worker(index):
            if index < 4:
                start.wait(timeout=10)
            return self.append(events[index], operation=ops[index]).business_sequence

        with ThreadPoolExecutor(max_workers=4) as pool:
            sequences = list(pool.map(worker, range(8)))
        self.assertEqual(sorted(sequences), list(range(1, 9)))
        self.assertEqual(self.rows(), (8, 0, 1))

    def run_processes(self, args):
        env = dict(os.environ, DATABASE_URL=self.scoped_url, NOESIS_DATABASE_URL=self.scoped_url)
        children = [
            subprocess.Popen(
                [sys.executable, "-m", "tests.economic_events_worker", json.dumps(arg)],
                cwd=Path(__file__).parents[1],
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for arg in args
        ]
        try:
            for child in children:
                self.assertEqual(child.stdout.readline().strip(), "READY")
            for child in children:
                child.stdin.write("go\n")
                child.stdin.flush()
            results = []
            for child in children:
                out, err = child.communicate(timeout=30)
                self.assertEqual(child.returncode, 0, err)
                results.append(json.loads(out))
            return results
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate()

    def args(self, event, op):
        return dict(
            event=event.canonical_bytes().decode(),
            operation_uuid=op.operation_uuid,
            user_id=self.user["id"],
            business_id=self.bid,
        )

    def test_two_processes_replay_one_event_and_same_sequence(self):
        event = self.make_event()
        op = self.operation(event)
        results = self.run_processes([self.args(event, op)] * 2)
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.rows(), (1, 0, 1))

    def test_two_processes_conflicting_slot_and_distinct_sequences(self):
        first = self.make_event()
        op = self.operation(first)
        second = self.make_event(revision=2)
        results = self.run_processes([self.args(first, op), self.args(second, op)])
        self.assertEqual(sum(bool(r.get("conflict")) for r in results), 1)
        self.assertEqual(self.rows(), (1, 0, 1))
        third = self.make_event(revision=3)
        fourth = self.make_event(revision=4)
        results = self.run_processes(
            [self.args(third, self.operation(third)), self.args(fourth, self.operation(fourth))]
        )
        self.assertEqual({r["sequence"] for r in results}, {2, 3})


if __name__ == "__main__":
    unittest.main()
