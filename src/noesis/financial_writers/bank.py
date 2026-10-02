"""Núcleo de mutación prestado; el propietario exterior confirma o revierte."""

from .. import db

from . import readers

from .boundary import run
from ..core.money import quantize_currency


def _mutate_add_bank_transaction(
    conn,
    business_id: int,
    *,
    import_hash: str,
    booked_on: str,
    amount: float,
    description: str = "",
    counterparty: str = "",
    reference: str = "",
    currency: str = "EUR",
) -> dict | None:
    """Guarda un movimiento una sola vez; nunca lo convierte en cobro solo."""
    if not readers.get_business(conn, business_id):
        raise ValueError("Negocio no encontrado.")
    try:
        db.date.fromisoformat(booked_on)
    except ValueError as exc:
        raise ValueError("La fecha del movimiento no es válida.") from exc
    number = (
        db.Decimal(str(amount)).quantize(db.Decimal("0.01"), rounding=db.ROUND_HALF_UP)
        if conn.legacy
        else quantize_currency(amount)
    )
    if not number.is_finite() or number == 0:
        raise ValueError("El movimiento necesita un importe distinto de cero.")
    clean_hash = str(import_hash or "").strip().lower()
    if not db.re.fullmatch("[0-9a-f]{64}", clean_hash):
        raise ValueError("La huella del movimiento no es válida.")
    fields = {
        "description": db._payment_text(description, "La descripción", 500),
        "counterparty": db._payment_text(counterparty, "La contraparte", 200),
        "reference": db._payment_text(reference, "La referencia", 200),
    }
    row = conn.execute(
        "INSERT INTO bank_transactions (business_id, import_hash, booked_on, amount, currency, description, counterparty, reference, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (business_id, import_hash) DO NOTHING RETURNING id",
        (
            business_id,
            clean_hash,
            booked_on,
            db.Decimal(str(number)),
            (currency or "EUR").strip().upper()[:3],
            fields["description"],
            fields["counterparty"],
            fields["reference"],
            db._now(),
        ),
    ).fetchone()
    if not row:
        return None
    transaction_id = row["id"]
    return readers.get_bank_transaction(conn, transaction_id, business_id)


def add_bank_transaction(borrowed, *args, legacy=False, expected_revision=None, **kwargs):
    return run(
        _mutate_add_bank_transaction,
        borrowed,
        args,
        kwargs,
        kind="bank_transaction",
        identity=None,
        legacy=legacy,
        expected_revision=expected_revision,
    )


def _mutate_suggest_bank_transaction(
    conn,
    transaction_id: int,
    business_id: int,
    invoice_id: int | None,
    *,
    score: int | None = None,
    reason: str = "",
) -> dict | None:
    if invoice_id is not None:
        invoice = readers.get_invoice(conn, invoice_id, business_id)
        if not invoice or invoice.get("status") == "borrador":
            raise ValueError("La factura sugerida no es válida.")
    cur = conn.execute(
        "UPDATE bank_transactions SET status=?, suggested_invoice_id=?, match_score=?, match_reason=? WHERE id=? AND business_id=? AND status IN ('imported','suggested')",
        (
            "suggested" if invoice_id is not None else "imported",
            invoice_id,
            score,
            db._payment_text(reason, "El motivo", 300),
            transaction_id,
            business_id,
        ),
    )
    return readers.get_bank_transaction(conn, transaction_id, business_id) if cur.rowcount else None


def suggest_bank_transaction(borrowed, *args, legacy=False, expected_revision=None, **kwargs):
    return run(
        _mutate_suggest_bank_transaction,
        borrowed,
        args,
        kwargs,
        kind="bank_transaction",
        identity="transaction_id",
        legacy=legacy,
        expected_revision=expected_revision,
    )


def _mutate_confirm_bank_transaction(conn, transaction_id: int, business_id: int) -> dict:
    """Confirma una sugerencia y registra el cobro en la misma transacción."""
    lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
    movement = conn.execute(
        "SELECT * FROM bank_transactions WHERE id=? AND business_id=?" + lock,
        (transaction_id, business_id),
    ).fetchone()
    if not movement:
        raise ValueError("Movimiento no encontrado.")
    if movement["status"] == "confirmed":
        return dict(movement)
    invoice_id = movement.get("suggested_invoice_id")
    if movement["status"] != "suggested" or not invoice_id:
        raise ValueError("Este movimiento no tiene una factura sugerida.")
    amount = db.Decimal(str(movement["amount"])).quantize(db.Decimal("0.01"))
    if amount <= 0:
        raise ValueError("Solo una entrada de dinero puede confirmar un cobro.")
    invoice, already_paid = db._locked_invoice_with_paid(conn, invoice_id, business_id)
    if not invoice or invoice["status"] == "borrador" or (not invoice.get("number")):
        raise ValueError("La factura ya no admite este cobro.")
    total = db.Decimal(str(invoice["total"])).quantize(db.Decimal("0.01"))
    if already_paid + amount > total:
        raise ValueError("El movimiento supera lo que queda por cobrar.")
    note = " · ".join(
        (
            value
            for value in (
                "Conciliado desde extracto",
                movement.get("reference"),
                movement.get("description"),
            )
            if value
        )
    )[:500]
    payment_id = db._insert_invoice_payment(
        conn, invoice, amount, "extracto_bancario", f"{movement['booked_on']}T12:00:00", note
    )
    db._set_invoice_payment_state(
        conn, invoice, already_paid + amount, f"{movement['booked_on']}T12:00:00"
    )
    db._record_invoice_event(
        conn,
        business_id,
        "cobro",
        invoice_id=invoice_id,
        details=f"importe={db.Decimal(str(amount)):.2f};metodo=extracto_bancario",
        created_at=f"{movement['booked_on']}T12:00:00",
    )
    now = db._now()
    conn.execute(
        "UPDATE bank_transactions SET status='confirmed', confirmed_at=? WHERE id=? AND business_id=?",
        (now, transaction_id, business_id),
    )
    conn.execute(
        "INSERT INTO bank_payment_links (business_id,bank_transaction_id,payment_id) VALUES (?,?,?)",
        (business_id, transaction_id, payment_id),
    )
    return readers.get_bank_transaction(conn, transaction_id, business_id) or {}


def confirm_bank_transaction(borrowed, *args, legacy=False, expected_revision=None, **kwargs):
    return run(
        _mutate_confirm_bank_transaction,
        borrowed,
        args,
        kwargs,
        kind="bank_transaction",
        identity="transaction_id",
        legacy=legacy,
        expected_revision=expected_revision,
    )


def _mutate_ignore_bank_transaction(conn, transaction_id: int, business_id: int) -> dict | None:
    cur = conn.execute(
        "UPDATE bank_transactions SET status='ignored', suggested_invoice_id=NULL, match_score=NULL, match_reason=NULL WHERE id=? AND business_id=? AND status<>'confirmed'",
        (transaction_id, business_id),
    )
    return readers.get_bank_transaction(conn, transaction_id, business_id) if cur.rowcount else None


def ignore_bank_transaction(borrowed, *args, legacy=False, expected_revision=None, **kwargs):
    return run(
        _mutate_ignore_bank_transaction,
        borrowed,
        args,
        kwargs,
        kind="bank_transaction",
        identity="transaction_id",
        legacy=legacy,
        expected_revision=expected_revision,
    )
