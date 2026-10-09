"""Catálogo cerrado de evidencia durable F, compartido por writes y replay."""

from .contracts import (ProviderAttestation, closed, hash_text, stamp, positive_id, uuid_text,
                        Result, Reason, Provider, Observation, DispatchResult, requirement, Environment)
from .schema import ATTESTATIONS, RUNS, BINDINGS, OUTBOX_BINDINGS, ATTEMPTS, STARTS, RESULTS, OBSERVATIONS, OUTBOXES


def validate(table, value):
    if table == ATTESTATIONS:
        ProviderAttestation.create(value)
        return
    fields = {
        RUNS: ('preflight_uuid', 'evaluation_uuid', 'context', 'context_hash', 'result', 'reasons', 'created_at', 'expires_at'),
        BINDINGS: ('request_uuid', 'preflight_uuid', 'preflight_hash'),
        OUTBOX_BINDINGS: ('binding_uuid', 'outbox_type', 'outbox_id', 'operation_uuid', 'activation_generation', 'capability', 'provider', 'request_fingerprint'),
        ATTEMPTS: ('attempt_uuid', 'claimed_at', 'attestation_hash', 'binding_uuid', 'attestation_uuid', 'operation_uuid', 'activation_generation', 'capability', 'provider', 'request_fingerprint', 'idempotency_fingerprint'),
        STARTS: ('start_uuid', 'attempt_uuid', 'started_at'),
        RESULTS: ('result_uuid', 'attempt_uuid', 'result', 'category', 'provider_reference_hash', 'status_code', 'completed_at', 'real_io'),
        OBSERVATIONS: ('observation_uuid', 'kind', 'reference_hash', 'reason'),
    }[table]
    closed(value, ('version', 'business_id') + fields)
    for name, item in value.items():
        if name.endswith('_uuid'):
            uuid_text(item)
        if name.endswith(('_hash', '_fingerprint')) and item is not None:
            hash_text(item)
        if name.endswith('_at'):
            stamp(item)
    if table in (ATTEMPTS, OUTBOX_BINDINGS):
        positive_id(value['activation_generation'])
        if requirement(value['capability']) != Provider(value['provider']):
            raise ValueError('Capability/provider distintos.')
    if table == OUTBOX_BINDINGS:
        positive_id(value['outbox_id'])
        if value['outbox_type'] not in OUTBOXES:
            raise ValueError('Outbox desconocida.')
        expected = 'AEAT_VERIFACTU' if value['outbox_type'].startswith('verifactu') else 'EMAIL_DELIVERY' if value['outbox_type'] == 'email_outbox' else 'META_WHATSAPP'
        if value['provider'] != expected:
            raise ValueError('Outbox/provider distintos.')
    if table == RESULTS:
        DispatchResult(value['result'])
        if value['category'] not in ('success', 'accepted_with_errors', 'rejected', 'timeout', 'duplicate_confirmed', 'crash_after_start', 'guard_before_io'):
            raise ValueError('Categoría de resultado desconocida.')
        if type(value['real_io']) is not bool or value['status_code'] is not None and (type(value['status_code']) is not int or not 100 <= value['status_code'] <= 599):
            raise ValueError('Metadata de resultado inválida.')
        expected = ('SUCCEEDED' if value['category'] in ('success','accepted_with_errors','duplicate_confirmed') else 'FAILED_TERMINAL' if value['category']=='rejected' else 'ABORTED_BEFORE_IO' if value['category']=='guard_before_io' else 'UNKNOWN_EXTERNAL_RESULT')
        if value['result'] != expected:
            raise ValueError('Resultado/categoría incompatibles.')
    if table == OBSERVATIONS:
        Observation(value['kind'])
        if value['reason'] is not None:
            Reason(value['reason'])
    if table == RUNS:
        from .contracts import digest
        reasons = [Reason(r).value for r in value['reasons']]
        if reasons != sorted(set(reasons)) or (Result(value['result']) == Result.PASS) != (not reasons) or digest(value['context']) != value['context_hash']:
            raise ValueError('Preflight incoherente.')
        context = value['context']
        expected = {'evaluation_uuid', 'evaluation_hash', 'profile', 'profile_hash', 'capabilities', 'dependencies', 'requirements', 'attestations', 'environment', 'privacy', 'privacy_refs', 'history_hash', 'source_hash', 'configuration_hash', 'volume', 'uncertain_attempts_hash', 'control', 'policy_version', 'operational_limits', 'code_version', 'schema_version', 'actor_user_id', 'actor_session_version', 'permission', 'action', 'recovery'}
        if context.get('action') == 'resume' and 'recovery_readiness' in context:
            expected.add('recovery_readiness')
            proof = context['recovery_readiness']
            if proof is not None:
                from noesis.financial_activation.recovery_readiness import validate_proof
                validate_proof(proof)
                if (proof['business_id'] != value['business_id'] or proof['evaluation_uuid'] != value['evaluation_uuid']
                        or proof['evaluation_hash'] != context['evaluation_hash']
                        or proof['profile_hash'] != context['profile_hash'] or proof['capabilities'] != context['capabilities']
                        or proof['actor_user_id'] != context['actor_user_id']
                          or proof['actor_session_version'] != context['actor_session_version']
                          or proof['previous_generation'] != context['control']['activation_generation']
                          or proof['configuration_hash'] != context['configuration_hash']
                          or proof['source_hash'] != context['source_hash']
                          or proof['code_version'] != context['code_version']
                          or not context['recovery']
                          or proof['pause_receipt_uuid'] != context['recovery']['pause_receipt_uuid']
                          or proof['pause_receipt_hash'] != context['recovery']['pause_receipt_hash']
                          or proof['generation_receipt_hash'] != context['recovery']['generation_receipt_hash']
                          or proof['snapshot_hash'] != digest(context['recovery']['snapshot'])):
                    raise ValueError('Continuidad/preflight distintos.')
            elif value['result'] == Result.PASS:
                raise ValueError('PASS resume requiere continuidad.')
        if set(context) != expected or context['schema_version'] != 79 or context['policy_version'] != 1 or context['action'] not in ('enable', 'resume'):
            raise ValueError('Contexto preflight cerrado requerido.')
        Environment(context['environment'])
        from noesis.financial_activation.contracts import Profile
        profile = Profile(tuple(context['profile']['capabilities']), context['profile']['profile_version'])
        if profile.content_hash != context['profile_hash']:
            raise ValueError('Perfil/hash incoherentes.')
