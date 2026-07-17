"""Adaptador de facturación.

Define una interfaz común (`InvoicingProvider`) y dos implementaciones:

  - InternalInvoicingProvider -> emisión REAL interna: numeración correlativa por
                                 negocio + PDF real + registro Veri*Factu cuando el
                                 negocio activa el modo nativo.
  - HoldedInvoicingProvider   -> conexión real con la API de Holded (Verifactu),
                                 se activa cuando hay HOLDED_API_KEY.

Verifactu/TicketBAI NO se construyen aquí: los resuelve el proveedor homologado
(Holded/Quipu). Nosotros solo le pasamos los datos.
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


class HoldedInvoicingProvider:
    """Integración real con la API de Holded para emisión con Verifactu.

    Crea la factura en Holded (que se encarga de la numeración legal y del
    registro en Verifactu/TicketBAI). Si la llamada falla, cae al proveedor
    interno como respaldo para no bloquear al autónomo.

    Docs: https://developers.holded.com/reference/create-document-1
    """

    _API = "https://api.holded.com/api/invoicing/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _post(self, path: str, data: dict) -> dict:
        import json as _json
        import urllib.request
        url = f"{self._API}/{path}"
        body = _json.dumps(data).encode()
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("key", self.api_key)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=20) as resp:
            return _json.loads(resp.read().decode())

    def _find_or_create_contact(self, client: dict) -> str | None:
        """Busca o crea el contacto en Holded y devuelve su id."""
        import json as _json
        import urllib.request
        name = client.get("name") or "Cliente"
        # Buscar por nombre
        try:
            req = urllib.request.Request(
                f"{self._API.replace('/invoicing/v1', '')}/contacts/v1/contacts",
                headers={"key": self.api_key})
            contacts = _json.loads(urllib.request.urlopen(req, timeout=15).read())
            for c in contacts:
                if c.get("name", "").lower() == name.lower():
                    return c.get("id")
        except Exception:  # noqa: BLE001
            pass
        # Crear contacto
        contact_data = {"name": name, "type": "client", "isperson": True}
        if client.get("nif"):
            contact_data["vatnumber"] = client["nif"]
        if client.get("email"):
            contact_data["email"] = client["email"]
        if client.get("address"):
            contact_data["billAddress"] = {"address": client["address"]}
        try:
            resp = self._post("../contacts/v1/contacts", contact_data)
            return resp.get("id")
        except Exception:  # noqa: BLE001
            return None

    def issue(self, invoice: dict, client: dict) -> dict:
        import logging
        log = logging.getLogger("noesis.invoicing")
        contact_id = self._find_or_create_contact(client)
        item = {
            "name": invoice.get("concept") or "Servicio",
            "units": 1,
            "subtotal": invoice.get("base", 0),
            "tax": invoice.get("vat_rate", 21),
        }
        if invoice.get("irpf_rate"):
            item["retention"] = invoice["irpf_rate"]
        doc_data: dict = {"items": [item]}
        if contact_id:
            doc_data["contactId"] = contact_id
        else:
            doc_data["contactName"] = client.get("name") or "Cliente"
        try:
            resp = self._post("documents/invoice", doc_data)
            return {
                "number": resp.get("invoiceNum") or resp.get("number"),
                "pdf_url": resp.get("pdfUrl"),
                "verifactu_id": resp.get("id"),
                "due_date": resp.get("dueDate"),
                "sent_to": client.get("email") or client.get("name"),
            }
        except Exception as e:  # noqa: BLE001
            log.error("Holded falló, usando emisión interna: %s", e)
            return InternalInvoicingProvider().issue(invoice, client)


def get_provider() -> InvoicingProvider:
    """Holded si hay API key; si no, emisión interna (correlativa por negocio + PDF)."""
    from .. import config
    if config.HOLDED_API_KEY:
        return HoldedInvoicingProvider(config.HOLDED_API_KEY)
    return InternalInvoicingProvider()
