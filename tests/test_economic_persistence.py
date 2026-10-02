"""Persistencia económica en SQLite local descartable."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noesis import config, db, migrations
from noesis.core.persistence import FinancialSession
from noesis.economic_events.service import EconomicEvents
from noesis.financial_operations.contracts import StateError
from tests.economic_persistence_contract import EconomicPersistenceContract


class EconomicPersistenceSQLite(EconomicPersistenceContract, unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = patch.multiple(
            config, DATABASE_URL="", DB_PATH=Path(self.temp.name) / "events.db"
        )
        self.settings.start()
        migrations.upgrade()
        self.seed()

    def tearDown(self):
        self.settings.stop()
        self.temp.cleanup()

    def test_append_requires_outer_transaction_without_implicit_commit(self):
        event = self.make_event()
        operation = self.operation(event)
        with db.get_conn() as conn:
            service = EconomicEvents(FinancialSession(conn), self.bid)
            with self.assertRaises(StateError):
                service.append(
                    self.principal,
                    event,
                    operation_uuid=operation.operation_uuid,
                    event_slot="primary",
                    revision_reader=lambda *_: 1,
                )
        self.assertEqual(self.rows(), (0, 0, 0))
        with self.assertRaisesRegex(RuntimeError, "Fallo exterior"):
            with self.transaction() as (service, _):
                service.append(
                    self.principal,
                    event,
                    operation_uuid=operation.operation_uuid,
                    event_slot="primary",
                    revision_reader=lambda *_: 1,
                )
                raise RuntimeError("Fallo exterior")
        self.assertEqual(self.rows(), (0, 0, 0))

    def test_complete_empty_migration_cycle(self):
        self.assertEqual(migrations.downgrade(0), 0)
        self.assertEqual(migrations.current_version(), 0)
        self.assertEqual(migrations.upgrade(), 63)


if __name__ == "__main__":
    unittest.main()
