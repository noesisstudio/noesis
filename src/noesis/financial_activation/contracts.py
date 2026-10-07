"""Contratos cerrados de 1.10A. Un hash nunca concede autoridad."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from types import MappingProxyType

from noesis.financial_operations.contracts import positive_id, uuid_text


class Capability(str, Enum):
    INVOICE_ISSUE = "invoice.issue"
    INVOICE_RECTIFY = "invoice.rectify"
    CUSTOMER_PAYMENT_RECORD = "customer_payment.record"
    SUPPLIER_INVOICE_CONFIRM = "supplier_invoice.confirm"
    SUPPLIER_INVOICE_CORRECT = "supplier_invoice.correct"
    SUPPLIER_INVOICE_VOID = "supplier_invoice.void"
    EXPENSE_CONFIRM = "expense.confirm"
    EXPENSE_VOID = "expense.void"
    BANK_IMPORT = "bank_transaction.import"
    BANK_MATCH = "bank_transaction.match"
    FISCAL_CANCEL = "invoice.fiscal_cancel"
    WEB = "channel.web_financial"
    WHATSAPP = "channel.whatsapp_financial"
    AEAT = "provider.aeat_dispatch"
    EMAIL = "provider.email_delivery"


class Outcome(str, Enum):
    FULL = "fully_eligible"
    PARTIAL = "partially_eligible"
    BLOCKED = "blocked"


class CapabilityResult(str, Enum):
    ELIGIBLE = "eligible"
    BLOCKED = "blocked"
    NOT_REQUESTED = "not_requested"
    NOT_APPLICABLE = "not_applicable"


class ControlState(str, Enum):
    OFF = "off"
    VALIDATING = "validating"


class Permission(str, Enum):
    EVALUATE = "financial.readiness.evaluate"


class Reason(str, Enum):
    HISTORY_PENDING = "HISTORY_PENDING"
    RECONCILIATION_BLOCKED = "RECONCILIATION_BLOCKED"
    RECONCILIATION_MISSING = "RECONCILIATION_MISSING"
    BOUNDARY_INVALID = "BOUNDARY_INVALID"
    SOURCE_DRIFT = "SOURCE_DRIFT"
    UNSUPPORTED_HISTORICAL_INVOICE = "UNSUPPORTED_HISTORICAL_INVOICE"
    CAPABILITY_DEPENDENCY_BLOCKED = "CAPABILITY_DEPENDENCY_BLOCKED"
    FISCAL_CAPABILITY_INCOMPLETE = "FISCAL_CAPABILITY_INCOMPLETE"
    BANK_EVIDENCE_UNVALIDATED = "BANK_EVIDENCE_UNVALIDATED"
    PROVIDER_PREFLIGHT_MISSING = "PROVIDER_PREFLIGHT_MISSING"
    PRIVACY_NOT_READY = "PRIVACY_NOT_READY"
    EXPORT_NOT_READY = "EXPORT_NOT_READY"
    VOLUME_OUTSIDE_POLICY = "VOLUME_OUTSIDE_POLICY"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    CONTEXT_CHANGED = "CONTEXT_CHANGED"
    CONTROL_INVALID = "CONTROL_INVALID"
    FISCAL_PROVIDER_NOT_APPLICABLE = "FISCAL_PROVIDER_NOT_APPLICABLE"
    CONTINUITY_NOT_IMPLEMENTED = "CONTINUITY_NOT_IMPLEMENTED"


VERSION = 1
SCHEMAS = (74, 75, 76, 77, 78)
C = Capability
DEPENDENCIES = MappingProxyType(
    {
        C.INVOICE_ISSUE: (C.INVOICE_RECTIFY, C.WEB),
        C.INVOICE_RECTIFY: (C.WEB,),
        C.CUSTOMER_PAYMENT_RECORD: (C.WEB,),
        C.SUPPLIER_INVOICE_CONFIRM: (C.WEB,),
        C.SUPPLIER_INVOICE_CORRECT: (C.SUPPLIER_INVOICE_CONFIRM,),
        C.SUPPLIER_INVOICE_VOID: (C.SUPPLIER_INVOICE_CONFIRM,),
        C.EXPENSE_CONFIRM: (C.WEB,),
        C.EXPENSE_VOID: (C.EXPENSE_CONFIRM,),
        C.BANK_IMPORT: (C.WEB,),
        C.BANK_MATCH: (C.BANK_IMPORT, C.CUSTOMER_PAYMENT_RECORD),
        C.FISCAL_CANCEL: (C.INVOICE_RECTIFY, C.AEAT),
        C.WEB: (),
        C.WHATSAPP: (),
        C.AEAT: (),
        C.EMAIL: (),
    }
)
FINANCIAL = frozenset(c for c in C if not c.value.startswith(("channel.", "provider.")))


def canonical(value):
    def check(item):
        if item is None or type(item) in (str, int, bool):
            return
        if type(item) is dict and all(type(k) is str for k in item):
            for v in item.values():
                check(v)
        elif type(item) in (list, tuple):
            for v in item:
                check(v)
        else:
            raise TypeError("Contrato readiness sin float ni objetos libres.")

    check(value)
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def version_one(value):
    if type(value) is not int or value != VERSION:
        raise ValueError("Versión readiness desconocida.")


def instant(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Instante aware requerido.")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


@dataclass(frozen=True, slots=True)
class Profile:
    capabilities: tuple[Capability, ...]
    profile_version: int = VERSION

    def __post_init__(self):
        version_one(self.profile_version)
        if type(self.capabilities) is not tuple or not self.capabilities:
            raise ValueError("Perfil explícito no vacío requerido.")
        values = tuple(Capability(c) for c in self.capabilities)
        if len(set(values)) != len(values):
            raise ValueError("Capacidades repetidas.")
        object.__setattr__(self, "capabilities", tuple(sorted(values, key=lambda c: c.value)))

    def value(self):
        return dict(
            profile_version=self.profile_version, capabilities=[c.value for c in self.capabilities]
        )

    @property
    def content_hash(self):
        return digest(self.value())

    def closure(self, *, fiscal_cancel_required):
        if type(fiscal_cancel_required) is not bool:
            raise TypeError("Condición fiscal verificada requerida.")
        edges = dict(DEPENDENCIES)
        if fiscal_cancel_required:
            edges[C.INVOICE_ISSUE] += (C.FISCAL_CANCEL, C.AEAT)
        needed = set(self.capabilities)
        while True:
            expanded = needed | {d for c in needed for d in edges[c]}
            if expanded == needed:
                break
            needed = expanded
        return tuple(sorted(needed, key=lambda c: c.value)), {
            c.value: sorted(d.value for d in edges[c])
            for c in sorted(needed, key=lambda c: c.value)
        }


@dataclass(frozen=True, slots=True)
class HistoryContext:
    epoch_uuid: str
    manifest_uuid: str
    batch_uuid: str
    reconciliation_uuid: str

    def __post_init__(self):
        for field in self.__dataclass_fields__:
            object.__setattr__(self, field, uuid_text(getattr(self, field)))

    def value(self):
        return {f: getattr(self, f) for f in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class Policy:
    policy_version: int = VERSION
    max_items: int = 64
    ttl_seconds: int = 300

    def __post_init__(self):
        version_one(self.policy_version)
        for value, maximum in ((self.max_items, 64), (self.ttl_seconds, 300)):
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError("Política fuera del límite aprobado.")

    def value(self):
        return dict(
            policy_version=self.policy_version,
            max_items=self.max_items,
            ttl_seconds=self.ttl_seconds,
        )


def capability_proof(capability, result, reasons, dependencies, evidence):
    capability, result = Capability(capability), CapabilityResult(result)
    reasons = sorted({Reason(r).value for r in reasons})
    if result == CapabilityResult.NOT_APPLICABLE:
        if (
            capability != C.AEAT
            or reasons != [Reason.FISCAL_PROVIDER_NOT_APPLICABLE.value]
            or evidence.get("verifactu_enabled") is not False
            or not isinstance(evidence.get("configuration_hash"), str)
            or len(evidence["configuration_hash"]) != 64
            or any(c not in "0123456789abcdef" for c in evidence["configuration_hash"])
        ):
            raise ValueError("not_applicable requiere evidencia fiscal tipada.")
    elif result == CapabilityResult.BLOCKED and not reasons:
        raise ValueError("Bloqueo sin razón.")
    elif result in (CapabilityResult.ELIGIBLE, CapabilityResult.NOT_REQUESTED) and reasons:
        raise ValueError("Razón incompatible con resultado.")
    value = dict(
        capability=capability.value,
        result=result.value,
        reasons=reasons,
        dependencies=dependencies,
        evidence=evidence,
    )
    for key, dependency_result in dependencies.items():
        Capability(key)
        CapabilityResult(dependency_result)
    canonical(value)
    return value


def future_ready_candidate(outcome, *, expires_at, now):
    """Solo contrato de consumo futuro; nunca cambia un estado."""
    return Outcome(outcome) == Outcome.FULL and instant(now) < instant(expires_at)


def tenant(value):
    return positive_id(value)
