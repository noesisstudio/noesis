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
        and db.subscription_allows_access(business)
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
        if not db.subscription_allows_access(business):
            continue
        if not business.get("payment_reminders_enabled"):
            continue
        permission = db.automation_decision(
            business["id"], "payment_reminders"
        )
        # La cadencia guardada en Ajustes es la regla aprobada por el usuario.
        # En modo "preguntar" o "bloqueado", el scheduler nunca escribe fuera.
        if permission["mode"] != "rules":
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
            db.record_assistant_action(
                business["id"],
                "payment_reminders",
                f"Encolé el aviso de cobro de la factura "
                f"{invoice.get('number') or invoice['id']} según tu cadencia.",
                status="executed",
                target_type="invoice",
                target_id=invoice["id"],
                payload={
                    "step": step,
                    "days_outstanding": elapsed,
                    "idempotency_key": idempotency_key,
                },
                requested_by="system",
                approved_by="regla de cobros",
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
    """Cierre semanal (domingo por la tarde): el estado del negocio en 5 líneas
    para que el lunes empiece sin ruido mental. No hace falta abrir la app."""
    year, week, _ = datetime.now().isocalendar()
    run_key = f"weekly:{year}-W{week:02d}"
    if not db.claim_scheduled_run(run_key):
        return
    for business in _active_businesses():
        prefs = db.resolve_whatsapp_reports(business.get("whatsapp_reports"))
        if not prefs["resumen_semanal"]:
            continue
        bid = business["id"]
        month = db.month_billing(business_id=bid)
        pending = db.pending_payments(bid)
        forecast = db.cash_forecast(bid)
        lines = [f"📊 Tu semana en {business['name']}:"]
        lines.append(
            f"• Facturado este mes: {_eur(month['invoiced'])} · "
            f"cobrado: {_eur(month['collected'])}"
        )
        if pending:
            oldest = pending[0]
            who = oldest.get("client_name") or "un cliente"
            lines.append(
                f"• Te deben {_eur(month['pending'])} en {len(pending)} "
                f"factura(s). La más antigua: {who}, {_eur(oldest['total'])}."
            )
        else:
            lines.append("• Nadie te debe nada. Todo cobrado 💪")
        if forecast["iva_reserva"]:
            lines.append(
                f"• Aparta {_eur(forecast['iva_reserva'])} para el IVA del "
                "trimestre: es de Hacienda, no tuyo."
            )
        lines.append(
            f"• Próximos {forecast['days']} días: si cobras lo pendiente y "
            f"gastas lo habitual, te quedan {_eur(forecast['neto'])}."
        )
        if pending:
            lines.append(
                f"➡️ Acción de la semana: reclama a "
                f"{pending[0].get('client_name') or 'tu cliente'} "
                f"({_eur(pending[0]['total'])})."
            )
        else:
            lines.append(
                "➡️ Acción de la semana: cierra los presupuestos abiertos."
            )
        _deliver_template(
            business,
            "\n".join(lines),
            "semanal",
            config.WHATSAPP_TEMPLATE_WEEKLY_SUMMARY,
            f"{run_key}:{business['id']}",
        )


def send_collection_proposals(now: datetime | None = None) -> int:
    """Cobros en piloto automático: si hay una factura vencida y el negocio no
    tiene recordatorios automáticos, Noesis propone reclamarla por WhatsApp y
    espera un SÍ del dueño antes de escribir al cliente."""
    from . import whatsapp

    if not whatsapp.is_configured():
        return 0
    point = now or datetime.now()
    day = f"{point:%Y-%m-%d}"
    if not db.claim_scheduled_run(f"collect-proposal:{day}"):
        return 0
    queued = 0
    for business in _active_businesses():
        if business.get("payment_reminders_enabled"):
            continue  # ya se reclama solo, sin preguntar
        phone = business.get("whatsapp_phone")
        if not phone:
            continue
        overdue = [
            invoice for invoice in db.pending_payments(business["id"])
            if (invoice.get("days_outstanding") or 0) >= 7
            and invoice.get("client_id")
        ]
        if not overdue:
            continue
        top = overdue[0]
        idempotency_key = (
            f"collect-proposal:{business['id']}:{top['id']}"
        )
        if db.get_whatsapp_message_by_idempotency_key(
            idempotency_key, business["id"]
        ):
            continue
        client = db.get_client(top["client_id"], business["id"])
        if not client:
            continue
        number = top.get("number") or str(top["id"])
        text = (
            f"💶 {client.get('name') or 'Un cliente'} te debe "
            f"{_eur(top['total'])} (factura {number}, "
            f"{top['days_outstanding']} días). ¿Le mando el recordatorio "
            "con su enlace de pago? Responde SÍ o NO."
        )
        # La propuesta caduca en 12 h; si el dueño responde SÍ se ejecuta.
        db.set_pending_action(
            business["id"], phone, "reclamar",
            {"invoice_id": top["id"]}, ttl_minutes=720,
        )
        if _deliver_template(
            business,
            text,
            "cobro",
            config.WHATSAPP_TEMPLATE_PAYMENT_ALERT,
            idempotency_key,
        ):
            queued += 1
    return queued


def send_founder_digest(now: datetime | None = None) -> bool:
    """Agente CFO interno: cada lunes, los departamentos del centro de mando
    informan a dirección por email. Cifras deterministas, coste cero."""
    from ..adapters import email as email_adapter

    point = now or datetime.now()
    year, week, _ = point.isocalendar()
    if not db.claim_scheduled_run(f"founder-digest:{year}-W{week:02d}"):
        return False
    admins = db.list_admin_emails()
    if not admins:
        return True
    data = db.admin_overview()
    reports = data["dept_reports"]
    body = "\n".join([
        f"Parte semanal de Noesis · semana {week:02d}/{year}",
        "",
        f"💰 Finanzas: {reports['finanzas']}",
        f"📈 Crecimiento: {reports['crecimiento']}",
        f"📣 Marketing: {reports['marketing']}",
        f"⚙️ Operaciones: {reports['operaciones']}",
        f"👥 Clientes: {reports['clientes']}",
        "",
        f"KPIs: {data['total']} cuenta(s) · MRR {data['mrr']} € · "
        f"coste IA {data['finanzas']['ai_cost_eur']} € · "
        f"{len(data['alerts'])} alarma(s).",
        "",
        f"Detalle completo: {config.BASE_URL}/admin",
        "— Generado automáticamente por el centro de mando.",
    ])
    subject = f"Noesis · parte semanal W{week:02d}: MRR {data['mrr']} €"
    for address in admins:
        email_adapter.send_email(address, subject, body)
    log.info("Parte semanal del fundador enviado a %d dirección(es).",
             len(admins))
    return True


def send_gestoria_packages(now: datetime | None = None) -> int:
    """Al cerrar cada período, avisa a la gestoría de que su paquete está listo."""
    from . import gestoria

    point = now or datetime.now()
    if point.day > 5:
        return 0
    notified = 0
    for business in db.list_businesses():
        if not db.subscription_allows_access(business):
            continue
        cadence = business.get("gestoria_cadence") or "off"
        if cadence == "off" or not business.get("gestoria_email"):
            continue
        permission = db.automation_decision(business["id"], "send_gestoria")
        if permission["mode"] != "rules":
            continue
        if cadence == "trimestral" and point.month not in (1, 4, 7, 10):
            continue
        label = gestoria.previous_label(cadence, point.date())
        if not db.claim_scheduled_run(f"gestoria:{business['id']}:{label}"):
            continue
        package = gestoria.build_package(business["id"], label)
        if not package:
            continue
        _data, meta = package
        emailed = gestoria.notify_gestoria(business, label)
        if emailed:
            db.mark_gestoria_delivery(business["id"], label, "notified")
        db.record_assistant_action(
            business["id"],
            "send_gestoria",
            f"Preparé el paquete {label} v{meta['version']} según tu cadencia"
            + (" y avisé a tu gestoría." if emailed else "."),
            status="executed" if emailed else "failed",
            target_type="gestoria_delivery",
            payload={"label": label, "version": meta["version"],
                     "emailed": bool(emailed)},
            requested_by="system",
            approved_by="cadencia de gestoría",
            error=None if emailed else "No se pudo enviar el aviso por email.",
        )
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
        if not db.subscription_allows_access(business):
            db.mark_verifactu_retry(
                item["id"],
                error="Suscripción inactiva: remisión pausada.",
                next_attempt_at=(
                    now + timedelta(seconds=config.VERIFACTU_RETRY_MAX_SECONDS)
                ).isoformat(timespec="seconds"),
                updated_at=now.isoformat(timespec="seconds"),
            )
            continue
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
        day_of_week="sun",
        hour=18,
        minute=0,
        id="weekly",
    )
    scheduler.add_job(
        send_collection_proposals,
        "cron",
        hour=10,
        minute=0,
        id="collect-proposals",
    )
    scheduler.add_job(
        send_founder_digest,
        "cron",
        day_of_week="mon",
        hour=9,
        minute=0,
        id="founder-digest",
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
