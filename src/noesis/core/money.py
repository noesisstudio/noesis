"""Contrato monetario del núcleo nuevo; no sustituye cálculos legacy.

Entrada canónica con punto decimal, sin exponentes textuales ni separadores.
parse_money conserva hasta 18 decimales; Money cierra a céntimos HALF_UP.
El límite de magnitud corresponde a NUMERIC(20, 4); EUR es la única moneda
operativa. No se deducen tipos fiscales ni se ofrecen conversiones de divisas.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Context, Decimal, ROUND_HALF_UP, localcontext
from enum import Enum
import re


MAX_AMOUNT = Decimal("9999999999999999.9999")
_CANONICAL = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?\Z")


class Currency(str, Enum):
    """Monedas soportadas explícitamente; ampliar con reglas y pruebas propias."""

    EUR = "EUR"

    @property
    def quantum(self) -> Decimal:
        return Decimal("0.01")


def parse_money(value: Decimal | str | int) -> Decimal:
    """Lee un importe exacto sin redondear; nunca acepta float ni bool."""
    if isinstance(value, bool) or not isinstance(value, (Decimal, str, int)):
        raise TypeError("El importe debe ser Decimal, entero o texto decimal canónico.")
    if isinstance(value, str):
        if len(value) > 64 or not _CANONICAL.fullmatch(value):
            raise ValueError("Usa punto decimal, sin espacios, separadores ni exponentes.")
    amount = Decimal(value)
    if not amount.is_finite():
        raise ValueError("El importe debe ser finito.")
    if amount.copy_abs() > MAX_AMOUNT:
        raise ValueError("El importe excede el rango NUMERIC(20, 4).")
    if amount.as_tuple().exponent < -18 or len(amount.as_tuple().digits) > 64:
        raise ValueError("El importe admite como máximo 18 decimales de entrada.")
    return amount


def quantize_currency(
    value: Decimal | str | int, currency: Currency | str = Currency.EUR,
) -> Decimal:
    """Cierra el importe a la precisión de moneda, HALF_UP, sin contexto global."""
    currency = Currency(currency)
    amount = parse_money(value)
    with localcontext(Context(prec=50, rounding=ROUND_HALF_UP)):
        result = amount.quantize(currency.quantum)
    parse_money(result)  # El acarreo del redondeo también debe caber en BD.
    return result.copy_abs() if result.is_zero() else result


@dataclass(frozen=True, slots=True)
class Money:
    """Importe final inmutable en una moneda; construirlo es un límite de redondeo."""

    amount: Decimal
    currency: Currency = Currency.EUR

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise TypeError("Money requiere Decimal; usa Money.parse para texto o enteros.")
        currency = Currency(self.currency)
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "amount", quantize_currency(self.amount, currency))

    @classmethod
    def parse(cls, value: Decimal | str | int, currency: Currency | str = Currency.EUR) -> Money:
        return cls(parse_money(value), Currency(currency))

    def to_decimal_string(self) -> str:
        """Valor para JSON/TEXT; nunca convertirlo a float para serializar."""
        return format(self.amount, "f")

    def _combine(self, other: Money, *, subtract: bool) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError("No se pueden combinar monedas distintas.")
        with localcontext(Context(prec=50, rounding=ROUND_HALF_UP)):
            amount = self.amount - other.amount if subtract else self.amount + other.amount
        return Money(amount, self.currency)

    def __add__(self, other: Money) -> Money:
        return self._combine(other, subtract=False)

    def __sub__(self, other: Money) -> Money:
        return self._combine(other, subtract=True)
