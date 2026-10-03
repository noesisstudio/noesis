"""Payloads en memoria; el esquema69 y EconomicEvent durable no se amplían.

El wrapper valida origin/version. No invoca append ni construye eventos durables.
v1 y v2 de emisión conservan sus validadores, bytes y hashes originales.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import Enum

from noesis.core.money import Currency
from noesis.economic_events.contracts import (
    CATALOG, EventType, Field, _schema, _supplier, _expense, validate_payload,
)
from .canonical import CanonicalContract, sha256


class EventOrigin(str, Enum):
    LIVE = "live"
    HISTORICAL = "historical"


class EvidenceBasis(str, Enum):
    VERIFIED_FACT = "verified_fact"
    OBSERVED_STATE = "observed_state"


HISTORICAL_V2 = frozenset((EventType.SUPPLIER_INVOICE_CONFIRMED,
                           EventType.EXPENSE_CONFIRMED, EventType.BANK_TRANSACTION_IMPORTED))


@dataclass(frozen=True, slots=True)
class EventPayload(CanonicalContract):
    event_type: EventType
    payload_version: int
    origin: EventOrigin
    payload: Mapping[str, object]
    currency: Currency

    def __post_init__(self):
        kind, origin = EventType(self.event_type), EventOrigin(self.origin)
        object.__setattr__(self, "event_type", kind)
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "currency", Currency(self.currency))
        version = self.payload_version
        if type(version) is not int:
            raise ValueError("Versión entera requerida.")
        if version != 2 or kind not in HISTORICAL_V2:
            result = validate_payload(kind, self.payload, version)
        else:
            if origin != EventOrigin.HISTORICAL:
                raise ValueError("Este v2 solo admite origin=historical.")
            spec = CATALOG[kind]
            original_date = "imported_on" if kind == EventType.BANK_TRANSACTION_IMPORTED else "confirmed_on"
            fields = tuple(Field(f.name, f.kind, f.optional, True) if f.name == original_date else f
                           for f in spec.fields)
            result = _schema(self.payload, fields + (Field("evidence_basis", "text"), Field("evidence_hash", "text")))
            EvidenceBasis(result["evidence_basis"])
            sha256(result["evidence_hash"])
            if kind == EventType.SUPPLIER_INVOICE_CONFIRMED:
                _supplier(result)
            elif kind == EventType.EXPENSE_CONFIRMED:
                _expense(result)
            elif result["amount"] == 0:
                raise ValueError("Movimiento no nulo requerido.")
        object.__setattr__(self, "payload", result)

    @property
    def amount(self):
        path = CATALOG[self.event_type].amount_path
        if path is None:
            return None
        value = self.payload
        for key in path:
            value = value[key]
        return value

    @property
    def economic_date(self):
        value = self.payload[CATALOG[self.event_type].economic_date_field]
        return None if value is None else date.fromisoformat(value)

    @property
    def evidence_basis(self):
        if self.payload_version == 2 and self.event_type in HISTORICAL_V2:
            return EvidenceBasis(self.payload["evidence_basis"])
        return EvidenceBasis.VERIFIED_FACT
