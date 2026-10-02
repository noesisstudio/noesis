"""Núcleo de mutación prestado; el propietario exterior confirma o revierte."""

from .. import db

from . import readers

from .boundary import run, positive_money


def _mutate_add_invoice_payment(
    conn, invoice_id, amount, *, business_id: int, method=None, paid_at=None, note=None
) -> dict:
    """Registra un cobro sin alterar el registro fiscal inmutable de la factura."""
    amount_decimal = db.Decimal(
        str(positive_money(amount, "El importe", legacy=conn.legacy))
    ).quantize(db.Decimal("0.01"))
    method = db._payment_text(method, "El método", 50)
    note = db._payment_text(note, "La nota", 500)
    paid_at = db._payment_paid_at(paid_at)
    invoice, already_paid = db._locked_invoice_with_paid(conn, invoice_id, business_id)
    if not invoice:
        raise ValueError("Factura no encontrada.")
    if invoice["status"] == "borrador" or not invoice.get("number"):
        raise ValueError("Solo se pueden cobrar facturas emitidas.")
    total = db.Decimal(str(invoice["total"])).quantize(db.Decimal("0.01"))
    if total <= 0:
        raise ValueError("Esta factura no admite cobros.")
    new_paid = already_paid + amount_decimal
    if new_paid > total:
        remaining = max(total - already_paid, db.Decimal("0.00"))
        raise ValueError(
            f"El cobro supera el importe pendiente ({db.Decimal(str(remaining)):.2f} €)."
        )
    payment_id = db._insert_invoice_payment(conn, invoice, amount_decimal, method, paid_at, note)
    db._set_invoice_payment_state(conn, invoice, new_paid, paid_at)
    db._record_invoice_event(
        conn,
        business_id,
        "cobro",
        invoice_id=invoice_id,
        details=f"importe={db.Decimal(str(amount_decimal)):.2f};metodo={method or 'no indicado'}",
        created_at=paid_at,
    )
    payment = conn.execute(
        "SELECT * FROM invoice_payments WHERE id=? AND business_id=? AND invoice_id=?",
        (payment_id, business_id, invoice_id),
    ).fetchone()
    saved = dict(payment)
    conn.observations.append(
        (
            "observe_payment_received",
            (business_id,),
            {
                "invoice_id": invoice_id,
                "payment_id": payment_id,
                "amount": amount_decimal,
                "occurred_at": paid_at,
            },
        )
    )
    return saved


def add_invoice_payment(borrowed, *args, legacy=False, expected_revision=None, **kwargs):
    return run(
        _mutate_add_invoice_payment,
        borrowed,
        args,
        kwargs,
        kind="invoice_payment",
        identity=None,
        target_kind="invoice",
        target_identity="invoice_id",
        legacy=legacy,
        expected_revision=expected_revision,
    )


def _mutate_mark_invoice_paid(conn, invoice_id, business_id) -> dict | None:
    """Registra el importe restante; repetir la operación no duplica el cobro."""
    payment_time = db._now()
    payment_id = None
    invoice, already_paid = db._locked_invoice_with_paid(conn, invoice_id, business_id)
    if not invoice or invoice["status"] == "borrador" or (not invoice.get("number")):
        return None
    total = db.Decimal(str(invoice["total"])).quantize(db.Decimal("0.01"))
    remaining = total - already_paid
    if total <= 0:
        return None
    if remaining > 0:
        payment_id = db._insert_invoice_payment(
            conn, invoice, remaining, None, payment_time, "Cobro completo registrado"
        )
        db._set_invoice_payment_state(conn, invoice, total, payment_time)
        db._record_invoice_event(
            conn,
            business_id,
            "cobro",
            invoice_id=invoice_id,
            details=f"importe={db.Decimal(str(remaining)):.2f};metodo=no indicado",
            created_at=payment_time,
        )
    saved = readers.get_invoice(conn, invoice_id, business_id)
    if payment_id is not None:
        conn.observations.append(
            (
                "observe_payment_received",
                (business_id,),
                {
                    "invoice_id": invoice_id,
                    "payment_id": payment_id,
                    "amount": remaining,
                    "occurred_at": payment_time,
                },
            )
        )
    return saved


def mark_invoice_paid(borrowed, *args, legacy=False, expected_revision=None, **kwargs):
    return run(
        _mutate_mark_invoice_paid,
        borrowed,
        args,
        kwargs,
        kind="invoice",
        identity="invoice_id",
        legacy=legacy,
        expected_revision=expected_revision,
    )
