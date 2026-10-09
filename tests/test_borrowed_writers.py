"""Contrato de escritores prestados sobre SQLite real."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noesis import config, db, migrations
from tests.borrowed_writers_contract import BorrowedWritersContract


class BorrowedWritersSQLite(BorrowedWritersContract, unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        settings = patch.multiple(config, DATABASE_URL="", DB_PATH=Path(self.temp.name) / "test.db")
        settings.start()
        self.addCleanup(settings.stop)
        # Composición de infraestructura previa a coverage76; C prueba writer en76.
        migrations.upgrade(75)
        self.seed()

    def test_fiscal_output_equals_previous_main_golden(self):
        from tests.fiscal_parity import scenario

        from tests.fixtures_phase14_fiscal import REFERENCE as expected
        self.assertEqual(scenario(db, self.bid, self.client["id"]), expected["result"])
