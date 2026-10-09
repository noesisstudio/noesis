"""Contratos F cerrados: ninguna prueba equivale a autorización financiera."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import re

from noesis.financial_activation.contracts import canonical, digest, instant, tenant
from noesis.financial_operations.contracts import uuid_text, positive_id


class Provider(StrEnum):
    AEAT = "AEAT_VERIFACTU"
    META = "META_WHATSAPP"
    EMAIL = "EMAIL_DELIVERY"


class Implementation(StrEnum):
    AEAT = "aeat_soap"
    META = "meta_graph"
    BREVO = "brevo"
    SMTP = "smtp"
    GMAIL = "gmail"


class Environment(StrEnum):
    LOCAL = "local"
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class Level(StrEnum):
    LOCAL = "local_verified"
    SANDBOX = "sandbox_verified"
    PRODUCTION_CONFIG = "production_config_verified"
    OBSERVED = "production_observed"


class Result(StrEnum):
    PASS = "PASS"
    BLOCKED = "BLOCKED"


class Permission(StrEnum):
    PREFLIGHT = "financial.providers.preflight"


class Reason(StrEnum):
    READINESS_NOT_FULL = "READINESS_NOT_FULL"
    READINESS_STALE = "READINESS_STALE"
    PRIVACY_NOT_READY = "PRIVACY_NOT_READY"
    EXPORT_NOT_READY = "EXPORT_NOT_READY"
    ATTESTATION_MISSING = "PROVIDER_ATTESTATION_MISSING"
    ATTESTATION_STALE = "PROVIDER_ATTESTATION_STALE"
    ENVIRONMENT_MISMATCH = "PROVIDER_ENVIRONMENT_MISMATCH"
    CONFIG_DRIFT = "PROVIDER_CONFIG_DRIFT"
    LEVEL_INSUFFICIENT = "PROVIDER_LEVEL_INSUFFICIENT"
    PENDING_OPERATION = "PENDING_OPERATION"
    UNKNOWN_RESULT = "UNCERTAIN_EXTERNAL_RESULT"
    BANK_UNVALIDATED = "BANK_CAPABILITY_UNVALIDATED"
    HISTORY_INVALID = "HISTORY_INVALID"
    VOLUME = "VOLUME_OUTSIDE_POLICY"
    CLOSING = "ACCOUNT_CLOSING"
    CLOSED = "ACCOUNT_CLOSED"
    SESSION_STALE = "SESSION_STALE"
    CONFIGURATION_CHANGED = "CONFIGURATION_CHANGED"
    DEPENDENCY_BLOCKED = "CAPABILITY_DEPENDENCY_BLOCKED"
    CONFIG_INVALID = "PROVIDER_CONFIGURATION_INVALID"
    SAFE_CHECK_UNIMPLEMENTED = "SAFE_CHECK_UNIMPLEMENTED"
    NETWORK_NOT_AUTHORIZED = "NETWORK_NOT_AUTHORIZED"
    OBSERVATION_REQUIRES_RESULT = "OBSERVATION_REQUIRES_REAL_RESULT"
    UNBOUND = "FINANCIAL_OUTBOX_UNBOUND"
    STALE_GENERATION = "STALE_GENERATION"
    PAUSED = "HOLD_DISPATCH"
    FENCE = "HISTORY_FENCE_ACTIVE"
    INTEGRITY = "CONTINUITY_MISMATCH"


class DispatchResult(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED_TERMINAL"
    UNKNOWN = "UNKNOWN_EXTERNAL_RESULT"
    ABORTED = "ABORTED_BEFORE_IO"


class DispatchPolicy(StrEnum):
    DRAIN = "DRAIN_COMMITTED"
    HOLD = "HOLD_DISPATCH"


class Observation(StrEnum):
    PREFLIGHT = "provider_preflight"
    ATTEMPT = "provider_attempt"
    UNKNOWN = "provider_unknown_result"
    ERROR = "provider_error"
    ACTIVATION_BLOCKED = "activation_blocked"
    CONTINUITY = "continuity_mismatch"
    STALE = "stale_generation"
    PAUSE = "pause_required"
    EXPORT = "export_failure"


def clock():
    return datetime.now(timezone.utc)


def stamp(value):
    return instant(value if isinstance(value, datetime) else datetime.fromisoformat(value))


def hash_text(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Huella SHA-256/HMAC canónica requerida.")
    return value


def closed(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError("Contrato F cerrado requerido.")
    canonical(value)
    if type(value["version"]) is not int or value["version"] != 1:
        raise ValueError("Versión F desconocida.")
    tenant(value["business_id"])
    return value


def requirement(capability):
    """La única spec de C declara la dependencia; desconocidos fallan cerrados."""
    from noesis.financial_activation.capabilities import specification
    value = specification(capability).provider_requirement
    return Provider(value) if value is not None else None


def sufficient(level, environment):
    level, environment = Level(level), Environment(environment)
    return ((environment == Environment.PRODUCTION and level in (Level.PRODUCTION_CONFIG, Level.OBSERVED))
            or (environment == Environment.SANDBOX and level == Level.SANDBOX)
            or (environment == Environment.LOCAL and level == Level.LOCAL))


ATTESTATION_FIELDS = (
    "version", "business_id", "attestation_uuid", "provider", "implementation", "capability",
    "environment", "level", "configuration_fingerprint", "credential_fingerprint", "checker_version",
    "code_version", "schema_version", "actor_user_id", "actor_session_version", "checked_at", "expires_at",
    "result", "reasons", "evidence", "source_attempt_uuid",
)


@dataclass(frozen=True)
class ProviderAttestation:
    body_canonical: str

    @classmethod
    def create(cls, body):
        closed(body, ATTESTATION_FIELDS)
        uuid_text(body["attestation_uuid"])
        provider = Provider(body["provider"])
        impl = Implementation(body["implementation"])
        if impl not in {Provider.AEAT: (Implementation.AEAT,), Provider.META: (Implementation.META,),
                        Provider.EMAIL: (Implementation.BREVO, Implementation.SMTP, Implementation.GMAIL)}[provider]:
            raise ValueError("Implementación no pertenece al provider.")
        if requirement(body["capability"]) != provider:
            raise ValueError("Capability/provider incompatibles.")
        env, level = Environment(body["environment"]), Level(body["level"])
        if level == Level.OBSERVED:
            if env != Environment.PRODUCTION or body["source_attempt_uuid"] is None:
                raise ValueError(Reason.OBSERVATION_REQUIRES_RESULT)
            uuid_text(body["source_attempt_uuid"])
        elif body["source_attempt_uuid"] is not None:
            raise ValueError("Preflight no observa una operación externa.")
        if body['result'] == Result.PASS and (level == Level.SANDBOX and env != Environment.SANDBOX
                or level == Level.PRODUCTION_CONFIG and env != Environment.PRODUCTION):
            raise ValueError("Entorno incompatible con nivel.")
        for field in ("configuration_fingerprint", "credential_fingerprint"):
            hash_text(body[field])
        if body["checker_version"] != "financial_provider_checker_v1" or type(body["schema_version"]) is not int or body["schema_version"] != 79:
            raise ValueError("Checker/schema F desconocido.")
        if not isinstance(body["code_version"], str) or not 1 <= len(body["code_version"]) <= 128:
            raise ValueError("Código identificable requerido.")
        positive_id(body["actor_user_id"])
        if type(body["actor_session_version"]) is not int or body["actor_session_version"] < 0:
            raise ValueError("Sesión actual requerida.")
        start, end = datetime.fromisoformat(stamp(body["checked_at"])), datetime.fromisoformat(stamp(body["expires_at"]))
        if not 0 < (end - start).total_seconds() <= 300:
            raise ValueError("TTL operativo máximo cinco minutos.")
        reasons = [Reason(r).value for r in body["reasons"]]
        if reasons != sorted(set(reasons)) or (Result(body["result"]) == Result.PASS) != (not reasons):
            raise ValueError("Resultado/motivos incoherentes.")
        evidence = body["evidence"]
        if set(evidence) != {"configuration_valid", "safe_check", "certificate_sha256", "check_reference_hash", "synthetic"}:
            raise ValueError("Evidencia F cerrada sin respuestas libres.")
        if type(evidence["configuration_valid"]) is not bool or type(evidence["synthetic"]) is not bool:
            raise ValueError("Evidencia booleana requerida.")
        if evidence["safe_check"] not in ("not_requested", "unavailable", "verified_readonly", "durable_result"):
            raise ValueError("Check desconocido.")
        for name in ("certificate_sha256", "check_reference_hash"):
            if evidence[name] is not None:
                hash_text(evidence[name])
        if body["result"] == Result.PASS:
            if not evidence["configuration_valid"]:
                raise ValueError("Configuración inválida no puede pasar.")
            if level in (Level.PRODUCTION_CONFIG, Level.SANDBOX) and evidence["safe_check"] != "verified_readonly":
                raise ValueError("Check seguro concreto requerido.")
            if level == Level.OBSERVED and (evidence["safe_check"] != "durable_result" or evidence["synthetic"]):
                raise ValueError(Reason.OBSERVATION_REQUIRES_RESULT)
        return cls(canonical(body))

    @property
    def body(self):
        import json
        return json.loads(self.body_canonical)

    @property
    def content_hash(self):
        return digest(self.body)


@dataclass(frozen=True)
class OperationalPolicy:
    version: int = 1
    history_max_items: int = 64
    gate_wait_goal_ms: int = 1000
    handoff_warning_ms: int = 2000
    handoff_review_ms: int = 5000
    readiness_ttl_seconds: int = 300
    cutoff_warning_seconds: int = 300
    cutoff_intervention_seconds: int = 900

    def __post_init__(self):
        from dataclasses import asdict
        if asdict(self) != dict(version=1, history_max_items=64, gate_wait_goal_ms=1000,
                               handoff_warning_ms=2000, handoff_review_ms=5000, readiness_ttl_seconds=300,
                               cutoff_warning_seconds=300, cutoff_intervention_seconds=900):
            raise ValueError("Política operativa v1 cerrada; no SLO ni política legal.")

    def value(self):
        from dataclasses import asdict
        return asdict(self)
