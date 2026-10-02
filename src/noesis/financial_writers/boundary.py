"""Resultados internos y lectura del efecto real dentro de la transacción.

REAL/DOUBLE históricos no recuperan precisión. Se exponen Decimal y procedencia
binaria explícita; entradas exactas se conservan antes de adaptar a esas columnas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Context, Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP, localcontext
import hashlib
import inspect
import json
from types import MappingProxyType
from typing import Mapping

from ..core.locks import lock_business
from ..core.money import Currency, parse_money
from ..core.persistence import FinancialSession

TABLES = {
    "invoice": "invoices",
    "invoice_payment": "invoice_payments",
    "received_invoice": "received_invoices",
    "expense": "expenses",
    "bank_transaction": "bank_transactions",
    "invoice_cancellation_record": "invoice_cancellation_records",
}
MONEY_FIELDS = {
    "invoice": ("base", "vat_amount", "irpf_amount", "total"),
    "invoice_payment": ("amount",),
    "received_invoice": ("base", "vat_amount", "irpf_amount", "total"),
    "expense": ("amount",),
    "bank_transaction": ("amount",),
    "invoice_cancellation_record": (),
}
MUTABLE = {"received_invoice", "expense", "bank_transaction"}


def freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(freeze(v) for v in value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _json(value):
    if isinstance(value, Mapping):
        return {k: _json(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_json(v) for v in value]
    if isinstance(value, Decimal):
        return format(value, "f")
    return value


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    business_id: int
    source_type: str
    source_id: int
    revision: int
    fingerprint: str
    amounts: Mapping
    data: Mapping
    money_provenance: str = "legacy_binary_storage"
    deleted: bool = False


@dataclass(frozen=True, slots=True)
class WriterResult:
    legacy: Mapping | None
    snapshots: tuple[SourceSnapshot, ...]
    exact_inputs: Mapping
    input_provenance: str
    payment_id: int | None = None
    observations: tuple = ()
    prepared_values: tuple = ()

    def legacy_value(self):
        # Los consumidores públicos conservan dict/list y dinero float.
        def thaw(v):
            if isinstance(v, Mapping):
                return {k: thaw(x) for k, x in v.items()}
            if isinstance(v, tuple):
                return [thaw(x) for x in v]
            if isinstance(v, Decimal):
                return float(v)
            return v

        return thaw(self.legacy)


def connection(value):
    conn = value.borrowed_connection if isinstance(value, FinancialSession) else value
    raw = conn.raw
    if conn.dialect == "sqlite":
        active = raw.in_transaction
    else:
        from psycopg.pq import TransactionStatus

        active = raw.info.transaction_status == TransactionStatus.INTRANS
    if not active:
        raise ValueError("El propietario debe iniciar la transacción exterior.")
    return conn


def snapshot(conn, business_id, source_type, source_id, *, deleted=False):
    kind = getattr(source_type, "value", source_type)
    if kind == "cancellation_record":
        kind = "invoice_cancellation_record"
    table = TABLES[kind]
    lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
    row = conn.execute_exact(
        f"SELECT * FROM {table} WHERE business_id=? AND id=?" + lock,
        (business_id, source_id),
    ).fetchone()
    if not row:
        return None
    data = dict(row)
    if kind == "invoice":
        # Status de cobro no cambia la revisión de la emisión congelada.
        from ..migrations import _IMMUTABLE_INVOICE_FIELDS

        revision_data = {k: row.get(k) for k in _IMMUTABLE_INVOICE_FIELDS}
        lines = conn.execute_exact(
            "SELECT * FROM invoice_lines WHERE business_id=? AND invoice_id=? ORDER BY position,id",
            (business_id, source_id),
        ).fetchall()
        data["lines"] = lines
        revision_data["lines"] = lines
        revision_data["identity"] = (business_id, source_id)
        for key, table_name in (
            ("fiscal_record", "invoice_records"),
            ("document_profile", "document_profiles"),
        ):
            if key == "fiscal_record":
                sql = f"SELECT * FROM {table_name} WHERE business_id=? AND invoice_id=?"
                params = (business_id, source_id)
            else:
                sql = f"SELECT * FROM {table_name} WHERE business_id=? AND id=?"
                params = (business_id, row.get("document_profile_id"))
            data[key] = conn.execute_exact(sql, params).fetchone()
    else:
        revision_data = data
    digest = hashlib.sha256(
        json.dumps(
            _json(freeze(revision_data)), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    revision = int(row["_financial_revision"]) if kind in MUTABLE else (int(digest[:15], 16) + 1)
    if kind in {"received_invoice", "expense"}:
        fk = "received_invoice_id" if kind == "received_invoice" else "expense_id"
        data["documents"] = conn.execute_exact(
            f"SELECT * FROM documents WHERE business_id=? AND {fk}=? ORDER BY id",
            (business_id, source_id),
        ).fetchall()
        data["classifications"] = conn.execute_exact(
            f"SELECT c.* FROM document_classifications c JOIN documents d ON d.id=c.document_id "
            f"AND d.business_id=c.business_id WHERE d.business_id=? AND d.{fk}=? ORDER BY c.id",
            (business_id, source_id),
        ).fetchall()
    amounts = {
        k: None
        if row.get(k) is None
        else Decimal(str(row[k])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        for k in MONEY_FIELDS[kind]
    }
    return SourceSnapshot(
        business_id,
        kind,
        int(source_id),
        revision,
        digest,
        freeze(amounts),
        freeze(data),
        deleted=deleted,
    )


def revision_reader(business_id):
    """Reader de confianza para 1.3; origen eliminado/ajeno no tiene revisión."""

    def read(session, source_type, source_id):
        conn = connection(session)
        lock_business(conn, business_id)
        captured = snapshot(conn, business_id, source_type, source_id)
        return captured.revision if captured else None

    return read


class WriterConnection:
    """Adaptación localizada a columnas legacy; sin autoridad transaccional."""

    def __init__(self, conn, *, legacy):
        self.conn, self.legacy = conn, legacy
        self.dialect = conn.dialect
        self.payments = []
        self.observations = []
        self.prepared_values = []

    def execute(self, sql, params=()):
        # Decimal existe antes de la adaptación; el esquema legacy sigue binario.
        exact = tuple((i, v) for i, v in enumerate(params) if isinstance(v, Decimal))
        if exact:
            self.prepared_values.append((sql, exact))
        adapted = tuple(float(v) if isinstance(v, Decimal) else v for v in params)
        cursor = (self.conn.execute(sql, adapted) if self.legacy else
                  _WriterCursor(self.conn.execute_exact(sql, adapted)))
        if sql.lstrip().startswith("INSERT INTO invoice_payments"):
            row = cursor.fetchone()
            self.payments.append(int(row["id"]))
            return _CapturedCursor(cursor, row)
        return cursor

    def execute_exact(self, sql, params=()):
        return self.conn.execute_exact(sql, params)


class _CapturedCursor:
    def __init__(self, cursor, row):
        self.cursor, self.row = cursor, row

    @property
    def rowcount(self):
        return self.cursor.rowcount

    def fetchone(self):
        row, self.row = self.row, None
        return row


class _WriterCursor:
    """Fechas compatibles con el motor prestado; nunca Decimal → float al leer.

    REAL/DOUBLE de origen permanece binario hasta el snapshot explícito.
    No utiliza la normalización monetaria de la fachada pública.
    """

    def __init__(self, cursor):
        self.cursor = cursor

    @property
    def rowcount(self):
        return self.cursor.rowcount

    @staticmethod
    def _row(row):
        from ..db import Record
        if row is None:
            return None
        return Record((k,v.isoformat() if isinstance(v,(date,datetime)) else v) for k,v in row.items())

    def fetchone(self):
        return self._row(self.cursor.fetchone())

    def fetchall(self):
        return [self._row(row) for row in self.cursor.fetchall()]


def positive_money(value, label, *, legacy=False):
    from .. import db

    try:
        number = Decimal(str(value)) if legacy else parse_money(value)
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise ValueError(f"{label} no es un importe válido.") from exc
    if not number.is_finite() or number <= 0 or number > Decimal("10000000"):
        # Mismos mensajes y límites de la API legacy.
        db._positive_money(value, label)
    rounded = number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if not legacy and rounded <= 0:
        raise ValueError(f"{label} debe ser positivo después del redondeo.")
    return rounded


def optional_money(conn, value):
    if value in (None, ""):
        return None
    number = (
        Decimal(str(int(value) if isinstance(value, bool) else value))
        if conn.legacy
        else parse_money(value)
    )
    if not number.is_finite() or number < 0:
        raise ValueError("El importe debe ser finito y no negativo.")
    if conn.legacy:
        return Decimal(str(round(float(value), 2)))
    return number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _run(
    mutation,
    borrowed,
    args,
    kwargs,
    *,
    kind,
    identity=None,
    legacy=False,
    expected_revision=None,
    target_kind=None,
    target_identity=None,
):
    conn = connection(borrowed)
    bound = inspect.signature(mutation).bind(conn, *args, **kwargs)
    bound.apply_defaults()
    business_id = int(bound.arguments["business_id"])
    lock_business(conn, business_id)
    # Capturar la entrada antes de cualquier normalizador legacy.
    inputs = {k: v for k, v in bound.arguments.items() if k != "conn"}

    def check(v):
        if isinstance(v, float) and not legacy:
            raise TypeError("Writer exacto no admite float.")
        if isinstance(v, Decimal):
            parse_money(v)
        if isinstance(v, Mapping):
            for x in v.values():
                check(x)
        elif isinstance(v, (tuple, list)):
            for x in v:
                check(x)

    check(inputs)
    if not legacy and "currency" in inputs:
        Currency(inputs["currency"])
    exact_inputs = freeze(inputs)
    before = snapshot(conn, business_id, kind, bound.arguments[identity]) if identity else None
    if not legacy and before and before.data.get("currency", "EUR") != "EUR":
        raise ValueError("El writer exacto solo admite EUR.")
    expected_source = (
        snapshot(conn, business_id, target_kind, bound.arguments[target_identity])
        if target_kind and target_identity
        else before
    )
    if expected_revision is not None and (
        not expected_source or expected_source.revision != expected_revision
    ):
        raise ValueError("Revisión de origen antigua; vuelve a revisar.")
    proxy = WriterConnection(conn, legacy=legacy)
    value = mutation(proxy, *args, **kwargs)
    source_id = bound.arguments[identity] if identity else (value or {}).get("id")
    deleted = mutation.__name__.startswith("_mutate_delete_")
    captured = (
        SourceSnapshot(
            before.business_id,
            before.source_type,
            before.source_id,
            before.revision,
            before.fingerprint,
            before.amounts,
            before.data,
            before.money_provenance,
            True,
        )
        if deleted and before
        else snapshot(conn, business_id, kind, source_id)
        if source_id is not None
        else None
    )
    snapshots = [captured] if captured else []
    for payment_id in proxy.payments:
        payment = snapshot(conn, business_id, "invoice_payment", payment_id)
        if not captured or captured.source_type != "invoice_payment":
            snapshots.append(payment)
    if kind in {"invoice_payment", "bank_transaction"} and proxy.payments:
        parent_id = snapshots[-1].data["invoice_id"]
        snapshots.append(snapshot(conn, business_id, "invoice", parent_id))
    return WriterResult(
        freeze(value),
        tuple(snapshots),
        exact_inputs,
        "legacy_input_allowed" if legacy else "exact_input",
        proxy.payments[-1] if proxy.payments else None,
        freeze(proxy.observations),
        tuple(proxy.prepared_values),
    )


def run(*args, **kwargs):
    # HALF_UP explícito en moneda; HALF_EVEN para quantize legacy no anotado.
    # Un contexto de quien llama no puede reducir la precisión de la frontera.
    with localcontext(Context(prec=50, rounding=ROUND_HALF_EVEN)):
        return _run(*args, **kwargs)


def observe(result):
    """Solo el propietario llama tras commit; no pertenece al writer."""
    from .. import value_ledger

    for name, args, kwargs in result.observations:
        values = dict(kwargs)
        if "metadata" in values:
            values["metadata"] = dict(values["metadata"])
        getattr(value_ledger, name)(*args, **values)
