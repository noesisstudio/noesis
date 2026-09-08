"""Paquete para la gestoría: todo lo del período, limpio y en un solo ZIP.

El autónomo deja de pasar la caja de zapatos: facturas emitidas (PDF + CSV),
gastos con sus justificantes y un resumen fiscal de una hoja. La gestoría lo
descarga desde su enlace privado /g/{token} (sin contraseña, revocable).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import zipfile

from .. import config, db

log = logging.getLogger("noesis.gestoria")


def previous_label(cadence: str, today=None) -> str:
    """Etiqueta del último período CERRADO según la cadencia."""
    from datetime import date, timedelta

    point = today or date.today()
    previous = point.replace(day=1) - timedelta(days=1)
    if cadence == "trimestral":
        return f"{previous.year}-T{(previous.month - 1) // 3 + 1}"
    return f"{previous:%Y-%m}"


def _csv_bytes(headers: list[str], rows: list[list]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def _summary_pdf(business: dict, label: str, invoices: list[dict],
                 expenses: list[dict]) -> bytes:
    """Resumen fiscal de una hoja (fpdf2, fuentes core: importes en EUR)."""
    from fpdf import FPDF

    revenue_base = round(sum(i["base"] for i in invoices), 2)
    vat_output = round(sum(i["vat_amount"] for i in invoices), 2)
    irpf_withheld = round(sum(i.get("irpf_amount") or 0 for i in invoices), 2)
    total_invoiced = round(sum(i["total"] for i in invoices), 2)
    expense_total = round(sum(e["amount"] for e in expenses), 2)
    vat_input = round(sum(
        e["amount"] - e["amount"] / (1 + (e.get("vat_rate") or 0) / 100)
        for e in expenses
    ), 2)

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=20)
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(20, 70, 59)
    pdf.cell(0, 10, f"Resumen para la gestoria - {label}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 11)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(0, 8, f"{business.get('name') or ''} - NIF "
                   f"{business.get('nif') or 'sin datos'}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    rows = [
        ("Facturas emitidas", str(len(invoices))),
        ("Base imponible facturada", f"{revenue_base:.2f} EUR"),
        ("IVA repercutido", f"{vat_output:.2f} EUR"),
        ("IRPF retenido en factura", f"{irpf_withheld:.2f} EUR"),
        ("Total facturado", f"{total_invoiced:.2f} EUR"),
        ("Gastos del periodo", str(len(expenses))),
        ("Importe de gastos", f"{expense_total:.2f} EUR"),
        ("IVA soportado (estimado)", f"{vat_input:.2f} EUR"),
        ("IVA resultado (repercutido - soportado)",
         f"{round(vat_output - vat_input, 2):.2f} EUR"),
    ]
    for concept, value in rows:
        pdf.set_font("helvetica", "", 10.5)
        pdf.cell(120, 8, concept, border="B")
        pdf.set_font("helvetica", "B", 10.5)
        pdf.cell(60, 8, value, border="B", align="R",
                 new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_font("helvetica", "I", 9)
    pdf.set_text_color(110, 110, 110)
    pdf.multi_cell(0, 5, "Generado por Bynoesis (bynoesis.com). Los PDFs de las "
                         "facturas y los justificantes de gasto acompanan a este "
                         "resumen dentro del mismo paquete.")
    return bytes(pdf.output())


def _safe_filename(value: str) -> str:
    """Evita rutas y nombres ambiguos dentro del paquete compartido."""
    clean = str(value or "documento").replace("/", "-").replace("\\", "-")
    clean = "".join(char for char in clean if char.isalnum() or char in " ._-()")
    return clean.strip(" .")[:140] or "documento"


def build_package(
    business_id: int, label: str, *, record_delivery: bool = True,
) -> tuple[bytes, dict] | None:
    """Crea un paquete ordenado y comprobable; puede omitir el registro en demos."""
    from ..documents import repo as docrepo, service as docservice
    from .invoice_pdf import build_invoice_pdf

    business = db.get_business(business_id)
    if not business:
        return None
    start, end = db.gestoria_period_range(label)
    invoices = db.gestoria_invoices_in(business_id, start, end)
    expenses = db.gestoria_expenses_in(business_id, start, end)
    received = db.gestoria_received_in(business_id, start, end)
    documents = docrepo.list_for_business(business_id)
    by_expense: dict[int, list[dict]] = {}
    by_received: dict[int, list[dict]] = {}
    for document in documents:
        if document.get("expense_id") is not None:
            by_expense.setdefault(int(document["expense_id"]), []).append(document)
        if document.get("received_invoice_id") is not None:
            by_received.setdefault(
                int(document["received_invoice_id"]), []
            ).append(document)

    files: list[str] = []
    missing_expense_receipts: list[int] = []
    missing_received_originals: list[int] = []
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
        def write(path: str, payload: bytes | str) -> None:
            bundle.writestr(path, payload)
            files.append(path)

        write(
            "00-resumen/resumen.pdf",
            _summary_pdf(business, label, invoices, expenses),
        )
        write("01-ingresos/facturas.csv", _csv_bytes(
            ["numero", "fecha", "cliente", "base", "iva", "irpf", "total",
             "estado", "cobrado"],
            [[i.get("number") or i["id"], str(i.get("issued_at") or "")[:10],
              i.get("client_name") or "", i["base"], i["vat_amount"],
              i.get("irpf_amount") or 0, i["total"], i["status"],
              i.get("paid_amount") or 0] for i in invoices],
        ))
        for invoice in invoices:
            pdf = build_invoice_pdf(invoice["id"], business_id)
            if pdf:
                number = _safe_filename(
                    invoice.get("number") or f"id-{invoice['id']}"
                )
                write(f"01-ingresos/facturas/{number}.pdf", pdf)

        write("02-gastos/gastos.csv", _csv_bytes(
            ["fecha", "concepto", "categoria", "iva_pct", "importe",
             "proyecto"],
            [[str(e.get("spent_on") or e.get("created_at") or "")[:10],
              e["concept"], e.get("category") or "", e.get("vat_rate") or "",
              e["amount"], e.get("project_name") or ""] for e in expenses],
        ))
        for expense in expenses:
            attached = False
            for document in by_expense.get(int(expense["id"]), []):
                payload = docservice.file_bytes(business_id, document["id"])
                if not payload:
                    continue
                data, _mime, filename = payload
                write(
                    f"02-gastos/justificantes/{document['id']}-"
                    f"{_safe_filename(filename)}",
                    data,
                )
                attached = True
            if not attached:
                missing_expense_receipts.append(int(expense["id"]))

        write("03-facturas-recibidas/facturas-recibidas.csv", _csv_bytes(
            ["numero", "fecha", "proveedor", "base", "iva_pct", "cuota_iva",
             "irpf", "total", "estado"],
            [[r.get("number") or r["id"],
              str(r.get("issued_on") or r.get("created_at") or "")[:10],
              r.get("supplier_name") or "", r.get("base") or "",
              r.get("vat_rate") or "", r.get("vat_amount") or "",
              r.get("irpf_amount") or "", r["total"], r["status"]]
             for r in received],
        ))
        for invoice in received:
            attached = False
            for document in by_received.get(int(invoice["id"]), []):
                payload = docservice.file_bytes(business_id, document["id"])
                if not payload:
                    continue
                data, _mime, filename = payload
                write(
                    f"03-facturas-recibidas/originales/{document['id']}-"
                    f"{_safe_filename(filename)}",
                    data,
                )
                attached = True
            if not attached:
                missing_received_originals.append(int(invoice["id"]))

        try:
            xml = db.export_verifactu_xml(
                business_id, from_day=start, to_day=end
            )
            if xml:
                write("04-fiscal/verifactu.xml", xml)
        except Exception:  # noqa: BLE001
            log.info("Paquete %s sin XML Veri*Factu (no disponible).", label)

        source = {
            "business_id": business_id,
            "period": label,
            "invoices": [{
                "id": i["id"], "number": i.get("number"),
                "issued_at": str(i.get("issued_at") or ""),
                "base": i.get("base"), "vat": i.get("vat_amount"),
                "irpf": i.get("irpf_amount"), "total": i.get("total"),
                "status": i.get("status"), "paid": i.get("paid_amount"),
            } for i in invoices],
            "expenses": [{
                "id": e["id"], "spent_on": str(e.get("spent_on") or ""),
                "concept": e.get("concept"), "amount": e.get("amount"),
                "vat_rate": e.get("vat_rate"), "project_id": e.get("project_id"),
            } for e in expenses],
            "received_invoices": [{
                "id": r["id"], "number": r.get("number"),
                "issued_on": str(r.get("issued_on") or ""),
                "supplier_id": r.get("supplier_id"), "base": r.get("base"),
                "vat": r.get("vat_amount"), "irpf": r.get("irpf_amount"),
                "total": r.get("total"), "status": r.get("status"),
            } for r in received],
            "documents": sorted(({
                "id": d["id"], "stored_name": d.get("stored_name"),
                "expense_id": d.get("expense_id"),
                "received_invoice_id": d.get("received_invoice_id"),
            } for d in documents
                if d.get("expense_id") in {e["id"] for e in expenses}
                or d.get("received_invoice_id") in {r["id"] for r in received}
            ), key=lambda item: item["id"]),
        }
        source_hash = hashlib.sha256(json.dumps(
            source, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest()
        manifest = {
            "noesis_package": 1,
            "business": business.get("name") or "",
            "nif": business.get("nif") or "",
            "period": {"label": label, "start": start, "end": end},
            "counts": {
                "invoices": len(invoices),
                "expenses": len(expenses),
                "received_invoices": len(received),
            },
            "missing": {
                "expense_receipts": missing_expense_receipts,
                "received_invoice_originals": missing_received_originals,
            },
            "source_hash": source_hash,
            "files": sorted(files + ["MANIFIESTO.json"]),
        }
        bundle.writestr(
            "MANIFIESTO.json",
            json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        )

    data = buffer.getvalue()
    artifact_hash = hashlib.sha256(data).hexdigest()
    delivery = None
    if record_delivery:
        delivery = db.record_gestoria_delivery(
            business_id,
            label,
            source_hash=source_hash,
            artifact_hash=artifact_hash,
            file_size=len(data),
            manifest=manifest,
        )
    meta = {
        "label": label,
        "invoices": len(invoices),
        "expenses": len(expenses),
        "received_invoices": len(received),
        "source_hash": source_hash,
        "artifact_hash": artifact_hash,
        "version": delivery["version"] if delivery else 0,
        "manifest": manifest,
    }
    return data, meta


def notify_gestoria(business: dict, label: str) -> bool:
    """Email a la gestoría con el enlace del portal (nunca adjuntos pesados)."""
    from ..adapters import email as email_adapter

    email = business.get("gestoria_email")
    token = business.get("gestoria_token")
    if not email or not token:
        return False
    link = f"{config.BASE_URL}/g/{token}"
    return email_adapter.queue_email(
        email,
        f"Documentación {label} de {business.get('name') or 'su cliente'}",
        (f"Hola,\n\n{business.get('name') or 'Su cliente'} usa Bynoesis para su "
         f"gestión. El paquete del período {label} (facturas emitidas, gastos "
         f"con justificantes y resumen fiscal) ya está disponible aquí:\n\n"
         f"{link}\n\nEste enlace es privado; no lo compartas.\n\n— Bynoesis"),
        business_id=business["id"],
        idempotency_key=f"gestoria:{business['id']}:{label}",
    )
