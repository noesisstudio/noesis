"""Rutas de facturacion, gastos, cobros e impuestos."""

from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, File, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from ... import config, db, tools as invoice_tools
from ...tools import run_tool
from ..deps import _read_json

router = APIRouter()

@router.get("/api/{business_id}/invoices")
def api_invoices(business_id: int):
    return db.list_invoices(business_id)


@router.get("/api/{business_id}/invoices/{invoice_id}")
def api_invoice(business_id: int, invoice_id: int):
    invoice = db.get_invoice(invoice_id, business_id)
    if invoice is None:
        return JSONResponse({"error": "Factura no encontrada."}, status_code=404)
    return invoice


@router.get("/api/{business_id}/invoices/{invoice_id}/history")
def api_invoice_history(business_id: int, invoice_id: int):
    if not db.get_invoice(invoice_id, business_id):
        return JSONResponse({"error": "Factura no encontrada."}, status_code=404)
    return db.list_invoice_events(business_id, invoice_id=invoice_id)


@router.post("/api/{business_id}/invoices")
async def api_create_invoice(business_id: int, request: Request):
    """Crea una factura en borrador desde la web (además de por el asistente).

    Acepta un cliente existente (client_id) o un nombre nuevo (client_name), que se
    da de alta al vuelo para que la primera factura no exija crear antes la ficha.
    """
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    client_id = body.get("client_id")
    if not client_id:
        new_name = (body.get("client_name") or "").strip()
        if not new_name:
            return JSONResponse(
                {"error": "Indica un cliente para la factura."}, status_code=400
            )
        existing = db.find_client(new_name, business_id)
        client_id = existing["id"] if existing else db.add_client(
            new_name, business_id=business_id
        )["id"]
    try:
        client_id = int(client_id)
        invoice = db.add_invoice(
            client_id,
            (body.get("concept") or "").strip(),
            body.get("base"),
            vat_rate=body.get("vat_rate", config.DEFAULT_VAT_RATE),
            irpf_rate=body.get("irpf_rate", 0),
            business_id=business_id,
            lines=body.get("lines"),
            invoice_type=body.get("invoice_type", "F1"),
            series_id=body.get("series_id"),
            operation_date=body.get("operation_date"),
            notes=body.get("notes"),
            payment_method=body.get("payment_method"),
            legal_mention=body.get("legal_mention"),
        )
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return invoice


@router.patch("/api/{business_id}/invoices/{invoice_id}")
async def api_update_invoice_draft(
    business_id: int, invoice_id: int, request: Request
):
    try:
        body = await _read_json(request)
        return db.update_invoice_draft(
            invoice_id,
            business_id,
            client_id=int(body.get("client_id")),
            lines=body.get("lines"),
            irpf_rate=body.get("irpf_rate", 0),
            invoice_type=body.get("invoice_type", "F1"),
            series_id=body.get("series_id"),
            operation_date=body.get("operation_date"),
            notes=body.get("notes"),
            payment_method=body.get("payment_method"),
            legal_mention=body.get("legal_mention"),
        )
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/api/{business_id}/invoices/{invoice_id}/rectify")
async def api_rectify_invoice(
    business_id: int, invoice_id: int, request: Request
):
    try:
        body = await _read_json(request)
        invoice = db.create_rectifying_invoice(
            invoice_id,
            business_id,
            concept=body.get("concept"),
            base=body.get("base"),
            vat_rate=body.get("vat_rate", 21),
            irpf_rate=body.get("irpf_rate", 0),
            invoice_type=body.get("invoice_type", "R1"),
            rectification_type=body.get("rectification_type", "I"),
            reason=body.get("reason"),
            lines=body.get("lines"),
            series_id=body.get("series_id"),
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return invoice


@router.patch("/api/{business_id}/invoices/{invoice_id}/rectification")
async def api_update_rectifying_invoice(
    business_id: int, invoice_id: int, request: Request
):
    try:
        body = await _read_json(request)
        return db.update_rectifying_invoice_draft(
            invoice_id,
            business_id,
            concept=body.get("concept"),
            base=body.get("base"),
            vat_rate=body.get("vat_rate", config.DEFAULT_VAT_RATE),
            irpf_rate=body.get("irpf_rate", 0),
            invoice_type=body.get("invoice_type", "R1"),
            rectification_type=body.get("rectification_type", "I"),
            reason=body.get("reason"),
            lines=body.get("lines"),
            series_id=body.get("series_id"),
        )
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/api/{business_id}/invoices/{invoice_id}/cancel-verifactu")
async def api_cancel_verifactu_record(
    business_id: int, invoice_id: int, request: Request
):
    invoice = db.get_invoice(invoice_id, business_id)
    if not invoice or not invoice.get("number"):
        return JSONResponse({"error": "Factura emitida no encontrada."}, status_code=404)
    try:
        body = await _read_json(request)
        expected = f"ANULAR {invoice['number']}"
        if (body.get("confirmation") or "").strip() != expected:
            raise ValueError(f"Escribe exactamente {expected} para confirmar.")
        record = db.create_invoice_cancellation_record(
            invoice_id, business_id, reason=body.get("reason")
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)
    return record


@router.get("/api/{business_id}/invoice-series")
def api_invoice_series(business_id: int):
    return db.list_invoice_series(business_id)


@router.post("/api/{business_id}/invoice-series", status_code=201)
async def api_add_invoice_series(business_id: int, request: Request):
    try:
        body = await _read_json(request)
        return db.add_invoice_series(
            business_id,
            code=body.get("code"),
            name=body.get("name"),
            document_type=body.get("document_type"),
            prefix_template=body.get("prefix_template"),
            padding=body.get("padding", 4),
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.get("/api/{business_id}/recurring-invoices")
def api_recurring_invoices(business_id: int):
    return db.list_recurring_invoices(business_id)


@router.post("/api/{business_id}/recurring-invoices", status_code=201)
async def api_add_recurring_invoice(business_id: int, request: Request):
    try:
        body = await _read_json(request)
        return db.add_recurring_invoice(
            business_id,
            int(body.get("client_id")),
            name=body.get("name"),
            cadence=body.get("cadence"),
            interval_count=body.get("interval_count", 1),
            next_run_on=body.get("next_run_on"),
            ends_on=body.get("ends_on"),
            auto_issue=bool(body.get("auto_issue", False)),
            lines=body.get("lines"),
            irpf_rate=body.get("irpf_rate", 0),
            invoice_type=body.get("invoice_type", "F1"),
            series_id=body.get("series_id"),
            notes=body.get("notes"),
            payment_method=body.get("payment_method"),
        )
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/api/{business_id}/recurring-invoices/{recurring_id}/status")
async def api_recurring_invoice_status(
    business_id: int, recurring_id: int, request: Request
):
    try:
        body = await _read_json(request)
        result = db.set_recurring_invoice_status(
            recurring_id, business_id, body.get("status")
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if result is None:
        return JSONResponse({"error": "Programación no encontrada."}, status_code=404)
    return result


@router.get("/api/{business_id}/verifactu/export.xml")
def api_verifactu_export(
    business_id: int,
    from_: str = Query("", alias="from"),
    to: str = "",
):
    try:
        start = date.fromisoformat(from_).isoformat() if from_ else None
        end = date.fromisoformat(to).isoformat() if to else None
        payload = db.export_verifactu_xml(
            business_id, from_day=start, to_day=end
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return Response(
        content=payload,
        media_type="application/xml; charset=utf-8",
        headers={
            "Content-Disposition": (
                'attachment; filename="registros_verifactu.xml"'
            )
        },
    )


@router.get("/api/{business_id}/verifactu/integrity")
def api_verifactu_integrity(business_id: int):
    return db.verify_invoice_record_chain(business_id)


@router.get("/api/{business_id}/expenses")
def api_expenses(business_id: int):
    return db.list_expenses(business_id)


@router.post("/api/{business_id}/expenses/from-photo", status_code=201)
async def api_expense_from_photo(
    business_id: int, file: UploadFile = File(...)
):
    """Guarda la foto y devuelve sugerencias; nunca crea el gasto."""
    from ...adapters import extraction
    from ...documents import service as docservice, storage

    filename = file.filename or "ticket"
    if storage.ext_of(filename) not in storage.IMAGE_EXTS:
        return JSONResponse(
            {"error": "Sube una foto JPG, PNG, WEBP o HEIC."},
            status_code=400,
        )
    max_bytes = config.MAX_UPLOAD_MB * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        return JSONResponse(
            {"error": f"El archivo supera el límite de {config.MAX_UPLOAD_MB} MB."},
            status_code=413,
        )
    try:
        document = docservice.upload(
            business_id,
            filename,
            data,
            kind="ticket",
            run_ocr=False,
        )
    except docservice.UploadError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    extracted = await run_in_threadpool(
        extraction.extract_expense,
        data,
        storage.mime_for(filename),
    )
    fields = extracted or {
        "concept": None,
        "amount": None,
        "vat_rate": None,
        "date": None,
        "supplier": None,
    }
    return {
        "document": document,
        "extracted": extracted is not None,
        "draft": {
            **fields,
            "category": "Ticket",
            "document_id": document["id"],
        },
    }


@router.post("/api/{business_id}/expenses")
async def api_add_expense(business_id: int, request: Request):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    concept = (body.get("concept") or "").strip()
    try:
        amount = float(body.get("amount"))
    except (TypeError, ValueError):
        amount = 0
    if not concept or amount <= 0:
        return JSONResponse({"error": "Concepto e importe (>0) son obligatorios."},
                            status_code=400)
    try:
        return db.add_expense(
            concept,
            amount,
            vat_rate=body.get("vat_rate"),
            category=body.get("category"),
            spent_on=body.get("spent_on") or body.get("date"),
            document_id=body.get("document_id"),
            project_id=body.get("project_id"),
            business_id=business_id,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.delete("/api/{business_id}/expenses/{expense_id}")
def api_delete_expense(business_id: int, expense_id: int):
    db.delete_expense(expense_id, business_id)
    return {"ok": True}




@router.delete("/api/{business_id}/invoices/{invoice_id}")
def api_delete_invoice(business_id: int, invoice_id: int):
    if not db.delete_invoice(invoice_id, business_id):
        return JSONResponse(
            {"error": "Solo se pueden borrar facturas en borrador."},
            status_code=409,
        )
    return {"ok": True}




@router.get("/api/{business_id}/invoices/{invoice_id}/pdf")
def api_invoice_pdf(business_id: int, invoice_id: int):
    from ..invoice_pdf import build_invoice_pdf
    data = build_invoice_pdf(invoice_id, business_id)
    if data is None:
        return JSONResponse({"error": "Factura no encontrada."}, status_code=404)
    inv = db.get_invoice(invoice_id, business_id)
    name = f"factura_{inv.get('number') or invoice_id}.pdf"
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{name}"'})




@router.post("/api/{business_id}/invoices/{invoice_id}/pay")
def api_mark_paid(business_id: int, invoice_id: int):
    inv = db.mark_invoice_paid(invoice_id, business_id)
    if inv is None:
        return JSONResponse(
            {"error": "Solo se puede cobrar una factura emitida."}, status_code=409
        )
    return inv


@router.get("/api/{business_id}/invoices/{invoice_id}/payments")
def api_invoice_payments(business_id: int, invoice_id: int):
    if not db.get_invoice(invoice_id, business_id):
        return JSONResponse({"error": "Factura no encontrada."}, status_code=404)
    return db.list_invoice_payments(invoice_id, business_id)


@router.post(
    "/api/{business_id}/invoices/{invoice_id}/payments",
    status_code=201,
)
async def api_add_invoice_payment(
    business_id: int, invoice_id: int, request: Request
):
    if not db.get_invoice(invoice_id, business_id):
        return JSONResponse({"error": "Factura no encontrada."}, status_code=404)
    try:
        body = await _read_json(request)
        return db.add_invoice_payment(
            invoice_id,
            body.get("amount"),
            business_id=business_id,
            method=body.get("method"),
            paid_at=body.get("paid_at"),
            note=body.get("note"),
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/api/{business_id}/invoices/{invoice_id}/send")
def api_send_invoice(business_id: int, invoice_id: int):
    # Emite una factura borrador desde la web (mismo flujo que el chat, aislado).
    result = json.loads(run_tool("enviar_factura",
                                 {"factura_id": invoice_id}, business_id))
    if not result.get("ok"):
        return JSONResponse({"error": result.get("error", "No se pudo enviar.")},
                            status_code=400)
    return result["factura"]


@router.post("/api/{business_id}/invoices/{invoice_id}/deliver")
async def api_deliver_invoice(
    business_id: int, invoice_id: int, request: Request
):
    """Entrega por el canal habitual y deja el intento en una outbox durable."""
    from ...adapters import email as email_adapter

    invoice = db.get_invoice(invoice_id, business_id)
    if not invoice:
        return JSONResponse({"error": "Factura no encontrada."}, status_code=404)
    if invoice.get("status") == "borrador" or not invoice.get("number"):
        return JSONResponse(
            {"error": "Emite la factura antes de enviarla al cliente."},
            status_code=409,
        )
    client = db.get_client(invoice["client_id"], business_id) or {}
    try:
        body = await _read_json(request)
        explicit_email = (body.get("email") or "").strip()
        channel = (body.get("channel") or "auto").strip().lower()
        if not explicit_email:
            delivered = invoice_tools.prepare_invoice_delivery(
                business_id, invoice_id, channel=channel
            )
            return {
                **delivered,
                "email": delivered["target"]
                if delivered["channel"] == "email" else None,
            }
        target = explicit_email
        business = db.get_business(business_id) or {}
        subject = f"Factura {invoice['number']} — {business.get('name') or 'Noesis'}"
        text_body = (
            f"Hola {client.get('name') or ''},\n\n"
            f"Te enviamos la factura {invoice['number']} por "
            f"{invoice['total']:.2f} EUR. Encontrarás el PDF adjunto.\n\n"
            f"— {business.get('name') or 'Noesis'}"
        )
        queued = email_adapter.queue_email(
            target,
            subject,
            text_body,
            business_id=business_id,
            idempotency_key=(
                body.get("idempotency_key")
                or f"invoice:{business_id}:{invoice_id}:email:{date.today().isoformat()}"
            ),
            entity_type="invoice",
            entity_id=invoice_id,
        )
        db.record_invoice_communication(
            invoice_id,
            business_id,
            "entrega_preparada",
            details=f"correo={target}",
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"queued": bool(queued), "email": target}


# ----------------------------------------------------------- Presupuestos ---
@router.get("/api/{business_id}/quotes")
def api_quotes(business_id: int):
    return db.list_quotes(business_id)


@router.get("/api/{business_id}/quotes/{quote_id}/pdf")
def api_quote_pdf(business_id: int, quote_id: int):
    from ..invoice_pdf import build_quote_pdf
    quote = db.get_quote(quote_id, business_id)
    data = build_quote_pdf(quote_id, business_id) if quote else None
    if data is None:
        return JSONResponse({"error": "Presupuesto no encontrado."}, status_code=404)
    name = f"presupuesto_{quote.get('number') or quote_id}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{name}"'},
    )


@router.post("/api/{business_id}/quotes")
async def api_add_quote(business_id: int, request: Request):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    cliente = (body.get("cliente") or "").strip()
    concepto = (body.get("concepto") or "").strip()
    try:
        base = float(body.get("base"))
    except (TypeError, ValueError):
        base = 0
    if not cliente or not concepto or base <= 0:
        return JSONResponse({"error": "Cliente, concepto e importe (>0) son obligatorios."},
                            status_code=400)
    args = {"cliente": cliente, "concepto": concepto, "base": base}
    if body.get("iva") is not None:
        args["iva"] = body["iva"]
    if body.get("irpf") is not None:
        args["irpf"] = body["irpf"]
    if body.get("validez_dias") is not None:
        args["validez_dias"] = body["validez_dias"]
    if body.get("notas") is not None:
        args["notas"] = body["notas"]
    result = json.loads(run_tool("crear_presupuesto", args, business_id))
    if not result.get("ok"):
        return JSONResponse({"error": result.get("error", "No se pudo crear.")},
                            status_code=400)
    return result["presupuesto"]


@router.post("/api/{business_id}/quotes/{quote_id}/send")
def api_send_quote(business_id: int, quote_id: int):
    try:
        q = db.mark_quote_sent(quote_id, business_id)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)
    if q is None:
        return JSONResponse({"error": "Presupuesto no encontrado."}, status_code=404)
    return q


@router.post("/api/{business_id}/quotes/{quote_id}/accept")
def api_accept_quote(business_id: int, quote_id: int):
    try:
        res = db.accept_quote(quote_id, business_id, decision_source="owner")
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)
    if res is None:
        return JSONResponse({"error": "Presupuesto no encontrado."}, status_code=404)
    return res


@router.post("/api/{business_id}/quotes/{quote_id}/reject")
def api_reject_quote(business_id: int, quote_id: int):
    try:
        q = db.reject_quote(quote_id, business_id, decision_source="owner")
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)
    if q is None:
        return JSONResponse({"error": "Presupuesto no encontrado."}, status_code=404)
    return q


@router.delete("/api/{business_id}/quotes/{quote_id}")
def api_delete_quote(business_id: int, quote_id: int):
    if not db.delete_quote(quote_id, business_id):
        return JSONResponse(
            {"error": "Solo se pueden borrar presupuestos en borrador."},
            status_code=409,
        )
    return {"ok": True}


# -------------------------------------------------------------- Impuestos ---
@router.get("/api/{business_id}/taxes")
def api_taxes(business_id: int, year: int = 0, quarter: int = 0):
    today = date.today()
    year = year or today.year
    quarter = quarter or (today.month - 1) // 3 + 1
    try:
        return {**db.tax_quarter(year, quarter, business_id),
                "current_year": today.year}
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
