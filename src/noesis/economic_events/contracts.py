"""Catálogo cerrado v1 y representación canónica propia (no RFC 8785).

Validar un hecho no autoriza una operación ni reconoce ingresos, impuestos o caja.
Solo se importan stdlib y el contrato monetario de Fase 0.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Context, Decimal, localcontext
from enum import Enum
import hashlib
import json
import re
from types import MappingProxyType
from uuid import UUID

from noesis.core.money import Currency, parse_money, quantize_currency


class EventType(str, Enum):
    INVOICE_ISSUED = "invoice.issued"
    INVOICE_RECTIFIED = "invoice.rectified"
    CUSTOMER_PAYMENT_RECEIVED = "customer_payment.received"
    SUPPLIER_INVOICE_CONFIRMED = "supplier_invoice.confirmed"
    SUPPLIER_INVOICE_CORRECTED = "supplier_invoice.corrected"
    SUPPLIER_INVOICE_VOIDED = "supplier_invoice.voided"
    EXPENSE_CONFIRMED = "expense.confirmed"
    EXPENSE_VOIDED = "expense.voided"
    BANK_TRANSACTION_IMPORTED = "bank_transaction.imported"
    BANK_TRANSACTION_MATCHED = "bank_transaction.matched"
    INVOICE_FISCAL_CANCELLATION_REGISTERED = "invoice.fiscal_cancellation_registered"


class SourceType(str, Enum):
    INVOICE = "invoice"
    INVOICE_PAYMENT = "invoice_payment"
    RECEIVED_INVOICE = "received_invoice"
    EXPENSE = "expense"
    BANK_TRANSACTION = "bank_transaction"
    INVOICE_CANCELLATION_RECORD = "invoice_cancellation_record"


class FutureImpact(str, Enum):
    GL = "GL"
    TAX = "Tax"
    AR = "AR"
    AP = "AP"
    TREASURY = "Treasury"
    EVIDENCE = "Evidence"


class RelationType(str, Enum):
    RECTIFIES = "rectifies"
    CORRECTS = "corrects"
    VOIDS = "voids"
    SETTLES = "settles"
    MATCHES = "matches"
    EVIDENCE_FOR = "evidence_for"


@dataclass(frozen=True, slots=True)
class Field:
    """Campo cerrado: tipo, presencia y nulabilidad son decisiones independientes."""

    name: str
    kind: str
    optional: bool = False
    nullable: bool = False


@dataclass(frozen=True, slots=True)
class RelationRule:
    kind: RelationType
    targets: tuple[EventType, ...]


@dataclass(frozen=True, slots=True)
class EventSpec:
    payload_version: int
    source_type: SourceType
    fields: tuple[Field, ...]
    amount_path: tuple[str, ...] | None
    amount_semantics: str
    economic_date_field: str
    relations: tuple[RelationRule, ...]
    future_impacts: tuple[FutureImpact, ...]


_INVOICE = (
    Field("invoice_number", "text"), Field("invoice_kind", "text"),
    Field("issued_on", "date"), Field("base", "money"), Field("vat_amount", "money"),
    Field("irpf_amount", "money"), Field("total", "money"),
    Field("operation_on", "date", optional=True, nullable=True),
    Field("due_on", "date", optional=True, nullable=True),
)
_SUPPLIER = (
    Field("total", "money"), Field("issued_on", "date", nullable=True),
    Field("invoice_number", "text", optional=True, nullable=True),
    Field("due_on", "date", optional=True, nullable=True),
    Field("base", "money", optional=True, nullable=True),
    Field("vat_amount", "money", optional=True, nullable=True),
    Field("irpf_amount", "money", optional=True, nullable=True),
)
_EXPENSE = (
    Field("total", "money"), Field("spent_on", "date", nullable=True),
    Field("description", "text"),
    Field("vat_amount", "money", optional=True, nullable=True),
)
_ISSUED = (EventType.INVOICE_ISSUED, EventType.INVOICE_RECTIFIED)
_RECEIVED = (EventType.SUPPLIER_INVOICE_CONFIRMED, EventType.SUPPLIER_INVOICE_CORRECTED)
_F = FutureImpact
_R = RelationType

# El catálogo es la única puerta de entrada: no contiene acontecimientos operativos.
CATALOG: Mapping[EventType, EventSpec] = MappingProxyType({
    EventType.INVOICE_ISSUED: EventSpec(
        1, SourceType.INVOICE, _INVOICE, ("total",), "Total exigible emitido, >= 0.",
        "issued_on", (), (_F.GL, _F.TAX, _F.AR, _F.EVIDENCE)),
    EventType.INVOICE_RECTIFIED: EventSpec(
        1, SourceType.INVOICE,
        _INVOICE + (Field("reason", "text"), Field("rectification_method", "text")), ("total",),
        "Diferencia firmada de la rectificativa; no total de la original.", "issued_on",
        (RelationRule(_R.RECTIFIES, _ISSUED),), (_F.GL, _F.TAX, _F.AR, _F.EVIDENCE)),
    EventType.CUSTOMER_PAYMENT_RECEIVED: EventSpec(
        1, SourceType.INVOICE_PAYMENT,
        (Field("invoice_id", "id"), Field("amount", "money"), Field("received_on", "date"),
         Field("method", "text", optional=True, nullable=True)),
        ("amount",), "Cobro real positivo, parcial o completo; no importe de factura.",
        "received_on", (RelationRule(_R.SETTLES, _ISSUED),),
        (_F.GL, _F.AR, _F.TREASURY, _F.EVIDENCE)),
    EventType.SUPPLIER_INVOICE_CONFIRMED: EventSpec(
        1, SourceType.RECEIVED_INVOICE, _SUPPLIER + (Field("confirmed_on", "date"),),
        ("total",), "Total confirmado >= 0; no prueba pago ni deducibilidad.", "issued_on",
        (), (_F.GL, _F.TAX, _F.AP, _F.EVIDENCE)),
    EventType.SUPPLIER_INVOICE_CORRECTED: EventSpec(
        1, SourceType.RECEIVED_INVOICE,
        (Field("before", "supplier_snapshot"), Field("after", "supplier_snapshot"),
         Field("corrected_on", "date"), Field("reason", "text")),
        ("after", "total"), "Total sustitutivo completo; before/after no son dos compras.",
        "corrected_on", (RelationRule(_R.CORRECTS, _RECEIVED),),
        (_F.GL, _F.TAX, _F.AP, _F.EVIDENCE)),
    EventType.SUPPLIER_INVOICE_VOIDED: EventSpec(
        1, SourceType.RECEIVED_INVOICE,
        (Field("before", "supplier_snapshot"), Field("voided_on", "date"),
         Field("reason", "text")), ("before", "total"),
        "Total anterior contextual >= 0; retirada, no devolución ni pago.", "voided_on",
        (RelationRule(_R.VOIDS, _RECEIVED),), (_F.GL, _F.TAX, _F.AP, _F.EVIDENCE)),
    EventType.EXPENSE_CONFIRMED: EventSpec(
        1, SourceType.EXPENSE, _EXPENSE + (Field("confirmed_on", "date"),), ("total",),
        "Gasto confirmado positivo; no prueba pago ni deducibilidad.", "spent_on",
        (), (_F.GL, _F.TAX, _F.EVIDENCE)),
    EventType.EXPENSE_VOIDED: EventSpec(
        1, SourceType.EXPENSE,
        (Field("before", "expense_snapshot"), Field("voided_on", "date"),
         Field("reason", "text")), ("before", "total"),
        "Total anterior contextual positivo; retirada, no reembolso.", "voided_on",
        (RelationRule(_R.VOIDS, (EventType.EXPENSE_CONFIRMED,)),),
        (_F.GL, _F.TAX, _F.EVIDENCE)),
    EventType.BANK_TRANSACTION_IMPORTED: EventSpec(
        1, SourceType.BANK_TRANSACTION,
        (Field("amount", "money"), Field("booked_on", "date", nullable=True),
         Field("imported_on", "date"), Field("value_on", "date", optional=True, nullable=True),
         Field("bank_reference", "text", optional=True, nullable=True)),
        ("amount",), "Movimiento firmado no nulo: entrada positiva, salida negativa.",
        "booked_on", (), (_F.TREASURY, _F.EVIDENCE)),
    EventType.BANK_TRANSACTION_MATCHED: EventSpec(
        1, SourceType.BANK_TRANSACTION,
        (Field("amount", "money"), Field("invoice_payment_id", "id"),
         Field("matched_on", "date")), ("amount",),
        "Importe positivo vinculado al cobro; evidencia, nunca segunda caja.", "matched_on",
        (RelationRule(_R.MATCHES, (EventType.CUSTOMER_PAYMENT_RECEIVED,)),
         RelationRule(_R.EVIDENCE_FOR, (EventType.BANK_TRANSACTION_IMPORTED,))), (_F.EVIDENCE,)),
    EventType.INVOICE_FISCAL_CANCELLATION_REGISTERED: EventSpec(
        1, SourceType.INVOICE_CANCELLATION_RECORD,
        (Field("invoice_id", "id"), Field("invoice_number", "text"),
         Field("original_total", "money"), Field("registered_on", "date"),
         Field("reason", "text")), None,
        "Sin amount: original_total es contexto firmado, no reversión económica.",
        "registered_on", (RelationRule(_R.EVIDENCE_FOR, _ISSUED),), (_F.EVIDENCE,)),
})


def _positive_id(value: object) -> int:
    if type(value) is not int or value <= 0 or value > 9223372036854775807:
        raise ValueError("Identificador/revisión entero positivo BIGINT requerido.")
    return value


def _uuid(value: object) -> UUID:
    if not isinstance(value, (str, UUID)):
        raise ValueError("UUID requerido.")
    result = UUID(str(value))
    if result.int == 0:
        raise ValueError("UUID nulo no permitido.")
    return result


def _date(value: object) -> str:
    if type(value) is date:
        return value.isoformat()
    if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return date.fromisoformat(value).isoformat()
    raise ValueError("Fecha civil ISO YYYY-MM-DD requerida; no timestamp.")


def _instant(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Instante datetime con zona horaria requerido.")
    return value.astimezone(timezone.utc)


def _money(value: object) -> Decimal:
    if not isinstance(value, (Decimal, str)):
        raise TypeError("Importe final: Decimal o string decimal, nunca float/bool/entero JSON.")
    amount = parse_money(value)
    result = quantize_currency(amount)
    if amount != result:
        raise ValueError("Un hecho final no admite fracciones de céntimo ni redondeo implícito.")
    return result


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        raise ValueError("Texto no vacío de hasta 2048 caracteres requerido.")
    value.encode("utf-8")  # Rechaza sustitutos Unicode aislados; conserva el texto original.
    return value


def _schema(raw: object, fields: tuple[Field, ...]) -> Mapping[str, object]:
    if not isinstance(raw, Mapping) or any(type(key) is not str for key in raw):
        raise ValueError("Payload/snapshot debe ser un mapping con claves string.")
    names = {field.name for field in fields}
    if set(raw) - names:
        raise ValueError("Campos adicionales no permitidos.")
    result = {}
    for field in fields:
        if field.name not in raw and not field.optional:
            raise ValueError(f"Falta el campo obligatorio {field.name}.")
        value = raw.get(field.name)
        if value is None and (field.nullable or field.optional and field.name not in raw):
            result[field.name] = None
            continue
        if field.kind == "supplier_snapshot":
            value = _schema(value, _SUPPLIER)
            _supplier(value)
        elif field.kind == "expense_snapshot":
            value = _schema(value, _EXPENSE)
            _expense(value)
        else:
            value = {"money": _money, "date": _date, "text": _text,
                     "id": _positive_id}[field.kind](value)
        result[field.name] = value
    return MappingProxyType(result)


def _breakdown(payload: Mapping[str, object]) -> None:
    values = tuple(payload.get(key) for key in ("base", "vat_amount", "irpf_amount"))
    if all(value is not None for value in values):
        with localcontext(Context(prec=50)):
            expected = values[0] + values[1] - values[2]
        if expected != payload["total"]:
            raise ValueError("Total incoherente con base + IVA - IRPF declarado.")


def _supplier(payload: Mapping[str, object]) -> None:
    for key in ("total", "base", "vat_amount", "irpf_amount"):
        if payload.get(key) is not None and payload[key] < 0:
            raise ValueError("Snapshot de recibida requiere importes no negativos.")
    _breakdown(payload)


def _expense(payload: Mapping[str, object]) -> None:
    if payload["total"] <= 0:
        raise ValueError("Gasto positivo requerido.")
    vat = payload.get("vat_amount")
    if vat is not None and not 0 <= vat <= payload["total"]:
        raise ValueError("IVA de gasto fuera del total declarado.")


def validate_payload(event_type: EventType | str, payload: Mapping[str, object],
                     payload_version: int = 1) -> Mapping[str, object]:
    """Copia y congela un payload v1; campos ausentes opcionales se fijan a null."""
    event_type = EventType(event_type)
    spec = CATALOG[event_type]
    if type(payload_version) is not int or payload_version != spec.payload_version:
        raise ValueError("Versión de payload desconocida.")
    result = _schema(payload, spec.fields)
    if event_type in _ISSUED:
        kinds = ("F1", "F2") if event_type == EventType.INVOICE_ISSUED else (
            "R1", "R2", "R3", "R4", "R5")
        if result["invoice_kind"] not in kinds:
            raise ValueError("Tipo de factura incompatible con el hecho.")
        if event_type == EventType.INVOICE_RECTIFIED and result["rectification_method"] != "I":
            raise ValueError("v1 admite solo rectificación por diferencias (I).")
        _breakdown(result)
        if event_type == EventType.INVOICE_ISSUED and any(
                result[key] < 0 for key in ("total", "base", "vat_amount", "irpf_amount")):
            raise ValueError("Factura ordinaria requiere importes no negativos.")
    elif event_type == EventType.SUPPLIER_INVOICE_CONFIRMED:
        _supplier(result)
    elif event_type == EventType.EXPENSE_CONFIRMED:
        _expense(result)
    elif event_type in (EventType.CUSTOMER_PAYMENT_RECEIVED, EventType.BANK_TRANSACTION_MATCHED):
        if result["amount"] <= 0:
            raise ValueError("Importe positivo requerido.")
    elif event_type == EventType.BANK_TRANSACTION_IMPORTED and result["amount"] == 0:
        raise ValueError("Movimiento bancario no nulo requerido.")
    return result


def _json_value(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Mapping):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def _canonical(value: object) -> bytes:
    return json.dumps(_json_value(value), sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_payload(event_type: EventType | str, payload: Mapping[str, object],
                      payload_version: int = 1) -> bytes:
    return _canonical(validate_payload(event_type, payload, payload_version))


def payload_hash(event_type: EventType | str, payload: Mapping[str, object],
                 payload_version: int = 1, currency: Currency | str = Currency.EUR) -> str:
    """SHA-256 del contenido tipado, no una clave de idempotencia de operación."""
    return hashlib.sha256(_canonical({
        "canonical_version": 1, "event_type": EventType(event_type).value,
        "payload_version": payload_version, "currency": Currency(currency).value,
        "payload": validate_payload(event_type, payload, payload_version),
    })).hexdigest()


@dataclass(frozen=True, slots=True)
class EventRelation:
    kind: RelationType
    target_event_id: UUID
    target_event_type: EventType
    business_id: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", RelationType(self.kind))
        object.__setattr__(self, "target_event_id", _uuid(self.target_event_id))
        object.__setattr__(self, "target_event_type", EventType(self.target_event_type))
        _positive_id(self.business_id)


@dataclass(frozen=True, slots=True)
class EconomicEvent:
    """Hecho en memoria. Identidad aportada por el llamador; no ejecuta ni persiste."""

    event_id: UUID
    business_id: int
    event_type: EventType
    source_type: SourceType
    source_id: int
    source_revision: int
    occurred_at: datetime | None
    observed_at: datetime
    payload: Mapping[str, object]
    payload_version: int = 1
    currency: Currency = Currency.EUR
    relations: tuple[EventRelation, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", _uuid(self.event_id))
        for name in ("business_id", "source_id", "source_revision"):
            _positive_id(getattr(self, name))
        event_type = EventType(self.event_type)
        spec = CATALOG[event_type]
        source_type = SourceType(self.source_type)
        if source_type != spec.source_type:
            raise ValueError("Origen incompatible con el tipo de evento.")
        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(self, "source_type", source_type)
        object.__setattr__(self, "currency", Currency(self.currency))
        object.__setattr__(self, "observed_at", _instant(self.observed_at))
        if self.occurred_at is not None:
            object.__setattr__(self, "occurred_at", _instant(self.occurred_at))
        object.__setattr__(self, "payload", validate_payload(
            event_type, self.payload, self.payload_version))
        if not isinstance(self.relations, (tuple, list)) or any(
                not isinstance(item, EventRelation) for item in self.relations):
            raise ValueError("Relaciones tipadas requeridas.")
        for rule in spec.relations:
            matching = [item for item in self.relations if item.kind == rule.kind]
            if len(matching) != 1 or matching[0].target_event_type not in rule.targets:
                raise ValueError("Relación obligatoria ausente, múltiple o incompatible.")
        allowed = {rule.kind for rule in spec.relations}
        for item in self.relations:
            if (item.kind not in allowed or item.business_id != self.business_id
                    or item.target_event_id == self.event_id):
                raise ValueError("Relación no permitida, entre empresas o consigo mismo.")
        object.__setattr__(self, "relations", tuple(sorted(
            self.relations, key=lambda item: (item.kind.value, str(item.target_event_id)))))

    @property
    def amount(self) -> Decimal | None:
        path = CATALOG[self.event_type].amount_path
        if path is None:
            return None
        value = self.payload
        for key in path:
            value = value[key]
        return value

    @property
    def economic_date(self) -> date | None:
        value = self.payload[CATALOG[self.event_type].economic_date_field]
        return None if value is None else date.fromisoformat(value)

    @property
    def payload_hash(self) -> str:
        return payload_hash(self.event_type, self.payload, self.payload_version, self.currency)

    def canonical_bytes(self) -> bytes:
        """Sobre completo: identidad/origen/fechas/relaciones también quedan cubiertos."""
        return _canonical({
            "canonical_version": 1, "event_id": str(self.event_id),
            "business_id": self.business_id, "event_type": self.event_type.value,
            "source_type": self.source_type.value, "source_id": self.source_id,
            "source_revision": self.source_revision, "payload_version": self.payload_version,
            "occurred_at": None if self.occurred_at is None else self.occurred_at.isoformat(
                timespec="microseconds"),
            "observed_at": self.observed_at.isoformat(timespec="microseconds"),
            "currency": self.currency.value, "amount": self.amount,
            "payload": self.payload, "relations": tuple({
                "kind": item.kind.value, "target_event_id": str(item.target_event_id),
                "target_event_type": item.target_event_type.value, "business_id": item.business_id,
            } for item in self.relations),
        })

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()
