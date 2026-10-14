"""Foundation: PostgreSQL18 propio, sin outbound; locks y rollback reales."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import quote
from uuid import uuid4

from noesis import config, db, migrations
from noesis.schema_lineage import inspect, require_runtime, SchemaLineageError, MIGRATION_LOCK_KEY
from tests import postgres_financial_operations as operations_pg
from tests.test_schema_lineage import A75_GOLDEN


class SchemaLineagePostgres(unittest.TestCase):
    setUpClass = classmethod(operations_pg.FinancialOperationsPostgres.setUpClass.__func__)
    tearDownClass = classmethod(operations_pg.FinancialOperationsPostgres.tearDownClass.__func__)

    def fresh(self, target):
        """Cada caso tiene namespace vacío distinto; jamás un esquema real."""
        namespace = "lineage_case_" + uuid4().hex
        with db.get_conn() as conn:
            conn.execute("CREATE SCHEMA " + namespace)
        url = self.original_url + ("&" if "?" in self.original_url else "?") + "options=" + quote("-csearch_path=" + namespace)
        db.close_pool()
        settings = patch.object(config, "DATABASE_URL", url)
        settings.start()
        def cleanup():
            db.close_pool()
            settings.stop()
            with db.get_conn() as conn:
                conn.execute("DROP SCHEMA " + namespace + " CASCADE")
            db.close_pool()
        self.addCleanup(cleanup)
        if target:
            self.assertEqual(migrations.upgrade(target), target)
        return namespace

    def test_zero_73_74_75_and_empty_downgrade(self):
        self.fresh(0)
        for target in (73, 74, 75):
            self.assertEqual(migrations.upgrade(target), target)
            with db.get_conn() as conn:
                self.assertEqual(inspect(conn).schema_version, target)
        self.assertEqual(migrations.downgrade(74), 74)
        self.assertEqual(migrations.upgrade(), 75)

    def test_canonical75_exact_identity_and_no_new_financial_effect(self):
        self.fresh(75)
        with db.get_conn() as conn:
            observation = require_runtime(conn)
            self.assertEqual(observation.lineage_fingerprint, A75_GOLDEN)
            self.assertEqual(observation.migration_identity[-2:],
                             ((74, 'captacion_hoja_y_tipo'), (75, 'evaluacion_readiness_financiera')))
            for table in ('financial_activation_control', 'financial_readiness_evaluations',
                          'financial_readiness_capabilities', 'financial_operations', 'economic_events'):
                self.assertEqual(conn.execute('SELECT COUNT(*) AS n FROM '+table).fetchone()['n'], 0)
            tables = {r['tablename'] for r in conn.execute(
                'SELECT tablename FROM pg_tables WHERE schemaname=current_schema()').fetchall()}
            self.assertTrue({'financial_activation_grants', 'financial_handoff_receipts',
                             'financial_provider_attempts'}.isdisjoint(tables))
        # Sin fila de control equivale a off/generation0/ever_enabledfalse.
        for flag in ('FINANCIAL_CORE_ENABLED', 'LEDGER_REPORTING_ENABLED', 'OPEN_ITEMS_ENABLED',
                     'NEW_TAX_ENGINE_ENABLED', 'NEW_BANK_RECONCILIATION_ENABLED'):
            self.assertFalse(getattr(config, flag))

    def test_amount_check_and_unknown_owned_objects_remain_fail_closed(self):
        from noesis.schema_lineage import lock_migrator
        self.fresh(75)
        changes = {
            'changed_limit': [
                'ALTER TABLE economic_events DROP CONSTRAINT economic_events_amount_check',
                'ALTER TABLE economic_events ADD CONSTRAINT economic_events_amount_check CHECK '
                '(amount IS NULL OR (amount BETWEEN -9999999999999999.99 AND 9999999999999999.98 AND amount=trunc(amount,2)))',
            ],
            'changed_scale': [
                'ALTER TABLE economic_events DROP CONSTRAINT economic_events_amount_check',
                'ALTER TABLE economic_events ADD CONSTRAINT economic_events_amount_check CHECK '
                '(amount IS NULL OR (amount BETWEEN -9999999999999999.99 AND 9999999999999999.99 AND amount=trunc(amount,3)))',
            ],
            'changed_operator': [
                'ALTER TABLE economic_events DROP CONSTRAINT economic_events_amount_check',
                'ALTER TABLE economic_events ADD CONSTRAINT economic_events_amount_check CHECK '
                '(amount IS NULL OR (amount > -9999999999999999.99 AND amount <= 9999999999999999.99 AND amount=trunc(amount,2)))',
            ],
            'changed_boolean': [
                'ALTER TABLE economic_events DROP CONSTRAINT economic_events_amount_check',
                'ALTER TABLE economic_events ADD CONSTRAINT economic_events_amount_check CHECK '
                '(amount IS NULL OR (amount BETWEEN -9999999999999999.99 AND 9999999999999999.99 OR amount=trunc(amount,2)))',
            ],
            'missing_check': ['ALTER TABLE economic_events DROP CONSTRAINT economic_events_amount_check'],
            'unknown_owned_column': ['ALTER TABLE economic_events ADD COLUMN unknown_financial_column TEXT'],
            'extra_financial_trigger': [
                "CREATE FUNCTION qa_unknown_economic_guard() RETURNS trigger LANGUAGE plpgsql AS 'BEGIN RETURN NEW; END'",
                'CREATE TRIGGER unknown_financial_guard BEFORE INSERT ON economic_events '
                'FOR EACH ROW EXECUTE FUNCTION qa_unknown_economic_guard()',
            ],
        }
        with db.get_conn() as conn:
            lock_migrator(conn)
            self.assertEqual(require_runtime(conn).schema_version, 75)
            for label, statements in changes.items():
                with self.subTest(change=label):
                    conn.execute('SAVEPOINT negative_object')
                    try:
                        for statement in statements:
                            conn.execute(statement)
                        with self.assertRaisesRegex(SchemaLineageError, 'SCHEMA_OBJECT_MISMATCH'):
                            require_runtime(conn)
                    finally:
                        conn.execute('ROLLBACK TO SAVEPOINT negative_object')
                        conn.execute('RELEASE SAVEPOINT negative_object')
                    self.assertEqual(require_runtime(conn).schema_version, 75)

    def test_crm_drop_readd_preserves_logical_columns_despite_attnum_holes(self):
        self.fresh(75)
        for _ in range(2):
            self.assertEqual(migrations.downgrade(73), 73)
            self.assertEqual(migrations.upgrade(), 75)
            with db.get_conn() as conn:
                self.assertEqual(require_runtime(conn).schema_version, 75)

    def test_retention_owner_profiles_never_authorize_consumers_and_return_exact75(self):
        from noesis.schema_lineage import lock_migrator, require_compatible
        from noesis.schema_objects import expected_objects, physical_objects
        from noesis.schema_retention import retention_objects
        from noesis.schema_lineage import canonical
        from noesis.core.persistence import FinancialSession
        from noesis.financial_activation.evaluator import FinancialReadinessEvaluator
        from noesis import readiness
        from noesis.web import server
        self.fresh(75)
        for target in (55, 54, 53, 58):
            self.assertEqual(migrations.downgrade(target), target)
            with db.get_conn() as conn:
                # El consumidor SHARE jamás reconoce retención como canonical.
                with self.assertRaisesRegex(SchemaLineageError, 'SCHEMA_OBJECT_MISMATCH'):
                    require_compatible(conn, (target,))
            with db.get_conn() as conn:
                lock_migrator(conn)
                observation = inspect(conn)
                self.assertEqual(observation.integrity, 'TECHNICAL_ONLY')
                self.assertEqual(observation.object_profile_id, f'postgres/retention-owner/{target}/v1')
                self.assertEqual(physical_objects(conn), retention_objects(target))
                expected_hash = hashlib.sha256(canonical(retention_objects(target)).encode()).hexdigest()
                self.assertEqual(observation.object_profile_hash, expected_hash)
                self.assertEqual(inspect(conn).object_profile_hash, observation.object_profile_hash)
                addresses = conn.execute_exact('SELECT host(inet_server_addr()) AS address, '
                                               'inet_server_addr()::text AS original_text').fetchone()
                self.assertEqual(addresses['address'], '127.0.0.1')
                self.assertEqual(addresses['original_text'], '127.0.0.1/32')
                for consumer in (
                    observation.binding,
                    lambda: observation.require_canonical((target, 75)),
                    lambda: require_compatible(conn, (target,)),
                    lambda: require_runtime(conn),
                ):
                    with self.assertRaisesRegex(SchemaLineageError, 'SCHEMA_LINEAGE_MISMATCH'):
                        consumer()
                evaluator = FinancialReadinessEvaluator(FinancialSession(conn), 1)
                with self.assertRaisesRegex(SchemaLineageError, 'SCHEMA_LINEAGE_MISMATCH'):
                    evaluator.read(None, str(uuid4()))
                # Consumidores reales sobre la TX prestada: no otra conexión,
                # scheduler, provider ni commit durante esta prueba negativa.
                with patch.object(db, 'get_conn', return_value=nullcontext(conn)), patch.object(server, 'start_scheduler') as scheduler:
                    with self.assertRaisesRegex(SchemaLineageError, 'SCHEMA_LINEAGE_MISMATCH'):
                        server._startup()
                    scheduler.assert_not_called()
                    report = readiness.collect_readiness()
                    self.assertFalse(report['ready'])
                    self.assertTrue(any(c['area'] == 'base de datos' and c['status'] == 'blocker' for c in report['checks']))
                with patch.object(config, 'IS_PRODUCTION', True):
                    self.assertEqual(inspect(conn).errors, ('SCHEMA_OBJECT_MISMATCH',))
                with patch('noesis.schema_retention.socket.if_nameindex', return_value=[(1, 'lo'), (2, 'eth0')]):
                    self.assertEqual(inspect(conn).errors, ('SCHEMA_OBJECT_MISMATCH',))
                print('PG_RETENTION_AUTHORITY ' + json.dumps({
                    'version': target, 'profile_id': observation.object_profile_id,
                    'profile_hash': expected_hash, 'integrity': observation.integrity,
                    'runtime': 'REJECTED', 'binding': 'REJECTED',
                    'readiness': 'REJECTED', 'startup_serving': 'REJECTED',
                }, sort_keys=True), flush=True)
            # Cada ruta vuelve a canonical75 antes de cualquier runtime válido.
            self.assertEqual(migrations.upgrade(), 75)
            with db.get_conn() as conn:
                self.assertEqual(require_runtime(conn).integrity, 'VERIFIED')
                self.assertEqual(physical_objects(conn), expected_objects('postgres', 75))

    def test_retention_rejects_partial_changed_unknown_and_future_objects(self):
        from noesis.schema_lineage import lock_migrator
        from noesis.schema_objects import physical_objects
        self.fresh(75)
        changes = (
            'ALTER TABLE assistant_messages DROP COLUMN actor',
            'ALTER TABLE assistant_messages ALTER COLUMN actor TYPE VARCHAR(100)',
            'ALTER TABLE invoices ADD COLUMN retention_unknown TEXT',
            'ALTER TABLE whatsapp_ingress DROP CONSTRAINT whatsapp_ingress_pkey',
            'CREATE TABLE financial_future_unknown(id INTEGER)',
            'CREATE TABLE unrelated_extra(id INTEGER)',
        )
        for target in (55, 54, 53, 58):
            self.assertEqual(migrations.downgrade(target), target)
            with db.get_conn() as conn:
                lock_migrator(conn)
                original = physical_objects(conn)
                for statement in changes:
                    with self.subTest(version=target, alteration=changes.index(statement)):
                        conn.execute('SAVEPOINT retention_negative')
                        try:
                            conn.execute(statement)
                            self.assertEqual(inspect(conn).errors, ('SCHEMA_OBJECT_MISMATCH',))
                        finally:
                            conn.execute('ROLLBACK TO SAVEPOINT retention_negative')
                            conn.execute('RELEASE SAVEPOINT retention_negative')
                        self.assertEqual(inspect(conn).integrity, 'TECHNICAL_ONLY')
                        self.assertEqual(physical_objects(conn), original)
                print('PG_RETENTION_NEGATIVES ' + json.dumps({
                    'version': target, 'alterations_rejected': len(changes),
                    'physical_snapshot_unchanged': True,
                }, sort_keys=True), flush=True)
            self.assertEqual(migrations.upgrade(), 75)
            with db.get_conn() as conn:
                self.assertEqual(require_runtime(conn).integrity, 'VERIFIED')

    def test_known_old68_delete_repaired_but_unknown_function_never_adopted(self):
        from noesis.schema_objects import OLD_CASH_DELETE
        self.fresh(68)
        with db.get_conn() as conn:
            conn.execute(OLD_CASH_DELETE.replace("RETURN NEW", "RETURN NULL"))
        with self.assertRaisesRegex(SchemaLineageError, "OBJECT_MISMATCH"):
            migrations.upgrade()
        with db.get_conn() as conn:
            conn.execute(OLD_CASH_DELETE)
        self.assertEqual(migrations.upgrade(), 75)
        with db.get_conn() as conn:
            self.assertEqual(require_runtime(conn).schema_version, 75)

    def test_savepoint_before_lock_rejected_no_rollback_or_isolation_change(self):
        self.fresh(75)
        with db.get_conn() as conn:
            conn.execute("SAVEPOINT caller_boundary")
            for callback in (lambda: require_runtime(conn), lambda: migrations.upgrade_connection(conn)):
                with self.assertRaisesRegex(SchemaLineageError, "TX_PROTOCOL_REQUIRED"):
                    callback()
            conn.execute("ROLLBACK TO SAVEPOINT caller_boundary")
            self.assertEqual(conn.execute("SHOW transaction_isolation").fetchone()[0], "read committed")

    def test_legacy74_and_legacy75_rejected(self):
        self.fresh(74)
        with db.get_conn() as conn:
            conn.execute("UPDATE schema_migrations SET name='evaluacion_readiness_financiera' WHERE version=74")
        for stage in (74, 75):
            if stage == 75:
                with db.get_conn() as conn:
                    conn.execute("INSERT INTO schema_migrations VALUES (75,'resoluciones_antecedentes_financieros',now())")
            with self.assertRaisesRegex(SchemaLineageError, "LEGACY_FINANCIAL"):
                migrations.upgrade()
        self.assertFalse(migrations.is_current())

    def test_warm_lexer_never_caches_live_integrity_or_missing_guards(self):
        self.fresh(75)
        for _ in range(2):
            with db.get_conn() as conn:
                self.assertEqual(require_runtime(conn).schema_version, 75)
        with db.get_conn() as conn:
            conn.execute("ALTER TABLE businesses ADD COLUMN unrecognized_column INTEGER")
        with db.get_conn() as conn, self.assertRaisesRegex(SchemaLineageError, "OBJECT_MISMATCH"):
            require_runtime(conn)
        with db.get_conn() as conn:
            conn.execute("ALTER TABLE businesses DROP COLUMN unrecognized_column")
        with db.get_conn() as conn:
            self.assertEqual(require_runtime(conn).schema_version, 75)
        with db.get_conn() as conn:
            conn.execute("DROP TRIGGER financial_readiness_evaluations_insert ON financial_readiness_evaluations")
        with db.get_conn() as conn, self.assertRaisesRegex(SchemaLineageError, "OBJECT_MISMATCH"):
            require_runtime(conn)
        self.assertFalse(migrations.is_current())

    def test_row75_without_objects_cannot_be_adopted(self):
        self.fresh(74)
        with db.get_conn() as conn:
            conn.execute("INSERT INTO schema_migrations VALUES (75,'evaluacion_readiness_financiera',now())")
        with self.assertRaisesRegex(SchemaLineageError, "OBJECT_MISMATCH"):
            migrations.upgrade()

    def test_two_migrators_wait_then_revalidate_without_duplicate_ddl(self):
        self.fresh(74)
        acquired = threading.Event()
        release = threading.Event()
        original = migrations._upgrade_readiness75
        calls = []
        def observed(conn):
            calls.append("DDL")
            acquired.set()
            self.assertTrue(release.wait(10))
            original(conn)
        entries = migrations.MIGRATIONS[:-1] + ((75, "evaluacion_readiness_financiera", observed, migrations._downgrade_readiness75),)
        with patch.object(migrations, "MIGRATIONS", entries), ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(migrations.upgrade)
            self.assertTrue(acquired.wait(10))
            second = workers.submit(migrations.upgrade)
            time.sleep(0.4)
            self.assertFalse(second.done())
            release.set()
            self.assertEqual(first.result(20), 75)
            self.assertEqual(second.result(20), 75)
        self.assertEqual(calls, ["DDL"])

    def test_real_30_second_advisory_timeout_without_ddl(self):
        self.fresh(74)
        with db.get_conn() as holder:
            holder.execute("SELECT pg_advisory_xact_lock(?)", (MIGRATION_LOCK_KEY,))
            started = time.monotonic()
            with self.assertRaisesRegex(SchemaLineageError, "MIGRATION_LOCK_TIMEOUT"):
                migrations.upgrade()
            duration = time.monotonic() - started
            self.assertGreaterEqual(duration, 30)
            self.assertLess(duration, 36)
        with db.get_conn() as conn:
            self.assertEqual(inspect(conn).schema_version, 74)

    def test_share_before_repeatable_snapshot_read_only_no_isolation_change(self):
        self.fresh(75)
        with db.get_conn() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            self.assertEqual(require_runtime(conn).schema_version, 75)
            self.assertEqual(conn.execute("SHOW transaction_isolation").fetchone()[0], "repeatable read")
            self.assertEqual(conn.execute("SHOW transaction_read_only").fetchone()[0], "on")

    def test_late_lock_on_snapshot_rejected_without_restart(self):
        self.fresh(75)
        with db.get_conn() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            conn.execute("SELECT 1")
            with self.assertRaisesRegex(SchemaLineageError, "SCHEMA_TX_PROTOCOL_REQUIRED"):
                require_runtime(conn)
            self.assertEqual(conn.execute("SHOW transaction_isolation").fetchone()[0], "repeatable read")

    def test_failure_after_ddl_rolls_back_metadata_and_tables(self):
        self.fresh(74)
        def failure(conn):
            migrations._upgrade_readiness75(conn)
            raise RuntimeError("synthetic crash boundary")
        entries = migrations.MIGRATIONS[:-1] + ((75, "evaluacion_readiness_financiera", failure, migrations._downgrade_readiness75),)
        with patch.object(migrations, "MIGRATIONS", entries), self.assertRaisesRegex(RuntimeError, "synthetic crash"):
            migrations.upgrade()
        with db.get_conn() as conn:
            self.assertEqual(inspect(conn).schema_version, 74)
        self.assertEqual(migrations.upgrade(), 75)

    def _crash(self, boundary):
        self.fresh(74)
        environment = {**os.environ, "DATABASE_URL": config.DATABASE_URL,
                       "NOESIS_DATABASE_URL": config.DATABASE_URL}
        child = subprocess.Popen([sys.executable, "-m", "tests.schema_lineage_worker", boundary],
                                 cwd=Path(__file__).parents[1], env=environment,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), "READY")
            child.kill()
            child.communicate(timeout=20)
            with db.get_conn() as conn:
                self.assertEqual(inspect(conn).schema_version, 74)
            self.assertEqual(migrations.upgrade(), 75)
        finally:
            if child.poll() is None:
                child.kill()
            child.communicate()

    def test_process_crash_after_ddl_before_registry(self):
        self._crash("before_registry")

    def test_process_crash_after_registry_before_commit(self):
        self._crash("after_registry")


if __name__ == "__main__":
    unittest.main()
