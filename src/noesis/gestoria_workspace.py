"""Lectura fiscal y documental explicable para la cartera de gestoría.

No presenta modelos ni decide deducibilidad. Ordena datos existentes, declara qué
no conoce y conserva siempre la separación por ``business_id``.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from io import BytesIO
import math

from . import db
from .documents import repo as docrepo


DOCUMENT_FILTERS = {"todos", "ingresos", "gastos", "tickets", "pendientes", "otros"}


def _money(value) -> float:
    return round(float(value or 0), 2)


def _period(year: int, quarter: int | None) -> dict:
    year = max(2000, min(int(year), date.today().year + 1))
    if quarter is None:
        return {
            "year": year, "quarter": None, "label": str(year),
            "start": f"{year}-01-01", "end": f"{year}-12-31",
        }
    quarter = int(quarter)
    if quarter not in {1, 2, 3, 4}:
        raise ValueError("El trimestre debe estar entre 1 y 4.")
    start, end = db.gestoria_period_range(f"{year}-T{quarter}")
    return {
        "year": year, "quarter": quarter, "label": f"T{quarter} {year}",
        "start": start, "end": end,
    }


def _in_period(value, period: dict) -> bool:
    day = str(value or "")[:10]
    return bool(day) and period["start"] <= day <= period["end"]


def _expense_tax(item: dict) -> tuple[float, float, bool]:
    total = _money(item.get("amount"))
    rate = item.get("vat_rate")
    if rate in (None, ""):
        return total, 0.0, False
    base = total / (1 + float(rate) / 100) if float(rate) else total
    return _money(base), _money(total - base), True


def _received_tax(item: dict) -> tuple[float, float, bool]:
    if item.get("base") is None or item.get("vat_amount") is None:
        return _money(item.get("base") or item.get("total")), 0.0, False
    return _money(item["base"]), _money(item["vat_amount"]), True


def _tax_groups(invoices: list[dict], expenses: list[dict],
                received: list[dict]) -> list[dict]:
    groups: dict[float, dict] = defaultdict(
        lambda: {"rate": 0.0, "output_base": 0.0, "output_vat": 0.0,
                 "input_base": 0.0, "input_vat": 0.0}
    )
    for item in invoices:
        rate = float(item.get("vat_rate") or 0)
        group = groups[rate]
        group["rate"] = rate
        group["output_base"] += float(item.get("base") or 0)
        group["output_vat"] += float(item.get("vat_amount") or 0)
    for item in expenses:
        rate = float(item.get("vat_rate") or 0)
        base, vat, known = _expense_tax(item)
        if known:
            group = groups[rate]
            group["rate"] = rate
            group["input_base"] += base
            group["input_vat"] += vat
    for item in received:
        rate = float(item.get("vat_rate") or 0)
        base, vat, known = _received_tax(item)
        if known:
            group = groups[rate]
            group["rate"] = rate
            group["input_base"] += base
            group["input_vat"] += vat
    return [
        {key: _money(value) for key, value in group.items()}
        for _rate, group in sorted(groups.items())
    ]


def _document_group(document: dict) -> str:
    kind = document.get("kind") or "documento"
    if kind == "ticket":
        return "tickets"
    if kind == "factura_emitida" or document.get("invoice_id") is not None:
        return "ingresos"
    if (kind == "factura_recibida" or document.get("expense_id") is not None
            or document.get("received_invoice_id") is not None):
        return "gastos"
    return "otros"


def _period_documents(business_id: int, period: dict, *, view: str) -> list[dict]:
    view = view if view in DOCUMENT_FILTERS else "todos"
    invoices = {int(item["id"]): item for item in db.list_invoices(business_id)}
    expenses = {int(item["id"]): item for item in db.list_expenses(business_id)}
    received = {
        int(item["id"]): item for item in db.list_received_invoices(business_id)
    }
    out = []
    for original in docrepo.list_for_business(business_id):
        item = dict(original)
        effective = item.get("created_at")
        if item.get("invoice_id") in invoices:
            linked = invoices[int(item["invoice_id"])]
            effective = linked.get("issued_at") or linked.get("created_at")
        elif item.get("expense_id") in expenses:
            linked = expenses[int(item["expense_id"])]
            effective = linked.get("spent_on") or linked.get("created_at")
        elif item.get("received_invoice_id") in received:
            linked = received[int(item["received_invoice_id"])]
            effective = linked.get("issued_on") or linked.get("created_at")
        if not _in_period(effective, period):
            continue
        item["effective_on"] = str(effective or "")[:10]
        item["group"] = _document_group(item)
        item["archive_key"] = f"document:{item['id']}"
        item["source_type"] = "uploaded_document"
        item["file_url"] = (
            f"/api/{business_id}/documents/{item['id']}/file"
        )
        item["preview_url"] = (
            f"/api/{business_id}/documents/{item['id']}/preview"
        )
        item["previewable"] = (
            str(item.get("mime") or "").startswith("image/")
            or item.get("mime") == "application/pdf"
        )
        if view == "pendientes" and item.get("doc_status") != "pendiente_revisar":
            continue
        if view not in {"todos", "pendientes"} and item["group"] != view:
            continue
        out.append(item)

    # Las facturas creadas por Bynoesis ya tienen un PDF reproducible desde su
    # registro contable. Se proyectan en el archivo sin duplicar ni el fichero ni
    # los metadatos. Si existe un original subido y vinculado, ese documento es la
    # representación visible y se evita una segunda fila.
    linked_invoice_ids = {
        int(item["invoice_id"])
        for item in out
        if item.get("invoice_id") is not None
    }
    for invoice_id, invoice in invoices.items():
        if invoice_id in linked_invoice_ids:
            continue
        effective = invoice.get("issued_at") or invoice.get("created_at")
        if not _in_period(effective, period):
            continue
        invoice_type = str(invoice.get("invoice_type") or "F1").upper()
        document_name = (
            "Ticket" if invoice_type == "F2" else
            "Rectificativa" if invoice_type.startswith("R") else
            "Factura"
        )
        visible_number = invoice.get("number") or f"borrador-{invoice_id}"
        item = {
            "id": None,
            "archive_key": f"invoice:{invoice_id}",
            "source_type": "generated_invoice",
            "invoice_id": invoice_id,
            "expense_id": None,
            "received_invoice_id": None,
            "client_id": invoice.get("client_id"),
            "client_name": invoice.get("client_name"),
            "project_name": None,
            "kind": "factura_emitida",
            "group": "ingresos",
            "filename": f"{document_name} {visible_number}.pdf",
            "mime": "application/pdf",
            "size": 0,
            "note": invoice.get("concept"),
            "ocr_text": None,
            "ocr_amount": invoice.get("total"),
            "confidence": None,
            "doc_status": (
                "pendiente_revisar"
                if invoice.get("status") == "borrador" else "validado"
            ),
            "record_status": invoice.get("status"),
            "effective_on": str(effective or "")[:10],
            "created_at": invoice.get("created_at"),
            "previewable": False,
            "file_url": f"/api/{business_id}/invoices/{invoice_id}/pdf",
            "preview_url": None,
            "read_only": True,
        }
        if view == "pendientes" and item["doc_status"] != "pendiente_revisar":
            continue
        if view not in {"todos", "pendientes"} and item["group"] != view:
            continue
        out.append(item)
    return sorted(
        out,
        key=lambda item: (
            str(item.get("effective_on") or ""),
            str(item.get("archive_key") or ""),
        ),
        reverse=True,
    )


def _filter_documents(documents: list[dict], view: str) -> list[dict]:
    view = view if view in DOCUMENT_FILTERS else "todos"
    if view == "todos":
        return list(documents)
    if view == "pendientes":
        return [item for item in documents
                if item.get("doc_status") == "pendiente_revisar"]
    return [item for item in documents if item.get("group") == view]


def document_archive(
    business_id: int,
    *,
    year: int,
    quarter: int | None,
    document_view: str = "todos",
) -> dict:
    """Archivo común para titular y gestoría, con una única regla de período."""
    period = _period(year, quarter)
    all_documents = _period_documents(business_id, period, view="todos")
    return {
        "period": period,
        "documents": _filter_documents(all_documents, document_view),
        "document_view": (
            document_view if document_view in DOCUMENT_FILTERS else "todos"
        ),
        "document_counts": {
            key: len(_filter_documents(all_documents, key))
            for key in DOCUMENT_FILTERS
        },
    }


def _annual_347(invoices: list[dict], received: list[dict]) -> list[dict]:
    parties: dict[tuple[str, str], float] = defaultdict(float)
    for item in invoices:
        nif = (item.get("recipient_nif") or "").strip()
        name = item.get("recipient_name") or item.get("client_name") or "Cliente sin nombre"
        if nif:
            parties[(name, nif)] += float(item.get("total") or 0)
    for item in received:
        nif = (item.get("supplier_nif") or "").strip()
        name = item.get("supplier_name") or "Proveedor sin nombre"
        if nif:
            parties[(name, nif)] += float(item.get("total") or 0)
    return [
        {"name": name, "nif": nif, "total": _money(total)}
        for (name, nif), total in sorted(
            parties.items(), key=lambda entry: entry[1], reverse=True
        ) if total > 3005.06
    ]


def fiscal_period(business_id: int, year: int, quarter: int | None) -> dict:
    period = _period(year, quarter)
    invoices = [
        item for item in db.list_invoices(business_id)
        if item.get("status") in {"enviada", "parcial", "cobrada"}
        and _in_period(item.get("issued_at") or item.get("created_at"), period)
    ]
    expenses = [
        item for item in db.list_expenses(business_id)
        if _in_period(item.get("spent_on") or item.get("created_at"), period)
    ]
    received = [
        item for item in db.list_received_invoices(business_id)
        if _in_period(item.get("issued_on") or item.get("created_at"), period)
    ]
    output_base = _money(sum(float(item.get("base") or 0) for item in invoices))
    output_vat = _money(sum(float(item.get("vat_amount") or 0) for item in invoices))
    input_parts = [_expense_tax(item) for item in expenses]
    received_parts = [_received_tax(item) for item in received]
    input_base = _money(sum(item[0] for item in input_parts + received_parts))
    input_vat = _money(sum(item[1] for item in input_parts + received_parts))
    incomplete_tax = sum(not item[2] for item in input_parts + received_parts)

    all_documents = docrepo.list_for_business(business_id)
    expense_docs = {int(item["expense_id"]) for item in all_documents
                    if item.get("expense_id") is not None}
    received_docs = {int(item["received_invoice_id"]) for item in all_documents
                     if item.get("received_invoice_id") is not None}
    missing_receipts = sum(int(item["id"]) not in expense_docs for item in expenses)
    missing_originals = sum(int(item["id"]) not in received_docs for item in received)
    expected = len(expenses) + len(received)
    covered = expected - missing_receipts - missing_originals
    readiness = 100 if not expected else round(max(0, covered) / expected * 100)
    return {
        **period,
        "invoices": invoices, "expenses": expenses, "received": received,
        "output_base": output_base, "output_vat": output_vat,
        "input_base": input_base, "input_vat": input_vat,
        "vat_result": _money(output_vat - input_vat),
        "income_tax_withheld": _money(sum(
            float(item.get("irpf_amount") or 0) for item in invoices
        )),
        "supplier_withholdings": _money(sum(
            float(item.get("irpf_amount") or 0) for item in received
        )),
        "tax_groups": _tax_groups(invoices, expenses, received),
        "missing_receipts": missing_receipts,
        "missing_received_originals": missing_originals,
        "incomplete_tax_records": incomplete_tax,
        "readiness_pct": readiness,
        "records": len(invoices) + len(expenses) + len(received),
    }


def workspace(business_id: int, *, year: int, quarter: int | None,
              document_view: str = "todos") -> dict:
    current = fiscal_period(business_id, year, quarter)
    annual = fiscal_period(business_id, year, None)
    quarters = [fiscal_period(business_id, year, value) for value in range(1, 5)]
    archive = document_archive(
        business_id, year=year, quarter=quarter, document_view="todos"
    )
    all_period_documents = archive["documents"]
    documents = _filter_documents(all_period_documents, document_view)
    pending = [item for item in all_period_documents
               if item.get("doc_status") == "pendiente_revisar"]
    unlinked = [item for item in all_period_documents if (
        item.get("kind") in {"ticket", "factura_recibida", "factura_emitida"}
        and item.get("invoice_id") is None and item.get("expense_id") is None
        and item.get("received_invoice_id") is None
    )]
    profile = db.get_gestoria_fiscal_profile(business_id)
    obligations = set(profile["obligations"])
    model_130 = db.tax_quarter(year, quarter or 4, business_id)
    detected_115 = _money(sum(
        float(item.get("irpf_amount") or 0) for item in current["received"]
        if "alquiler" in str(item.get("category") or "").lower()
    ))
    is_company = profile["taxpayer_type"] == "sociedad"
    is_modules = profile["income_tax_regime"] == "estimacion_objetiva"
    models = [
        {"code": "303", "name": "IVA", "amount": current["vat_result"],
         "status": "preparado" if not current["incomplete_tax_records"] else "revisar",
         "detail": "IVA cobrado menos IVA pagado conocido",
         "active": "303" in obligations},
        {"code": "390", "name": "Resumen anual de IVA",
         "amount": annual["vat_result"],
         "status": "seguimiento" if "390" in obligations else "configurar",
         "detail": "Acumulado anual; la exoneración debe confirmarla el despacho",
         "active": "390" in obligations},
        {"code": "130", "name": "Pago fraccionado IRPF",
         "amount": model_130["irpf_pago"] if not is_company and not is_modules else None,
         "status": ("no_aplica" if is_company or is_modules else
                    "preparado" if "130" in obligations else "configurar"),
         "detail": "Estimación directa acumulada; faltan ajustes y pagos reales",
         "active": "130" in obligations},
        {"code": "131", "name": "Pago fraccionado por módulos",
         "amount": None,
         "status": "revisar" if "131" in obligations else "no_aplica" if not is_modules else "configurar",
         "detail": "Necesita módulos, índices y minoraciones que Bynoesis no inventa",
         "active": "131" in obligations},
        {"code": "111", "name": "Retenciones de profesionales y equipo",
         "amount": current["supplier_withholdings"],
         "status": "revisar" if current["supplier_withholdings"] else "sin_movimientos",
         "detail": "Retenciones detectadas en facturas recibidas",
         "active": "111" in obligations},
        {"code": "115", "name": "Retenciones de alquiler",
         "amount": detected_115,
         "status": "revisar" if detected_115 else "sin_movimientos",
         "detail": "Solo se detecta si el gasto está marcado como alquiler",
         "active": "115" in obligations},
        {"code": "347", "name": "Operaciones con terceros",
         "amount": None, "status": "revisar" if _annual_347(
             annual["invoices"], annual["received"]
         ) else "sin_candidatos",
         "detail": "Candidatos anuales por encima de 3.005,06 €",
         "active": "347" in obligations},
        {"code": "349", "name": "Operaciones intracomunitarias",
         "amount": None, "status": "configurar" if "349" in obligations else "sin_datos",
         "detail": "Falta identificar país y naturaleza intracomunitaria de la operación",
         "active": "349" in obligations},
        {"code": "200", "name": "Impuesto sobre Sociedades",
         "amount": None, "status": "seguimiento" if "200" in obligations else "no_aplica" if not is_company else "configurar",
         "detail": "Seguimiento anual; ajustes contables y tipo efectivo no se presuponen",
         "active": "200" in obligations},
        {"code": "202", "name": "Pago fraccionado de Sociedades",
         "amount": None, "status": "revisar" if "202" in obligations else "no_aplica" if not is_company else "configurar",
         "detail": "La modalidad y bases previas deben confirmarse con el despacho",
         "active": "202" in obligations},
    ]
    return {
        "period": current, "annual": annual, "quarters": quarters,
        "documents": documents,
        "document_view": (
            document_view if document_view in DOCUMENT_FILTERS else "todos"
        ),
        "document_counts": archive["document_counts"],
        "pending_documents": pending, "unlinked_documents": unlinked,
        "profile": profile, "models": models,
        "model_347_candidates": _annual_347(
            annual["invoices"], annual["received"]
        ),
    }


def portfolio_snapshot(business_id: int, *, year: int, quarter: int) -> dict:
    period = fiscal_period(business_id, year, quarter)
    documents = _period_documents(business_id, period, view="todos")
    pending = [item for item in documents
               if item.get("doc_status") == "pendiente_revisar"]
    unlinked = [item for item in documents if (
        item.get("kind") in {"ticket", "factura_recibida", "factura_emitida"}
        and item.get("invoice_id") is None and item.get("expense_id") is None
        and item.get("received_invoice_id") is None
    )]
    attention = (
        len({str(item["archive_key"]) for item in pending + unlinked})
        + period["missing_receipts"] + period["missing_received_originals"]
    )
    profile = db.get_gestoria_fiscal_profile(business_id)
    return {
        "period_label": period["label"],
        "readiness_pct": period["readiness_pct"],
        "vat_result": period["vat_result"],
        "attention": attention,
        "documents": len(documents),
        "profile_ready": profile["taxpayer_type"] != "sin_configurar",
    }


def preview_image(data: bytes, mime: str) -> tuple[bytes, str] | None:
    """Devuelve una previsualización acotada sin habilitar iframes ni plugins."""
    if mime.startswith("image/"):
        return data, mime
    if mime != "application/pdf":
        return None
    try:
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(BytesIO(data))
        if not len(document):
            document.close()
            return None
        page = document[0]
        width, height = (float(value) for value in page.get_size())
        if (not math.isfinite(width) or not math.isfinite(height)
                or width <= 0 or height <= 0):
            page.close()
            document.close()
            return None
        scale = min(1.45, math.sqrt(2_500_000 / (width * height)))
        if scale < 0.02:
            page.close()
            document.close()
            return None
        bitmap = page.render(scale=scale, draw_annots=False)
        image = bitmap.to_pil()
        try:
            image.thumbnail((1500, 1800))
            output = BytesIO()
            image.convert("RGB").save(output, format="JPEG", quality=86, optimize=True)
            return output.getvalue(), "image/jpeg"
        finally:
            image.close()
            bitmap.close()
            page.close()
            document.close()
    except Exception:  # El original sigue disponible para descarga segura.
        return None
