"""Contrato v1 cerrado: identidad exacta y evidencia, sin autoridad financiera."""

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json

from noesis.economic_events.contracts import SourceType
from noesis.financial_operations.contracts import positive_id, uuid_text

SCHEMAS = (75,)


def canonical(value):
    def normalize(v):
        if v is None or type(v) in (str, int, bool):
            return v
        if isinstance(v, Decimal) and v.is_finite():
            return format(v, "f")
        if isinstance(v, (date, datetime)):
            return v.isoformat()
        if isinstance(v, Mapping) and all(type(k) is str for k in v):
            return {k: normalize(x) for k, x in v.items()}
        if isinstance(v, (tuple, list)):
            return [normalize(x) for x in v]
        raise TypeError("Contrato de antecedentes sin float ni objetos libres.")

    return json.dumps(
        normalize(value), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class Origin(str, Enum):
    HISTORICAL = "historical"
    LIVE = "live"


class Quality(str, Enum):
    VERIFIED = "verified_fact"
    OBSERVED = "observed_state"


class Outcome(str, Enum):
    RESOLVED = "resolved"
    BLOCKED = "blocked"


class Permission(str, Enum):
    RESOLVE = "financial.antecedent.resolve"
    READ = "financial.antecedent.read"


class Purpose(str, Enum):
    CUSTOMER_PAYMENT = "customer_payment_against_invoice"
    RECTIFY = "rectify_invoice"
    FISCAL_CANCEL = "fiscal_cancel_invoice"
    BANK_MATCH = "bank_match_invoice"
    SUPPLIER_CORRECT = "supplier_invoice_correct"
    SUPPLIER_VOID = "supplier_invoice_void"
    EXPENSE_VOID = "expense_void"
    INSPECT = "inspect_evidence"


class Reason(str, Enum):
    NOT_FOUND = "ANTECEDENT_NOT_FOUND"
    UNSUPPORTED = "ANTECEDENT_UNSUPPORTED"
    NOT_VERIFIED = "ANTECEDENT_NOT_VERIFIED"
    OBSERVED_INSUFFICIENT = "OBSERVED_STATE_INSUFFICIENT"
    SOURCE_CHANGED = "SOURCE_CHANGED"
    EVENT_MISSING = "EVENT_MISSING"
    EVENT_INVALID = "EVENT_INVALID"
    OPERATION_INVALID = "OPERATION_INVALID"
    AUTHORIZATION_INVALID = "AUTHORIZATION_INVALID"
    COVERAGE_INCOMPLETE = "COVERAGE_INCOMPLETE"
    PAYMENT_HISTORY_INCOMPLETE = "PAYMENT_HISTORY_INCOMPLETE"
    MONEY_UNCERTAIN = "MONEY_UNCERTAIN"
    DATE_UNCERTAIN = "DATE_UNCERTAIN"
    FISCAL_INCOMPLETE = "FISCAL_EVIDENCE_INCOMPLETE"
    DEPENDENCY_INVALID = "DEPENDENCY_INVALID"
    PURPOSE_NOT_ALLOWED = "PURPOSE_NOT_ALLOWED"
    HISTORICAL_INVALID = "HISTORICAL_PROOF_INVALID"
    LIVE_INVALID = "LIVE_PROOF_INVALID"


CATALOG = MappingProxyType(
    {
        Purpose.CUSTOMER_PAYMENT: ("invoice", ("invoice.issued", "invoice.rectified")),
        Purpose.RECTIFY: ("invoice", ("invoice.issued", "invoice.rectified")),
        Purpose.FISCAL_CANCEL: ("invoice", ("invoice.issued", "invoice.rectified")),
        Purpose.BANK_MATCH: ("invoice", ("invoice.issued", "invoice.rectified")),
        Purpose.SUPPLIER_CORRECT: (
            "received_invoice",
            ("supplier_invoice.confirmed", "supplier_invoice.corrected"),
        ),
        Purpose.SUPPLIER_VOID: (
            "received_invoice",
            ("supplier_invoice.confirmed", "supplier_invoice.corrected"),
        ),
        Purpose.EXPENSE_VOID: ("expense", ("expense.confirmed",)),
        Purpose.INSPECT: (None, ()),
    }
)


@dataclass(frozen=True, slots=True)
class AntecedentRef:
    source_type: SourceType
    source_id: int
    revision: int
    event_uuid: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "source_type", SourceType(self.source_type))
        positive_id(self.source_id)
        positive_id(self.revision)
        if self.event_uuid is not None:
            object.__setattr__(self, "event_uuid", uuid_text(self.event_uuid))

    def value(self):
        return dict(
            source_type=self.source_type.value,
            source_id=self.source_id,
            revision=self.revision,
            event_uuid=self.event_uuid,
        )


@dataclass(frozen=True, slots=True)
class ResolutionRequest:
    antecedent: AntecedentRef
    purpose: Purpose
    bank_movement: AntecedentRef | None = None
    request_version: int = 1

    def __post_init__(self):
        if type(self.request_version) is not int or self.request_version != 1:
            raise ValueError("Versión de resolución desconocida.")
        if not isinstance(self.antecedent, AntecedentRef):
            raise TypeError("Identidad tipada requerida.")
        object.__setattr__(self, "purpose", Purpose(self.purpose))
        if self.bank_movement is not None and (
            not isinstance(self.bank_movement, AntecedentRef)
            or self.bank_movement.source_type != SourceType.BANK_TRANSACTION
            or self.purpose != Purpose.BANK_MATCH
        ):
            raise ValueError("Movimiento exacto solo para propósito bank match.")

    def value(self):
        return dict(
            request_version=1,
            purpose=self.purpose.value,
            antecedent=self.antecedent.value(),
            bank_movement=None if self.bank_movement is None else self.bank_movement.value(),
        )


FIELDS = (
    "amount",
    "currency",
    "economic_date",
    "source_state",
    "state_components",
    "prior_payments",
    "fiscal_evidence",
    "bank_movement",
    "base",
    "vat_amount",
    "irpf_amount",
    "invoice_number",
    "due_on",
)


def field_proof(known, value_hash=None):
    if type(known) is not bool or (known != (value_hash is not None)):
        raise ValueError("Known/unknown explícito requerido.")
    if value_hash is not None and (
        len(value_hash) != 64 or any(c not in "0123456789abcdef" for c in value_hash)
    ):
        raise ValueError("Hash SHA-256 requerido.")
    return dict(state="known" if known else "unknown", value_hash=value_hash)


def validate_result(value):
    """Valida forma cerrada además del hash; no sustituye comprobar la BD actual."""
    keys = {
        "resolution_version",
        "business_id",
        "request",
        "outcome",
        "reasons",
        "origin",
        "quality",
        "event_uuid",
        "operation_uuid",
        "authorization_uuid",
        "batch_uuid",
        "item_uuid",
        "reconciliation_uuid",
        "source_hash",
        "event_content_hash",
        "event_record_hash",
        "proof",
        "amount",
        "currency",
        "remaining",
        "dependencies",
        "context_hash",
        "evidence_hash",
    }
    if (
        set(value) != keys
        or type(value["resolution_version"]) is not int
        or value["resolution_version"] != 1
    ):
        raise ValueError("Resultado v1 cerrado requerido.")
    positive_id(value["business_id"])
    req = value["request"]
    rebuilt = ResolutionRequest(
        AntecedentRef(**req["antecedent"]),
        req["purpose"],
        None if req["bank_movement"] is None else AntecedentRef(**req["bank_movement"]),
        req["request_version"],
    )
    if rebuilt.value() != req:
        raise ValueError("Request incoherente.")
    state = Outcome(value["outcome"])
    reasons = sorted({Reason(r).value for r in value["reasons"]})
    if reasons != value["reasons"] or bool(reasons) != (state == Outcome.BLOCKED):
        raise ValueError("Outcome/reasons incoherentes.")
    if value["origin"] is not None:
        Origin(value["origin"])
    if value["quality"] is not None:
        Quality(value["quality"])
    if set(value["proof"]) != set(FIELDS):
        raise ValueError("Prueba known/unknown incompleta.")
    for p in value["proof"].values():
        if set(p) != {"state", "value_hash"} or p != field_proof(
            p["state"] == "known", p["value_hash"]
        ):
            raise ValueError("Prueba known/unknown inválida.")
    for key in (
        "event_uuid",
        "operation_uuid",
        "authorization_uuid",
        "batch_uuid",
        "item_uuid",
        "reconciliation_uuid",
    ):
        if value[key] is not None:
            uuid_text(value[key])
    for key in ("amount", "remaining"):
        if value[key] is not None:
            from noesis.core.money import parse_money

            number = parse_money(value[key])
            if not isinstance(value[key], str) or format(number, ".2f") != value[key]:
                raise ValueError("Dinero canónico en céntimos requerido.")
    from noesis.financial_history.canonical import sha256

    for key in (
        "source_hash",
        "context_hash",
        "evidence_hash",
        "event_content_hash",
        "event_record_hash",
    ):
        if value[key] is not None:
            sha256(value[key])
    if not isinstance(value["dependencies"], list) or len(value["dependencies"]) > 64:
        raise ValueError("Dependencias cerradas y acotadas requeridas.")
    for dep in value["dependencies"]:
        if set(dep) != {
            "relation",
            "event_uuid",
            "source_type",
            "source_id",
            "revision",
            "evidence_hash",
        } or dep["relation"] not in (
            "rectifies",
            "corrects",
            "voids",
            "settles",
            "matches",
            "evidence_for",
            "bank_evidence",
        ):
            raise ValueError("Dependencia cerrada requerida.")
        uuid_text(dep["event_uuid"])
        SourceType(dep["source_type"])
        positive_id(dep["source_id"])
        positive_id(dep["revision"])
        sha256(dep["evidence_hash"])
    if value["currency"] not in (None, "EUR"):
        raise ValueError("Moneda inválida.")
    if state == Outcome.RESOLVED and (
        not all(
            value[k]
            for k in (
                "event_uuid",
                "origin",
                "quality",
                "operation_uuid",
                "authorization_uuid",
                "source_hash",
                "event_content_hash",
                "event_record_hash",
            )
        )
        or (rebuilt.purpose != Purpose.INSPECT and value["quality"] != Quality.VERIFIED.value)
        or (
            value["origin"] == Origin.HISTORICAL.value
            and not all(value[k] for k in ("batch_uuid", "item_uuid", "reconciliation_uuid"))
        )
    ):
        raise ValueError("Resolved sin prueba estructural.")
    canonical(value)  # Rechaza float, NaN y tipos no admitidos recursivamente.
    if digest({k: v for k, v in value.items() if k != "evidence_hash"}) != value["evidence_hash"]:
        raise ValueError("Hash de evidencia incoherente.")
    return value
