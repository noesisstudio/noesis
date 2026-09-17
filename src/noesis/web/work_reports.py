"""Informes verificables de jornada en CSV y PDF."""

from __future__ import annotations

import csv
from io import StringIO

from fpdf import FPDF

from .. import db
from .invoice_pdf import _draw_brandmark, _hex_to_rgb

INK = (22, 39, 31)
MUTED = (95, 107, 99)
LINE = (220, 224, 226)


def _location(event: dict) -> str:
    if event.get("lat") is None or event.get("lng") is None:
        return ""
    return f"{event['lat']},{event['lng']}"


def build_clockin_csv(data: dict) -> bytes:
    output = StringIO(newline="")
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "trabajador", "dia", "hora_original", "hora_efectiva", "accion",
        "estado", "horas_dia", "ubicacion", "precision_m", "origen",
        "sello_sha256", "sello_anterior", "motivo_correccion",
    ])
    for day in data["days"]:
        for event in day["events"]:
            effective_at = event.get("effective_at") or event["at"]
            writer.writerow([
                data["worker"]["name"],
                day["day"],
                str(event["at"])[11:19],
                str(effective_at)[11:19] if not event.get("annulled") else "",
                event["action"],
                event.get("correction_status") or "original",
                f"{day['hours']:.2f}",
                _location(event),
                event.get("accuracy") if event.get("accuracy") is not None else "",
                event["source"],
                event["seal"],
                event.get("prev_seal") or "",
                event.get("correction_reason") or "",
            ])
    writer.writerow([])
    integrity = data["integrity"]
    writer.writerow([
        "integridad",
        "VALIDA" if integrity["valid"] else "ALTERADA",
        f"{integrity['checked']} registros verificados",
        integrity.get("broken_at") or "",
    ])
    writer.writerow([
        "nota",
        "Los fichajes originales son inalterables. Las correcciones se conservan "
        "en un registro de auditoria separado.",
    ])
    return ("\ufeff" + output.getvalue()).encode("utf-8")


class _WorkReportPDF(FPDF):
    def __init__(self, business_name: str):
        super().__init__(format="A4")
        self.business_name = business_name

    def footer(self):
        self.set_y(-13)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 5, f"{self.business_name} - pagina {self.page_no()}", align="C")


def build_clockin_pdf(data: dict) -> bytes:
    business = data["business"]
    worker = data["worker"]
    brand = _hex_to_rgb(db.business_brand_color(business))
    pdf = _WorkReportPDF(business.get("name") or "Empresa")
    pdf.set_auto_page_break(True, 18)
    pdf.set_margins(17, 17, 17)
    pdf.add_page()

    _draw_brandmark(pdf, business, 17, 15, 14, brand)
    pdf.set_xy(35, 16)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*brand)
    pdf.cell(100, 7, business.get("name") or "Empresa")
    pdf.set_xy(132, 16)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*INK)
    pdf.cell(60, 7, "INFORME DE JORNADA", align="R")
    pdf.set_xy(35, 24)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(100, 5, f"Trabajador: {worker['name']}")
    pdf.set_xy(132, 24)
    pdf.cell(60, 5, f"{data['from']} a {data['to']}", align="R")

    pdf.set_y(37)
    integrity = data["integrity"]
    if integrity["valid"]:
        pdf.set_fill_color(226, 241, 234)
        integrity_text = (
            f"INTEGRIDAD VALIDA - {integrity['checked']} registros verificados"
        )
        integrity_color = (31, 138, 109)
    else:
        pdf.set_fill_color(247, 232, 227)
        integrity_text = (
            "CADENA ALTERADA - incidencia en el registro "
            f"{integrity.get('broken_at') or '?'}"
        )
        integrity_color = (192, 83, 63)
    pdf.set_text_color(*integrity_color)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 9, integrity_text, fill=True, align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    if not data["days"]:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(0, 6, "No hay registros de jornada en el periodo indicado.")

    for day in data["days"]:
        if pdf.get_y() > 250:
            pdf.add_page()
        pdf.set_fill_color(*brand)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(
            0, 8, f"{day['day']}  |  {day['hours']:.2f} horas efectivas",
            fill=True, new_x="LMARGIN", new_y="NEXT",
        )
        if not day["events"]:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*MUTED)
            pdf.cell(0, 7, "Sin eventos dentro de este dia.",
                     new_x="LMARGIN", new_y="NEXT")
        for event in day["events"]:
            if pdf.get_y() > 246:
                pdf.add_page()
            effective_at = event.get("effective_at") or event["at"]
            status = event.get("correction_status") or "original"
            effective_time = (
                "anulado" if event.get("annulled") else str(effective_at)[11:19]
            )
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*INK)
            pdf.cell(31, 7, event["action"].upper())
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(38, 7, f"Original {str(event['at'])[11:19]}")
            pdf.cell(42, 7, f"Efectivo {effective_time}")
            pdf.cell(34, 7, f"Estado: {status}")
            pdf.cell(0, 7, event["source"], align="R",
                     new_x="LMARGIN", new_y="NEXT")
            location = _location(event) or "sin ubicacion"
            pdf.set_text_color(*MUTED)
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(
                0, 5, f"Ubicacion: {location}  |  Precision: "
                f"{event.get('accuracy') or '-'} m",
                new_x="LMARGIN", new_y="NEXT",
            )
            pdf.set_font("Courier", "", 7)
            pdf.multi_cell(0, 3.8, f"Sello SHA-256: {event['seal']}")
            if event.get("correction_reason"):
                pdf.set_x(pdf.l_margin)
                pdf.set_font("Helvetica", "I", 8)
                pdf.set_text_color(*MUTED)
                pdf.multi_cell(
                    0, 4.2,
                    f"Correccion auditada: {event['correction_reason']}",
                )
            pdf.set_draw_color(*LINE)
            pdf.line(17, pdf.get_y() + 1, 193, pdf.get_y() + 1)
            pdf.ln(3)
        pdf.ln(3)

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*INK)
    pdf.cell(0, 6, "Nota de integridad",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*MUTED)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(
        0, 4.5,
        "Cada fichaje original esta sellado con SHA-256 y enlazado al sello "
        "anterior del mismo trabajador. Los originales no se editan ni se borran; "
        "cualquier rectificacion o anulacion queda en una auditoria separada. "
        "Conservacion prevista: cuatro anos conforme al articulo 34.9 del Estatuto "
        "de los Trabajadores.",
    )
    return bytes(pdf.output())


def build_clockin_xlsx(data: dict) -> bytes:
    """Misma jornada que el CSV, en una hoja con tipos y filtro."""
    from . import xlsx

    headers = [
        "Trabajador", "Dia", "Hora original", "Hora efectiva", "Accion",
        "Estado", "Horas del dia", "Ubicacion", "Precision (m)", "Origen",
        "Sello SHA256", "Sello anterior", "Motivo de la correccion",
    ]
    rows: list[list] = []
    for day in data["days"]:
        for event in day["events"]:
            effective_at = event.get("effective_at") or event["at"]
            rows.append([
                data["worker"]["name"],
                day["day"],
                str(event["at"])[11:19],
                str(effective_at)[11:19] if not event.get("annulled") else "",
                event["action"],
                event.get("correction_status") or "original",
                round(float(day["hours"]), 2),
                _location(event),
                event.get("accuracy") if event.get("accuracy") is not None else "",
                event["source"],
                event["seal"],
                event.get("prev_seal") or "",
                event.get("correction_reason") or "",
            ])
    integrity = data["integrity"]
    rows.append([])
    rows.append([
        "integridad",
        "VALIDA" if integrity["valid"] else "ALTERADA",
        f"{integrity['checked']} registros verificados",
        integrity.get("broken_at") or "",
    ])
    rows.append([
        "nota",
        "Los fichajes originales son inalterables. Las correcciones se "
        "conservan en un registro de auditoria separado.",
    ])
    return xlsx.build_sheet(headers, rows, title="Jornada")
