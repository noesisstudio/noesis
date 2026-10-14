"""Aislamiento del adaptador de fixtures: ninguna relajacion en producto."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noesis import config, db, migrations, schema_objects
from noesis.schema_lineage import inspect, SchemaLineageError
from tests.synthetic_schema_profiles import convert_storage, _validate, ORIGINAL_VALIDATE


class SyntheticProfileIsolation(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        settings = patch.multiple(config, DATABASE_URL="", DB_PATH=Path(folder.name)/"fixture.db", IS_PRODUCTION=False)
        settings.start()
        self.addCleanup(settings.stop)
        validation = patch.object(schema_objects, "validate_objects", ORIGINAL_VALIDATE)
        validation.start()
        self.addCleanup(validation.stop)
        migrations.upgrade()

    def converted(self):
        with db.get_conn() as conn:
            convert_storage(conn)

    def observation(self, conn):
        return inspect(conn, objects=False)

    def test_product_rejects_fixture_and_hash_is_separate(self):
        self.converted()
        with db.get_conn() as conn:
            conn.execute("BEGIN")
            observation = self.observation(conn)
            with self.assertRaises(SchemaLineageError):
                ORIGINAL_VALIDATE(conn, observation)
            profile, actual_hash = _validate(conn, observation)
            from noesis.schema_lineage import canonical
            import hashlib
            product_hash = hashlib.sha256(canonical(schema_objects.expected_objects("sqlite",75)).encode()).hexdigest()
            self.assertEqual(profile,"sqlite/canonical75/v1")
            self.assertNotEqual(actual_hash,product_hash)

    def test_partial_or_unknown_storage_never_matches_fixture(self):
        with db.get_conn() as conn:
            conn.execute("PRAGMA writable_schema=ON")
            import re
            ddl = conn.execute("SELECT sql FROM sqlite_master WHERE name='expenses'").fetchone()["sql"]
            conn.execute("UPDATE sqlite_master SET sql=? WHERE name='expenses'", (re.sub(r"\bamount\s+REAL\b", "amount TEXT", ddl),))
            conn.execute("PRAGMA schema_version=999")
            conn.execute("PRAGMA writable_schema=OFF")
        with db.get_conn() as conn:
            conn.execute("BEGIN")
            with self.assertRaises(SchemaLineageError):
                _validate(conn, self.observation(conn))

    def test_fixture_never_hides_missing_financial_guard(self):
        self.converted()
        with db.get_conn() as conn:
            conn.execute("DROP TRIGGER financial_readiness_evaluations_insert")
        with db.get_conn() as conn:
            conn.execute("BEGIN")
            with self.assertRaises(SchemaLineageError):
                _validate(conn,self.observation(conn))

    def test_production_mode_never_accepts_fixture(self):
        self.converted()
        with patch.object(config,"IS_PRODUCTION",True), db.get_conn() as conn:
            conn.execute("BEGIN")
            with self.assertRaises(SchemaLineageError):
                _validate(conn,self.observation(conn))
