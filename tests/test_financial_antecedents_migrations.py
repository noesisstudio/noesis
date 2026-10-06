"""Migration75 vacía reversible; evidencia durable impide pérdida."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noesis import config, db, migrations
from noesis.financial_history.reconciliation_verifier import storage_hash


def migration_cycle(test):
    migrations.upgrade(74)
    with db.get_conn() as c:
        c.execute(
            "INSERT INTO businesses (name,created_at) VALUES ('Conservado','2026-10-06T00:00:00')"
        )
        before = [storage_hash(r) for r in c.execute_exact("SELECT * FROM businesses").fetchall()]
    test.assertEqual(migrations.upgrade(75), 75)
    test.assertEqual(migrations.downgrade(74), 74)
    test.assertEqual(migrations.upgrade(75), 75)
    with db.get_conn() as c:
        test.assertEqual(
            before,
            [storage_hash(r) for r in c.execute_exact("SELECT * FROM businesses").fetchall()],
        )
    if not config.DATABASE_URL:
        test.assertEqual(migrations.downgrade(0), 0)
        test.assertEqual(migrations.upgrade(75), 75)


class AntecedentsMigrationSQLite(unittest.TestCase):
    def test_empty_cycle_preserves_legacy_and_full_sqlite_cycle(self):
        with tempfile.TemporaryDirectory(prefix="noesis-110b-cycle-") as path:
            with patch.multiple(config, DATABASE_URL="", DB_PATH=Path(path) / "fixture.db"):
                migration_cycle(self)
