"""Generación del PDF de una factura, con los datos fiscales del negocio.

Usa fpdf2 (Python puro, sin dependencias del sistema). Evita el símbolo € porque
las fuentes base de PDF no lo incluyen; se usa "EUR".
"""

from __future__ import annotations

from datetime import date

from fpdf import FPDF

from .. import db

FOREST = (20, 70, 59)
TEAL = (46, 139, 116)
INK = (22, 39, 31)
MUTED = (95, 107, 99)
LINE = (220, 216, 200)


def _eur(n) -> str:
    s = f"{(n or 0):,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") + " EUR"


def build_invoice_pdf(invoice_id: int, business_id: int) -> bytes | None:
    inv = db.get_invoice(invoice_id)
    if not inv or inv["business_id"] != business_id:
        return None
    biz = db.get_business(business_id) or {}
    client = db.get_client(inv["client_id"]) or {}

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, 18)
    pdf.add_page()
    pdf.set_margins(18, 18, 18)

    # --- Cabecera: negocio + título FACTURA ---
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*FOREST)
    pdf.cell(110, 10, biz.get("name", "Mi Negocio"))
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*INK)
    pdf.cell(0, 10, "FACTURA", align="R")
    pdf.ln(11)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED)
    datos = []
    if biz.get("nif"):
        datos.append(f"NIF: {biz['nif']}")
    if biz.get("address"):
        datos.append(biz["address"])
    pdf.cell(110, 5, "  |  ".join(datos))
    numero = inv.get("number") or "(borrador)"
    pdf.cell(0, 5, f"Nº {numero}", align="R")
    pdf.ln(5)
    fecha = (inv.get("issued_at") or inv.get("created_at") or "")[:10]
    pdf.cell(110, 5, "")
    pdf.cell(0, 5, f"Fecha: {fecha or date.today().isoformat()}", align="R")
    pdf.ln(12)

    # --- Cliente ---
    pdf.set_draw_color(*LINE)
    pdf.set_fill_color(247, 245, 238)
    pdf.set_text_color(*MUTED)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 6, "FACTURAR A", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*INK)
    pdf.cell(0, 7, client.get("name", inv.get("client_name") or "Cliente"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    # --- Tabla de conceptos ---
    pdf.set_fill_color(*FOREST)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(96, 9, "  Concepto", fill=True)
    pdf.cell(26, 9, "Base", align="R", fill=True)
    pdf.cell(26, 9, "IVA", align="R", fill=True)
    pdf.cell(26, 9, "Total ", align="R", fill=True)
    pdf.ln(9)

    pdf.set_text_color(*INK)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(96, 9, "  " + inv["concept"])
    pdf.cell(26, 9, _eur(inv["base"]).replace(" EUR", ""), align="R")
    pdf.cell(26, 9, f"{inv['vat_rate']:.0f}%", align="R")
    pdf.cell(26, 9, _eur(inv["total"]).replace(" EUR", "") + " ", align="R")
    pdf.ln(9)
    pdf.set_draw_color(*LINE)
    pdf.line(18, pdf.get_y(), 192, pdf.get_y())
    pdf.ln(6)

    # --- Totales ---
    def total_row(label, value, bold=False, color=INK):
        pdf.cell(122, 7, "")
        pdf.set_font("Helvetica", "B" if bold else "", 11 if bold else 10)
        pdf.set_text_color(*color)
        pdf.cell(30, 7, label, align="R")
        pdf.cell(0, 7, _eur(value), align="R", new_x="LMARGIN", new_y="NEXT")

    total_row("Base imponible", inv["base"])
    total_row(f"IVA ({inv['vat_rate']:.0f}%)", inv["vat_amount"])
    if inv.get("irpf_amount"):
        total_row(f"IRPF (-{inv['irpf_rate']:.0f}%)", -inv["irpf_amount"], color=MUTED)
    pdf.ln(1)
    total_row("TOTAL", inv["total"], bold=True, color=FOREST)

    # --- Pie ---
    pdf.ln(14)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(0, 4,
                   "Factura generada con Noesis. Documento de prueba: la emision "
                   "legal definitiva (Verifactu) se realiza al integrar el proveedor "
                   "homologado.")

    out = pdf.output()
    return bytes(out)
