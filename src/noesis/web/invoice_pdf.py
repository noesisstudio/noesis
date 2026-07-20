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

from .. import db, verifactu

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
    record = db.get_invoice_record(invoice_id, business_id)
    # Una factura que nació con registro conserva siempre su QR aunque el negocio
    # desactive el modo para futuras emisiones.
    verifactu_active = bool(record)
    issuer_name = inv.get("issuer_name") or biz.get("name") or "Mi Negocio"
    issuer_nif = inv.get("issuer_nif") or biz.get("nif")
    issuer_address = inv.get("issuer_address") or biz.get("address")
    recipient_name = (
        inv.get("recipient_name") or client.get("name")
        or inv.get("client_name") or "Cliente"
    )
    recipient_nif = inv.get("recipient_nif") or client.get("nif")
    recipient_address = inv.get("recipient_address") or client.get("address")
    invoice_type = (inv.get("invoice_type") or "F1").upper()
    is_rectifying = invoice_type.startswith("R")

    tpl = _TEMPLATES.get(biz.get("invoice_template") or "clasica", _TEMPLATES["clasica"])
    fam = "Times" if tpl["serif"] else "Helvetica"
    brand = _hex_to_rgb(db.business_brand_color(biz))

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, 18)
    pdf.add_page()
    pdf.set_margins(18, 18, 18)

    # --- Cabecera: QR tributario (si procede) + marca + título FACTURA ---
    header_x = 60 if verifactu_active else 18
    text_x = 80 if verifactu_active else 38
    if verifactu_active:
        pdf.set_xy(18, 10)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*INK)
        pdf.cell(35, 5, "QR tributario:", align="C")
        qr = BytesIO(verifactu.qr_png(record["qr_url"]))
        pdf.image(qr, x=18, y=15, w=35, h=35)
        pdf.set_xy(18, 51)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*INK)
        pdf.cell(35, 5, "VERI*FACTU", align="C")

    _draw_brandmark(pdf, biz, header_x, 16, 16, brand)
    pdf.set_xy(text_x, 17)
    pdf.set_font(fam, "B", 21)
    pdf.set_text_color(*brand)
    pdf.cell(68 if verifactu_active else 110, 8, issuer_name)
    pdf.set_xy(150, 17)
    pdf.set_font(fam, "B", 13 if is_rectifying else 20)
    pdf.set_text_color(*INK)
    title = "RECTIFICATIVA" if is_rectifying else tpl["title"]
    pdf.cell(42, 8, title, align="R")

    pdf.set_xy(text_x, 25)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED)
    datos = []
    if issuer_nif:
        datos.append(f"NIF: {issuer_nif}")
    if issuer_address:
        datos.append(issuer_address)
    pdf.cell(68 if verifactu_active else 112, 5, "  |  ".join(datos))
    numero = inv.get("number") or "(borrador)"
    pdf.set_xy(150, 25)
    pdf.cell(42, 5, f"Nº {numero}", align="R")
    fecha = (inv.get("issued_at") or inv.get("created_at") or "")[:10]
    pdf.set_xy(150, 30)
    pdf.cell(42, 5, f"Fecha: {fecha or date.today().isoformat()}", align="R")
    if inv.get("operation_date"):
        pdf.set_xy(150, 35)
        pdf.cell(42, 5, f"Operación: {inv['operation_date']}", align="R")

    pdf.set_y(62 if verifactu_active else 40)
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
    if is_rectifying:
        original = db.get_invoice(inv.get("rectifies_invoice_id"), business_id)
        reference = original.get("number") if original else None
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*brand)
        pdf.cell(0, 5, f"FACTURA RECTIFICATIVA {invoice_type}",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*MUTED)
        details = []
        if reference:
            details.append(f"Rectifica la factura {reference}")
        if inv.get("rectification_reason"):
            details.append(f"Motivo: {inv['rectification_reason']}")
        if details:
            pdf.multi_cell(0, 5, "  |  ".join(details))
    pdf.ln(8)

    # --- Tabla de conceptos (cabecera según plantilla) ---
    if tpl["table_fill"]:
        pdf.set_fill_color(*brand)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(72, 9, "  Concepto", fill=True)
        pdf.cell(18, 9, "Cant.", align="R", fill=True)
        pdf.cell(28, 9, "Precio", align="R", fill=True)
        pdf.cell(18, 9, "IVA", align="R", fill=True)
        pdf.cell(38, 9, "Total ", align="R", fill=True)
        pdf.ln(9)
    else:
        pdf.set_text_color(*brand)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(72, 8, "Concepto")
        pdf.cell(18, 8, "Cant.", align="R")
        pdf.cell(28, 8, "Precio", align="R")
        pdf.cell(18, 8, "IVA", align="R")
        pdf.cell(38, 8, "Total", align="R")
        pdf.ln(8)
        pdf.set_draw_color(*brand)
        pdf.line(18, pdf.get_y(), 192, pdf.get_y())
        pdf.ln(2)

    lines = inv.get("lines") or [{
        "description": inv["concept"], "quantity": 1,
        "unit_price": inv["base"], "discount_rate": 0,
        "vat_rate": inv["vat_rate"], "total": inv["base"] + inv["vat_amount"],
        "base": inv["base"], "vat_amount": inv["vat_amount"],
    }]
    for line in lines:
        pdf.set_text_color(*INK)
        pdf.set_font(fam, "", 9)
        row_y = pdf.get_y()
        pdf.set_xy(18, row_y)
        description = line["description"]
        if line.get("discount_rate"):
            description += f" · dto. {line['discount_rate']:g}%"
        pdf.multi_cell(
            72, 5, ("  " if tpl["table_fill"] else "") + description
        )
        row_bottom = max(pdf.get_y(), row_y + 9)
        pdf.set_xy(90, row_y)
        pdf.cell(18, 9, f"{line['quantity']:g}", align="R")
        pdf.cell(28, 9, _eur(line["unit_price"]).replace(" EUR", ""), align="R")
        pdf.cell(18, 9, f"{line['vat_rate']:g}%", align="R")
        pdf.cell(
            38, 9,
            _eur(line["total"]).replace(" EUR", "")
            + (" " if tpl["table_fill"] else ""), align="R",
        )
        pdf.set_y(row_bottom)
        pdf.set_draw_color(*LINE)
        pdf.line(18, pdf.get_y(), 192, pdf.get_y())
        pdf.ln(3)
    pdf.ln(3)

    # --- Totales ---
    def total_row(label, value, bold=False, color=INK):
        pdf.cell(85, 7, "")
        pdf.set_font(fam, "B" if bold else "", 11 if bold else 10)
        pdf.set_text_color(*color)
        pdf.cell(40, 7, label, align="R")
        pdf.cell(49, 7, _eur(value), align="R",
                 new_x="LMARGIN", new_y="NEXT")

    total_row("Base imponible", inv["base"])
    tax_groups = {}
    for line in lines:
        rate = float(line["vat_rate"])
        tax_groups[rate] = tax_groups.get(rate, 0) + float(line["vat_amount"])
    for rate, amount in sorted(tax_groups.items()):
        total_row(f"IVA ({rate:g}%)", amount)
    if inv.get("irpf_amount"):
        total_row(f"IRPF (-{inv['irpf_rate']:.0f}%)", -inv["irpf_amount"], color=MUTED)
    pdf.ln(1)
    total_row("TOTAL", inv["total"], bold=True, color=brand)

    # --- Forma de pago (si el negocio la ha configurado) ---
    pay_lines = []
    if inv.get("payment_method"):
        pay_lines.append(f"Método:  {inv['payment_method']}")
    if biz.get("payment_iban"):
        pay_lines.append(f"Transferencia:  {biz['payment_iban']}")
    if biz.get("payment_bizum"):
        pay_lines.append(f"Bizum:  {biz['payment_bizum']}")
    if biz.get("payment_note"):
        pay_lines.append(biz["payment_note"])
    if pay_lines:
        pdf.ln(12)
        pdf.set_font(fam, "B", 9)
        pdf.set_text_color(*brand)
        pdf.cell(0, 6, "FORMA DE PAGO", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(fam, "", 10)
        pdf.set_text_color(*INK)
        for line in pay_lines:
            pdf.multi_cell(0, 5, line, new_x="LMARGIN", new_y="NEXT")

    if inv.get("notes") or inv.get("legal_mention"):
        pdf.ln(8)
        pdf.set_font(fam, "B", 9)
        pdf.set_text_color(*brand)
        pdf.cell(0, 6, "NOTAS", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(fam, "", 9)
        pdf.set_text_color(*INK)
        if inv.get("notes"):
            pdf.multi_cell(0, 5, inv["notes"], new_x="LMARGIN", new_y="NEXT")
        if inv.get("legal_mention"):
            pdf.multi_cell(
                0, 5, inv["legal_mention"], new_x="LMARGIN", new_y="NEXT"
            )

    # --- Pie ---
    pdf.ln(10 if pay_lines else 14)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(
        0, 4,
        "Factura generada con Noesis. Conserva este documento junto con los "
        "registros y justificantes de la operacion.",
    )

    out = pdf.output()
    return bytes(out)
