"""Emisión capturada en SQLite real."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noesis import config, db
from tests.invoice_capture_contract import InvoiceCaptureContract


class InvoiceCaptureSQLite(InvoiceCaptureContract, unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        settings = patch.multiple(config, DATABASE_URL="", DB_PATH=Path(self.temp.name) / "test.db")
        settings.start()
        self.addCleanup(settings.stop)
        db.init_db()
        self.setup_capture()

    def test_captured_fiscal_output_equals_phase14_golden(self):
        from tests.fiscal_parity import scenario
        from tests.fixtures_phase14_fiscal import REFERENCE
        def captured_issue(invoice_id, business_id):
            op = self.approve(invoice_id)
            self.capture.execute(self.principal, op.operation_uuid)
            return db.get_invoice(invoice_id, business_id)
        with patch.object(db, "issue_invoice", side_effect=captured_issue):
            self.assertEqual(scenario(db, self.bid, self.client["id"]), REFERENCE["result"])
