"""D: aceptación sintética; nunca readiness de producción ni provider preflight."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import nullcontext
from uuid import uuid4

from noesis import config, db
from noesis.core.persistence import FinancialSession
from noesis.financial_activation.contracts import Capability as C, CapabilityResult as CR, Profile, Policy, capability_proof, instant
from noesis.financial_activation.evaluator import FinancialReadinessEvaluator
from noesis.financial_activation.handoff import FinancialActivation
from noesis.financial_activation.handoff_schema import TABLES
from noesis.financial_operations.contracts import AccessDenied, ConflictError, StateError
from tests.financial_readiness_contract import ReadinessContract


class HandoffSQLite(unittest.TestCase):
    seed = ReadinessContract.seed
    setup_readiness = ReadinessContract.setup_readiness
    cut = ReadinessContract.cut
    draft = ReadinessContract.draft
    issued = ReadinessContract.issued
    approved = ReadinessContract.approved

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='noesis-110d-test-')
        self.addCleanup(temp.cleanup)
        settings = patch.multiple(config, DATABASE_URL='', DB_PATH=Path(temp.name) / 'fixture.db')
        settings.start()
        self.addCleanup(settings.stop)
        db.init_db()
        self.setup_readiness()
        self.cut()
        self.api = FinancialActivation(self.bid, code_version='fixture')

    def fixture_full(self, capabilities=(C.EXPENSE_CONFIRM,)):
        """SOLO fixture: pruebas A FULL estructurales, sin cambiar blockers runtime."""
        profile, uid = Profile(capabilities), str(uuid4())
        now = datetime.now(timezone.utc)
        with db.get_conn() as conn:
            conn.execute('BEGIN IMMEDIATE')
            ev = FinancialReadinessEvaluator(FinancialSession(conn), self.bid)
            result = ev.evaluate(self.principal, uuid4(), profile, history=self.reference, code_version='fixture', now=now)
            closure, edges = profile.closure(fiscal_cancel_required=result['context']['verifactu_enabled'])
            proofs = []
            for cap in sorted(C, key=lambda c: c.value):
                status = CR.ELIGIBLE if cap in closure else CR.NOT_REQUESTED
                dependencies = {d: CR.ELIGIBLE.value for d in edges.get(cap.value, ())}
                proofs.append(capability_proof(cap, status, [], dependencies, {'synthetic_fixture': True}))
            body = dict(profile=profile.value(), outcome='fully_eligible', reasons=[], capabilities=proofs, context=result['context'])
            ev.repo.store(self.principal, uid, profile, Policy(), 'fixture', result['context'], body,
                          instant(now), instant(now + timedelta(minutes=5)))
        return uid

    def approved_request(self, action='enable', **kw):
        if action == 'enable':
            if 'evaluation_uuid' not in kw:
                kw['evaluation_uuid'] = self.fixture_full()
        req = self.api.prepare(self.principal, uuid4(), action, **kw)
        self.api.authorize(self.principal, req.body['request_uuid'], approved_hash=req.content_hash)
        return req

    def enable(self):
        req = self.approved_request()
        for stage in ('validating', 'ready', 'enabled'):
            receipt = self.api.advance(self.principal, req.body['request_uuid'], stage)
        return req, receipt

    def control(self):
        with db.get_conn() as conn:
            return dict(conn.execute('SELECT * FROM financial_activation_control WHERE business_id=?', (self.bid,)).fetchone())

    def test_handoff_retains_certificate_and_history_identity(self):
        with db.get_conn() as conn:
            before = self.api.snapshot(FinancialSession(conn), self.principal)
        req, result = self.enable()
        c = self.control()
        self.assertEqual((c['state'], c['activation_generation'], bool(c['ever_enabled'])), ('enabled', 1, True))
        with db.get_conn() as conn:
            epoch = conn.execute('SELECT * FROM financial_history_epochs WHERE business_id=?', (self.bid,)).fetchone()
            cut = conn.execute('SELECT * FROM financial_history_cut_manifests WHERE business_id=?', (self.bid,)).fetchone()
            self.assertEqual(epoch['state'], 'handed_off')
            self.assertEqual(str(epoch['handoff_uuid']), result['receipt_uuid'])
            self.assertFalse(epoch['fence_enabled'])
            self.assertTrue(cut['certifiable'])
            self.assertFalse(cut['boundary_current'])
            self.assertEqual(str(cut['epoch_uuid']), self.reference.epoch_uuid)
            self.assertEqual(conn.execute('SELECT COUNT(*) AS n FROM economic_events WHERE business_id=?', (self.bid,)).fetchone()['n'], 0)
            self.assertEqual(conn.execute('SELECT COUNT(*) AS n FROM financial_operations WHERE business_id=?', (self.bid,)).fetchone()['n'], 0)
            self.assertEqual(before, self.api.snapshot(FinancialSession(conn), self.principal))
        self.assertEqual(result, self.api.advance(self.principal, req.body['request_uuid'], 'enabled'))
        with self.assertRaisesRegex(ValueError, 'evidencia financiera durable'):
            db.delete_business_cascade(self.bid)
        self.assertEqual(c, self.control())

    def test_channel_only_and_runtime_blocked_financial_readiness_denied(self):
        with self.assertRaises(StateError):
            self.api.prepare(self.principal, uuid4(), 'enable', evaluation_uuid=self.fixture_full((C.WEB,)))
        now = datetime.now(timezone.utc)
        with db.get_conn() as conn:
            conn.execute('BEGIN IMMEDIATE')
            result = FinancialReadinessEvaluator(FinancialSession(conn), self.bid).evaluate(
                self.principal, uuid4(), Profile((C.EXPENSE_CONFIRM,)), history=self.reference, code_version='fixture', now=now)
        with self.assertRaises(StateError):
            self.api.prepare(self.principal, uuid4(), 'enable', evaluation_uuid=result['evaluation_uuid'])

    def test_explicit_permission_and_exact_human_hash_required(self):
        uid = self.fixture_full()
        with self.assertRaises(AccessDenied):
            self.api.prepare(self.principal, uuid4(), 'enable', evaluation_uuid=uid, permission='financial.authorize')
        req = self.api.prepare(self.principal, uuid4(), 'enable', evaluation_uuid=uid)
        with self.assertRaises(ConflictError):
            self.api.authorize(self.principal, req.body['request_uuid'], approved_hash='0'*64)
        with self.assertRaises(AccessDenied):
            self.api.authorize(self.principal, req.body['request_uuid'], approved_hash=req.content_hash, kind='mandate')

    def test_activation_request_closed_versioned_deterministic_and_immutable(self):
        from noesis.financial_activation.activation_contracts import ActivationRequest
        request = self.approved_request()
        body = request.body
        self.assertEqual(ActivationRequest(dict(reversed(list(body.items())))).content_hash, request.content_hash)
        body['profile']['capabilities'].append('expense.void')
        self.assertNotEqual(body, request.body)
        mutations = ({'request_version': 2}, {'business_id': 1.0}, {'activation_generation': True}, {'permission': 'financial.authorize'}, {'schema_version': 76}, {'extra': 'no permitido'}, {'capabilities': ['expense.confirm']}, {'recovery_proof': {}}, {'action': 'unknown'})
        for change in mutations:
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                ActivationRequest(dict(request.body, **change))
        for key in request.body:
            incomplete = request.body
            del incomplete[key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                ActivationRequest(incomplete)

    def test_pause_resume_increments_generation_without_new_a_evaluation(self):
        self.enable()
        req = self.approved_request('pause', pause_reason='operator_request')
        self.api.advance(self.principal, req.body['request_uuid'], 'paused')
        self.assertEqual(self.control()['state'], 'paused')
        req = self.approved_request('resume')
        self.api.advance(self.principal, req.body['request_uuid'], 'enabled')
        c = self.control()
        self.assertEqual((c['state'], c['activation_generation'], bool(c['ever_enabled'])), ('enabled', 2, True))

    def test_raw_sql_cannot_jump_or_disable_monotonic_control(self):
        for target in ('validating', 'ready'):
            request = self.approved_request()
            self.api.advance(self.principal, request.body['request_uuid'], 'validating')
            if target == 'ready':
                self.api.advance(self.principal, request.body['request_uuid'], 'ready')
            abort = self.approved_request('abort')
            receipt = self.api.advance(self.principal, abort.body['request_uuid'], 'off')
            self.assertEqual(receipt, self.api.advance(self.principal, abort.body['request_uuid'], 'off'))
            self.assertEqual((self.control()['state'], self.control()['activation_generation'], bool(self.control()['ever_enabled'])), ('off', 0, False))
        self.enable()
        with self.assertRaises(StateError):
            self.approved_request('abort')
        for statement in ("state='off'", 'ever_enabled=FALSE', 'activation_generation=0'):
            with self.assertRaises(Exception), db.get_conn() as conn:
                conn.execute('UPDATE financial_activation_control SET ' + statement + ',control_revision=control_revision+1 WHERE business_id=?', (self.bid,))
        self.assertEqual(self.control()['state'], 'enabled')
        with self.assertRaises(Exception), db.get_conn() as conn:
            conn.execute("INSERT INTO financial_activation_revisions(business_id,control_revision,state,activation_generation,receipt_uuid) VALUES (?,10000,'enabled',1,?)", (self.bid, str(uuid4())))

    def test_prepare_context_cannot_create_human_activation_authority(self):
        from noesis.financial_activation.execution_context import execution_context
        from noesis.financial_activation.activation_contracts import ActivationPermission
        uid = self.fixture_full()
        req = self.api.prepare(self.principal, uuid4(), 'enable', evaluation_uuid=uid)
        with self.assertRaises(Exception), self.api.transaction(self.principal, ActivationPermission.MANAGE) as s:
            with execution_context(s, self.api.context(req, 'prepare')):
                s.execute("INSERT INTO financial_activation_authorizations(business_id,authorization_uuid,request_uuid,approved_hash,actor_user_id,actor_session_version,kind,permission,authorized_at) VALUES (?,?,?,?,?,0,'human_confirmation','financial.activation.manage',?)", (self.bid, str(uuid4()), req.body['request_uuid'], req.content_hash, self.principal.user_id, instant(datetime.now(timezone.utc))))
        with db.get_conn() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) AS n FROM financial_activation_authorizations WHERE business_id=?', (self.bid,)).fetchone()['n'], 0)

    def test_new_operation_is_bound_and_legacy_is_blocked_even_with_flag_off(self):
        from noesis.purchasing_capture import ExpenseCapture
        from noesis.financial_operations.contracts import EntryIdentity
        self.enable()
        with self.assertRaises(StateError):
            db.add_expense('Material', '12.10', business_id=self.bid)
        service = ExpenseCapture(self.bid)
        with patch.object(config, 'FINANCIAL_CORE_ENABLED', True):
            request = service.review_confirm(self.principal, amount='12.10', concept='Material')
            op = service.prepare(self.principal, EntryIdentity.web_api(uuid4()), request)
            self.assertEqual(op.activation_generation, 1)
            service.authorize(self.principal, op.operation_uuid, channel='web_api', approved_hash=request.request_hash, approved_revision=None)
            result = service.execute(self.principal, op.operation_uuid)
            self.assertEqual(result.state.value, 'committed')
        self.assertEqual(result, service.operations.recover(self.principal, op.operation_uuid))
        with self.assertRaises(StateError):
            db.add_expense('Otro', '1.00', business_id=self.bid)

    def test_handoff_each_precommit_checkpoint_rolls_back(self):
        req = self.approved_request()
        for stage in ('validating', 'ready'):
            self.api.advance(self.principal, req.body['request_uuid'], stage)
        original = self.control()
        points = ('readiness_verified', 'receipt_written', 'generation_written', 'grants_written', 'epoch_handed_off',
                  'fence_removed', 'certificate_verified', 'before_control', 'control_written', 'before_commit')
        for point in points:
            with self.subTest(point=point):
                def crash(name):
                    if name == point:
                        raise RuntimeError('synthetic crash')
                with patch.object(self.api, 'checkpoint', side_effect=crash), self.assertRaises(RuntimeError):
                    self.api.advance(self.principal, req.body['request_uuid'], 'enabled')
                self.assertEqual(original, self.control())
                with db.get_conn() as conn:
                    self.assertTrue(conn.execute('SELECT fence_enabled FROM financial_history_control WHERE business_id=?', (self.bid,)).fetchone()['fence_enabled'])
                    for table in TABLES[-2:]:
                        self.assertEqual(conn.execute('SELECT COUNT(*) AS n FROM ' + table + ' WHERE business_id=?', (self.bid,)).fetchone()['n'], 0)
        self.api.advance(self.principal, req.body['request_uuid'], 'enabled')

    def test_postcommit_response_loss_recovers_same_receipt(self):
        req = self.approved_request()
        for stage in ('validating', 'ready'):
            self.api.advance(self.principal, req.body['request_uuid'], stage)
        def crash(name):
            if name == 'after_commit':
                raise RuntimeError('response lost')
        with patch.object(self.api, 'checkpoint', side_effect=crash), self.assertRaises(RuntimeError):
            self.api.advance(self.principal, req.body['request_uuid'], 'enabled')
        receipt = self.api.advance(self.principal, req.body['request_uuid'], 'enabled')
        self.assertEqual(str(self.control()['current_transition_uuid']), receipt['receipt_uuid'])

    def test_executor_cannot_commit_effect_before_operation_result(self):
        from noesis.purchasing_capture import ExpenseCapture
        from noesis.financial_operations.contracts import EntryIdentity
        self.enable()
        with patch.object(config, 'FINANCIAL_CORE_ENABLED', True):
            service = ExpenseCapture(self.bid)
            request = service.review_confirm(self.principal, amount='12.10', concept='Material')
            op = service.prepare(self.principal, EntryIdentity.web_api(uuid4()), request)
            service.authorize(self.principal, op.operation_uuid, channel='web_api', approved_hash=request.request_hash, approved_revision=None)
            def unsafe(session, request):
                from noesis.financial_writers import purchasing
                purchasing.add_expense(session, 'Material', '12.10', business_id=self.bid)
                session.borrowed_connection.raw.commit()
                raise AssertionError('Un efecto no puede confirmarse aquí')
            with self.assertRaises(Exception) as error:
                service.operations.execute(self.principal, op.operation_uuid, unsafe)
            self.assertNotIsInstance(error.exception, AssertionError)
        with db.get_conn() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) AS n FROM expenses WHERE business_id=?', (self.bid,)).fetchone()['n'], 0)
            self.assertEqual(c.execute('SELECT state FROM financial_operations WHERE business_id=? AND operation_uuid=?', (self.bid, op.operation_uuid)).fetchone()['state'], 'approved')

    def test_authorized_executor_cannot_commit_an_extra_uncovered_source(self):
        from noesis.purchasing_capture import ExpenseCapture
        from noesis.financial_operations.contracts import EntryIdentity
        from noesis.financial_writers import purchasing
        self.enable()
        with patch.object(config, 'FINANCIAL_CORE_ENABLED', True):
            service = ExpenseCapture(self.bid)
            request = service.review_confirm(self.principal, amount='12.10', concept='Material')
            op = service.prepare(self.principal, EntryIdentity.web_api(uuid4()), request)
            service.authorize(self.principal, op.operation_uuid, channel='web_api', approved_hash=request.request_hash, approved_revision=None)
            original = purchasing.add_expense
            def injected(session, *args, **kwargs):
                session.execute("INSERT INTO expenses(business_id,concept,amount,created_at) VALUES (?,'Extra sin evidencia','1.00','2026-10-06T00:00:00+00:00')", (self.bid,))
                return original(session, *args, **kwargs)
            with patch.object(purchasing, 'add_expense', side_effect=injected), self.assertRaises(Exception):
                service.execute(self.principal, op.operation_uuid)
        with db.get_conn() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) AS n FROM expenses WHERE business_id=?', (self.bid,)).fetchone()['n'], 0)
            self.assertEqual(c.execute('SELECT state FROM financial_operations WHERE business_id=? AND operation_uuid=?', (self.bid, op.operation_uuid)).fetchone()['state'], 'approved')

    def test_invoice_issue_authority_cannot_create_payment_state(self):
        from noesis.invoice_capture.service import InvoiceCapture
        from noesis.financial_operations.contracts import EntryIdentity
        from noesis.financial_writers import invoices
        req = self.approved_request(evaluation_uuid=self.fixture_full((C.INVOICE_ISSUE,)))
        for stage in ('validating','ready','enabled'):
            self.api.advance(self.principal, req.body['request_uuid'], stage)
        invoice = self.draft()
        service = InvoiceCapture(self.bid)
        with patch.object(config, 'FINANCIAL_CORE_ENABLED', True):
            request = service.review(self.principal, invoice['id'])
            op = service.prepare(self.principal, EntryIdentity.web_api(uuid4()), request)
            service.authorize(self.principal, op.operation_uuid, channel='web_api', approved_hash=request.request_hash, approved_revision=request.expected_revision)
            original = invoices.issue_invoice
            def injected(session, *args, **kwargs):
                result = original(session, *args, **kwargs)
                session.execute("UPDATE invoices SET status='cobrada',paid_at='2026-10-06' WHERE business_id=? AND id=?", (self.bid, invoice['id']))
                return result
            with patch.object(invoices, 'issue_invoice', side_effect=injected), self.assertRaises(Exception):
                service.execute(self.principal, op.operation_uuid)
        with db.get_conn() as c:
            self.assertEqual(c.execute('SELECT status FROM invoices WHERE business_id=? AND id=?',(self.bid, invoice['id'])).fetchone()['status'], 'borrador')
            self.assertEqual(c.execute('SELECT COUNT(*) AS n FROM economic_events WHERE business_id=?',(self.bid,)).fetchone()['n'], 0)

    def exact_fixture(self):
        from tests.financial_history_import_contract import HistoryImportContract
        HistoryImportContract.exact_storage(self)

    def test_b_historical_resolution_survives_handoff_byte_for_byte(self):
        from noesis.financial_antecedents.resolver import AntecedentResolver
        from noesis.financial_antecedents.contracts import AntecedentRef, ResolutionRequest, Purpose
        self.setup_readiness()  # Otro tenant sintético sin epoch previo.
        self.exact_fixture()
        with db.get_conn() as c:
            c.execute("INSERT INTO expenses (business_id,concept,amount,created_at) VALUES (?,'Material','12.10','2026-09-01T00:00:00+00:00')", (self.bid,))
        self.assertEqual(self.cut()['result'], 'PASS')
        self.api = FinancialActivation(self.bid, code_version='fixture')
        with db.get_conn() as c:
            c.execute('BEGIN IMMEDIATE')
            e = c.execute("SELECT * FROM economic_events WHERE business_id=? AND source_type='expense'", (self.bid,)).fetchone()
            request = ResolutionRequest(AntecedentRef('expense', e['source_id'], e['source_revision'], str(e['event_uuid'])), Purpose.INSPECT)
            original = AntecedentResolver(FinancialSession(c), self.bid).persist_resolution(self.principal, uuid4(), request)
        self.assertEqual(original['result']['outcome'], 'resolved')
        self.enable()
        with db.get_conn() as c:
            c.execute('BEGIN IMMEDIATE')
            self.assertEqual(original, AntecedentResolver(FinancialSession(c), self.bid).verify_resolution(self.principal, original))

    def test_pause_cancels_pending_revokes_mandates_and_old_authority_never_returns(self):
        from noesis.purchasing_capture import ExpenseCapture
        from noesis.financial_operations.contracts import EntryIdentity
        self.enable()
        service = ExpenseCapture(self.bid)
        with patch.object(config, 'FINANCIAL_CORE_ENABLED', True):
            request = service.review_confirm(self.principal, amount='12.10', concept='Material')
            op = service.prepare(self.principal, EntryIdentity.web_api(uuid4()), request)
            service.authorize(self.principal, op.operation_uuid, channel='web_api', approved_hash=request.request_hash, approved_revision=None)
            mandate = service.operations.grant_mandate(self.principal, request, channel='web_api', expires_at=datetime.now(timezone.utc)+timedelta(minutes=3))
            pause = self.approved_request('pause', pause_reason='operator_request')
            self.api.advance(self.principal, pause.body['request_uuid'], 'paused')
            with self.assertRaises(StateError):
                service.execute(self.principal, op.operation_uuid)
            self.assertEqual(service.operations.recover(self.principal, op.operation_uuid).state.value, 'cancelled')
            with db.get_conn() as c:
                self.assertIsNotNone(c.execute('SELECT revoked_at FROM financial_authorizations WHERE business_id=? AND authorization_uuid=?', (self.bid, mandate)).fetchone()['revoked_at'])
            resume = self.approved_request('resume')
            self.api.advance(self.principal, resume.body['request_uuid'], 'enabled')
            with self.assertRaises(StateError):
                service.execute(self.principal, op.operation_uuid)

    def test_no_new_historical_epoch_after_ever_enabled(self):
        from noesis.financial_history.importer import HistoryImporter
        self.enable()
        with self.assertRaises(Exception):
            HistoryImporter(self.bid).open(self.principal, uuid4(), repository_version='fixture', environment_identity='synthetic')
        self.assertEqual(self.control()['state'], 'enabled')

    def as_migrator(self):
        return nullcontext()

    def test_migration77_preserves_populated_parents_sealed_a_and_active_foreign_keys(self):
        from noesis import migrations
        tables = ('financial_history_epochs', 'financial_history_cut_manifests', 'financial_history_manifests',
                  'financial_history_items', 'financial_history_import_batches', 'financial_history_import_items',
                  'financial_history_reconciliations', 'financial_readiness_evaluations', 'financial_readiness_capabilities')
        with self.as_migrator():
            if migrations.current_version() > 76:
                migrations.downgrade(76)
            self.assertEqual(migrations.current_version(), 76)
            self.fixture_full()
            with db.get_conn() as c:
                before = {t: [dict(r) for r in c.execute_exact('SELECT * FROM ' + t + ' WHERE business_id=? ORDER BY 1,2', (self.bid,)).fetchall()] for t in tables}
            migrations.upgrade(77)
            with db.get_conn() as c:
                for t in tables:
                    after = [dict(r) for r in c.execute_exact('SELECT * FROM ' + t + ' WHERE business_id=? ORDER BY 1,2', (self.bid,)).fetchall()]
                    self.assertEqual(len(after), len(before[t]))
                    for old, new in zip(before[t], after):
                        self.assertEqual(old, {key: new[key] for key in old})
                if c.dialect == 'sqlite':
                    self.assertEqual(c.execute('PRAGMA foreign_keys').fetchone()['foreign_keys'], 1)
                    self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(), [])
            with self.assertRaises(Exception), db.get_conn() as c:
                c.execute('UPDATE financial_history_cut_manifests SET plan_hash=? WHERE business_id=?', ('0'*64, self.bid))

    def test_direct_sql_final_surfaces_fail_without_context_and_drafts_survive_pause(self):
        self.enable()
        invoice = self.draft()
        statements = (
            ("UPDATE invoices SET status='emitida' WHERE business_id=? AND id=?", (self.bid, invoice['id'])),
            ("INSERT INTO invoice_payments(business_id,invoice_id,amount) VALUES (?,?,'1.00')", (self.bid, invoice['id'])),
            ("INSERT INTO received_invoices(business_id,total) VALUES (?,'1.00')", (self.bid,)),
            ("INSERT INTO expenses(business_id,concept,amount,created_at) VALUES (?,'SQL','1.00','2026-10-06')", (self.bid,)),
            ("INSERT INTO bank_transactions(business_id,amount) VALUES (?,'1.00')", (self.bid,)),
            ("INSERT INTO invoice_cancellation_records(business_id,invoice_id) VALUES (?,?)", (self.bid, invoice['id'])),
        )
        for sql, parameters in statements:
            with self.subTest(sql=sql), self.assertRaises(Exception), db.get_conn() as c:
                c.execute(sql, parameters)
        pause = self.approved_request('pause', pause_reason='operator_request')
        self.api.advance(self.principal, pause.body['request_uuid'], 'paused')
        draft = self.draft()
        with db.get_conn() as c:
            c.execute("UPDATE invoices SET concept='Borrador editable' WHERE business_id=? AND id=?", (self.bid, draft['id']))
            self.assertEqual(c.execute('SELECT status FROM invoices WHERE business_id=? AND id=?', (self.bid, draft['id'])).fetchone()['status'], 'borrador')

    def test_wrong_transaction_context_bindings_fail_and_committed_cannot_replay(self):
        from noesis.purchasing_capture import ExpenseCapture
        from noesis.financial_operations.contracts import EntryIdentity
        from noesis.financial_activation.execution_context import execution_context
        self.enable()
        service = ExpenseCapture(self.bid)
        with patch.object(config, 'FINANCIAL_CORE_ENABLED', True):
            request = service.review_confirm(self.principal, amount='12.10', concept='Material')
            op = service.prepare(self.principal, EntryIdentity.web_api(uuid4()), request)
            service.authorize(self.principal, op.operation_uuid, channel='web_api', approved_hash=request.request_hash, approved_revision=None)
            valid = dict(kind='effect', business_id=self.bid, operation_uuid=op.operation_uuid, generation=1, capability='expense.confirm', availability=True, request_hash=request.request_hash)
            changes = ({'generation': 0}, {'capability': 'supplier_invoice.confirm'}, {'operation_uuid': str(uuid4())}, {'business_id': self.bid + 100000}, {'kind': 'fake'}, {'availability': False})
            for change in changes:
                with self.subTest(change=change), self.assertRaises(Exception), db.get_conn() as c:
                    s = FinancialSession(c)
                    if s.dialect == 'sqlite':
                        s.execute('BEGIN IMMEDIATE')
                    with execution_context(s, dict(valid, **change)):
                        s.execute("INSERT INTO expenses(business_id,concept,amount,created_at) VALUES (?,'Directo','12.10','2026-10-06')", (self.bid,))
            service.execute(self.principal, op.operation_uuid)
            with self.assertRaises(Exception), db.get_conn() as c:
                s = FinancialSession(c)
                if s.dialect == 'sqlite':
                    s.execute('BEGIN IMMEDIATE')
                with execution_context(s, valid):
                    s.execute("INSERT INTO expenses(business_id,concept,amount,created_at) VALUES (?,'Replay','12.10','2026-10-06')", (self.bid,))

    def test_pause_and_resume_precommit_failure_and_postcommit_recovery(self):
        from noesis.purchasing_capture import ExpenseCapture
        from noesis.financial_operations.contracts import EntryIdentity
        self.enable()
        service = ExpenseCapture(self.bid)
        with patch.object(config, 'FINANCIAL_CORE_ENABLED', True):
            request = service.review_confirm(self.principal, amount='12.10', concept='Material')
            op = service.prepare(self.principal, EntryIdentity.web_api(uuid4()), request)
            service.operations.grant_mandate(self.principal, request, channel='web_api', expires_at=datetime.now(timezone.utc)+timedelta(minutes=3))
        pause = self.approved_request('pause', pause_reason='operator_request')
        before = self.control()
        for point in ('before_pause_cancel', 'after_pause_cancel', 'before_pause_revoke', 'after_pause_revoke', 'pause_terminalization', 'receipt_written', 'before_control', 'control_written', 'before_commit'):
            def crash(name):
                if name == point:
                    raise RuntimeError('crash sintético')
            with self.subTest(action='pause', point=point), patch.object(self.api, 'checkpoint', side_effect=crash), self.assertRaises(RuntimeError):
                self.api.advance(self.principal, pause.body['request_uuid'], 'paused')
            self.assertEqual(self.control(), before)
            self.assertEqual(service.operations.recover(self.principal, op.operation_uuid).state.value, 'prepared')
        self.api.advance(self.principal, pause.body['request_uuid'], 'paused')
        resume = self.approved_request('resume')
        before = self.control()
        for point in ('receipt_written', 'generation_written', 'grants_written', 'before_control', 'control_written', 'before_commit'):
            def crash(name):
                if name == point:
                    raise RuntimeError('crash sintético')
            with self.subTest(action='resume', point=point), patch.object(self.api, 'checkpoint', side_effect=crash), self.assertRaises(RuntimeError):
                self.api.advance(self.principal, resume.body['request_uuid'], 'enabled')
            self.assertEqual(self.control(), before)
        def crash(name):
            if name == 'after_commit':
                raise RuntimeError('respuesta perdida')
        with patch.object(self.api, 'checkpoint', side_effect=crash), self.assertRaises(RuntimeError):
            self.api.advance(self.principal, resume.body['request_uuid'], 'enabled')
        receipt = self.api.advance(self.principal, resume.body['request_uuid'], 'enabled')
        self.assertEqual((receipt['activation_generation'], self.control()['activation_generation']), (2, 2))

    def execute_capture(self, service, request):
        from noesis.financial_operations.contracts import EntryIdentity
        identity = EntryIdentity.imported(request.parameters['batch'], request.parameters['row']) if request.command_type.value == 'bank_transaction.import' else EntryIdentity.web_api(uuid4())
        op = service.prepare(self.principal, identity, request)
        service.authorize(self.principal, op.operation_uuid, channel=identity.namespace, approved_hash=request.request_hash, approved_revision=request.expected_revision)
        result = service.execute(self.principal, op.operation_uuid)
        self.assertEqual(result.activation_generation, 1)
        self.assertEqual(result.state.value, 'committed')
        return result

    def test_all_existing_capture_families_execute_under_exact_grants(self):
        from datetime import date
        from noesis.financial_activation.contracts import FINANCIAL
        from noesis.invoice_capture.service import InvoiceCapture
        from noesis.payment_capture.service import PaymentCapture
        from noesis.bank_capture.service import BankCapture
        from noesis.purchasing_capture import SupplierInvoiceCapture, ExpenseCapture
        from noesis.fiscal_cancellation_capture.service import FiscalCancellationCapture
        from noesis.financial_antecedents.resolver import AntecedentResolver
        from noesis.financial_antecedents.contracts import AntecedentRef, ResolutionRequest, Purpose
        self.setup_readiness()
        db.update_verifactu_mode(self.bid, True)
        self.cut()
        self.api = FinancialActivation(self.bid, code_version='fixture')
        req = self.approved_request(evaluation_uuid=self.fixture_full(tuple(FINANCIAL)))
        for stage in ('validating', 'ready', 'enabled'):
            self.api.advance(self.principal, req.body['request_uuid'], stage)
        today = date.today().isoformat()
        with patch.object(config, 'FINANCIAL_CORE_ENABLED', True), patch('urllib.request.urlopen', side_effect=AssertionError('red prohibida')):
            invoices, pay, bank = InvoiceCapture(self.bid), PaymentCapture(self.bid), BankCapture(self.bid)
            invoice = self.draft()
            issued = self.execute_capture(invoices, invoices.review(self.principal, invoice['id']))
            self.execute_capture(pay, pay.review(self.principal, invoice['id'], amount='5.00'))
            imported = self.execute_capture(bank, bank.review_import(self.principal, batch_uuid=uuid4(), row_key='one', account_scope='synthetic', statement_hash='a'*64, booked_on=today, amount='10.00'))
            db.suggest_bank_transaction(imported.result['bank_transaction_id'], self.bid, invoice['id'], score=1, reason='Candidato local')
            self.execute_capture(bank, bank.review_match(self.principal, imported.result['bank_transaction_id']))
            rectifying = db.create_rectifying_invoice(invoice['id'], self.bid, concept='Rectificar', base='1.00', reason='Diferencia confirmada')
            self.execute_capture(invoices, invoices.review(self.principal, rectifying['id']))
            supplier, expense = SupplierInvoiceCapture(self.bid), ExpenseCapture(self.bid)
            supplier_result = self.execute_capture(supplier, supplier.review_confirm(self.principal, total='121.00', base='100.00', vat_amount='21.00', irpf_amount='0.00', vat_rate='21', number='REC1', issued_on=today))
            sid = supplier_result.result['source_id']
            self.execute_capture(supplier, supplier.review_correct(self.principal, sid, reason='Corrección humana', total='242.00', base='200.00', vat_amount='42.00'))
            self.execute_capture(supplier, supplier.review_void(self.principal, sid, reason='Retirada humana'))
            er = self.execute_capture(expense, expense.review_confirm(self.principal, amount='12.10', concept='Material', vat_amount='2.10', vat_rate='21', spent_on=today))
            self.execute_capture(expense, expense.review_void(self.principal, er.result['source_id'], reason='Retirada humana'))
            with db.get_conn() as c:
                c.execute("UPDATE verifactu_outbox SET status='aceptado' WHERE business_id=? AND invoice_id=?", (self.bid, invoice['id']))
                e = c.execute('SELECT * FROM economic_events WHERE business_id=? AND event_uuid=?', (self.bid, issued.result['event_uuid'])).fetchone()
                ref = AntecedentRef('invoice', e['source_id'], e['source_revision'], str(e['event_uuid']))
                resolution = AntecedentResolver(FinancialSession(c), self.bid).persist_resolution(self.principal, uuid4(), ResolutionRequest(ref, Purpose.FISCAL_CANCEL))
            cancel = FiscalCancellationCapture(self.bid)
            self.execute_capture(cancel, cancel.review(self.principal, resolution, reason='Alta duplicada'))
