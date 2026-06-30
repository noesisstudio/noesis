"""Tareas programadas de Noesis.

Se envían por el WhatsApp de Noesis al teléfono del autónomo (un solo canal). Si no
hay token de WhatsApp configurado, `whatsapp.send` registra en el log.

  - Resumen diario:        cada día a las 08:00
  - Recordatorios de cobro: cada día a las 09:00 (facturas vencidas)
  - Resumen semanal:       lunes a las 08:00
  - Copia de seguridad:    cada día a las 03:30
"""

from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from .. import db
from ..agent import daily_summary_text
from . import backups

log = logging.getLogger("noesis.alerts")
_scheduler: BackgroundScheduler | None = None


def _deliver(business: dict, text: str, kind: str) -> bool:
    # Envía por el WhatsApp de Noesis al teléfono del autónomo (un solo canal para
    # todo: comandos, facturas y alertas). Si no hay token, whatsapp.send hace log.
    from . import whatsapp
    phone = business.get("whatsapp_phone")
    if phone:
        sent = whatsapp.send(phone, text)
        log.info("[ALERTA %s] -> %s | enviada=%s", kind, business["name"], sent)
        return sent
    log.warning("[ALERTA %s] sin teléfono -> %s", kind, business["name"])
    return False


def _active_businesses() -> list[dict]:
    return [b for b in db.list_businesses() if b.get("whatsapp_status") == "conectado"]


def send_daily_summaries() -> None:
    if not db.claim_scheduled_run(f"daily:{datetime.now():%Y-%m-%d}"):
        return
    for biz in _active_businesses():
        _deliver(biz, daily_summary_text(biz["id"]), "diario")


def _eur(n) -> str:
    return f"{(n or 0):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def send_payment_reminders() -> None:
    """Avisa al autónomo de las facturas vencidas, con un texto listo para reenviar
    a cada cliente. No reclama más de una vez por semana la misma factura."""
    if not db.claim_scheduled_run(f"reminders:{datetime.now():%Y-%m-%d}"):
        return
    for biz in _active_businesses():
        overdue = db.overdue_invoices(biz["id"])
        pending_reminder = []
        for inv in overdue:
            last = inv.get("last_reminder_at")
            recent = last and (datetime.now() - datetime.fromisoformat(last)).days < 7
            if not recent:
                pending_reminder.append(inv)
        if not pending_reminder:
            continue
        total = sum(i["total"] for i in pending_reminder)
        lines = [f"🔔 Cobros vencidos en {biz['name']}: "
                 f"{len(pending_reminder)} factura(s), {_eur(total)} por reclamar.\n"]
        for inv in pending_reminder[:6]:
            who = inv.get("client_name") or "cliente"
            lines.append(
                f"• {who} — {_eur(inv['total'])} (vencida hace {inv['days_late']} días). "
                f"Mensaje sugerido: «Hola {who}, te recuerdo la factura "
                f"{inv.get('number') or ''} de {_eur(inv['total'])}. ¿La puedes abonar "
                f"esta semana? Gracias.»")
        if _deliver(biz, "\n".join(lines), "cobros"):
            for inv in pending_reminder[:6]:
                db.mark_reminder_sent(inv["id"], biz["id"])
        # Enviar también recordatorio por email al cliente final (si tiene email).
        _send_client_reminders(biz, pending_reminder[:6])


def _send_client_reminders(biz: dict, invoices: list[dict]) -> None:
    """Envía recordatorios directos a los clientes finales por email (si disponible)."""
    from ..adapters import email as email_adapter
    if not email_adapter.available():
        return
    for inv in invoices:
        client = db.get_client(inv.get("client_id"), biz["id"]) if inv.get("client_id") else None
        if not client or not client.get("email"):
            continue
        email_adapter.send_reminder_email(
            client["email"], biz.get("name", "Tu proveedor"),
            client.get("name", "Cliente"),
            inv.get("number") or str(inv["id"]),
            _eur(inv["total"]),
            inv.get("days_late") or 0)


def send_weekly_summaries() -> None:
    year, week, _ = datetime.now().isocalendar()
    if not db.claim_scheduled_run(f"weekly:{year}-W{week:02d}"):
        return
    for biz in _active_businesses():
        m = db.month_billing(business_id=biz["id"])
        pend = db.pending_payments(biz["id"])
        text = (f"📊 Resumen semanal de {biz['name']}:\n"
                f"Facturado este mes: {m['invoiced']:.2f} € · "
                f"Pendiente de cobro: {m['pending']:.2f} € ({len(pend)} facturas) · "
                f"Gastos: {m['expenses']:.2f} € · "
                f"Beneficio estimado: {m['estimated_profit']:.2f} €.")
        _deliver(biz, text, "semanal")


def run_daily_backup() -> None:
    if db.claim_scheduled_run(f"backup:{datetime.now():%Y-%m-%d}"):
        backups.run_backup()


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler:
        return _scheduler
    sched = BackgroundScheduler(timezone="Europe/Madrid")
    sched.add_job(send_daily_summaries, "cron", hour=8, minute=0, id="daily")
    sched.add_job(send_payment_reminders, "cron", hour=9, minute=0, id="reminders")
    sched.add_job(send_weekly_summaries, "cron", day_of_week="mon", hour=8,
                  minute=0, id="weekly")
    sched.add_job(run_daily_backup, "cron", hour=3, minute=30, id="backup")
    sched.start()
    _scheduler = sched
    log.info("Scheduler iniciado (diario 08:00, cobros 09:00, semanal lun 08:00, "
             "backup 03:30).")
    return sched
