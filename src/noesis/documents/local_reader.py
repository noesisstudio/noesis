"""Lectura local y determinista de facturas, tickets y extractos a partir de su texto.

No usa red ni IA: trabaja con el texto que ya sacan pypdf o Tesseract. Solo propone
campos; nada se contabiliza sin la confirmación del titular. Ante la duda deja el
campo vacío en vez de adivinarlo, y marca como «supuesto» lo que no está etiquetado.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from ..fiscal_validation import valid_spanish_tax_id

CENT = Decimal("0.01")
VAT_RATES = (0, 4, 10, 21)
MAX_LINES = 800
MAX_ITEMS = 40
MAX_DOCUMENTS = 20

_MONTHS = {
    "enero": 1, "ene": 1, "gener": 1, "january": 1, "jan": 1,
    "febrero": 2, "feb": 2, "febrer": 2, "february": 2,
    "marzo": 3, "marc": 3, "march": 3,
    "abril": 4, "abr": 4, "april": 4, "apr": 4,
    "mayo": 5, "maig": 5, "may": 5,
    "junio": 6, "juny": 6, "june": 6, "jun": 6,
    "julio": 7, "juliol": 7, "july": 7, "jul": 7,
    "agosto": 8, "agost": 8, "august": 8, "ago": 8, "aug": 8,
    "septiembre": 9, "setiembre": 9, "setembre": 9, "september": 9, "sep": 9, "sept": 9,
    "octubre": 10, "october": 10, "oct": 10,
    "noviembre": 11, "novembre": 11, "november": 11, "nov": 11,
    "diciembre": 12, "desembre": 12, "december": 12, "dic": 12, "dec": 12,
}

# Importes con decimales (1.234,56 · 1234,56 · 1,234.56 · 12.50) o enteros seguidos
# de moneda. Un entero suelto es demasiado ambiguo: teléfonos, unidades, códigos.
_AMOUNT_RE = re.compile(
    r"(?<![\w.,/-])"
    r"(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d{1,3}(?:,\d{3})+\.\d{1,2}|\d+(?:[.,]\d{1,2})?)"
    r"(?:\s*(€|eur\b|euros?\b))?"
    r"(?![\w%]|[.,]\d|/\d)"
)
_NUMERIC_DATE = re.compile(r"(?<!\d)(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})(?!\d)")
_ISO_DATE = re.compile(r"(?<!\d)(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})(?!\d)")
_TEXT_DATE = re.compile(
    r"(?<!\d)(\d{1,2})\s+(?:de\s+|d')?([a-z]{3,10})\.?\s+(?:de\s+|del\s+)?(\d{4})(?!\d)"
)
_PERCENT = re.compile(r"(?<![\d.,])(\d{1,2}(?:[.,]\d{1,2})?)\s*%")
_TAX_ID = re.compile(
    r"(?<![a-z0-9])(?:es)?([abcdefghjnpqrsuvw][ -]?\d{7}[ -]?[0-9a-j]"
    r"|\d{8}[ -]?[a-z]|[xyz][ -]?\d{7}[ -]?[a-z])(?![a-z0-9])"
)
_PHONE = re.compile(r"(?:\+?\d{2}\s?)?(?:\d{3}\s?\d{2}\s?\d{2}\s?\d{2}|\d{3}\s\d{3}\s\d{3})(?!\d)")

_LABELS = (
    ("total", 2, re.compile(
        r"\b(?:total\s+(?:factura|fra|a\s+pagar|importe|import|documento|document|eur|euros)"
        r"|importe\s+total|import\s+total|total\s+a\s+pagar|a\s+pagar|total\s+amount"
        r"|amount\s+due|grand\s+total|total\s+due|total\s+con\s+iva"
        r"|total\s+(?:iva|impuestos)\s+(?:incluido|incluidos|inclos|inclosos))\b"
    )),
    ("total", 1, re.compile(r"\btotal\b")),
    ("base", 1, re.compile(
        r"\b(?:base\s+imponible|base\s+imposable|base\s+imp\b\.?|total\s+base|subtotal"
        r"|sub-total|importe\s+neto|import\s+net|total\s+neto|taxable\s+amount"
        r"|net\s+amount|base)\b"
    )),
    ("irpf", 1, re.compile(r"\b(?:irpf|retencion|retencio|withholding)\b")),
    ("vat", 1, re.compile(r"\b(?:cuota\s+(?:de\s+)?iva|quota\s+iva|total\s+iva|iva|i\.v\.a\.?|vat)\b")),
)
# Líneas de pago o de unidades: su «total» no es el importe de la factura.
_NOT_A_TOTAL = re.compile(
    r"\b(?:pagado|entregado|efectivo|efectiu|cambio|canvi|tarjeta|targeta|unidades|uds|"
    r"articulos|articles|lineas|linies|kg|puntos|punts|ahorro|estalvi|saldo\s+anterior)\b"
)
_INCLUDED_TAX = re.compile(r"\b(?:iva|impuestos)\s+(?:incluido|incluidos|inclos|inclosos|incl\.?)\b")
_ISSUE_CONTEXT = re.compile(r"\b(?:fecha|data|emision|emisio|expedicion|expedicio|date|fra\.?|factura)\b")
_DUE_CONTEXT = re.compile(r"\b(?:venc\w*|vto\.?|due|fecha\s+limite|pagar\s+antes|forma\s+de\s+pago\s+hasta)\b")
_NUMBER_LABEL = re.compile(
    r"(?:\bfactura(?:\s+simplificada|\s+rectificativa)?\s*(?:n\.?\s*[o°]\.?|num(?:ero)?\.?|#)?"
    r"|\bfra\.?\s*(?:n\.?\s*[o°]\.?)?|\binvoice\s*(?:no\.?|number|#)?"
    r"|\b(?:ticket|tiquet)\s*(?:n\.?\s*[o°]\.?|num(?:ero)?\.?|#)"
    r"|\bn\.?\s*[o°]\.?\s*(?:de\s+)?(?:factura|fra|documento|document|ticket|tiquet)"
    r"|\bnum(?:ero)?\.?\s*(?:de\s+)?(?:factura|fra|documento|document|ticket))"
    r"\s*[:#.]?\s*([a-z0-9][a-z0-9/_.-]{0,28})"
)
_GENERIC_NUMBER_LABEL = re.compile(r"(?:\bn\.?\s*[o°]\.?|\bnum(?:ero)?\.?|\bref(?:erencia)?\.?)\s*[:#]\s*([a-z0-9][a-z0-9/_.-]{0,28})")
_STATEMENT_WORDS = re.compile(
    r"\b(?:extracto|extracte|relacion\s+de\s+facturas|relacio\s+de\s+factures|estado\s+de\s+cuenta"
    r"|facturas\s+pendientes|factures\s+pendents|saldo\s+pendiente|saldo\s+deudor"
    r"|recordatorio\s+de\s+pago|resumen\s+de\s+facturas|listado\s+de\s+facturas"
    r"|deuda\s+pendiente|facturas\s+vencidas|reclamacion\s+de\s+deuda)\b"
)
_TICKET_WORDS = re.compile(r"\b(?:factura\s+simplificada|ticket|tiquet|tique|recibo|rebut|simplificada)\b")
_COMPANY_SUFFIX = re.compile(r"\b(?:s\.?\s?l\.?\s?u?\.?|s\.?\s?a\.?\s?u?\.?|s\.?\s?c\.?\s?p\.?|c\.?\s?b\.?|s\.?\s?coop\.?)(?:\s|$|,)", re.I)
_NOT_A_NAME = re.compile(
    r"\b(?:factura|fra|ticket|tiquet|fecha|data|cliente|client|total|iva|base|importe|import|"
    r"pagina|pag|telefono|telf|tel|movil|email|e-mail|correo|www|http|calle|c/|avda|avenida|"
    r"direccion|domicilio|cp|codigo|nif|cif|dni|nie|numero|num|descripcion|concepto|cantidad|"
    r"precio|unidades|forma\s+de\s+pago|vencimiento|iban|banco|gracias|simplificada|original|copia)\b"
)


def fold(text) -> str:
    """Minúsculas sin acentos, conservando la longitud de casi cualquier texto."""
    text = unicodedata.normalize("NFKD", str(text or "").lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def money(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        amount = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None
    return amount if amount.is_finite() else None


def amount_value(raw: str) -> Decimal | None:
    """Convierte 1.234,56 · 1,234.56 · 45,2 · 12.50 a Decimal con dos decimales."""
    text = str(raw or "").strip()
    if not text:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", text):
        text = text.replace(".", "")
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    if not value.is_finite() or value < 0 or value > Decimal("10000000"):
        return None
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _blank(text: str, pattern: re.Pattern) -> str:
    return pattern.sub(lambda m: " " * (m.end() - m.start()), text)


def _mask(folded: str) -> str:
    """Oculta fechas, porcentajes, NIF y teléfonos para que no parezcan importes."""
    masked = folded
    for pattern in (_NUMERIC_DATE, _ISO_DATE, _TEXT_DATE, _TAX_ID, _PERCENT, _PHONE):
        masked = _blank(masked, pattern)
    return masked


def amounts(folded: str) -> list[tuple[int, Decimal]]:
    found = []
    for match in _AMOUNT_RE.finditer(_mask(folded)):
        raw, currency = match.group(1), match.group(2)
        thousands_only = re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw)
        has_decimals = bool(re.search(r"[.,]\d{1,2}$", raw)) and not thousands_only
        if not has_decimals and not currency:
            continue
        value = amount_value(raw)
        if value is not None:
            found.append((match.start(), value))
    return found


def _rates(folded: str) -> list[int]:
    out = []
    for raw in _PERCENT.findall(folded):
        try:
            value = Decimal(raw.replace(",", "."))
        except InvalidOperation:
            continue
        if value == value.to_integral_value() and int(value) in VAT_RATES:
            out.append(int(value))
    return out


def _percent_values(folded: str) -> list[Decimal]:
    out = []
    for raw in _PERCENT.findall(folded):
        try:
            out.append(Decimal(raw.replace(",", ".")))
        except InvalidOperation:
            continue
    return out


def parse_date(day, month, year) -> date | None:
    try:
        day, year = int(day), int(year)
        month = int(month) if str(month).isdigit() else _MONTHS.get(str(month)[:10])
        if month is None:
            return None
        if year < 100:
            year += 2000
        if not 2000 <= year <= 2100:
            return None
        return date(year, int(month), day)
    except (TypeError, ValueError):
        return None


def dates(folded: str) -> list[date]:
    found = []
    for match in _NUMERIC_DATE.finditer(folded):
        value = parse_date(match.group(1), match.group(2), match.group(3))
        if value:
            found.append((match.start(), value))
    for match in _ISO_DATE.finditer(folded):
        value = parse_date(match.group(3), match.group(2), match.group(1))
        if value:
            found.append((match.start(), value))
    for match in _TEXT_DATE.finditer(folded):
        value = parse_date(match.group(1), match.group(2), match.group(3))
        if value:
            found.append((match.start(), value))
    return [value for _pos, value in sorted(found, key=lambda item: item[0])]


def tax_ids(folded: str) -> list[str]:
    out = []
    for raw in _TAX_ID.findall(folded):
        cleaned = re.sub(r"[^a-z0-9]", "", raw).upper()
        if valid_spanish_tax_id(cleaned) and cleaned not in out:
            out.append(cleaned)
    return out


def _clean_tax_id(value) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _label_spans(folded: str) -> list[tuple[int, int, str, int]]:
    spans = []
    for name, strength, pattern in _LABELS:
        for match in pattern.finditer(folded):
            spans.append((match.start(), match.end(), name, strength))
    spans.sort(key=lambda span: (span[0], -(span[1] - span[0])))
    kept: list[tuple[int, int, str, int]] = []
    for span in spans:
        if any(other[0] <= span[0] < other[1] for other in kept):
            continue
        kept.append(span)
    return kept


def _lines(text: str) -> list[str]:
    return [line.strip() for line in str(text or "").splitlines()][:MAX_LINES]


def _money_candidates(lines: list[str]) -> dict:
    """Recoge importes etiquetados línea a línea, incluidas tablas cabecera/valores."""
    found: dict[str, list[dict]] = {"total": [], "base": [], "vat": [], "irpf": []}
    breakdown: list[tuple[int, Decimal, Decimal]] = []
    folded_lines = [fold(line) for line in lines]
    for index, folded in enumerate(folded_lines):
        if not folded:
            continue
        line_amounts = amounts(folded)
        rates = _rates(folded)
        # Desglose por tipo: una línea con 21 % y dos importes donde uno es el 21 % del otro.
        for rate in (rate for rate in rates if rate):
            values = sorted({value for _pos, value in line_amounts}, reverse=True)
            for base in values:
                expected = (base * rate / 100).quantize(CENT, rounding=ROUND_HALF_UP)
                vat = next((v for v in values if v != base and abs(v - expected) <= CENT), None)
                if vat is not None:
                    breakdown.append((rate, base, vat))
                    break
        spans = _label_spans(_blank(folded, _INCLUDED_TAX))
        if not spans:
            continue
        if not line_amounts:
            following = next((
                other for other in folded_lines[index + 1:index + 3] if other.strip()
            ), "")
            follow_amounts = amounts(following) if following else []
            if following and not _label_spans(following) and follow_amounts:
                if len(follow_amounts) == len(spans):
                    pairs = zip(spans, [value for _pos, value in follow_amounts])
                elif len(spans) == 1 and len(follow_amounts) == 1:
                    pairs = [(spans[0], follow_amounts[0][1])]
                else:
                    pairs = []
                for (_start, _end, name, strength), value in pairs:
                    if name == "total" and _NOT_A_TOTAL.search(folded):
                        continue
                    found[name].append({"value": value, "strength": strength, "line": index,
                                        "rates": rates})
            continue
        for position, (start, end, name, strength) in enumerate(spans):
            if name == "total" and strength == 1 and _NOT_A_TOTAL.search(folded):
                continue
            region_end = spans[position + 1][0] if position + 1 < len(spans) else len(folded)
            region = [value for pos, value in line_amounts if end <= pos < region_end]
            if not region:
                continue
            if len(spans) == 1 and name == "base":
                value = region[0]
            elif position + 1 < len(spans):
                value = region[0]
            else:
                value = region[-1]
            found[name].append({"value": value, "strength": strength, "line": index,
                                "rates": rates, "percents": _percent_values(folded)})
    found["breakdown"] = breakdown
    return found


def _money_fields(lines: list[str]) -> dict:
    candidates = _money_candidates(lines)
    result: dict = {"base": None, "vat_rate": None, "vat_amount": None,
                    "irpf_amount": None, "total": None, "guessed": []}
    totals = candidates["total"]
    if totals:
        best = max(totals, key=lambda item: (item["strength"], item["line"]))
        result["total"] = best["value"]
    breakdown = []
    for rate, base, vat in candidates["breakdown"]:
        if (rate, base, vat) not in breakdown:
            breakdown.append((rate, base, vat))
    distinct_rates = {rate for rate, _base, _vat in breakdown}
    if len(distinct_rates) >= 2:
        per_rate = {}
        for rate, base, vat in breakdown:
            per_rate.setdefault(rate, (base, vat))
        result["base"] = sum((base for base, _vat in per_rate.values()), Decimal("0.00"))
        result["vat_amount"] = sum((vat for _base, vat in per_rate.values()), Decimal("0.00"))
    elif breakdown:
        rate, base, vat = breakdown[-1]
        result.update(base=base, vat_amount=vat, vat_rate=rate)
    if result["base"] is None and candidates["base"]:
        result["base"] = candidates["base"][-1]["value"]
    if result["vat_amount"] is None and candidates["vat"]:
        vat_lines = candidates["vat"]
        by_rate = {}
        for item in vat_lines:
            key = item["rates"][0] if item["rates"] else None
            by_rate[key] = item["value"]
        if len([key for key in by_rate if key is not None]) >= 2:
            result["vat_amount"] = sum(
                (value for key, value in by_rate.items() if key is not None), Decimal("0.00")
            )
        else:
            chosen = vat_lines[-1]
            result["vat_amount"] = chosen["value"]
            if chosen["rates"] and result["vat_rate"] is None:
                result["vat_rate"] = chosen["rates"][0]
    if candidates["irpf"]:
        result["irpf_amount"] = candidates["irpf"][-1]["value"]
    base, vat = result["base"], result["vat_amount"]
    if result["vat_rate"] is None and base and vat is not None and len(distinct_rates) < 2:
        for rate in VAT_RATES:
            if abs((base * rate / 100).quantize(CENT, rounding=ROUND_HALF_UP) - vat) <= CENT:
                result["vat_rate"] = rate
                break
    if result["total"] is None:
        every = sorted({
            value for line in lines for _pos, value in amounts(fold(line))
        })
        if len(every) == 1:
            result["total"] = every[0]
        elif every and base is not None and vat is not None:
            expected = base + vat - (result["irpf_amount"] or Decimal("0.00"))
            if any(abs(value - expected) <= CENT for value in every):
                result["total"] = expected
        elif every:
            result["total"] = every[-1]
            result["guessed"].append("total")
    return result


def _document_number(lines: list[str]) -> str | None:
    for pattern in (_NUMBER_LABEL, _GENERIC_NUMBER_LABEL):
        for line in lines:
            folded = fold(line)
            for match in pattern.finditer(folded):
                raw = match.group(1).strip("./-_")
                if not re.search(r"\d", raw) or len(raw) < 1:
                    continue
                if _NUMERIC_DATE.fullmatch(raw) or _ISO_DATE.fullmatch(raw):
                    continue
                if re.fullmatch(r"\d+[.,]\d{1,2}", raw) or tax_ids(raw):
                    continue
                if len(folded) == len(line):
                    raw = line[match.start(1):match.start(1) + len(raw)]
                return raw.upper()[:50]
    return None


def _issue_and_due_dates(lines: list[str]) -> tuple[str | None, str | None]:
    issued = due = None
    fallback = None
    for line in lines:
        folded = fold(line)
        found = dates(folded)
        if not found:
            continue
        if _DUE_CONTEXT.search(folded):
            due = due or found[0]
            if _ISSUE_CONTEXT.search(folded) and len(found) >= 2 and not issued:
                issued = found[0]
                due = found[1]
            continue
        if _ISSUE_CONTEXT.search(folded) and not issued:
            issued = found[0]
        fallback = fallback or found[0]
    issued = issued or fallback
    if issued and due and due < issued:
        due = None
    return (issued.isoformat() if issued else None, due.isoformat() if due else None)


def _looks_like_name(line: str, business_name: str | None) -> bool:
    folded = fold(line)
    letters = len(re.findall(r"[a-z]", folded))
    if letters < 3 or len(line) > 90:
        return False
    if sum(ch.isdigit() for ch in line) > letters:
        return False
    if _NOT_A_NAME.search(folded) and not _COMPANY_SUFFIX.search(line):
        return False
    business = fold(business_name).strip()
    if business and (business in folded or folded.strip() in business):
        return False
    return True


def _clean_name(line: str) -> str:
    text = _TAX_ID.sub(" ", fold(line)) if len(fold(line)) != len(line) else line
    if len(fold(line)) == len(line):
        folded = fold(line)
        pieces = []
        last = 0
        for match in _TAX_ID.finditer(folded):
            pieces.append(line[last:match.start()])
            last = match.end()
        pieces.append(line[last:])
        text = " ".join(pieces)
    text = re.sub(r"\b(?:C\.?I\.?F|N\.?I\.?F|DNI|NIE|VAT)\b\.?\s*:?", " ", text, flags=re.I)
    text = re.sub(r"\s{2,}", " ", text).strip(" :-·|,")
    return text[:200]


_CUSTOMER_CONTEXT = re.compile(
    r"\b(?:cliente|client|destinatario|destinatari|facturar\s+a|bill\s+to|receptor|"
    r"comprador|datos\s+del\s+cliente|dades\s+del\s+client|customer)\b"
)


def _parties(lines: list[str], ids: list[str], own: str) -> tuple[str | None, str | None]:
    """(NIF emisor, NIF receptor). Una etiqueta de cliente pesa más que el orden."""
    if not ids:
        return None, None
    folded_lines = [fold(line) for line in lines]
    first_line: dict[str, int] = {}
    labelled_customer: set[str] = set()
    for index, folded in enumerate(folded_lines):
        for value in tax_ids(folded):
            first_line.setdefault(value, index)
            window = " ".join(folded_lines[max(0, index - 2):index + 1])
            if _CUSTOMER_CONTEXT.search(window):
                labelled_customer.add(value)
    ordered = sorted(ids, key=lambda value: first_line.get(value, 0))
    customers = [value for value in ordered if value in labelled_customer]
    if customers:
        customer = customers[0]
        supplier = next((value for value in ordered if value != customer), None)
        return supplier, customer
    if own and own in ordered:
        if ordered[0] == own:
            return own, next((value for value in ordered if value != own), None)
        return next((value for value in ordered if value != own), None), own
    return ordered[0], (ordered[1] if len(ordered) > 1 else None)


def _supplier(lines: list[str], supplier_nif: str | None, business_name: str | None) -> str | None:
    if supplier_nif:
        for index, line in enumerate(lines):
            if supplier_nif in _clean_tax_id(line):
                candidate = _clean_name(line)
                if _looks_like_name(candidate, business_name):
                    return candidate
                for previous in reversed(lines[max(0, index - 3):index]):
                    if previous and _looks_like_name(previous, business_name):
                        return _clean_name(previous)
                break
    head = [line for line in lines[:14] if line]
    for line in head:
        if _COMPANY_SUFFIX.search(line) and _looks_like_name(line, business_name):
            return _clean_name(line)
    for line in head[:6]:
        if _looks_like_name(line, business_name):
            return _clean_name(line)
    return None


def _kind(folded_text: str, fields: dict) -> str:
    if re.search(r"\bfactura\s+simplificada\b", folded_text):
        return "ticket"
    if re.search(r"\bfactura\b|\binvoice\b|\bfra\.", folded_text):
        return "factura"
    if re.search(r"\balbaran\b|\balbara\b|\bdelivery\s+note\b", folded_text):
        return "albaran"
    if re.search(r"\bpresupuesto\b|\bpressupost\b", folded_text):
        return "presupuesto"
    if re.search(r"\bcontrato\b|\bcontracte\b", folded_text):
        return "contrato"
    if _TICKET_WORDS.search(folded_text) or fields.get("total") is not None:
        return "ticket"
    return "documento"


def fields_from_text(text: str | None, *, business_nif: str | None = None,
                     business_name: str | None = None) -> dict | None:
    """Campos de UN documento. None si el texto no aporta nada útil."""
    lines = _lines(text)
    if not any(lines):
        return None
    folded_text = fold("\n".join(lines))
    money_fields = _money_fields(lines)
    own = _clean_tax_id(business_nif)
    supplier_nif, customer_nif = _parties(lines, tax_ids(folded_text), own)
    issued_on, due_on = _issue_and_due_dates(lines)
    if own and supplier_nif == own:
        supplier = business_name
    else:
        supplier = _supplier(lines, supplier_nif, business_name)
    fields = {
        "number": _document_number(lines),
        "issued_on": issued_on,
        "due_on": due_on,
        "supplier": supplier,
        "supplier_nif": supplier_nif,
        "customer": business_name if own and customer_nif == own else None,
        "customer_nif": customer_nif,
        "concept": None,
        **{key: money_fields[key] for key in ("base", "vat_rate", "vat_amount", "irpf_amount", "total")},
        "guessed": money_fields["guessed"],
    }
    fields["kind"] = _kind(folded_text, fields)
    useful = ("total", "base", "number", "supplier_nif")
    if not any(fields.get(key) not in (None, "") for key in useful):
        return None
    return fields


def statement_from_text(text: str | None, *, business_nif: str | None = None,
                        business_name: str | None = None) -> dict | None:
    """Extracto o relación de varias facturas: filas con número, fecha e importe."""
    lines = _lines(text)
    folded_text = fold("\n".join(lines))
    if not _STATEMENT_WORDS.search(folded_text):
        return None
    items = []
    seen = set()
    for line in lines:
        folded = fold(line)
        row_dates = dates(folded)
        row_amounts = amounts(folded)
        if not row_dates or not row_amounts:
            continue
        stripped = _mask(folded)
        stripped = _AMOUNT_RE.sub(lambda m: " " * (m.end() - m.start()), stripped)
        number = re.search(r"(?<![\w])([a-z]{0,6}[-/]?\d{2,}[a-z0-9/-]*)(?![\w])", stripped)
        if not number:
            continue
        raw = number.group(1)
        if len(folded) == len(line):
            raw = line[number.start(1):number.end(1)]
        key = raw.upper()
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "number": key[:50],
            "issued_on": row_dates[0].isoformat(),
            "due_on": row_dates[1].isoformat() if len(row_dates) > 1 else None,
            "total": row_amounts[-1][1] if len(row_amounts) == 1 else row_amounts[0][1],
            "pending": row_amounts[-1][1] if len(row_amounts) > 1 else None,
        })
        if len(items) >= MAX_ITEMS:
            break
    if len(items) < 2:
        return None
    ids = tax_ids(folded_text)
    own = _clean_tax_id(business_nif)
    others = [value for value in ids if value != own]
    issuer_is_business = bool(own and ids and ids[0] == own)
    return {
        "issuer": business_name if issuer_is_business else _supplier(
            lines, others[0] if others else None, business_name
        ),
        "issuer_nif": own if issuer_is_business else (others[0] if others else None),
        "customer_nif": (others[0] if issuer_is_business and others else
                         (own if own in ids else None)),
        "items": items,
    }


def read(text: str | None, *, pages: list[str] | None = None,
         business_nif: str | None = None, business_name: str | None = None) -> dict | None:
    """Lectura completa: un documento, varias facturas por página o un extracto."""
    statement = statement_from_text(text, business_nif=business_nif, business_name=business_name)
    if statement:
        return {"documents": [], "statement": statement, "source": "texto"}
    documents = []
    if pages and len(pages) >= 2:
        groups: list[dict] = []
        for number, page_text in enumerate(pages[:200], start=1):
            fields = fields_from_text(page_text, business_nif=business_nif, business_name=business_name)
            starts_new = bool(fields and (fields.get("number") or fields.get("total") is not None))
            same_number = bool(
                groups and fields and fields.get("number")
                and groups[-1]["fields"].get("number") == fields.get("number")
            )
            if starts_new and not same_number:
                groups.append({"fields": fields, "pages": [number, number]})
            elif groups:
                groups[-1]["pages"][1] = number
                if fields:
                    for key, value in fields.items():
                        if groups[-1]["fields"].get(key) in (None, "", []) and value not in (None, "", []):
                            groups[-1]["fields"][key] = value
        complete = [group for group in groups if group["fields"].get("total") is not None]
        if len(complete) >= 2 and len(complete) == len(groups):
            groups[0]["pages"][0] = 1
            for group in groups[:MAX_DOCUMENTS]:
                documents.append({**group["fields"], "pages": group["pages"]})
    if not documents:
        fields = fields_from_text(text, business_nif=business_nif, business_name=business_name)
        if fields:
            documents = [{**fields, "pages": None}]
    if not documents:
        return None
    return {"documents": documents, "statement": None, "source": "texto"}
