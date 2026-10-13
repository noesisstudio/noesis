"""Identidad de backups CRM74; ningún migrador/runtime financiero nuevo."""

import gzip
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from noesis import db, migrations
from noesis.web import backups
from noesis.web.postgres_backup_identity import (
    CANONICAL_CRM74, CANONICAL_PRE74, LEGACY_FINANCIAL, LEGACY_NAMES,
    describe, expected_identities, fingerprint, privacy_status, read_identity,
)
from noesis.web.postgres_backup_tools import BackupError


class BackupIdentityContracts(unittest.TestCase):
    def test_current_catalog_is_main_crm74(self):
        self.assertEqual(migrations.LATEST_VERSION, 74)
        self.assertEqual(expected_identities()[-1], [74, "captacion_hoja_y_tipo"])
        self.assertEqual(describe(expected_identities())["schema_lineage_id"], CANONICAL_CRM74)

    def test_schema73_distinct_identity(self):
        older = expected_identities()[:73]
        self.assertEqual(describe(older)["schema_lineage_id"], CANONICAL_PRE74)
        self.assertNotEqual(fingerprint(older), fingerprint(expected_identities()))
        with self.assertRaisesRegex(BackupError, "CURRENT_CANONICAL_CRM74_REQUIRED"):
            describe(older, require_current=True)

    def test_fingerprint_matches_approved_design(self):
        design = Path(__file__).parents[1] / "docs/architecture/SCHEMA-LINEAGE-75-80-fingerprints.md"
        self.assertIn(f'| canonical74 | `{fingerprint(expected_identities())}` |',
                      design.read_text(encoding="utf-8"))
        # Identidad sin applied_at, no objetos ni autoridad.
        self.assertEqual(fingerprint(expected_identities()), fingerprint(expected_identities()))

    def test_wrong_name_gap_duplicate_future_and_corrupt(self):
        good = expected_identities()
        variants = [good[:73] + [[74, "wrong_name"]], good[:30] + good[31:],
                    good + [good[-1]], good + [[75, "future_unknown"]],
                    good[:73] + [[True, "captacion_hoja_y_tipo"]],
                    good[:73] + [[74.0, "captacion_hoja_y_tipo"]],
                    good[:73] + [[74, None]], [], list(reversed(good))]
        for identity in variants:
            with self.subTest(identity=identity[-1:] if identity else []):
                with self.assertRaises(BackupError):
                    describe(identity)

    def test_legacy_financial74_to79_never_current(self):
        for n in range(74, 80):
            legacy = expected_identities()[:73] + [[74 + i, name] for i, name in enumerate(LEGACY_NAMES[:n - 73])]
            identity = describe(legacy)
            self.assertEqual(identity["schema_lineage_id"], LEGACY_FINANCIAL)
            self.assertNotEqual(identity["schema_lineage_fingerprint"], fingerprint(expected_identities()))
            with self.assertRaisesRegex(BackupError, "CURRENT_CANONICAL_CRM74_REQUIRED"):
                describe(legacy, require_current=True)
            self.assertEqual(privacy_status(identity),
                             "POST_RESTORE_PRIVACY_RECONCILIATION_REQUIRED" if n >= 78 else "NO_E_INSTALLED")

    def test_legacy_mixed_names_rejected(self):
        legacy = expected_identities()[:73] + [[74, LEGACY_NAMES[0]], [75, "unknown"]]
        with self.assertRaisesRegex(BackupError, "MIGRATION_IDENTITY_MISMATCH"):
            describe(legacy)

    def test_null_registry_timestamp_rejected_without_changing_fingerprint(self):
        conn = Mock()
        conn.execute.return_value.fetchall.return_value = [(n, name, "synthetic-time")
                                                          for n, name in expected_identities()]
        self.assertEqual(read_identity(conn)["schema_lineage_fingerprint"], fingerprint(expected_identities()))
        conn.execute.return_value.fetchall.return_value[-1] = (74, "captacion_hoja_y_tipo", None)
        with self.assertRaisesRegex(BackupError, "SCHEMA_METADATA_INCOMPLETE"):
            read_identity(conn)

    def test_physical_sqlite_migration_paths_0_32_73_to74(self):
        for start in (0, 32, 73):
            with self.subTest(start=start), sqlite3.connect(":memory:") as raw:
                raw.row_factory = sqlite3.Row
                conn = db.Connection(raw, "sqlite")
                migrations.upgrade_connection(conn, start)
                self.assertEqual(migrations.upgrade_connection(conn), 74)
                rows = conn.execute("SELECT version,name FROM schema_migrations ORDER BY version").fetchall()
                self.assertEqual([[row["version"], row["name"]] for row in rows], expected_identities())
                self.assertIsNotNone(conn.execute("SELECT * FROM sales_sheets LIMIT 0"))
                self.assertEqual(conn.execute_exact("PRAGMA foreign_key_check").fetchall(), [])


class LegacyBackupIdentityContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with sqlite3.connect(":memory:") as raw:
            raw.row_factory = sqlite3.Row
            migrations.upgrade_connection(db.Connection(raw, "sqlite"))
            cls.columns = {row["name"]: [col[1] for col in raw.execute('PRAGMA table_info("' + row["name"] + '")')]
                           for row in raw.execute("SELECT name FROM sqlite_master WHERE type='table' AND name<>'sqlite_sequence' ORDER BY name")}

    def artifact(self, folder, identities, version=74):
        path = Path(folder) / "fixture.dump.gz"
        tables = list(self.columns)
        with gzip.open(path, "wt") as output:
            output.write(json.dumps({"format": backups.POSTGRES_DUMP_FORMAT, "schema_version": version,
                                    "tables": tables, "counts": {t: len(identities) if t == "schema_migrations" else 0 for t in tables}}) + "\n")
            for name, columns in self.columns.items():
                output.write(json.dumps({"type": "table", "name": name, "columns": columns}) + "\n")
                if name == "schema_migrations":
                    for n, label in identities:
                        row = {"version": n, "name": label, "applied_at": "2026-10-13T00:00:00"}
                        output.write(json.dumps({"type": "row", "values": [row[c] for c in columns]}) + "\n")
        return path

    def test_v1_current74_exact_registry_supported_offline(self):
        with tempfile.TemporaryDirectory() as folder:
            # Orden de almacenamiento V1 no promete orden numérico.
            path = self.artifact(folder, list(reversed(expected_identities())))
            self.assertEqual(backups._legacy_preflight(path)["schema_version"], 74)

    def test_v1_73_requires_catalog73(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.artifact(folder, expected_identities()[:73], 73)
            with self.assertRaisesRegex(BackupError, "MATCHING_SCHEMA_CATALOG"):
                backups._legacy_preflight(path)

    def test_v1_wrong_legacy_gap_duplicate_corrupt_future_rejected_before_target(self):
        good = expected_identities()
        variants = [(good[:73] + [[74, "wrong"]], 74),
                    (good[:73] + [[74, LEGACY_NAMES[0]]], 74),
                    (good[:20] + good[21:], 74), (good + [good[-1]], 74),
                    ([], 74), (good + [[75, "unknown"]], 75)]
        for rows, version in variants:
            with self.subTest(version=version, last=rows[-1:] if rows else []), tempfile.TemporaryDirectory() as folder:
                path = self.artifact(folder, rows, version)
                connection = Mock()
                with self.assertRaises(BackupError):
                    backups._restore_postgres_dump(connection, path)
                connection.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
