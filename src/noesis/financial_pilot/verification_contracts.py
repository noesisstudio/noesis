"""G-VERIFY v1. Catálogo cerrado; metadatos autenticados no sustituyen hechos BD."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from types import MappingProxyType

from noesis.financial_activation.contracts import Profile, canonical, tenant
from noesis.financial_operations.contracts import uuid_text, positive_id
from noesis.financial_providers.contracts import hash_text
from .contracts import Owner


class Verifier(StrEnum):
    LEGAL_POLICY = 'LEGAL_POLICY'
    PILOT_BUSINESS = 'PILOT_BUSINESS'
    PILOT_PROFILE = 'PILOT_PROFILE'
    READINESS = 'READINESS'
    HISTORY = 'HISTORY'
    PRIVACY = 'PRIVACY'
    EXPORT = 'EXPORT'
    PROVIDER_ATTESTATION = 'PROVIDER_ATTESTATION'
    BACKUP = 'BACKUP'
    RESTORE = 'RESTORE'
    DEPLOYMENT_COMPATIBILITY = 'DEPLOYMENT_COMPATIBILITY'
    RUNTIME_KEY = 'RUNTIME_KEY'
    OPERATORS = 'OPERATORS'
    BACKUP_CUSTODIAN = 'BACKUP_CUSTODIAN'
    PAUSE_RUNBOOK = 'PAUSE_RUNBOOK'
    UNKNOWN_RUNBOOK = 'UNKNOWN_RUNBOOK'
    MONITORING = 'MONITORING'
    MAIN_INTEGRATION = 'MAIN_INTEGRATION'
    PRODUCTION_ACTIVATION = 'PRODUCTION_ACTIVATION'
    RESUME_CONTINUITY = 'RESUME_CONTINUITY'


class EvidenceType(StrEnum):
    SYSTEM = 'SYSTEM_DERIVED'
    HUMAN = 'HUMAN_ATTESTED'
    PROVIDER = 'EXTERNAL_PROVIDER_DERIVED'
    LEGAL = 'LEGAL_REVIEW_DERIVED'
    BACKUP = 'BACKUP_DRILL_DERIVED'
    DEPLOYMENT = 'DEPLOYMENT_DERIVED'


class Cohort(StrEnum):
    REAL = 'REAL'
    SYNTHETIC = 'SYNTHETIC'


class Failure(StrEnum):
    MISSING = 'MISSING_EVIDENCE'
    INVALID = 'INVALID_EVIDENCE'
    STALE = 'STALE_EVIDENCE'
    SCOPE = 'SCOPE_MISMATCH'
    AUTHORITY = 'UNTRUSTED_AUTHORITY'
    CONTEXT = 'CONTEXT_CHANGED'
    SYNTHETIC = 'SYNTHETIC_NOT_REAL'
    BLOCKED = 'PREREQUISITE_BLOCKED'
    PRODUCTION = 'PRODUCTION_ACTIVATION_NOT_AUTHORIZED'


class VerificationError(ValueError):
    def __init__(self, reason):
        self.reason = Failure(reason)
        super().__init__(self.reason.value)


@dataclass(frozen=True, slots=True)
class Spec:
    evidence_type: EvidenceType
    authority: Owner
    source: str
    algorithm: str
    ttl_seconds: int
    real_access_required: bool
    human_confirmation_required: bool
    version: int = 1
    business_scope: str = 'exact_business_and_profile_closure'
    canonical_proof: str = 'canonical_json_v1_context_and_source_bound'
    failure_reasons: tuple = tuple(Failure)


V, T, O = Verifier, EvidenceType, Owner
CATALOG = MappingProxyType({
    V.LEGAL_POLICY: Spec(T.LEGAL, O.LEGAL, 'E_policy_and_professional_receipt', 'exact_approved_policy_human_receipt', 86400, True, True),
    V.PILOT_BUSINESS: Spec(T.HUMAN, O.HOLDER, 'A_F_scoped_sources_and_holder', 'exhaustive_empty_and_explicit_selection', 300, True, True),
    V.PILOT_PROFILE: Spec(T.HUMAN, O.HOLDER, 'A_profile_C_registry_and_holder', 'exact_profile_and_transitive_closure', 300, True, True),
    V.READINESS: Spec(T.SYSTEM, O.PRIMARY, 'A_verify_readiness', 'reuse_full_every_use', 300, True, False),
    V.HISTORY: Spec(T.SYSTEM, O.PRIMARY, 'history_certificate_and_B', 'reuse_history_and_B_no_promotion', 300, True, False),
    V.PRIVACY: Spec(T.SYSTEM, O.LEGAL, 'E_readiness', 'current_policy_and_open_account', 300, True, False),
    V.EXPORT: Spec(T.SYSTEM, O.PRIMARY, 'E_manifest', 'current_complete_tenant_snapshot', 300, True, False),
    V.PROVIDER_ATTESTATION: Spec(T.PROVIDER, O.ENGINEERING, 'F_attestations', 'production_environment_level_ttl_fingerprints', 300, True, False),
    V.BACKUP: Spec(T.BACKUP, O.BACKUP, 'authorized_backup_collector', 'encrypted_custodied_access_checked_scoped_metadata', 86400, True, True),
    V.RESTORE: Spec(T.BACKUP, O.BACKUP, 'isolated_restore_drill_collector', 'exact_backup_schema_integrity_and_E_replay', 86400, True, True),
    V.DEPLOYMENT_COMPATIBILITY: Spec(T.DEPLOYMENT, O.ENGINEERING, 'deployment_inventory_collector', 'all_replicas_workers_scheduler_code_schema_roles_flags', 300, True, True),
    V.RUNTIME_KEY: Spec(T.DEPLOYMENT, O.ENGINEERING, 'role_access_probe_collector', 'required_and_forbidden_key_access_matrix', 300, True, True),
    V.OPERATORS: Spec(T.HUMAN, O.HOLDER, 'holder_role_assignment_receipt', 'closed_roles_current_ids_sessions', 86400, True, True),
    V.BACKUP_CUSTODIAN: Spec(T.HUMAN, O.HOLDER, 'holder_custody_receipt', 'exact_backup_custodian_assignment', 86400, True, True),
    V.PAUSE_RUNBOOK: Spec(T.HUMAN, O.PRIMARY, 'pause_rehearsal_receipt', 'actual_pause_hold_drain_rehearsal', 86400, True, True),
    V.UNKNOWN_RUNBOOK: Spec(T.HUMAN, O.SECONDARY, 'unknown_rehearsal_receipt', 'all_providers_unknown_no_retry_rehearsal', 86400, True, True),
    V.MONITORING: Spec(T.HUMAN, O.PRIMARY, 'F_read_model_and_operator_receipt', 'all_required_sections_access_and_backup_freshness', 300, True, True),
    V.MAIN_INTEGRATION: Spec(T.DEPLOYMENT, O.ENGINEERING, 'CI_and_review_collector', 'current_main_ancestry_chain_full_clean_CI_review', 300, True, True),
    V.PRODUCTION_ACTIVATION: Spec(T.SYSTEM, O.ENGINEERING, 'D_production_guard', 'real_remains_blocked_synthetic_contract_only', 300, False, False),
    V.RESUME_CONTINUITY: Spec(T.HUMAN, O.ENGINEERING, 'D79_continuity_rehearsal_receipt', 'expired_A_G_plus_one_and_negative_cases', 86400, False, True),
})


def now_utc():
    return datetime.now(timezone.utc)


def timestamp(value):
    if type(value) is not str:
        raise VerificationError(Failure.INVALID)
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise VerificationError(Failure.INVALID)
    return result


def sha(value):
    if type(value) is not str or len(value) != 40 or any(c not in '0123456789abcdef' for c in value):
        raise VerificationError(Failure.INVALID)
    return value


@dataclass(frozen=True, slots=True)
class VerificationContext:
    business_id: int
    profile: Profile
    evaluation_uuid: str
    code_sha: str
    cohort: Cohort = Cohort.REAL
    financial_chain_sha: str | None = None
    integration_base_sha: str | None = None

    def __post_init__(self):
        tenant(self.business_id)
        if type(self.profile) is not Profile:
            raise TypeError('Profile A exacto requerido.')
        object.__setattr__(self, 'evaluation_uuid', uuid_text(self.evaluation_uuid))
        sha(self.code_sha)
        for value in (self.financial_chain_sha, self.integration_base_sha):
            if value is not None:
                sha(value)
        object.__setattr__(self, 'cohort', Cohort(self.cohort))

    def value(self):
        return dict(version=1, business_id=self.business_id, profile=self.profile.value(),
                    evaluation_uuid=self.evaluation_uuid, code_sha=self.code_sha, cohort=self.cohort.value,
                    financial_chain_sha=self.financial_chain_sha, integration_base_sha=self.integration_base_sha)


def closed(value, names):
    if type(value) is not dict or set(value) != set(names):
        raise VerificationError(Failure.INVALID)
    canonical(value)
    return value


def identifier(value):
    # UUID opaco: excluye paths, URLs, correos y nombres de personas.
    return uuid_text(value)


def actor(value):
    closed(value, ('user_id', 'session_version'))
    positive_id(value['user_id'])
    if type(value['session_version']) is not int or value['session_version'] < 0:
        raise VerificationError(Failure.INVALID)
    return value


def fingerprint(value):
    return hash_text(value)
