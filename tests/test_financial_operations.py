"""Operaciones reales en SQLite descartable; sin productores del producto."""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import threading
import tempfile
import unittest
from unittest.mock import patch

from noesis import config, migrations
from tests.financial_operations_contract import OperationsContract


class FinancialOperationsSQLite(OperationsContract, unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = patch.multiple(config, DATABASE_URL="", DB_PATH=Path(self.temp.name) / "operations.db")
        self.settings.start()
        migrations.upgrade()
        self.seed()

    def tearDown(self):
        self.settings.stop()
        self.temp.cleanup()

    def test_two_sqlite_connections_reserve_and_execute_once(self):
        ready = threading.Barrier(2)
        def reserve():
            ready.wait(timeout=10)
            return self.reserve()
        with ThreadPoolExecutor(max_workers=2) as executor:
            rows = list(executor.map(lambda _: reserve(), range(2)))
        self.assertEqual(rows[0].operation_uuid, rows[1].operation_uuid)
        op = self.approved()
        ready = threading.Barrier(2)
        def execute():
            ready.wait(timeout=10)
            return self.service.execute(self.principal, op.operation_uuid, self.effect)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: execute(), range(2)))
        self.assertEqual(results[0].result, results[1].result)
        self.assertEqual(self.count_effects(), 1)


if __name__ == "__main__":
    unittest.main()
