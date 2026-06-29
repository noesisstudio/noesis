"""Alertas programadas: resumen diario y semanal (sin ser pesado).

Hoy escriben en el log (y quedan listas para enviarse por WhatsApp). Cuando
conectemos Meta Cloud API, se cambia `_deliver` por el envío real.

  - Resumen diario:  cada día a las 08:00
  - Resumen semanal: lunes a las 08:00
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .. import db
from ..agent import daily_summary_text

log = logging.getLogger("noesis.alerts")
_scheduler: BackgroundScheduler | None = None


def _deliver(business: dict, text: str, kind: str) -> None:
    # Envía por el WhatsApp de Noesis al teléfono del autónomo (un solo canal para
    # todo: comandos, facturas y alertas). Si no hay token, whatsapp.send hace log.
    from . import whatsapp
    phone = business.get("whatsapp_phone")
    if phone:
        whatsapp.send(phone, text)
    log.info("[ALERTA %s] -> %s", kind, business["name"])


def _active_businesses() -> list[dict]:
    return [b for b in db.list_businesses() if b.get("whatsapp_status") == "conectado"]


def send_daily_summaries() -> None:
    for biz in _active_businesses():
        _deliver(biz, daily_summary_text(biz["id"]), "diario")


def send_weekly_summaries() -> None:
    for biz in _active_businesses():
        m = db.month_billing(business_id=biz["id"])
        pend = db.pending_payments(biz["id"])
        text = (f"📊 Resumen semanal de {biz['name']}:\n"
                f"Facturado este mes: {m['invoiced']:.2f} € · "
                f"Pendiente de cobro: {m['pending']:.2f} € ({len(pend)} facturas) · "
                f"Gastos: {m['expenses']:.2f} € · "
                f"Beneficio estimado: {m['estimated_profit']:.2f} €.")
        _deliver(biz, text, "semanal")


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler:
        return _scheduler
    sched = BackgroundScheduler(timezone="Europe/Madrid")
    sched.add_job(send_daily_summaries, "cron", hour=8, minute=0, id="daily")
    sched.add_job(send_weekly_summaries, "cron", day_of_week="mon", hour=8,
                  minute=0, id="weekly")
    sched.start()
    _scheduler = sched
    log.info("Scheduler de alertas iniciado (diario 08:00, semanal lun 08:00).")
    return sched
