"""Ciclos vacíos74→73→74 y74→0→74 sin tocar migraciones anteriores."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noesis import config, db, migrations
from noesis.financial_activation.schema import TABLES
from noesis.financial_history.reconciliation_verifier import storage_hash


def migration_cycle(test):
    migrations.upgrade()
    with db.get_conn() as conn:
        conn.execute(
            "INSERT INTO businesses (name,created_at) VALUES ('Conservado','2026-10-05T00:00:00')"
        )
        before = [
            storage_hash(r) for r in conn.execute_exact("SELECT * FROM businesses").fetchall()
        ]
    test.assertEqual(migrations.downgrade(73), 73)
    test.assertEqual(migrations.upgrade(), migrations.LATEST_VERSION)
    with db.get_conn() as conn:
        test.assertEqual(
            before,
            [storage_hash(r) for r in conn.execute_exact("SELECT * FROM businesses").fetchall()],
        )
        for table in TABLES:
            test.assertEqual(conn.execute("SELECT COUNT(*) AS n FROM " + table).fetchone()["n"], 0)
    # Las migraciones antiguas PostgreSQL no soportan el ciclo completo hasta0.
    # A verifica74→73→74 en ambos motores; SQLite amplía hasta0.
    if config.DATABASE_URL == "":
        test.assertEqual(migrations.downgrade(0), 0)
        test.assertEqual(migrations.upgrade(), migrations.LATEST_VERSION)


class ReadinessMigrationSQLite(unittest.TestCase):
    def test_cycles_and_legacy_row_preserved(self):
        with tempfile.TemporaryDirectory(prefix="noesis-110a-migration-") as path:
            with patch.multiple(config, DATABASE_URL="", DB_PATH=Path(path) / "empty.db"):
                migration_cycle(self)
