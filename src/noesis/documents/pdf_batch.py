"""Separación local explícita de un lote PDF, sin crear apuntes contables."""
from io import BytesIO
import re

from .. import config
from . import repo, service, validation

MAX_PARTS = 20


def _source(business_id: int, doc_id: int):
    from pypdf import PdfReader

    doc = repo.get(doc_id, business_id)
    if not doc:
        raise ValueError("Documento no encontrado.")
    if any(doc.get(key) for key in ("invoice_id", "received_invoice_id", "expense_id")):
        raise ValueError("Este archivo ya está vinculado a un registro. Revisa ese registro antes de separar el PDF.")
    payload = service.file_bytes(business_id, doc_id)
    if not payload or payload[1] != "application/pdf":
        raise ValueError("La separación requiere un PDF original disponible.")
    data = payload[0]
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValueError("El PDF supera el tamaño permitido.")
    validation.validate("lote.pdf", data)
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise ValueError("El PDF está cifrado. Sube una copia sin contraseña.")
        if "/AcroForm" in reader.trailer["/Root"]:
            raise ValueError("No se separan PDF con firmas o formularios. Conserva el original y solicita las facturas individuales.")
        count = len(reader.pages)
        if not 2 <= count <= config.MAX_PDF_PAGES:
            raise ValueError(f"El lote debe tener entre 2 y {config.MAX_PDF_PAGES} páginas.")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("No se puede abrir este PDF con seguridad.") from exc
    return doc, reader, count


def page_groups(ranges: str, count: int) -> list[tuple[int, int]]:
    """Rangos exhaustivos, ordenados y sin páginas repetidas u omitidas."""
    if not isinstance(ranges, str) or len(ranges) > 500:
        raise ValueError("Indica rangos como 1-2; 3; 4-5.")
    groups = []
    next_page = 1
    for item in ranges.split(";"):
        match = re.fullmatch(r"\s*(\d{1,3})(?:\s*-\s*(\d{1,3}))?\s*", item)
        if not match:
            raise ValueError("Separa cada factura con punto y coma: 1-2; 3; 4-5.")
        start, end = int(match[1]), int(match[2] or match[1])
        if start != next_page or end < start or end > count:
            raise ValueError("Incluye todas las páginas en orden, sin repetir ni omitir ninguna.")
        groups.append((start, end))
        next_page = end + 1
    if next_page != count + 1 or not 2 <= len(groups) <= MAX_PARTS:
        raise ValueError(f"Separa el lote completo en entre 2 y {MAX_PARTS} facturas.")
    return groups


def inspect(business_id: int, doc_id: int) -> dict:
    doc, _reader, count = _source(business_id, doc_id)
    with repo._conn() as conn:
        previous = conn.execute(
            "SELECT reason FROM document_classifications WHERE document_id=? "
            "AND business_id=? AND method='pdf_batch' ORDER BY id LIMIT 1",
            (doc_id, business_id),
        ).fetchone()
    return {"document_id": doc["id"], "pages": count, "max_parts": MAX_PARTS,
            "ranges": previous["reason"] if previous else ""}


def split(business_id: int, doc_id: int, ranges: str) -> dict:
    """Reintento por hash; ante fallo parcial devuelve los archivos ya guardados.

    No se modifica el original ni se heredan clientes/importes del lote. Cada
    parte pasa por las defensas de upload y queda pendiente de revisión humana.
    """
    from pypdf import PdfWriter

    _doc, reader, count = _source(business_id, doc_id)
    groups = page_groups(ranges, count)
    outputs = []
    total_bytes = 0
    for start, end in groups:
        writer = PdfWriter()
        for index in range(start - 1, end):
            writer.add_page(reader.pages[index])
        stream = BytesIO()
        writer.write(stream)
        data = stream.getvalue()
        total_bytes += len(data)
        if total_bytes > 2 * config.MAX_UPLOAD_MB * 1024 * 1024:
            raise ValueError("Las partes superan el tamaño de procesamiento permitido.")
        validation.validate("factura.pdf", data)
        outputs.append((start, end, data))

    # La clasificación identifica el original como lote, no como una factura.
    # Se registra antes de guardar partes para bloquear también lotes parciales.
    repo.register_pdf_batch(doc_id, business_id, ";".join(f"{start}-{end}" for start, end in groups))
    documents = []
    for start, end, data in outputs:
        try:
            child = service.upload(
                business_id, f"lote-{doc_id}-paginas-{start}-{end}.pdf", data,
                run_ocr=False, auto_classify=False, pending_review=True,
                note=f"Copia separada del documento #{doc_id}. Páginas {start}-{end}. Revisar contra el original.",
            )
            reused = False
        except service.DuplicateDocument as exc:
            child = repo.get(exc.existing_id, business_id)
            reused = True
        except Exception:  # No repetir silenciosamente ni ocultar un lote parcial.
            return {"ok": False, "documents": documents,
                    "error": "No se pudo completar la separación. Las partes listadas ya están guardadas; reintenta los mismos rangos para continuar sin duplicarlas."}
        documents.append({"id": child["id"], "pages": f"{start}-{end}", "reused": reused})
    repo.set_review(doc_id, business_id, kind="documento", doc_status="revisado",
                    review_note="Lote original conservado. Revisa y registra las facturas individuales; este original no se contabiliza.")
    return {"ok": True, "documents": documents, "original_id": doc_id}
