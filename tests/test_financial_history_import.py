"""Importer1.9D sobre SQLite descartable."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noesis import config, db
from tests.financial_history_import_contract import HistoryImportContract


class HistoryImportSQLite(HistoryImportContract, unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        settings = patch.multiple(config, DATABASE_URL="", DB_PATH=Path(temp.name) / "fixture.db")
        settings.start()
        self.addCleanup(settings.stop)
        db.init_db()
        self.setup_import()


if __name__ == "__main__":
    unittest.main()
