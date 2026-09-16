"""Una sola lectura por documento: IA consentida y texto local, contrastados.

La IA lee mejor fotos y maquetas complejas; el texto local es gratuito, privado y
no se equivoca de cifra cuando el PDF es digital. Se combinan así: la IA propone,
el texto rellena lo que falta y, si los totales no coinciden, se le pregunta al
titular en vez de elegir uno a escondidas.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from io import BytesIO

from . import local_reader, pdf_text

log = logging.getLogger("noesis.documents.reading")

PDF_MIME = "application/pdf"
_FILLABLE = (
    "number", "issued_on", "due_on", "supplier", "supplier_nif", "customer",
    "customer_nif", "base", "vat_rate", "vat_amount", "irpf_amount", "total",
)


def page_count(data: bytes, mime: str) -> int:
    if mime != PDF_MIME:
        return 1
    try:
        from pypdf import PdfReader

        return len(PdfReader(BytesIO(data), strict=False).pages)
    except Exception:  # noqa: BLE001 - PDF ilegible: se trata como una sola pieza.
        return 0


def _plain(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


def _plain_document(document: dict) -> dict:
    return {key: _plain(value) for key, value in document.items()}


def merge(ai: dict | None, local: dict | None) -> dict:
    """Combina ambas lecturas sin ocultar desacuerdos."""
    if ai and (ai.get("documents") or ai.get("statement")):
        documents = [_plain_document(document) for document in ai.get("documents") or []]
        statement = ai.get("statement")
        source = "ia"
        local_documents = (local or {}).get("documents") or []
        if len(documents) == len(local_documents) and documents:
            for document, text_document in zip(documents, local_documents):
                text_document = _plain_document(text_document)
                filled = False
                for field in _FILLABLE:
                    if document.get(field) in (None, "") and text_document.get(field) not in (None, ""):
                        document[field] = text_document[field]
                        filled = True
                ai_total, text_total = document.get("total"), text_document.get("total")
                if (
                    ai_total is not None and text_total is not None
                    and "total" not in (text_document.get("guessed") or [])
                    and abs(float(ai_total) - float(text_total)) > 0.02
                ):
                    document.setdefault("conflicts", []).append(
                        {"field": "total", "values": [float(ai_total), float(text_total)]}
                    )
                if filled:
                    source = "mixto"
        if not statement and (local or {}).get("statement") and not documents:
            statement = local["statement"]
        return {"documents": documents, "statement": statement, "source": source}
    if local and (local.get("documents") or local.get("statement")):
        statement = local.get("statement")
        if statement:
            statement = {
                **statement,
                "items": [_plain_document(row) for row in statement.get("items") or []],
            }
        return {
            "documents": [_plain_document(document) for document in local.get("documents") or []],
            "statement": statement,
            "source": "texto",
        }
    return {"documents": [], "statement": None, "source": "ninguno"}


def read(business: dict, document: dict, data: bytes, mime: str, *,
         allow_ai: bool, business_id: int | None = None) -> dict:
    """Lectura completa de un documento ya guardado. Nunca crea registros."""
    from ..adapters import extraction

    business = business or {}
    pages = pdf_text.extract_pages(data) if mime == PDF_MIME else None
    text = document.get("ocr_text")
    if not text and pages:
        text = "\n".join(pages)
    local = None
    try:
        local = local_reader.read(
            text, pages=pages, business_nif=business.get("nif"),
            business_name=business.get("name"),
        )
    except Exception as exc:  # noqa: BLE001 - la lectura local nunca rompe la entrada.
        log.warning("La lectura local del documento falló: %s", type(exc).__name__)
    ai = None
    if allow_ai:
        ai = extraction.read_document(
            data, mime, business_name=business.get("name"),
            business_nif=business.get("nif"), business_id=business_id,
        )
    result = merge(ai, local)
    result["page_count"] = page_count(data, mime)
    result["ai_used"] = bool(ai)
    return result
