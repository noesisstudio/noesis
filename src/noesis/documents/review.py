"""Revisión conversacional de lo leído en un documento, antes de contabilizarlo.

Una lectura (IA o texto local) es solo una propuesta. El titular la corrige con
frases cortas y la confirma cuando las cifras cuadran. Lo que dice el titular manda
sobre lo leído, y lo calculado se enseña como calculado. Este módulo no escribe en
la base de datos: prepara, corrige, valida y redacta.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from ..fiscal_validation import invoice_draft_issues
from .local_reader import CENT, VAT_RATES, amount_value, fold, money

FIELDS = (
    "supplier", "supplier_nif", "customer", "customer_nif", "number", "issued_on",
    "due_on", "concept", "base", "vat_rate", "vat_amount", "irpf_amount", "total",
)
MONEY_FIELDS = ("base", "vat_amount", "irpf_amount", "total")
TEXT_LIMITS = {"supplier": 200, "customer": 200, "supplier_nif": 20, "customer_nif": 20,
               "number": 50, "concept": 300}
MODES = ("gasto", "recibida", "emitida", "archivo")
ARCHIVE_LABELS = {"albaran": "albarán", "presupuesto": "presupuesto",
                  "contrato": "contrato", "documento": "documento"}
LABELS = {
    "supplier": "proveedor", "supplier_nif": "NIF", "customer": "cliente",
    "customer_nif": "NIF del cliente", "number": "número", "issued_on": "fecha",
    "due_on": "vencimiento", "concept": "concepto", "base": "base",
    "vat_rate": "tipo de IVA", "vat_amount": "IVA", "irpf_amount": "IRPF",
    "total": "total", "mode": "tipo de documento",
}
_ARITHMETIC_MARK = "no coincide"


# ----------------------------------------------------------------- utilidades


def _clean_id(value) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _clean(field: str, value):
    if value in (None, "", []):
        return None
    if field in MONEY_FIELDS:
        amount = money(value)
        if amount is None or amount < 0 or amount > Decimal("10000000"):
            return None
        return float(amount)
    if field == "vat_rate":
        try:
            rate = int(Decimal(str(value)))
        except Exception:  # noqa: BLE001
            return None
        return rate if rate in VAT_RATES else None
    if field in ("issued_on", "due_on"):
        try:
            return date.fromisoformat(str(value)[:10]).isoformat()
        except ValueError:
            return None
    if field in ("supplier_nif", "customer_nif"):
        cleaned = _clean_id(value)
        return cleaned[:20] or None
    text = re.sub(r"\s+", " ", str(value)).strip(" ,:;-")
    # «S.L.» conserva su punto; el de final de frase («Leroy Merlin.») sobra.
    if text.endswith(".") and not re.search(r"(?:^|[\s.])[A-Za-z]\.$", text):
        text = text[:-1].rstrip()
    return text[:TEXT_LIMITS.get(field, 200)] or None


def eur(value) -> str:
    amount = money(value) or Decimal("0.00")
    text = f"{amount:,.2f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def _day(value: str | None) -> str:
    try:
        return date.fromisoformat(str(value)).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(value or "")


def direction(fields: dict, business: dict | None) -> str:
    """'emitida', 'recibida' o 'desconocida' según NIF o nombre del negocio."""
    business = business or {}
    own = _clean_id(business.get("nif"))
    name = fold(business.get("name")).strip()
    is_issuer = bool(
        (own and own == _clean_id(fields.get("supplier_nif")))
        or (len(name) > 3 and name in fold(fields.get("supplier")))
    )
    is_receiver = bool(
        (own and own == _clean_id(fields.get("customer_nif")))
        or (len(name) > 3 and name in fold(fields.get("customer")))
    )
    if is_issuer and not is_receiver:
        return "emitida"
    if is_receiver and not is_issuer:
        return "recibida"
    return "desconocida"


def mode_for(kind: str | None, fields: dict, business: dict | None, *,
             media: str = "image") -> tuple[str, str | None]:
    """Qué se hará al confirmar: gasto, factura recibida, emitida histórica o archivo."""
    kind = (kind or "").strip().lower()
    found_direction = direction(fields, business)
    if found_direction == "emitida" or (kind == "factura_emitida" and found_direction != "recibida"):
        return "emitida", None
    if kind in ("albaran", "presupuesto", "contrato"):
        return "archivo", kind
    if kind == "ticket":
        return "gasto", None
    if kind in ("factura_recibida", "factura") or found_direction == "recibida":
        return "recibida", None
    if fields.get("number") or fields.get("supplier_nif"):
        return "recibida", None
    if fields.get("total") is not None:
        return "gasto", None
    return ("recibida" if media == "document" else "gasto"), None


def new_item(*, fields: dict | None, kind: str | None, business: dict | None,
             document_id: int | None, origin_document_id: int | None = None,
             source: str = "ninguno", pages=None, conflicts=None, guessed=None,
             media: str = "image", note: str | None = None) -> dict:
    fields = fields or {}
    clean = {field: _clean(field, fields.get(field)) for field in FIELDS}
    mode, archive_kind = mode_for(kind, clean, business, media=media)
    return {
        "document_id": int(document_id) if document_id else None,
        "origin_document_id": int(origin_document_id) if origin_document_id else None,
        "mode": mode,
        "archive_kind": archive_kind,
        "fields": clean,
        "user": [],
        "source": source,
        "pages": list(pages) if pages else None,
        "conflicts": [dict(item) for item in (conflicts or []) if isinstance(item, dict)],
        "guessed": [str(item) for item in (guessed or [])],
        "irpf_percent": None,
        "note": note,
    }


# ------------------------------------------------------------- cálculo y estado


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def derive(fields: dict, irpf_percent=None) -> tuple[dict, list[str]]:
    """Completa lo que se deduce con certeza aritmética; nunca inventa un dato."""
    base = money(fields.get("base"))
    vat = money(fields.get("vat_amount"))
    irpf = money(fields.get("irpf_amount"))
    total = money(fields.get("total"))
    rate = fields.get("vat_rate")
    rate = Decimal(int(rate)) if rate is not None else None
    percent = Decimal(str(irpf_percent)) if irpf_percent is not None else None
    derived: list[str] = []

    if rate is not None and base is None and vat is None and total is not None:
        if irpf is None and percent is not None:
            base = _quantize(total / (1 + rate / 100 - percent / 100))
        else:
            base = _quantize((total + (irpf or 0)) / (1 + rate / 100))
        derived.append("base")
    if base is not None and irpf is None and percent is not None:
        irpf = _quantize(base * percent / 100)
        derived.append("irpf_amount")
    if rate is not None and base is not None and vat is None:
        if total is not None and "base" in derived:
            vat = _quantize(total - base + (irpf or 0))
        else:
            vat = _quantize(base * rate / 100)
        derived.append("vat_amount")
    if rate is None:
        if base is not None and total is not None and vat is None:
            candidate = _quantize(total - base + (irpf or 0))
            if candidate >= 0:
                vat = candidate
                derived.append("vat_amount")
        if base is None and vat is not None and total is not None:
            candidate = _quantize(total - vat + (irpf or 0))
            if candidate >= 0:
                base = candidate
                derived.append("base")
    if total is None and base is not None and vat is not None:
        total = _quantize(base + vat - (irpf or 0))
        derived.append("total")
    if rate is None and base and vat is not None:
        for candidate in VAT_RATES:
            if abs(_quantize(base * candidate / 100) - vat) <= CENT * 2:
                rate = Decimal(candidate)
                derived.append("vat_rate")
                break

    values = dict(fields)
    values.update({
        "base": float(base) if base is not None else None,
        "vat_amount": float(vat) if vat is not None else None,
        "irpf_amount": float(irpf) if irpf is not None else None,
        "total": float(total) if total is not None else None,
        "vat_rate": int(rate) if rate is not None else None,
    })
    return values, derived


def evaluate(item: dict) -> dict:
    """Valores, avisos que bloquean, datos que faltan y si ya se puede confirmar."""
    user = set(item.get("user") or [])
    values, derived = derive(item.get("fields") or {}, item.get("irpf_percent"))
    mode = item.get("mode")
    issues = list(invoice_draft_issues(values)) if mode in ("gasto", "recibida", "emitida") else []
    for conflict in item.get("conflicts") or []:
        field = conflict.get("field")
        found = [value for value in conflict.get("values") or [] if value is not None]
        if field in user or len(found) < 2:
            continue
        issues.append(
            f"He leído dos {LABELS.get(field, field)}es distintos: "
            + " y ".join(eur(value) for value in found[:2])
            + f". Dime cuál es («{LABELS.get(field, field)} {eur(found[0])[:-2]}»)."
        )
    for field in item.get("guessed") or []:
        if field in user or values.get(field) is None:
            continue
        issues.append(
            f"No he encontrado la palabra «total»: he tomado el importe más alto "
            f"({eur(values[field])}). Confírmalo con «total {eur(values[field])[:-2]}» o dime el correcto."
        )
    missing = []
    if mode in ("gasto", "recibida") and values.get("total") is None:
        missing.append("el total")
    if mode == "recibida" and not (values.get("supplier") or values.get("supplier_nif")):
        missing.append("el proveedor")
    return {"values": values, "derived": derived, "issues": issues, "missing": missing,
            "ready": not issues and not missing}


def _arithmetic_conflict(item: dict) -> bool:
    values, _derived = derive(item["fields"], item.get("irpf_percent"))
    return any(_ARITHMETIC_MARK in issue for issue in invoice_draft_issues(values))


def _reconcile(item: dict) -> list[str]:
    """Si una corrección del titular choca con lo leído, se descarta lo leído."""
    if not _arithmetic_conflict(item):
        return []
    user = set(item.get("user") or [])
    dropped = []
    for field in ("vat_amount", "base", "total", "irpf_amount"):
        if field in user or item["fields"].get(field) is None:
            continue
        item["fields"][field] = None
        dropped.append(field)
        if not _arithmetic_conflict(item):
            break
    return dropped


# ------------------------------------------------------------------ correcciones

_NUM = r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?"
_CURRENCY = r"(?:\s*(?:€|eur|euros))?"
_DATE_RAW = (
    r"(\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?|\d{4}-\d{1,2}-\d{1,2}"
    r"|\d{1,2}\s+(?:de\s+)?[a-z]{3,10}(?:\s+(?:de\s+)?\d{4})?|hoy|ayer|avui|ahir)"
)
_KEYWORD = (
    r"(?:total|importe|import|base|iva|cuota|quota|irpf|retencion|retencio|proveedor|"
    r"proveidor|emisor|nif|cif|fecha|data|vence|vencimiento|numero|num|concepto|"
    r"concepte|es\s+un|es\s+una|recalcula|sin\s+iva|sin\s+irpf)"
)
# Se separa por «;», salto de línea, «,» o «y» delante de otro dato, y también por
# un espacio cuando antes hay una cifra: «total 12,50 proveedor Bar Pepe». Un nombre
# como «proveedor Total Energies» no se parte porque «Total» no sigue a un número.
_SEPARATOR = re.compile(
    rf"\s*(?:;|\n|,\s+(?=(?:el\s+|la\s+)?{_KEYWORD}\b)"
    rf"|\s+(?:y|i)\s+(?=(?:el\s+|la\s+)?{_KEYWORD}\b)"
    rf"|(?<=[0-9%€])\s+(?=(?:el\s+|la\s+)?{_KEYWORD}\b)"
    rf"|(?<=\beur)\s+(?=(?:el\s+|la\s+)?{_KEYWORD}\b)"
    rf"|(?<=\beuros)\s+(?=(?:el\s+|la\s+)?{_KEYWORD}\b))\s*"
)
_LEADING_NO = re.compile(r"^\s*no\s*[,.:;]?\s+(?=\S)", re.I)
_PATTERNS = (
    ("mode", re.compile(
        r"(?:no\s+)?(?:es|era|son)?\s*(?:un|una|el|la)?\s*"
        r"(gasto|ticket|tiquet|factura\s+recibida|factura\s+de\s+proveedor|factura\s+de\s+compra|"
        r"recibida|factura\s+emitida|emitida|factura|albaran|presupuesto|contrato)"
    )),
    ("mine", re.compile(r"(?:la\s+)?(?:he\s+hecho|hice|emiti|la\s+emiti|es\s+mia|es\s+meva)(?:\s+yo)?")),
    ("recalc", re.compile(r"(?:recalcula\w*|calcula\w*)(?:\s+.*)?")),
    ("no_vat", re.compile(r"sin\s+iva|exento(?:\s+de\s+iva)?|iva\s+exento|sense\s+iva")),
    ("no_irpf", re.compile(r"sin\s+(?:irpf|retencion)|sense\s+(?:irpf|retencio)")),
    ("no_nif", re.compile(r"(?:sin|quita(?:r)?|borra(?:r)?|elimina(?:r)?)\s+(?:el\s+)?(?:nif|cif)")),
    ("total", re.compile(
        rf"(?:el\s+)?(?:total|importe(?:\s+total)?|import(?:\s+total)?|precio|he\s+pagado|pague|pagado|son)"
        rf"\s*(?:es|era|son|seria|:|=|de)?\s*({_NUM}){_CURRENCY}"
        r"(?:\s+(?:con|amb)\s+(?:el\s+)?iva(?:\s+(?:del|al))?\s+(0|4|10|21)\s*%?)?"
    )),
    ("base", re.compile(rf"(?:la\s+)?base(?:\s+imponible|\s+imposable)?\s*(?:es|era|:|=|de)?\s*({_NUM}){_CURRENCY}")),
    ("vat_amount", re.compile(rf"(?:la\s+)?(?:cuota|quota)(?:\s+de)?\s+(?:del\s+)?iva\s*(?:es|era|:|=|de)?\s*({_NUM}){_CURRENCY}")),
    ("vat_rate", re.compile(r"(?:el\s+)?(?:tipo\s+(?:de\s+)?)?iva\s*(?:es|era|:|=|del|al|de)?\s*(0|4|10|21)\s*(?:%|por\s*ciento)?")),
    ("vat_amount", re.compile(rf"(?:el\s+)?iva\s*(?:es|era|:|=|de)?\s*(\d+[.,]\d{{1,2}}|(?:{_NUM})\s*(?:€|eur|euros))")),
    ("irpf", re.compile(rf"(?:el\s+)?(?:irpf|retencion|retencio)\s*(?:es|era|:|=|del|de)?\s*({_NUM})\s*(%|€|eur|euros)?")),
    ("nif", re.compile(r"(?:el\s+)?(?:nif|cif|nie|dni)(?:\s+del\s+proveedor)?\s*(?:es|era|:)?\s*([a-z0-9][a-z0-9 .-]{6,16})")),
    ("issued_on", re.compile(rf"(?:la\s+)?(?:fecha|data|es\s+del|emitida\s+el|del\s+dia|dia)\s*(?:es|era|:|de\s+emision)?\s*{_DATE_RAW}")),
    ("due_on", re.compile(rf"(?:vence|vencimiento|venciment|vto|se\s+paga\s+el|pagar\s+antes\s+del)\s*(?:el|es|:)?\s*{_DATE_RAW}")),
    ("number", re.compile(
        r"(?:el\s+)?(?:numero|num|n\s*o|n°)(?:\s+de\s+factura)?\s*(?:es|:|#)?\s*([a-z0-9][a-z0-9/_.-]{0,30})"
        r"|(?:la\s+)?factura\s+(?:es\s+la\s+|numero\s+|num\s+|n\s*o\s*)?([a-z]{0,6}[-/]?\d[a-z0-9/_.-]{0,30})"
    )),
    ("supplier", re.compile(
        r"(?:el\s+)?(?:proveedor|proveidor|emisor|empresa|tienda|botiga|comercio)\s*(?:es|era|:)?\s+(.{2,80})"
        r"|(?:es|era)\s+de\s+(.{2,80})"
    )),
    ("concept", re.compile(r"(?:el\s+)?(?:concepto|concepte|descripcion)\s*(?:es|:)?\s+(.{2,200})")),
    ("bare", re.compile(rf"({_NUM}){_CURRENCY}(?:\s+(?:en|de|a|para|por)?\s*(.{{2,80}}))?")),
)


def _original_slice(original: str, folded: str, match: re.Match, group: int) -> str:
    start, end = match.span(group)
    if len(original) == len(folded):
        return original[start:end]
    return folded[start:end]


def _user_amount(raw: str) -> Decimal | None:
    value = amount_value(raw)
    if value is None or value > Decimal("10000000"):
        return None
    return value


def _user_date(raw: str, today: date, *, after: str | None = None) -> str | None:
    raw = raw.strip()
    if raw in ("hoy", "avui"):
        return today.isoformat()
    if raw in ("ayer", "ahir"):
        return (today - timedelta(days=1)).isoformat()
    from .local_reader import parse_date

    year_given = True
    numeric = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?", raw)
    iso = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", raw)
    textual = re.fullmatch(r"(\d{1,2})\s+(?:de\s+)?([a-z]{3,10})(?:\s+(?:de\s+)?(\d{4}))?", raw)
    if numeric:
        day, month, year = numeric.groups()
    elif iso:
        year, month, day = iso.groups()
    elif textual:
        day, month, year = textual.groups()
    else:
        return None
    if not year:
        year_given = False
        year = today.year
    value = parse_date(day, month, year)
    if value is None:
        return None
    if not year_given:
        if after:
            try:
                reference = date.fromisoformat(after)
            except ValueError:
                reference = None
            if reference and value < reference:
                value = parse_date(day, month, int(year) + 1) or value
        elif value > today + timedelta(days=31):
            value = parse_date(day, month, int(year) - 1) or value
    return value.isoformat()


def _has_letters(text: str, minimum: int = 2) -> bool:
    return len(re.findall(r"[a-zA-ZáéíóúüñçÁÉÍÓÚÜÑÇ]", text or "")) >= minimum


def _set(item: dict, field: str, value, changed: list[str]) -> None:
    item["fields"][field] = _clean(field, value)
    if field not in item["user"]:
        item["user"].append(field)
    if field not in changed:
        changed.append(field)
    item["conflicts"] = [c for c in item.get("conflicts") or [] if c.get("field") != field]
    item["guessed"] = [g for g in item.get("guessed") or [] if g != field]


def _apply_clause(item: dict, original: str, today: date, changed: list[str]) -> bool:
    # «no, el total es 45» corrige; el «no» suelto lo trata quien llama.
    original = _LEADING_NO.sub("", original).strip().strip("!¡¿?").strip()
    folded = fold(original)
    if not folded:
        return True
    mode = item["mode"]
    for name, pattern in _PATTERNS:
        match = pattern.fullmatch(folded)
        if not match:
            continue
        if name == "mode":
            word = match.group(1)
            if word in ("gasto", "ticket", "tiquet"):
                item["mode"], item["archive_kind"] = "gasto", None
            elif word in ("factura emitida", "emitida"):
                item["mode"], item["archive_kind"] = "emitida", None
            elif word in ("albaran", "presupuesto", "contrato"):
                item["mode"], item["archive_kind"] = "archivo", word
            else:
                item["mode"], item["archive_kind"] = "recibida", None
            changed.append("mode")
            return True
        if name == "mine":
            item["mode"], item["archive_kind"] = "emitida", None
            changed.append("mode")
            return True
        if name == "recalc":
            for field in ("base", "vat_amount"):
                if field not in item["user"] and item["fields"].get(field) is not None:
                    item["fields"][field] = None
                    changed.append(field)
            item["conflicts"] = []
            return True
        if name == "no_vat":
            _set(item, "vat_rate", 0, changed)
            _set(item, "vat_amount", 0, changed)
            return True
        if name == "no_irpf":
            item["irpf_percent"] = None
            _set(item, "irpf_amount", 0, changed)
            return True
        if name == "no_nif":
            field = "customer_nif" if mode == "emitida" else "supplier_nif"
            item["fields"][field] = None
            if field not in item["user"]:
                item["user"].append(field)
            changed.append(field)
            return True
        if name == "total":
            amount = _user_amount(match.group(1))
            if amount is None:
                return False
            _set(item, "total", amount, changed)
            if match.group(2) is not None:
                _set(item, "vat_rate", int(match.group(2)), changed)
            return True
        if name in ("base", "vat_amount"):
            raw = re.sub(r"\s*(?:€|eur|euros)$", "", match.group(1))
            amount = _user_amount(raw)
            if amount is None:
                return False
            _set(item, name, amount, changed)
            return True
        if name == "vat_rate":
            _set(item, "vat_rate", int(match.group(1)), changed)
            return True
        if name == "irpf":
            amount = _user_amount(match.group(1))
            unit = match.group(2)
            if amount is None:
                return False
            is_percent = unit == "%" or (
                unit is None and amount <= 25 and not re.search(r"[.,]", match.group(1))
            )
            if is_percent:
                item["irpf_percent"] = float(amount)
                item["fields"]["irpf_amount"] = None
                if "irpf_amount" not in item["user"]:
                    item["user"].append("irpf_amount")
                changed.append("irpf_amount")
            else:
                item["irpf_percent"] = None
                _set(item, "irpf_amount", amount, changed)
            return True
        if name == "nif":
            cleaned = _clean_id(match.group(1))
            if len(cleaned) < 8 or not re.search(r"\d", cleaned):
                return False
            _set(item, "customer_nif" if mode == "emitida" else "supplier_nif", cleaned, changed)
            return True
        if name in ("issued_on", "due_on"):
            after = item["fields"].get("issued_on") if name == "due_on" else None
            value = _user_date(match.group(1), today, after=after)
            if value is None:
                return False
            _set(item, name, value, changed)
            return True
        if name == "number":
            raw_group = 1 if match.group(1) else 2
            raw = _original_slice(original, folded, match, raw_group).strip(" .")
            if not re.search(r"\d", raw):
                return False
            _set(item, "number", raw.upper(), changed)
            return True
        if name == "supplier":
            group = 1 if match.group(1) else 2
            raw = _original_slice(original, folded, match, group).strip(" ,")
            if not _has_letters(raw):
                amount = _user_amount(raw.replace("€", "").strip())
                if amount is None:
                    return False
                _set(item, "total", amount, changed)
                return True
            if fold(raw) in ("acuerdo", "nada", "verdad", "momento"):
                return False
            _set(item, "customer" if mode == "emitida" else "supplier", raw, changed)
            return True
        if name == "concept":
            _set(item, "concept", _original_slice(original, folded, match, 1).strip(), changed)
            return True
        if name == "bare":
            amount = _user_amount(match.group(1))
            if amount is None:
                return False
            _set(item, "total", amount, changed)
            if match.group(2):
                rest = _original_slice(original, folded, match, 2).strip(" .,")
                if not _has_letters(rest):
                    return True
                if mode == "gasto":
                    _set(item, "concept", rest, changed)
                    if not item["fields"].get("supplier"):
                        _set(item, "supplier", rest, changed)
                elif mode == "recibida":
                    _set(item, "supplier", rest, changed)
            return True
    return False


def apply_correction(item: dict, text: str, *, today: date | None = None,
                     labelled_only: bool = False) -> tuple[list[str], list[str]]:
    """Aplica las frases del titular. Devuelve (campos cambiados, trozos no entendidos)."""
    today = today or date.today()
    text = _LEADING_NO.sub("", str(text or "")[:600])
    folded_text = fold(text)
    cuts = [0]
    for match in _SEPARATOR.finditer(folded_text):
        cuts.extend([match.start(), match.end()])
    cuts.append(len(folded_text))
    same_length = len(folded_text) == len(text)
    clauses = []
    for index in range(0, len(cuts) - 1, 2):
        start, end = cuts[index], cuts[index + 1]
        piece = text[start:end] if same_length else folded_text[start:end]
        if piece.strip():
            clauses.append(piece)
    changed: list[str] = []
    unknown: list[str] = []
    for clause in clauses:
        if labelled_only and re.fullmatch(rf"\s*(?:{_NUM}){_CURRENCY}.*", fold(clause)):
            unknown.append(clause.strip())
            continue
        snapshot = (dict(item["fields"]), list(item["user"]), item["mode"], item.get("irpf_percent"))
        if not _apply_clause(item, clause, today, changed):
            item["fields"], item["user"], item["mode"], item["irpf_percent"] = (
                snapshot[0], snapshot[1], snapshot[2], snapshot[3]
            )
            unknown.append(clause.strip())
    if any(field in MONEY_FIELDS or field in ("vat_rate", "irpf_amount") for field in changed):
        for field in _reconcile(item):
            if field not in changed:
                changed.append(field)
    return changed, unknown


# ------------------------------------------------------------------ presentación

_TITLES = {"gasto": "🧾 *Gasto*", "recibida": "📄 *Factura recibida*",
           "emitida": "📤 *Factura emitida por ti*"}


def render(item: dict, *, position: int | None = None, count: int | None = None) -> str:
    """Resumen breve para WhatsApp con lo leído, lo calculado y qué puede responder."""
    state = evaluate(item)
    values, derived = state["values"], set(state["derived"])
    mode = item.get("mode")
    title = _TITLES.get(mode) or f"📎 *{ARCHIVE_LABELS.get(item.get('archive_kind') or 'documento', 'Documento').capitalize()}*"
    if count and count > 1 and position:
        title = f"({position} de {count}) " + title
    lines = [title]
    party = values.get("customer") if mode == "emitida" else values.get("supplier")
    party_nif = values.get("customer_nif") if mode == "emitida" else values.get("supplier_nif")
    if party or party_nif:
        lines.append(" · ".join(part for part in (party, party_nif) if part))
    identity = []
    if values.get("number"):
        identity.append(f"Nº {values['number']}")
    if values.get("issued_on"):
        identity.append(_day(values["issued_on"]))
    if values.get("due_on"):
        identity.append(f"vence {_day(values['due_on'])}")
    if identity:
        lines.append(" · ".join(identity))
    if mode == "gasto" and values.get("concept"):
        lines.append(values["concept"])

    def mark(field: str) -> str:
        return " (calculado)" if field in derived else ""

    money_parts = []
    if values.get("base") is not None:
        money_parts.append(f"Base {eur(values['base'])}{mark('base')}")
    if values.get("vat_amount") is not None:
        rate = f" {values['vat_rate']} %" if values.get("vat_rate") is not None else ""
        money_parts.append(f"IVA{rate} {eur(values['vat_amount'])}{mark('vat_amount')}")
    elif values.get("vat_rate") is not None:
        money_parts.append(f"IVA {values['vat_rate']} %")
    if values.get("irpf_amount"):
        money_parts.append(f"IRPF −{eur(values['irpf_amount'])}{mark('irpf_amount')}")
    if values.get("total") is not None:
        money_parts.append(f"Total *{eur(values['total'])}*{mark('total')}")
    if money_parts:
        lines.append(" · ".join(money_parts))
    if item.get("pages") and count and count > 1:
        start, end = item["pages"][0], item["pages"][-1]
        lines.append(f"Páginas {start}-{end}" if end != start else f"Página {start}")
    if item.get("note"):
        lines.append(f"ℹ️ {item['note']}")
    if item.get("source") == "texto" and (values.get("total") is not None):
        lines.append("ℹ️ Leído del texto del documento, sin IA: comprueba las cifras.")
    for issue in state["issues"]:
        lines.append(f"⚠️ {issue}")

    readable = any(values.get(key) is not None for key in ("total", "base", "number", "supplier"))
    if mode in ("gasto", "recibida") and not readable:
        lines.append("No he podido leer los datos.")
    if state["missing"]:
        lines.append("Me falta " + " y ".join(state["missing"]) + ".")

    if mode == "emitida":
        footer = ("La archivo como factura tuya ya emitida, sin volver a emitirla. "
                  "Responde *SÍ* para archivarla, o «es recibida» si te la han hecho a ti.")
    elif mode == "archivo":
        footer = ("Responde *SÍ* para archivarlo así, o dime qué es "
                  "(«es un gasto», «es una factura»).")
    elif state["missing"] and not readable:
        example = "«45,20 Leroy Merlin»"
        footer = (f"Escríbeme el total y de quién es, por ejemplo {example}. "
                  "Si no es un gasto, dime qué es («es una factura», «es un albarán»).")
    elif state["missing"]:
        footer = ("Escríbeme lo que falta (p. ej. «total 45,20» o «proveedor Leroy Merlin») "
                  "y te pediré el SÍ.")
    elif state["issues"]:
        footer = ("Corrígelo aquí mismo (p. ej. «total 45,20», «base 37,36» o «IVA 10») "
                  "y te pediré el SÍ cuando cuadre.")
    else:
        action = "apuntarlo como gasto" if mode == "gasto" else "guardarla"
        footer = (f"Responde *SÍ* para {action}. Si algo está mal, corrígelo "
                  "(p. ej. «total 45,20», «proveedor Leroy Merlin», «IVA 10» o «es un gasto»).")
    footer += " *NO* lo deja solo archivado."
    if count and count > 1:
        footer += " *TODAS* guarda las que estén completas."
    lines.append("")
    lines.append(footer)
    return "\n".join(lines)


def help_text() -> str:
    return ("No he entendido el cambio. Puedes escribir, por ejemplo: «total 45,20», "
            "«base 37,36», «IVA 10», «IRPF 15», «proveedor Leroy Merlin», "
            "«NIF B12345678», «fecha 12/09», «número F-123» o «es un gasto».")
