"""Identidad de servidor y contenido financiero canónico, sin ejecución."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
import hashlib
import json
from types import MappingProxyType
from uuid import UUID

from noesis.core.money import Currency, parse_money, quantize_currency


class CommandType(str, Enum):
    INVOICE_ISSUE = "invoice.issue"
    INVOICE_RECTIFY = "invoice.rectify"
    CUSTOMER_PAYMENT_RECORD = "customer_payment.record"
    SUPPLIER_INVOICE_CONFIRM = "supplier_invoice.confirm"
    SUPPLIER_INVOICE_CORRECT = "supplier_invoice.correct"
    SUPPLIER_INVOICE_VOID = "supplier_invoice.void"
    EXPENSE_CONFIRM = "expense.confirm"
    EXPENSE_VOID = "expense.void"
    BANK_TRANSACTION_IMPORT = "bank_transaction.import"
    BANK_TRANSACTION_MATCH = "bank_transaction.match"
    INVOICE_FISCAL_CANCEL = "invoice.fiscal_cancel"


class EntryNamespace(str, Enum):
    WEB_API = "web_api"
    CHAT = "chat"
    WHATSAPP = "whatsapp"
    DOCUMENT_REVIEW = "document_review"
    RECURRING = "recurring"
    IMPORT = "import"
    HISTORICAL = "historical"


class OperationState(str, Enum):
    PREPARED = "prepared"
    APPROVED = "approved"
    COMMITTED = "committed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class AuthorizationKind(str, Enum):
    HUMAN = "human_confirmation"
    MANDATE = "mandate"
    HISTORICAL_UNKNOWN = "historical_unknown"


class ConflictError(ValueError):
    """La identidad estable ya tiene otro contenido; no tocar la operación."""


class AccessDenied(PermissionError):
    """Respuesta uniforme sin confirmar existencia de un UUID ajeno."""


class StateError(ValueError):
    """Transición, revisión o autorización incompatible."""


def positive_id(value: object) -> int:
    if type(value) is not int or not 0 < value <= 9223372036854775807:
        raise ValueError("Identificador/revisión BIGINT positivo requerido.")
    return value


def uuid_text(value: object) -> str:
    if not isinstance(value, (str, UUID)):
        raise ValueError("UUID requerido.")
    result = UUID(str(value))
    if not result.int:
        raise ValueError("UUID nulo no permitido.")
    return str(result)


_RESERVED = {"operation_uuid", "entry_key", "entry_namespace", "idempotency_key",
             "business_id", "authorization_uuid", "approved_by_ai"}


def exact_json(value: object, *, depth: int = 0) -> object:
    """JSON acotado sin float; Decimal intermedio conserva escala y rango de Money."""
    if depth > 12:
        raise ValueError("Contenido demasiado anidado.")
    if isinstance(value, float):
        raise TypeError("Ningún float en contenido financiero canónico.")
    if isinstance(value, Decimal):
        return format(parse_money(value), "f")
    if value is None or type(value) in (bool, int):
        return value
    if isinstance(value, str):
        if len(value) > 8192:
            raise ValueError("Texto demasiado largo.")
        value.encode("utf-8")
        return value
    if isinstance(value, Mapping):
        if len(value) > 256 or any(type(key) is not str for key in value):
            raise ValueError("Mapping acotado con claves string requerido.")
        if set(value) & _RESERVED:
            raise ValueError("Identidad/autoridad no pueden formar parte de argumentos del modelo.")
        return {key: exact_json(item, depth=depth + 1) for key, item in value.items()}
    if isinstance(value, (tuple, list)) and len(value) <= 256:
        return [exact_json(item, depth=depth + 1) for item in value]
    raise TypeError("Tipo no admitido en contenido canónico.")


def canonical_json(value: object) -> str:
    result = json.dumps(exact_json(value), ensure_ascii=False, sort_keys=True,
                        separators=(",", ":"), allow_nan=False)
    if len(result.encode("utf-8")) > 65536:
        raise ValueError("Contenido canónico excede 64 KiB.")
    return result


def strict_json(text: str) -> object:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Claves JSON duplicadas.")
            result[key] = value
        return result

    def reject(value):
        raise ValueError("JSON numérico decimal/no finito no permitido; usa strings.")

    return json.loads(text, object_pairs_hook=pairs, parse_float=reject, parse_constant=reject)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class Principal:
    """Contexto emitido por autenticación del servidor, jamás por una herramienta IA."""

    user_id: int
    session_version: int

    def __post_init__(self):
        positive_id(self.user_id)
        if type(self.session_version) is not int or self.session_version < 0:
            raise ValueError("Versión de sesión requerida.")


@dataclass(frozen=True, slots=True)
class EntryIdentity:
    """Clave derivada exclusivamente de recibos/IDs estables del canal autenticado."""

    namespace: EntryNamespace
    key: str

    def __post_init__(self):
        object.__setattr__(self, "namespace", EntryNamespace(self.namespace))
        if (not isinstance(self.key, str) or len(self.key) != 64
                or any(char not in "0123456789abcdef" for char in self.key)):
            raise ValueError("Huella de identidad de servidor requerida.")

    @classmethod
    def _derive(cls, namespace, components):
        return cls(namespace, digest(canonical_json(components)))

    @classmethod
    def web_api(cls, request_uuid):
        return cls._derive(EntryNamespace.WEB_API, [uuid_text(request_uuid)])

    @classmethod
    def chat(cls, turn_uuid, proposal_revision):
        return cls._derive(EntryNamespace.CHAT, [uuid_text(turn_uuid), positive_id(proposal_revision)])

    @classmethod
    def whatsapp(cls, provider_message_id, action_index=1):
        if not isinstance(provider_message_id, str) or not provider_message_id.strip():
            raise ValueError("ID estable de mensaje requerido.")
        return cls._derive(EntryNamespace.WHATSAPP, [provider_message_id, positive_id(action_index)])

    @classmethod
    def document_review(cls, document_id, revision):
        return cls._derive(EntryNamespace.DOCUMENT_REVIEW, [positive_id(document_id), positive_id(revision)])

    @classmethod
    def whatsapp_scoped(cls, provider, recipient, business_id, message_id, action_index=1, version=1):
        if any(not isinstance(v, str) or not v.strip() or len(v) > 256 for v in (provider, recipient, message_id)):
            raise ValueError('Provider/receptor/recibo real requeridos.')
        return cls._derive(EntryNamespace.WHATSAPP, [provider, recipient, positive_id(business_id),
                          message_id, positive_id(action_index), positive_id(version)])

    @classmethod
    def reviewed_document(cls, review_uuid, document_id, item=1, version=1):
        return cls._derive(EntryNamespace.DOCUMENT_REVIEW, [uuid_text(review_uuid), positive_id(document_id),
                          positive_id(item), positive_id(version)])

    @classmethod
    def recurring(cls, schedule_id, cycle):
        if type(cycle) is not date:
            raise ValueError("Ciclo civil explícito requerido.")
        return cls._derive(EntryNamespace.RECURRING, [positive_id(schedule_id), cycle.isoformat()])

    @classmethod
    def imported(cls, batch_uuid, row_key):
        if not isinstance(row_key, str) or not row_key.strip():
            raise ValueError("Clave estable de fila requerida.")
        return cls._derive(EntryNamespace.IMPORT, [uuid_text(batch_uuid), row_key])

    @classmethod
    def historical(cls, source_type, source_id, revision):
        if source_type not in {"invoice", "invoice_payment", "received_invoice", "expense", "bank_transaction"}:
            raise ValueError("Origen histórico cerrado requerido.")
        return cls._derive(EntryNamespace.HISTORICAL,
                           [source_type, positive_id(source_id), positive_id(revision)])


@dataclass(frozen=True, slots=True)
class FinancialRequest:
    """Snapshot de comando: sin defaults variables ni IDs de operación en parámetros.

    parameters contiene todos los valores adicionales que cambian el efecto;
    el futuro productor validará su semántica por comando antes de aprobarlo.
    El núcleo no transforma una propuesta IA en una orden ejecutable.
    """

    command_type: CommandType
    target_id: int | None
    amount: Decimal | str | None
    effective_on: date | str | None
    expected_revision: int | None
    reason: str | None
    parameters: Mapping[str, object]
    currency: Currency = Currency.EUR
    command_version: int = 1

    def __post_init__(self):
        object.__setattr__(self, "command_type", CommandType(self.command_type))
        object.__setattr__(self, "currency", Currency(self.currency))
        if type(self.command_version) is not int or self.command_version != 1:
            raise ValueError("Versión de comando desconocida.")
        if self.target_id is not None:
            positive_id(self.target_id)
        if self.expected_revision is not None:
            positive_id(self.expected_revision)
            if self.target_id is None:
                raise ValueError("Revisión requiere entidad destino.")
        if self.amount is not None:
            if not isinstance(self.amount, (Decimal, str)):
                raise TypeError("Importe Decimal/string requerido.")
            raw = parse_money(self.amount)
            amount = quantize_currency(raw)
            if raw != amount:
                raise ValueError("Importe final con fracción de céntimo.")
            object.__setattr__(self, "amount", amount)
        if self.effective_on is not None:
            if type(self.effective_on) is date:
                value = self.effective_on.isoformat()
            elif isinstance(self.effective_on, str):
                value = date.fromisoformat(self.effective_on).isoformat()
                if value != self.effective_on:
                    raise ValueError("Fecha ISO YYYY-MM-DD requerida.")
            else:
                raise ValueError("Fecha civil requerida.")
            object.__setattr__(self, "effective_on", value)
        if self.reason is not None and (not isinstance(self.reason, str) or not self.reason.strip()):
            raise ValueError("Motivo no vacío o null requerido.")
        if not isinstance(self.parameters, Mapping):
            raise ValueError("Parámetros explícitos requeridos.")
        object.__setattr__(self, "parameters", _freeze(exact_json(self.parameters)))
        self.canonical()  # Comprueba también tamaño y Unicode del sobre completo.

    def canonical(self) -> str:
        return canonical_json({
            "canonical_version": 1, "command_type": self.command_type.value,
            "command_version": self.command_version, "target_id": self.target_id,
            "amount": self.amount, "currency": self.currency.value,
            "effective_on": self.effective_on, "expected_revision": self.expected_revision,
            "reason": self.reason, "parameters": self.parameters,
        })

    @property
    def request_hash(self):
        return digest(self.canonical())

    @classmethod
    def from_canonical(cls, text):
        raw = strict_json(text)
        if not isinstance(raw, dict) or raw.pop("canonical_version", None) != 1:
            raise ValueError("Versión canónica desconocida.")
        result = cls(**raw)
        if result.canonical() != text:
            raise ValueError("Request persistido no canónico.")
        return result


@dataclass(frozen=True, slots=True)
class Operation:
    operation_uuid: str
    business_id: int
    state: OperationState
    request: FinancialRequest
    authorization_uuid: str | None
    result_version: int | None
    result: Mapping[str, object] | None

    @classmethod
    def from_row(cls, row):
        if row.get("entry_namespace") == EntryNamespace.HISTORICAL.value and row["state"] in ("approved", "committed"):
            raise StateError("Registro histórico no admite estado ejecutable.")
        request = FinancialRequest.from_canonical(row["request_canonical"])
        if request.request_hash != row["request_hash"]:
            raise ValueError("Huella del request persistido incoherente.")
        result = row["result_canonical"]
        if result is not None:
            if digest(result) != row["result_hash"]:
                raise ValueError("Huella del resultado persistido incoherente.")
            result = _freeze(strict_json(result))
        return cls(uuid_text(row["operation_uuid"]), row["business_id"], OperationState(row["state"]),
                   request, None if row["authorization_uuid"] is None else uuid_text(row["authorization_uuid"]),
                   row["result_version"], result)
