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
from PIL import Image

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


def _invoice_visual_business(invoice: dict, business: dict) -> dict:
    """Aplica la marca congelada al emitir; los borradores usan la vigente."""
    if invoice.get("status") == "borrador" or not invoice.get("document_profile_id"):
        return business
    profile = db.get_invoice_document_profile(invoice["id"], business["id"])
    if not profile:
        return business
    visual = dict(business)
    for field in db._DOCUMENT_PROFILE_FIELDS:
        visual[field] = profile.get(field)
    return visual


def _draw_document_footer(
    pdf: FPDF, biz: dict, *, default_text: str, document_kind: str,
) -> None:
    """Pie textual y distintivo opcional sin invadir el contenido fiscal."""
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(0, 4, biz.get("document_footer") or default_text)

    show_image = bool(biz.get("footer_image_data")) and (
        document_kind == "invoice" or biz.get("footer_image_scope") == "all"
    )
    if not show_image:
        return
    try:
        data = base64.b64decode(biz["footer_image_data"], validate=True)
        with Image.open(BytesIO(data)) as image:
            pixel_w, pixel_h = image.size
        if pixel_w <= 0 or pixel_h <= 0:
            return
        width_percent = int(biz.get("footer_image_width") or 100)
        width_percent = width_percent if width_percent in db.FOOTER_IMAGE_WIDTHS else 100
        image_w = 174 * width_percent / 100
        image_h = image_w * pixel_h / pixel_w
        if image_h > 48:
            image_h = 48
            image_w = image_h * pixel_w / pixel_h
        if pdf.get_y() + image_h + 8 > 279:
            pdf.add_page()
            pdf.set_y(18)
        else:
            pdf.ln(5)
        alignment = biz.get("footer_image_alignment") or "center"
        if alignment == "left":
            image_x = 18
        elif alignment == "right":
            image_x = 192 - image_w
        else:
            image_x = 18 + (174 - image_w) / 2
        pdf.image(BytesIO(data), x=image_x, y=pdf.get_y(), w=image_w, h=image_h)
        pdf.set_y(pdf.get_y() + image_h)
    except Exception:  # noqa: BLE001 -- perfil antiguo/corrupto: PDF aún utilizable
        return


def build_invoice_pdf(invoice_id: int, business_id: int) -> bytes | None:
    inv = db.get_invoice(invoice_id, business_id)
    if not inv:
        return None
    biz = db.get_business(business_id) or {}
    biz = _invoice_visual_business(inv, biz)
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
    if not pay_lines:
        pdf.ln(4)
    _draw_document_footer(
        pdf, biz, document_kind="invoice",
        default_text=(
            "Factura generada con Noesis. Conserva este documento junto con los "
            "registros y justificantes de la operación."
        ),
    )

    out = pdf.output()
    return bytes(out)


def build_quote_pdf(quote_id: int, business_id: int) -> bytes | None:
    """Genera el presupuesto con la misma identidad visual que la factura.

    El PDF es una representación comercial: no emite factura, no reserva número
    fiscal y deja claro su estado para no confundirlo con un documento tributario.
    """
    quote = db.get_quote(quote_id, business_id)
    if not quote:
        return None
    biz = db.get_business(business_id) or {}
    client = db.get_client(quote["client_id"], business_id) or {}
    tpl = _TEMPLATES.get(
        biz.get("invoice_template") or "clasica", _TEMPLATES["clasica"]
    )
    fam = "Times" if tpl["serif"] else "Helvetica"
    brand = _hex_to_rgb(db.business_brand_color(biz))

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, 18)
    pdf.set_margins(18, 18, 18)
    pdf.add_page()

    _draw_brandmark(pdf, biz, 18, 16, 16, brand)
    pdf.set_xy(38, 17)
    pdf.set_font(fam, "B", 21)
    pdf.set_text_color(*brand)
    pdf.cell(105, 8, biz.get("name") or "Mi Negocio")
    pdf.set_xy(145, 17)
    pdf.set_font(fam, "B", 19)
    pdf.set_text_color(*INK)
    pdf.cell(47, 8, "PRESUPUESTO", align="R")

    issuer = []
    if biz.get("nif"):
        issuer.append(f"NIF: {biz['nif']}")
    if biz.get("address"):
        issuer.append(biz["address"])
    pdf.set_xy(38, 26)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(105, 5, "  |  ".join(issuer))
    pdf.set_xy(145, 26)
    pdf.cell(47, 5, f"Nº {quote.get('number') or 'BORRADOR'}", align="R")
    pdf.set_xy(145, 31)
    pdf.cell(47, 5, f"Fecha: {(quote.get('created_at') or '')[:10]}", align="R")
    if quote.get("valid_until"):
        pdf.set_xy(145, 36)
        pdf.cell(47, 5, f"Válido hasta: {str(quote['valid_until'])[:10]}", align="R")

    pdf.set_y(48)
    pdf.set_draw_color(*brand)
    pdf.set_line_width(.5)
    pdf.line(18, pdf.get_y(), 192, pdf.get_y())
    pdf.ln(9)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, "PRESUPUESTO PARA", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(fam, "B", 12)
    pdf.set_text_color(*INK)
    pdf.cell(0, 7, client.get("name") or quote.get("client_name") or "Cliente",
             new_x="LMARGIN", new_y="NEXT")
    client_data = []
    if client.get("nif"):
        client_data.append(f"NIF: {client['nif']}")
    if client.get("address"):
        client_data.append(client["address"])
    if client_data:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(0, 5, "  |  ".join(client_data))
    pdf.ln(8)

    if tpl["table_fill"]:
        pdf.set_fill_color(*brand)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(104, 9, "  Concepto", fill=True)
        pdf.cell(34, 9, "Base", align="R", fill=True)
        pdf.cell(36, 9, "Total ", align="R", fill=True)
    else:
        pdf.set_text_color(*brand)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(104, 9, "Concepto")
        pdf.cell(34, 9, "Base", align="R")
        pdf.cell(36, 9, "Total", align="R")
    pdf.ln(9)
    row_y = pdf.get_y()
    pdf.set_font(fam, "", 10)
    pdf.set_text_color(*INK)
    pdf.multi_cell(104, 6, quote["concept"])
    row_bottom = max(pdf.get_y(), row_y + 12)
    pdf.set_xy(122, row_y)
    pdf.cell(34, 9, _eur(quote["base"]), align="R")
    pdf.cell(36, 9, _eur(quote["total"]), align="R")
    pdf.set_y(row_bottom)
    pdf.set_draw_color(*LINE)
    pdf.line(18, pdf.get_y(), 192, pdf.get_y())
    pdf.ln(7)

    def total_row(label, value, *, bold=False):
        pdf.cell(86, 7, "")
        pdf.set_font(fam, "B" if bold else "", 11 if bold else 10)
        pdf.set_text_color(*(brand if bold else INK))
        pdf.cell(45, 7, label, align="R")
        pdf.cell(43, 7, _eur(value), align="R", new_x="LMARGIN", new_y="NEXT")

    total_row("Base imponible", quote["base"])
    total_row(f"IVA ({quote['vat_rate']:g}%)", quote["vat_amount"])
    if quote.get("irpf_amount"):
        total_row(f"IRPF (-{quote['irpf_rate']:g}%)", -quote["irpf_amount"])
    total_row("TOTAL", quote["total"], bold=True)

    sections = []
    if quote.get("notes"):
        sections.append(("DETALLES", quote["notes"]))
    if biz.get("quote_terms"):
        sections.append(("CONDICIONES", biz["quote_terms"]))
    for title, body in sections:
        pdf.ln(8)
        pdf.set_font(fam, "B", 9)
        pdf.set_text_color(*brand)
        pdf.cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(fam, "", 9)
        pdf.set_text_color(*INK)
        pdf.multi_cell(0, 5, body, new_x="LMARGIN", new_y="NEXT")

    _draw_document_footer(
        pdf, biz, document_kind="quote",
        default_text=(
            "Este presupuesto no es una factura. Su aprobación prepara el trabajo; "
            "la factura se emitirá por separado."
        ),
    )
    return bytes(pdf.output())


def build_brand_preview_pdf(business_id: int) -> bytes | None:
    """Muestra exacta y segura de la identidad, sin crear una factura ficticia."""
    biz = db.get_business(business_id)
    if not biz:
        return None
    tpl = _TEMPLATES.get(
        biz.get("invoice_template") or "clasica", _TEMPLATES["clasica"]
    )
    fam = "Times" if tpl["serif"] else "Helvetica"
    brand = _hex_to_rgb(db.business_brand_color(biz))
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, 18)
    pdf.set_margins(18, 18, 18)
    pdf.add_page()
    _draw_brandmark(pdf, biz, 18, 16, 16, brand)
    pdf.set_xy(38, 17)
    pdf.set_font(fam, "B", 21)
    pdf.set_text_color(*brand)
    pdf.cell(105, 8, biz.get("name") or "Mi negocio")
    pdf.set_xy(145, 17)
    pdf.set_font(fam, "B", 18)
    pdf.set_text_color(*INK)
    pdf.cell(47, 8, tpl["title"], align="R")
    pdf.set_xy(38, 26)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(105, 5, "Tu información fiscal aparecerá aquí")
    pdf.set_xy(145, 26)
    pdf.cell(47, 5, "VISTA PREVIA", align="R")
    pdf.set_y(46)
    pdf.set_draw_color(*brand)
    pdf.line(18, pdf.get_y(), 192, pdf.get_y())
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, "CLIENTE DE EJEMPLO", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(fam, "B", 12)
    pdf.set_text_color(*INK)
    pdf.cell(0, 7, "Así verá tu cliente la factura", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    if tpl["table_fill"]:
        pdf.set_fill_color(*brand)
        pdf.set_text_color(255, 255, 255)
    else:
        pdf.set_text_color(*brand)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(110, 9, "  Trabajo realizado", fill=tpl["table_fill"])
    pdf.cell(64, 9, "Importe ", align="R", fill=tpl["table_fill"])
    pdf.ln(12)
    pdf.set_font(fam, "", 10)
    pdf.set_text_color(*INK)
    pdf.cell(110, 8, "Servicio de ejemplo")
    pdf.cell(64, 8, "1.000,00 EUR", align="R")
    pdf.ln(18)
    pdf.set_font(fam, "B", 12)
    pdf.set_text_color(*brand)
    pdf.cell(0, 8, "TOTAL  1.210,00 EUR", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(18)
    pdf.set_fill_color(247, 232, 227)
    pdf.set_text_color(130, 64, 48)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(
        0, 8, "VISTA PREVIA · NO ES UNA FACTURA FISCAL", align="C", fill=True,
        new_x="LMARGIN", new_y="NEXT",
    )
    _draw_document_footer(
        pdf, biz, document_kind="invoice",
        default_text="Tu pie habitual aparecerá aquí.",
    )
    return bytes(pdf.output())
