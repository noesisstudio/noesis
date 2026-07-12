"""Orquestación de documentos: subir, validar, leer (OCR) y borrar.

Es el ÚNICO punto que usa el servidor web. Encadena storage (disco) + repo (BD) +
ocr (lectura), de forma que la lógica delicada (validaciones, límites, OCR) está
toda junta y aislada.
"""

from __future__ import annotations

import json

from .. import config
from . import ocr, repo, storage


class UploadError(Exception):
    """Error de validación al subir un documento (mensaje apto para el usuario)."""


def upload(business_id: int, filename: str, data: bytes, *, kind: str = "documento",
           client_id: int | None = None, invoice_id: int | None = None,
           note: str | None = None, run_ocr: bool = True,
           auto_classify: bool = False) -> dict:
    """Valida y guarda un documento. Si es imagen y hay OCR, intenta leer el importe.

    Lanza UploadError con un mensaje claro si el archivo no es válido.
    """
    if not data:
        raise UploadError("El archivo está vacío.")
    if not storage.is_allowed(filename):
        raise UploadError("Formato no admitido. Sube un PDF o una foto (JPG/PNG/WEBP/HEIC).")
    max_bytes = config.MAX_UPLOAD_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise UploadError(f"El archivo supera el límite de {config.MAX_UPLOAD_MB} MB.")

    ocr_text = ocr_amount = None
    if run_ocr and storage.ext_of(filename) in storage.IMAGE_EXTS:
        result = ocr.extract(data)
        if result:
            ocr_text = result.get("text") or None
            ocr_amount = result.get("amount")

    stored_name = storage.save(business_id, filename, data)
    doc = repo.add(
        business_id, filename=filename, stored_name=stored_name,
        mime=storage.mime_for(filename), size=len(data), kind=kind,
        client_id=client_id, invoice_id=invoice_id, note=note,
        ocr_text=ocr_text, ocr_amount=ocr_amount,
        doc_status="pendiente_revisar" if auto_classify else "revisado")
    if auto_classify:
        proposal = classify(business_id, doc["id"])
        doc = repo.get(doc["id"], business_id) or doc
        doc["classification"] = proposal
    return doc


def classify(business_id: int, doc_id: int) -> dict | None:
    """Clasificación única para web y WhatsApp, siempre pendiente de confirmación."""
    from .. import db
    from ..adapters import extraction

    doc = repo.get(doc_id, business_id)
    payload = file_bytes(business_id, doc_id) if doc else None
    if not doc or not payload:
        return None
    data, mime, filename = payload
    business = db.get_business(business_id) or {}
    proposal = extraction.classify_document(
        data, mime, filename,
        text_hint=doc.get("ocr_text"),
        business_name=business.get("name"), business_nif=business.get("nif"),
    )
    kind = proposal.get("kind") or "documento"
    confidence = float(proposal.get("confidence") or 0)
    reason = proposal.get("reason") or "Revisa el tipo antes de registrarlo."
    # Una propuesta dudosa no cambia el tipo a la fuerza.
    applied_kind = kind if confidence >= 65 else "documento"
    repo.record_classification(
        doc_id, business_id, detected_kind=kind, confidence=confidence,
        method=proposal.get("method") or "heuristica", reason=reason,
    )
    repo.set_review(
        doc_id, business_id, kind=applied_kind,
        doc_status="pendiente_revisar", confidence=confidence,
        review_note=reason,
    )
    db.record_product_event(
        business_id, "document_classified",
        json.dumps({"kind": kind, "method": proposal.get("method"),
                    "confidence": round(confidence)}, separators=(",", ":")),
    )
    return {**proposal, "applied_kind": applied_kind,
            "needs_confirmation": True, "document_id": doc_id}


def file_bytes(business_id: int, doc_id: int) -> tuple[bytes, str, str] | None:
    """Devuelve (bytes, mime, filename) de un documento, o None si no existe."""
    doc = repo.get(doc_id, business_id)
    if not doc:
        return None
    data = storage.read(business_id, doc["stored_name"])
    if data is None:
        return None
    return data, doc.get("mime") or "application/octet-stream", doc["filename"]


def delete(business_id: int, doc_id: int) -> bool:
    """Borra metadato + fichero físico. True si existía."""
    doc = repo.delete(doc_id, business_id)
    if not doc:
        return False
    storage.delete(business_id, doc["stored_name"])
    return True


def invoice_draft(business_id: int, doc_id: int) -> dict | None:
    """Borrador de factura extraído por IA del documento, con dirección detectada.

    NUNCA crea registros: devuelve datos para que el usuario los revise. Si la IA
    no está disponible o no está segura, devuelve lo que haya (o None) y el
    documento queda pendiente de revisión manual. Los datos del documento son
    datos, no instrucciones (defensa en adapters/extraction.py).
    """
    from .. import db
    from ..adapters import extraction

    doc = repo.get(doc_id, business_id)
    if not doc:
        return None
    payload = file_bytes(business_id, doc_id)
    if not payload:
        return None
    data, mime, _filename = payload
    draft = extraction.extract_invoice(data, mime)
    if draft is None:
        repo.set_review(doc_id, business_id, doc_status="pendiente_revisar",
                        review_note="Sin extracción automática: revisar a mano.")
        return None
    business = db.get_business(business_id) or {}
    draft["direction"] = extraction.detect_direction(
        draft, business_nif=business.get("nif"),
        business_name=business.get("name"))
    kind = ("factura_emitida" if draft["direction"] == "emitida"
            else "factura_recibida" if draft["direction"] == "recibida"
            else None)
    repo.set_review(doc_id, business_id, kind=kind,
                    doc_status="pendiente_revisar",
                    confidence=draft.get("confidence"))
    if draft.get("supplier") or draft.get("supplier_nif"):
        known = db.find_supplier(business_id, nif=draft.get("supplier_nif"),
                                 name=draft.get("supplier"))
        draft["supplier_id"] = known["id"] if known else None
    return draft


def confirm_received_invoice(business_id: int, doc_id: int, *, total,
                             supplier_name: str | None = None,
                             supplier_nif: str | None = None,
                             supplier_id: int | None = None,
                             **fields) -> dict:
    """Confirmación humana del borrador: crea la recibida y vincula el documento.

    Crea el proveedor si no existe (por NIF o nombre exacto). Lanza ValueError
    con mensaje apto para el usuario si algo no cuadra.
    """
    from .. import db

    doc = repo.get(doc_id, business_id)
    if not doc:
        raise UploadError("Documento no encontrado.")
    if supplier_id is None and (supplier_name or supplier_nif):
        known = db.find_supplier(business_id, nif=supplier_nif,
                                 name=supplier_name)
        if known:
            supplier_id = known["id"]
        elif supplier_name:
            supplier_id = db.add_supplier(
                supplier_name, nif=supplier_nif, business_id=business_id)["id"]
    received = db.add_received_invoice(
        total, supplier_id=supplier_id, document_id=doc_id,
        business_id=business_id, **fields)
    repo.set_review(doc_id, business_id, kind="factura_recibida",
                    doc_status="revisado")
    repo.confirm_classification(doc_id, business_id, "factura_recibida")
    return received


def convert_ticket_to_expense(business_id: int, doc_id: int,
                              concept: str | None = None,
                              amount: float | None = None,
                              vat_rate: float | None = None,
                              spent_on: str | None = None) -> dict | None:
    """Convierte un ticket/factura escaneada en un gasto registrado.

    Usa el importe leído por OCR si no se pasa uno. Devuelve el gasto creado, o None
    si no hay importe disponible. Vincula el documento al gasto confirmado.
    """
    from .. import db
    doc = repo.get(doc_id, business_id)
    if not doc:
        return None
    amount = amount if amount is not None else doc.get("ocr_amount")
    if not amount or float(amount) <= 0:
        return None
    concept = (concept or doc.get("filename") or "Gasto de ticket").strip()
    expense = db.add_expense(
        concept,
        float(amount),
        vat_rate=vat_rate,
        category="Ticket",
        spent_on=spent_on,
        document_id=doc_id,
        business_id=business_id,
    )
    repo.set_review(doc_id, business_id, kind="ticket", doc_status="revisado")
    repo.confirm_classification(doc_id, business_id, "ticket")
    return expense
