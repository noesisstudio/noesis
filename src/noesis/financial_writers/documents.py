"""Confirmaciones documentales locales en una única transacción prestada."""

from decimal import Decimal

from ..documents import repo

from ..documents.service import UploadError

from . import readers, purchasing

from .boundary import run


def _resolve_supplier(
    conn, business_id: int, *, name: str | None = None, nif: str | None = None
) -> int | None:
    """Proveedor existente por NIF o nombre exacto; si no existe y hay nombre, se crea."""
    if not (name or nif):
        return None
    known = readers.find_supplier(conn, business_id, nif=nif, name=name)
    if known:
        return known["id"]
    if name:
        return readers.add_supplier(conn, name, nif=nif, business_id=business_id)["id"]
    return None


def _mutate_record_received_invoice(
    conn,
    business_id: int,
    *,
    total,
    supplier_name: str | None = None,
    supplier_nif: str | None = None,
    note: str | None = None,
    **fields,
) -> dict:
    """Factura recibida confirmada que no tiene archivo propio (fila de un extracto
    o varias facturas en una misma página). El original sigue en Documentos."""
    supplier_id = _resolve_supplier(conn, business_id, name=supplier_name, nif=supplier_nif)
    return purchasing._mutate_add_received_invoice(
        conn, total, supplier_id=supplier_id, note=note, business_id=business_id, **fields
    )


def record_received_invoice(borrowed, *args, legacy=False, **kwargs):
    return run(
        _mutate_record_received_invoice,
        borrowed,
        args,
        kwargs,
        kind="received_invoice",
        legacy=legacy,
    )


def _mutate_confirm_received_invoice(
    conn,
    business_id: int,
    doc_id: int,
    *,
    total,
    supplier_name: str | None = None,
    supplier_nif: str | None = None,
    supplier_id: int | None = None,
    **fields,
) -> dict:
    """Confirmación humana del borrador: crea la recibida y vincula el documento.

    Crea el proveedor si no existe (por NIF o nombre exacto). Lanza ValueError
    con mensaje apto para el usuario si algo no cuadra.
    """
    doc = repo._get_with_conn(conn, doc_id, business_id)
    if not doc:
        raise UploadError("Documento no encontrado.")
    if repo._is_batch_source_with_conn(conn, doc_id, business_id):
        raise ValueError("Este PDF es un lote. Revisa y registra las facturas individuales.")
    if supplier_id is None:
        supplier_id = _resolve_supplier(conn, business_id, name=supplier_name, nif=supplier_nif)
    received = purchasing._mutate_add_received_invoice(
        conn, total, supplier_id=supplier_id, document_id=doc_id, business_id=business_id, **fields
    )
    repo._set_review_with_conn(
        conn, doc_id, business_id, kind="factura_recibida", doc_status="revisado"
    )
    _confirm_classification(conn, doc_id, business_id, "factura_recibida")
    return received


def confirm_received_invoice(borrowed, *args, legacy=False, **kwargs):
    return run(
        _mutate_confirm_received_invoice,
        borrowed,
        args,
        kwargs,
        kind="received_invoice",
        legacy=legacy,
    )


def _mutate_convert_ticket_to_expense(
    conn,
    business_id: int,
    doc_id: int,
    concept: str | None = None,
    amount: float | None = None,
    vat_rate: float | None = None,
    spent_on: str | None = None,
    *,
    vat_amount=None,
    category="Ticket",
    project_id=None,
) -> dict | None:
    """Convierte un ticket/factura escaneada en un gasto registrado.

    Usa el importe leído por OCR si no se pasa uno. Devuelve el gasto creado, o None
    si no hay importe disponible. Vincula el documento al gasto confirmado.
    """
    doc = repo._get_with_conn(conn, doc_id, business_id)
    if not doc:
        return None
    amount = amount if amount is not None else doc.get("ocr_amount")
    if not amount or Decimal(str(amount)) <= 0:
        return None
    concept = (concept or doc.get("filename") or "Gasto de ticket").strip()
    expense = purchasing._mutate_add_expense(
        conn,
        concept,
        Decimal(str(amount)),
        vat_rate=vat_rate,
        category=category,
        spent_on=spent_on,
        document_id=doc_id,
        project_id=project_id if project_id is not None else doc.get("project_id"),
        business_id=business_id,
        vat_amount=vat_amount,
    )
    repo._set_review_with_conn(conn, doc_id, business_id, kind="ticket", doc_status="revisado")
    _confirm_classification(conn, doc_id, business_id, "ticket")
    return expense


def convert_ticket_to_expense(borrowed, *args, legacy=False, **kwargs):
    return run(
        _mutate_convert_ticket_to_expense, borrowed, args, kwargs, kind="expense", legacy=legacy
    )


def _confirm_classification(conn, doc_id, business_id, kind):
    result = repo._confirm_classification_with_conn(conn, doc_id, business_id, kind)
    if result:
        conn.observations.append(
            (
                "observe_useful_action",
                (business_id, "document_classification_confirmed"),
                {
                    "entity_type": "document",
                    "entity_id": doc_id,
                    "idempotency_key": f"document_classification:{result['id']}",
                    "metadata": {
                        "detected_kind": result.get("detected_kind"),
                        "confirmed_kind": kind,
                        "corrected": result.get("detected_kind") != kind,
                    },
                },
            )
        )
    return result
