"""Paquete para la gestoría: todo lo del período, limpio y en un solo ZIP.

El autónomo deja de pasar la caja de zapatos: facturas emitidas (PDF + CSV),
gastos con sus justificantes y un resumen fiscal de una hoja. La gestoría lo
descarga desde su enlace privado /g/{token} (sin contraseña, revocable).
"""

from __future__ import annotations

import csv
import io
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
    pdf.multi_cell(0, 5, "Generado por Noesis (bynoesis.com). Los PDFs de las "
                         "facturas y los justificantes de gasto acompanan a este "
                         "resumen dentro del mismo paquete.")
    return bytes(pdf.output())


def build_package(business_id: int, label: str) -> tuple[bytes, dict] | None:
    """ZIP del período: facturas (PDF+CSV), gastos (CSV) y justificantes."""
    from ..documents import repo as docrepo, service as docservice
    from .invoice_pdf import build_invoice_pdf

    business = db.get_business(business_id)
    if not business:
        return None
    start, end = db.gestoria_period_range(label)
    invoices = db.gestoria_invoices_in(business_id, start, end)
    expenses = db.gestoria_expenses_in(business_id, start, end)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
        for invoice in invoices:
            pdf = build_invoice_pdf(invoice["id"], business_id)
            if pdf:
                number = (invoice.get("number") or f"id-{invoice['id']}"
                          ).replace("/", "-")
                bundle.writestr(f"facturas/{number}.pdf", pdf)
        bundle.writestr("facturas.csv", _csv_bytes(
            ["numero", "fecha", "cliente", "base", "iva", "irpf", "total",
             "estado", "cobrado"],
            [[i.get("number") or i["id"], str(i.get("issued_at") or "")[:10],
              i.get("client_name") or "", i["base"], i["vat_amount"],
              i.get("irpf_amount") or 0, i["total"], i["status"],
              i.get("paid_amount") or 0] for i in invoices],
        ))
        bundle.writestr("gastos.csv", _csv_bytes(
            ["fecha", "concepto", "categoria", "iva_pct", "importe"],
            [[str(e.get("spent_on") or e.get("created_at") or "")[:10],
              e["concept"], e.get("category") or "",
              e.get("vat_rate") or "", e["amount"]] for e in expenses],
        ))
        received = db.gestoria_received_in(business_id, start, end)
        if received:
            bundle.writestr("facturas-recibidas.csv", _csv_bytes(
                ["numero", "fecha", "proveedor", "base", "iva_pct", "cuota_iva",
                 "irpf", "total", "estado"],
                [[r.get("number") or r["id"],
                  str(r.get("issued_on") or r.get("created_at") or "")[:10],
                  r.get("supplier_name") or "", r.get("base") or "",
                  r.get("vat_rate") or "", r.get("vat_amount") or "",
                  r.get("irpf_amount") or "", r["total"], r["status"]]
                 for r in received],
            ))
        expense_ids = {e["id"] for e in expenses}
        for document in docrepo.list_for_business(business_id):
            if document.get("expense_id") not in expense_ids:
                continue
            payload = docservice.file_bytes(business_id, document["id"])
            if payload:
                data, _mime, filename = payload
                safe = filename.replace("/", "-").replace("\\", "-")
                bundle.writestr(
                    f"justificantes/{document['id']}-{safe}", data
                )
        bundle.writestr(
            "resumen.pdf", _summary_pdf(business, label, invoices, expenses)
        )
        try:
            xml = db.export_verifactu_xml(
                business_id, from_day=start, to_day=end
            )
            if xml:
                bundle.writestr("verifactu.xml", xml)
        except Exception:  # noqa: BLE001 — el XML es un extra, nunca rompe el ZIP
            log.info("Paquete %s sin XML Veri*Factu (no disponible).", label)

    meta = {"label": label, "invoices": len(invoices),
            "expenses": len(expenses)}
    return buffer.getvalue(), meta


def notify_gestoria(business: dict, label: str) -> bool:
    """Email a la gestoría con el enlace del portal (nunca adjuntos pesados)."""
    from ..adapters import email as email_adapter

    email = business.get("gestoria_email")
    token = business.get("gestoria_token")
    if not email or not token or not email_adapter.available():
        return False
    link = f"{config.BASE_URL}/g/{token}"
    return email_adapter.send_email(
        email,
        f"Documentación {label} de {business.get('name') or 'su cliente'}",
        (f"Hola,\n\n{business.get('name') or 'Su cliente'} usa Noesis para su "
         f"gestión. El paquete del período {label} (facturas emitidas, gastos "
         f"con justificantes y resumen fiscal) ya está disponible aquí:\n\n"
         f"{link}\n\nEste enlace es privado; no lo compartas.\n\n— Noesis"),
    )
