"""Reconciliación1.9E sobre SQLite temporal."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noesis import config, db
from tests.financial_history_reconciliation_contract import HistoryReconciliationContract


class HistoryReconciliationSQLite(HistoryReconciliationContract,unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="noesis-19e-")
        self.addCleanup(temp.cleanup)
        settings = patch.multiple(config,DATABASE_URL="",DB_PATH=Path(temp.name)/"fixture.db")
        settings.start()
        self.addCleanup(settings.stop)
        db.init_db()
        self.setup_reconciliation()


if __name__ == "__main__":
    unittest.main()
