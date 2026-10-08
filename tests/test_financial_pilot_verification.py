"""G SQLite sintético; template vacío evita repetir migrations79 por caso."""
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from noesis import config, db
from tests.financial_pilot_verification_contract import PilotVerificationContract


class PilotVerificationSQLite(PilotVerificationContract, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template_dir = tempfile.TemporaryDirectory(prefix='noesis-g-empty-template-')
        cls.template = Path(cls.template_dir.name)/'empty.db'
        with patch.multiple(config, DATABASE_URL='', DB_PATH=cls.template):
            db.init_db()

    @classmethod
    def tearDownClass(cls):
        cls.template_dir.cleanup()

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='noesis-g-synthetic-')
        self.addCleanup(temp.cleanup)
        path = Path(temp.name)/'synthetic.db'
        shutil.copyfile(self.template, path)
        p = patch.multiple(config, DATABASE_URL='', DB_PATH=path)
        p.start()
        self.addCleanup(p.stop)
        self.setup_providers()
