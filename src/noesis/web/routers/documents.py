"""Rutas de documentos, proveedores y facturas recibidas."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from ... import db
from ..deps import _read_json

router = APIRouter()

# =========================================================== DOCUMENTOS ===== #
@router.get("/api/{business_id}/documents")
def api_documents(business_id: int, client_id: int = 0):
    from ...documents import repo as docrepo
    return docrepo.list_for_business(business_id, client_id or None)


@router.get("/api/{business_id}/documents/ocr-status")
def api_ocr_status(business_id: int):
    """Indica si la lectura de fotos (OCR) está activa en este servidor."""
    from ...documents import ocr
    return {"ocr": ocr.available()}


@router.post("/api/{business_id}/documents")
async def api_upload_document(business_id: int, file: UploadFile = File(...),
                              kind: str = Form("documento"),
                              client_id: str = Form(""), invoice_id: str = Form(""),
                              note: str = Form("")):
    from ...documents import service as docservice
    # Lectura ACOTADA: nunca cargamos en memoria más de lo permitido. Sin este tope,
    # un archivo enorme agotaría la RAM antes de que el servicio validara el tamaño.
    max_bytes = config.MAX_UPLOAD_MB * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        return JSONResponse(
            {"error": f"El archivo supera el límite de {config.MAX_UPLOAD_MB} MB."},
            status_code=413,
        )

    def _opt_int(v):
        try:
            return int(v) if str(v).strip() else None
        except (TypeError, ValueError):
            return None

    try:
        doc = docservice.upload(business_id, file.filename or "documento", data,
                                kind=kind, client_id=_opt_int(client_id),
                                invoice_id=_opt_int(invoice_id), note=note or None)
    except docservice.UploadError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return doc


@router.get("/api/{business_id}/documents/{doc_id}/file")
def api_document_file(business_id: int, doc_id: int):
    from ...documents import service as docservice
    got = docservice.file_bytes(business_id, doc_id)
    if got is None:
        return JSONResponse({"error": "Documento no encontrado."}, status_code=404)
    data, mime, filename = got
    # Sanea el nombre para la cabecera: sin comillas ni saltos que la rompan.
    safe_name = re.sub(r'[\r\n"\\]', "_", filename or "documento")[:120]
    return Response(content=data, media_type=mime,
                    headers={"Content-Disposition": f'inline; filename="{safe_name}"'})


@router.delete("/api/{business_id}/documents/{doc_id}")
def api_delete_document(business_id: int, doc_id: int):
    from ...documents import service as docservice
    if not docservice.delete(business_id, doc_id):
        return JSONResponse({"error": "Documento no encontrado."}, status_code=404)
    return {"ok": True}


@router.post("/api/{business_id}/documents/{doc_id}/to-expense")
async def api_document_to_expense(business_id: int, doc_id: int, request: Request):
    """Convierte un ticket/factura escaneada en un gasto (usa el importe del OCR)."""
    from ...documents import service as docservice
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    amount = body.get("amount")
    try:
        amount = float(amount) if amount not in (None, "") else None
    except (TypeError, ValueError):
        amount = None
    try:
        gasto = docservice.convert_ticket_to_expense(
            business_id,
            doc_id,
            concept=body.get("concept"),
            amount=amount,
            vat_rate=body.get("vat_rate"),
            spent_on=body.get("spent_on") or body.get("date"),
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if gasto is None:
        return JSONResponse(
            {"error": "No hay importe para registrar. Indica uno o sube una foto legible."},
            status_code=400)
    return gasto


@router.post("/api/{business_id}/documents/{doc_id}/draft")
def api_document_draft(business_id: int, doc_id: int):
    """Borrador de factura extraído por IA. Nunca crea registros: solo propone."""
    from ...documents import service as docservice
    draft = docservice.invoice_draft(business_id, doc_id)
    if draft is None:
        return JSONResponse(
            {"error": "No se pudo leer el documento automáticamente. "
                      "Queda pendiente de revisión manual.",
             "pending": True},
            status_code=200)
    return draft


@router.post("/api/{business_id}/documents/{doc_id}/review")
async def api_document_review(business_id: int, doc_id: int, request: Request):
    """Corrección humana: tipo, estado y nota del documento. Queda trazado."""
    from ...documents import repo as docrepo
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    try:
        doc = docrepo.set_review(
            doc_id, business_id,
            kind=body.get("kind") or None,
            doc_status=body.get("doc_status") or None,
            review_note=body.get("review_note") or None)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if doc is None:
        return JSONResponse({"error": "Documento no encontrado."}, status_code=404)
    return doc


# ------------------------------------------- Proveedores y facturas recibidas
@router.get("/api/{business_id}/suppliers")
def api_suppliers(business_id: int):
    return db.list_suppliers(business_id)


@router.post("/api/{business_id}/suppliers")
async def api_add_supplier(business_id: int, request: Request):
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    try:
        return db.add_supplier(
            body.get("name"), nif=body.get("nif"), email=body.get("email"),
            phone=body.get("phone"), note=body.get("note"),
            business_id=business_id)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.get("/api/{business_id}/received-invoices")
def api_received_invoices(business_id: int, status: str = ""):
    try:
        return db.list_received_invoices(business_id, status=status or None)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/api/{business_id}/received-invoices")
async def api_add_received_invoice(business_id: int, request: Request):
    """Alta de factura recibida: manual o confirmando el borrador de un documento."""
    from ...documents import service as docservice
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    fields = {key: body.get(key) for key in (
        "number", "concept", "issued_on", "due_on", "base", "vat_rate",
        "vat_amount", "irpf_amount", "category", "note") if body.get(key)
        not in (None, "")}
    try:
        doc_id = body.get("document_id")
        if doc_id not in (None, ""):
            return docservice.confirm_received_invoice(
                business_id, int(doc_id), total=body.get("total"),
                supplier_name=body.get("supplier_name"),
                supplier_nif=body.get("supplier_nif"),
                supplier_id=body.get("supplier_id") or None, **fields)
        supplier_id = body.get("supplier_id") or None
        if not supplier_id and body.get("supplier_name"):
            known = db.find_supplier(business_id, nif=body.get("supplier_nif"),
                                     name=body.get("supplier_name"))
            supplier_id = known["id"] if known else db.add_supplier(
                body.get("supplier_name"), nif=body.get("supplier_nif"),
                business_id=business_id)["id"]
        return db.add_received_invoice(
            body.get("total"), supplier_id=supplier_id,
            business_id=business_id, **fields)
    except (ValueError, TypeError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except docservice.UploadError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/api/{business_id}/received-invoices/{received_id}/status")
async def api_received_invoice_status(business_id: int, received_id: int,
                                      request: Request):
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    try:
        return db.set_received_invoice_status(
            received_id, body.get("status"), business_id=business_id)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.delete("/api/{business_id}/received-invoices/{received_id}")
def api_delete_received_invoice(business_id: int, received_id: int):
    db.delete_received_invoice(received_id, business_id)
    return {"ok": True}


# ------------------------------------------------------ Productos/servicios
