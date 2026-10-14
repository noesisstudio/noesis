"""POSTGRES_BACKUP_V2 A–Y: PostgreSQL18 real, sólo namespace sin outbound."""
import gzip
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import Mock, patch

from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

from noesis import config, db, migrations
from noesis.core.persistence import FinancialSession
from noesis.financial_activation.contracts import Capability, Profile
from noesis.financial_activation.evaluator import FinancialReadinessEvaluator
from noesis.financial_operations.contracts import Principal
from noesis.schema_lineage import canonical, require_runtime
from noesis.schema_objects import expected_objects, physical_objects
from noesis.web import backups, postgres_native_backup as native
from noesis.web import postgres_backup_tools as tools
from noesis.web.postgres_backup_identity import LEGACY_FINANCIAL, expected_identities, describe
from tests.postgres_identity_diagnostic import amount_check, object_diff
from tests.postgres_check_semantics import AmountCheckSemanticProof


class PostgresBackupV2(AmountCheckSemanticProof, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not tools.outbound_blocked():
            raise RuntimeError("Matriz requiere namespace sin outbound")
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.folder = Path(cls.temporary.name)
        cls.documents = cls.folder / "documents"
        cls.documents.mkdir()
        (cls.documents / "sample.txt").write_text("Documento sintético de matriz V2", encoding="utf-8")
        cls.source_context = tools.disposable_target()
        cls.source = cls.source_context.__enter__()
        cls.addClassCleanup(cls.source_context.__exit__, None, None, None)
        cls.docs_patch = patch.object(backups.config, "DOCS_PATH", cls.documents)
        cls.docs_patch.start()
        cls.addClassCleanup(cls.docs_patch.stop)
        with cls.source.connection() as conn:
            conn.row_factory = dict_row
            migrations.upgrade_connection(db.Connection(conn, "postgres"))
        # Evidencia A75 sintética poblada: no basta un roundtrip de tablas vacías.
        db.close_pool()
        try:
            with patch.object(config, "DATABASE_URL", cls.source.dsn):
                with db.get_conn() as conn:
                    conn.execute("SELECT setval(pg_get_serial_sequence('businesses','id'),200000)")
                business = db.create_business("A75 synthetic restore")
                cls.bid = business["id"]
                if cls.bid == 15:
                    raise AssertionError("Business piloto reservado")
                db.set_trial(cls.bid, days=14)
                user = db.create_user("a75-restore@example.test", "fixture", cls.bid)
                with db.get_conn() as conn:
                    cls.evaluation = FinancialReadinessEvaluator(FinancialSession(conn), cls.bid).evaluate(
                        Principal(user["id"], 0), uuid4(), Profile((Capability.EXPENSE_CONFIRM,)),
                        code_version="synthetic-restore")
        finally:
            db.close_pool()
        cls.archive75 = cls.folder / "source75.pgdump"
        cls.manifest75 = native.create(cls.source.dsn, cls.archive75, backups._create_documents_backup,
                                       backups._verify_documents_backup)
        with cls.source.connection() as conn:
            conn.row_factory = dict_row
            cls.source75_objects = physical_objects(db.Connection(conn, "postgres"), "public")
            cls.source_check = amount_check(db.Connection(conn, 'postgres'), 'v2-source-check')
            object_diff(db.Connection(conn, 'postgres'), 'v2-source0-to75-profile')
            cls.evaluation_body = conn.execute(
                "SELECT result_canonical FROM financial_readiness_evaluations WHERE business_id=%s",
                (cls.bid,),
            ).fetchone()["result_canonical"]
        # Destino A propio: restaurar ANTES de añadir future/hstore al origen.
        cls.target75_context = tools.disposable_target()
        cls.target75 = cls.target75_context.__enter__()
        cls.addClassCleanup(cls.target75_context.__exit__, None, None, None)
        with patch.object(migrations, "upgrade_connection", side_effect=AssertionError("V2 cannot migrate")):
            cls.result75 = native.restore(cls.archive75, cls.target75, backups._verify_documents_backup)
        with cls.target75.connection() as conn:
            conn.row_factory = dict_row
            cls.restored_check = amount_check(db.Connection(conn, 'postgres'), 'v2-restored-check')
            object_diff(db.Connection(conn, 'postgres'), 'v2-restored-profile')
        with cls.source.connection() as conn:
            conn.execute("CREATE SCHEMA future")
            conn.execute("CREATE TYPE future.status AS ENUM ('open','closed')")
            conn.execute("CREATE DOMAIN future.positive AS numeric(20,4) CHECK (VALUE>=0)")
            conn.execute("CREATE COLLATION future.from_c (provider=libc,locale='C')")
            conn.execute("CREATE TABLE future.parent (id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,"
                         "extra future.status NOT NULL, amount future.positive, label text COLLATE future.from_c, UNIQUE(extra), CHECK (id>0))")
            conn.execute("CREATE TABLE future.child (id integer PRIMARY KEY, parent_id bigint,"
                         "FOREIGN KEY(parent_id) REFERENCES future.parent(id) DEFERRABLE INITIALLY DEFERRED)")
            conn.execute("CREATE INDEX unknown_amount ON future.parent(amount)")
            conn.execute("CREATE FUNCTION future.guard() RETURNS trigger LANGUAGE plpgsql AS "
                         "'BEGIN IF NEW.amount<1 THEN RAISE EXCEPTION ''blocked''; END IF; RETURN NEW; END'")
            conn.execute("CREATE TRIGGER unknown_guard BEFORE INSERT ON future.parent "
                         "FOR EACH ROW EXECUTE FUNCTION future.guard()")
            conn.execute("CREATE VIEW future.unknown_view AS SELECT id,amount FROM future.parent")
            conn.execute("CREATE EXTENSION hstore")
            conn.execute("INSERT INTO future.parent(extra,amount) VALUES ('open',1234567890123.4567)")
            conn.execute("INSERT INTO future.child VALUES (1,1)")
            conn.execute("SELECT setval('future.parent_id_seq', 500, true)")
        cls.archive = cls.folder / "unknown-objects75.pgdump"
        cls.manifest = native.create(cls.source.dsn, cls.archive, backups._create_documents_backup,
                                    backups._verify_documents_backup)
        cls.target_context = tools.disposable_target()
        cls.target = cls.target_context.__enter__()
        cls.addClassCleanup(cls.target_context.__exit__, None, None, None)
        with patch.object(migrations, "upgrade_connection", side_effect=AssertionError("V2 cannot migrate")):
            cls.result = native.restore(cls.archive, cls.target, backups._verify_documents_backup)

    def copy_set(self):
        path = self.folder / "copy.pgdump"
        for suffix in (".pgdump", ".docs.zip", ".manifest.json"):
            shutil.copyfile(native.pair(self.archive, suffix), native.pair(path, suffix))
        return path

    def test_A_dump18(self):
        self.assertEqual(tools.Toolchain.discover().major, 18)
        with self.assertRaises(tools.BackupError):
            tools.Toolchain.discover().check_server(19)

    def test_B_restore18(self):
        self.assertIn("18.6", self.result["pg_restore_version"])

    def test_C_backup75_restore75(self):
        result = native.verify(self.archive75, backups._verify_documents_backup)
        self.assertEqual(result["schema_version"], 75)
        self.assertEqual(result["technical_integrity"], "PASS")

    def test_D_unknown_objects75_restore_runner75(self):
        self.assertEqual(migrations.LATEST_VERSION, 75)
        self.assertEqual(self.result["schema_version"], 75)
        self.assertEqual(self.result["privacy_status"], "NO_E_INSTALLED")
        self.assertFalse(self.result["serving_authorized"])
        self.assertFalse(self.result["g_real_evidence"])
        self.assertEqual(self.result["schema_lineage_id"], "CANONICAL_CRM74_FINANCIAL75_80")
        self.assertEqual(self.manifest["migration_identities"], expected_identities())
        self.assertEqual(self.manifest["manifest_contract_version"], 2)
        self.assertEqual(self.result["schema_lineage_fingerprint"], self.manifest["schema_lineage_fingerprint"])

    def test_populated_A75_restore_preserves_hash_binding_and_off_state(self):
        with self.target75.connection() as raw:
            raw.row_factory = dict_row
            restored = physical_objects(db.Connection(raw, "postgres"), "public")
            self.assertIsNone(raw.execute("SELECT to_regnamespace('future') AS namespace").fetchone()["namespace"])
            self.assertIsNone(raw.execute("SELECT extname FROM pg_extension WHERE extname='hstore'").fetchone())
        expected = expected_objects("postgres", 75)
        source = self.source75_objects
        differences = []
        for key in sorted(set(source) | set(expected) | set(restored)):
            if source.get(key) == expected.get(key) == restored.get(key):
                continue
            def digest(objects):
                return hashlib.sha256(canonical(objects[key]).encode("utf-8")).hexdigest() if key in objects else None
            differences.append({"object_key": key,
                                "classification": "missing" if key not in restored else "extra" if key not in expected else "changed",
                                "source_hash": digest(source), "expected_hash": digest(expected),
                                "restored_hash": digest(restored)})
        print("V2_CANONICAL75_OBJECT_DIFF " + json.dumps(differences, sort_keys=True), flush=True)
        # Sólo hashes en diagnóstico: nunca exponer descriptor SQL ni datos.
        self.assertFalse(differences, "V2 STRUCTURAL MISMATCH: " + json.dumps(differences, sort_keys=True))
        db.close_pool()
        try:
            with patch.object(config, "DATABASE_URL", self.target75.dsn):
                with db.get_conn() as conn:
                    observed = require_runtime(conn)
                    self.assertEqual(observed.schema_version, 75)
                    self.assertEqual(observed.binding(), self.evaluation["context"]["schema_binding"])
                    row = conn.execute("SELECT result_canonical,content_hash FROM financial_readiness_evaluations WHERE business_id=?", (self.bid,)).fetchone()
                    self.assertEqual(row["content_hash"], self.evaluation["content_hash"])
                    body = json.loads(row["result_canonical"])
                    self.assertTrue(row["result_canonical"] == self.evaluation_body, "Restored evaluation body must be byte-exact")
                    self.assertEqual(body["context"], self.evaluation["context"])
                    self.assertEqual(body["capabilities"], self.evaluation["capabilities"])
                    control = conn.execute("SELECT state,activation_generation,ever_enabled FROM financial_activation_control WHERE business_id=?", (self.bid,)).fetchone()
                    self.assertEqual((control["state"], control["activation_generation"], control["ever_enabled"]), ("off", 0, False))
                    for table in ('economic_events', 'financial_operations'):
                        self.assertEqual(conn.execute("SELECT COUNT(*) AS n FROM " + table + " WHERE business_id=?", (self.bid,)).fetchone()["n"], 0)
        finally:
            db.close_pool()
        self.assertEqual(self.result75["technical_integrity"], "PASS")
        self.assertEqual(self.result75["privacy_status"], "NO_E_INSTALLED")
        self.assertFalse(self.result75["serving_authorized"])
        self.assertFalse(self.result75["g_real_evidence"])

    def test_corrupt_registry_shape_cannot_claim_canonical75_backup(self):
        with tools.disposable_target() as source:
            with source.connection() as raw:
                raw.row_factory = dict_row
                migrations.upgrade_connection(db.Connection(raw, "postgres"))
                raw.execute("ALTER TABLE schema_migrations DROP CONSTRAINT schema_migrations_pkey")
            with self.assertRaisesRegex(tools.BackupError, "METADATA_INCOMPLETE"):
                native.create(source.dsn, self.folder / "corrupt-registry75.pgdump",
                              backups._create_documents_backup, backups._verify_documents_backup)

    def test_E_unknown_table(self):
        with self.target.connection() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM future.parent").fetchone()[0], 1)

    def test_F_unknown_column_decimal(self):
        with self.target.connection() as conn:
            value = conn.execute("SELECT amount FROM future.parent").fetchone()[0]
            self.assertEqual(str(value), "1234567890123.4567")

    def test_G_index(self):
        with self.target.connection() as conn:
            self.assertIsNotNone(conn.execute("SELECT to_regclass('future.unknown_amount')").fetchone()[0])

    def test_H_fk(self):
        with self.target.connection() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM pg_constraint WHERE conrelid='future.child'::regclass AND contype='f'").fetchone()[0], 1)

    def test_I_check(self):
        with self.target.connection() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM pg_constraint WHERE conrelid='future.parent'::regclass AND contype='c'").fetchone()[0], 1)

    def test_J_deferred(self):
        with self.target.connection() as conn:
            self.assertEqual(conn.execute("SELECT condeferrable,condeferred FROM pg_constraint WHERE conrelid='future.child'::regclass AND contype='f'").fetchone(), (True, True))

    def test_K_trigger(self):
        with self.target.connection() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM pg_trigger WHERE tgname='unknown_guard'").fetchone()[0], 1)

    def test_L_function(self):
        with self.target.connection() as conn:
            self.assertIsNotNone(conn.execute("SELECT to_regprocedure('future.guard()')").fetchone()[0])

    def test_M_sequence_value(self):
        with self.target.connection() as conn:
            self.assertEqual(conn.execute("SELECT last_value,is_called FROM future.parent_id_seq").fetchone(), (500, True))

    def test_N_schema_version(self):
        with self.target.connection() as conn:
            self.assertEqual(conn.execute("SELECT max(version) FROM schema_migrations").fetchone()[0], 75)

    def test_O_missing_archive(self):
        path = self.copy_set()
        path.unlink()
        with self.assertRaisesRegex(tools.BackupError, "INCOMPLETE"):
            native.load_set(path, backups._verify_documents_backup)

    def test_P_corrupted_archive_even_with_updated_hash(self):
        path = self.copy_set()
        path.write_bytes(b"invalid custom archive")
        manifest = json.loads(native.pair(path, ".manifest.json").read_text())
        manifest.update(archive_sha256=native.file_hash(path), archive_size=path.stat().st_size)
        native.pair(path, ".manifest.json").write_text(json.dumps(manifest))
        with tools.disposable_target() as target, self.assertRaisesRegex(tools.BackupError, "NATIVE_TOOL_FAILED"):
            native.restore(path, target, backups._verify_documents_backup)

    def test_Q_hash_mismatch(self):
        path = self.copy_set()
        with path.open("ab") as output:
            output.write(b"corrupt")
        with self.assertRaisesRegex(tools.BackupError, "HASH_MISMATCH"):
            native.load_set(path, backups._verify_documents_backup)

    def test_R_missing_docs(self):
        path = self.copy_set()
        native.pair(path, ".docs.zip").unlink()
        with self.assertRaisesRegex(tools.BackupError, "INCOMPLETE"):
            native.load_set(path, backups._verify_documents_backup)

    def test_S_docs_hash_mismatch(self):
        path = self.copy_set()
        native.pair(path, ".docs.zip").write_bytes(b"damaged")
        with self.assertRaisesRegex(tools.BackupError, "HASH_MISMATCH"):
            native.load_set(path, backups._verify_documents_backup)

    def test_T_missing_extension_blocks(self):
        with self.target.connection() as conn, self.assertRaisesRegex(tools.BackupError, "EXTENSION_UNAVAILABLE"):
            native.check_extensions(conn, [["noesis_nonexistent_extension", "0.0"]])

    def test_U_v1_newer_rejected_before_DDL(self):
        path = self.folder / "legacy.dump.gz"
        with gzip.open(path, "wt") as stream:
            stream.write(json.dumps({"format": backups.POSTGRES_DUMP_FORMAT, "schema_version": 79}) + "\n")
        raw = Mock()
        with self.assertRaisesRegex(tools.BackupError, "LEGACY_BACKUP_REQUIRES_NEWER_SCHEMA_CATALOG"):
            backups._restore_postgres_dump(raw, path)
        raw.execute.assert_not_called()

    def test_V_secrets_excluded_and_password_file_removed(self):
        with tools.libpq_environment(make_conninfo(host="/tmp/fixture", dbname="fixture", user="fixture", password="synthetic-only")) as env:  # pragma: allowlist secret - contraseña ficticia de test
            path = Path(env["PGPASSFILE"])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("PGPASSWORD", env)
        self.assertFalse(path.exists())
        text = native.pair(self.archive, ".manifest.json").read_text()
        for forbidden in ("synthetic-only", self.source.dsn, "DATABASE_URL", "PGPASSWORD"):
            self.assertNotIn(forbidden, text)

    def test_W_nonempty_rejected(self):
        with tools.disposable_target() as target:
            with target.connection() as conn:
                conn.execute("CREATE TABLE unrelated(id int)")
            with self.assertRaisesRegex(tools.BackupError, "DESTINATION_NOT_EMPTY"):
                native.restore(self.archive, target, backups._verify_documents_backup)

    def test_X_source_and_arbitrary_target_rejected(self):
        with self.assertRaises(tools.BackupError):
            native.restore(self.archive, self.source, backups._verify_documents_backup)
        with self.assertRaisesRegex(tools.BackupError, "DISPOSABLE_TARGET_REQUIRED"):
            native.restore(self.archive, self.source.dsn, backups._verify_documents_backup)

    def test_Y_no_migrations_and_all_object_inventory(self):
        # setUpClass restaura con migrations.upgrade_connection reemplazado por excepción.
        self.assertEqual(self.result["technical_integrity"], "PASS")
        classes = self.manifest["archive_object_classes"]
        for kind in ("TABLE", "TABLE DATA", "SEQUENCE", "SEQUENCE SET", "INDEX", "CONSTRAINT",
                     "FK CONSTRAINT", "FUNCTION", "TRIGGER", "TYPE", "DOMAIN", "VIEW", "EXTENSION"):
            self.assertGreater(classes.get(kind, 0), 0, kind)
        with self.target.connection() as conn:
            self.assertIsNotNone(conn.execute(sql.SQL("SELECT to_regclass(%s)"), ("future.unknown_view",)).fetchone()[0])

    def test_destination_immutable_and_expired(self):
        with tools.disposable_target() as target:
            with self.assertRaises(AttributeError):
                target.dsn = self.source.dsn
        with self.assertRaisesRegex(tools.BackupError, "DISPOSABLE_TARGET_REQUIRED"):
            target.connection()

    def test_consumed_target_cannot_be_reused(self):
        with self.assertRaisesRegex(tools.BackupError, "DESTINATION_NOT_EMPTY"):
            native.restore(self.archive, self.target, backups._verify_documents_backup)

    def test_different_instance_identity_blocks_before_restore(self):
        path = self.copy_set()
        with tools.disposable_target() as target:
            manifest_path = native.pair(path, ".manifest.json")
            manifest = json.loads(manifest_path.read_text())
            manifest['source_database_fingerprint'] = target.identity
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(tools.BackupError, "IDENTITY_MISMATCH"):
                native.restore(path, target, backups._verify_documents_backup)

    def test_v1_75_supported_but_unknown_table_75_rejected(self):
        with tools.disposable_target() as source:
            with source.connection() as conn:
                conn.row_factory = dict_row
                migrations.upgrade_connection(db.Connection(conn, "postgres"))
            with patch.object(backups.config, "DATABASE_URL", source.dsn), patch.object(backups.config, "BACKUP_DIR", self.folder):
                path, counts = backups._create_postgres_backup_v1()
                backups._verify_postgres_backup(path, counts)
            with gzip.open(path, "rt") as stream:
                records = stream.readlines()
            header = json.loads(records[0])
            header['tables'].append('unknown_future')
            header['counts']['unknown_future'] = 0
            records[0] = json.dumps(header)+'\n'
            records.append(json.dumps({'type':'table','name':'unknown_future','columns':['id']})+'\n')
            with gzip.open(path, "wt") as stream:
                stream.writelines(records)
            raw = Mock()
            with self.assertRaisesRegex(tools.BackupError, "LEGACY_BACKUP_REQUIRES_NEWER_SCHEMA_CATALOG"):
                backups._restore_postgres_dump(raw, path)
            raw.execute.assert_not_called()

    def test_missing_ddl_detected(self):
        path = self.copy_set()
        manifest_path = native.pair(path, ".manifest.json")
        manifest = json.loads(manifest_path.read_text())
        manifest['objects']['indexes']['sha256'] = '0'*64
        manifest_path.write_text(json.dumps(manifest))
        with tools.disposable_target() as target, self.assertRaisesRegex(tools.BackupError, "INVENTORY_MISMATCH.*indexes"):
            native.restore(path, target, backups._verify_documents_backup)

    def test_failed_dump_removes_only_owned_partial_set(self):
        path = self.folder / "failed.pgdump"
        good = self.archive
        def failure(argv, **kwargs):
            if any(arg.startswith('--file=') for arg in argv):
                native.pair(path, '.pgdump.part').write_bytes(b'partial')
                raise tools.BackupError('NATIVE_TOOL_FAILED')
            return tools.run(argv, **kwargs)
        with patch.object(native, 'run', side_effect=failure):
            with self.assertRaisesRegex(tools.BackupError, "NATIVE_TOOL_FAILED"):
                native.create(self.source.dsn,path,backups._create_documents_backup,backups._verify_documents_backup)
        self.assertFalse(path.exists())
        self.assertFalse(native.pair(path, '.pgdump.part').exists())
        native.load_set(good,backups._verify_documents_backup)

    def test_database_locale_roundtrip(self):
        settings = {"encoding":"UTF8", "provider":"c", "lc_collate":"C.utf8", "lc_ctype":"C.utf8",
                    "locale":None, "collation_version":None, "icu_rules":None}
        with tools.disposable_target(settings=settings) as source:
            with source.connection() as conn:
                conn.row_factory = dict_row
                migrations.upgrade_connection(db.Connection(conn, "postgres"))
            path = self.folder / "locale.pgdump"
            manifest = native.create(source.dsn,path,backups._create_documents_backup,backups._verify_documents_backup)
            self.assertEqual(manifest['database_settings'], settings)
            self.assertEqual(native.verify(path,backups._verify_documents_backup)['technical_integrity'], 'PASS')
        self.assertEqual(self.manifest['objects']['collations']['count'], 1)

    def test_wrong_database_locale_blocks_before_restore(self):
        path = self.copy_set()
        manifest_path = native.pair(path, '.manifest.json')
        manifest = json.loads(manifest_path.read_text())
        manifest['database_settings']['lc_collate'] = 'C.utf8'
        manifest_path.write_text(json.dumps(manifest))
        with tools.disposable_target() as target:
            with self.assertRaisesRegex(tools.BackupError, 'DATABASE_ENCODING_LOCALE_VERSION_MISMATCH'):
                native.restore(path,target,backups._verify_documents_backup)
            self.assertFalse(target.used)

    def test_identity_tampered_manifest_rejected_before_target(self):
        path = self.copy_set()
        manifest_path = native.pair(path, ".manifest.json")
        for field, value in (("schema_lineage_fingerprint", "0" * 64),
                             ("schema_lineage_id", LEGACY_FINANCIAL),
                             ("schema_version", 73), ("manifest_contract_version", True)):
            body = dict(self.manifest)
            body[field] = value
            manifest_path.write_text(json.dumps(body))
            with patch.object(native, "disposable_target") as target:
                with self.assertRaises(tools.BackupError):
                    native.verify(path, backups._verify_documents_backup)
            target.assert_not_called()

    def test_manifest_identity_vs_restored_registry_exact(self):
        path = self.copy_set()
        manifest_path = native.pair(path, ".manifest.json")
        body = json.loads(manifest_path.read_text())
        body.update(describe(expected_identities()[:73]))
        manifest_path.write_text(json.dumps(body))
        with tools.disposable_target() as target, self.assertRaisesRegex(tools.BackupError, "RESTORED_INVENTORY_MISMATCH"):
            native.restore(path, target, backups._verify_documents_backup)

    def test_previous_manifest_contract_preserved_without_rewrite(self):
        path = self.copy_set()
        manifest_path = native.pair(path, ".manifest.json")
        body = json.loads(manifest_path.read_text())
        for key in ("manifest_contract_version", "migration_identities", "schema_lineage_fingerprint", "schema_lineage_id"):
            body.pop(key)
        manifest_path.write_text(json.dumps(body))
        original = manifest_path.read_bytes()
        result = native.verify(path, backups._verify_documents_backup)
        self.assertEqual(result["manifest_contract_version"], 1)
        self.assertEqual(result["schema_lineage_id"], "CANONICAL_CRM74_FINANCIAL75_80")
        self.assertEqual(manifest_path.read_bytes(), original)
        self.assertFalse(result["serving_authorized"])

    def test_canonical75_registry_timestamp_rows_survive_exactly(self):
        with self.source.connection() as source, self.target.connection() as target:
            query = "SELECT version,name,applied_at FROM public.schema_migrations ORDER BY version"
            self.assertEqual(source.execute(query).fetchall(), target.execute(query).fetchall())
            self.assertIsNotNone(target.execute("SELECT to_regclass('public.sales_sheets')").fetchone()[0])

    def test_legacy_financial79_frozen_synthetic_roundtrip(self):
        source_dir = Path(os.environ.get("NOESIS_LEGACY_FINANCIAL_FIXTURE", ".legacy-financial-fixture")) / "src"
        if not (source_dir / "noesis/migrations.py").is_file():
            self.fail("Frozen synthetic legacy79 source required; no real backup fallback")
        with tools.disposable_target() as source:
            env = tools.safe_environment() | {"PYTHONPATH": str(source_dir.resolve()),
                                               "PYTHON_DOTENV_DISABLED": "1", "NOESIS_FIXTURE_DSN": source.dsn}
            # SHA congelado por CI; sólo construye un esquema vacío sintético.
            tools.run([sys.executable, "-c", "import os,psycopg; from psycopg.rows import dict_row; "
                       "from noesis import db,migrations; "
                       "c=psycopg.connect(os.environ['NOESIS_FIXTURE_DSN'],row_factory=dict_row); "
                       "migrations.upgrade_connection(db.Connection(c,'postgres')); c.commit(); c.close()"], env=env)
            path = self.folder / "legacy79.pgdump"
            manifest = native.create(source.dsn, path, backups._create_documents_backup, backups._verify_documents_backup)
            self.assertEqual(manifest["schema_lineage_id"], LEGACY_FINANCIAL)
            self.assertEqual(manifest["schema_version"], 79)
            result = native.verify(path, backups._verify_documents_backup)
            self.assertEqual(result["schema_lineage_id"], LEGACY_FINANCIAL)
            self.assertEqual(result["privacy_status"], native.PRIVACY_REQUIRED)
            self.assertEqual(result["schema_lineage_fingerprint"], manifest["schema_lineage_fingerprint"])
            self.assertFalse(result["serving_authorized"])

    def test_postgres_migration_paths_0_32_73_to75(self):
        for start in (0, 32, 73):
            with self.subTest(start=start), tools.disposable_target() as source:
                with source.connection() as conn:
                    conn.row_factory = dict_row
                    wrapped = db.Connection(conn, "postgres")
                    migrations.upgrade_connection(wrapped, start)
                    self.assertEqual(migrations.upgrade_connection(wrapped), 75)
                    rows = conn.execute("SELECT version,name FROM schema_migrations ORDER BY version").fetchall()
                    self.assertEqual([[r["version"], r["name"]] for r in rows], expected_identities())


if __name__ == "__main__":
    unittest.main()
