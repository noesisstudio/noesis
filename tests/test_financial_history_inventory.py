"""Inventario1.9B sobre SQLite descartable y contrato estructural sin efectos."""

import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noesis import config, db
from tests.financial_history_inventory_contract import HistoryInventoryContract


class HistoryInventorySQLite(HistoryInventoryContract, unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        settings = patch.multiple(config,DATABASE_URL='',DB_PATH=Path(temp.name)/'fixture.db')
        settings.start()
        self.addCleanup(settings.stop)
        db.init_db()
        self.setup_history()


class HistoryInventoryStructural(unittest.TestCase):
    def test_no_financial_effect_imports_calls_or_dynamic_escape(self):
        root = Path(__file__).parents[1]/'src/noesis/financial_history'
        forbidden = ('financial_writers','invoice_capture','payment_capture','bank_capture','purchasing_capture',
                     'financial_operations.service','economic_events.service','adapters','verifactu_client',
                     'financial_channels','documents.service')
        for path in root.glob('*.py'):
            with self.subTest(path=path.name):
                tree = ast.parse(path.read_text(encoding='utf-8'))
                for node in ast.walk(tree):
                    if isinstance(node,ast.ImportFrom):
                        self.assertFalse(any(f in (node.module or '') for f in forbidden))
                    if isinstance(node,ast.Import):
                        self.assertFalse(any(f in name.name for name in node.names for f in forbidden))
                    if isinstance(node,ast.Call):
                        name = ast.unparse(node.func)
                        self.assertFalse(any(name.endswith('.'+f) or name==f for f in (
                            'append_event','execute_capture','issue_invoice','add_invoice_payment','confirm_bank_transaction',
                            'import_module','__import__','eval','exec')))
                if path.stem in ('classifier','planning','raw','sources'):
                    self.assertFalse(any(isinstance(n,ast.ImportFrom) and n.module in ('noesis','noesis.db') for n in ast.walk(tree)))
                if path.stem == 'readers':
                    self.assertFalse(any(isinstance(n,ast.Call) and ast.unparse(n.func).endswith(('.commit','.rollback','.get_conn')) for n in ast.walk(tree)))


if __name__ == '__main__':
    unittest.main()
