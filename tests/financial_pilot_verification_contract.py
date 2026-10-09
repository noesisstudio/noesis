"""G-VERIFY: colectores autenticados exclusivamente sintéticos y BD real de fixture."""

from dataclasses import FrozenInstanceError
from datetime import timedelta
import hashlib
import hmac
import secrets
from unittest.mock import patch
from uuid import uuid4

from noesis import db
from noesis.core.persistence import FinancialSession
from noesis.financial_activation.contracts import Profile, Capability as C, canonical, digest, instant
from noesis.financial_privacy.repository import PrivacyRepository
from noesis.financial_privacy.schema import POLICIES
from noesis.financial_history.service import FLAGS
from noesis.financial_pilot.verification_contracts import (Verifier as V, CATALOG, Cohort, VerificationContext,
                                                         VerificationError, now_utc, EvidenceType)
from noesis.financial_pilot.evidence import SourceAuthority, TrustStore, VerifiedEvidence
from noesis.financial_pilot.verifiers import PilotVerifiers, SYSTEM, KEY_MATRIX, MONITORING_SECTIONS, RECOVERY_CASES
from noesis.financial_pilot.gate import PilotGate
from noesis.financial_pilot.contracts import Owner, PreparationContext
from noesis.financial_pilot.report import assess
from tests.financial_recovery_readiness_contract import RecoveryContract


class PilotVerificationContract:
    seed = RecoveryContract.seed
    setup_providers = RecoveryContract.setup_providers
    setup_readiness = RecoveryContract.setup_readiness
    cut = RecoveryContract.cut
    draft = RecoveryContract.draft
    issued = RecoveryContract.issued
    approved = RecoveryContract.approved
    policy = RecoveryContract.policy
    check = RecoveryContract.check
    verified = RecoveryContract.verified
    evaluate = RecoveryContract.evaluate
    ready = RecoveryContract.ready
    enable = RecoveryContract.enable
    pause = RecoveryContract.pause
    expense_operation = RecoveryContract.expense_operation
    economic_state = RecoveryContract.economic_state
    def gate_fixture(self, *, providers=False, cohort=Cohort.SYNTHETIC):
        capabilities = (C.EXPENSE_CONFIRM, C.EMAIL) if providers else (C.EXPENSE_CONFIRM,)
        self.second_user = db.create_user(uuid4().hex + '@example.test', 'fixture', self.bid)
        value, _ = self.ready(capabilities, (C.EMAIL,) if providers else ())
        self.assertEqual(value['outcome'], 'fully_eligible', value)
        self.ctx = VerificationContext(self.bid, Profile(capabilities), value['evaluation_uuid'], '1'*40, cohort, '2'*40, '7'*40)
        self.keys = {v:secrets.token_bytes(32) for v in V if v not in SYSTEM}
        self.trust = TrustStore(tuple(SourceAuthority(v, Cohort.SYNTHETIC, key) for v,key in self.keys.items()))
        self.now = now_utc()
        return value

    def verifiers(self, s, **kw):
        if s.dialect == 'sqlite':
            if not s.borrowed_connection.raw.in_transaction:
                s.execute('BEGIN IMMEDIATE')
        elif s.borrowed_connection.raw.info.transaction_status == 0:
            s.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        return PilotVerifiers(s, self.principal, kw.pop('context', self.ctx), trust=kw.pop('trust', self.trust),
                              code_version='fixture', clock=kw.pop('clock', lambda:self.now), **kw)

    def a(self):
        return dict(user_id=self.principal.user_id, session_version=self.principal.session_version)

    def key_metadata(self):
        return dict(probe_uuid=str(uuid4()), key_fingerprint='2'*64,
                    matrix={r:dict(accessible=a, inaccessible=b) for r,(a,b) in KEY_MATRIX.items()})

    def metadata(self, api):
        current, a = api.current(), self.a()
        policy_ref = current['privacy_refs'][POLICIES]
        row = PrivacyRepository(api.s, self.bid).load(POLICIES, policy_ref['uuid'])
        body = PrivacyRepository(api.s, self.bid).body(POLICIES, policy_ref['uuid'])
        backup = dict(backup_uuid=str(uuid4()), created_at=instant(self.now-timedelta(seconds=1)), content_hash='3'*64,
                      encryption='AT_REST_VERIFIED', access_verification_uuid=str(uuid4()), custodian=a,
                      storage_class='PRIVATE_IMMUTABLE', location_class='ISOLATED_VAULT', scope='business_and_system',
                      business_id=self.bid, system_uuid=str(uuid4()))
        key = self.key_metadata()
        roles = {o.value:a for o in Owner}
        roles[Owner.SECONDARY.value] = dict(user_id=self.second_user['id'], session_version=0)
        replicas = [dict(replica_uuid=str(uuid4()), role=r, code_sha=self.ctx.code_sha, schema_version=79,
                         flags=dict.fromkeys(FLAGS, False), database_role='RESTRICTED_RUNTIME') for r in ('web_runtime','financial_worker','scheduler')]
        def runbook(scenario, operator=a):
            return dict(rehearsal_uuid=str(uuid4()), scenario=scenario, operator=operator, completed_at=instant(self.now),
                        result='PASS', failures=[], runbook_version=1, runbook_hash='4'*64, accepted_hash='4'*64)
        return {
            V.LEGAL_POLICY:dict(policy_uuid=policy_ref['uuid'], policy_hash=digest(body['policy']), approval_actor=a,
                                approval_at=str(row['created_at']), policy_version=1, review_uuid=str(uuid4())),
            V.PILOT_BUSINESS:dict(selection_uuid=str(uuid4()), business_id=self.bid, criterion='EMPTY'),
            V.PILOT_PROFILE:dict(selection_uuid=str(uuid4()), profile=self.ctx.profile.value(), profile_hash=self.ctx.profile.content_hash,
                                 capabilities=current['capabilities'], dependencies=current['dependencies']),
            V.BACKUP:backup,
            V.RESTORE:dict(drill_uuid=str(uuid4()), backup=backup, environment_uuid=str(uuid4()), isolation='OUTBOUND_DENIED', schema_version=79,
                           result='PASS', integrity_expected_hash='5'*64, integrity_actual_hash='5'*64,
                           E_registry_hash='6'*64, E_replayed_hash='6'*64, completed_at=instant(self.now), operator=a, custodian=a),
            V.RUNTIME_KEY:key,
            V.DEPLOYMENT_COMPATIBILITY:dict(inventory_uuid=str(uuid4()), code_sha=self.ctx.code_sha, schema_version=79,
                                           expected_replicas=[r['replica_uuid'] for r in replicas], replicas=replicas, runtime_keys=key),
            V.OPERATORS:dict(assignment_uuid=str(uuid4()), roles=roles),
            V.BACKUP_CUSTODIAN:dict(assignment_uuid=str(uuid4()), custodian=a, backup=backup),
            V.PAUSE_RUNBOOK:runbook('D_PAUSE_F_HOLD_EMAIL_META_DRAIN_COMMITTED_AEAT'),
            V.UNKNOWN_RUNBOOK:runbook('EMAIL_META_AEAT_UNKNOWN_NO_AUTOMATIC_RETRY', roles[Owner.SECONDARY.value]),
            V.MONITORING:dict(access_probe_uuid=str(uuid4()), operator=a, sections=list(MONITORING_SECTIONS), backup=backup),
            V.MAIN_INTEGRATION:dict(integration_base_sha='7'*40, current_main_sha='7'*40, financial_chain_sha=self.ctx.financial_chain_sha,
                                    integration_sha=self.ctx.code_sha, base_ancestor_sha='7'*40, chain_ancestor_sha=self.ctx.financial_chain_sha,
                                    CI_run_uuid=str(uuid4()), CI_scope='COMPLETE_A_G', CI_sha=self.ctx.code_sha, CI_conclusion='SUCCESS',
                                    failures=0, errors=0, review_uuid=str(uuid4()), review_result='ACCEPTED'),
            V.RESUME_CONTINUITY:dict(rehearsal_uuid=str(uuid4()), schema_version=79, completed_at=instant(self.now), operator=a,
                                     cases=dict.fromkeys(RECOVERY_CASES, 'PASS'), original_a_hash='9'*64, previous_generation=1,
                                     new_generation=2, original_handoff_hash='a'*64, pause_hash='b'*64, recovery_hash='c'*64),
        }

    def envelope(self, api, v, metadata):
        e = dict(version=1, verifier=v.value, evidence_type=CATALOG[v].evidence_type.value, cohort=Cohort.SYNTHETIC.value,
                 business_id=self.bid, profile_hash=self.ctx.profile.content_hash, context_hash=digest(api.current()),
                 receipt_uuid=str(uuid4()), issued_at=instant(self.now), expires_at=instant(self.now+timedelta(seconds=300)),
                 authority=CATALOG[v].authority.value,
                 actor=dict(user_id=self.second_user['id'], session_version=0) if CATALOG[v].authority == Owner.SECONDARY else self.a(), metadata=metadata)
        signature = hmac.new(self.keys[v], canonical(e).encode(), hashlib.sha256).hexdigest()
        return e, signature

    def verify(self, api, v, m):
        e, sig = self.envelope(api, v, m)
        return api.verify(v, envelope=e, signature=sig)

    def all_evidence(self, api):
        metadata = self.metadata(api)
        return tuple(api.verify(v) if v in SYSTEM else self.verify(api, v, metadata[v]) for v in V)

    def test_all_twenty_verified_synthetic_ready_never_authorizes(self):
        self.gate_fixture()
        before = self.economic_state()
        with db.get_conn() as conn:
            api = self.verifiers(FinancialSession(conn))
            evidence = self.all_evidence(api)
            gate = PilotGate(api)
            result = gate.decide(evidence)
            self.assertEqual(result.body['result'], 'PILOT_READY', result.body)
            self.assertEqual(len(result.body['evidence_hashes']), 20)
            self.assertFalse(result.body['activation_authorized'])
            self.assertFalse(result.body['real_evidence_verified'])
            self.assertEqual(result.body['scope'], 'SYNTHETIC_STRUCTURAL')
            self.assertEqual(gate.validate(result, evidence), result.body)
            self.assertEqual(result.content_hash, gate.decide(tuple(reversed(evidence))).content_hash)
        self.assertEqual(before, self.economic_state())

    def test_catalog_closed_complete_types_and_contracts(self):
        self.assertEqual(set(CATALOG), set(V))
        self.assertEqual(len(CATALOG), 20)
        self.assertEqual({s.evidence_type for s in CATALOG.values()}, set(EvidenceType))
        with self.assertRaises(TypeError):
            CATALOG[V.BACKUP] = None
        with self.assertRaises(ValueError):
            V('verified=true')
        self.assertTrue(all(s.version == 1 and s.failure_reasons and s.algorithm and s.source and s.ttl_seconds for s in CATALOG.values()))

    def test_missing_each_of_twenty_verifiers_blocks(self):
        self.gate_fixture()
        with db.get_conn() as conn:
            api = self.verifiers(FinancialSession(conn))
            evidence = self.all_evidence(api)
            for v in V:
                with self.subTest(verifier=v):
                    result = PilotGate(api).decide(tuple(e for e in evidence if e.body['verifier'] != v))
                    self.assertEqual(result.body['result'], 'PILOT_BLOCKED')
                    self.assertIn(v, [b['verifier'] for b in result.body['blockers']])

    def test_unsigned_hash_reference_claims_are_not_authority(self):
        self.gate_fixture()
        with db.get_conn() as conn:
            api = self.verifiers(FinancialSession(conn), trust=TrustStore())
            m = self.metadata(api)[V.BACKUP]
            e, sig = self.envelope(api, V.BACKUP, m)
            with self.assertRaises(VerificationError):
                api.verify(V.BACKUP, envelope=e, signature=sig)
            for claim in ({'verified':True}, {'approved':True}, {'result':'PASS'}, {'hash':'a'*64}, 'reference'):
                with self.subTest(claim=claim), self.assertRaises(TypeError):
                    PilotGate(api).decide((claim,))

    def test_signed_metadata_still_requires_type_specific_validation(self):
        self.gate_fixture()
        with db.get_conn() as conn:
            api = self.verifiers(FinancialSession(conn))
            for v in V:
                if v not in SYSTEM:
                    with self.subTest(verifier=v), self.assertRaises(VerificationError):
                        self.verify(api, v, {'verified':True})

    def test_tamper_every_envelope_field_rejected(self):
        self.gate_fixture()
        with db.get_conn() as conn:
            api = self.verifiers(FinancialSession(conn))
            e, sig = self.envelope(api, V.BACKUP, self.metadata(api)[V.BACKUP])
            for field in e:
                with self.subTest(field=field), self.assertRaises(VerificationError):
                    api.verify(V.BACKUP, envelope=dict(e, **{field:None}), signature=sig)

    def test_tamper_opaque_evidence_and_report_invalid(self):
        self.gate_fixture()
        with db.get_conn() as conn:
            api = self.verifiers(FinancialSession(conn))
            evidence = self.all_evidence(api)
            gate = PilotGate(api)
            result = gate.decide(evidence)
            with self.assertRaises(FrozenInstanceError):
                result.canonical_content = '{}'
            for field in ('result', 'blockers', 'context', 'context_hash', 'evidence_hashes', 'activation_authorized'):
                altered = object.__new__(type(result))
                object.__setattr__(altered, 'canonical_content', canonical(dict(result.body, **{field:None})))
                object.__setattr__(altered, '_seal', result._seal)
                with self.subTest(field=field), self.assertRaises(VerificationError):
                    gate.validate(altered, evidence)
            altered = object.__new__(VerifiedEvidence)
            object.__setattr__(altered, 'canonical_content', canonical(dict(evidence[0].body, business_id=self.bid+1)))
            object.__setattr__(altered, '_seal', evidence[0]._seal)
            self.assertEqual(gate.decide((altered,)).body['result'], 'PILOT_BLOCKED')

    def test_source_expiry_context_drift_and_session_rotation(self):
        self.gate_fixture()
        with db.get_conn() as conn:
            api = self.verifiers(FinancialSession(conn))
            evidence = self.all_evidence(api)
            result = PilotGate(api).decide(evidence)
            self.now += timedelta(seconds=301)
            self.assertEqual(PilotGate(api).decide(evidence).body['result'], 'PILOT_BLOCKED')
            with self.assertRaises(VerificationError):
                PilotGate(api).validate(result, evidence)

    def test_current_configuration_drift_rejects_old_proof(self):
        self.gate_fixture()
        with db.get_conn() as conn:
            api = self.verifiers(FinancialSession(conn))
            proof = api.verify(V.PRIVACY)
            conn.execute('UPDATE businesses SET address=? WHERE id=?', ('Drift', self.bid))
            with self.assertRaises(VerificationError):
                api.recheck(proof)

    def test_cross_tenant_signed_backup_rejected(self):
        self.gate_fixture()
        other = db.create_business('Otro sintético', 'other@example.test')
        outsider = db.create_user(uuid4().hex+'@example.test', 'fixture', other['id'])
        with db.get_conn() as conn:
            api = self.verifiers(FinancialSession(conn))
            m = self.metadata(api)[V.BACKUP]
            m['business_id'] += 1
            with self.assertRaises(VerificationError):
                self.verify(api, V.BACKUP, m)
            m['business_id'] = self.bid
            m['custodian'] = dict(user_id=outsider['id'], session_version=0)
            with self.assertRaises(VerificationError):
                self.verify(api, V.BACKUP, m)

    def test_synthetic_never_real_and_real_D_guard_remains_blocked(self):
        self.gate_fixture(cohort=Cohort.REAL)
        with db.get_conn() as conn:
            api = self.verifiers(FinancialSession(conn))
            with self.assertRaises(VerificationError):
                self.verify(api, V.BACKUP, self.metadata(api)[V.BACKUP])
            with self.assertRaises(VerificationError):
                api.verify(V.PRODUCTION_ACTIVATION)

    def test_provider_local_and_sandbox_never_production(self):
        self.gate_fixture(providers=True)
        from noesis.financial_providers.contracts import Level
        with db.get_conn() as conn:
            self.assertTrue(self.verifiers(FinancialSession(conn)).verify(V.PROVIDER_ATTESTATION))
        for level in (Level.LOCAL, Level.SANDBOX):
            self.check(C.EMAIL, level)
            with self.subTest(level=level), db.get_conn() as conn, self.assertRaises(VerificationError):
                self.verifiers(FinancialSession(conn)).verify(V.PROVIDER_ATTESTATION)

    def test_provisional_policy_fails_legal_privacy_and_A(self):
        self.gate_fixture()
        self.policy(approved=False)
        with db.get_conn() as conn:
            api = self.verifiers(FinancialSession(conn))
            for v in (V.PRIVACY, V.READINESS):
                with self.subTest(verifier=v), self.assertRaises(VerificationError):
                    api.verify(v)
            with self.assertRaises(VerificationError):
                self.verify(api, V.LEGAL_POLICY, self.metadata(api)[V.LEGAL_POLICY])

    def test_backup_encryption_access_scope_and_secret_extra_rejected(self):
        self.gate_fixture()
        with db.get_conn() as conn:
            api = self.verifiers(FinancialSession(conn))
            m = self.metadata(api)[V.BACKUP]
            for changes in ({'encryption':'UNVERIFIED'}, {'access_verification_uuid':None}, {'scope':'other'},
                            {'created_at':instant(self.now-timedelta(days=2))}, {'DATABASE_URL':'secret'}, {'path':'C:/secret'}):
                with self.subTest(changes=changes), self.assertRaises((VerificationError, ValueError)):
                    self.verify(api, V.BACKUP, dict(m, **changes))

    def test_restore_requires_actual_drill_integrity_E_replay_and_isolation(self):
        self.gate_fixture()
        with db.get_conn() as conn:
            api = self.verifiers(FinancialSession(conn))
            m = self.metadata(api)[V.RESTORE]
            for changes in ({'isolation':'NETWORK_ENABLED'}, {'schema_version':78}, {'result':'FAIL'},
                            {'integrity_actual_hash':'d'*64}, {'E_replayed_hash':'e'*64}, {'drill_uuid':None}):
                with self.subTest(changes=changes), self.assertRaises((VerificationError, ValueError)):
                    self.verify(api, V.RESTORE, dict(m, **changes))

    def test_deployment_all_replicas_flags_roles_keys_and_old_code(self):
        self.gate_fixture()
        with db.get_conn() as conn:
            api = self.verifiers(FinancialSession(conn))
            m = self.metadata(api)[V.DEPLOYMENT_COMPATIBILITY]
            for change in ({'schema_version':78}, {'code_sha':'f'*40}, {'replicas':m['replicas'][:-1]}, {'expected_replicas':[]}):
                with self.subTest(change=change), self.assertRaises(VerificationError):
                    self.verify(api, V.DEPLOYMENT_COMPATIBILITY, dict(m, **change))
            m['runtime_keys']['matrix']['db_runtime']['accessible'] = ['execution_verifier_key']
            with self.assertRaises(VerificationError):
                self.verify(api, V.DEPLOYMENT_COMPATIBILITY, m)

    def test_runbook_markdown_without_rehearsal_cannot_pass(self):
        self.gate_fixture()
        with db.get_conn() as conn:
            api = self.verifiers(FinancialSession(conn))
            for v in (V.PAUSE_RUNBOOK, V.UNKNOWN_RUNBOOK):
                m = self.metadata(api)[v]
                for changes in ({'rehearsal_uuid':'docs/runbook.md'}, {'failures':['UNKNOWN']}, {'result':'FAIL'}, {'scenario':'MARKDOWN_EXISTS'}):
                    with self.subTest(verifier=v, changes=changes), self.assertRaises((VerificationError, ValueError)):
                        self.verify(api, v, dict(m, **changes))

    def test_main_integration_partial_CI_wrong_ancestry_failures_rejected(self):
        self.gate_fixture()
        with db.get_conn() as conn:
            api = self.verifiers(FinancialSession(conn))
            m = self.metadata(api)[V.MAIN_INTEGRATION]
            for changes in ({'CI_scope':'ONLY_G'}, {'failures':1}, {'errors':1}, {'CI_conclusion':'FAIL'}, {'base_ancestor_sha':'f'*40}, {'review_result':'PENDING'}):
                with self.subTest(changes=changes), self.assertRaises(VerificationError):
                    self.verify(api, V.MAIN_INTEGRATION, dict(m, **changes))

    def test_profile_cannot_be_selected_optimized_or_shrunk(self):
        self.gate_fixture()
        with db.get_conn() as conn:
            api = self.verifiers(FinancialSession(conn))
            m = self.metadata(api)[V.PILOT_PROFILE]
            with self.assertRaises(VerificationError):
                self.verify(api, V.PILOT_PROFILE, dict(m, capabilities=[]))

    def test_empty_drafts_allowed_but_operations_not_hidden(self):
        # El borrador precede al corte, igual que en el flujo histórico autorizado.
        with patch.object(self, 'cut', return_value=None):
            self.setup_providers()
            self.draft()
        self.cut()
        self.gate_fixture()
        with db.get_conn() as conn:
            api = self.verifiers(FinancialSession(conn))
            m = self.metadata(api)[V.PILOT_BUSINESS]
            self.assertTrue(self.verify(api, V.PILOT_BUSINESS, m))
        # Un Capture sintético autorizado bloquea EMPTY, sin efectos del gate.
        self.enable()
        self.expense_operation()
        with db.get_conn() as conn:
            api = self.verifiers(FinancialSession(conn))
            with self.assertRaises(VerificationError):
                self.verify(api, V.PILOT_BUSINESS, m)

    def test_gprep_assess_still_anti_ready(self):
        report = assess(PreparationContext('1'*40, '2'*64), now=now_utc())
        self.assertEqual(report['result'], 'PILOT_BLOCKED')
        self.assertFalse(report['activation_authorized'])

    def test_no_float_extra_versions_and_no_secret_exports(self):
        self.gate_fixture()
        with db.get_conn() as conn:
            api = self.verifiers(FinancialSession(conn))
            m = self.metadata(api)[V.BACKUP]
            for change in ({'business_id':float(self.bid)}, {'extra':'secret'}):
                with self.assertRaises((TypeError, VerificationError)):
                    self.verify(api, V.BACKUP, dict(m, **change))
            result = PilotGate(api).decide(self.all_evidence(api))
            for marker in ('SYNTHETIC-BREVO-SECRET', 'SYNTHETIC-AEAT-PASSWORD', 'DATABASE_URL', 'private.pem'):
                self.assertNotIn(marker, result.canonical_content)
            self.assertNotIn('xxxxxxxx', repr(SourceAuthority(V.BACKUP, Cohort.SYNTHETIC, b'x'*32)))

    def test_read_only_verifiers_never_DML(self):
        self.gate_fixture()
        with db.get_conn() as conn:
            statements = []
            execute = conn.execute_exact
            def tracked(sql, params=()):
                statements.append(str(sql))
                return execute(sql, params)
            with patch.object(conn, 'execute_exact', side_effect=tracked):
                api = self.verifiers(FinancialSession(conn))
                PilotGate(api).decide(self.all_evidence(api))
            self.assertFalse(any(s.lstrip().upper().startswith(('INSERT','UPDATE','DELETE','CREATE','ALTER','DROP')) for s in statements))

    def test_duplicate_evidence_and_foreign_verifier_instance_rejected(self):
        self.gate_fixture()
        with db.get_conn() as conn:
            api = self.verifiers(FinancialSession(conn))
            e = api.verify(V.PRIVACY)
            with self.assertRaises(VerificationError):
                PilotGate(api).decide((e,e))
            other = self.verifiers(FinancialSession(conn))
            self.assertEqual(PilotGate(other).decide((e,)).body['result'], 'PILOT_BLOCKED')
