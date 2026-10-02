"""Escenario reproducible; la referencia se capturó del código main anterior."""

from datetime import date
from unittest.mock import patch

from noesis import verifactu


class FiscalDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 10, 2)


def scenario(database, business_id, client_id):
    result = []
    with (
        patch.object(database, "date", FiscalDate),
        patch.object(database, "_now", return_value="2026-10-02T10:00:00"),
        patch.object(
            verifactu, "generated_at_with_timezone", return_value="2026-10-02T10:00:00+02:00"
        ),
    ):
        database.update_verifactu_mode(business_id, True)
        first = database.add_invoice(
            client_id,
            "Varias",
            None,
            business_id=business_id,
            irpf_rate=15,
            lines=[
                {"description": str(rate), "quantity": 1, "unit_price": "10.05", "vat_rate": rate}
                for rate in (21, 10, 4, 0)
            ],
        )
        second = database.add_invoice(
            client_id, "Ticket", "100", business_id=business_id, invoice_type="F2"
        )
        issued = []
        for invoice in (first, second):
            issued.append(database.issue_invoice(invoice["id"], business_id))
        for typ in ("R1", "R2", "R3", "R4", "R5"):
            original = second if typ == "R5" else first
            draft = database.create_rectifying_invoice(
                original["id"],
                business_id,
                concept="Rectificación",
                base="-2.675",
                invoice_type=typ,
                reason="Error de precio",
            )
            issued.append(database.issue_invoice(draft["id"], business_id))
        for invoice in issued:
            record = database.get_invoice_record(invoice["id"], business_id)
            result.append({"invoice": invoice, "record": record})
        with database.get_conn() as conn:
            conn.execute(
                "UPDATE verifactu_outbox SET status='aceptado' WHERE business_id=? AND invoice_id=?",
                (business_id, first["id"]),
            )
        cancellation = database.create_invoice_cancellation_record(
            first["id"], business_id, reason="Error confirmado"
        )
        records = database.list_invoice_records(business_id)
        result.append(
            {
                "cancellation": cancellation,
                "xml": verifactu.build_aeat_xml(
                    database.get_business(business_id), records
                ).decode(),
            }
        )
    return result
