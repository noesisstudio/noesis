"""Vencimientos en modo borrador + autorización humana de cada emisión."""

from datetime import date
from noesis import db
from noesis.core.persistence import FinancialSession
from noesis.financial_operations.contracts import EntryIdentity, Principal, StateError
from noesis.invoice_capture.service import fingerprint
from .service import ChannelContext, FinancialChannels, checkpoint


def template_hash(schedule):
    excluded = {"next_run_on", "last_generated_at", "updated_at", "status"}
    return fingerprint({k: v for k, v in schedule.items() if k not in excluded})


def validate_occurrence(session, bid, context):
    schedule = session.borrowed_connection.execute_exact(
        "SELECT * FROM recurring_invoices WHERE business_id=? AND id=?"
        + (" FOR SHARE" if session.dialect == "postgres" else ""),
        (bid, context["schedule_id"]),
    ).fetchone()
    run = session.execute(
        "SELECT * FROM recurring_invoice_runs WHERE business_id=? AND recurring_id=? AND scheduled_for=?",
        (bid, context["schedule_id"], context["scheduled_for"]),
    ).fetchone()
    if (
        not schedule
        or schedule["status"] != "active"
        or template_hash(schedule) != context["template_hash"]
        or not run
        or run["invoice_id"] != context["invoice_id"]
        or run["status"] != "completed"
        or run["financial_template_hash"] != context["template_hash"]
    ):
        raise StateError("La recurrencia ha cambiado o no está activa; se necesita otra revisión.")


def occurrence_for_invoice(bid, invoice_id, *, session=None, validate=True):
    if session is None:
        with db.get_conn() as conn:
            from noesis.core.locks import lock_business
            borrowed = FinancialSession(conn)
            lock_business(borrowed, bid)
            return occurrence_for_invoice(bid, invoice_id, session=borrowed, validate=validate)
    run = session.execute(
        "SELECT * FROM recurring_invoice_runs WHERE business_id=? AND invoice_id=?",
        (bid, invoice_id),
    ).fetchone()
    if not run:
        return None
    if not run["financial_template_hash"]:
        raise StateError(
            "Vencimiento legacy sin contexto durable; no inferir autoridad ni reconstruir historia."
        )
    context = {
        "schedule_id": run["recurring_id"],
        "scheduled_for": str(run["scheduled_for"])[:10],
        "invoice_id": invoice_id,
        "template_hash": run["financial_template_hash"],
    }
    if validate:
        validate_occurrence(session, bid, context)
    return EntryIdentity.recurring(
        run["recurring_id"], date.fromisoformat(context["scheduled_for"])
    ), context


def process_due(*, today=None, limit=100):
    from noesis.financial_writers import recurring

    from noesis.financial_history.fence import available_predicate, HistoricalFenceActive
    today = today or date.today()
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT r.* FROM recurring_invoices r WHERE status='active' AND next_run_on<=? AND "
            + available_predicate(conn, "r.business_id") + " "
            "ORDER BY next_run_on,id LIMIT ?",
            (today.isoformat(), max(1, min(int(limit), 500))),
        ).fetchall()
    result = []
    for row in rows:
        checkpoint("recurring_before_prepare")
        try:
            with db.get_conn() as conn:
                conn.execute("BEGIN IMMEDIATE")
                generated = recurring.generate_cycle(
                    conn,
                    row["id"],
                    row["business_id"],
                    str(row["next_run_on"])[:10],
                    today=today,
                    legacy=True,
                    draft_only=True,
                )
        except HistoricalFenceActive:
            continue
        if generated.legacy is not None:
            result.append(generated.legacy_value())
        checkpoint("recurring_draft_committed")
    # Recuperación tras commit del borrador, aunque el next_run ya haya avanzado.
    with db.get_conn() as conn:
        pending = conn.execute(
            "SELECT r.business_id,r.invoice_id,b.owner_email FROM recurring_invoice_runs r "
            "JOIN businesses b ON b.id=r.business_id JOIN invoices i ON i.id=r.invoice_id AND i.business_id=r.business_id "
            "WHERE r.status='completed' AND r.financial_template_hash IS NOT NULL AND i.status='borrador' AND "
            + available_predicate(conn, "r.business_id") + " ORDER BY r.id LIMIT ?",
            (max(1, min(int(limit), 500)),),
        ).fetchall()
    for row in pending:
        user = db.get_user_by_email(row["owner_email"]) if row["owner_email"] else None
        if not user or user["business_id"] != row["business_id"] or not user["is_active"]:
            continue  # Borrador sin propietario autenticable: ninguna autoridad inventada.
        try:
            identity, context = occurrence_for_invoice(row["business_id"], row["invoice_id"])
        except StateError:
            db.log.warning("Vencimiento %s bloqueado por cambio de recurrencia.", row["invoice_id"])
            continue
        principal = Principal(user["id"], user["session_version"])
        ctx = ChannelContext(
            row["business_id"], principal, identity, f"web:{user['id']}:{user['session_version']}"
        )
        FinancialChannels(ctx).propose(
            {"command": "invoice.issue", "target_id": row["invoice_id"], "fields": {}},
            recurring_context=context,
        )
    return result
