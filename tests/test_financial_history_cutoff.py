"""Corte1.9C: SQLite aislado, contrato compartido."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noesis import config, db
from tests.financial_history_cutoff_contract import HistoryCutoffContract
from tests.financial_history_cutoff_races import CutoffProcessRaces


class HistoryCutoffSQLite(HistoryCutoffContract, CutoffProcessRaces, unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        settings = patch.multiple(config, DATABASE_URL="", DB_PATH=Path(temp.name) / "fixture.db")
        settings.start()
        self.addCleanup(settings.stop)
        db.init_db()
        self.setup_cut()


if __name__ == "__main__":
    unittest.main()
