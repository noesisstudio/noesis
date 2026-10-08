"""Continuidad G sintética, sockets denegados por el fixture F compartido."""

from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from noesis import config, db
from noesis.core.persistence import FinancialSession
from noesis.financial_activation.contracts import Capability as C, digest
from noesis.financial_operations.contracts import ConflictError, StateError
from tests.test_financial_providers import ProviderContract


class RecoveryContract:
    seed = ProviderContract.seed
    setup_providers = ProviderContract.setup_providers
    setup_readiness = ProviderContract.setup_readiness
    cut = ProviderContract.cut
    draft = ProviderContract.draft
    issued = ProviderContract.issued
    approved = ProviderContract.approved
    policy = ProviderContract.policy
    check = ProviderContract.check
    verified = ProviderContract.verified
    evaluate = ProviderContract.evaluate
    ready = ProviderContract.ready
    enable = ProviderContract.enable
    pause = ProviderContract.pause
    expense_operation = ProviderContract.expense_operation
    bound_email = ProviderContract.bound_email
    economic_state = ProviderContract.economic_state

    def expire(self, capabilities=(C.EXPENSE_CONFIRM,), providers=()):
        value, refs = self.enable(capabilities, providers)
        now = datetime.fromisoformat(value['expires_at']) + timedelta(seconds=1)
        for module in ('noesis.financial_activation.handoff', 'noesis.financial_providers.preflight',
                       'noesis.financial_providers.attestations'):
            p = patch(module + '.clock', return_value=now)
            p.start()
            self.addCleanup(p.stop)
        self.pause()
        self.exporter.export(self.principal, uuid4())
        return value, refs

    def resume(self, value, refs):
        preflight = self.preflight.evaluate(self.principal, value['evaluation_uuid'], attestations=refs, action='resume')
        self.assertEqual(preflight['result'], 'PASS', preflight)
        req = self.api.prepare(self.principal, uuid4(), 'resume', preflight_uuid=preflight['preflight_uuid'])
        self.api.authorize(self.principal, req.body['request_uuid'], approved_hash=req.content_hash)
        receipt = self.api.advance(self.principal, req.body['request_uuid'], 'enabled')
        self.assertEqual(receipt['activation_generation'], 2)
        self.assertEqual(receipt['evidence']['recovery_readiness_hash'], digest(preflight['context']['recovery_readiness']))
        return receipt

    def test_expired_a_current_continuity_resumes_g_plus_one(self):
        value, refs = self.expire()
        with db.get_conn() as conn:
            ev = self.api.generation(FinancialSession(conn), 1)[2]
            original = conn.execute_exact('SELECT * FROM financial_readiness_evaluations WHERE business_id=?', (self.bid,)).fetchall()
        self.resume(value, refs)
        with db.get_conn() as conn:
            self.assertEqual(original, conn.execute_exact('SELECT * FROM financial_readiness_evaluations WHERE business_id=?', (self.bid,)).fetchall())
            self.assertEqual(ev, self.api.generation(FinancialSession(conn), 1)[2])
            self.assertFalse(conn.execute('SELECT fence_enabled FROM financial_history_control WHERE business_id=?', (self.bid,)).fetchone()['fence_enabled'])

    def test_expired_a_source_drift_blocks_paused(self):
        value, refs = self.expire()
        db.update_fiscal(self.bid, address='Drift sintético')
        self.assertEqual(self.preflight.evaluate(self.principal, value['evaluation_uuid'], attestations=refs, action='resume')['result'], 'BLOCKED')

    def test_expired_a_provisional_privacy_blocks(self):
        value, refs = self.expire()
        self.policy(approved=False)
        self.assertEqual(self.preflight.evaluate(self.principal, value['evaluation_uuid'], attestations=refs, action='resume')['result'], 'BLOCKED')

    def test_expired_a_provider_stale_blocks(self):
        value, refs = self.expire((C.EXPENSE_CONFIRM, C.EMAIL), (C.EMAIL,))
        from noesis.financial_providers import attestations
        with patch.object(attestations, 'clock', return_value=datetime.fromisoformat(value['expires_at']) + timedelta(days=2)):
            result = self.preflight.evaluate(self.principal, value['evaluation_uuid'], attestations=refs, action='resume')
        self.assertEqual(result['result'], 'BLOCKED')

    def test_expired_a_fresh_provider_resumes(self):
        value, _ = self.expire((C.EXPENSE_CONFIRM, C.EMAIL), (C.EMAIL,))
        refs = {C.EMAIL.value:self.verified()['attestation_uuid']}
        self.resume(value, refs)

    def test_expired_a_unknown_external_result_remains_paused(self):
        from noesis.financial_providers.dispatch import FinancialProviderDispatch
        value, refs = self.enable()
        binding = self.bound_email()
        def timeout(attempt):
            raise TimeoutError('Resultado sintético desconocido')
        result = FinancialProviderDispatch(self.bid).dispatch(binding['binding_uuid'], transport=timeout)
        self.assertEqual(result['result'], 'UNKNOWN_EXTERNAL_RESULT')
        now = datetime.fromisoformat(value['expires_at']) + timedelta(seconds=1)
        with patch('noesis.financial_activation.handoff.clock', return_value=now), patch('noesis.financial_providers.preflight.clock', return_value=now):
            self.pause()
            self.exporter.export(self.principal, uuid4())
            pf = self.preflight.evaluate(self.principal, value['evaluation_uuid'], attestations=refs, action='resume')
            self.assertEqual(pf['result'], 'BLOCKED')
            with db.get_conn() as c:
                self.assertEqual(self.api.control(FinancialSession(c))['state'], 'paused')

    def test_expired_a_profile_change_cannot_use_original_grants(self):
        value, refs = self.expire()
        from noesis.financial_activation.handoff import FinancialActivation
        original = FinancialActivation.generation
        def changed(api, session, generation):
            request, proofs, receipt = original(api, session, generation)
            from noesis.financial_activation.contracts import Profile
            return dict(request, profile=Profile((C.EXPENSE_VOID,)).value()), proofs, receipt
        with patch.object(FinancialActivation, 'generation', changed):
            pf = self.preflight.evaluate(self.principal, value['evaluation_uuid'], attestations=refs, action='resume')
        self.assertEqual(pf['result'], 'BLOCKED')

    def test_expired_a_requires_current_operator_session_not_original_A_session(self):
        from noesis.financial_operations.contracts import Principal, AccessDenied
        value, refs = self.expire()
        with db.get_conn() as c:
            c.execute('UPDATE users SET session_version=1 WHERE id=? AND business_id=?', (self.principal.user_id, self.bid))
        with self.assertRaises(AccessDenied):
            self.preflight.evaluate(self.principal, value['evaluation_uuid'], action='resume')
        self.principal = Principal(self.principal.user_id, 1)
        self.resume(value, refs)

    def test_original_a_expiry_still_blocks_first_enable(self):
        value, refs = self.ready()
        from noesis.financial_providers import preflight
        with patch.object(preflight, 'clock', return_value=datetime.fromisoformat(value['expires_at']) + timedelta(seconds=1)):
            result = self.preflight.evaluate(self.principal, value['evaluation_uuid'], attestations=refs)
        self.assertEqual(result['result'], 'BLOCKED')

    def test_production_guard_unchanged(self):
        value, refs = self.expire()
        with patch.object(config, 'IS_PRODUCTION', True), self.assertRaises(StateError):
            self.api.prepare(self.principal, uuid4(), 'resume')

    def test_recovery_proof_closed_tamper_fields_and_float(self):
        from noesis.financial_activation.recovery_readiness import validate_proof
        value, refs = self.expire()
        pf = self.preflight.evaluate(self.principal, value['evaluation_uuid'], attestations=refs, action='resume')
        proof = pf['context']['recovery_readiness']
        self.assertIsNotNone(proof, pf)
        for change in ({'version':2}, {'business_id':True}, {'extra':True}, {'actor_session_version':0.0}, {'profile_hash':'invalid'}):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                validate_proof(dict(proof, **change))

    def test_preflight_readonly_core_and_recovery_every_use(self):
        value, refs = self.expire()
        before = self.economic_state()
        pf = self.preflight.evaluate(self.principal, value['evaluation_uuid'], attestations=refs, action='resume')
        with db.get_conn() as conn:
            self.preflight.verify(FinancialSession(conn), self.principal, pf['preflight_uuid'])
        self.assertEqual(before, self.economic_state())
        db.update_fiscal(self.bid, address='Otra dirección')
        with db.get_conn() as conn, self.assertRaises(ConflictError):
            self.preflight.verify(FinancialSession(conn), self.principal, pf['preflight_uuid'])
