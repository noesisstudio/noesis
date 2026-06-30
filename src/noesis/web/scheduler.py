"""Tareas programadas y worker de la cola de WhatsApp.

Los avisos programados son conversaciones iniciadas por Noesis y siempre usan una
plantilla aprobada por Meta. Las respuestas inmediatas al usuario se gestionan en
``whatsapp.py`` como texto libre dentro de la ventana de 24 horas.
"""

from __future__ import annotations

import logging
from datetime import datetime

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


def send_payment_reminders() -> None:
    """Avisa al autónomo de facturas vencidas como máximo una vez por semana."""
    day = f"{datetime.now():%Y-%m-%d}"
    if not db.claim_scheduled_run(f"reminders:{day}"):
        return
    for business in _active_businesses():
        pending_reminder = []
        for invoice in db.overdue_invoices(business["id"]):
            last = invoice.get("last_reminder_at")
            recent = (
                last
                and (datetime.now() - datetime.fromisoformat(last)).days < 7
            )
            if not recent:
                pending_reminder.append(invoice)
        if not pending_reminder:
            continue
        total = sum(invoice["total"] for invoice in pending_reminder)
        lines = [
            f"🔔 Cobros vencidos en {business['name']}: "
            f"{len(pending_reminder)} factura(s), {_eur(total)} por reclamar.\n"
        ]
        for invoice in pending_reminder[:6]:
            who = invoice.get("client_name") or "cliente"
            lines.append(
                f"• {who} — {_eur(invoice['total'])} "
                f"(vencida hace {invoice['days_late']} días). "
                f"Mensaje sugerido: «Hola {who}, te recuerdo la factura "
                f"{invoice.get('number') or ''} de {_eur(invoice['total'])}. "
                "¿La puedes abonar esta semana? Gracias.»"
            )
        if _deliver_template(
            business,
            "\n".join(lines),
            "cobros",
            config.WHATSAPP_TEMPLATE_PAYMENT_ALERT,
            f"reminders:{day}:{business['id']}",
        ):
            for invoice in pending_reminder[:6]:
                db.mark_reminder_sent(invoice["id"], business["id"])
        _send_client_reminders(business, pending_reminder[:6])


def _send_client_reminders(business: dict, invoices: list[dict]) -> None:
    """Envía recordatorios directos por email si hay SMTP configurado."""
    from ..adapters import email as email_adapter

    if not email_adapter.available():
        return
    for invoice in invoices:
        client = (
            db.get_client(invoice.get("client_id"), business["id"])
            if invoice.get("client_id")
            else None
        )
        if not client or not client.get("email"):
            continue
        email_adapter.send_reminder_email(
            client["email"],
            business.get("name", "Tu proveedor"),
            client.get("name", "Cliente"),
            invoice.get("number") or str(invoice["id"]),
            _eur(invoice["total"]),
            invoice.get("days_late") or 0,
        )


def send_weekly_summaries() -> None:
    year, week, _ = datetime.now().isocalendar()
    run_key = f"weekly:{year}-W{week:02d}"
    if not db.claim_scheduled_run(run_key):
        return
    for business in _active_businesses():
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


def process_whatsapp_outbox() -> None:
    """Procesa mensajes vencidos; la BD coordina las réplicas."""
    from . import whatsapp

    whatsapp.process_outbox(limit=25)


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
        process_whatsapp_outbox,
        "interval",
        seconds=15,
        id="whatsapp-outbox",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(run_daily_backup, "cron", hour=3, minute=30, id="backup")
    scheduler.start()
    _scheduler = scheduler
    log.info(
        "Scheduler iniciado (WhatsApp cada 15s, diario 08:00, cobros 09:00, "
        "semanal lun 08:00, backup 03:30)."
    )
    return scheduler
