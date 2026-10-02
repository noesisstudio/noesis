"""Contrato Fase1.7 sobre SQLite real."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noesis import config, db
from tests.purchasing_capture_contract import PurchasingCaptureContract


class PurchasingCaptureSQLite(PurchasingCaptureContract, unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        settings = patch.multiple(config, DATABASE_URL='', DB_PATH=Path(self.temp.name)/'test.db')
        settings.start()
        self.addCleanup(settings.stop)
        db.init_db()
        self.setup_capture()
