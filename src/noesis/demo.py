"""Datos de demostración para que el prototipo arranque con algo que mirar."""

from datetime import date, datetime, timedelta

from . import db


def seed(*, reset: bool = True) -> int:
    """Carga clientes, trabajos de hoy y una factura pendiente de ejemplo."""
    if reset:
        db.reset_db()
    business = db.create_business(
        "Fontanería Demo", "demo@bynoesis.com", "Fontanería"
    )
    business_id = business["id"]
    db.update_fiscal(
        business_id, name="Fontanería Demo", nif="12345678Z",
        address="Calle Principal 1, Barcelona",
    )

    marta = db.add_client(
        "Marta García", phone="+34600111222", zone="Badalona",
        nif="11111111H", address="Calle Marina 10, Badalona",
        business_id=business_id,
    )
    carlos = db.add_client(
        "Carlos Ruiz", phone="+34600333444", zone="Barcelona",
        nif="22222222J", address="Calle Aragón 20, Barcelona",
        business_id=business_id,
    )
    laura = db.add_client(
        "Laura Soler", phone="+34600555666", zone="Barcelona",
        nif="33333333P", address="Calle Mallorca 30, Barcelona",
        business_id=business_id,
    )

    today = date.today()
    at = lambda h, m=0: datetime(today.year, today.month, today.day, h, m).isoformat(timespec="minutes")

    db.add_job(marta["id"], "Cambio de grifo cocina", scheduled_for=at(9, 30),
               zone="Badalona", price_estimate=95, business_id=business_id)
    db.add_job(carlos["id"], "Revisión caldera", scheduled_for=at(12, 0),
               zone="Barcelona", price_estimate=120, business_id=business_id)
    db.add_job(laura["id"], "Presupuesto reforma baño", scheduled_for=at(17, 0),
               zone="Barcelona", business_id=business_id)

    # Una factura ya enviada y sin cobrar (para ver los avisos de cobro).
    inv = db.add_invoice(
        carlos["id"], "Sustitución termo eléctrico", 180,
        business_id=business_id,
    )
    db.issue_invoice(inv["id"], business_id)
    # La marcamos como emitida hace 12 días para que salga el aviso de retraso.
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE invoices SET issued_at=?, due_date=? WHERE id=?",
            (
                (today - timedelta(days=12)).isoformat(),
                (today - timedelta(days=2)).isoformat(),
                inv["id"],
            ),
        )
    return business_id
