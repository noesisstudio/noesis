"""Catálogos cerrados y contratos puros de 1.9A; no afirman evidencia por sí solos."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
import re
from types import MappingProxyType
from uuid import UUID, uuid5

from noesis.economic_events.contracts import CATALOG, EventType, RelationType, SourceType, _date, _uuid
from noesis.financial_operations.contracts import ConflictError, EntryIdentity, EntryNamespace, positive_id
from .canonical import CanonicalContract, instant, sha256, version_one
from .money_evidence import RawMonetaryEvidence
from .payloads import EventOrigin, EventPayload, EvidenceBasis, HISTORICAL_V2


class Classification(str, Enum):
    VERIFIED_HISTORY = "A"
    OBSERVED_STATE = "B"
    AMBIGUOUS = "C"
    NOT_AUTOMATICALLY_TRANSFORMABLE = "D"


class Disposition(str, Enum):
    CANDIDATE = "candidate"
    COVERED_EXISTING = "covered_existing"
    OUT_OF_SCOPE = "out_of_scope"
    EXCLUDED = "excluded"
    PENDING_INCIDENCE = "pending_incidence"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class IncidenceCode(str, Enum):
    MONEY_BINARY_UNCORROBORATED = "MONEY_BINARY_UNCORROBORATED"
    MONEY_SUBCENT = "MONEY_SUBCENT"
    REQUIRED_VALUE_UNKNOWN = "REQUIRED_VALUE_UNKNOWN"
    SYNTHETIC_LEGACY_PAYMENT = "SYNTHETIC_LEGACY_PAYMENT"
    PAID_WITHOUT_PAYMENT = "PAID_WITHOUT_PAYMENT"
    PAYMENT_OVER_TOTAL = "PAYMENT_OVER_TOTAL"
    POSSIBLE_DUPLICATE_PAYMENT = "POSSIBLE_DUPLICATE_PAYMENT"
    FISCAL_AMOUNT_MISMATCH = "FISCAL_AMOUNT_MISMATCH"
    MIGRATED_DOCUMENT_PROFILE = "MIGRATED_DOCUMENT_PROFILE"
    RECTIFICATION_PARENT_MISSING = "RECTIFICATION_PARENT_MISSING"
    BANK_LINK_AMBIGUOUS = "BANK_LINK_AMBIGUOUS"
    SOURCE_DRIFT = "SOURCE_DRIFT"
    SOURCE_HISTORY_LOST = "SOURCE_HISTORY_LOST"
    EXISTING_EVENT_CONFLICT = "EXISTING_EVENT_CONFLICT"


class ReasonCode(str, Enum):
    VERIFIED_FACT = "verified_fact"
    OBSERVED_STATE = "observed_state"
    COVERED_EXISTING = "covered_existing"
    OUT_OF_SCOPE = "out_of_scope"
    EXCLUDED = "excluded"
    INCIDENCE = "incidence"


class RuleId(str, Enum):
    VERIFIED = "history.verified"
    OBSERVED = "history.observed"
    AMBIGUOUS = "history.ambiguous"
    NOT_TRANSFORMABLE = "history.not_transformable"


RULE_CATALOG = MappingProxyType({
    (RuleId.VERIFIED, 1): Classification.VERIFIED_HISTORY,
    (RuleId.OBSERVED, 1): Classification.OBSERVED_STATE,
    (RuleId.AMBIGUOUS, 1): Classification.AMBIGUOUS,
    (RuleId.NOT_TRANSFORMABLE, 1): Classification.NOT_AUTOMATICALLY_TRANSFORMABLE,
})


@dataclass(frozen=True, slots=True)
class Assessment(CanonicalContract):
    classification: Classification
    disposition: Disposition
    severity: Severity
    rule_id: RuleId
    rule_version: int
    reason: ReasonCode
    evidence_hashes: tuple[str, ...]
    incidence_code: IncidenceCode | None

    def __post_init__(self):
        for name, kind in (("classification", Classification), ("disposition", Disposition),
                           ("severity", Severity), ("rule_id", RuleId), ("reason", ReasonCode)):
            object.__setattr__(self, name, kind(getattr(self, name)))
        version_one(self.rule_version)
        if RULE_CATALOG[(self.rule_id, self.rule_version)] != self.classification:
            raise ValueError("Regla y categoría incompatibles.")
        hashes = _hashes(self.evidence_hashes)
        if not hashes:
            raise ValueError("Clasificación requiere evidencia referenciada, incluso de ausencia.")
        object.__setattr__(self, "evidence_hashes", hashes)
        if self.incidence_code is not None:
            object.__setattr__(self, "incidence_code", IncidenceCode(self.incidence_code))
        if self.classification in (Classification.AMBIGUOUS, Classification.NOT_AUTOMATICALLY_TRANSFORMABLE):
            if self.disposition not in (Disposition.PENDING_INCIDENCE, Disposition.EXCLUDED):
                raise ValueError("C/D no son candidatos ni cobertura demostrada.")
            if self.incidence_code is None or self.reason not in (ReasonCode.INCIDENCE, ReasonCode.EXCLUDED):
                raise ValueError("C/D requieren un código cerrado de incidencia/exclusión.")
        elif self.disposition == Disposition.CANDIDATE:
            expected = ReasonCode.VERIFIED_FACT if self.classification == Classification.VERIFIED_HISTORY else ReasonCode.OBSERVED_STATE
            if self.reason != expected or self.incidence_code is not None:
                raise ValueError("Candidato A/B requiere razón correspondiente sin incidencia pendiente.")
        if self.disposition == Disposition.COVERED_EXISTING and self.reason != ReasonCode.COVERED_EXISTING:
            raise ValueError("Cobertura existente requiere razón explícita.")
        if self.disposition == Disposition.OUT_OF_SCOPE and self.reason != ReasonCode.OUT_OF_SCOPE:
            raise ValueError("Fuera de alcance requiere razón explícita.")
        if self.disposition == Disposition.EXCLUDED and self.reason != ReasonCode.EXCLUDED:
            raise ValueError("Exclusión requiere razón explícita; no elimina severidad.")
        if self.disposition == Disposition.PENDING_INCIDENCE and (self.reason != ReasonCode.INCIDENCE or self.incidence_code is None):
            raise ValueError("Pendiente exige código de incidencia cerrado.")


def _hashes(values):
    if not isinstance(values, (tuple, list)) or len(values) > 256:
        raise TypeError("Tupla/lista acotada de referencias requerida.")
    result = tuple(sorted(sha256(value) for value in values))
    if len(set(result)) != len(result):
        raise ValueError("Evidencia duplicada.")
    return result


class RevisionKind(str, Enum):
    OBSERVED_REVISION = "observed_revision"
    IMMUTABLE_FINGERPRINT = "immutable_fingerprint"
    DURABLE_REVISION = "durable_revision"


@dataclass(frozen=True, slots=True)
class RevisionIdentity(CanonicalContract):
    kind: RevisionKind
    value: int
    fingerprint: str | None

    def __post_init__(self):
        object.__setattr__(self, "kind", RevisionKind(self.kind))
        positive_id(self.value)
        if self.kind == RevisionKind.IMMUTABLE_FINGERPRINT:
            sha256(self.fingerprint)
        elif self.fingerprint is not None:
            raise ValueError("La evidencia no debe cambiar la identidad de una revisión observada.")


@dataclass(frozen=True, slots=True)
class SourceReference(CanonicalContract):
    business_id: int
    source_type: SourceType
    source_id: int

    def __post_init__(self):
        positive_id(self.business_id)
        positive_id(self.source_id)
        object.__setattr__(self, "source_type", SourceType(self.source_type))


@dataclass(frozen=True, slots=True)
class HistoricalIdentity(CanonicalContract):
    source: SourceReference
    revision: RevisionIdentity
    event_type: EventType
    fact_slot: str
    derivation_version: int = 1

    def __post_init__(self):
        version_one(self.derivation_version)
        if not isinstance(self.source, SourceReference) or not isinstance(self.revision, RevisionIdentity):
            raise TypeError("Origen y revisión tipados requeridos.")
        kind = EventType(self.event_type)
        object.__setattr__(self, "event_type", kind)
        if CATALOG[kind].source_type != self.source.source_type:
            raise ValueError("Tipo de hecho incompatible con origen.")
        if not isinstance(self.fact_slot, str) or not re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", self.fact_slot):
            raise ValueError("Slot estable cerrado requerido.")

    @property
    def entry_identity(self):
        return EntryIdentity(EntryNamespace.HISTORICAL, self.content_hash)

    @property
    def event_uuid(self):
        # Namespace constante propio, sin manifest, operador, reloj ni retry.
        return uuid5(UUID("5e7bbdba-976c-5dc5-bab7-1c14304c41c6"), self.content_hash)

    def assert_same_evidence(self, previous_hash, current_hash):
        if sha256(previous_hash) != sha256(current_hash):
            raise ConflictError("Misma identidad histórica con evidencia incompatible.")


class LegacyDateKind(str, Enum):
    UNKNOWN = "unknown"
    CIVIL_DATE = "civil_date"
    NAIVE_TIMESTAMP = "naive_timestamp"
    AWARE_TIMESTAMP = "aware_timestamp"


class DatePrecision(str, Enum):
    UNKNOWN = "unknown"
    DAY = "day"
    INSTANT = "instant"


@dataclass(frozen=True, slots=True)
class HistoricalDates(CanonicalContract):
    legacy_kind: LegacyDateKind
    legacy_representation: str | None
    civil_date: date | str | None
    economic_date: date | str | None
    occurred_at: datetime | None
    observed_at: datetime
    recorded_at: datetime | None

    def __post_init__(self):
        kind = LegacyDateKind(self.legacy_kind)
        object.__setattr__(self, "legacy_kind", kind)
        object.__setattr__(self, "observed_at", instant(self.observed_at))
        for name in ("civil_date", "economic_date"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, date.fromisoformat(_date(value)))
        for name in ("occurred_at", "recorded_at"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, instant(value))
        raw = self.legacy_representation
        if kind == LegacyDateKind.UNKNOWN:
            if raw is not None or self.civil_date is not None or self.economic_date is not None or self.occurred_at is not None:
                raise ValueError("Fecha desconocida no se completa desde el reloj.")
        elif kind == LegacyDateKind.CIVIL_DATE:
            if date.fromisoformat(_date(raw)) != self.civil_date or self.occurred_at is not None:
                raise ValueError("Fecha civil no acredita un instante.")
        else:
            if not isinstance(raw, str) or len(raw) > 64:
                raise ValueError("Timestamp legacy explícito requerido.")
            parsed = datetime.fromisoformat(raw)
            aware = parsed.tzinfo is not None and parsed.utcoffset() is not None
            if aware != (kind == LegacyDateKind.AWARE_TIMESTAMP):
                raise ValueError("Zona legacy incompatible con su tipo declarado.")
            if self.civil_date != parsed.date():
                raise ValueError("Fecha civil no coincide con timestamp original.")
            if kind == LegacyDateKind.NAIVE_TIMESTAMP and self.occurred_at is not None:
                raise ValueError("No asignar timezone a un timestamp naive.")
            if kind == LegacyDateKind.AWARE_TIMESTAMP and self.occurred_at != instant(parsed):
                raise ValueError("Instante debe coincidir con evidencia aware original.")
        if self.economic_date is not None and self.economic_date != self.civil_date:
            raise ValueError("Fecha económica debe tener evidencia civil coincidente.")

    @property
    def precision(self):
        return DatePrecision.INSTANT if self.occurred_at is not None else (
            DatePrecision.DAY if self.economic_date is not None else DatePrecision.UNKNOWN)


class EvidenceSource(str, Enum):
    DOCUMENT = "document"
    INVOICE_RECORD = "invoice_record"
    CANCELLATION_RECORD = "invoice_cancellation_record"
    DOCUMENT_PROFILE = "document_profile"
    BANK_LINK = "bank_payment_link"
    RECURRING_RUN = "recurring_invoice_run"
    EXISTING_EVENT = "economic_event"


@dataclass(frozen=True, slots=True)
class EvidenceReference(CanonicalContract):
    business_id: int
    kind: EvidenceSource
    reference_id: int | UUID
    evidence_hash: str

    def __post_init__(self):
        positive_id(self.business_id)
        object.__setattr__(self, "kind", EvidenceSource(self.kind))
        if self.kind == EvidenceSource.EXISTING_EVENT:
            object.__setattr__(self, "reference_id", _uuid(self.reference_id))
        else:
            positive_id(self.reference_id)
        sha256(self.evidence_hash)


# Solo valores contractuales necesarios, nunca PDFs, XML, imágenes ni notas.
MONEY_PATHS = frozenset(("amount", "total", "base", "vat_amount", "irpf_amount", "original_total",
    "before.total", "before.base", "before.vat_amount", "before.irpf_amount", "after.total",
    "after.base", "after.vat_amount", "after.irpf_amount"))


@dataclass(frozen=True, slots=True)
class HistoricalEvidence(CanonicalContract):
    source: SourceReference
    revision: RevisionIdentity
    basis: EvidenceBasis
    observed_at: datetime
    dates: HistoricalDates
    money: Mapping[str, RawMonetaryEvidence]
    references: tuple[EvidenceReference, ...]
    contract_version: int = 1

    def __post_init__(self):
        version_one(self.contract_version)
        if not isinstance(self.source, SourceReference) or not isinstance(self.revision, RevisionIdentity):
            raise TypeError("Origen/revisión tipados requeridos.")
        object.__setattr__(self, "basis", EvidenceBasis(self.basis))
        object.__setattr__(self, "observed_at", instant(self.observed_at))
        if not isinstance(self.dates, HistoricalDates) or self.dates.observed_at != self.observed_at or self.dates.recorded_at is not None:
            raise ValueError("Evidencia requiere fechas fuente/observación; no incorporación inventada.")
        if (not isinstance(self.money, Mapping) or set(self.money) - MONEY_PATHS
                or any(not isinstance(v, RawMonetaryEvidence) for v in self.money.values())):
            raise ValueError("Solo evidencia monetaria tipada en campos cerrados.")
        object.__setattr__(self, "money", MappingProxyType(dict(self.money)))
        if not isinstance(self.references, (tuple, list)) or any(not isinstance(r, EvidenceReference) for r in self.references):
            raise TypeError("Referencias mínimas tipadas requeridas, sin blobs.")
        if any(r.business_id != self.source.business_id for r in self.references):
            raise ValueError("Evidencia de otro negocio.")
        refs = tuple(sorted(self.references, key=lambda r: (r.kind.value, str(r.reference_id))))
        if len({(r.kind, str(r.reference_id)) for r in refs}) != len(refs):
            raise ValueError("Referencia duplicada/incompatible.")
        object.__setattr__(self, "references", refs)
        self.canonical_bytes()


@dataclass(frozen=True, slots=True)
class ExistingCoverage(CanonicalContract):
    identity: HistoricalIdentity
    event_uuid: UUID
    event_content_hash: str
    origin: EventOrigin

    def __post_init__(self):
        if not isinstance(self.identity, HistoricalIdentity):
            raise TypeError("Identidad concreta requerida.")
        object.__setattr__(self, "event_uuid", _uuid(self.event_uuid))
        object.__setattr__(self, "origin", EventOrigin(self.origin))
        sha256(self.event_content_hash)


@dataclass(frozen=True, slots=True)
class HistoricalDependency(CanonicalContract):
    relation: RelationType
    target: HistoricalIdentity
    parent_assessment: Assessment | None

    def __post_init__(self):
        object.__setattr__(self, "relation", RelationType(self.relation))
        if not isinstance(self.target, HistoricalIdentity):
            raise TypeError("Dependencia requiere identidad concreta; importe/fecha no identifican.")
        if self.parent_assessment is not None and not isinstance(self.parent_assessment, Assessment):
            raise TypeError("Estado del antecedente tipado requerido.")

    @property
    def satisfied(self):
        parent = self.parent_assessment
        return (parent is not None and parent.classification == Classification.VERIFIED_HISTORY
                and parent.disposition in (Disposition.CANDIDATE, Disposition.COVERED_EXISTING)
                and parent.severity != Severity.BLOCKING)


def _monetary_values(payload, prefix=""):
    for key, value in payload.items():
        path = prefix + key
        if path in MONEY_PATHS:
            yield path, value
        elif key in ("before", "after"):
            yield from _monetary_values(value, path + ".")


@dataclass(frozen=True, slots=True)
class HistoricalCandidate(CanonicalContract):
    identity: HistoricalIdentity
    event_payload: EventPayload
    evidence: HistoricalEvidence
    dates: HistoricalDates
    assessment: Assessment
    dependencies: tuple[HistoricalDependency, ...]
    existing_coverage: ExistingCoverage | None
    contract_version: int = 1

    def __post_init__(self):
        version_one(self.contract_version)
        for value, kind in ((self.identity, HistoricalIdentity), (self.event_payload, EventPayload),
                            (self.evidence, HistoricalEvidence), (self.dates, HistoricalDates),
                            (self.assessment, Assessment)):
            if not isinstance(value, kind):
                raise TypeError("Candidato requiere contratos tipados.")
        identity, payload, evidence = self.identity, self.event_payload, self.evidence
        if payload.payload_version == 2 and payload.event_type in (EventType.INVOICE_ISSUED, EventType.INVOICE_RECTIFIED):
            raise ValueError("Payload de emisión v2 válido, pero candidato histórico requiere contrato raw por línea/fiscal aún no definido.")
        if (payload.origin != EventOrigin.HISTORICAL or identity.event_type != payload.event_type
                or identity.source != evidence.source or identity.revision != evidence.revision):
            raise ValueError("Origen, identidad y evidencia incompatibles.")
        if payload.evidence_basis != evidence.basis:
            raise ValueError("B no puede presentarse como verified_fact.")
        expected = Classification.VERIFIED_HISTORY if evidence.basis == EvidenceBasis.VERIFIED_FACT else Classification.OBSERVED_STATE
        if self.assessment.classification in (Classification.VERIFIED_HISTORY, Classification.OBSERVED_STATE):
            if self.assessment.classification != expected:
                raise ValueError("Categoría incompatible con evidencia.")
        if evidence.content_hash not in self.assessment.evidence_hashes:
            raise ValueError("La clasificación no referencia esta evidencia.")
        if payload.payload_version == 2 and payload.event_type in HISTORICAL_V2:
            if payload.payload["evidence_hash"] != evidence.content_hash:
                raise ValueError("Payload no referencia evidencia congelada.")
        if self.dates.recorded_at is not None:
            raise ValueError("Un candidato no inventa recorded_at antes de incorporación.")
        if self.dates != evidence.dates or self.dates.economic_date != payload.economic_date:
            raise ValueError("Fechas del candidato y payload/evidencia incompatibles.")
        money = dict(_monetary_values(payload.payload))
        if set(evidence.money) != set(money):
            raise ValueError("Cada importe, incluido NULL, requiere evidencia y ningún campo extra.")
        corroboration_hashes = {r.evidence_hash for r in evidence.references}
        for raw in evidence.money.values():
            if set(raw.corroborating_hashes) - corroboration_hashes:
                raise ValueError("Corroboración no referenciada por la evidencia del candidato.")
        if self.assessment.classification in (Classification.VERIFIED_HISTORY, Classification.OBSERVED_STATE):
            if any(not evidence.money[key].validates_declared_amount(value) for key, value in money.items()):
                raise ValueError("A/B no presentan candidatos monetarios sin evidencia como dinero seguro.")
        if not isinstance(self.dependencies, (tuple, list)) or any(not isinstance(d, HistoricalDependency) for d in self.dependencies):
            raise TypeError("Dependencias tipadas requeridas.")
        deps = tuple(sorted(self.dependencies, key=lambda d: (d.relation.value, d.target.content_hash)))
        rules = CATALOG[payload.event_type].relations
        if {d.relation for d in deps} != {r.kind for r in rules} or len(deps) != len(rules):
            raise ValueError("Dependencias exactas del catálogo requeridas.")
        for dep in deps:
            rule = next(r for r in rules if r.kind == dep.relation)
            if (dep.target.source.business_id != identity.source.business_id
                    or dep.target == identity or dep.target.event_type not in rule.targets):
                raise ValueError("Dependencia cruzada/propia/incompatible.")
            if dep.relation in (RelationType.CORRECTS, RelationType.VOIDS):
                if (dep.target.source != identity.source or dep.target.revision.value >= identity.revision.value
                        or dep.target.revision.kind != identity.revision.kind):
                    raise ValueError("Corrección/retirada requiere antecedente del mismo origen y revisión acreditada anterior.")
            if dep.relation == RelationType.RECTIFIES and dep.target.source == identity.source:
                raise ValueError("Una rectificativa no rectifica su propia fuente.")
            expected_key = "invoice_id" if dep.relation in (RelationType.SETTLES, RelationType.EVIDENCE_FOR) and payload.event_type in (
                EventType.CUSTOMER_PAYMENT_RECEIVED, EventType.INVOICE_FISCAL_CANCELLATION_REGISTERED) else (
                "invoice_payment_id" if dep.relation == RelationType.MATCHES else None)
            if expected_key and dep.target.source.source_id != payload.payload[expected_key]:
                raise ValueError("Dependencia no corresponde al ID declarado.")
            if dep.relation == RelationType.EVIDENCE_FOR and payload.event_type == EventType.BANK_TRANSACTION_MATCHED:
                if dep.target.source != identity.source:
                    raise ValueError("Match requiere importación del mismo movimiento.")
        object.__setattr__(self, "dependencies", deps)
        if self.existing_coverage is not None:
            if not isinstance(self.existing_coverage, ExistingCoverage) or self.existing_coverage.identity != identity:
                raise ValueError("Cobertura existente de otro hecho.")
        if (self.assessment.disposition == Disposition.COVERED_EXISTING) != (self.existing_coverage is not None):
            raise ValueError("Disposición y referencia de cobertura deben concordar.")
        self.canonical_bytes()

    @property
    def importable(self):
        return (self.assessment.classification in (Classification.VERIFIED_HISTORY, Classification.OBSERVED_STATE)
                and self.assessment.disposition == Disposition.CANDIDATE
                and self.assessment.severity != Severity.BLOCKING
                and all(d.satisfied for d in self.dependencies)
                and all(raw.validates_declared_amount(value) for key, value in _monetary_values(self.event_payload.payload)
                        for raw in (self.evidence.money[key],)))

    @property
    def amount(self):
        return self.event_payload.amount

    @property
    def currency(self):
        return self.event_payload.currency

    @property
    def evidence_hash(self):
        return self.evidence.content_hash


class DecisionKind(str, Enum):
    ADD_EVIDENCE = "add_evidence"
    SELECT_SUPPORTED_INTERPRETATION = "select_supported_interpretation"
    EXCLUDE = "exclude"
    KEEP_BLOCKED = "keep_blocked"


@dataclass(frozen=True, slots=True)
class HistoricalIncidence(CanonicalContract):
    source: SourceReference
    evidence_hash: str
    code: IncidenceCode
    assessment: Assessment

    def __post_init__(self):
        if not isinstance(self.source, SourceReference) or not isinstance(self.assessment, Assessment):
            raise TypeError("Incidencia requiere origen y clasificación tipados.")
        sha256(self.evidence_hash)
        object.__setattr__(self, "code", IncidenceCode(self.code))
        if self.assessment.incidence_code != self.code or self.evidence_hash not in self.assessment.evidence_hashes:
            raise ValueError("Incidencia y evidencia/clasificación incompatibles.")


@dataclass(frozen=True, slots=True)
class HistoricalDecision(CanonicalContract):
    incidence: HistoricalIncidence
    kind: DecisionKind
    recorded_by: int
    decided_at: datetime
    evidence: tuple[EvidenceReference, ...]
    interpretation_hash: str | None

    def __post_init__(self):
        if not isinstance(self.incidence, HistoricalIncidence):
            raise TypeError("Decisión requiere incidencia concreta.")
        object.__setattr__(self, "kind", DecisionKind(self.kind))
        positive_id(self.recorded_by)
        object.__setattr__(self, "decided_at", instant(self.decided_at))
        if not isinstance(self.evidence, (tuple, list)) or any(not isinstance(r, EvidenceReference) for r in self.evidence):
            raise TypeError("Evidencia explícita requerida; sin notas/blobs.")
        if any(r.business_id != self.incidence.source.business_id for r in self.evidence):
            raise ValueError("Evidencia de otro negocio.")
        refs = tuple(sorted(self.evidence, key=lambda r: (r.kind.value, str(r.reference_id))))
        if len({(r.kind, str(r.reference_id)) for r in refs}) != len(refs):
            raise ValueError("Evidencia duplicada.")
        object.__setattr__(self, "evidence", refs)
        if self.kind in (DecisionKind.ADD_EVIDENCE, DecisionKind.SELECT_SUPPORTED_INTERPRETATION) and not refs:
            raise ValueError("Resolver requiere nueva evidencia, no una opinión.")
        if self.kind == DecisionKind.SELECT_SUPPORTED_INTERPRETATION:
            sha256(self.interpretation_hash)
        elif self.interpretation_hash is not None:
            raise ValueError("Interpretación solo para selección sustentada.")


@dataclass(frozen=True, slots=True)
class HistoricalAuditContext(CanonicalContract):
    business_id: int
    recorded_by: int
    manifest_uuid: UUID
    item_uuid: UUID
    evidence_hash: str
    permission: str

    def __post_init__(self):
        positive_id(self.business_id)
        positive_id(self.recorded_by)
        object.__setattr__(self, "manifest_uuid", _uuid(self.manifest_uuid))
        object.__setattr__(self, "item_uuid", _uuid(self.item_uuid))
        sha256(self.evidence_hash)
        if self.permission != "historical.audit":
            raise ValueError("Contexto interno histórico/auditoría requerido.")

    def matches(self, identity, evidence_hash):
        """Solo concordancia declarada; el futuro servicio debe autenticar permiso/items."""
        if not isinstance(identity, HistoricalIdentity):
            raise TypeError("Identidad histórica requerida.")
        return self.business_id == identity.source.business_id and self.evidence_hash == sha256(evidence_hash)
