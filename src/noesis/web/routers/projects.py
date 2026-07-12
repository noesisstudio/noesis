"""Rutas de proyectos, costes y equipo asignado."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ... import db
from ..deps import _read_json

router = APIRouter()


async def _body(request: Request):
    try:
        return await _read_json(request), None
    except ValueError as exc:
        return None, JSONResponse({"error": str(exc)}, status_code=400)


@router.get("/api/{business_id}/projects")
def api_projects(business_id: int):
    return db.project_summary(business_id)


@router.post("/api/{business_id}/projects", status_code=201)
async def api_create_project(business_id: int, request: Request):
    body, error = await _body(request)
    if error:
        return error
    try:
        return db.add_project(
            body.get("name"), body.get("budget"), client_id=body.get("client_id"),
            location=body.get("location"), planned_hours=body.get("planned_hours", 0),
            starts_on=body.get("starts_on"), ends_on=body.get("ends_on"),
            note=body.get("note"), business_id=business_id,
        )
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.get("/api/{business_id}/projects/{project_id}")
def api_project(business_id: int, project_id: int):
    project = db.get_project(project_id, business_id)
    if not project:
        return JSONResponse({"error": "Proyecto no encontrado."}, status_code=404)
    return project


@router.patch("/api/{business_id}/projects/{project_id}")
async def api_update_project(business_id: int, project_id: int, request: Request):
    body, error = await _body(request)
    if error:
        return error
    try:
        project = db.update_project(
            project_id, business_id=business_id, progress=body.get("progress"),
            status=body.get("status"),
        )
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if not project:
        return JSONResponse({"error": "Proyecto no encontrado."}, status_code=404)
    return project


@router.post("/api/{business_id}/projects/{project_id}/members", status_code=201)
async def api_add_project_member(business_id: int, project_id: int, request: Request):
    body, error = await _body(request)
    if error:
        return error
    try:
        return db.add_project_member(
            project_id, int(body.get("worker_id")), body.get("hourly_cost", 0),
            body.get("role"), business_id=business_id,
        )
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/api/{business_id}/projects/{project_id}/entries", status_code=201)
async def api_add_project_entry(business_id: int, project_id: int, request: Request):
    body, error = await _body(request)
    if error:
        return error
    try:
        return db.add_project_entry(
            project_id, body.get("kind"), body.get("description"),
            body.get("quantity"), body.get("unit_cost"), body.get("worker_id"),
            body.get("entry_on"), business_id=business_id,
        )
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
