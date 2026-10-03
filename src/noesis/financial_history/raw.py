"""Extracción física: float solo para inspeccionar bits, jamás como Money."""

from dataclasses import dataclass
from decimal import Context, Decimal, ROUND_HALF_UP, localcontext
import math
import struct

from noesis.core.money import MAX_AMOUNT
from .canonical import CanonicalContract
from .money_evidence import (
    CorroborationStatus as CS, MoneyProvenance as MP, MoneyReason as MR,
    RawMonetaryEvidence, StorageEngine, StorageType,
)


@dataclass(frozen=True, slots=True)
class MoneyObservation(CanonicalContract):
    storage_class: str
    driver_kind: str
    driver_value: str | None
    sql_text: str | None
    sql_bits: str | None
    evidence: RawMonetaryEvidence | None
    invalid_reason: str | None


def observe_money(engine, value, storage_class, sql_text, sql_bits=None):
    """Conserva valor del driver y SQL antes de calcular cualquier diagnóstico."""
    engine = StorageEngine(engine)
    kind = type(value).__name__
    driver = None if value is None else repr(value) if isinstance(value, float) else str(value)
    raw = None
    invalid = None
    if value is None:
        raw = RawMonetaryEvidence(engine, StorageType.NULL, None, None, None, None, None,
            None, None, MP.UNKNOWN, CS.UNKNOWN, None, (), MR.UNKNOWN)
    elif isinstance(value, float):
        bits = struct.pack('!d', value).hex()
        if sql_bits is not None and bits != sql_bits:
            raise ValueError('Bits del driver no coinciden con float8send.')
        number = Decimal.from_float(value) if math.isfinite(value) else None
        candidate = delta = None
        reason = MR.NON_FINITE if number is None else MR.BINARY_UNCORROBORATED
        if number is not None:
            with localcontext(Context(prec=1200, rounding=ROUND_HALF_UP)):
                cent = number.quantize(Decimal('0.01'))
                distance = number - cent
                # ULP distingue residuo representacional de subcéntimo material;
                # nunca se utiliza para acreditar el decimal original.
                if abs(distance) > max(Decimal.from_float(math.ulp(value)) * 2, Decimal('0.000000000001')):
                    reason = MR.SUBCENT
                if abs(cent) <= MAX_AMOUNT:
                    candidate, delta = cent, distance
        raw = RawMonetaryEvidence(engine, StorageType.DOUBLE if engine == StorageEngine.POSTGRES else StorageType.REAL,
            driver, None, bits, number, None, candidate, delta, MP.LEGACY_BINARY,
            CS.UNCORROBORATED, None, (), reason)
    elif isinstance(value, (Decimal, str)) and storage_class in ('numeric', 'text'):
        try:
            number = Decimal(value)
            with localcontext(Context(prec=1200)):
                reason = MR.EXACT_VALUE if number == number.quantize(Decimal('0.01')) else MR.SUBCENT
            raw = RawMonetaryEvidence(engine, StorageType.NUMERIC if engine == StorageEngine.POSTGRES else StorageType.TEXT,
                str(value), number, None, None, None, None, None, MP.EXACT, CS.EXACT, None, (), reason)
        except (ValueError, ArithmeticError):
            invalid = 'invalid_exact_storage'
    else:
        invalid = 'unsupported_storage_class'
    result = MoneyObservation(str(storage_class), kind, driver, sql_text, sql_bits, raw, invalid)
    result.canonical_bytes()
    return result
