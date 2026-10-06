"""76 aditiva/reversible en vacío; no reconstruye huellas ni registros."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noesis import config, db, migrations
from noesis.financial_history.reconciliation_verifier import storage_hash


def migration_cycle(test):
    migrations.upgrade(75)
    with db.get_conn() as conn:
        conn.execute("INSERT INTO businesses (name,created_at) VALUES ('Conservado C','2026-10-06T00:00:00')")
        before = [storage_hash(r) for r in conn.execute_exact("SELECT * FROM businesses").fetchall()]
    test.assertEqual(migrations.upgrade(76), 76)
    test.assertEqual(migrations.downgrade(75), 75)
    test.assertEqual(migrations.upgrade(76), 76)
    with db.get_conn() as conn:
        test.assertEqual(before, [storage_hash(r) for r in conn.execute_exact("SELECT * FROM businesses").fetchall()])
    if not config.DATABASE_URL:
        test.assertEqual(migrations.downgrade(0), 0)
        test.assertEqual(migrations.upgrade(76), 76)


class FiscalCancellationMigrationSQLite(unittest.TestCase):
    def test_empty_cycle_preserves_existing_and_full_sqlite_cycle(self):
        with tempfile.TemporaryDirectory(prefix="noesis-110c-cycle-") as path:
            with patch.multiple(config, DATABASE_URL="", DB_PATH=Path(path) / "fixture.db"):
                migration_cycle(self)
