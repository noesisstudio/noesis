"""Importación bancaria local y sugerencias explicables de conciliación.

No conecta cuentas ni mueve dinero. Lee un CSV aportado por el titular, elimina
duplicados y propone qué ingreso podría corresponder a una factura. La confirmación
final siempre ocurre en la capa web y queda registrada como cobro.
"""

from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import io
import re
import unicodedata

from . import db


_DATE_FIELDS = ("fecha", "fechaoperacion", "fechavalor", "date", "bookedon")
_AMOUNT_FIELDS = ("importe", "amount", "monto", "valor")
_DESCRIPTION_FIELDS = ("concepto", "descripcion", "description", "detalle")
_COUNTERPARTY_FIELDS = ("ordenante", "contraparte", "counterparty", "titular", "nombre")
_REFERENCE_FIELDS = ("referencia", "reference", "ref")
_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y")


def _plain(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in text if not unicodedata.combining(char)).lower()


def _key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", _plain(value))


def _first(row: dict[str, str], names: tuple[str, ...]) -> str:
    normalized = {_key(key): str(value or "").strip() for key, value in row.items()}
    for name in names:
        if normalized.get(name):
            return normalized[name]
    return ""


def _date(value: str) -> str:
    raw = (value or "").strip()
    for pattern in _DATE_FORMATS:
        try:
            return datetime.strptime(raw[:10], pattern).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"No entiendo la fecha «{raw[:30]}» del extracto.")


def _amount(value: str) -> float:
    raw = str(value or "").strip().replace("\u00a0", "").replace(" ", "")
    negative = raw.startswith("(") and raw.endswith(")")
    raw = raw.strip("()").replace("€", "").replace("EUR", "").replace("eur", "")
    raw = re.sub(r"[^0-9,.-]", "", raw)
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        number = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"No entiendo el importe «{value[:30]}» del extracto.") from exc
    if negative:
        number = -number
    if not number.is_finite() or number == 0:
        raise ValueError("El extracto contiene un importe vacío o igual a cero.")
    return float(number.quantize(Decimal("0.01")))


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("No se pudo leer la codificación del CSV.")


def _rows(content: bytes) -> list[dict[str, str]]:
    text = _decode(content)
    if not text.strip():
        raise ValueError("El extracto está vacío.")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = None
    reader = (
        csv.DictReader(io.StringIO(text), dialect=dialect)
        if dialect is not None
        else csv.DictReader(io.StringIO(text), delimiter=";")
    )
    if not reader.fieldnames:
        raise ValueError("El CSV no tiene una fila de cabeceras.")
    rows = [dict(row) for row in reader if any(str(value or "").strip() for value in row.values())]
    if len(rows) > 5000:
        raise ValueError("Importa como máximo 5.000 movimientos cada vez.")
    return rows


def _fingerprint(booked_on: str, amount: float, description: str,
                 counterparty: str, reference: str, occurrence: int) -> str:
    source = "|".join((
        booked_on, f"{amount:.2f}", _plain(description).strip(),
        _plain(counterparty).strip(), _plain(reference).strip(), str(occurrence),
    ))
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def import_csv(business_id: int, content: bytes) -> dict:
    """Importa y propone coincidencias; devuelve solo contadores operativos."""
    created = 0
    duplicates = 0
    occurrences: dict[tuple[str, float, str, str, str], int] = {}
    for row in _rows(content):
        booked_on = _date(_first(row, _DATE_FIELDS))
        amount = _amount(_first(row, _AMOUNT_FIELDS))
        description = _first(row, _DESCRIPTION_FIELDS)
        counterparty = _first(row, _COUNTERPARTY_FIELDS)
        reference = _first(row, _REFERENCE_FIELDS)
        identity = (booked_on, amount, description, counterparty, reference)
        occurrences[identity] = occurrences.get(identity, 0) + 1
        saved = db.add_bank_transaction(
            business_id,
            import_hash=_fingerprint(
                booked_on, amount, description, counterparty, reference,
                occurrences[identity],
            ),
            booked_on=booked_on,
            amount=amount,
            description=description,
            counterparty=counterparty,
            reference=reference,
        )
        if saved:
            created += 1
        else:
            duplicates += 1
    suggested = suggest_pending(business_id)
    return {"created": created, "duplicates": duplicates, "suggested": suggested}


def suggest_pending(business_id: int) -> int:
    invoices = db.pending_payments(business_id)
    suggested = 0
    for movement in db.list_bank_transactions(business_id, status="imported", limit=500):
        if float(movement["amount"]) <= 0:
            continue
        haystack = _key(" ".join(
            str(movement.get(field) or "")
            for field in ("description", "counterparty", "reference")
        ))
        candidates = []
        for invoice in invoices:
            score = 0
            reasons = []
            if abs(float(invoice["remaining_amount"]) - float(movement["amount"])) < 0.005:
                score += 60
                reasons.append("mismo importe")
            number = _key(invoice.get("number"))
            if number and number in haystack:
                score += 60
                reasons.append("referencia de factura")
            client = _key(invoice.get("client_name"))
            if len(client) >= 4 and client in haystack:
                score += 35
                reasons.append("nombre del cliente")
            concept = _key(invoice.get("concept"))
            if len(concept) >= 6 and concept in haystack:
                score += 15
                reasons.append("concepto")
            if score:
                candidates.append((score, invoice, reasons))
        candidates.sort(key=lambda item: item[0], reverse=True)
        if not candidates or candidates[0][0] < 60:
            continue
        if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
            continue
        score, invoice, reasons = candidates[0]
        db.suggest_bank_transaction(
            movement["id"], business_id, invoice["id"],
            score=score, reason="Coincide por " + ", ".join(reasons) + ".",
        )
        suggested += 1
    return suggested
