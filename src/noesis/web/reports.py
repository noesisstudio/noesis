"""Generación de informes descargables (CSV por ahora; PDF más adelante)."""

from __future__ import annotations

import csv
import io

from .. import db


def _cell(value):
    """Evita que Excel interprete contenido del usuario como una fórmula."""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _csv(headers: list[str], rows: list[list]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")  # ; para que Excel español lo abra bien
    w.writerow(headers)
    w.writerows([[_cell(value) for value in row] for row in rows])
    return buf.getvalue()


def costs_csv(business_id: int) -> str:
    rows = [[e["created_at"][:10], e["concept"], f"{e['amount']:.2f}",
             e.get("vat_rate") or "", e.get("category") or ""]
            for e in db.list_expenses(business_id)]
    return _csv(["Fecha", "Concepto", "Importe", "IVA%", "Categoria"], rows)


def invoices_csv(business_id: int) -> str:
    rows = [[i.get("number") or "(borrador)", i["created_at"][:10],
             i.get("client_name") or "", i["concept"], f"{i['base']:.2f}",
             f"{i['vat_amount']:.2f}", f"{i.get('irpf_amount') or 0:.2f}",
             f"{i['total']:.2f}", i["status"]]
            for i in db.list_invoices(business_id)]
    return _csv(["Numero", "Fecha", "Cliente", "Concepto", "Base", "IVA",
                 "IRPF", "Total", "Estado"], rows)
