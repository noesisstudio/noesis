"""Generación de informes descargables (CSV y Excel; PDF más adelante).

Las filas se construyen una sola vez con sus tipos reales. El CSV las formatea a
texto y el Excel las pasa tal cual, para que en la hoja se puedan sumar y ordenar
sin tocar nada.
"""

from __future__ import annotations

import csv
import io

from .. import db
from . import xlsx


def _cell(value):
    """Evita que Excel interprete contenido del usuario como una fórmula."""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _money(value) -> str:
    return f"{float(value or 0):.2f}"


def _csv(headers: list[str], rows: list[list]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")  # ; para que Excel español lo abra bien
    w.writerow(headers)
    w.writerows([[_cell(value) for value in row] for row in rows])
    return buf.getvalue()


COSTS_HEADERS = ["Fecha", "Concepto", "Importe", "IVA%", "Categoria"]
INVOICES_HEADERS = ["Numero", "Fecha", "Cliente", "Concepto", "Base", "IVA",
                    "IRPF", "Total", "Estado"]
RECEIVED_HEADERS = ["Fecha", "Proveedor", "Numero", "Base", "IVA", "Total",
                    "Estado"]


def _costs_rows(business_id: int) -> list[list]:
    return [[e["created_at"][:10], e["concept"], float(e["amount"] or 0),
             e.get("vat_rate") or "", e.get("category") or ""]
            for e in db.list_expenses(business_id)]


def _invoices_rows(business_id: int) -> list[list]:
    return [[i.get("number") or "(borrador)", i["created_at"][:10],
             i.get("client_name") or "", i["concept"], float(i["base"] or 0),
             float(i["vat_amount"] or 0), float(i.get("irpf_amount") or 0),
             float(i["total"] or 0), i["status"]]
            for i in db.list_invoices(business_id)]


def _received_rows(business_id: int) -> list[list]:
    filas = []
    for r in db.list_received_invoices(business_id):
        fecha = r.get("issued_on") or str(r.get("created_at") or "")[:10]
        filas.append([
            fecha, r.get("supplier_name") or "", r.get("number") or "",
            float(r["base"]) if r.get("base") is not None else "",
            float(r["vat_amount"]) if r.get("vat_amount") is not None else "",
            float(r.get("total") or 0), r.get("status") or "",
        ])
    return filas


def costs_csv(business_id: int) -> str:
    rows = [[fila[0], fila[1], _money(fila[2]), fila[3], fila[4]]
            for fila in _costs_rows(business_id)]
    return _csv(COSTS_HEADERS, rows)


def invoices_csv(business_id: int) -> str:
    rows = [[fila[0], fila[1], fila[2], fila[3], _money(fila[4]),
             _money(fila[5]), _money(fila[6]), _money(fila[7]), fila[8]]
            for fila in _invoices_rows(business_id)]
    return _csv(INVOICES_HEADERS, rows)


def costs_xlsx(business_id: int) -> bytes:
    return xlsx.build_sheet(COSTS_HEADERS, _costs_rows(business_id),
                            title="Gastos")


def invoices_xlsx(business_id: int) -> bytes:
    return xlsx.build_sheet(INVOICES_HEADERS, _invoices_rows(business_id),
                            title="Facturas emitidas")


def received_invoices_xlsx(business_id: int) -> bytes:
    return xlsx.build_sheet(RECEIVED_HEADERS, _received_rows(business_id),
                            title="Facturas recibidas")


def received_invoices_csv(business_id: int) -> str:
    rows = [[fila[0], fila[1], fila[2],
             _money(fila[3]) if fila[3] != "" else "",
             _money(fila[4]) if fila[4] != "" else "",
             _money(fila[5]), fila[6]]
            for fila in _received_rows(business_id)]
    return _csv(RECEIVED_HEADERS, rows)
