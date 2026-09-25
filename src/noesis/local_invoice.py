"""Planes locales de factura, sin red ni efectos sobre datos del negocio.

Gramática acotada y anclada: nunca se aprovecha una coincidencia parcial.
El motor de facturación existente sigue siendo la única calculadora monetaria.
"""
from dataclasses import dataclass
from decimal import Decimal
import re
import unicodedata

from . import config

NUMBER = r"(?:\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d{1,7}(?:[.,]\d{1,2})?)"


def enabled() -> bool:
    return config.LOCAL_PLANNER_ENABLED and config.ASSISTANT_REVIEW_ENABLED


def normalized(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower())
                   if not unicodedata.combining(c))


def decimal_number(text: str) -> Decimal:
    if not re.fullmatch(NUMBER, text):
        raise ValueError("Indica un número positivo, sin fórmulas ni signos.")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", text):
        text = text.replace(".", "")
    value = Decimal(text)
    if not value.is_finite() or not 0 < value <= 1_000_000:
        raise ValueError("La cantidad o precio debe ser positivo y no superar un millón.")
    return value


@dataclass(frozen=True)
class InvoiceLine:
    description: str
    quantity: Decimal
    unit_price: Decimal


@dataclass(frozen=True)
class LocalInvoicePlan:
    client: str
    lines: tuple[InvoiceLine, ...]
    vat: int
    invoice_type: str

    def arguments(self) -> dict:
        return {
            "cliente": self.client, "concepto": "; ".join(x.description for x in self.lines),
            "base": 0, "iva": self.vat, "tipo_factura": self.invoice_type,
            "lineas": [{"description": x.description, "quantity": str(x.quantity),
                        "unit_price": str(x.unit_price), "vat_rate": self.vat}
                       for x in self.lines],
        }


def parse(message: str) -> LocalInvoicePlan | None:
    """Admite líneas con precio NETO explícito; lo demás no se interpreta aquí."""
    if len(message) > 4000:
        return None
    text = message.strip().rstrip(".")
    match = re.fullmatch(
        r"(?:(?:crea(?:me)?|créame|hazme|prepara|fes(?:-me)?)\s+(?:una?\s+)?)?"
        r"(factura|ticket|tiquet)(?:\s+de\s+(?:venta|venda))?\s+"
        r"(?:para|a|per\s+a)\s+(.{1,160}?)\s+(?:con|amb|:)\s+(.+)",
        text, re.I,
    )
    if not match:
        return None
    kind, client, body = match.groups()
    # No interpretar negación, acciones adicionales o datos fiscales omitidos.
    if re.search(r"\b(?:no|sin|sense|menos|menys|irpf)\b", normalized(text)):
        return None
    tax = re.search(r"[,;]?\s+(?:más|mas|més|mes|\+)\s+IVA\s*(?:(?:del|al)\s*)?(0|4|10|21)\s*%$", body, re.I)
    if not tax:
        return None
    body = body[:tax.start()].strip()
    parts = re.split(r"\s*;\s*|\s+(?:y|i)\s+(?=\d)", body, flags=re.I)
    if not 1 <= len(parts) <= 20 or not client.strip():
        return None
    lines = []
    for part in parts:
        line = re.fullmatch(
            rf"({NUMBER})\s+([^\d\n;]{{1,100}}?)\s+a\s+({NUMBER})"
            r"\s*(?:€|euros?|eur)(?:\s+(?:cada\s+un[oa]|la\s+unidad))?",
            part.strip(), re.I,
        )
        if not line:
            return None
        quantity, description, price = line.groups()
        if any(c in description for c in "<>={}[]"):
            return None
        try:
            lines.append(InvoiceLine(description.strip(), decimal_number(quantity), decimal_number(price)))
        except ValueError:
            return None
    if len("; ".join(x.description for x in lines)) > 500:
        return None
    return LocalInvoicePlan(client.strip(), tuple(lines), int(tax.group(1)),
                            "F1" if kind.lower() == "factura" else "F2")


def revise(message: str, arguments: dict) -> dict | None:
    """Corrige SOLO una propuesta pendiente; nunca busca ni edita una emitida."""
    text = normalized(message).strip().rstrip(".")
    text = re.sub(r"^no,?\s+", "", text)
    detail = re.fullmatch(
        r"(?:cambia|corrige|pon)\s+(?:la\s+)?linea\s+(\d{1,2})\s+"
        r"(concepto|iva)\s+(?:a\s+)?(.+)", text)
    if detail:
        position, field, value = detail.groups()
        lines = [dict(line) for line in arguments.get("lineas", [])]
        index = int(position) - 1
        if not 0 <= index < len(lines):
            raise ValueError("Esa línea no está en la propuesta. Indica una línea existente.")
        if field == "iva":
            rate = re.fullmatch(r"(0|4|10|21)\s*%?", value)
            if not rate:
                raise ValueError("Indica un IVA de 0, 4, 10 o 21% para esa línea.")
            lines[index]["vat_rate"] = int(rate.group(1))
        else:
            # Mantener mayúsculas y acentos del concepto dictado, no el texto normalizado.
            original = re.sub(r"^no,?\s+", "", message.strip().rstrip("."), flags=re.I)
            description = original[detail.start(3):].strip()
            if not description or len(description) > 500 or any(c in description for c in "<>={}[];\n"):
                raise ValueError("Indica un concepto de texto para una sola línea.")
            lines[index]["description"] = description
        return {**arguments, "lineas": lines,
                "concepto": "; ".join(line["description"] for line in lines)}
    explicit = re.fullmatch(
        rf"(?:cambia|corrige|pon)\s+(?:la\s+)?linea\s+(\d{{1,2}})\s+"
        rf"(cantidad|precio)\s+(?:a\s+)?({NUMBER})(?:\s*(?:euros?|€|unidades?))?", text)
    natural = re.fullmatch(rf"(?:las?|los?)\s+([a-z ]{{1,60}}?)\s+eran\s+({NUMBER})", text)
    client = re.fullmatch(r"(?:cambia|corrige)\s+(?:el\s+)?cliente\s+a\s+(.{1,160})", message.strip(), re.I)
    if client:
        return {**arguments, "cliente": client.group(1).strip(), "cliente_id": None}
    if not explicit and not natural:
        return None
    lines = [dict(line) for line in arguments.get("lineas", [])]
    if not lines:
        raise ValueError("La propuesta no tiene líneas identificables. Escribe la orden completa.")
    if explicit:
        position, field, number = explicit.groups()
        index = int(position) - 1
    else:
        label, number = natural.groups()
        matches = [i for i, line in enumerate(lines)
                   if re.search(r"\b" + re.escape(label) + r"\b", normalized(line["description"]))]
        if len(matches) != 1:
            raise ValueError("No identifico una sola línea. Indica su número y el cambio.")
        index, field = matches[0], "cantidad"
    if not 0 <= index < len(lines):
        raise ValueError("Esa línea no está en la propuesta. Indica una línea existente.")
    lines[index]["quantity" if field == "cantidad" else "unit_price"] = str(decimal_number(number))
    return {**arguments, "lineas": lines}


def remember_invoice(business_id: int, actor: str, invoice_id: int) -> None:
    """Foco efímero y aislado; almacena un ID verificado, nunca texto del modelo."""
    from . import db
    if db.get_invoice(invoice_id, business_id):
        db.set_pending_action(business_id, "local-invoice:" + actor, "invoice_focus",
                              {"invoice_id": invoice_id}, ttl_minutes=10)


def reference_response(business_id: int, actor: str, message: str) -> dict | None:
    """Lectura de PDF o propuesta de emisión; jamás busca la última factura global."""
    import json
    from . import action_review, db
    text = normalized(message).strip().rstrip(".?!")
    issue = re.fullmatch(r"(?:emite|emitir|emitela|emet|emetla)(?:\s+(?:la\s+)?factura\s*#?(\d{1,9}))?", text)
    pdf = re.fullmatch(r"(?:pasame|dame|enviame|descarga|muestrame|passam)\s+(?:el\s+)?pdf"
                       r"(?:\s+(?:de\s+)?(?:la\s+)?factura(?:\s*#?(\d{1,9}))?)?", text)
    if not issue and not pdf:
        return None
    reference = (issue or pdf).group(1)
    if reference:
        invoice_id = int(reference)
    else:
        focus = db.get_pending_action(business_id, "local-invoice:" + actor)
        invoice_id = json.loads(focus["payload"]).get("invoice_id") if focus else None
    invoice = db.get_invoice(invoice_id, business_id) if invoice_id else None
    if not invoice:
        return {"reply": "Indica el número de una factura de tu negocio. No tengo un documento inequívoco en esta conversación.", "source": "local"}
    if issue:
        return action_review.propose(business_id, "enviar_factura", {"factura_id": invoice["id"]})
    url = f"/api/{business_id}/invoices/{invoice['id']}/pdf"
    label = "borrador" if invoice["status"] == "borrador" else "factura"
    return {"reply": f"Aquí tienes el PDF del {label} #{invoice['id']}: [Abrir PDF]({url}). No he emitido ni enviado nada a un cliente.",
            "source": "local", "pdf_url": url}
