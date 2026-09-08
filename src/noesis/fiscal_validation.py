"""Comprobaciones deterministas para datos fiscales propuestos por OCR/IA.

Estas funciones no corrigen ni contabilizan nada. Solo detectan incoherencias para
que el titular revise el borrador antes de confirmarlo.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


_NIF_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"  # pragma: allowlist secret -- tabla pública NIF
_CIF_CONTROL_LETTERS = "JABCDEFGHI"


def _clean_identifier(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def valid_spanish_tax_id(value: str | None) -> bool:
    """Valida NIF de persona, NIE y NIF de entidad españoles."""
    tax_id = _clean_identifier(value)
    if not tax_id:
        return False
    if re.fullmatch(r"\d{8}[A-Z]", tax_id):
        return tax_id[-1] == _NIF_LETTERS[int(tax_id[:8]) % 23]
    if re.fullmatch(r"[XYZ]\d{7}[A-Z]", tax_id):
        number = str("XYZ".index(tax_id[0])) + tax_id[1:8]
        return tax_id[-1] == _NIF_LETTERS[int(number) % 23]
    if not re.fullmatch(r"[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]", tax_id):
        return False
    digits = [int(char) for char in tax_id[1:8]]
    even_sum = sum(digits[index] for index in (1, 3, 5))
    odd_sum = sum(sum(divmod(digits[index] * 2, 10)) for index in (0, 2, 4, 6))
    control = (10 - (even_sum + odd_sum) % 10) % 10
    control_digit = str(control)
    control_letter = _CIF_CONTROL_LETTERS[control]
    if tax_id[0] in "ABEH":
        return tax_id[-1] == control_digit
    if tax_id[0] in "KPQS":
        return tax_id[-1] == control_letter
    return tax_id[-1] in {control_digit, control_letter}


def _decimal(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def invoice_draft_issues(draft: dict) -> list[str]:
    """Devuelve avisos comprensibles sin bloquear facturas con datos parciales."""
    issues: list[str] = []
    base = _decimal(draft.get("base"))
    vat = _decimal(draft.get("vat_amount"))
    irpf = _decimal(draft.get("irpf_amount"))
    total = _decimal(draft.get("total"))
    rate = _decimal(draft.get("vat_rate"))
    tolerance = Decimal("0.02")

    if base is not None and rate is not None and vat is not None:
        expected_vat = (base * rate / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if abs(vat - expected_vat) > tolerance:
            issues.append("La cuota de IVA no coincide con la base y el tipo indicados.")
    if base is not None and vat is not None and total is not None:
        expected_total = base + vat - (irpf or Decimal("0.00"))
        if abs(total - expected_total) > tolerance:
            issues.append("El total no coincide con base + IVA − IRPF.")

    for field, label in (
        ("supplier_nif", "El NIF del proveedor"),
        ("customer_nif", "El NIF del cliente"),
    ):
        cleaned = _clean_identifier(draft.get(field))
        looks_spanish = bool(re.fullmatch(
            r"(?:\d{8}[A-Z]|[XYZ]\d{7}[A-Z]|[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J])",
            cleaned,
        ))
        if looks_spanish and not valid_spanish_tax_id(cleaned):
            issues.append(f"{label} no supera la comprobación de control.")
    if draft.get("issued_on") and draft.get("due_on"):
        if str(draft["due_on"]) < str(draft["issued_on"]):
            issues.append("El vencimiento es anterior a la fecha de emisión.")
    return issues
