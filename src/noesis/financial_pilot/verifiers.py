"""Verificadores específicos prestados, sin conexión propia, DML, red ni ficheros."""

from datetime import timedelta
import json
import secrets

from noesis import config
from noesis.core.persistence import FinancialSession, schema_version
from noesis.financial_activation.contracts import HistoryContext, canonical, digest, instant
from noesis.financial_activation.evaluator import FinancialReadinessEvaluator
from noesis.financial_activation.readiness_verifier import verify_readiness
from noesis.financial_operations.contracts import Principal, StateError, ConflictError, AccessDenied
from noesis.financial_privacy.repository import PrivacyRepository, assert_open
from noesis.financial_privacy.retention import readiness_evidence, source_inventory
from noesis.financial_privacy.schema import POLICIES, EXPORTS
from noesis.financial_providers.attestations import verify as verify_attestation
from noesis.financial_providers.repository import ProviderRepository
from noesis.financial_providers.schema import ATTESTATIONS, ATTEMPTS, RESULTS
from noesis.financial_providers.contracts import requirement, Environment
from noesis.financial_history.service import FLAGS
from .contracts import Owner
from .evidence import TrustStore, _sealed, _check_seal
from .verification_contracts import (Verifier as V, Cohort, CATALOG, VerificationContext,
    Failure, VerificationError, now_utc, closed, fingerprint, identifier, actor, timestamp, sha)


SYSTEM = frozenset((V.READINESS, V.HISTORY, V.PRIVACY, V.EXPORT, V.PROVIDER_ATTESTATION, V.PRODUCTION_ACTIVATION))
MONITORING_SECTIONS = ('activation', 'generation', 'grants', 'preflight', 'provider_expiry',
                       'pending_unknown', 'closure', 'history', 'backup_freshness')
RECOVERY_CASES = ('expired_a_resumes_g_plus_one', 'source_drift_blocks', 'provider_stale_blocks',
                  'privacy_invalid_blocks', 'unknown_blocks', 'profile_change_blocks', 'old_grant_blocks')
KEY_MATRIX = {'web_runtime': (['credential_fingerprint'], ['execution_verifier_key']),
              'financial_worker': (['credential_fingerprint'], ['execution_verifier_key']),
              'scheduler': (['credential_fingerprint'], ['execution_verifier_key']),
              'db_runtime': ([], ['execution_verifier_key']),
              'execution_verifier': (['execution_verifier_key'], [])}


def require(condition, reason=Failure.BLOCKED):
    if not condition:
        raise VerificationError(reason)


class PilotVerifiers:
    """Composición privada. REAL/SYNTHETIC procede del entorno confiable, no del chat.

    El llamador presta una transacción consistente y conserva conexión/TX.
    Cada uso vuelve a leer BD y autenticar recibos. No registrar datos reales aquí.
    """
    def __init__(self, session, principal, context, *, trust=None, code_version, clock=now_utc):
        if type(session) is not FinancialSession or type(principal) is not Principal or type(context) is not VerificationContext:
            raise TypeError('Sesión/principal/contexto cerrados requeridos.')
        self.s, self.principal, self.context = session, principal, context
        self.bid, self.code_version, self.clock = context.business_id, code_version, clock
        self.trust = trust if trust is not None else TrustStore()
        if type(self.trust) is not TrustStore:
            raise TypeError('TrustStore privado requerido.')
        conn = session.borrowed_connection
        if session.dialect == 'sqlite':
            require(conn.raw.in_transaction, Failure.INVALID)
        else:
            level = session.execute("SELECT current_setting('transaction_isolation') AS level").fetchone()['level']
            require(level in ('repeatable read', 'serializable'), Failure.INVALID)
        self._key, self._issued = secrets.token_bytes(32), {}

    def current(self):
        try:
            return self._current()
        except (StateError, ConflictError, AccessDenied, KeyError, TypeError) as exc:
            raise VerificationError(Failure.BLOCKED) from exc

    def _current(self):
        require(schema_version(self.s.borrowed_connection) == 79)
        ev = FinancialReadinessEvaluator(self.s, self.bid)
        business = ev._permission(self.principal, activation_verification=True)
        assert_open(self.s, self.bid)
        closure, edges = self.context.profile.closure(fiscal_cancel_required=bool(business['verifactu_enabled']))
        require(not {'bank_transaction.import', 'bank_transaction.match'} & {c.value for c in closure})
        return dict(context=self.context.value(), capabilities=[c.value for c in closure], dependencies=edges,
                    configuration_hash=ev._configuration(business), sources=ev._sources(),
                    inventory=source_inventory(self.s, self.bid), privacy=readiness_evidence(self.s, self.bid),
                    privacy_refs=self._privacy_refs(), code_version=self.code_version,
                    flags={f:bool(getattr(config, f)) for f in FLAGS},
                    actor=dict(user_id=self.principal.user_id, session_version=self.principal.session_version))

    def _privacy_refs(self):
        refs = {}
        for t in (POLICIES, EXPORTS):
            row = self.s.execute('SELECT evidence_uuid,content_hash FROM ' + t + ' WHERE business_id=? ORDER BY created_at DESC,evidence_uuid DESC LIMIT 1', (self.bid,)).fetchone()
            refs[t] = dict(uuid=str(row['evidence_uuid']), content_hash=row['content_hash']) if row else None
        return refs

    def _principal(self, value):
        actor(value)
        PrivacyRepository(self.s, self.bid).principal(Principal(value['user_id'], value['session_version']))

    def verify(self, verifier, *, envelope=None, signature=None):
        """Dispatch cerrado; cada tipo ejecuta un algoritmo específico, nunca bool."""
        v, now = V(verifier), self.clock()
        current = self.current()
        context_hash = digest(current)
        if v in SYSTEM:
            require(envelope is None and signature is None, Failure.INVALID)
            metadata = None
        else:
            require(envelope is not None, Failure.MISSING)
            metadata = self.trust.authenticate(envelope, signature, v, context_hash, self.context, now)
            self._principal(envelope['actor'])
        try:
            proof = getattr(self, '_verify_' + v.value.lower())(metadata, current, now)
        except (StateError, ConflictError, AccessDenied, KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, VerificationError):
                raise
            raise VerificationError(Failure.BLOCKED) from exc
        expires = now + timedelta(seconds=min(300, CATALOG[v].ttl_seconds))
        if envelope:
            expires = min(expires, timestamp(envelope['expires_at']))
        value = dict(version=1, verifier=v.value, evidence_type=CATALOG[v].evidence_type.value,
                     business_id=self.bid, profile_hash=self.context.profile.content_hash,
                     cohort=self.context.cohort.value, context_hash=context_hash,
                     proof=proof, source_receipt_hash=digest(envelope) if envelope else None,
                     source_actor=envelope['actor'] if envelope else None,
                     created_at=instant(now), expires_at=instant(expires))
        obj = _sealed(value, self._key)
        self._issued[obj.content_hash] = (canonical(envelope) if envelope else None, signature)
        return obj

    def recheck(self, obj):
        _check_seal(obj, self._key)
        value = obj.body
        require(value['business_id'] == self.bid and value['profile_hash'] == self.context.profile.content_hash, Failure.SCOPE)
        require(value['cohort'] == self.context.cohort, Failure.SYNTHETIC)
        require(timestamp(value['created_at']) <= self.clock() < timestamp(value['expires_at']), Failure.STALE)
        require(value['context_hash'] == digest(self.current()), Failure.CONTEXT)
        source = self._issued.get(obj.content_hash)
        require(source is not None, Failure.AUTHORITY)
        old, signature = source
        new = self.verify(value['verifier'], envelope=json.loads(old) if old else None, signature=signature)
        require(new.body['proof'] == value['proof'], Failure.CONTEXT)
        return value

    def _readiness(self, now):
        proof = verify_readiness(self.s, self.bid, self.principal, self.context.evaluation_uuid, now=now, locking=False)
        require(proof['profile'] == self.context.profile.value(), Failure.SCOPE)
        require(proof['evaluation']['context']['code_version'] == self.code_version == config.RELEASE_ID)
        return proof

    def _verify_readiness(self, metadata, current, now):
        return self._readiness(now)

    def _verify_history(self, metadata, current, now):
        proof = self._readiness(now)
        h = proof['history']
        reference = HistoryContext(*(h[k] for k in ('epoch_uuid', 'manifest_uuid', 'batch_uuid', 'reconciliation_uuid')))
        checked, reasons = FinancialReadinessEvaluator(self.s, self.bid)._history(reference)
        require(not reasons)
        from noesis.financial_antecedents.proofs import ProofChecker
        checker = ProofChecker(self.s, self.bid)
        events = []
        for row in self.s.borrowed_connection.execute_exact('SELECT * FROM economic_events WHERE business_id=? ORDER BY event_uuid', (self.bid,)).fetchall():
            p = checker.check(row)
            require(p['quality'] == 'verified_fact')  # Unknown no se promueve.
            events.append(p['hash'])
        return dict(history=checked, event_proofs=events)

    def _verify_privacy(self, metadata, current, now):
        require(current['privacy']['privacy_ready'])
        return current['privacy']

    def _verify_export(self, metadata, current, now):
        require(current['privacy']['export_ready'])
        ref = current['privacy_refs'][EXPORTS]
        PrivacyRepository(self.s, self.bid).body(EXPORTS, ref['uuid'])
        return ref

    def _verify_legal_policy(self, m, current, now):
        closed(m, ('policy_uuid', 'policy_hash', 'approval_actor', 'approval_at', 'policy_version', 'review_uuid'))
        identifier(m['review_uuid'])
        fingerprint(m['policy_hash'])
        self._principal(m['approval_actor'])
        ref = current['privacy_refs'][POLICIES]
        require(ref is not None and ref['uuid'] == identifier(m['policy_uuid']))
        row = PrivacyRepository(self.s, self.bid).load(POLICIES, ref['uuid'])
        body = PrivacyRepository(self.s, self.bid).body(POLICIES, ref['uuid'])
        require(current['privacy']['privacy_ready'] and body['policy']['status'] == 'approved_for_operation')
        require(m['policy_hash'] == digest(body['policy']) == body['approved_hash'])
        require(m['policy_version'] == body['policy']['version'] and type(m['policy_version']) is int)
        require(m['approval_actor'] == dict(user_id=body['approved_by'], session_version=body['approval_session_version']))
        require(timestamp(m['approval_at']) == timestamp(str(row['created_at'])) and timestamp(m['approval_at']) <= now)
        return m

    def _verify_pilot_business(self, m, current, now):
        closed(m, ('selection_uuid', 'business_id', 'criterion'))
        identifier(m['selection_uuid'])
        require(type(m['business_id']) is int and m['business_id'] == self.bid and m['criterion'] == 'EMPTY', Failure.SCOPE)
        counts = {}
        for table in ('financial_operations', 'financial_authorizations', 'economic_events', ATTEMPTS, RESULTS,
                      'invoice_cancellation_records', 'financial_closure_authorizations', 'financial_closure_receipts'):
            counts[table] = self.s.execute('SELECT COUNT(*) AS n FROM ' + table + ' WHERE business_id=?', (self.bid,)).fetchone()['n']
        ambiguity = self.s.execute("SELECT COUNT(*) AS n FROM financial_history_items WHERE business_id=? AND (classification IN ('C','D') OR disposition='pending_incidence' OR unresolved_dependency_canonical<>'[]')", (self.bid,)).fetchone()['n']
        require(current['sources']['empty'] and not any(counts.values()) and not ambiguity)
        return dict(selection=m, criterion='EMPTY', sources=current['sources'], counts=counts, historical_ambiguity=ambiguity)

    def _verify_pilot_profile(self, m, current, now):
        closed(m, ('selection_uuid', 'profile', 'profile_hash', 'capabilities', 'dependencies'))
        identifier(m['selection_uuid'])
        require(m['profile'] == self.context.profile.value() and m['profile_hash'] == self.context.profile.content_hash, Failure.SCOPE)
        require(m['capabilities'] == current['capabilities'] and m['dependencies'] == current['dependencies'], Failure.SCOPE)
        from noesis.financial_activation.capabilities import specification
        for c in current['capabilities']:
            specification(c)
        return m

    def _verify_provider_attestation(self, m, current, now):
        proofs = {}
        from noesis.financial_activation.contracts import Capability
        for text in current['capabilities']:
            c = Capability(text)
            if requirement(c) is None:
                continue
            business = FinancialReadinessEvaluator(self.s, self.bid)._permission(self.principal, activation_verification=True)
            if text == 'provider.aeat_dispatch' and not business['verifactu_enabled']:
                continue
            row = self.s.execute('SELECT evidence_uuid FROM ' + ATTESTATIONS + ' WHERE business_id=? AND capability=? ORDER BY created_at DESC,evidence_uuid DESC LIMIT 1', (self.bid, text)).fetchone()
            require(row is not None, Failure.MISSING)
            uid = str(row['evidence_uuid'])
            proof = verify_attestation(self.s, self.bid, uid, text, environment=Environment.PRODUCTION, code_version=self.code_version, now=now)
            body = ProviderRepository(self.s, self.bid).load(ATTESTATIONS, uid)
            require(body['level'] == 'production_config_verified')
            require(not body['evidence']['synthetic'] or self.context.cohort == Cohort.SYNTHETIC, Failure.SYNTHETIC)
            proofs[text] = proof
        return dict(requirements=proofs, environment=Environment.PRODUCTION.value)

    def _backup(self, m, now):
        closed(m, ('backup_uuid', 'created_at', 'content_hash', 'encryption', 'access_verification_uuid',
                   'custodian', 'storage_class', 'location_class', 'scope', 'business_id', 'system_uuid'))
        for k in ('backup_uuid', 'access_verification_uuid', 'system_uuid'):
            identifier(m[k])
        fingerprint(m['content_hash'])
        self._principal(m['custodian'])
        require(m['encryption'] == 'AT_REST_VERIFIED' and m['storage_class'] in ('PRIVATE_IMMUTABLE', 'PRIVATE_OFFLINE')
                and m['location_class'] in ('ISOLATED_VAULT', 'OFFLINE_CUSTODY')
                and m['scope'] == 'business_and_system' and type(m['business_id']) is int and m['business_id'] == self.bid)
        require(0 <= (now-timestamp(m['created_at'])).total_seconds() <= 86400, Failure.STALE)
        return m

    def _verify_backup(self, m, current, now):
        return self._backup(m, now)

    def _verify_restore(self, m, current, now):
        closed(m, ('drill_uuid', 'backup', 'environment_uuid', 'isolation', 'schema_version', 'result',
                   'integrity_expected_hash', 'integrity_actual_hash', 'E_registry_hash', 'E_replayed_hash',
                   'completed_at', 'operator', 'custodian'))
        self._backup(m['backup'], now)
        for k in ('drill_uuid', 'environment_uuid'):
            identifier(m[k])
        for k in ('integrity_expected_hash', 'integrity_actual_hash', 'E_registry_hash', 'E_replayed_hash'):
            fingerprint(m[k])
        self._principal(m['operator'])
        self._principal(m['custodian'])
        require(m['custodian'] == m['backup']['custodian'] and m['isolation'] == 'OUTBOUND_DENIED'
                and type(m['schema_version']) is int and m['schema_version'] == 79 and m['result'] == 'PASS'
                and m['integrity_expected_hash'] == m['integrity_actual_hash'] and m['E_registry_hash'] == m['E_replayed_hash'])
        require(timestamp(m['backup']['created_at']) <= timestamp(m['completed_at']) <= now)
        return m

    def _verify_runtime_key(self, m, current, now):
        closed(m, ('probe_uuid', 'key_fingerprint', 'matrix'))
        identifier(m['probe_uuid'])
        fingerprint(m['key_fingerprint'])
        require(type(m['matrix']) is dict and set(m['matrix']) == set(KEY_MATRIX))
        for role, (required, forbidden) in KEY_MATRIX.items():
            p = closed(m['matrix'][role], ('accessible', 'inaccessible'))
            require(p['accessible'] == required and p['inaccessible'] == forbidden)
        return m

    def _verify_deployment_compatibility(self, m, current, now):
        closed(m, ('inventory_uuid', 'code_sha', 'schema_version', 'expected_replicas', 'replicas', 'runtime_keys'))
        identifier(m['inventory_uuid'])
        require(sha(m['code_sha']) == self.context.code_sha and type(m['schema_version']) is int and m['schema_version'] == 79)
        require(type(m['expected_replicas']) is list and type(m['replicas']) is list)
        expected = [identifier(x) for x in m['expected_replicas']]
        actual, roles = [], []
        for replica in m['replicas']:
            closed(replica, ('replica_uuid', 'role', 'code_sha', 'schema_version', 'flags', 'database_role'))
            actual.append(identifier(replica['replica_uuid']))
            roles.append(replica['role'])
            require(replica['role'] in ('web_runtime', 'financial_worker', 'scheduler'))
            require(replica['code_sha'] == m['code_sha'] and type(replica['schema_version']) is int and replica['schema_version'] == 79)
            require(replica['database_role'] == 'RESTRICTED_RUNTIME' and replica['flags'] == dict.fromkeys(FLAGS, False)
                    and all(type(x) is bool for x in replica['flags'].values()))
        require(sorted(actual) == sorted(expected) and len(set(actual)) == len(actual)
                and set(roles) == {'web_runtime', 'financial_worker', 'scheduler'})
        self._verify_runtime_key(m['runtime_keys'], current, now)
        require(not any(current['flags'].values()))
        return m

    def _verify_operators(self, m, current, now):
        closed(m, ('assignment_uuid', 'roles'))
        identifier(m['assignment_uuid'])
        require(type(m['roles']) is dict and set(m['roles']) == {o.value for o in Owner})
        for a in m['roles'].values():
            self._principal(a)
        require(m['roles'][Owner.PRIMARY]['user_id'] != m['roles'][Owner.SECONDARY]['user_id'])
        return m

    def _verify_backup_custodian(self, m, current, now):
        closed(m, ('assignment_uuid', 'custodian', 'backup'))
        identifier(m['assignment_uuid'])
        self._principal(m['custodian'])
        self._backup(m['backup'], now)
        require(m['custodian'] == m['backup']['custodian'])
        return m

    def _runbook(self, m, scenario, now):
        closed(m, ('rehearsal_uuid', 'scenario', 'operator', 'completed_at', 'result', 'failures', 'runbook_version', 'runbook_hash', 'accepted_hash'))
        identifier(m['rehearsal_uuid'])
        fingerprint(m['runbook_hash'])
        fingerprint(m['accepted_hash'])
        self._principal(m['operator'])
        require(m['scenario'] == scenario and m['result'] == 'PASS' and m['failures'] == []
                and type(m['runbook_version']) is int and m['runbook_version'] == 1 and m['accepted_hash'] == m['runbook_hash'])
        require(0 <= (now-timestamp(m['completed_at'])).total_seconds() <= 86400, Failure.STALE)
        return m

    def _verify_pause_runbook(self, m, current, now):
        return self._runbook(m, 'D_PAUSE_F_HOLD_EMAIL_META_DRAIN_COMMITTED_AEAT', now)

    def _verify_unknown_runbook(self, m, current, now):
        return self._runbook(m, 'EMAIL_META_AEAT_UNKNOWN_NO_AUTOMATIC_RETRY', now)

    def _verify_monitoring(self, m, current, now):
        closed(m, ('access_probe_uuid', 'operator', 'sections', 'backup'))
        identifier(m['access_probe_uuid'])
        self._principal(m['operator'])
        require(m['sections'] == list(MONITORING_SECTIONS))
        self._backup(m['backup'], now)
        from noesis.financial_providers.observability import read
        state = read(self.s, self.bid, Principal(**m['operator']))
        require(not state['pending_attempts'] and not state['unknown_results'] and state['privacy']['privacy_ready'])
        # No meter edad calculada en proof determinista; el estado durable sí.
        return dict(access=m, durable_state_hash=digest(current['inventory']))

    def _verify_main_integration(self, m, current, now):
        closed(m, ('integration_base_sha', 'current_main_sha', 'financial_chain_sha', 'integration_sha',
                   'base_ancestor_sha', 'chain_ancestor_sha', 'CI_run_uuid', 'CI_scope', 'CI_sha',
                   'CI_conclusion', 'failures', 'errors', 'review_uuid', 'review_result'))
        for k in ('integration_base_sha', 'current_main_sha', 'financial_chain_sha', 'integration_sha', 'base_ancestor_sha', 'chain_ancestor_sha', 'CI_sha'):
            sha(m[k])
        identifier(m['CI_run_uuid'])
        identifier(m['review_uuid'])
        require(m['integration_base_sha'] == m['current_main_sha'] == m['base_ancestor_sha'] == self.context.integration_base_sha
                and m['financial_chain_sha'] == m['chain_ancestor_sha'] == self.context.financial_chain_sha
                and m['CI_sha'] == m['integration_sha'] == self.context.code_sha and m['CI_scope'] == 'COMPLETE_A_G'
                and m['CI_conclusion'] == 'SUCCESS' and m['review_result'] == 'ACCEPTED'
                and type(m['failures']) is int and m['failures'] == 0 and type(m['errors']) is int and m['errors'] == 0)
        return m

    def _verify_production_activation(self, m, current, now):
        # G no implementa el arco productivo. Jamás retirar el guard D por evidencia.
        require(self.context.cohort == Cohort.SYNTHETIC and not config.IS_PRODUCTION, Failure.PRODUCTION)
        return dict(production_guard='PRESERVED_BLOCKED', scope='SYNTHETIC_CONTRACT_ONLY', activation_authorized=False)

    def _verify_resume_continuity(self, m, current, now):
        closed(m, ('rehearsal_uuid', 'schema_version', 'completed_at', 'operator', 'cases', 'original_a_hash',
                   'previous_generation', 'new_generation', 'original_handoff_hash', 'pause_hash', 'recovery_hash'))
        identifier(m['rehearsal_uuid'])
        self._principal(m['operator'])
        for k in ('original_a_hash', 'original_handoff_hash', 'pause_hash', 'recovery_hash'):
            fingerprint(m[k])
        require(type(m['schema_version']) is int and m['schema_version'] == 79 and type(m['previous_generation']) is int
                and type(m['new_generation']) is int and m['previous_generation'] >= 1
                and m['new_generation'] == m['previous_generation'] + 1)
        require(type(m['cases']) is dict and set(m['cases']) == set(RECOVERY_CASES) and all(x == 'PASS' for x in m['cases'].values()))
        require(0 <= (now-timestamp(m['completed_at'])).total_seconds() <= 86400, Failure.STALE)
        return m
