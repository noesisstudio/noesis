"""Rutas de resumen, analisis, agenda e informes financieros."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from ... import db
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
    return chat.daily_plan(business_id)


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


@router.get("/api/{business_id}/agenda")
def api_agenda(business_id: int, week: bool = False, start: str = "", end: str = ""):
    if start and end:
        return db.jobs_between(start, end, business_id)
    if week:
        today = date.today()
        return db.jobs_between(today.isoformat(),
                               (today + timedelta(days=6)).isoformat(), business_id)
    return db.jobs_for_date(date.today().isoformat(), business_id)




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
