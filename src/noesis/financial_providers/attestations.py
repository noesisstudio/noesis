"""Preflight de provider explícito. No se ejecuta desde readiness ni workers."""

from noesis.core.persistence import schema_version
from datetime import timedelta, datetime
from uuid import uuid4
from noesis import config
from noesis.financial_operations.contracts import AccessDenied, StateError, uuid_text, Principal
from .contracts import (ProviderAttestation, Provider, Level, Environment, Result, Reason,
                        Permission, clock, instant, requirement, sufficient, digest)
from .configuration import snapshot
from .repository import ProviderRepository
from .schema import ATTESTATIONS


def safe_check(provider, implementation, environment):
    """F no tiene autorización de red: interfaces de control plane fail closed.

    Los clientes de entrega existentes no demuestran que una operación de prueba
    sea inocua. No llamarlos para obtener readiness. Una implementación futura
    debe probar un check readonly específico antes de cambiar este resultado.
    """
    return dict(verified=False, reference_hash=None, synthetic=False)


def check(session, business_id, principal, capability, *, code_version,
          attestation_uuid=None, level=Level.LOCAL, network_authorized=False,
          permission=Permission.PREFLIGHT):
    if permission != Permission.PREFLIGHT:
        raise AccessDenied("financial.providers.preflight requerido.")
    if type(network_authorized) is not bool or schema_version(session.borrowed_connection) != 79:
        raise StateError('Schema79 y autoridad de red booleana explícita requeridos.')
    repo = ProviderRepository(session, business_id)
    repo.principal(principal)
    from noesis.financial_privacy.repository import assert_open
    assert_open(session, business_id)
    level = Level(level)
    if level == Level.OBSERVED:
        raise StateError(Reason.OBSERVATION_REQUIRES_RESULT)
    provider = requirement(capability)
    if provider is None:
        raise ValueError("Esta capability no requiere provider.")
    current = snapshot(session, business_id, provider)
    now = clock()
    reasons, proof = [], dict(verified=False, reference_hash=None, synthetic=False)
    if not current["configuration_valid"]:
        reasons.append(Reason.CONFIG_INVALID.value)
    if level in (Level.PRODUCTION_CONFIG, Level.SANDBOX):
        if not network_authorized:
            reasons.append(Reason.NETWORK_NOT_AUTHORIZED.value)
        else:
            # Autorización específica, nunca permiso heredado de IA/autorizar dinero.
            # La implementación actual bloquea incluso con permiso explícito.
            proof = safe_check(provider, current["implementation"], current["environment"])
            if not proof["verified"]:
                reasons.append(Reason.SAFE_CHECK_UNIMPLEMENTED.value)
        expected = Environment.PRODUCTION if level == Level.PRODUCTION_CONFIG else Environment.SANDBOX
        if current["environment"] != expected:
            reasons.append(Reason.ENVIRONMENT_MISMATCH.value)
    uid = uuid_text(attestation_uuid or uuid4())
    body = dict(version=1, business_id=business_id, attestation_uuid=uid, provider=provider.value,
                implementation=current["implementation"], capability=capability.value if hasattr(capability, "value") else capability,
                environment=current["environment"], level=level.value,
                configuration_fingerprint=current["configuration_fingerprint"], credential_fingerprint=current["credential_fingerprint"],
                checker_version="financial_provider_checker_v1", code_version=code_version, schema_version=79,
                actor_user_id=principal.user_id, actor_session_version=principal.session_version,
                checked_at=instant(now), expires_at=instant(now + timedelta(minutes=5)),
                result=Result.BLOCKED.value if reasons else Result.PASS.value, reasons=sorted(set(reasons)),
                evidence=dict(configuration_valid=current["configuration_valid"],
                              safe_check="verified_readonly" if proof["verified"] else "not_requested" if level == Level.LOCAL else "unavailable",
                              certificate_sha256=current["certificate_sha256"], check_reference_hash=proof["reference_hash"], synthetic=proof["synthetic"]),
                source_attempt_uuid=None)
    attestation = ProviderAttestation.create(body)
    columns = {k: body[k] for k in ("provider", "implementation", "capability", "environment", "level", "configuration_fingerprint", "credential_fingerprint", "expires_at", "result", "source_attempt_uuid")}
    repo.append(ATTESTATIONS, uid, principal, attestation.body, now, **columns)
    return attestation.body


def verify(session, business_id, attestation_uuid, capability, *, environment=Environment.PRODUCTION,
           code_version=None, now=None):
    repo = ProviderRepository(session, business_id)
    body = repo.load(ATTESTATIONS, attestation_uuid)
    if body is None:
        raise StateError(Reason.ATTESTATION_MISSING)
    ProviderAttestation.create(body)
    try:
        repo.principal(Principal(body['actor_user_id'],body['actor_session_version']))
    except AccessDenied as exc:
        raise StateError(Reason.SESSION_STALE) from exc
    if body["provider"] != requirement(capability) or body["capability"] != capability:
        raise StateError(Reason.ENVIRONMENT_MISMATCH)
    if body["result"] != Result.PASS or (now or clock()) >= datetime.fromisoformat(body["expires_at"]):
        raise StateError(Reason.ATTESTATION_STALE)
    if body["environment"] != Environment(environment):
        raise StateError(Reason.ENVIRONMENT_MISMATCH)
    if not sufficient(body["level"], environment):
        raise StateError(Reason.LEVEL_INSUFFICIENT)
    if code_version is not None and body["code_version"] != code_version:
        raise StateError(Reason.CONFIG_DRIFT)
    if config.IS_PRODUCTION and body["evidence"]["synthetic"]:
        raise StateError(Reason.LEVEL_INSUFFICIENT)
    current = snapshot(session, business_id, Provider(body["provider"]))
    if (not current["configuration_valid"] or any(body[k] != current[k] for k in
            ("provider", "implementation", "environment", "configuration_fingerprint", "credential_fingerprint"))):
        raise StateError(Reason.CONFIG_DRIFT)
    return dict(attestation_uuid=body["attestation_uuid"], content_hash=digest(body),
                configuration_fingerprint=body["configuration_fingerprint"], credential_fingerprint=body["credential_fingerprint"])


def readiness_evidence(session, business_id, capabilities, *, code_version):
    """Sólo verifica recibos existentes. No renovar, escribir ni hacer network."""
    result = {}
    for capability in capabilities:
        if requirement(capability) is None:
            continue
        rows = session.execute(f"SELECT evidence_uuid FROM {ATTESTATIONS} WHERE business_id=? AND capability=? ORDER BY created_at DESC,evidence_uuid DESC LIMIT 1",
                               (business_id, capability.value)).fetchall()
        if rows:
            try:
                result[capability.value] = verify(session, business_id, str(rows[0]["evidence_uuid"]), capability,
                                                   code_version=code_version)
            except (StateError, ValueError):
                result[capability.value] = None
        else:
            result[capability.value] = None
    return result


def record_observed(session, business_id, principal, attempt_uuid):
    """Sólo derivación de resultado real durable. Ninguna entrada preflight manual."""
    from .schema import ATTEMPTS, RESULTS, STARTS
    repo = ProviderRepository(session, business_id)
    attempt = repo.load(ATTEMPTS, attempt_uuid)
    row = session.execute(f"SELECT evidence_uuid FROM {RESULTS} WHERE business_id=? AND attempt_uuid=? AND result='SUCCEEDED'", (business_id, uuid_text(attempt_uuid))).fetchone()
    if not attempt or not row:
        raise StateError(Reason.OBSERVATION_REQUIRES_RESULT)
    result = repo.load(RESULTS, str(row['evidence_uuid']))
    source = repo.load(ATTESTATIONS, attempt['attestation_uuid'])
    if (not result['real_io'] or source['evidence']['synthetic'] or source['environment'] != Environment.PRODUCTION
            or not session.execute(f"SELECT 1 FROM {STARTS} WHERE business_id=? AND attempt_uuid=?", (business_id, uuid_text(attempt_uuid))).fetchone()):
        raise StateError(Reason.OBSERVATION_REQUIRES_RESULT)
    verify(session, business_id, source['attestation_uuid'], source['capability'])
    now = clock()
    body = dict(source, attestation_uuid=str(uuid4()), level=Level.OBSERVED.value, source_attempt_uuid=uuid_text(attempt_uuid),
                checked_at=instant(now), expires_at=instant(now + timedelta(minutes=5)),
                actor_user_id=principal.user_id, actor_session_version=principal.session_version,
                evidence=dict(source['evidence'], safe_check='durable_result', check_reference_hash=digest(result)))
    value = ProviderAttestation.create(body)
    columns = {k: body[k] for k in ("provider", "implementation", "capability", "environment", "level", "configuration_fingerprint", "credential_fingerprint", "expires_at", "result", "source_attempt_uuid")}
    return repo.append(ATTESTATIONS, body['attestation_uuid'], principal, value.body, now, **columns)
