"""Tareas programadas y worker de la cola de WhatsApp.

Los avisos programados son conversaciones iniciadas por Noesis y siempre usan una
plantilla aprobada por Meta. Las respuestas inmediatas al usuario se gestionan en
``whatsapp.py`` como texto libre dentro de la ventana de 24 horas.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from .. import config, db
from ..agent import daily_summary_text
from . import backups

log = logging.getLogger("noesis.alerts")
_scheduler: BackgroundScheduler | None = None


def _deliver_template(
    business: dict,
    text: str,
    kind: str,
    template_name: str,
    idempotency_key: str,
) -> bool:
    """Encola un proactivo con una clave estable para impedir duplicados."""
    from . import whatsapp

    phone = business.get("whatsapp_phone")
    if not phone:
        log.warning("[ALERTA %s] sin teléfono -> %s", kind, business["name"])
        return False
    queued = whatsapp.send_template(
        phone,
        template_name,
        [text],
        business_id=business["id"],
        idempotency_key=idempotency_key,
    )
    log.info(
        "[ALERTA %s] -> %s | encolada=%s", kind, business["name"], queued
    )
    return queued


def _active_businesses() -> list[dict]:
    return [
        business for business in db.list_businesses()
        if business.get("whatsapp_status") == "conectado"
    ]


def send_daily_summaries() -> None:
    day = f"{datetime.now():%Y-%m-%d}"
    if not db.claim_scheduled_run(f"daily:{day}"):
        return
    for business in _active_businesses():
        prefs = db.resolve_whatsapp_reports(business.get("whatsapp_reports"))
        if not prefs["brief_manana"]:
            continue
        _deliver_template(
            business,
            daily_summary_text(business["id"]),
            "diario",
            config.WHATSAPP_TEMPLATE_DAILY_SUMMARY,
            f"daily:{day}:{business['id']}",
        )


def _eur(number) -> str:
    return (
        f"{(number or 0):,.2f} €"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def _payment_reminder_step(
    invoice: dict,
    cadence: list[int],
    point: datetime,
) -> tuple[int, int] | None:
    anchor = invoice.get("due_date") or invoice.get("issued_at")
    if not anchor:
        return None
    try:
        anchor_day = datetime.fromisoformat(str(anchor)).date()
    except ValueError:
        return None
    elapsed = (point.date() - anchor_day).days
    eligible = [step for step in cadence if step <= elapsed]
    return (max(eligible), elapsed) if eligible else None


def send_payment_reminders(now: datetime | None = None) -> int:
    """Encola un recordatorio por factura y escalón, nunca texto libre."""
    from . import whatsapp

    if not whatsapp.is_configured():
        return 0
    point = now or datetime.now()
    day = f"{point:%Y-%m-%d}"
    if not db.claim_scheduled_run(f"payment-reminders:{day}"):
        return 0

    queued = 0
    for business in db.list_businesses():
        if not business.get("payment_reminders_enabled"):
            continue
        cadence = db.payment_reminder_days(business)
        for invoice in db.pending_payments(business["id"]):
            due = _payment_reminder_step(invoice, cadence, point)
            if not due:
                continue
            step, elapsed = due
            idempotency_key = (
                f"payment-reminder:{business['id']}:{invoice['id']}:{step}"
            )
            if db.get_whatsapp_message_by_idempotency_key(
                idempotency_key, business["id"]
            ):
                continue
            client = (
                db.get_client(invoice.get("client_id"), business["id"])
                if invoice.get("client_id")
                else None
            )
            phone = whatsapp.recipient_phone(
                client.get("phone") if client else None
            )
            if not client or not phone:
                continue
            token = db.get_or_create_portal_token(
                business["id"], client["id"]
            )
            if not token:
                continue
            portal_url = f"{config.BASE_URL}/p/{token}"
            try:
                whatsapp.queue_payment_reminder(
                    phone,
                    client.get("name") or "cliente",
                    business.get("name") or "Tu proveedor",
                    invoice.get("number") or str(invoice["id"]),
                    _eur(invoice["total"]),
                    portal_url,
                    business_id=business["id"],
                    idempotency_key=idempotency_key,
                )
            except (db.DatabaseError, ValueError):
                log.exception(
                    "No se pudo encolar el recordatorio de la factura %s.",
                    invoice["id"],
                )
                continue
            db.mark_reminder_sent(invoice["id"], business["id"])
            db.record_product_event(
                business["id"],
                "payment_reminder_queued",
                json.dumps(
                    {
                        "invoice_id": invoice["id"],
                        "step": step,
                        "days_outstanding": elapsed,
                        "remaining": invoice["total"],
                    },
                    separators=(",", ":"),
                ),
            )
            queued += 1
    return queued


def send_daily_closings(now: datetime | None = None) -> int:
    """Cierre del día por WhatsApp: lo hecho, lo facturado, lo cobrado y el
    siguiente paso. Cada negocio elige su hora (17-21) en Ajustes."""
    point = now or datetime.now()
    day = f"{point:%Y-%m-%d}"
    queued = 0
    for business in _active_businesses():
        prefs = db.resolve_whatsapp_reports(business.get("whatsapp_reports"))
        if not prefs["cierre_tarde"] or prefs["hora_tarde"] != point.hour:
            continue
        idempotency_key = f"closing:{day}:{business['id']}"
        if db.get_whatsapp_message_by_idempotency_key(
            idempotency_key, business["id"]
        ):
            continue
        bid = business["id"]
        jobs_today = db.jobs_for_date(day, bid)
        done_jobs = [
            job for job in jobs_today if job.get("status") != "cancelado"
        ]
        invoices_today = [
            invoice for invoice in db.list_invoices(bid)
            if str(invoice.get("issued_at") or "").startswith(day)
        ]
        collected = db.payments_received_on(bid, day)
        lines = [f"🌙 Cierre del día en {business['name']}:"]
        lines.append(f"• Trabajos de hoy: {len(done_jobs)}")
        if invoices_today:
            total = sum(invoice["total"] for invoice in invoices_today)
            lines.append(
                f"• Facturado: {len(invoices_today)} factura(s), {_eur(total)}"
            )
        lines.append(f"• Cobrado hoy: {_eur(collected)}")
        pending = db.pending_payments(bid)
        if pending:
            first = pending[0]
            who = first.get("client_name") or "un cliente"
            lines.append(
                f"➡️ Mañana lo primero: reclamar a {who} "
                f"({_eur(first['total'])} pendiente)."
            )
        else:
            lines.append("➡️ Sin cobros pendientes. Todo al día 💪")
        if _deliver_template(
            business,
            "\n".join(lines),
            "cierre",
            config.WHATSAPP_TEMPLATE_DAILY_CLOSING,
            idempotency_key,
        ):
            queued += 1
    return queued


def send_quarterly_tax_notices(now: datetime | None = None) -> int:
    """Aviso fiscal al cerrar cada trimestre: 303/130 estimados y fecha límite."""
    point = now or datetime.now()
    if point.month not in (1, 4, 7, 10):
        return 0
    previous = point - timedelta(days=10)
    quarter = (previous.month - 1) // 3 + 1
    year = previous.year
    run_key = f"tax-notice:{year}-Q{quarter}"
    if not db.claim_scheduled_run(run_key):
        return 0
    queued = 0
    for business in _active_businesses():
        prefs = db.resolve_whatsapp_reports(business.get("whatsapp_reports"))
        if not prefs["aviso_fiscal"]:
            continue
        try:
            taxes = db.tax_quarter(year, quarter, business["id"])
        except ValueError:
            continue
        month_name = {1: "enero", 4: "abril", 7: "julio", 10: "octubre"}[
            point.month
        ]
        text = (
            f"🧾 Cierre fiscal del {taxes['label']} en {business['name']}:\n"
            f"IVA (modelo 303): {_eur(taxes['iva_resultado'])} · "
            f"IRPF (modelo 130): {_eur(taxes['irpf_pago'])}.\n"
            f"Plazo de presentación: hasta el 20 de {month_name}. "
            "Tienes el detalle en Tesorería."
        )
        if _deliver_template(
            business,
            text,
            "fiscal",
            config.WHATSAPP_TEMPLATE_TAX_NOTICE,
            f"{run_key}:{business['id']}",
        ):
            queued += 1
    return queued


def send_weekly_summaries() -> None:
    year, week, _ = datetime.now().isocalendar()
    run_key = f"weekly:{year}-W{week:02d}"
    if not db.claim_scheduled_run(run_key):
        return
    for business in _active_businesses():
        prefs = db.resolve_whatsapp_reports(business.get("whatsapp_reports"))
        if not prefs["resumen_semanal"]:
            continue
        month = db.month_billing(business_id=business["id"])
        pending = db.pending_payments(business["id"])
        text = (
            f"📊 Resumen semanal de {business['name']}:\n"
            f"Facturado este mes: {month['invoiced']:.2f} € · "
            f"Pendiente de cobro: {month['pending']:.2f} € "
            f"({len(pending)} facturas) · "
            f"Gastos: {month['expenses']:.2f} € · "
            f"Beneficio estimado: {month['estimated_profit']:.2f} €."
        )
        _deliver_template(
            business,
            text,
            "semanal",
            config.WHATSAPP_TEMPLATE_WEEKLY_SUMMARY,
            f"{run_key}:{business['id']}",
        )


def send_gestoria_packages(now: datetime | None = None) -> int:
    """Al cerrar cada período, avisa a la gestoría de que su paquete está listo."""
    from . import gestoria

    point = now or datetime.now()
    if point.day > 5:
        return 0
    notified = 0
    for business in db.list_businesses():
        cadence = business.get("gestoria_cadence") or "off"
        if cadence == "off" or not business.get("gestoria_email"):
            continue
        if cadence == "trimestral" and point.month not in (1, 4, 7, 10):
            continue
        label = gestoria.previous_label(cadence, point.date())
        if not db.claim_scheduled_run(f"gestoria:{business['id']}:{label}"):
            continue
        emailed = gestoria.notify_gestoria(business, label)
        db.record_product_event(
            business["id"],
            "gestoria_package_ready",
            json.dumps({"label": label, "emailed": bool(emailed)},
                       separators=(",", ":")),
        )
        notified += 1
    return notified


def process_whatsapp_outbox() -> None:
    """Procesa mensajes vencidos; la BD coordina las réplicas."""
    from . import whatsapp

    whatsapp.process_outbox(limit=25)


def process_verifactu_outbox(limit: int = 25) -> int:
    """Remite registros vencidos respetando backoff y control de flujo AEAT."""
    from .. import verifactu_client

    if not verifactu_client.is_enabled():
        return 0
    db.enqueue_missing_verifactu_records()
    processed = 0
    for _ in range(max(1, min(int(limit), 1000))):
        now = datetime.now()
        item = db.claim_next_verifactu_submission(
            now=now.isoformat(timespec="seconds"),
            stale_before=(now - timedelta(minutes=5)).isoformat(timespec="seconds"),
        )
        if not item:
            break
        business = db.get_business(item["business_id"])
        record = db.get_invoice_record(item["invoice_id"], item["business_id"])
        if not business or not record:
            db.mark_verifactu_retry(
                item["id"],
                error="No se encuentra el negocio o el registro de facturación.",
                next_attempt_at=(
                    now + timedelta(seconds=config.VERIFACTU_RETRY_MAX_SECONDS)
                ).isoformat(timespec="seconds"),
                updated_at=now.isoformat(timespec="seconds"),
            )
            break
        try:
            result = verifactu_client.submit_records(business, [record])
        except verifactu_client.VerifactuTransportError as exc:
            delay = min(
                config.VERIFACTU_RETRY_MAX_SECONDS,
                config.VERIFACTU_RETRY_BASE_SECONDS
                * (2 ** max(0, int(item["attempts"]) - 1)),
            )
            db.mark_verifactu_retry(
                item["id"],
                error=str(exc),
                next_attempt_at=(
                    now + timedelta(seconds=delay)
                ).isoformat(timespec="seconds"),
                updated_at=now.isoformat(timespec="seconds"),
            )
            log.warning("Remisión Veri*Factu aplazada: %s", exc)
            break
        completed_at = datetime.now().isoformat(timespec="seconds")
        db.mark_verifactu_result(
            item["id"],
            status=result.status,
            csv=result.csv,
            global_status=result.global_status,
            error_code=result.error_code,
            error_description=result.error_description,
            response=result.raw_response,
            wait_seconds=result.wait_seconds,
            completed_at=completed_at,
        )
        processed += 1
        if result.wait_seconds:
            until = (
                datetime.fromisoformat(completed_at)
                + timedelta(seconds=result.wait_seconds)
            ).isoformat(timespec="seconds")
            db.postpone_verifactu_submissions(until, completed_at)
            break
    return processed


def run_daily_backup() -> None:
    if db.claim_scheduled_run(f"backup:{datetime.now():%Y-%m-%d}"):
        backups.run_backup()


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler:
        return _scheduler
    scheduler = BackgroundScheduler(timezone="Europe/Madrid")
    scheduler.add_job(send_daily_summaries, "cron", hour=8, minute=0, id="daily")
    scheduler.add_job(
        send_payment_reminders, "cron", hour=9, minute=0, id="reminders"
    )
    scheduler.add_job(
        send_weekly_summaries,
        "cron",
        day_of_week="mon",
        hour=8,
        minute=0,
        id="weekly",
    )
    scheduler.add_job(
        send_daily_closings,
        "cron",
        hour="17-21",
        minute=5,
        id="closing",
    )
    scheduler.add_job(
        send_quarterly_tax_notices,
        "cron",
        month="1,4,7,10",
        day=1,
        hour=10,
        minute=0,
        id="tax-notice",
    )
    scheduler.add_job(
        send_gestoria_packages,
        "cron",
        day="1-5",
        hour=9,
        minute=30,
        id="gestoria",
    )
    scheduler.add_job(
        process_whatsapp_outbox,
        "interval",
        seconds=15,
        id="whatsapp-outbox",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        process_verifactu_outbox,
        "interval",
        seconds=15,
        id="verifactu-outbox",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(run_daily_backup, "cron", hour=3, minute=30, id="backup")
    scheduler.start()
    _scheduler = scheduler
    log.info(
        "Scheduler iniciado (colas WhatsApp/Veri*Factu cada 15s, diario 08:00, "
        "cobros 09:00, semanal lun 08:00, backup 03:30)."
    )
    return scheduler
