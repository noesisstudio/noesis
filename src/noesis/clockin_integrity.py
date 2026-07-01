"""Sellado determinista de fichajes para detectar cualquier manipulación.

La cadena se calcula únicamente con los datos originales del fichaje. Las
correcciones viven en una tabla aparte y nunca cambian el sello histórico.
"""

from __future__ import annotations

import hashlib
import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping


def _canonical(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("El sello no admite números no finitos.")
        return format(value, ".15g")
    return str(value)


def clockin_seal(row: Mapping[str, Any], prev_seal: str | None = None) -> str:
    """Calcula SHA-256 según el contrato inmutable del registro de jornada."""
    values = (
        row.get("business_id"),
        row.get("worker_id"),
        row.get("action"),
        row.get("at"),
        row.get("source"),
        row.get("lat"),
        row.get("lng"),
        row.get("job_id"),
        prev_seal if prev_seal is not None else row.get("prev_seal"),
    )
    payload = "|".join(_canonical(value) for value in values)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
