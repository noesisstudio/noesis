"""F sobre DB descartable. Todos los providers simulados, sockets bloqueados."""

from datetime import datetime, timedelta
import json
from pathlib import Path
import socket
import ssl
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from noesis import config, db, migrations
from noesis.core.persistence import FinancialSession
from noesis.financial_activation.contracts import Capability as C, Profile, instant
from noesis.financial_activation.handoff import FinancialActivation
from noesis.financial_activation.evaluator import FinancialReadinessEvaluator
from noesis.financial_operations.contracts import AccessDenied, ConflictError, StateError, Principal
from noesis.financial_privacy.export import FinancialEvidenceExporter, verify_export
from noesis.financial_privacy.retention import register_policy, provisional_policy
from noesis.financial_privacy.contracts import digest as privacy_digest
from noesis.financial_providers import attestations
from noesis.financial_providers.contracts import (ProviderAttestation, Provider, Level, Environment,
                                                Permission, OperationalPolicy, requirement, sufficient, clock, digest, canonical)
from noesis.financial_providers.preflight import FinancialIntegratedPreflight
from noesis.financial_providers.repository import ProviderRepository
from noesis.financial_providers.schema import ATTESTATIONS, OUTBOX_BINDINGS, ATTEMPTS, TABLES
from noesis.financial_providers.dispatch import FinancialProviderDispatch, bind, process_bound
from noesis.financial_operations.contracts import EntryIdentity
from tests.financial_readiness_contract import ReadinessContract
from tests.test_financial_privacy import synthetic_approved_policy


class ProviderContract:
    seed = ReadinessContract.seed
    setup_readiness = ReadinessContract.setup_readiness
    cut = ReadinessContract.cut
    draft = ReadinessContract.draft
    issued = ReadinessContract.issued
    approved = ReadinessContract.approved

    def setup_providers(self):
        self.setup_readiness()
        self.api = FinancialActivation(self.bid, code_version="fixture")
        self.preflight = FinancialIntegratedPreflight(self.bid, code_version="fixture")
        self.exporter = FinancialEvidenceExporter(self.bid, code_version="fixture")
        network = patch.object(socket.socket, "connect", side_effect=AssertionError("Outbound prohibido en F sintética"))
        # PG utiliza libpq; socket Python queda bloqueado incluso en loopback.
        network.start()
        self.addCleanup(network.stop)
        settings = patch.multiple(config, BREVO_API_KEY="SYNTHETIC-BREVO-SECRET-DO-NOT-EXPORT",  # pragma: allowlist secret - marcador sintético de exclusión
                                  SMTP_FROM="synthetic@example.test", IS_PRODUCTION=False, RELEASE_ID='fixture')
        settings.start()
        self.addCleanup(settings.stop)
        temp = tempfile.TemporaryDirectory(prefix='noesis-f-dummy-cert-')
        self.addCleanup(temp.cleanup)
        cert, key = Path(temp.name)/'public.pem', Path(temp.name)/'private.pem'
        cert.write_text('SYNTHETIC-PUBLIC-CERTIFICATE', encoding='utf-8')
        key.write_text('SYNTHETIC-AEAT-PRIVATE-KEY-MARKER-NOT-EXPORT', encoding='utf-8')
        settings = patch.multiple(config, VERIFACTU_AEAT_ENV='produccion', VERIFACTU_CERT_PATH=str(cert), VERIFACTU_KEY_PATH=str(key), VERIFACTU_KEY_PASSWORD='SYNTHETIC-AEAT-PASSWORD-MARKER')
        settings.start()
        self.addCleanup(settings.stop)
        # Certificado/clave fake sólo para estructura; no prueba criptográfica real.
        tls = patch.object(ssl.SSLContext, 'load_cert_chain', return_value=None)
        tls.start()
        self.addCleanup(tls.stop)
        self.tls_patch = tls
        db.update_verifactu_mode(self.bid, True)
        from noesis.web import whatsapp
        meta = patch.multiple(whatsapp, _TOKEN='SYNTHETIC-META-TOKEN-MARKER-NOT-EXPORT', _PHONE_ID='synthetic-phone')
        meta.start()
        self.addCleanup(meta.stop)
        self.meta_connection = db.create_whatsapp_connection(self.bid, waba_id=str(uuid4().int % 100000000000), phone_number_id=str(uuid4().int % 100000000000), status='active')
        self.cut()

    def policy(self, approved=True):
        value = synthetic_approved_policy() if approved else provisional_policy(uuid4())
        with db.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            register_policy(FinancialSession(conn), self.bid, self.principal, value,
                            approved_hash=privacy_digest(value) if approved else None)
        return value

    def check(self, capability=C.EMAIL, level=Level.LOCAL, **kwargs):
        with db.get_conn() as c:
            c.execute("BEGIN IMMEDIATE")
            return attestations.check(FinancialSession(c), self.bid, self.principal, capability,
                                      level=level, code_version="fixture", **kwargs)

    def verified(self, capability=C.EMAIL):
        # Sustituir ÚNICAMENTE el check readonly. Nunca escribir A FULL ni quitar blockers.
        with patch.object(attestations, "safe_check", return_value=dict(verified=True, reference_hash=digest({"synthetic": True}), synthetic=True)):
            return self.check(capability, Level.PRODUCTION_CONFIG, network_authorized=True)

    def evaluate(self, capabilities=(C.EXPENSE_CONFIRM,)):
        with db.get_conn() as c:
            c.execute("BEGIN IMMEDIATE")
            return FinancialReadinessEvaluator(FinancialSession(c), self.bid).evaluate(
                self.principal, uuid4(), Profile(capabilities), history=self.reference,
                code_version="fixture", now=clock())

    def ready(self, capabilities=(C.EXPENSE_CONFIRM,), providers=()):
        refs = {c.value: self.verified(c)["attestation_uuid"] for c in providers}
        self.policy()
        self.exporter.export(self.principal, uuid4())
        value = self.evaluate(capabilities)
        return value, refs

    def enable(self, capabilities=(C.EXPENSE_CONFIRM, C.EMAIL), providers=(C.EMAIL,)):
        value, refs = self.ready(capabilities, providers)
        self.assertEqual(value['outcome'], 'fully_eligible', value)
        receipt = self.preflight.evaluate(self.principal, value['evaluation_uuid'], attestations=refs)
        self.assertEqual(receipt['result'], 'PASS', receipt)
        req = self.api.prepare(self.principal, uuid4(), 'enable', evaluation_uuid=value['evaluation_uuid'], preflight_uuid=receipt['preflight_uuid'])
        self.api.authorize(self.principal, req.body['request_uuid'], approved_hash=req.content_hash)
        for stage in ('validating', 'ready', 'enabled'):
            self.api.advance(self.principal, req.body['request_uuid'], stage)
        flag = patch.object(config, 'FINANCIAL_CORE_ENABLED', True)
        flag.start()
        self.addCleanup(flag.stop)
        self.origin_evaluation = value
        return value, refs

    def expense_operation(self):
        from noesis.purchasing_capture import ExpenseCapture
        service = ExpenseCapture(self.bid)
        req = service.review_confirm(self.principal, amount='12.10', concept='Material sintético')
        identity = EntryIdentity.web_api(uuid4())
        op = service.prepare(self.principal, identity, req)
        service.authorize(self.principal, op.operation_uuid, channel=identity.namespace, approved_hash=req.request_hash, approved_revision=req.expected_revision)
        return service.execute(self.principal, op.operation_uuid)

    def bound_email(self, op=None):
        op = op or self.expense_operation()
        row = db.enqueue_email_message(business_id=self.bid, to_email='synthetic@example.test', subject='Comunicación sintética', text_body='Contenido sintético', entity_type='client_message')
        with db.get_conn() as c:
            c.execute('BEGIN IMMEDIATE')
            result = bind(FinancialSession(c), self.bid, self.principal, 'email_outbox', row['id'], op.operation_uuid)
        return result

    def bound_invoice(self):
        from noesis.invoice_capture.service import InvoiceCapture
        capture = InvoiceCapture(self.bid)
        invoice = self.draft()
        req = capture.review(self.principal, invoice['id'])
        identity = EntryIdentity.web_api(uuid4())
        op = capture.prepare(self.principal, identity, req)
        capture.authorize(self.principal, op.operation_uuid, channel=identity.namespace, approved_hash=req.request_hash, approved_revision=req.expected_revision)
        done = capture.execute(self.principal, op.operation_uuid)
        with db.get_conn() as c:
            row = c.execute('SELECT evidence_uuid FROM ' + OUTBOX_BINDINGS + ' WHERE business_id=? AND operation_uuid=?', (self.bid, done.operation_uuid)).fetchone()
            result = ProviderRepository(FinancialSession(c), self.bid).load(OUTBOX_BINDINGS, str(row['evidence_uuid']))
        return result

    def bound_meta(self, op=None):
        op = op or self.expense_operation()
        row = db.enqueue_whatsapp_message(business_id=self.bid,connection_id=self.meta_connection['id'],to_phone='34600000000',message_type='text',text_body='Sólo comunicación sintética',financial_operation_uuid=op.operation_uuid)
        with db.get_conn() as c:
            r = c.execute('SELECT evidence_uuid FROM '+OUTBOX_BINDINGS+' WHERE business_id=? AND outbox_type=? AND outbox_id=?',(self.bid,'whatsapp_outbox',row['id'])).fetchone()
            return ProviderRepository(FinancialSession(c),self.bid).load(OUTBOX_BINDINGS,str(r['evidence_uuid']))

    def pause(self):
        req = self.api.prepare(self.principal, uuid4(), 'pause', pause_reason='operator_request')
        self.api.authorize(self.principal, req.body['request_uuid'], approved_hash=req.content_hash)
        return self.api.advance(self.principal, req.body['request_uuid'], 'paused')

    def economic_state(self):
        from noesis.financial_history.reconciliation_verifier import storage_hash
        with db.get_conn() as c:
            return {t: sorted(storage_hash(r) for r in c.execute_exact('SELECT * FROM ' + t + ' WHERE business_id=?', (self.bid,)).fetchall()) for t in ('financial_operations','financial_authorizations','economic_events','economic_event_links','financial_activation_grants','financial_activation_generations','financial_history_manifests','financial_history_import_batches','financial_retention_policies')}

    @staticmethod
    def success(attempt):
        return dict(category='success', reference='synthetic-provider-reference', status_code=200)

    def test_email_dispatch_one_call_exact_replay_no_economic_effects(self):
        self.enable()
        binding = self.bound_email()
        before = self.economic_state()
        calls = []
        def send(a):
            calls.append(a['attempt_uuid'])
            # Una segunda conexión independiente obtiene el gate durante I/O.
            with db.get_conn() as c:
                c.execute('BEGIN IMMEDIATE')
                from noesis.core.locks import lock_business
                lock_business(FinancialSession(c), self.bid)
            return self.success(a)
        api = FinancialProviderDispatch(self.bid)
        first = api.dispatch(binding['binding_uuid'], transport=send)
        self.assertEqual(first['result'], 'SUCCEEDED')
        self.assertEqual(first, api.dispatch(binding['binding_uuid'], transport=send))
        self.assertEqual(len(calls), 1)
        self.assertEqual(before, self.economic_state())
        with db.get_conn() as c:
            self.assertEqual(c.execute('SELECT status FROM email_outbox WHERE business_id=? AND id=?', (self.bid, binding['outbox_id'])).fetchone()['status'], 'sent')

    def test_email_timeout_unknown_never_automatically_retried(self):
        self.enable()
        binding = self.bound_email()
        calls = []
        def send(a):
            calls.append(a)
            return dict(category='timeout', reference=None, status_code=None)
        result = FinancialProviderDispatch(self.bid).dispatch(binding['binding_uuid'], transport=send)
        self.assertEqual(result['result'], 'UNKNOWN_EXTERNAL_RESULT')
        self.assertEqual(process_bound('email_outbox', only_ids=[binding['outbox_id']], transport=send), [])
        self.assertEqual(FinancialProviderDispatch(self.bid).dispatch(binding['binding_uuid'], transport=send), result)
        self.assertEqual(len(calls), 1)

    def test_synthetic_backup_restore_preserves_unknown_without_replay(self):
        from noesis.web import backups
        from noesis.financial_privacy.restore import prepare_restored_database
        from noesis.financial_providers.schema import RESULTS

        self.enable()
        binding = self.bound_email()
        result = FinancialProviderDispatch(self.bid).dispatch(
            binding['binding_uuid'], transport=lambda _: dict(category='timeout'))
        self.assertEqual(result['result'], 'UNKNOWN_EXTERNAL_RESULT')
        before = self.economic_state()
        restored = []

        def checked_restore(session, bundle):
            own = session.execute('SELECT evidence_uuid FROM ' + RESULTS + ' WHERE business_id=?', (self.bid,)).fetchall()
            self.assertEqual(len(own), 1)
            self.assertEqual(ProviderRepository(session, self.bid).load(RESULTS, str(own[0]['evidence_uuid'])), result)
            restored.append(prepare_restored_database(session, bundle))
            # Restaurar no borra ni reabre un resultado externo desconocido.
            self.assertEqual(ProviderRepository(session, self.bid).load(RESULTS, str(own[0]['evidence_uuid'])), result)
            return restored[-1]

        with tempfile.TemporaryDirectory(prefix='noesis-f-synthetic-backup-') as tmp, patch.object(config, 'BACKUP_DIR', Path(tmp)):
            if config.DATABASE_URL:
                db.close_pool()
                with patch.object(config, 'DATABASE_URL', self.backup_database_url):
                    path, counts = backups._create_postgres_backup()
                    with patch('noesis.financial_privacy.restore.prepare_restored_database', checked_restore):
                        backups._verify_postgres_backup(path, counts)
                    db.close_pool()
            else:
                path, counts = backups._create_sqlite_backup()
                with patch('noesis.financial_privacy.restore.prepare_restored_database', checked_restore):
                    backups._verify_sqlite_backup(path, counts)
            self.assertTrue(path.is_file())
        self.assertEqual(len(restored), 1)
        self.assertEqual(before, self.economic_state())
        self.assertEqual(FinancialProviderDispatch(self.bid).dispatch(
            binding['binding_uuid'], transport=lambda _: self.fail('No repetir I/O tras restore')), result)

    def test_email_terminal_rejection_and_malformed_outcome(self):
        self.enable()
        op = self.expense_operation()
        for outcome, expected in ((dict(category='rejected',reference=None,status_code=403),'FAILED_TERMINAL'), (dict(category='duplicate_confirmed',reference=None,status_code=200),'UNKNOWN_EXTERNAL_RESULT'), (dict(category='success',reference='SYNTHETIC-SECRET',status_code=True),'UNKNOWN_EXTERNAL_RESULT')):
            binding = self.bound_email(op)
            result = FinancialProviderDispatch(self.bid).dispatch(binding['binding_uuid'], transport=lambda a: outcome)
            self.assertEqual(result['result'], expected)
            self.assertNotIn('SYNTHETIC-SECRET', canonical(result))

    def test_pause_holds_email_before_claim(self):
        self.enable()
        binding = self.bound_email()
        self.pause()
        with self.assertRaises(StateError):
            FinancialProviderDispatch(self.bid).dispatch(binding['binding_uuid'], transport=lambda a: self.fail('HOLD debe impedir I/O'))
        with db.get_conn() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) AS n FROM '+ATTEMPTS+' WHERE business_id=?', (self.bid,)).fetchone()['n'], 0)

    def test_rotation_after_claim_aborts_without_io(self):
        self.enable()
        binding = self.bound_email()
        api = FinancialProviderDispatch(self.bid)
        api.claim(binding['binding_uuid'])
        with patch.object(config, 'BREVO_API_KEY', 'SYNTHETIC-ROTATED'):
            value = api.dispatch(binding['binding_uuid'], transport=lambda a: self.fail('Credenciales cambiadas'))
        self.assertEqual(value['result'], 'ABORTED_BEFORE_IO')

    def test_crash_before_claim_has_no_attempt(self):
        self.enable()
        binding = self.bound_email()
        api = FinancialProviderDispatch(self.bid)
        api.checkpoint = lambda point: (_ for _ in ()).throw(RuntimeError('crash')) if point=='before_claim' else None
        with self.assertRaises(RuntimeError):
            api.dispatch(binding['binding_uuid'], transport=self.success)
        with db.get_conn() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) AS n FROM '+ATTEMPTS+' WHERE business_id=?', (self.bid,)).fetchone()['n'], 0)

    def test_crash_after_claim_commit_can_start_exactly_once(self):
        self.enable()
        binding = self.bound_email()
        api = FinancialProviderDispatch(self.bid)
        api.checkpoint = lambda point: (_ for _ in ()).throw(RuntimeError('crash')) if point=='after_claim_commit' else None
        with self.assertRaises(RuntimeError):
            api.dispatch(binding['binding_uuid'], transport=self.success)
        api.checkpoint = lambda point: None
        self.assertEqual(api.dispatch(binding['binding_uuid'], transport=self.success)['result'], 'SUCCEEDED')

    def test_crashes_after_start_never_call_provider_again(self):
        self.enable()
        op = self.expense_operation()
        for point in ('before_provider_call','after_provider_before_result','during_result_transaction','after_result_commit'):
            binding = self.bound_email(op)
            api, calls = FinancialProviderDispatch(self.bid), []
            def send(a):
                calls.append(a)
                return self.success(a)
            api.checkpoint = lambda p: (_ for _ in ()).throw(RuntimeError('crash')) if p==point else None
            with self.assertRaises(RuntimeError):
                api.dispatch(binding['binding_uuid'], transport=send)
            api.checkpoint = lambda p: None
            value = api.recover_unknown(binding['binding_uuid'])
            self.assertEqual(value['result'], 'SUCCEEDED' if point=='after_result_commit' else 'UNKNOWN_EXTERNAL_RESULT')
            self.assertEqual(api.dispatch(binding['binding_uuid'], transport=send), value)
            self.assertEqual(len(calls), 0 if point=='before_provider_call' else 1)

    def test_synthetic_result_cannot_become_production_observed(self):
        self.enable()
        binding = self.bound_email()
        FinancialProviderDispatch(self.bid).dispatch(binding['binding_uuid'], transport=self.success)
        with db.get_conn() as c:
            a = c.execute('SELECT evidence_uuid FROM '+ATTEMPTS+' WHERE business_id=?', (self.bid,)).fetchone()
            with self.assertRaises(StateError):
                attestations.record_observed(FinancialSession(c), self.bid, self.principal, str(a['evidence_uuid']))

    def test_aeat_committed_binding_and_drain_paused(self):
        self.enable((C.INVOICE_ISSUE,), (C.AEAT,))
        binding = self.bound_invoice()
        self.assertEqual(binding['provider'], 'AEAT_VERIFACTU')
        self.pause()
        value = FinancialProviderDispatch(self.bid).dispatch(binding['binding_uuid'], transport=self.success)
        self.assertEqual(value['result'], 'SUCCEEDED')

    def test_aeat_outcomes_specific_duplicate_and_timeout(self):
        self.enable((C.INVOICE_ISSUE,), (C.AEAT,))
        for category, expected in (('success','SUCCEEDED'),('accepted_with_errors','SUCCEEDED'),('rejected','FAILED_TERMINAL'),('timeout','UNKNOWN_EXTERNAL_RESULT'),('duplicate_confirmed','SUCCEEDED')):
            binding = self.bound_invoice()
            value = FinancialProviderDispatch(self.bid).dispatch(binding['binding_uuid'], transport=lambda a: dict(category=category, reference='synthetic-csv', status_code=200))
            self.assertEqual(value['result'], expected)

    def test_all_provider_secret_markers_absent_from_export(self):
        for cap in (C.EMAIL, C.AEAT, C.WHATSAPP):
            self.verified(cap)
        value = canonical(self.exporter.export(self.principal, uuid4()))
        for marker in ('SYNTHETIC-BREVO-SECRET','SYNTHETIC-META-TOKEN','SYNTHETIC-AEAT-PRIVATE-KEY','SYNTHETIC-AEAT-PASSWORD',str(Path(config.VERIFACTU_KEY_PATH))):
            self.assertNotIn(marker, value)

    def test_invalid_certificate_chain_blocked_without_network(self):
        self.tls_patch.stop()
        body = self.check(C.AEAT)
        self.assertEqual(body['result'], 'BLOCKED')

    def test_direct_sql_cannot_insert_or_rewrite_f_evidence(self):
        body = self.check()
        with db.get_conn() as c:
            row = c.execute('SELECT * FROM '+ATTESTATIONS+' WHERE business_id=?', (self.bid,)).fetchone()
        for table in TABLES:
            with db.get_conn() as c, self.assertRaises(Exception):
                c.execute('DELETE FROM '+table+' WHERE business_id=?', (self.bid,)) if table==ATTESTATIONS else c.execute('INSERT INTO '+table+' (business_id,evidence_uuid,contract_version,created_by,session_version,created_at,body_canonical,content_hash) VALUES (?,?,?,?,?,?,?,?)', (self.bid,str(uuid4()),1,self.principal.user_id,0,row['created_at'],'{}',digest({})))
        self.assertEqual(ProviderAttestation.create(body).body, body)

    def test_attestation_alone_blocks_account_deletion_and_is_retained(self):
        from noesis.financial_privacy.retention import source_inventory
        bid = db.create_business('Evidencia F sintética', uuid4().hex+'@example.test')['id']
        user = db.create_user(uuid4().hex+'@example.test', 'fixture', bid)
        principal = Principal(user['id'], 0)
        with db.get_conn() as c:
            c.execute('BEGIN IMMEDIATE')
            body = attestations.check(FinancialSession(c), bid, principal, C.EMAIL,
                                      code_version='fixture')
        with self.assertRaisesRegex(ValueError, 'evidencia financiera durable'):
            db.delete_business_cascade(bid)
        with db.get_conn() as c:
            session = FinancialSession(c)
            self.assertEqual(ProviderRepository(session, bid).load(ATTESTATIONS, body['attestation_uuid']), body)
            inventory = source_inventory(session, bid)
            self.assertEqual(inventory[ATTESTATIONS]['count'], 1)
            self.assertEqual(inventory[ATTESTATIONS]['category'], 'financial_provenance')
            self.assertTrue(set(TABLES).issubset(inventory))

    def test_observability_readonly_and_tenant_scoped(self):
        from noesis.financial_providers.observability import read, observe
        from noesis.financial_providers.contracts import Observation
        self.check()
        before = self.economic_state()
        with db.get_conn() as c:
            value = read(FinancialSession(c), self.bid, self.principal)
            self.assertEqual(value['business_id'], self.bid)
            self.assertEqual(value['activation_generation'], 0)
            c.execute('BEGIN IMMEDIATE')
            observe(FinancialSession(c), self.bid, self.principal, uuid4(), Observation.PREFLIGHT, reference_hash=digest(value))
        self.assertEqual(before, self.economic_state())

    def test_real_rehearsal_history_a_e_f_d_capture_export_pause_resume(self):
        value, _ = self.enable()
        binding = self.bound_email()
        api = FinancialProviderDispatch(self.bid)
        result = api.dispatch(binding['binding_uuid'], transport=self.success)
        self.assertEqual(result['result'], 'SUCCEEDED')
        self.assertTrue(verify_export(self.exporter.export(self.principal, uuid4())))
        self.pause()
        self.exporter.export(self.principal, uuid4())
        ref = self.verified()
        receipt = self.preflight.evaluate(self.principal, value['evaluation_uuid'], attestations={C.EMAIL.value:ref['attestation_uuid']}, action='resume')
        self.assertEqual(receipt['result'], 'PASS', receipt)
        request = self.api.prepare(self.principal, uuid4(), 'resume', preflight_uuid=receipt['preflight_uuid'])
        self.api.authorize(self.principal, request.body['request_uuid'], approved_hash=request.content_hash)
        final = self.api.advance(self.principal, request.body['request_uuid'], 'enabled')
        self.assertEqual(final['activation_generation'], 2)
        self.assertTrue(verify_export(self.exporter.export(self.principal, uuid4())))
        self.assertEqual(api.dispatch(binding['binding_uuid'], transport=lambda a:self.fail('Replay G1 no llama provider')), result)

    def test_generation_old_unstarted_binding_never_dispatches_in_new_generation(self):
        value, refs = self.enable()
        binding = self.bound_email()
        self.pause()
        self.exporter.export(self.principal, uuid4())
        receipt = self.preflight.evaluate(self.principal, value['evaluation_uuid'], attestations=refs, action='resume')
        self.assertEqual(receipt['result'], 'PASS', receipt)
        req = self.api.prepare(self.principal, uuid4(), 'resume', preflight_uuid=receipt['preflight_uuid'])
        self.api.authorize(self.principal, req.body['request_uuid'], approved_hash=req.content_hash)
        self.api.advance(self.principal, req.body['request_uuid'], 'enabled')
        with self.assertRaises(StateError):
            FinancialProviderDispatch(self.bid).dispatch(binding['binding_uuid'], transport=lambda a:self.fail('Grant G1 no permite dispatch G2'))

    def test_pause_after_claim_aborts_before_provider_call(self):
        self.enable()
        binding = self.bound_email()
        api = FinancialProviderDispatch(self.bid)
        api.checkpoint = lambda point: self.pause() if point=='before_provider_call' else None
        value = api.dispatch(binding['binding_uuid'], transport=lambda a:self.fail('Pausa antes de llamada'))
        self.assertEqual(value['result'], 'ABORTED_BEFORE_IO')

    def test_started_result_recordable_after_actor_session_invalidated(self):
        self.enable()
        binding = self.bound_email()
        def send(a):
            with db.get_conn() as c:
                c.execute('UPDATE users SET session_version=session_version+1 WHERE business_id=? AND id=?',(self.bid,self.principal.user_id))
            return self.success(a)
        result = FinancialProviderDispatch(self.bid).dispatch(binding['binding_uuid'], transport=send)
        self.assertEqual(result['result'], 'SUCCEEDED')

    def test_email_generic_nonfinancial_legacy_still_claimable(self):
        self.enable()
        row = db.enqueue_email_message(business_id=self.bid, to_email='synthetic@example.test',subject='Aviso de privacidad',text_body='Sólo sintético')
        from noesis.financial_activation.contracts import instant
        claim = db.claim_next_email_message(now=datetime.now().isoformat(), stale_before=instant(clock()-timedelta(minutes=10)))
        self.assertIsNotNone(claim)
        self.assertEqual(claim['id'],row['id'])

    def test_financial_legacy_claim_excludes_bound_email(self):
        self.enable()
        binding = self.bound_email()
        from noesis.financial_activation.contracts import instant
        claim = db.claim_next_email_message(now=datetime.now().isoformat(), stale_before=instant(clock()-timedelta(minutes=10)))
        self.assertTrue(claim is None or claim['id'] != binding['outbox_id'])

    def test_unbound_legacy_financial_meta_metadata_never_claimed(self):
        from noesis.financial_channels.whatsapp import PREFIX
        self.enable()
        rows = [db.enqueue_whatsapp_message(business_id=self.bid, connection_id=self.meta_connection['id'], to_phone='34600000000', message_type='template', template_name=name, template_params='[]')
                for name in (config.WHATSAPP_TEMPLATE_INVOICE, config.WHATSAPP_TEMPLATE_PAYMENT_REMINDER, config.WHATSAPP_TEMPLATE_PAYMENT_ALERT)]
        rows.append(db.enqueue_whatsapp_message(business_id=self.bid, connection_id=self.meta_connection['id'], to_phone='34600000000', message_type='text', text_body='Contenido opaco', idempotency_key=PREFIX+str(uuid4())+':'+digest({'synthetic': True})))
        for row in rows:
            claimed = db.claim_next_whatsapp_message(now=datetime.now().isoformat(), stale_before=instant(clock()-timedelta(minutes=10)), only_ids=[row['id']])
            self.assertIsNone(claimed)

    def test_nonfinancial_meta_legacy_still_claimable_after_handoff(self):
        self.enable()
        row = db.enqueue_whatsapp_message(business_id=self.bid, connection_id=self.meta_connection['id'], to_phone='34600000000', message_type='text', text_body='Aviso no financiero sintético')
        claimed = db.claim_next_whatsapp_message(now=datetime.now().isoformat(), stale_before=instant(clock()-timedelta(minutes=10)), only_ids=[row['id']])
        self.assertEqual(claimed['id'], row['id'])

    def test_missing_or_wrong_provider_preflight_blocks_closed_profile(self):
        value, refs = self.ready((C.EXPENSE_CONFIRM,C.EMAIL), (C.EMAIL,))
        self.assertEqual(value['outcome'],'fully_eligible')
        result = self.preflight.evaluate(self.principal, value['evaluation_uuid'])
        self.assertIn('PROVIDER_ATTESTATION_MISSING',result['reasons'])
        with self.assertRaises(ValueError):
            self.preflight.evaluate(self.principal,value['evaluation_uuid'],attestations={C.WHATSAPP.value:refs[C.EMAIL.value]})

    def test_bank_capability_remains_blocked(self):
        self.policy()
        self.exporter.export(self.principal,uuid4())
        value = self.evaluate((C.BANK_IMPORT,))
        receipt = self.preflight.evaluate(self.principal,value['evaluation_uuid'])
        self.assertIn('BANK_CAPABILITY_UNVALIDATED',receipt['reasons'])

    def test_meta_success_rejection_unknown_and_pause_hold(self):
        self.enable((C.EXPENSE_CONFIRM,C.WHATSAPP),(C.WHATSAPP,))
        op = self.expense_operation()
        for category,expected in (('success','SUCCEEDED'),('rejected','FAILED_TERMINAL'),('timeout','UNKNOWN_EXTERNAL_RESULT')):
            b = self.bound_meta(op)
            r = FinancialProviderDispatch(self.bid).dispatch(b['binding_uuid'],transport=lambda a:dict(category=category,reference='synthetic-wamid',status_code=200))
            self.assertEqual(r['result'],expected)
            self.assertEqual(process_bound('whatsapp_outbox',only_ids=[b['outbox_id']],transport=lambda a:self.fail('Terminal/unknown no se repite')),[])
        hold = self.bound_meta(op)
        self.pause()
        with self.assertRaises(StateError):
            FinancialProviderDispatch(self.bid).dispatch(hold['binding_uuid'],transport=lambda a:self.fail('Meta HOLD'))

    def test_e_closure_authorization_overrides_committed_aeat_drain(self):
        from noesis.financial_privacy.closure import FinancialClosure
        self.enable((C.INVOICE_ISSUE,),(C.AEAT,))
        binding = self.bound_invoice()
        self.pause()
        policy = self.policy()
        request = db.create_privacy_request(self.bid,requester_user_id=self.principal.user_id,request_type='account_closure',retention_required=True)
        self.exporter.export(self.principal,uuid4(),'account_closure')
        closure = FinancialClosure(self.bid)
        plan = closure.plan(self.principal,uuid4(),privacy_request_id=request['id'],policy_uuid=policy['policy_uuid'])
        auth = closure.authorize(self.principal,plan['plan_uuid'],approved_hash=privacy_digest(plan))
        with self.assertRaises(StateError):
            FinancialProviderDispatch(self.bid).dispatch(binding['binding_uuid'],transport=lambda a:self.fail('Cierre E domina drain'))
        receipt = closure.apply(self.principal,plan['plan_uuid'],authorization_uuid=auth['authorization_uuid'])
        self.assertIsNotNone(receipt)

    def test_unknown_blocks_resume_and_read_model_reports_it(self):
        from noesis.financial_providers.observability import read
        value,refs = self.enable()
        binding = self.bound_email()
        FinancialProviderDispatch(self.bid).dispatch(binding['binding_uuid'],transport=lambda a:dict(category='timeout',reference=None,status_code=None))
        self.pause()
        self.exporter.export(self.principal,uuid4())
        receipt = self.preflight.evaluate(self.principal,value['evaluation_uuid'],attestations=refs,action='resume')
        self.assertEqual(receipt['result'],'BLOCKED')
        self.assertIn('UNCERTAIN_EXTERNAL_RESULT',receipt['reasons'])
        with db.get_conn() as c:
            result = read(FinancialSession(c),self.bid,self.principal)
            self.assertEqual(result['unknown_results'],1)
            self.assertIn('UNCERTAIN_EXTERNAL_RESULT',result['alerts'])

    def test_handoff_review_threshold_blocks_before_commit(self):
        value,_ = self.ready()
        receipt = self.preflight.evaluate(self.principal,value['evaluation_uuid'])
        req = self.api.prepare(self.principal,uuid4(),'enable',evaluation_uuid=value['evaluation_uuid'],preflight_uuid=receipt['preflight_uuid'])
        self.api.authorize(self.principal,req.body['request_uuid'],approved_hash=req.content_hash)
        with patch('noesis.financial_providers.limits.handoff_timing',return_value='MANUAL_REVIEW_REQUIRED'), self.assertRaises(StateError):
            self.api.advance(self.principal,req.body['request_uuid'],'validating')
        with db.get_conn() as c:
            self.assertEqual(c.execute('SELECT state FROM financial_activation_control WHERE business_id=?',(self.bid,)).fetchone()['state'],'off')

    def test_preflight_and_d_expiry_revalidate_each_use(self):
        value,_ = self.ready()
        receipt = self.preflight.evaluate(self.principal,value['evaluation_uuid'])
        with patch('noesis.financial_providers.preflight.clock',return_value=clock()+timedelta(minutes=6)),self.assertRaises(StateError):
            self.api.prepare(self.principal,uuid4(),'enable',evaluation_uuid=value['evaluation_uuid'],preflight_uuid=receipt['preflight_uuid'])

    def test_sql_observed_without_real_result_is_blocked(self):
        source = self.verified()
        fake = dict(source,attestation_uuid=str(uuid4()),level='production_observed',source_attempt_uuid=str(uuid4()),evidence=dict(source['evidence'],synthetic=False,safe_check='durable_result'))
        columns = {k:fake[k] for k in ('provider','implementation','capability','environment','level','configuration_fingerprint','credential_fingerprint','expires_at','result','source_attempt_uuid')}
        with db.get_conn() as c,self.assertRaises(Exception):
            ProviderRepository(FinancialSession(c),self.bid).append(ATTESTATIONS,fake['attestation_uuid'],self.principal,fake,clock(),**columns)

    def test_environment_mismatch_persists_closed_blocked_attestation(self):
        with patch.object(config,'VERIFACTU_AEAT_ENV','pruebas'):
            value = self.check(C.AEAT,Level.PRODUCTION_CONFIG)
        self.assertEqual(value['result'],'BLOCKED')
        self.assertIn('PROVIDER_ENVIRONMENT_MISMATCH',value['reasons'])

    def test_code_drift_blocks_new_dispatch(self):
        self.enable()
        binding = self.bound_email()
        with patch.object(config,'RELEASE_ID','different-code'),self.assertRaises(StateError):
            FinancialProviderDispatch(self.bid).dispatch(binding['binding_uuid'],transport=lambda a:self.fail('Código nuevo requiere validación nueva'))

    def test_local_smtp_selected_and_secret_not_exported(self):
        with patch.multiple(config,BREVO_API_KEY='',SMTP_HOST='smtp.example.test',SMTP_PORT=587,SMTP_USER='synthetic@example.test',SMTP_PASS='SYNTHETIC-SMTP-SECRET-MARKER'):
            value = self.check()
            self.assertEqual(value['implementation'],'smtp')
            self.assertEqual(value['result'],'PASS')
            self.assertNotIn('SYNTHETIC-SMTP-SECRET-MARKER',canonical(self.exporter.export(self.principal,uuid4())))

    def test_pending_inactive_meta_connection_does_not_verify(self):
        with db.get_conn() as c:
            c.execute('UPDATE whatsapp_connections SET status=? WHERE business_id=? AND id=?',('pending',self.bid,self.meta_connection['id']))
        value = self.check(C.WHATSAPP)
        self.assertEqual(value['result'],'BLOCKED')

    def test_attestation_wrong_capability_and_actor_stale(self):
        value = self.verified()
        with db.get_conn() as c:
            with self.assertRaises(StateError):
                attestations.verify(FinancialSession(c),self.bid,value['attestation_uuid'],C.WHATSAPP)
            c.execute('UPDATE users SET session_version=session_version+1 WHERE business_id=? AND id=?',(self.bid,self.principal.user_id))
        with db.get_conn() as c,self.assertRaises(StateError):
            attestations.verify(FinancialSession(c),self.bid,value['attestation_uuid'],C.EMAIL)

    def test_empty_m79_roundtrip_preserves_previous_evidence(self):
        before = self.economic_state()
        if config.DATABASE_URL:
            db.close_pool()
            with patch.object(config,'DATABASE_URL',self.admin_scoped):
                self.assertEqual(migrations.downgrade(78),78)
                self.assertEqual(migrations.upgrade(79),79)
                with db.get_conn() as c:
                    for table in TABLES:
                        c.execute('GRANT SELECT,INSERT,UPDATE,DELETE ON '+table+' TO '+self.role)
                db.close_pool()
        else:
            self.assertEqual(migrations.downgrade(78),78)
            self.assertEqual(migrations.upgrade(79),79)
        self.assertEqual(before,self.economic_state())

    def test_gmail_selected_decryptable_scoped_and_secret_excluded(self):
        with patch.multiple(config,GOOGLE_CLIENT_ID='synthetic-client-id',GOOGLE_CLIENT_SECRET='SYNTHETIC-GMAIL-CLIENT-SECRET'):
            db.save_oauth_credentials(self.bid,'google',account_email='synthetic@example.test',refresh_token='SYNTHETIC-GMAIL-REFRESH-MARKER',scope='https://www.googleapis.com/auth/gmail.send')
            value = self.check()
            self.assertEqual(value['implementation'],'gmail')
            self.assertEqual(value['result'],'PASS')
            exported = canonical(self.exporter.export(self.principal,uuid4(),include_legacy=True))
            self.assertNotIn('SYNTHETIC-GMAIL-REFRESH-MARKER',exported)
            self.assertNotIn('SYNTHETIC-GMAIL-CLIENT-SECRET',exported)
            with db.get_conn() as c:
                c.execute('UPDATE oauth_credentials SET refresh_token=? WHERE business_id=? AND provider=?',('v1:invalid-synthetic-ciphertext',self.bid,'google'))
            self.assertEqual(self.check()['result'],'BLOCKED')

    def test_f_local_preflight_never_uses_legacy_normalisation(self):
        with patch.object(db,'_normalise_row',side_effect=AssertionError('Financial Core exacto requerido')):
            self.assertEqual(self.check()['result'],'PASS')

    def test_closed_catalog_from_single_c_registry(self):
        self.assertEqual(requirement(C.AEAT), Provider.AEAT)
        self.assertEqual(requirement(C.WHATSAPP), Provider.META)
        self.assertEqual(requirement(C.EMAIL), Provider.EMAIL)
        self.assertIsNone(requirement(C.WEB))
        for invalid in ("stripe", "quote.accepted", "supplier_payment.made", "provider.google_login"):
            with self.assertRaises(ValueError):
                requirement(invalid)

    def test_levels_are_semantic_not_numeric_ladder(self):
        self.assertFalse(sufficient(Level.LOCAL, Environment.PRODUCTION))
        self.assertFalse(sufficient(Level.SANDBOX, Environment.PRODUCTION))
        self.assertFalse(sufficient(Level.PRODUCTION_CONFIG, Environment.SANDBOX))
        self.assertTrue(sufficient(Level.PRODUCTION_CONFIG, Environment.PRODUCTION))
        self.assertTrue(sufficient(Level.OBSERVED, Environment.PRODUCTION))

    def test_local_no_network_is_not_production_verification(self):
        body = self.check()
        self.assertEqual(body["result"], "PASS")
        self.assertEqual(body["evidence"]["safe_check"], "not_requested")
        with db.get_conn() as c, self.assertRaisesRegex(StateError, "LEVEL_INSUFFICIENT"):
            attestations.verify(FinancialSession(c), self.bid, body["attestation_uuid"], C.EMAIL)

    def test_real_safe_checks_default_blocked_even_with_permission(self):
        for authorized in (False, True):
            body = self.check(level=Level.PRODUCTION_CONFIG, network_authorized=authorized)
            self.assertEqual(body["result"], "BLOCKED")

    def test_specific_permission_no_financial_authority_borrowed(self):
        for invalid in ("financial.authorize", "financial.activation.manage", "historical.record", "privacy.financial.close"):
            with self.assertRaises(AccessDenied):
                self.check(permission=invalid)
        self.assertEqual(Permission.PREFLIGHT.value, "financial.providers.preflight")

    def test_observed_cannot_be_preflighted(self):
        with self.assertRaisesRegex(StateError, "REAL_RESULT"):
            self.check(level=Level.OBSERVED)

    def test_closed_attestation_versions_fields_float_and_hash(self):
        body = self.check()
        for edit in (lambda v: v.update(version=2), lambda v: v.update(version=True), lambda v: v.pop("business_id"),
                     lambda v: v.update(extra="secret"), lambda v: v.update(actor_session_version=0.1),
                     lambda v: v.update(provider="Stripe"), lambda v: v.update(implementation="groq"),
                     lambda v: v["evidence"].update(raw_response="secret"), lambda v: v.update(credential_fingerprint="secret")):
            copy = json.loads(canonical(body))
            edit(copy)
            with self.assertRaises((ValueError, TypeError)):
                ProviderAttestation.create(copy)
        reversed_body = dict(reversed(list(body.items())))
        self.assertEqual(ProviderAttestation.create(body), ProviderAttestation.create(reversed_body))
        changed = dict(body, attestation_uuid=str(uuid4()))
        self.assertNotEqual(digest(body), digest(changed))

    def test_attestation_renewal_new_uuid_old_row_immutable(self):
        first, second = self.check(), self.check()
        self.assertNotEqual(first["attestation_uuid"], second["attestation_uuid"])
        for sql in ("UPDATE " + ATTESTATIONS + " SET result='BLOCKED' WHERE business_id=?", "DELETE FROM " + ATTESTATIONS + " WHERE business_id=?"):
            with self.assertRaises(Exception), db.get_conn() as c:
                c.execute(sql, (self.bid,))

    def test_credential_rotation_invalidates_existing_attestation(self):
        body = self.verified()
        with patch.object(config, "BREVO_API_KEY", "SYNTHETIC-ROTATED-SECRET"), db.get_conn() as c:
            with self.assertRaisesRegex(StateError, "CONFIG_DRIFT"):
                attestations.verify(FinancialSession(c), self.bid, body["attestation_uuid"], C.EMAIL)

    def test_sender_configuration_drift(self):
        body = self.verified()
        with patch.object(config, "SMTP_FROM", "changed@example.test"), db.get_conn() as c:
            with self.assertRaisesRegex(StateError, "CONFIG_DRIFT"):
                attestations.verify(FinancialSession(c), self.bid, body["attestation_uuid"], C.EMAIL)
        meta = self.verified(C.WHATSAPP)
        with patch.object(config, 'META_GRAPH_VERSION', 'v999.0'), db.get_conn() as c:
            with self.assertRaisesRegex(StateError, 'CONFIG_DRIFT'):
                attestations.verify(FinancialSession(c), self.bid, meta['attestation_uuid'], C.WHATSAPP)

    def test_synthetic_attestation_never_usable_in_production(self):
        body = self.verified()
        with patch.object(config, "IS_PRODUCTION", True), db.get_conn() as c:
            with self.assertRaisesRegex(StateError, "LEVEL_INSUFFICIENT"):
                attestations.verify(FinancialSession(c), self.bid, body["attestation_uuid"], C.EMAIL)

    def test_attestation_expiry(self):
        body = self.verified()
        with db.get_conn() as c, self.assertRaisesRegex(StateError, "ATTESTATION_STALE"):
            attestations.verify(FinancialSession(c), self.bid, body["attestation_uuid"], C.EMAIL,
                               now=clock() + timedelta(minutes=6))

    def test_cross_tenant_principal_and_references(self):
        body = self.verified()
        with db.get_conn() as c:
            other = db.create_business("Otro sintético", "other@example.test")
            self.assertIsNone(ProviderRepository(FinancialSession(c), other["id"]).load(ATTESTATIONS, body["attestation_uuid"]))
            with self.assertRaises(AccessDenied):
                ProviderRepository(FinancialSession(c), other["id"]).principal(self.principal)

    def test_policy_provisional_still_blocks_real_readiness_and_preflight(self):
        self.policy(approved=False)
        self.exporter.export(self.principal, uuid4())
        value = self.evaluate()
        self.assertNotEqual(value["outcome"], "fully_eligible")
        receipt = self.preflight.evaluate(self.principal, value["evaluation_uuid"])
        self.assertEqual(receipt["result"], "BLOCKED")
        self.assertIn("PRIVACY_NOT_READY", receipt["reasons"])
        with self.assertRaises(StateError):
            self.api.prepare(self.principal, uuid4(), "enable", evaluation_uuid=value["evaluation_uuid"], preflight_uuid=receipt["preflight_uuid"])

    def test_real_a_full_web_needs_no_meta_email_attestation(self):
        value, _ = self.ready()
        self.assertEqual(value["outcome"], "fully_eligible")
        receipt = self.preflight.evaluate(self.principal, value["evaluation_uuid"])
        self.assertEqual(receipt["result"], "PASS", receipt)
        self.assertEqual(receipt["context"]["requirements"], {})

    def test_provider_evidence_only_removes_provider_blocker_new_a(self):
        self.policy()
        self.exporter.export(self.principal, uuid4())
        old = self.evaluate((C.EXPENSE_CONFIRM, C.EMAIL))
        self.assertNotEqual(old["outcome"], "fully_eligible")
        self.verified()
        new = self.evaluate((C.EXPENSE_CONFIRM, C.EMAIL))
        self.assertEqual(new["outcome"], "fully_eligible")
        with db.get_conn() as c:
            self.assertEqual(FinancialReadinessEvaluator(FinancialSession(c), self.bid).read(self.principal, old["evaluation_uuid"]), old)

    def test_preflight_replay_exact_hash_and_uuid_conflict(self):
        value, _ = self.ready()
        uid = uuid4()
        first = self.preflight.evaluate(self.principal, value["evaluation_uuid"], preflight_uuid=uid)
        self.assertEqual(first, self.preflight.evaluate(self.principal, value["evaluation_uuid"], preflight_uuid=uid))
        with self.assertRaises((ValueError, ConflictError)):
            self.preflight.evaluate(self.principal, value["evaluation_uuid"], preflight_uuid=uid, environment=Environment.SANDBOX)

    def test_schema79_requires_exact_preflight_before_d_enable(self):
        value, _ = self.ready()
        with self.assertRaisesRegex(StateError, "preflight"):
            self.api.prepare(self.principal, uuid4(), "enable", evaluation_uuid=value["evaluation_uuid"])
        receipt = self.preflight.evaluate(self.principal, value["evaluation_uuid"])
        request = self.api.prepare(self.principal, uuid4(), "enable", evaluation_uuid=value["evaluation_uuid"], preflight_uuid=receipt["preflight_uuid"])
        self.assertEqual(request.body["schema_version"], 77)
        self.api.authorize(self.principal, request.body["request_uuid"], approved_hash=request.content_hash)
        for stage in ("validating", "ready", "enabled"):
            final = self.api.advance(self.principal, request.body["request_uuid"], stage)
        self.assertEqual(final["final_state"], "enabled")

    def test_no_secrets_in_export_or_evidence(self):
        self.check()
        value = self.exporter.export(self.principal, uuid4())
        self.assertTrue(verify_export(value))
        text = canonical(value)
        self.assertNotIn("SYNTHETIC-BREVO-SECRET-DO-NOT-EXPORT", text)
        self.assertNotIn(config.SECRET_KEY, text)
        self.assertIn(ATTESTATIONS, value["sections"])

    def test_downgrade_with_f_evidence_is_blocked(self):
        self.check()
        with self.assertRaisesRegex(ValueError, "evidencia F"):
            migrations.downgrade(78)
        self.assertEqual(migrations.current_version(), 79)

    def test_operational_policy_is_closed_and_not_legal_policy(self):
        self.assertEqual(OperationalPolicy().history_max_items, 64)
        with self.assertRaises(ValueError):
            OperationalPolicy(readiness_ttl_seconds=600)

    def test_session_stale_preflight(self):
        value, _ = self.ready()
        with self.assertRaises(AccessDenied):
            self.preflight.evaluate(Principal(self.user["id"], 1), value["evaluation_uuid"])


class ProviderSQLite(ProviderContract, unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="noesis-f-synthetic-")
        self.addCleanup(tmp.cleanup)
        p = patch.multiple(config, DATABASE_URL="", DB_PATH=Path(tmp.name) / "synthetic.db")
        p.start()
        self.addCleanup(p.stop)
        db.init_db()
        self.setup_providers()
