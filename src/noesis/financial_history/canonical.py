"""Representación v1 propia, determinista; no es RFC 8785 ni una firma."""

from collections.abc import Mapping
from dataclasses import fields
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
import hashlib
import json
from types import MappingProxyType
from uuid import UUID


def instant(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Instante con zona explícita requerido; no asignar zona legacy.")
    return value.astimezone(timezone.utc)


def sha256(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("SHA-256 hexadecimal minúsculo requerido.")
    return value


def version_one(value):
    if type(value) is not int or value != 1:
        raise ValueError("Versión de contrato desconocida.")


def _value(value, depth=0):
    if depth > 16:
        raise ValueError("Evidencia excesivamente anidada.")
    if isinstance(value, float):
        raise TypeError("Ningún float canónico; conservar bits/texto en RawMonetaryEvidence.")
    if isinstance(value, CanonicalContract):
        return {f.name: _value(getattr(value, f.name), depth + 1) for f in fields(value)}
    if isinstance(value, Enum):
        return _value(value.value, depth + 1)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Decimal canónico finito requerido.")
        if len(value.as_tuple().digits) > 1100 or abs(value.as_tuple().exponent) > 1100:
            raise ValueError("Decimal fuera del límite de evidencia.")
        return format(value, "f")
    if isinstance(value, datetime):
        return instant(value).isoformat(timespec="microseconds")
    if type(value) is date:
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if value is None or type(value) in (bool, int):
        return value
    if isinstance(value, str):
        if len(value) > 4096:
            raise ValueError("Texto canónico demasiado grande.")
        value.encode("utf-8")
        return value
    if isinstance(value, Mapping):
        if len(value) > 256 or any(type(k) is not str for k in value):
            raise ValueError("Mapa acotado con claves string requerido.")
        return {k: _value(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (tuple, list)) and len(value) <= 256:
        return [_value(v, depth + 1) for v in value]
    raise TypeError("Tipo ajeno al contrato de evidencia.")


def canonical_bytes(value):
    result = json.dumps(_value(value), sort_keys=True, ensure_ascii=False,
                        separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(result) > 131072:
        raise ValueError("Contrato supera 128 KiB; no copiar archivos ni conversaciones.")
    return result


def freeze(value):
    """Copia profunda validada; listas conservan orden y se vuelven tuplas."""
    canonical_bytes(value)
    if isinstance(value, Mapping):
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(v) for v in value)
    return value


class CanonicalContract:
    __slots__ = ()

    def canonical_bytes(self):
        return canonical_bytes({"canonical_version": 1, "contract": type(self).__name__, "value": self})

    @property
    def content_hash(self):
        return hashlib.sha256(self.canonical_bytes()).hexdigest()
