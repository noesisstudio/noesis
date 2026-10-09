"""B en SQLite temporal sin fuentes reales."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noesis import config, db
from tests.financial_antecedents_contract import AntecedentsContract


class AntecedentsSQLite(AntecedentsContract, unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="noesis-110b-")
        self.addCleanup(temp.cleanup)
        settings = patch.multiple(config, DATABASE_URL="", DB_PATH=Path(temp.name) / "fixture.db")
        settings.start()
        self.addCleanup(settings.stop)
        db.init_db()
        self.setup_antecedents()
