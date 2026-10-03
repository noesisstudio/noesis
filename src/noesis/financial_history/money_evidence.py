"""Evidencia de almacenamiento; un candidato a céntimos nunca es Money aprobado."""

from dataclasses import dataclass
from decimal import Context, Decimal, ROUND_HALF_UP, localcontext
from enum import Enum
import math
import re
import struct

from noesis.economic_events.contracts import _money
from .canonical import CanonicalContract, sha256, version_one


class StorageEngine(str, Enum):
    SQLITE = "sqlite"
    POSTGRES = "postgres"


class StorageType(str, Enum):
    NUMERIC = "numeric"
    TEXT = "text"
    REAL = "real"
    DOUBLE = "double_precision"
    NULL = "null"


class MoneyProvenance(str, Enum):
    EXACT = "exact"
    LEGACY_BINARY = "legacy_binary"
    UNKNOWN = "unknown"


class CorroborationStatus(str, Enum):
    EXACT = "exact"
    CORROBORATED = "corroborated"
    UNCORROBORATED = "uncorroborated"
    UNKNOWN = "unknown"


class MoneyReason(str, Enum):
    EXACT_VALUE = "exact_value"
    UNKNOWN = "unknown"
    BINARY_UNCORROBORATED = "binary_uncorroborated"
    BINARY_CORROBORATED = "binary_corroborated"
    SUBCENT = "subcent"
    NON_FINITE = "non_finite"


def raw_decimal(value):
    """Sin redondeo/rango Money: los bits binary64 pueden exigir 1074 decimales."""
    if not isinstance(value, (str, Decimal)):
        raise TypeError("Decimal/string de evidencia requerido; ningún float.")
    if isinstance(value, str) and (len(value) > 1200 or not re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]+)?", value)):
        raise ValueError("Representación decimal cruda inválida.")
    result = Decimal(value)
    if not result.is_finite() or abs(result.as_tuple().exponent) > 1100 or len(result.as_tuple().digits) > 1100:
        raise ValueError("Evidencia decimal no finita/fuera de límite.")
    return result


@dataclass(frozen=True, slots=True)
class RawMonetaryEvidence(CanonicalContract):
    storage_engine: StorageEngine
    storage_type: StorageType
    raw_representation: str | None
    exact_decimal: Decimal | str | None
    binary_representation: str | None
    binary_decimal: Decimal | str | None
    display_representation: str | None
    candidate_cent_value: Decimal | str | None
    delta: Decimal | str | None
    provenance: MoneyProvenance
    corroboration: CorroborationStatus
    corroborated_decimal: Decimal | str | None
    corroborating_hashes: tuple[str, ...]
    reason: MoneyReason
    contract_version: int = 1

    def __post_init__(self):
        version_one(self.contract_version)
        for name, kind in (("storage_engine", StorageEngine), ("storage_type", StorageType),
                           ("provenance", MoneyProvenance), ("corroboration", CorroborationStatus),
                           ("reason", MoneyReason)):
            object.__setattr__(self, name, kind(getattr(self, name)))
        for name in ("exact_decimal", "binary_decimal", "delta"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, raw_decimal(value))
        for name in ("candidate_cent_value", "corroborated_decimal"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _money(value))
        if not isinstance(self.corroborating_hashes, (tuple, list)):
            raise TypeError("Referencias de corroboración tipadas requeridas.")
        hashes = tuple(sorted(sha256(h) for h in self.corroborating_hashes))
        if len(set(hashes)) != len(hashes):
            raise ValueError("Corroboración duplicada.")
        object.__setattr__(self, "corroborating_hashes", hashes)
        if self.storage_type == StorageType.NULL:
            if (any(getattr(self, n) is not None for n in ("raw_representation", "exact_decimal",
                    "binary_representation", "binary_decimal", "display_representation", "candidate_cent_value",
                    "delta", "corroborated_decimal")) or hashes or self.provenance != MoneyProvenance.UNKNOWN
                    or self.corroboration != CorroborationStatus.UNKNOWN or self.reason != MoneyReason.UNKNOWN):
                raise ValueError("NULL desconocido no tiene valor ni candidato cero.")
        elif self.storage_type in (StorageType.NUMERIC, StorageType.TEXT):
            expected_type = StorageType.NUMERIC if self.storage_engine == StorageEngine.POSTGRES else StorageType.TEXT
            if self.storage_type != expected_type or self.provenance != MoneyProvenance.EXACT:
                raise ValueError("Procedencia exacta incompatible con motor/tipo.")
            if self.exact_decimal is None or raw_decimal(self.raw_representation) != self.exact_decimal:
                raise ValueError("Decimal exacto debe concordar con representación almacenada.")
            if self.binary_representation is not None or self.binary_decimal is not None:
                raise ValueError("Almacenamiento exacto no es binario.")
            if self.corroboration != CorroborationStatus.EXACT or hashes or self.corroborated_decimal is not None:
                raise ValueError("Valor exacto no requiere corroboración binaria.")
            self._diagnostic(self.exact_decimal)
            with localcontext(Context(prec=1200)):
                final = self.exact_decimal == self.exact_decimal.quantize(Decimal("0.01"))
            expected = MoneyReason.EXACT_VALUE if final else MoneyReason.SUBCENT
            if self.reason != expected:
                raise ValueError("Razón monetaria incompatible con precisión cruda.")
        else:
            expected_type = StorageType.DOUBLE if self.storage_engine == StorageEngine.POSTGRES else StorageType.REAL
            if self.storage_type != expected_type or self.provenance != MoneyProvenance.LEGACY_BINARY:
                raise ValueError("Procedencia binaria incompatible con motor/tipo.")
            if self.exact_decimal is not None:
                raise ValueError("REAL/DOUBLE nunca acredita el decimal original.")
            bits = self.binary_representation
            if not isinstance(bits, str) or not re.fullmatch(r"[0-9a-f]{16}", bits):
                raise ValueError("Bits IEEE754 binary64 en orden big-endian requeridos.")
            binary = struct.unpack("!d", bytes.fromhex(bits))[0]
            if not isinstance(self.raw_representation, str) or len(self.raw_representation) > 64:
                raise ValueError("Texto de lectura binaria requerido.")
            if not math.isfinite(binary):
                if (self.reason != MoneyReason.NON_FINITE or self.binary_decimal is not None
                        or self.candidate_cent_value is not None or self.delta is not None
                        or self.corroboration != CorroborationStatus.UNCORROBORATED
                        or hashes or self.corroborated_decimal is not None):
                    raise ValueError("No finito solo admite incidencia; ningún candidato.")
                text_value = float(self.raw_representation)
                if math.isfinite(text_value) or math.isnan(binary) != math.isnan(text_value):
                    raise ValueError("Texto/bits no finitos incompatibles.")
                if math.isinf(binary) and binary != text_value:
                    raise ValueError("Signo infinito incompatible.")
            else:
                if self.binary_decimal != Decimal.from_float(binary):
                    raise ValueError("Decimal de bits incompatible; no es el decimal original.")
                if struct.pack("!d", float(self.raw_representation)).hex() != bits:
                    raise ValueError("Texto de lectura no reproduce los bits.")
                self._diagnostic(self.binary_decimal)
                if self.corroboration == CorroborationStatus.CORROBORATED:
                    if not hashes or self.corroborated_decimal is None or self.reason != MoneyReason.BINARY_CORROBORATED:
                        raise ValueError("Corroboración exige valor explícito y evidencia referenciada.")
                    # Solo contraste de almacenamiento: nunca obtiene Money desde float.
                    # El signo del cero binario no cambia el cero económico conocido.
                    if Decimal.from_float(float(self.corroborated_decimal)) != self.binary_decimal:
                        raise ValueError("Decimal corroborante no reproduce el valor binario almacenado; incidencia.")
                elif (self.corroboration != CorroborationStatus.UNCORROBORATED or hashes
                      or self.corroborated_decimal is not None
                      or self.reason not in (MoneyReason.BINARY_UNCORROBORATED, MoneyReason.SUBCENT)):
                    raise ValueError("Sin corroboración el candidato sigue siendo diagnóstico.")
        if self.display_representation is not None:
            if self.reason == MoneyReason.NON_FINITE:
                if self.display_representation not in ("NaN", "Infinity", "-Infinity"):
                    raise ValueError("Display no finito cerrado requerido.")
            else:
                raw_decimal(self.display_representation)
        self.canonical_bytes()

    def _diagnostic(self, raw):
        if (self.candidate_cent_value is None) != (self.delta is None):
            raise ValueError("Candidato y delta deben coexistir o ser ambos desconocidos.")
        if self.candidate_cent_value is not None:
            with localcontext(Context(prec=1200, rounding=ROUND_HALF_UP)):
                if raw.quantize(Decimal("0.01")) != self.candidate_cent_value or raw - self.candidate_cent_value != self.delta:
                    raise ValueError("Candidato/delta diagnóstico no reproduce el valor crudo.")

    def validates_declared_amount(self, value):
        """Comprueba un importe ya declarado; nunca convierte un candidato en Money."""
        if value is None:
            return self.storage_type == StorageType.NULL
        final = _money(value)
        if self.provenance == MoneyProvenance.EXACT:
            return self.exact_decimal == final
        return (self.corroboration == CorroborationStatus.CORROBORATED
                and self.corroborated_decimal == final)
