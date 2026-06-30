"""Generación del PDF de una factura, con los datos fiscales y la MARCA del negocio.

Usa fpdf2 (Python puro, sin dependencias del sistema). Evita el símbolo € porque
las fuentes base de PDF no lo incluyen; se usa "EUR".

Personalización (sin saber diseñar):
  - 3 plantillas: clasica, minimal, editorial.
  - Color de marca del negocio (acentos).
  - Logo subido por el autónomo o, si no hay, un MONOGRAMA automático con sus
    iniciales sobre el color de marca.
"""

from __future__ import annotations

import base64
from datetime import date
from io import BytesIO

from fpdf import FPDF

from .. import db

INK = (22, 39, 31)
MUTED = (95, 107, 99)
LINE = (220, 216, 200)

# Config por plantilla: tipografía y si la cabecera de la tabla va rellena.
_TEMPLATES = {
    "clasica": {"serif": False, "table_fill": True, "title": "FACTURA"},
    "minimal": {"serif": False, "table_fill": False, "title": "Factura"},
    "editorial": {"serif": True, "table_fill": True, "title": "Factura"},
}


def _eur(n) -> str:
    s = f"{(n or 0):,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") + " EUR"


def _hex_to_rgb(value: str, default=(20, 70, 59)) -> tuple[int, int, int]:
    try:
        h = value.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except (TypeError, ValueError, IndexError):
        return default


def _draw_brandmark(pdf: FPDF, biz: dict, x: float, y: float, size: float,
                    brand_rgb: tuple[int, int, int]) -> None:
    """Dibuja el logo subido o, si no hay, un monograma con las iniciales."""
    if biz.get("logo_data"):
        try:
            data = base64.b64decode(biz["logo_data"])
            pdf.image(BytesIO(data), x=x, y=y, w=size, h=size)
            return
        except Exception:  # noqa: BLE001  (logo corrupto -> caemos al monograma)
            pass
    pdf.set_fill_color(*brand_rgb)
    pdf.rect(x, y, size, size, style="F")
    pdf.set_font("Helvetica", "B", 17)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(x, y)
    pdf.cell(size, size, db.business_initials(biz.get("name")), align="C")


def build_invoice_pdf(invoice_id: int, business_id: int) -> bytes | None:
    inv = db.get_invoice(invoice_id, business_id)
    if not inv:
        return None
    biz = db.get_business(business_id) or {}
    client = db.get_client(inv["client_id"], business_id) or {}
    issuer_name = inv.get("issuer_name") or biz.get("name") or "Mi Negocio"
    issuer_nif = inv.get("issuer_nif") or biz.get("nif")
    issuer_address = inv.get("issuer_address") or biz.get("address")
    recipient_name = (
        inv.get("recipient_name") or client.get("name")
        or inv.get("client_name") or "Cliente"
    )
    recipient_nif = inv.get("recipient_nif") or client.get("nif")
    recipient_address = inv.get("recipient_address") or client.get("address")

    tpl = _TEMPLATES.get(biz.get("invoice_template") or "clasica", _TEMPLATES["clasica"])
    fam = "Times" if tpl["serif"] else "Helvetica"
    brand = _hex_to_rgb(db.business_brand_color(biz))

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, 18)
    pdf.add_page()
    pdf.set_margins(18, 18, 18)

    # --- Cabecera: marca (logo/monograma) + nombre + título FACTURA ---
    _draw_brandmark(pdf, biz, 18, 16, 16, brand)
    pdf.set_xy(38, 17)
    pdf.set_font(fam, "B", 21)
    pdf.set_text_color(*brand)
    pdf.cell(110, 8, issuer_name)
    pdf.set_xy(150, 17)
    pdf.set_font(fam, "B", 20)
    pdf.set_text_color(*INK)
    pdf.cell(24, 8, tpl["title"], align="R")

    pdf.set_xy(38, 25)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED)
    datos = []
    if issuer_nif:
        datos.append(f"NIF: {issuer_nif}")
    if issuer_address:
        datos.append(issuer_address)
    pdf.cell(112, 5, "  |  ".join(datos))
    numero = inv.get("number") or "(borrador)"
    pdf.set_xy(150, 25)
    pdf.cell(24, 5, f"Nº {numero}", align="R")
    fecha = (inv.get("issued_at") or inv.get("created_at") or "")[:10]
    pdf.set_xy(150, 30)
    pdf.cell(24, 5, f"Fecha: {fecha or date.today().isoformat()}", align="R")

    pdf.set_y(40)
    pdf.set_draw_color(*brand)
    pdf.set_line_width(0.5)
    pdf.line(18, pdf.get_y(), 192, pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.ln(8)

    # --- Cliente ---
    pdf.set_text_color(*MUTED)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 6, "FACTURAR A", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(fam, "B", 12)
    pdf.set_text_color(*INK)
    pdf.cell(0, 7, recipient_name, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    recipient_data = []
    if recipient_nif:
        recipient_data.append(f"NIF: {recipient_nif}")
    if recipient_address:
        recipient_data.append(recipient_address)
    if recipient_data:
        pdf.multi_cell(0, 5, "  |  ".join(recipient_data))
    pdf.ln(8)

    # --- Tabla de conceptos (cabecera según plantilla) ---
    if tpl["table_fill"]:
        pdf.set_fill_color(*brand)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(96, 9, "  Concepto", fill=True)
        pdf.cell(26, 9, "Base", align="R", fill=True)
        pdf.cell(26, 9, "IVA", align="R", fill=True)
        pdf.cell(26, 9, "Total ", align="R", fill=True)
        pdf.ln(9)
    else:
        pdf.set_text_color(*brand)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(96, 8, "Concepto")
        pdf.cell(26, 8, "Base", align="R")
        pdf.cell(26, 8, "IVA", align="R")
        pdf.cell(26, 8, "Total", align="R")
        pdf.ln(8)
        pdf.set_draw_color(*brand)
        pdf.line(18, pdf.get_y(), 192, pdf.get_y())
        pdf.ln(2)

    pdf.set_text_color(*INK)
    pdf.set_font(fam, "", 10)
    pdf.cell(96, 9, ("  " if tpl["table_fill"] else "") + inv["concept"])
    pdf.cell(26, 9, _eur(inv["base"]).replace(" EUR", ""), align="R")
    pdf.cell(26, 9, f"{inv['vat_rate']:.0f}%", align="R")
    pdf.cell(26, 9, _eur(inv["total"]).replace(" EUR", "") + (" " if tpl["table_fill"] else ""), align="R")
    pdf.ln(9)
    pdf.set_draw_color(*LINE)
    pdf.line(18, pdf.get_y(), 192, pdf.get_y())
    pdf.ln(6)

    # --- Totales ---
    def total_row(label, value, bold=False, color=INK):
        pdf.cell(122, 7, "")
        pdf.set_font(fam, "B" if bold else "", 11 if bold else 10)
        pdf.set_text_color(*color)
        pdf.cell(30, 7, label, align="R")
        pdf.cell(0, 7, _eur(value), align="R", new_x="LMARGIN", new_y="NEXT")

    total_row("Base imponible", inv["base"])
    total_row(f"IVA ({inv['vat_rate']:.0f}%)", inv["vat_amount"])
    if inv.get("irpf_amount"):
        total_row(f"IRPF (-{inv['irpf_rate']:.0f}%)", -inv["irpf_amount"], color=MUTED)
    pdf.ln(1)
    total_row("TOTAL", inv["total"], bold=True, color=brand)

    # --- Pie ---
    pdf.ln(14)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(
        0, 4,
        "Factura generada con Noesis. Conserva este documento junto con los "
        "registros y justificantes de la operacion.",
    )

    out = pdf.output()
    return bytes(out)
