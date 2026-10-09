"""Matriz D: PostgreSQL loopback sintético, login runtime sin privilegios de clave."""

from unittest.mock import patch
from urllib.parse import urlsplit, urlunsplit, quote
from uuid import uuid4
import unittest
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager

from noesis import config, db, migrations
from tests.test_financial_activation_handoff import HandoffSQLite


class HandoffPostgres(HandoffSQLite):
    def seed(self):
        settings = patch.multiple(config, VERIFACTU_PRODUCER_NIF='B87654321', VERIFACTU_CERT_PATH='', VERIFACTU_KEY_PATH='', VERIFACTU_AEAT_ENV='')  # pragma: allowlist secret
        settings.start()
        self.addCleanup(settings.stop)
        self.business = db.create_business('Frontera D', 'fixture@example.test')
        self.bid = self.business['id']
        db.update_fiscal(self.bid, nif='A12345678', address='Calle 1')  # pragma: allowlist secret
        db.set_trial(self.bid, days=14)
        self.client = db.add_client('Cliente', business_id=self.bid, nif='B12345674', address='Calle 2')  # pragma: allowlist secret

    @classmethod
    def setUpClass(cls):
        parts = urlsplit(config.DATABASE_URL)
        if parts.hostname not in ('127.0.0.1', 'localhost', '::1') or parts.path != '/noesis_ci' or config.IS_PRODUCTION:
            raise RuntimeError('Solo /noesis_ci local descartable.')
        cls.admin_url = config.DATABASE_URL
        cls.schema = 'activation_d_' + uuid4().hex
        cls.role = 'activation_runtime_' + uuid4().hex
        # CI exige autenticación; conservar el login restringido sin depender
        # de que el cluster local tenga host authentication=trust.
        runtime_password = uuid4().hex
        from psycopg import sql

        with db.get_conn() as c:
            c.execute('CREATE SCHEMA ' + cls.schema)
            c.execute_exact(sql.SQL(
                'CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB '
                'NOCREATEROLE NOINHERIT NOBYPASSRLS'
            ).format(sql.Identifier(cls.role), sql.Literal(runtime_password)).as_string(c.raw))
        cls.admin_scoped = cls.admin_url + ('&' if parts.query else '?') + 'options=' + quote('-csearch_path=' + cls.schema)
        db.close_pool()
        with patch.object(config, 'DATABASE_URL', cls.admin_scoped):
            migrations.upgrade(77)
            with db.get_conn() as c:
                c.execute('CREATE TABLE phase14_marker (business_id BIGINT NOT NULL,label TEXT NOT NULL)')
                c.execute('GRANT USAGE ON SCHEMA ' + cls.schema + ' TO ' + cls.role)
                for row in c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() AND table_type='BASE TABLE'").fetchall():
                    if row['table_name'] == 'financial_execution_verifier_key':
                        continue
                    c.execute('GRANT SELECT,INSERT,UPDATE,DELETE ON ' + row['table_name'] + ' TO ' + cls.role)
                c.execute('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA ' + cls.schema + ' TO ' + cls.role)
            db.close_pool()
        runtime = urlunsplit(('postgresql', cls.role + ':' + quote(runtime_password, safe='') + '@' + parts.hostname + ':' + str(parts.port), parts.path,
                              'options=' + quote('-csearch_path=' + cls.schema), ''))
        cls.settings = patch.object(config, 'DATABASE_URL', runtime)
        cls.settings.start()
        cls.runtime_url = runtime

    @classmethod
    def tearDownClass(cls):
        db.close_pool()
        cls.settings.stop()
        with db.get_conn() as c:
            c.execute('DROP SCHEMA ' + cls.schema + ' CASCADE')
            c.execute('DROP ROLE ' + cls.role)
        db.close_pool()

    def setUp(self):
        self.setup_readiness()
        self.cut()
        from noesis.financial_activation.handoff import FinancialActivation
        self.api = FinancialActivation(self.bid, code_version='fixture')

    def exact_fixture(self):
        db.close_pool()
        try:
            with patch.object(config, 'DATABASE_URL', self.admin_scoped):
                super().exact_fixture()
                db.close_pool()
        finally:
            db.close_pool()

    @contextmanager
    def as_migrator(self):
        db.close_pool()
        schema = 'migration_d_' + uuid4().hex
        with patch.object(config, 'DATABASE_URL', self.admin_url), db.get_conn() as c:
            c.execute('CREATE SCHEMA ' + schema)
        db.close_pool()
        scoped = self.admin_url + ('&' if '?' in self.admin_url else '?') + 'options=' + quote('-csearch_path=' + schema)
        try:
            with patch.object(config, 'DATABASE_URL', scoped):
                migrations.upgrade(76)
                self.setup_readiness()
                self.cut()
                yield
                db.close_pool()
        finally:
            db.close_pool()
            with patch.object(config, 'DATABASE_URL', self.admin_url), db.get_conn() as c:
                c.execute('DROP SCHEMA ' + schema + ' CASCADE')
            db.close_pool()

    def workers(self, specifications):
        env = dict(os.environ, NOESIS_DATABASE_URL=self.runtime_url, DATABASE_URL=self.runtime_url, NOESIS_SECRET=config.SECRET_KEY)
        children = [subprocess.Popen([sys.executable, '-m', 'tests.financial_activation_handoff_worker', json.dumps(spec)],
                                     cwd=Path(__file__).parents[1], env=env, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for spec in specifications]
        try:
            for child in children:
                self.assertEqual(child.stdout.readline().strip(), 'READY')
            for child in children:
                child.stdin.write('go\n')
                child.stdin.flush()
            results = []
            for child in children:
                output, error = child.communicate(timeout=30)
                self.assertFalse(error, error)
                results.append((child.returncode, json.loads(output) if output.strip() else None))
            return results
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate()

    def worker_spec(self, req, stage='enabled', **kw):
        from noesis.financial_activation.configuration_snapshot import PRODUCER_FIELDS
        return dict(business_id=self.bid, user_id=self.principal.user_id, request_uuid=req.body['request_uuid'], stage=stage,
                    fixture_configuration={name: getattr(config, name) for name in PRODUCER_FIELDS}, **kw)

    def ready_request(self):
        req = self.approved_request()
        for stage in ('validating', 'ready'):
            self.api.advance(self.principal, req.body['request_uuid'], stage)
        return req

    def test_two_real_processes_same_handoff_recover_exact_receipt(self):
        req = self.ready_request()
        results = self.workers([self.worker_spec(req)] * 2)
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0], 0)
        self.assertEqual(self.control()['activation_generation'], 1)

    def test_two_real_processes_different_handoff_only_one_wins(self):
        first = self.ready_request()
        second = self.approved_request(evaluation_uuid=first.body['evaluation_uuid'])
        results = self.workers([self.worker_spec(first), self.worker_spec(second)])
        self.assertEqual(sum('receipt' in r[1] for r in results), 1)
        self.assertEqual(self.control()['activation_generation'], 1)

    def test_handoff_os_exit_at_every_durable_point_and_response_loss(self):
        req = self.ready_request()
        before = self.control()
        points = ('receipt_written', 'generation_written', 'grants_written', 'epoch_handed_off',
                  'fence_removed', 'certificate_verified', 'before_control', 'control_written', 'before_commit')
        for point in points:
            with self.subTest(point=point):
                self.assertEqual(self.workers([self.worker_spec(req, crash_point=point)])[0][0], 17)
                self.assertEqual(self.control(), before)
                with db.get_conn() as c:
                    self.assertTrue(c.execute('SELECT fence_enabled FROM financial_history_control WHERE business_id=?', (self.bid,)).fetchone()['fence_enabled'])
        self.assertEqual(self.workers([self.worker_spec(req, crash_point='after_commit')])[0][0], 17)
        receipt = self.api.advance(self.principal, req.body['request_uuid'], 'enabled')
        self.assertEqual(str(self.control()['current_transition_uuid']), receipt['receipt_uuid'])

    def test_handoff_gate_vs_direct_sql_writer_no_unprotected_window(self):
        req = self.ready_request()
        arrived, release = threading.Event(), threading.Event()
        def checkpoint(name):
            if name == 'fence_removed':
                arrived.set()
                self.assertTrue(release.wait(10))
        def writer():
            try:
                with db.get_conn() as c:
                    c.execute("INSERT INTO expenses (business_id,concept,amount,created_at) VALUES (?,'Directo','1.00','2026-10-06T00:00:00+00:00')", (self.bid,))
                return 'unsafe'
            except Exception:
                return 'denied'
        with ThreadPoolExecutor(max_workers=2) as pool, patch.object(self.api, 'checkpoint', side_effect=checkpoint):
            handoff = pool.submit(self.api.advance, self.principal, req.body['request_uuid'], 'enabled')
            self.assertTrue(arrived.wait(10))
            write = pool.submit(writer)
            release.set()
            self.assertEqual(write.result(timeout=15), 'denied')
            self.assertEqual(handoff.result(timeout=15)['final_state'], 'enabled')

    def race_at_checkpoint(self, request, stage, point, contender):
        """Dos conexiones reales; no esconder DeadlockDetected en el rechazo."""
        arrived, release, started = threading.Event(), threading.Event(), threading.Event()
        def checkpoint(name):
            if name == point:
                arrived.set()
                self.assertTrue(release.wait(10))
        def compete():
            started.set()
            try:
                return ('ok', contender())
            except Exception as exc:
                self.assertNotEqual(type(exc).__name__, 'DeadlockDetected')
                return ('denied', type(exc).__name__)
        with ThreadPoolExecutor(max_workers=2) as pool, patch.object(self.api, 'checkpoint', side_effect=checkpoint):
            transition = pool.submit(self.api.advance, self.principal, request.body['request_uuid'], stage)
            self.assertTrue(arrived.wait(10))
            other = pool.submit(compete)
            self.assertTrue(started.wait(10))
            try:
                deadline = time.monotonic() + 10
                while not other.done():
                    with db.get_conn() as c:
                        waiting = c.execute("SELECT COUNT(*) AS n FROM pg_stat_activity WHERE usename=? AND pid<>pg_backend_pid() AND state='active' AND wait_event_type='Lock'", (self.role,)).fetchone()['n']
                    if waiting:
                        break
                    self.assertLess(time.monotonic(), deadline, 'El contender debe demostrar contención real o rechazo bajo gate')
                    time.sleep(.01)
            finally:
                release.set()
            return transition.result(timeout=15), other.result(timeout=15)

    def test_handoff_vs_session_invalidation_linearizes_before_logout(self):
        req = self.ready_request()
        def invalidate():
            with db.get_conn() as c:
                c.execute('UPDATE users SET session_version=session_version+1 WHERE business_id=? AND id=?', (self.bid, self.principal.user_id))
        receipt, other = self.race_at_checkpoint(req, 'enabled', 'fence_removed', invalidate)
        self.assertEqual((receipt['final_state'], other[0]), ('enabled', 'ok'))
        with self.assertRaises(PermissionError):
            self.api.prepare(self.principal, uuid4(), 'pause', pause_reason='operator_request')

    def test_handoff_vs_source_configuration_drift_no_stale_effect_grant(self):
        from noesis.purchasing_capture import ExpenseCapture
        req = self.ready_request()
        def drift():
            with db.get_conn() as c:
                c.execute("UPDATE businesses SET name='Titular cambiado' WHERE id=?", (self.bid,))
        receipt, other = self.race_at_checkpoint(req, 'enabled', 'fence_removed', drift)
        self.assertEqual((receipt['final_state'], other[0]), ('enabled', 'ok'))
        with patch.object(config, 'FINANCIAL_CORE_ENABLED', True), self.assertRaises(ValueError):
            ExpenseCapture(self.bid).operations.prepare(self.principal, self.web_identity(), self.expense_request())

    def web_identity(self):
        from noesis.financial_operations.contracts import EntryIdentity
        return EntryIdentity.web_api(uuid4())

    def expense_request(self):
        from noesis.purchasing_capture import ExpenseCapture
        with patch.object(config, 'FINANCIAL_CORE_ENABLED', True):
            return ExpenseCapture(self.bid).review_confirm(self.principal, amount='12.10', concept='Material')

    def test_pause_vs_execute_and_prepare_then_resume_vs_stale_execute(self):
        from noesis.purchasing_capture import ExpenseCapture
        service = ExpenseCapture(self.bid)
        self.enable()
        with patch.object(config, 'FINANCIAL_CORE_ENABLED', True):
            request = self.expense_request()
            op = service.prepare(self.principal, self.web_identity(), request)
            service.authorize(self.principal, op.operation_uuid, channel='web_api', approved_hash=request.request_hash, approved_revision=None)
            pause = self.approved_request('pause', pause_reason='operator_request')
            receipt, other = self.race_at_checkpoint(pause, 'paused', 'after_pause_cancel', lambda: service.execute(self.principal, op.operation_uuid))
            self.assertEqual((receipt['final_state'], other[0]), ('paused', 'denied'))
            resume = self.approved_request('resume')
            receipt, other = self.race_at_checkpoint(resume, 'enabled', 'generation_written', lambda: service.execute(self.principal, op.operation_uuid))
            self.assertEqual((receipt['activation_generation'], other[0]), (2, 'denied'))
            pause = self.approved_request('pause', pause_reason='operator_request')
            receipt, other = self.race_at_checkpoint(pause, 'paused', 'receipt_written', lambda: service.prepare(self.principal, self.web_identity(), request))
            self.assertEqual((receipt['final_state'], other[0]), ('paused', 'denied'))

    def test_two_resume_processes_same_receipt_and_new_generation_only_once(self):
        self.enable()
        pause = self.approved_request('pause', pause_reason='operator_request')
        self.api.advance(self.principal, pause.body['request_uuid'], 'paused')
        resume = self.approved_request('resume')
        results = self.workers([self.worker_spec(resume)] * 2)
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0], 0)
        self.assertEqual(self.control()['activation_generation'], 2)

    def test_other_business_progresses_while_handoff_holds_gate(self):
        req = self.ready_request()
        other = db.create_business('Otro sintético', 'other@example.test')['id']
        def write_other():
            with db.get_conn() as c:
                c.execute("INSERT INTO expenses(business_id,concept,amount,created_at) VALUES (?,'Material','1.00','2026-10-06')", (other,))
        arrived, release = threading.Event(), threading.Event()
        def checkpoint(name):
            if name == 'fence_removed':
                arrived.set()
                self.assertTrue(release.wait(10))
        with ThreadPoolExecutor(max_workers=2) as pool, patch.object(self.api, 'checkpoint', side_effect=checkpoint):
            handoff = pool.submit(self.api.advance, self.principal, req.body['request_uuid'], 'enabled')
            self.assertTrue(arrived.wait(10))
            try:
                pool.submit(write_other).result(timeout=5)
            finally:
                release.set()
            self.assertEqual(handoff.result(timeout=15)['final_state'], 'enabled')

    def test_handoff_vs_history_open_and_impossible_pause(self):
        from noesis.financial_history.importer import HistoryImporter
        req = self.ready_request()
        _, other = self.race_at_checkpoint(req, 'enabled', 'fence_removed', lambda: HistoryImporter(self.bid).open(self.principal, uuid4(), repository_version='fixture', environment_identity='synthetic'))
        self.assertEqual(other[0], 'denied')
        self.setup_readiness()
        self.cut()
        from noesis.financial_activation.handoff import FinancialActivation
        self.api = FinancialActivation(self.bid, code_version='fixture')
        req = self.ready_request()
        # La confirmación enable no concede pause, ni durante su handoff.
        _, other = self.race_at_checkpoint(req, 'enabled', 'fence_removed', lambda: self.api.advance(self.principal, req.body['request_uuid'], 'paused'))
        self.assertEqual(other[0], 'denied')
        self.assertEqual(self.control()['state'], 'enabled')

    def test_handoff_vs_legacy_application_writer_and_raw_control_bypass(self):
        req = self.ready_request()
        _, other = self.race_at_checkpoint(req, 'enabled', 'fence_removed', lambda: db.add_expense('Legacy','1.00',business_id=self.bid))
        self.assertEqual(other[0], 'denied')
        pause = self.approved_request('pause', pause_reason='operator_request')
        def bypass():
            with db.get_conn() as c:
                c.execute('UPDATE financial_activation_control SET ever_enabled=FALSE,control_revision=control_revision+1 WHERE business_id=?', (self.bid,))
        _, other = self.race_at_checkpoint(pause, 'paused', 'receipt_written', bypass)
        self.assertEqual(other[0], 'denied')
        self.assertTrue(self.control()['ever_enabled'])

    def test_sql_started_before_enable_observes_live_guard_after_atomic_commit(self):
        from noesis.core.locks import lock_key
        from tests.postgres_financial_history_cutoff import HistoryCutoffPostgres
        req = self.ready_request()
        key = lock_key('d-statement-snapshot', uuid4())
        db.close_pool()
        with patch.object(config, 'DATABASE_URL', self.admin_scoped), db.get_conn() as c:
            c.execute(f"CREATE FUNCTION aa1_d_statement_pause() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_advisory_xact_lock({key}); RETURN NEW; END $$")
            c.execute('CREATE TRIGGER aa1_d_statement_pause BEFORE INSERT ON expenses FOR EACH ROW EXECUTE FUNCTION aa1_d_statement_pause()')
        db.close_pool()
        def writer():
            try:
                with db.get_conn() as c:
                    c.execute("INSERT INTO expenses(business_id,concept,amount,created_at) VALUES (?,'Snapshot previo','1.00','2026-10-06')", (self.bid,))
                return 'unsafe'
            except Exception as exc:
                self.assertNotEqual(type(exc).__name__, 'DeadlockDetected')
                return 'denied'
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                with db.get_conn() as pause:
                    pause.execute('SELECT pg_advisory_xact_lock(?)', (key,))
                    write = pool.submit(writer)
                    HistoryCutoffPostgres._waiting(self, 1, 'advisory', key)
                    self.assertFalse(self.control()['ever_enabled'])
                    self.api.advance(self.principal, req.body['request_uuid'], 'enabled')
                self.assertEqual(write.result(timeout=15), 'denied')
            self.assertTrue(self.control()['ever_enabled'])
        finally:
            db.close_pool()
            with patch.object(config, 'DATABASE_URL', self.admin_scoped), db.get_conn() as c:
                c.execute('DROP TRIGGER aa1_d_statement_pause ON expenses')
                c.execute('DROP FUNCTION aa1_d_statement_pause()')
            db.close_pool()

    def test_pause_resume_os_exit_all_durable_points(self):
        from noesis.purchasing_capture import ExpenseCapture
        self.enable()
        service = ExpenseCapture(self.bid)
        with patch.object(config, 'FINANCIAL_CORE_ENABLED', True):
            request = self.expense_request()
            op = service.prepare(self.principal, self.web_identity(), request)
            service.operations.grant_mandate(self.principal, request, channel='web_api', expires_at=datetime.now(timezone.utc)+timedelta(minutes=3))
        pause = self.approved_request('pause', pause_reason='operator_request')
        before = self.control()
        for point in ('before_pause_cancel','after_pause_cancel','before_pause_revoke','after_pause_revoke','pause_terminalization','receipt_written','before_control','control_written','before_commit'):
            with self.subTest(action='pause', point=point):
                self.assertEqual(self.workers([self.worker_spec(pause, stage='paused', crash_point=point)])[0][0], 17)
                self.assertEqual(self.control(), before)
                self.assertEqual(service.operations.recover(self.principal, op.operation_uuid).state.value, 'prepared')
        self.assertEqual(self.workers([self.worker_spec(pause, stage='paused', crash_point='after_commit')])[0][0], 17)
        self.api.advance(self.principal, pause.body['request_uuid'], 'paused')
        resume = self.approved_request('resume')
        before = self.control()
        for point in ('receipt_written','generation_written','grants_written','before_control','control_written','before_commit'):
            with self.subTest(action='resume', point=point):
                self.assertEqual(self.workers([self.worker_spec(resume, crash_point=point)])[0][0], 17)
                self.assertEqual(self.control(), before)
        self.assertEqual(self.workers([self.worker_spec(resume, crash_point='after_commit')])[0][0], 17)
        self.assertEqual(self.api.advance(self.principal, resume.body['request_uuid'], 'enabled')['activation_generation'], 2)

    def test_private_key_fake_claim_and_copied_claim_cannot_cross_transaction_or_login(self):
        from noesis.core.persistence import FinancialSession
        from noesis.financial_activation.execution_context import execution_context
        from noesis.purchasing_capture import ExpenseCapture
        from noesis.financial_writers import purchasing
        self.enable()
        import psycopg
        with self.assertRaises(psycopg.errors.InsufficientPrivilege), db.get_conn() as c:
            c.execute('SELECT verifier FROM financial_execution_verifier_key')
        with db.get_conn() as c:
            c.execute("SELECT set_config('noesis.execution_context',?,true)", (json.dumps(dict(kind='effect', business_id=self.bid, generation=1, availability=True)),))
            c.execute("SELECT set_config('noesis.execution_signature',?,true)", ('0'*64,))
            self.assertEqual(c.execute('SELECT noesis_execution_context() AS ctx').fetchone()['ctx'], {})
        service, copied = ExpenseCapture(self.bid), []
        original = purchasing.add_expense
        def observe(session, *args, **kwargs):
            copied.append(session.execute("SELECT current_setting('noesis.execution_context') AS body,current_setting('noesis.execution_signature') AS signature").fetchone())
            return original(session, *args, **kwargs)
        with patch.object(config, 'FINANCIAL_CORE_ENABLED', True), patch.object(purchasing, 'add_expense', side_effect=observe):
            request = self.expense_request()
            op = service.prepare(self.principal, self.web_identity(), request)
            service.authorize(self.principal, op.operation_uuid, channel='web_api', approved_hash=request.request_hash, approved_revision=None)
            service.execute(self.principal, op.operation_uuid)
        for attempt in range(2):
            if attempt:
                db.close_pool()  # Otra conexión/backend además de otra transacción.
            with db.get_conn() as c:
                c.execute("SELECT set_config('noesis.execution_context',?,true)", (copied[0]['body'],))
                c.execute("SELECT set_config('noesis.execution_signature',?,true)", (copied[0]['signature'],))
                self.assertEqual(c.execute('SELECT noesis_execution_context() AS ctx').fetchone()['ctx'], {})
        db.close_pool()
        try:
            with patch.object(config, 'DATABASE_URL', self.admin_scoped), db.get_conn() as c:
                c.execute('SET ROLE ' + self.role)
                with execution_context(FinancialSession(c), dict(kind='effect', business_id=self.bid, generation=1)):
                    self.assertEqual(c.execute('SELECT noesis_execution_context() AS ctx').fetchone()['ctx'], {})
                db.close_pool()
        finally:
            db.close_pool()


if __name__ == '__main__':
    unittest.main()
