"""Adaptador de facturación.

Define una interfaz común (`InvoicingProvider`) y dos implementaciones:

  - MockInvoicingProvider  -> simula la emisión (para el prototipo, sin cuentas)
  - HoldedInvoicingProvider -> stub listo para conectar la API real de Holded
                               (https://developers.holded.com) cuando toque.

Verifactu/TicketBAI NO se construyen aquí: los resuelve el proveedor real
(Holded/Quipu) que ya está homologado. Nosotros solo le pasamos los datos.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Protocol


class InvoicingProvider(Protocol):
    """Contrato que cualquier proveedor de facturación debe cumplir."""

    def issue(self, invoice: dict, client: dict) -> dict:
        """Emite la factura y devuelve {number, pdf_url, verifactu_id, due_date}."""
        ...


class MockInvoicingProvider:
    """Emisión simulada para el prototipo. No envía nada de verdad."""

    def __init__(self, payment_term_days: int = 15):
        self.payment_term_days = payment_term_days

    def _next_number(self) -> str:
        """Siguiente número correlativo basado en las facturas ya emitidas."""
        from .. import db
        with db.get_conn() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM invoices WHERE number IS NOT NULL"
            ).fetchone()[0]
        return f"F-{date.today().year}-{n + 1:04d}"

    def issue(self, invoice: dict, client: dict) -> dict:
        number = self._next_number()
        due = (date.today() + timedelta(days=self.payment_term_days)).isoformat()
        return {
            "number": number,
            "pdf_url": f"(simulado) factura_{number}.pdf",
            "verifactu_id": f"MOCK-{number}",
            "due_date": due,
            "sent_to": client.get("phone") or client.get("name"),
        }


class HoldedInvoicingProvider:
    """Stub de integración real con Holded. Pendiente de implementar.

    Cuando el negocio esté validado:
      POST https://api.holded.com/api/invoicing/v1/documents/invoice
      Headers: {"key": HOLDED_API_KEY}
      Body: {contactName, items:[{name, units, price, tax}], ...}
    Holded devuelve el documento con su numeración legal + Verifactu.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key

    def issue(self, invoice: dict, client: dict) -> dict:  # pragma: no cover
        raise NotImplementedError(
            "Integración con Holded pendiente. Se activa cuando validemos el "
            "negocio y demos de alta la cuenta Holded + API key. Ver "
            "https://developers.holded.com/reference/create-document-1"
        )


def get_provider() -> InvoicingProvider:
    """Devuelve el proveedor activo. Hoy: mock. Mañana: Holded según config."""
    return MockInvoicingProvider()
