"""Un vencimiento usa el mismo motor de creación/emisión, con commit exterior."""

import json

from .. import db
from . import invoices, readers
from .boundary import run


def _mutate_cycle(conn, recurring_id, business_id, scheduled_for, *, today=None, draft_only=False):
    from noesis import config
    draft_only = draft_only or config.FINANCIAL_CORE_ENABLED
    today = today or db.date.today()
    lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
    schedule = conn.execute(
        "SELECT * FROM recurring_invoices WHERE business_id=? AND id=?" + lock,
        (business_id, recurring_id),
    ).fetchone()
    business = readers.get_business(conn, business_id)
    if (
        not schedule
        or schedule["status"] != "active"
        or schedule["next_run_on"] != scheduled_for
        or scheduled_for > today.isoformat()
        or not business
        or not db.subscription_allows_access(business)
    ):
        return None
    now = db._now()
    run_row = conn.execute(
        "INSERT INTO recurring_invoice_runs (business_id,recurring_id,scheduled_for,status,created_at) "
        "VALUES (?,?,?,'processing',?) ON CONFLICT (business_id,recurring_id,scheduled_for) "
        "DO NOTHING RETURNING id",
        (business_id, recurring_id, scheduled_for, now),
    ).fetchone()
    if not run_row:
        stale = (db.datetime.now() - db.timedelta(minutes=10)).isoformat(timespec="seconds")
        run_row = conn.execute(
            "UPDATE recurring_invoice_runs SET created_at=?,error=NULL,status='processing' "
            "WHERE business_id=? AND recurring_id=? AND scheduled_for=? AND invoice_id IS NULL "
            "AND (status='error' OR created_at<=?) RETURNING id",
            (now, business_id, recurring_id, scheduled_for, stale),
        ).fetchone()
    if not run_row:
        return None
    # Las plantillas históricas contienen números JSON legacy, no dinero exacto.
    lines = json.loads(schedule["lines_json"], parse_float=db.Decimal)
    invoice = invoices._mutate_add_invoice(
        conn,
        schedule["client_id"],
        lines[0]["description"],
        None,
        business_id=business_id,
        lines=lines,
        irpf_rate=schedule["irpf_rate"],
        invoice_type=schedule["invoice_type"],
        series_id=schedule.get("series_id"),
        operation_date=scheduled_for,
        notes=schedule.get("notes"),
        payment_method=schedule.get("payment_method"),
    )
    if schedule.get("auto_issue") and not draft_only:
        invoice = invoices._mutate_issue_invoice(conn, invoice["id"], business_id)
    next_day = db._advance_recurring_day(
        db.date.fromisoformat(scheduled_for), schedule["cadence"], int(schedule["interval_count"])
    )
    end = db.date.fromisoformat(schedule["ends_on"]) if schedule.get("ends_on") else None
    status = "ended" if end and next_day > end else "active"
    completed_at = db._now()
    conn.execute(
        "UPDATE recurring_invoice_runs SET invoice_id=?,status='completed',completed_at=? "
        "WHERE id=? AND business_id=?",
        (invoice["id"], completed_at, run_row["id"], business_id),
    )
    if draft_only:
        from noesis.financial_channels.recurring import template_hash
        exact_schedule = conn.execute_exact('SELECT * FROM recurring_invoices WHERE business_id=? AND id=?',
                                            (business_id,recurring_id)).fetchone()
        conn.execute('UPDATE recurring_invoice_runs SET financial_template_hash=? WHERE id=? AND business_id=?',
                     (template_hash(exact_schedule),run_row['id'],business_id))
    conn.execute(
        "UPDATE recurring_invoices SET next_run_on=?,status=?,last_generated_at=?,updated_at=? "
        "WHERE id=? AND business_id=?",
        (next_day.isoformat(), status, completed_at, completed_at, recurring_id, business_id),
    )
    return invoice


def generate_cycle(borrowed, recurring_id, business_id, scheduled_for, *, today=None, legacy=False, draft_only=False):
    return run(
        _mutate_cycle,
        borrowed,
        (recurring_id, business_id, scheduled_for),
        {"today": today, "draft_only": draft_only},
        kind="invoice",
        legacy=legacy,
    )
