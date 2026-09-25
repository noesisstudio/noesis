"""Rollback aditivo: conserva columnas y no expone borradores incompletos."""
import unittest
from noesis import db, migrations
from tests import test_backend as fixtures


class PendingRollbackTests(unittest.TestCase):
    setUp = fixtures.BackendTestCase.setUp
    tearDown = fixtures.BackendTestCase.tearDown
    make_business = fixtures.BackendTestCase.make_business
    def test_complete_invoice_snapshot_survives_58_down_up(self):
        business, client = self.make_business()
        invoice = db.add_invoice(client["id"], "Servicio", 100,
                                    business_id=business["id"])
        before = db.get_invoice(invoice["id"], business["id"])
        self.assertEqual(migrations.downgrade(57), 57)
        self.assertEqual(db.get_invoice(invoice["id"], business["id"]), before)
        migrations.upgrade()
        self.assertEqual(db.get_invoice(invoice["id"], business["id"]), before)

    def test_pending_invoice_blocks_unsafe_rollback_without_losing_marker(self):
        business, client = self.make_business()
        invoice = db.add_invoice(client["id"], "Servicio", 100,
                                    business_id=business["id"])
        with db.get_conn() as conn:
            conn.execute("UPDATE invoices SET pending_fields=? WHERE id=? AND business_id=?",
                         ('["importe"]', invoice["id"], business["id"]))
        with self.assertRaisesRegex(ValueError, "incompletos"):
            migrations.downgrade(57)
        self.assertEqual(migrations.current_version(), migrations.LATEST_VERSION)
        self.assertEqual(db.get_invoice(invoice["id"], business["id"])["pending_fields"],
                         '["importe"]')
