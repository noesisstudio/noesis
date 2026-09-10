"""Plan de intención sin efectos: interpretar no autoriza ejecutar.

El canal resuelve las referencias contra sus datos y solicita confirmación.
La emisión y la entrega al titular se distinguen de enviar al cliente.
"""
from dataclasses import dataclass
from contextvars import ContextVar
import hashlib
import json
import re

from .nlu import _norm

expected_invoice: ContextVar[tuple | None] = ContextVar('expected_invoice', default=None)


@dataclass(frozen=True)
class InvoicePlan:
    issue: bool = False
    owner_pdf: bool = False
    ambiguous_recipient: bool = False


def invoice_plan(message: str) -> InvoicePlan:
    text = _norm(message)
    if re.search(r"\b(?:no|cancelar|cancela|cancelado)\b", text):
        return InvoicePlan()
    issue = bool(re.search(r"\b(?:emitir|emite|emitela|emetre|emet|emetla)\b", text))
    pdf = bool(re.search(r"\bpdf\b", text))
    owner = bool(re.search(r"\b(?:enviame|enviam|mandame|pasame|passam|aqui|a mi)\b", text))
    customer = bool(re.search(r"\b(?:al cliente|a la clienta|enviaselo|mandaselo|a su correo)\b", text))
    return InvoicePlan(issue=issue, owner_pdf=pdf and owner and not customer,
                       ambiguous_recipient=issue and pdf and (not owner or customer))


def invoice_fingerprint(invoice: dict, lines: list[dict]) -> str:
    """Confirmar una versión concreta, no cualquier estado futuro del mismo ID."""
    fields = ('id', 'business_id', 'client_id', 'concept', 'base', 'vat_rate',
              'vat_amount', 'irpf_rate', 'irpf_amount', 'total', 'invoice_type', 'status')
    content = {'invoice': {key: invoice.get(key) for key in fields}, 'lines': lines}
    return hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()
