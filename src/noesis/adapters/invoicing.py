"""Frontera de facturación nativa de Bynoesis.

La emisión, numeración, PDF y registro Veri*Factu son de desarrollo propio. El
contrato se conserva para desacoplar las herramientas del motor interno, no para
delegar facturas o datos fiscales a un proveedor externo.
"""

from __future__ import annotations

from typing import Protocol


class InvoicingProvider(Protocol):
    """Contrato que cualquier proveedor de facturación debe cumplir."""

    def issue(self, invoice: dict, client: dict) -> dict:
        """Emite la factura y devuelve {number, pdf_url, verifactu_id, due_date}."""
        ...


class InternalInvoicingProvider:
    """Emisión real interna, sin proveedor externo.

    Asigna un número de factura CORRELATIVO POR NEGOCIO (cada autónomo tiene su
    propia serie, como exige la ley) y el PDF real se genera bajo demanda. El
    registro Veri*Factu se genera en la misma transacción cuando el negocio activa
    el modo nativo.
    """

    def __init__(self, payment_term_days: int | None = None):
        self.payment_term_days = payment_term_days

    def issue(self, invoice: dict, client: dict) -> dict:
        from .. import db
        business_id = invoice.get("business_id")
        issued = db.issue_invoice(
            invoice["id"], business_id, payment_term_days=self.payment_term_days
        )
        return {
            "number": issued["number"],
            "pdf_url": f"/api/{business_id}/invoices/{invoice.get('id')}/pdf",
            "verifactu_id": None,
            "due_date": issued["due_date"],
            "sent_to": client.get("phone") or client.get("name"),
        }


def get_provider() -> InvoicingProvider:
    """Devuelve siempre el motor propio de facturación de Bynoesis."""
    return InternalInvoicingProvider()
