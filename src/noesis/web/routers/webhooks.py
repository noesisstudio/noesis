"""Rutas de salud y webhooks."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ... import db

router = APIRouter()


@router.get("/health")
def health(request: Request):
    """Liveness para el proveedor cloud: el proceso HTTP esta respondiendo."""
    return {"status": "ok", "service": "noesis", "version": request.app.version}


@router.get("/ready")
def readiness():
    """Readiness: comprueba que el almacenamiento esta inicializado y accesible."""
    try:
        from ... import migrations

        ready = migrations.is_current()
    except db.DatabaseError:
        ready = False
    if not ready:
        return JSONResponse({"status": "not_ready"}, status_code=503)
    return {"status": "ready"}
