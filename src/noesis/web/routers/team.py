"""Rutas de equipo y fichaje interno."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, Response

from ... import config, db
from .. import auth, whatsapp
from ..deps import _read_json

router = APIRouter()

def _worker_json(worker: dict) -> dict:
    return {
        key: value for key, value in worker.items()
        if key not in {"pin_hash", "phone_norm"}
    }


@router.get("/api/{business_id}/workers")
def api_workers(business_id: int):
    return db.clockins_today(business_id)


@router.get("/api/{business_id}/workers/productivity")
def api_workers_productivity(business_id: int, days: int = 30):
    """Rendimiento por persona (trabajos, ventas, horas) para el dueño."""
    return db.team_productivity(business_id, days=days)


@router.get("/api/{business_id}/workers/{worker_id}/clockins")
def api_worker_clockins(
    business_id: int,
    worker_id: int,
    from_: str = Query("", alias="from"),
    to: str = "",
):
    if not db.get_worker(worker_id, business_id):
        return JSONResponse({"error": "Trabajador no encontrado."}, status_code=404)
    try:
        start = (
            date.fromisoformat(from_).isoformat()
            if from_ else (date.today() - timedelta(days=29)).isoformat()
        )
        end = date.fromisoformat(to).isoformat() if to else date.today().isoformat()
    except ValueError:
        return JSONResponse({"error": "El rango de fechas no es válido."}, status_code=400)
    return {
        "items": db.worker_clockin_history(
            worker_id, business_id, from_day=start, to_day=end
        ),
        "integrity": db.verify_clockin_chain(business_id, worker_id),
    }


@router.post("/api/{business_id}/workers")
async def api_create_worker(business_id: int, request: Request):
    try:
        body = await _read_json(request)
        worker = db.create_worker(
            business_id,
            body.get("name"),
            phone=body.get("phone"),
            color=body.get("color"),
            pin=body.get("pin"),
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return _worker_json(worker)


@router.post("/api/{business_id}/workers/{worker_id}")
async def api_update_worker(
    business_id: int, worker_id: int, request: Request
):
    try:
        body = await _read_json(request)
        worker = db.update_worker(
            worker_id,
            business_id,
            name=body.get("name") if "name" in body else None,
            phone=body.get("phone") if "phone" in body else None,
            color=body.get("color") if "color" in body else None,
        )
        if worker is not None and "pin" in body:
            worker = db.set_worker_pin(
                worker_id, business_id, body.get("pin")
            )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if worker is None:
        return JSONResponse({"error": "Trabajador no encontrado."}, status_code=404)
    return _worker_json(worker)


@router.post("/api/{business_id}/workers/{worker_id}/active")
async def api_worker_active(
    business_id: int, worker_id: int, request: Request
):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if not isinstance(body.get("active"), bool):
        return JSONResponse({"error": "El estado activo no es válido."}, status_code=400)
    worker = db.set_worker_active(worker_id, business_id, body["active"])
    if worker is None:
        return JSONResponse({"error": "Trabajador no encontrado."}, status_code=404)
    return _worker_json(worker)


@router.post(
    "/api/{business_id}/workers/{worker_id}/clockins/{clockin_id}/correct"
)
async def api_correct_worker_clockin(
    request: Request,
    business_id: int,
    worker_id: int,
    clockin_id: int,
):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    user = auth.current_user(request)
    try:
        correction = db.correct_worker_clockin(
            business_id,
            worker_id,
            clockin_id,
            user["id"],
            new_at=body.get("new_at"),
            reason=body.get("reason"),
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if correction is None:
        return JSONResponse({"error": "Fichaje no encontrado."}, status_code=404)
    return {"ok": True, "correction": correction}


@router.post("/api/{business_id}/jobs/{job_id}/assign")
async def api_assign_job_worker(
    business_id: int, job_id: int, request: Request
):
    try:
        body = await _read_json(request)
        worker_id = body.get("worker_id")
        if worker_id in ("", None):
            worker_id = None
        else:
            worker_id = int(worker_id)
        job = db.assign_job_worker(job_id, worker_id, business_id)
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if job is None:
        return JSONResponse({"error": "Trabajo no encontrado."}, status_code=404)
    return job


@router.post("/api/{business_id}/workers/{worker_id}/send-day")
def api_send_worker_day(business_id: int, worker_id: int):
    worker = db.get_worker(worker_id, business_id)
    if not worker or not worker.get("active"):
        return JSONResponse({"error": "Trabajador no encontrado."}, status_code=404)
    if not worker.get("phone"):
        return JSONResponse(
            {"error": "Añade o vincula el teléfono del trabajador primero."},
            status_code=400,
        )
    today = date.today().isoformat()
    jobs = db.jobs_for_worker(worker_id, business_id, today)
    if jobs:
        lines = []
        for job in jobs:
            hour = str(job.get("scheduled_for") or "")[11:16] or "Sin hora"
            place = job.get("client_zone") or job.get("zone") or ""
            suffix = f" · {place}" if place else ""
            lines.append(
                f"• {hour} — {job.get('client_name') or 'Cliente'}: "
                f"{job.get('description') or 'Trabajo'}{suffix}"
            )
        body = (
            f"Hola, {worker['name']}. Tu planning de hoy:\n"
            + "\n".join(lines)
        )
    else:
        body = f"Hola, {worker['name']}. Hoy no tienes trabajos asignados."
    target_phone = "".join(
        character for character in worker["phone"] if character.isdigit()
    )
    if len(target_phone) == 9:
        target_phone = "34" + target_phone
    message = whatsapp.queue_text(
        target_phone,
        body,
        business_id=business_id,
        idempotency_key=f"worker-day:{business_id}:{worker_id}:{today}",
    )
    return {"ok": True, "message_id": message["id"], "status": message["status"]}


@router.get("/api/{business_id}/workers/{worker_id}/link")
def api_worker_link(business_id: int, worker_id: int):
    worker = db.get_worker(worker_id, business_id)
    if not worker or not worker.get("active"):
        return JSONResponse({"error": "Trabajador no encontrado."}, status_code=404)
    token = db.get_or_create_worker_token(business_id, worker_id)
    if not token:
        return JSONResponse({"error": "No se pudo crear el enlace."}, status_code=400)
    command = f"NOESIS EQUIPO {business_id} {worker['access_code']}"
    return {
        "url": f"{config.BASE_URL}/t/{token}",
        "path": f"/t/{token}",
        "access_code": worker["access_code"],
        "whatsapp_command": command,
    }


@router.get("/api/{business_id}/workers/{worker_id}/report")
def api_worker_report(
    business_id: int,
    worker_id: int,
    from_: str = Query("", alias="from"),
    to: str = "",
    format: str = "pdf",
):
    try:
        start = (
            date.fromisoformat(from_).isoformat()
            if from_ else (date.today() - timedelta(days=29)).isoformat()
        )
        end = date.fromisoformat(to).isoformat() if to else date.today().isoformat()
        data = db.clockin_report_data(business_id, worker_id, start, end)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if data is None:
        return JSONResponse({"error": "Trabajador no encontrado."}, status_code=404)
    from ..work_reports import build_clockin_csv, build_clockin_pdf
    safe_name = "".join(
        character if character.isalnum() else "_"
        for character in data["worker"]["name"].lower()
    ).strip("_") or f"trabajador_{worker_id}"
    if format.lower() == "csv":
        payload = build_clockin_csv(data)
        return Response(
            content=payload,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="jornada_{safe_name}_{start}_{end}.csv"'
                )
            },
        )
    if format.lower() != "pdf":
        return JSONResponse({"error": "Formato de informe no válido."}, status_code=400)
    payload = build_clockin_pdf(data)
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="jornada_{safe_name}_{start}_{end}.pdf"'
            )
        },
    )


