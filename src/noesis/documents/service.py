"""Orquestación de documentos: subir, validar, leer (OCR) y borrar.

Es el ÚNICO punto que usa el servidor web. Encadena storage (disco) + repo (BD) +
ocr (lectura), de forma que la lógica delicada (validaciones, límites, OCR) está
toda junta y aislada.
"""

from __future__ import annotations

from .. import config
from . import ocr, repo, storage


class UploadError(Exception):
    """Error de validación al subir un documento (mensaje apto para el usuario)."""


def upload(business_id: int, filename: str, data: bytes, *, kind: str = "documento",
           client_id: int | None = None, invoice_id: int | None = None,
           note: str | None = None, run_ocr: bool = True) -> dict:
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
    return repo.add(
        business_id, filename=filename, stored_name=stored_name,
        mime=storage.mime_for(filename), size=len(data), kind=kind,
        client_id=client_id, invoice_id=invoice_id, note=note,
        ocr_text=ocr_text, ocr_amount=ocr_amount)


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


def convert_ticket_to_expense(business_id: int, doc_id: int,
                              concept: str | None = None,
                              amount: float | None = None) -> dict | None:
    """Convierte un ticket/factura escaneada en un gasto registrado.

    Usa el importe leído por OCR si no se pasa uno. Devuelve el gasto creado, o None
    si no hay importe disponible. Deja el documento ligado por nota (trazabilidad).
    """
    from .. import db
    doc = repo.get(doc_id, business_id)
    if not doc:
        return None
    amount = amount if amount is not None else doc.get("ocr_amount")
    if not amount or float(amount) <= 0:
        return None
    concept = (concept or doc.get("filename") or "Gasto de ticket").strip()
    return db.add_expense(concept, float(amount), category="Ticket",
                          business_id=business_id)
