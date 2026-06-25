"""Datos de demostración para que el prototipo arranque con algo que mirar."""

from datetime import date, datetime, timedelta

from . import db


def seed() -> None:
    """Carga clientes, trabajos de hoy y una factura pendiente de ejemplo."""
    db.reset_db()

    marta = db.add_client("Marta García", phone="+34600111222", zone="Badalona")
    carlos = db.add_client("Carlos Ruiz", phone="+34600333444", zone="Barcelona")
    laura = db.add_client("Laura Soler", phone="+34600555666", zone="Barcelona")

    today = date.today()
    at = lambda h, m=0: datetime(today.year, today.month, today.day, h, m).isoformat(timespec="minutes")

    db.add_job(marta["id"], "Cambio de grifo cocina", scheduled_for=at(9, 30),
               zone="Badalona", price_estimate=95)
    db.add_job(carlos["id"], "Revisión caldera", scheduled_for=at(12, 0),
               zone="Barcelona", price_estimate=120)
    db.add_job(laura["id"], "Presupuesto reforma baño", scheduled_for=at(17, 0),
               zone="Barcelona")

    # Una factura ya enviada y sin cobrar (para ver los avisos de cobro).
    inv = db.add_invoice(carlos["id"], "Sustitución termo eléctrico", 180)
    db.mark_invoice_sent(
        inv["id"], "F-2026-0001",
        due_date=(today - timedelta(days=2)).isoformat(),
    )
    # La marcamos como emitida hace 12 días para que salga el aviso de retraso.
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE invoices SET issued_at=? WHERE id=?",
            ((today - timedelta(days=12)).isoformat(), inv["id"]),
        )
