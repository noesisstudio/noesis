"""Lineage sobre SQLite sintética: falsificaciones no pasan por MAX(version)."""

from pathlib import Path
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch

from noesis import config, db, migrations
from noesis.schema_lineage import (
    CATALOG, LineageId, SchemaLineageError, classify_registry, fingerprint,
    inspect, require_runtime,
)


CRM74_GOLDEN = "ee2de64c6e47629811c6cee2bfa8f28fea66bb9e23e28caa50bc0b62db697e24"  # pragma: allowlist secret; public golden
A75_GOLDEN = "289b8eb580edd4c45d2de40233ffd7dfc193999b10f49825661cba18905696a1"  # pragma: allowlist secret; public golden


class RegistryContract(unittest.TestCase):
    def test_canonical_prefixes_and_goldens(self):
        for n, lineage in ((73, LineageId.CANONICAL_PRE74), (74, LineageId.CANONICAL_CRM74),
                           (75, LineageId.CANONICAL_FINANCIAL_75_80_PREFIX)):
            with self.subTest(n=n):
                observation = classify_registry(CATALOG[:n])
                self.assertEqual(observation.lineage_id, lineage)
                self.assertEqual(observation.schema_version, n)
                self.assertFalse(observation.errors)
        self.assertEqual(fingerprint(CATALOG[:74]), CRM74_GOLDEN)
        self.assertEqual(fingerprint(CATALOG), A75_GOLDEN)
        self.assertEqual(fingerprint(tuple(reversed(CATALOG))), A75_GOLDEN)

    def test_legacy_sentinel_always_blocks_even_mixed_or_gapped(self):
        for tail in ([(74, "evaluacion_readiness_financiera")],
                     [(74, "evaluacion_readiness_financiera"), (75, "resoluciones_antecedentes_financieros")],
                     [(74, "evaluacion_readiness_financiera"), (76, "wrong")]):
            observation = classify_registry(list(CATALOG[:73]) + tail)
            self.assertEqual(observation.lineage_id, LineageId.LEGACY_FINANCIAL_74_79)
            with self.assertRaisesRegex(SchemaLineageError, "LEGACY_FINANCIAL"):
                observation.require_canonical((74, 75))

    def test_invalid_metadata_and_wrong_names(self):
        cases = [list(CATALOG[:74]) + [(75, "unknown")], list(CATALOG[:73]) + [(74, "unknown")],
                 list(CATALOG[:74]) + [(75, None)], list(CATALOG) + [(75, CATALOG[-1][1])],
                 list(CATALOG[:31]) + list(CATALOG[32:]), [(True, "esquema_inicial")],
                 [(1.0, "esquema_inicial")], [(0, "unknown")], [(-1, "unknown")]]
        for rows in cases:
            with self.subTest(rows=rows[-2:]):
                self.assertEqual(classify_registry(rows).lineage_id, LineageId.UNKNOWN_OR_CORRUPT)
                self.assertTrue(classify_registry(rows).errors)

    def test_future_designed_does_not_mean_installed(self):
        for number, name in ((76, "resoluciones_antecedentes_financieros"), (81, "unknown")):
            observation = classify_registry(list(CATALOG) + [(number, name)])
            self.assertEqual(observation.errors, ("FUTURE_SCHEMA_UNSUPPORTED",))
            with self.assertRaises(SchemaLineageError):
                observation.require_canonical((75,))

    def test_pure_lexer_cache_cannot_hide_changed_sql_or_be_mutated(self):
        from noesis.schema_objects import normalized_sql
        first = normalized_sql("CREATE TABLE sample (amount NUMERIC NOT NULL)")
        first.append("forged")
        self.assertNotIn("forged", normalized_sql("CREATE TABLE sample (amount NUMERIC NOT NULL)"))
        self.assertNotEqual(normalized_sql("CREATE TABLE sample (amount NUMERIC NOT NULL)"),
                            normalized_sql("CREATE TABLE sample (amount REAL NOT NULL)"))
        self.assertNotEqual(normalized_sql("CHECK (state='off')"), normalized_sql("CHECK (state='enabled')"))
        self.assertNotEqual(normalized_sql("CHECK (note='public.amount')", "public"),
                            normalized_sql("CHECK (note='amount')", "public"))
        self.assertNotEqual(normalized_sql('NEW."Amount"'), normalized_sql('NEW."amount"'))
        self.assertEqual(normalized_sql('CREATE TABLE public.sample (id INTEGER)', 'public'),
                         normalized_sql('CREATE TABLE sample (id INTEGER)'))

    def test_relevant_identity_changes_hash(self):
        changed = list(CATALOG)
        changed[-1] = (75, "evaluacion_readiness_financiera ")
        self.assertNotEqual(fingerprint(changed), A75_GOLDEN)
        self.assertTrue(classify_registry(changed).errors)


class SchemaLineageSQLite(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="noesis-lineage-")
        self.addCleanup(directory.cleanup)
        settings = patch.multiple(config, DATABASE_URL="", DB_PATH=Path(directory.name) / "fixture.db")
        settings.start()
        self.addCleanup(settings.stop)

    def observation(self):
        with db.get_conn() as conn:
            conn.execute("BEGIN")
            return inspect(conn)

    def test_corrupt_empty_registry_fails_before_any_callback(self):
        with db.get_conn() as conn:
            conn.execute("CREATE TABLE schema_migrations(version INTEGER,name TEXT NOT NULL,applied_at TEXT NOT NULL,PRIMARY KEY(version,name))")
        with patch.object(migrations, "_ensure_version_table", side_effect=AssertionError("DDL before identity")):
            with self.assertRaisesRegex(SchemaLineageError, "METADATA_INCOMPLETE"):
                migrations.upgrade(1)

    def test_fresh_and_staged_migration_paths(self):
        self.assertEqual(migrations.upgrade(73), 73)
        self.assertEqual(self.observation().lineage_id, LineageId.CANONICAL_PRE74)
        with db.get_conn() as conn:
            before = conn.execute_exact("SELECT * FROM schema_migrations ORDER BY version").fetchall()
        self.assertEqual(migrations.upgrade(74), 74)
        self.assertEqual(self.observation().lineage_id, LineageId.CANONICAL_CRM74)
        self.assertEqual(migrations.upgrade(75), 75)
        observed = self.observation()
        self.assertEqual(observed.integrity, "VERIFIED")
        self.assertEqual(observed.lineage_fingerprint, A75_GOLDEN)
        with db.get_conn() as conn:
            self.assertEqual(before, conn.execute_exact("SELECT * FROM schema_migrations WHERE version<=73 ORDER BY version").fetchall())
            self.assertEqual(conn.execute("SELECT COUNT(*) AS n FROM financial_activation_control").fetchone()["n"], 0)

    def test_fresh_zero_to75_and_current_no_writes(self):
        self.assertEqual(migrations.upgrade(), 75)
        with db.get_conn() as conn:
            before = conn.execute_exact("SELECT * FROM schema_migrations ORDER BY version").fetchall()
        self.assertEqual(migrations.upgrade(), 75)
        with db.get_conn() as conn:
            self.assertEqual(before, conn.execute_exact("SELECT * FROM schema_migrations ORDER BY version").fetchall())

    def test_legacy74_rejected_before_any_new_ddl(self):
        migrations.upgrade(74)
        with db.get_conn() as conn:
            conn.execute("UPDATE schema_migrations SET name='evaluacion_readiness_financiera' WHERE version=74")
        with self.assertRaisesRegex(SchemaLineageError, "LEGACY_FINANCIAL"):
            migrations.upgrade()
        with db.get_conn() as conn:
            self.assertIsNone(conn.execute("SELECT 1 FROM sqlite_master WHERE name='financial_activation_control'").fetchone())
        self.assertFalse(migrations.is_current())

    def test_wrong_name_gap_and_future_rejected_without_repair(self):
        migrations.upgrade(74)
        with db.get_conn() as conn:
            conn.execute("UPDATE schema_migrations SET name='wrong' WHERE version=74")
        with self.assertRaisesRegex(SchemaLineageError, "IDENTITY_MISMATCH"):
            migrations.upgrade()
        with db.get_conn() as conn:
            conn.execute("UPDATE schema_migrations SET name='captacion_hoja_y_tipo' WHERE version=74")
            conn.execute("DELETE FROM schema_migrations WHERE version=31")
        with self.assertRaisesRegex(SchemaLineageError, "MIGRATION_GAP"):
            migrations.upgrade()

    def test_row75_without_a_tables_fails_closed(self):
        migrations.upgrade(74)
        with db.get_conn() as conn:
            conn.execute("INSERT INTO schema_migrations VALUES (75,'evaluacion_readiness_financiera','2026-10-13')")
        self.assertIn("SCHEMA_OBJECT_MISMATCH", self.observation().errors)
        with self.assertRaisesRegex(SchemaLineageError, "OBJECT_MISMATCH"):
            migrations.upgrade()

    def test_critical_trigger_integrity(self):
        migrations.upgrade()
        with db.get_conn() as conn:
            conn.execute("DROP TRIGGER financial_readiness_evaluations_insert")
        self.assertIn("SCHEMA_OBJECT_MISMATCH", self.observation().errors)
        self.assertFalse(migrations.is_current())

    def test_unknown_financial_objects_cannot_hide_behind_quoted_case(self):
        migrations.upgrade()
        for name in ("Financial_unrecognized", "economic_unrecognized", "fiscal_cancellation_unrecognized"):
            with self.subTest(name=name):
                with db.get_conn() as conn:
                    conn.execute('CREATE TABLE "' + name + '" (id INTEGER)')
                self.assertIn("SCHEMA_OBJECT_MISMATCH", self.observation().errors)
                with self.assertRaises(SchemaLineageError):
                    migrations.upgrade()
                self.assertFalse(migrations.is_current())
                with db.get_conn() as conn:
                    conn.execute('DROP TABLE "' + name + '"')
        for kind, ddl in (("INDEX", "CREATE INDEX unrelated_alias ON expenses(concept)"),
                          ("TRIGGER", "CREATE TRIGGER unrelated_alias AFTER INSERT ON expenses BEGIN SELECT 1; END")):
            with self.subTest(kind=kind):
                with db.get_conn() as conn:
                    conn.execute(ddl)
                self.assertIn("SCHEMA_OBJECT_MISMATCH", self.observation().errors)
                with db.get_conn() as conn:
                    conn.execute(f"DROP {kind} unrelated_alias")

    def test_missing_registry_cannot_bootstrap_over_objects(self):
        migrations.upgrade(74)
        with db.get_conn() as conn:
            conn.execute("DROP TABLE schema_migrations")
        with self.assertRaisesRegex(SchemaLineageError, "METADATA_INCOMPLETE"):
            migrations.upgrade()

    def test_registry_shape_duplicate_and_noninteger(self):
        migrations.upgrade(74)
        with db.get_conn() as conn:
            conn.execute("ALTER TABLE schema_migrations RENAME TO saved_registry")
            conn.execute("CREATE TABLE schema_migrations(version REAL,name TEXT,applied_at TEXT)")
            conn.execute("INSERT INTO schema_migrations SELECT * FROM saved_registry")
            conn.execute("INSERT INTO schema_migrations SELECT * FROM saved_registry WHERE version=74")
        self.assertIn("SCHEMA_METADATA_INCOMPLETE", self.observation().errors)
        with self.assertRaises(SchemaLineageError):
            migrations.upgrade()

    def test_two_sqlite_migrators_revalidate_after_serialization(self):
        migrations.upgrade(74)
        start = threading.Barrier(2)
        def worker(_):
            start.wait(timeout=10)
            return migrations.upgrade()
        with ThreadPoolExecutor(max_workers=2) as workers:
            self.assertEqual(list(workers.map(worker, range(2))), [75, 75])
        self.assertEqual(self.observation().schema_version, 75)
        with db.get_conn() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS n FROM schema_migrations WHERE version=75").fetchone()["n"], 1)

    def test_callback_and_postvalidator_failure_rollback_whole_step(self):
        migrations.upgrade(74)
        def incomplete(conn):
            migrations._upgrade_readiness75(conn)
            conn.execute("DROP INDEX idx_readiness_created")
        entries = migrations.MIGRATIONS[:-1] + ((75, CATALOG[-1][1], incomplete, migrations._downgrade_readiness75),)
        with patch.object(migrations, "MIGRATIONS", entries), self.assertRaisesRegex(SchemaLineageError, "OBJECT_MISMATCH"):
            migrations.upgrade()
        self.assertEqual(self.observation().schema_version, 74)
        with db.get_conn() as conn:
            self.assertIsNone(conn.execute("SELECT 1 FROM sqlite_master WHERE name='financial_activation_control'").fetchone())
        self.assertEqual(migrations.upgrade(), 75)

    def test_borrowed_check_requires_tx_and_never_owns_commit(self):
        migrations.upgrade()
        with db.get_conn() as conn:
            with self.assertRaisesRegex(SchemaLineageError, "TX_PROTOCOL"):
                require_runtime(conn)
            conn.execute("BEGIN")
            with patch.object(conn, "commit", side_effect=AssertionError("commit propio")), patch.object(conn, "rollback", side_effect=AssertionError("rollback propio")):
                self.assertEqual(require_runtime(conn).schema_version, 75)
                self.assertTrue(conn.raw.in_transaction)

    def technical_fixture(self):
        migrations.upgrade()
        self.assertEqual(migrations.downgrade(10), 10)
        self.assertEqual(migrations.upgrade(), 75)

    def test_synthetic_technical_roundtrip_never_accredits_runtime_or_binding(self):
        from noesis.schema_lineage import lock_migrator
        self.technical_fixture()
        with db.get_conn() as conn:
            lock_migrator(conn)
            observation = inspect(conn)
            self.assertEqual(observation.integrity, "TECHNICAL_ONLY")
            with self.assertRaises(SchemaLineageError):
                observation.binding()
            with self.assertRaises(SchemaLineageError):
                require_runtime(conn)
            self.assertIsNone(conn.execute("SELECT 1 FROM financial_readiness_evaluations").fetchone())
        self.assertFalse(migrations.is_current())

    def test_technical_variant_never_available_in_production_mode(self):
        self.technical_fixture()
        with patch.object(config, "IS_PRODUCTION", True):
            with self.assertRaisesRegex(SchemaLineageError, "OBJECT_MISMATCH"):
                migrations.upgrade()
        self.assertEqual(migrations.current_version(), 75)

    def test_technical_variant_requires_actual_connection_file_binding(self):
        from noesis.schema_lineage import lock_migrator
        self.technical_fixture()
        with db.get_conn() as conn:
            lock_migrator(conn)
            with patch.object(config, "DB_PATH", Path(config.DB_PATH).with_name("unrelated.db")):
                self.assertIn("SCHEMA_OBJECT_MISMATCH", inspect(conn).errors)

    def test_technical_variant_does_not_tolerate_missing_financial_guards(self):
        self.technical_fixture()
        with db.get_conn() as conn:
            conn.execute("DROP TRIGGER financial_readiness_evaluations_insert")
        with self.assertRaisesRegex(SchemaLineageError, "OBJECT_MISMATCH"):
            migrations.upgrade()


if __name__ == "__main__":
    unittest.main()
