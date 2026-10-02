"""Contrato 1.6 en SQLite real."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noesis import config, db
from tests.payment_bank_capture_contract import PaymentBankCaptureContract


class PaymentBankCaptureSQLite(PaymentBankCaptureContract, unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        settings = patch.multiple(config,DATABASE_URL='',DB_PATH=Path(self.temp.name)/'test.db')
        settings.start()
        self.addCleanup(settings.stop)
        db.init_db()
        self.setup_capture()
