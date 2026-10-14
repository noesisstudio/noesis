"""Readiness A sobre SQLite aislado; sin datos reales."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noesis import config, db
from tests.financial_readiness_contract import ReadinessContract


class ReadinessSQLite(ReadinessContract, unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="noesis-110a-")
        self.addCleanup(temp.cleanup)
        settings = patch.multiple(config, DATABASE_URL="", DB_PATH=Path(temp.name) / "fixture.db")
        settings.start()
        self.addCleanup(settings.stop)
        db.init_db()
        self.setup_readiness()
