"""PilotReadinessReport v1: referencias no verificadas nunca acreditan realidad."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
import json

from noesis.financial_activation.contracts import Profile, canonical, digest, instant, tenant
from noesis.financial_providers.contracts import OperationalPolicy, hash_text


class PilotResult(StrEnum):
    READY = "PILOT_READY"
    BLOCKED = "PILOT_BLOCKED"


class Reason(StrEnum):
    LEGAL = "LEGAL_POLICY_UNAPPROVED"
    BUSINESS = "PILOT_BUSINESS_NOT_SELECTED"
    PROFILE = "PILOT_PROFILE_NOT_SELECTED"
    READINESS = "READINESS_NOT_FULL"
    STALE = "READINESS_STALE"
    HISTORY = "HISTORY_BLOCKED"
    UNSUPPORTED = "UNSUPPORTED_HISTORY"
    PRIVACY = "PRIVACY_NOT_READY"
    EXPORT = "EXPORT_NOT_READY"
    PROVIDER = "PROVIDER_ATTESTATION_MISSING"
    SAFE_CHECK = "SAFE_CHECK_UNIMPLEMENTED"
    PROVIDER_STALE = "PROVIDER_ATTESTATION_STALE"
    ENVIRONMENT = "PROVIDER_ENVIRONMENT_MISMATCH"
    BACKUP = "BACKUP_NOT_VERIFIED"
    RESTORE = "RESTORE_NOT_VERIFIED"
    DEPLOYMENT = "DEPLOYMENT_COMPATIBILITY_UNKNOWN"
    KEY = "RUNTIME_KEY_NOT_VERIFIED"
    OPERATOR = "OPERATOR_NOT_ASSIGNED"
    CUSTODIAN = "BACKUP_CUSTODIAN_NOT_ASSIGNED"
    PAUSE = "PAUSE_RUNBOOK_UNVERIFIED"
    UNKNOWN = "UNKNOWN_RESULT_RUNBOOK_UNVERIFIED"
    MONITORING = "MONITORING_NOT_READY"
    VOLUME = "VOLUME_OUTSIDE_POLICY"
    BANK = "BANK_NOT_ALLOWED"
    CLOSING = "ACCOUNT_CLOSING"
    CLOSED = "ACCOUNT_CLOSED"
    MAIN = "MAIN_INTEGRATION_PENDING"
    FISCAL = "FISCAL_CONTEXT_UNVERIFIED"
    REAL = "REAL_EVIDENCE_NOT_VERIFIED"
    D_PRODUCTION = "PRODUCTION_ACTIVATION_NOT_AUTHORIZED"
    RECOVERY = "RESUME_READINESS_CONTINUITY_UNVERIFIED"


class Owner(StrEnum):
    PRIMARY = "primary_operator"
    SECONDARY = "secondary_on_call"
    LEGAL = "privacy_legal_owner"
    BACKUP = "backup_custodian"
    ENGINEERING = "engineering_owner"
    HOLDER = "business_holder"


class EvidenceKind(StrEnum):
    MISSING = "missing"
    DOCUMENT = "documentation"
    SYNTHETIC = "synthetic"
    REFERENCE = "unverified_real_reference"


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    kind: EvidenceKind = EvidenceKind.MISSING
    content_hash: str | None = None
    business_id: int | None = None

    def __post_init__(self):
        object.__setattr__(self, "kind", EvidenceKind(self.kind))
        if self.business_id is not None:
            tenant(self.business_id)
        if self.kind == EvidenceKind.MISSING:
            if self.content_hash is not None or self.business_id is not None:
                raise ValueError("Ausencia no admite referencia inventada.")
        else:
            hash_text(self.content_hash)
            if self.kind != EvidenceKind.DOCUMENT and self.business_id is None:
                raise ValueError("Referencia de datos requiere tenant exacto.")

    def value(self):
        return dict(kind=self.kind.value, content_hash=self.content_hash, business_id=self.business_id)


@dataclass(frozen=True, slots=True)
class Finding:
    reason: Reason
    reference: EvidenceReference = EvidenceReference()

    def __post_init__(self):
        object.__setattr__(self, "reason", Reason(self.reason))
        if type(self.reference) is not EvidenceReference:
            raise TypeError("Referencia cerrada requerida.")

    def value(self):
        return dict(reason_code=self.reason.value, evidence_reference=self.reference.value())


@dataclass(frozen=True, slots=True)
class PreparationContext:
    code_sha: str
    source_context_hash: str
    business_id: int | None = None
    profile: Profile | None = None
    fiscal_required: bool | None = None
    findings: tuple[Finding, ...] = ()

    def __post_init__(self):
        if (type(self.code_sha) is not str or len(self.code_sha) != 40
                or any(c not in "0123456789abcdef" for c in self.code_sha)):
            raise ValueError("SHA Git completo requerido, sin etiquetas libres.")
        hash_text(self.source_context_hash)
        if self.business_id is not None:
            tenant(self.business_id)
        if self.profile is not None and type(self.profile) is not Profile:
            raise TypeError("Perfil A exacto requerido.")
        if self.fiscal_required is not None and type(self.fiscal_required) is not bool:
            raise TypeError("Condición fiscal desconocida o bool, nunca inferida.")
        if type(self.findings) is not tuple or any(type(f) is not Finding for f in self.findings):
            raise TypeError("Findings cerrados e inmutables requeridos.")
        if len({f.reason for f in self.findings}) != len(self.findings):
            raise ValueError("Reason code repetido.")
        for finding in self.findings:
            bid = finding.reference.business_id
            if bid is not None and bid != self.business_id:
                raise ValueError("Referencia cross-tenant rechazada.")
        object.__setattr__(self, "findings", tuple(sorted(self.findings, key=lambda f: f.reason)))

    def value(self):
        return dict(code_sha=self.code_sha, source_context_hash=self.source_context_hash,
                    business_id=self.business_id, profile=self.profile.value() if self.profile else None,
                    fiscal_required=self.fiscal_required, findings=[f.value() for f in self.findings])

    @classmethod
    def decode(cls, value):
        if type(value) is not dict or set(value) != {
            "code_sha", "source_context_hash", "business_id", "profile", "fiscal_required", "findings"
        }:
            raise ValueError("Contexto G-PREP cerrado requerido.")
        canonical(value)
        p = value["profile"]
        if p is not None and (type(p) is not dict or set(p) != {"profile_version", "capabilities"}
                              or type(p["capabilities"]) is not list):
            raise ValueError("Perfil A cerrado requerido.")
        if type(value["findings"]) is not list:
            raise ValueError("Lista de findings requerida.")
        findings = []
        for f in value["findings"]:
            if type(f) is not dict or set(f) != {"reason_code", "evidence_reference"}:
                raise ValueError("Finding cerrado requerido.")
            r = f["evidence_reference"]
            if type(r) is not dict or set(r) != {"kind", "content_hash", "business_id"}:
                raise ValueError("Referencia cerrada requerida.")
            findings.append(Finding(f["reason_code"], EvidenceReference(**r)))
        return cls(value["code_sha"], value["source_context_hash"], value["business_id"],
                   Profile(tuple(p["capabilities"]), p["profile_version"]) if p else None,
                   value["fiscal_required"], tuple(findings))


@dataclass(frozen=True, slots=True)
class PilotReadinessReport:
    canonical_content: str

    def __post_init__(self):
        from .report import assess
        body = json.loads(self.canonical_content)
        fields = {"version", "scope", "result", "software_status", "context", "context_hash",
                  "capability_closure", "provider_requirements", "blockers", "created_at", "expires_at",
                  "activation_authorized", "real_evidence_verified"}
        if type(body) is not dict or set(body) != fields or type(body["version"]) is not int or body["version"] != 1:
            raise ValueError("PilotReadinessReport v1 cerrado requerido.")
        expected = assess(PreparationContext.decode(body["context"]),
                          now=datetime.fromisoformat(body["created_at"]))
        if canonical(body) != canonical(expected):
            raise ValueError("Report alterado: no fabricar READY, authority ni evidencia real.")
        object.__setattr__(self, "canonical_content", canonical(body))

    @property
    def body(self):
        return json.loads(self.canonical_content)

    @property
    def content_hash(self):
        return digest(self.body)

    def current(self, context: PreparationContext, *, now: datetime):
        return (self.body["context_hash"] == digest(context.value())
                and instant(now) >= self.body["created_at"]
                and instant(now) < self.body["expires_at"])


def expiry(now):
    return instant(now + timedelta(seconds=OperationalPolicy().readiness_ttl_seconds))
