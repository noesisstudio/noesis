"""Adaptador de facturación.

Define una interfaz común (`InvoicingProvider`) y dos implementaciones:

  - InternalInvoicingProvider -> emisión REAL interna: numeración correlativa por
                                 negocio + PDF real (web/invoice_pdf.py). No registra
                                 en Verifactu (eso lo hará el proveedor homologado).
  - HoldedInvoicingProvider   -> conexión real con la API de Holded (Verifactu),
                                 se activa cuando hay HOLDED_API_KEY.

Verifactu/TicketBAI NO se construyen aquí: los resuelve el proveedor homologado
(Holded/Quipu). Nosotros solo le pasamos los datos.
"""

from __future__ import annotations

from datetime import date, timedelta
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
    registro en Verifactu queda pendiente del proveedor homologado (no es
    obligatorio para autónomos hasta jul-2027).
    """

    def __init__(self, payment_term_days: int = 15):
        self.payment_term_days = payment_term_days

    def _next_number(self, business_id: int) -> str:
        """Siguiente número correlativo de ESTE negocio (serie por año)."""
        from .. import db
        year = date.today().year
        with db.get_conn() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM invoices WHERE business_id=? "
                "AND number IS NOT NULL AND number LIKE ?",
                (business_id, f"{year}/%"),
            ).fetchone()[0]
        return f"{year}/{n + 1:04d}"

    def issue(self, invoice: dict, client: dict) -> dict:
        business_id = invoice.get("business_id")
        number = self._next_number(business_id)
        due = (date.today() + timedelta(days=self.payment_term_days)).isoformat()
        return {
            "number": number,
            "pdf_url": f"/api/{business_id}/invoices/{invoice.get('id')}/pdf",
            "verifactu_id": None,
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
    """Proveedor activo: Holded si hay API key configurada; si no, emisión interna real."""
    from .. import config
    if config.HOLDED_API_KEY:
        return HoldedInvoicingProvider(config.HOLDED_API_KEY)
    return InternalInvoicingProvider()
