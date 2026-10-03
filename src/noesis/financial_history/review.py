"""Decisión actual sobre un item diagnóstico, incluidas evidencias auxiliares."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from noesis.financial_operations.contracts import positive_id, uuid_text
from .canonical import CanonicalContract, instant, sha256
from .contracts import DecisionKind, EvidenceReference, ReasonCode


@dataclass(frozen=True, slots=True)
class ReviewRecord(CanonicalContract):
    business_id: int
    manifest_uuid: UUID
    item_uuid: UUID
    incidence_uuid: UUID
    decision_uuid: UUID
    recorded_by: int
    permission: str
    decision_type: DecisionKind
    evidence: tuple[EvidenceReference, ...]
    reason_code: ReasonCode
    interpretation_hash: str | None
    previous_decision_uuid: UUID | None
    decided_at: datetime

    def __post_init__(self):
        positive_id(self.business_id)
        positive_id(self.recorded_by)
        for name in ('manifest_uuid','item_uuid','incidence_uuid','decision_uuid'):
            object.__setattr__(self,name,UUID(uuid_text(getattr(self,name))))
        object.__setattr__(self,'decision_type',DecisionKind(self.decision_type))
        object.__setattr__(self,'reason_code',ReasonCode(self.reason_code))
        object.__setattr__(self,'decided_at',instant(self.decided_at))
        if self.permission!='historical.record':
            raise ValueError('Permiso de registro, nunca autorización financiera.')
        refs = tuple(self.evidence)
        if len(refs)>64 or any(not isinstance(r,EvidenceReference) or r.business_id!=self.business_id for r in refs):
            raise ValueError('Referencias mínimas tipadas del mismo negocio requeridas.')
        refs = tuple(sorted(refs,key=lambda r:(r.kind.value,str(r.reference_id))))
        if len({(r.kind,str(r.reference_id)) for r in refs})!=len(refs):
            raise ValueError('Referencia duplicada.')
        object.__setattr__(self,'evidence',refs)
        if self.decision_type in (DecisionKind.ADD_EVIDENCE,DecisionKind.SELECT_SUPPORTED_INTERPRETATION) and not refs:
            raise ValueError('La revisión requiere evidencia explícita.')
        if self.decision_type==DecisionKind.SELECT_SUPPORTED_INTERPRETATION:
            sha256(self.interpretation_hash)
        elif self.interpretation_hash is not None:
            raise ValueError('Solo seleccionar una interpretación respaldada admite su hash.')
        if self.previous_decision_uuid is not None:
            previous = UUID(uuid_text(self.previous_decision_uuid))
            if previous==self.decision_uuid:
                raise ValueError('Una decisión no es su propio antecedente.')
            object.__setattr__(self,'previous_decision_uuid',previous)
