"""Rutas de resumen, analisis, agenda e informes financieros."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, Response

from ... import banking, db
from .. import chat, reports
from ..deps import _read_json

router = APIRouter()

@router.get("/api/{business_id}/summary")
def api_summary(business_id: int):
    m = db.month_billing(business_id=business_id)
    pend = db.pending_payments(business_id)
    today = date.today().isoformat()
    return {**m,
            "clients": len(db.list_clients(business_id)),
            "jobs_today": len(db.jobs_for_date(today, business_id)),
            "pending_count": len(pend),
            "pending_total": round(sum(p["total"] for p in pend), 2)}


@router.get("/api/{business_id}/activation")
def api_activation(business_id: int):
    return db.activation_snapshot(business_id)


@router.get("/api/{business_id}/series")
def api_series(business_id: int):
    return db.monthly_series(business_id)


@router.get("/api/{business_id}/plan")
def api_plan(business_id: int):
    # Plan diario del copiloto (mismo cerebro que el asistente), para el dashboard.
    # En modo consulta lo calcula sin escribir recomendaciones nuevas en el ledger.
    can_record = db.subscription_allows_access(db.get_business(business_id))
    return chat.daily_plan(business_id, record=can_record)


@router.get("/api/{business_id}/recommendations")
def api_recommendations(business_id: int):
    # Ledger del copiloto: histórico de consejos y conteo por estado.
    return {"items": db.list_recommendations(business_id),
            "stats": db.recommendation_stats(business_id)}


@router.post("/api/{business_id}/recommendations/{rec_id}/status")
async def api_recommendation_status(business_id: int, rec_id: int, request: Request):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    try:
        rec = db.set_recommendation_status(rec_id, business_id, body.get("status"))
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if rec is None:
        return JSONResponse({"error": "Recomendación no encontrada."}, status_code=404)
    return rec


@router.post("/api/{business_id}/panel-layout")
async def api_panel_layout(business_id: int, request: Request):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    order = body.get("order")
    hidden = body.get("hidden")
    if not isinstance(order, list) or not isinstance(hidden, list):
        return JSONResponse({"error": "Formato de panel no válido."}, status_code=400)
    db.update_panel_layout(business_id, order, hidden)
    return {"ok": True}


@router.get("/api/{business_id}/analysis")
def api_analysis(business_id: int):
    return {**db.financial_analysis(business_id),
            "series": db.monthly_series(business_id, months=12)}


@router.get("/api/{business_id}/forecast")
def api_forecast(business_id: int, days: int = 30):
    """Previsión de caja: entra − sale − IVA a apartar, a N días vista."""
    return db.cash_forecast(business_id, days=days)


@router.get("/api/{business_id}/search")
def api_search(business_id: int, q: str = ""):
    """Buscador global: clientes, facturas, presupuestos y trabajos."""
    return db.global_search(business_id, q)




@router.delete("/api/{business_id}/jobs/{job_id}")
def api_delete_job(business_id: int, job_id: int):
    try:
        db.delete_job(job_id, business_id)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)
    return {"ok": True}


@router.get("/api/{business_id}/costs/breakdown")
def api_costs_breakdown(business_id: int):
    return db.expenses_by_category(business_id)


@router.get("/api/{business_id}/income/by-client")
def api_income_by_client(business_id: int):
    return db.income_by_client(business_id)


@router.get("/api/{business_id}/pending")
def api_pending(business_id: int):
    return db.pending_payments(business_id)


@router.post("/b/{business_id}/bank-import")
async def import_bank_statement(
    business_id: int, file: UploadFile = File(...)
):
    filename = (file.filename or "").lower()
    if not filename.endswith((".csv", ".txt")):
        return RedirectResponse(
            f"/b/{business_id}/cobros?bank_error=format#bank-reconciliation",
            status_code=303,
        )
    content = await file.read(5 * 1024 * 1024 + 1)
    await file.close()
    if len(content) > 5 * 1024 * 1024:
        return RedirectResponse(
            f"/b/{business_id}/cobros?bank_error=size#bank-reconciliation",
            status_code=303,
        )
    try:
        result = banking.import_csv(business_id, content)
    except ValueError:
        return RedirectResponse(
            f"/b/{business_id}/cobros?bank_error=content#bank-reconciliation",
            status_code=303,
        )
    db.record_product_event(
        business_id, "bank_statement_imported",
        json.dumps(result, separators=(",", ":")),
    )
    return RedirectResponse(
        f"/b/{business_id}/cobros?bank_imported={result['created']}"
        f"&bank_duplicates={result['duplicates']}#bank-reconciliation",
        status_code=303,
    )


@router.post("/api/{business_id}/bank-transactions/{transaction_id}/confirm")
def confirm_bank_match(business_id: int, transaction_id: int):
    try:
        transaction = db.confirm_bank_transaction(transaction_id, business_id)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    db.record_product_event(
        business_id, "bank_match_confirmed", f"transaction_id={transaction_id}"
    )
    return {"transaction": transaction}


@router.post("/api/{business_id}/bank-transactions/{transaction_id}/ignore")
def ignore_bank_match(business_id: int, transaction_id: int):
    transaction = db.ignore_bank_transaction(transaction_id, business_id)
    if not transaction:
        return JSONResponse({"error": "Movimiento no encontrado."}, status_code=404)
    db.record_product_event(
        business_id, "bank_match_ignored", f"transaction_id={transaction_id}"
    )
    return {"transaction": transaction}


@router.get("/api/{business_id}/agenda")
def api_agenda(business_id: int, week: bool = False, start: str = "", end: str = ""):
    if start and end:
        return db.jobs_between(start, end, business_id)
    if week:
        today = date.today()
        return db.jobs_between(today.isoformat(),
                               (today + timedelta(days=6)).isoformat(), business_id)
    return db.jobs_for_date(date.today().isoformat(), business_id)


def _ics_escape(value: object) -> str:
    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def _ics_event_dates(value: str) -> tuple[str, str]:
    """Devuelve líneas DTSTART/DTEND usando la hora local del negocio."""
    raw = (value or "").strip()
    if len(raw) == 10:
        start = date.fromisoformat(raw)
        return (
            f"DTSTART;VALUE=DATE:{start:%Y%m%d}",
            f"DTEND;VALUE=DATE:{start + timedelta(days=1):%Y%m%d}",
        )
    try:
        start_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        start_at = datetime.combine(date.today(), datetime.min.time())
    if start_at.tzinfo is not None:
        start_at = start_at.astimezone().replace(tzinfo=None)
    end_at = start_at + timedelta(hours=1)
    return (
        f"DTSTART;TZID=Europe/Madrid:{start_at:%Y%m%dT%H%M%S}",
        f"DTEND;TZID=Europe/Madrid:{end_at:%Y%m%dT%H%M%S}",
    )


def _calendar_ics(business: dict) -> str:
    today = date.today()
    jobs = db.jobs_between(
        (today - timedelta(days=365)).isoformat(),
        (today + timedelta(days=730)).isoformat(),
        business["id"],
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Noesis//Agenda de trabajos//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_ics_escape('Noesis · ' + business['name'])}",
        "X-WR-TIMEZONE:Europe/Madrid",
    ]
    for job in jobs:
        start_line, end_line = _ics_event_dates(job.get("scheduled_for") or "")
        summary = job.get("client_name") or job.get("description") or "Trabajo"
        details = [job.get("description")]
        if job.get("worker_name"):
            details.append(f"Asignado a {job['worker_name']}")
        if job.get("project_name"):
            details.append(f"Proyecto: {job['project_name']}")
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:job-{job['id']}@bynoesis.com",
            f"DTSTAMP:{stamp}",
            start_line,
            end_line,
            f"SUMMARY:{_ics_escape(summary)}",
            f"DESCRIPTION:{_ics_escape(' · '.join(str(x) for x in details if x))}",
        ])
        location = job.get("project_location")
        if location:
            lines.append(f"LOCATION:{_ics_escape(location)}")
        if job.get("status") == "cancelado":
            lines.append("STATUS:CANCELLED")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


@router.get("/cal/{token}.ics")
def public_calendar_feed(token: str):
    business = db.get_business_by_calendar_token(token)
    if not business:
        return Response("Calendario no encontrado.", status_code=404)
    return Response(
        _calendar_ics(business),
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'inline; filename="agenda-noesis.ics"',
            "Cache-Control": "private, max-age=300",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )


@router.post("/b/{business_id}/calendar-feed")
def update_calendar_feed(business_id: int, action: str = Form("create")):
    if action == "rotate":
        db.rotate_calendar_token(business_id)
        event = "calendar_feed_rotated"
    else:
        db.get_or_create_calendar_token(business_id)
        event = "calendar_feed_created"
    db.record_product_event(business_id, event)
    return RedirectResponse(f"/b/{business_id}/agenda#calendar-feed", status_code=303)




# ============================================================= INFORMES ===== #
def _csv_response(text: str, filename: str) -> Response:
    return Response(content="﻿" + text,
                    media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/api/{business_id}/reports/costs.csv")
def report_costs(business_id: int):
    return _csv_response(reports.costs_csv(business_id), "noesis_costes.csv")


@router.get("/api/{business_id}/reports/invoices.csv")
def report_invoices(business_id: int):
    return _csv_response(reports.invoices_csv(business_id), "noesis_facturas.csv")




@router.get("/api/{business_id}/pnl")
def api_pnl(business_id: int, year: int = 0):
    return db.profit_and_loss(business_id, year=year or None)


# ---------------------------------------------------------------- Idioma ---
