"""F en PostgreSQL nativo aislado, runtime sin acceso a clave HMAC."""

from unittest.mock import patch
import unittest
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from noesis import config, db, migrations
from noesis.financial_providers.dispatch import FinancialProviderDispatch
from noesis.financial_operations.contracts import StateError
from tests.test_financial_providers import ProviderContract
from tests.postgres_financial_activation_handoff import HandoffPostgres


class ProviderPostgres(ProviderContract, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        HandoffPostgres.setUpClass.__func__(cls)
        db.close_pool()
        with patch.object(config, "DATABASE_URL", cls.admin_scoped):
            migrations.upgrade(79)
            with db.get_conn() as c:
                from noesis.financial_privacy.schema import TABLES as E_TABLES, RESTORED
                from noesis.financial_providers.schema import TABLES
                for table in E_TABLES + (RESTORED,) + TABLES:
                    c.execute("GRANT SELECT,INSERT,UPDATE,DELETE ON " + table + " TO " + cls.role)
            db.close_pool()

    tearDownClass = classmethod(HandoffPostgres.tearDownClass.__func__)
    seed = HandoffPostgres.seed

    def setUp(self):
        self.setup_providers()

    def test_empty_m79_roundtrip_preserves_previous_evidence(self):
        # La matriz comparte esquema entre negocios. Un downgrade vacío necesita
        # otro esquema descartable, sin borrar evidencia de pruebas anteriores.
        with HandoffPostgres.as_migrator(self):
            migrations.upgrade(79)
            before = self.economic_state()
            self.assertEqual(migrations.downgrade(78), 78)
            self.assertEqual(migrations.upgrade(79), 79)
            self.assertEqual(before, self.economic_state())

    def test_synthetic_backup_restore_preserves_unknown_without_replay(self):
        with HandoffPostgres.as_migrator(self):
            migrations.upgrade(79)
            self.backup_database_url = config.DATABASE_URL
            with db.get_conn() as c:
                schema = c.execute_exact('SELECT current_schema() AS name').fetchone()['name']
                c.execute('GRANT USAGE ON SCHEMA ' + schema + ' TO ' + self.role)
                for row in c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() AND table_type='BASE TABLE'").fetchall():
                    if row['table_name'] != 'financial_execution_verifier_key':
                        c.execute('GRANT SELECT,INSERT,UPDATE,DELETE ON ' + row['table_name'] + ' TO ' + self.role)
                c.execute('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA ' + schema + ' TO ' + self.role)
            from urllib.parse import urlsplit, urlunsplit, quote
            parts = urlsplit(self.runtime_url)
            runtime = urlunsplit((parts.scheme, parts.netloc, parts.path, 'options=' + quote('-csearch_path=' + schema), ''))
            db.close_pool()
            with patch.object(config, 'DATABASE_URL', runtime):
                self.setup_providers()
                ProviderContract.test_synthetic_backup_restore_preserves_unknown_without_replay(self)
                db.close_pool()

    def worker_spec(self, binding=None, **kw):
        from noesis.financial_activation.configuration_snapshot import PRODUCER_FIELDS
        names = (*PRODUCER_FIELDS,'RELEASE_ID','FINANCIAL_CORE_ENABLED','BREVO_API_KEY','SMTP_FROM','VERIFACTU_AEAT_ENV','VERIFACTU_CERT_PATH','VERIFACTU_KEY_PATH','VERIFACTU_KEY_PASSWORD')
        return dict(business_id=self.bid,user_id=self.principal.user_id,binding_uuid=binding['binding_uuid'] if binding else None,settings={n:getattr(config,n) for n in names},**kw)

    def workers(self, specs):
        env = dict(os.environ,DATABASE_URL=self.runtime_url,NOESIS_DATABASE_URL=self.runtime_url,NOESIS_SECRET=config.SECRET_KEY)
        children = [subprocess.Popen([sys.executable,'-m','tests.financial_providers_worker',json.dumps(spec)],cwd=Path(__file__).parents[1],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for spec in specs]
        try:
            for child in children:
                self.assertEqual(child.stdout.readline().strip(),'READY')
            for child in children:
                child.stdin.write('go\n')
                child.stdin.flush()
            result = []
            for child in children:
                output,error = child.communicate(timeout=30)
                self.assertFalse(error,error)
                result.append((child.returncode,json.loads(output) if output.strip() else None))
            return result
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate()

    def test_processes_same_dispatch_one_fake_call(self):
        self.enable()
        binding = self.bound_email()
        with tempfile.TemporaryDirectory(prefix='noesis-f-process-counter-') as tmp:
            path = Path(tmp)/'calls.txt'
            results = self.workers([self.worker_spec(binding,counter=str(path))]*2)
            self.assertTrue(all(r[0]==0 for r in results),results)
            self.assertEqual(len(path.read_text().splitlines()),1)
            final = FinancialProviderDispatch(self.bid).dispatch(binding['binding_uuid'],transport=lambda a:self.fail('No segunda llamada'))
            self.assertEqual(final['result'],'SUCCEEDED')

    def test_processes_different_dispatch_both_exact_obligations(self):
        self.enable()
        op = self.expense_operation()
        bindings = [self.bound_email(op),self.bound_email(op)]
        with tempfile.TemporaryDirectory(prefix='noesis-f-process-counter-') as tmp:
            path = Path(tmp)/'calls.txt'
            results = self.workers([self.worker_spec(b,counter=str(path)) for b in bindings])
            self.assertTrue(all(r[0]==0 and r[1]['result']['result']=='SUCCEEDED' for r in results),results)
            self.assertEqual(len(set(path.read_text().splitlines())),2)

    def test_real_process_crashes_at_all_dispatch_boundaries(self):
        self.enable()
        op = self.expense_operation()
        for point in ('before_claim','after_claim_commit','before_provider_call','after_provider_before_result','during_result_transaction','after_result_commit'):
            binding = self.bound_email(op)
            with tempfile.TemporaryDirectory(prefix='noesis-f-process-crash-') as tmp:
                path = Path(tmp)/'calls.txt'
                result = self.workers([self.worker_spec(binding,counter=str(path),crash=point)])[0]
                self.assertEqual(result[0],71)
                count = len(path.read_text().splitlines()) if path.exists() else 0
                self.assertEqual(count,0 if point in ('before_claim','after_claim_commit','before_provider_call') else 1)
                api = FinancialProviderDispatch(self.bid)
                if point in ('before_claim','after_claim_commit'):
                    self.assertEqual(api.dispatch(binding['binding_uuid'],transport=self.success)['result'],'SUCCEEDED')
                else:
                    final = api.recover_unknown(binding['binding_uuid'])
                    self.assertEqual(final['result'],'SUCCEEDED' if point=='after_result_commit' else 'UNKNOWN_EXTERNAL_RESULT')
                    self.assertEqual(api.dispatch(binding['binding_uuid'],transport=lambda a:self.fail('Crash no permite retry')),final)

    def test_processes_same_preflight_uuid_exact_replay(self):
        from noesis.financial_activation.contracts import Capability
        value,refs = self.ready((Capability.EXPENSE_CONFIRM,self.email_capability()), (self.email_capability(),))
        spec = self.worker_spec(action='preflight',evaluation_uuid=value['evaluation_uuid'],preflight_uuid=str(uuid4()),attestations=refs)
        result = self.workers([spec,spec])
        self.assertEqual(result[0],result[1])
        self.assertEqual(result[0][1]['result']['result'],'PASS',result)

    @staticmethod
    def email_capability():
        from noesis.financial_activation.contracts import Capability
        return Capability.EMAIL

    def test_threads_same_claim_and_outside_tx_other_tenant_progress(self):
        self.enable()
        binding = self.bound_email()
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _:FinancialProviderDispatch(self.bid).claim(binding['binding_uuid']),range(2)))
        self.assertEqual(results[0],results[1])
        other = db.create_business('Otro sintético','other@example.test')
        entered,done = threading.Event(),threading.Event()
        def fake(a):
            entered.set()
            self.assertTrue(done.wait(5),'El provider no debe retener gate/TX')
            return self.success(a)
        def other_writer():
            self.assertTrue(entered.wait(5))
            with db.get_conn() as c:
                from noesis.core.locks import lock_business
                lock_business(c,other['id'])
                c.execute('INSERT INTO phase14_marker(business_id,label) VALUES (?,?)',(other['id'],'Synthetic progress'))
            done.set()
        with ThreadPoolExecutor(2) as pool:
            f = pool.submit(other_writer)
            result = FinancialProviderDispatch(self.bid).dispatch(binding['binding_uuid'],transport=fake)
            f.result(timeout=10)
        self.assertEqual(result['result'],'SUCCEEDED')

    def test_f_gate_wait_is_bounded_without_blocking_other_business(self):
        from noesis.financial_providers.preflight import transaction
        from noesis.core.locks import lock_business
        from noesis.financial_operations.contracts import Principal
        other = db.create_business('Otro sintético','other@example.test')
        user = db.create_user(uuid4().hex+'@example.test','fixture',other['id'])
        with db.get_conn() as holder:
            lock_business(holder,self.bid)
            with self.assertRaises(StateError):
                with transaction(self.bid,self.principal):
                    pass
            with transaction(other['id'],Principal(user['id'],0)):
                pass
