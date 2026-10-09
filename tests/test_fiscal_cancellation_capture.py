"""C sobre SQLite temporal, únicamente fixtures sintéticos."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noesis import config, db
from tests.fiscal_cancellation_contract import FiscalCancellationContract


class FiscalCancellationSQLite(FiscalCancellationContract, unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="noesis-110c-")
        self.addCleanup(temp.cleanup)
        settings = patch.multiple(config, DATABASE_URL="", DB_PATH=Path(temp.name) / "fixture.db")
        settings.start()
        self.addCleanup(settings.stop)
        db.init_db()
        self.setup_cancellation()
