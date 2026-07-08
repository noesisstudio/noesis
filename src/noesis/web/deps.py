"""Dependencias compartidas de la capa web."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .. import config, db
from . import auth

HERE = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=str(HERE / "templates"))


def _asset_version() -> str:
    """Versiona assets por fecha de modificacion para romper cache tras despliegues."""
    paths = [HERE / "static" / "app.css", HERE / "static" / "app.js"]
    try:
        return str(int(max(p.stat().st_mtime for p in paths if p.exists())))
    except ValueError:
        return "1"


# Disponible en todas las plantillas como {{ asset_v }}.
TEMPLATES.env.globals["asset_v"] = _asset_version()


def _eur(value) -> str:
    """Formato de dinero en espanol (1.234,56 EUR) para las plantillas."""
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        n = 0.0
    return f"{n:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


# Disponible en plantillas como {{ importe | eur }}.
TEMPLATES.env.filters["eur"] = _eur


def current_user(request: Request) -> dict | None:
    return auth.current_user(request)


def require_business(request: Request, business_id: int) -> dict | None:
    user = current_user(request)
    if not user or user["business_id"] != business_id:
        return None
    return db.get_business(business_id)


def csrf_response(request: Request) -> JSONResponse | None:
    path = request.url.path
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    if path.startswith("/webhook/"):
        return None
    origin = request.headers.get("origin")
    fetch_site = request.headers.get("sec-fetch-site", "")
    if fetch_site == "cross-site":
        return JSONResponse({"error": "petición cross-site rechazada"}, status_code=403)
    if origin:
        origin_url = urlsplit(origin)
        if origin_url.netloc.lower() != request.headers.get("host", "").lower():
            return JSONResponse({"error": "origen no autorizado"}, status_code=403)
    return None


async def auth_guard(request: Request, call_next):
    path = request.url.path
    csrf_error = csrf_response(request)
    if csrf_error is not None:
        return csrf_error

    if path.startswith("/b/") or path.startswith("/api/"):
        user = current_user(request)
        if not user:
            request.session.clear()
            if path.startswith("/api/"):
                return JSONResponse({"error": "no autenticado"}, status_code=401)
            return RedirectResponse("/login")
        parts = path.split("/")
        try:
            wanted = int(parts[2])
        except (IndexError, ValueError):
            wanted = None
        own_business_id = user["business_id"]
        if wanted is not None and own_business_id != wanted:
            if path.startswith("/api/"):
                return JSONResponse({"error": "no autorizado"}, status_code=403)
            return RedirectResponse(f"/b/{own_business_id}/resumen")
        business = db.get_business(own_business_id)
        allowed_when_blocked = (
            path.startswith(f"/b/{own_business_id}/suscripcion")
            or path == f"/b/{own_business_id}/account/delete"
            or path == f"/api/{own_business_id}/export"
        )
        if not db.subscription_allows_access(business) and not allowed_when_blocked:
            if path.startswith("/api/"):
                return JSONResponse(
                    {"error": "La suscripción no está activa."}, status_code=402
                )
            return RedirectResponse(f"/b/{own_business_id}/suscripcion?status=required")
    return await call_next(request)


async def _read_json(request: Request) -> dict:
    declared = request.headers.get("content-length")
    if declared:
        try:
            declared_size = int(declared)
        except ValueError as exc:
            raise ValueError("Content-Length no es válido.") from exc
        if declared_size > config.MAX_JSON_BYTES:
            raise ValueError("La petición es demasiado grande.")
    raw = await request.body()
    if len(raw) > config.MAX_JSON_BYTES:
        raise ValueError("La petición es demasiado grande.")
    try:
        data = json.loads(raw or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("El JSON no es válido.") from exc
    if not isinstance(data, dict):
        raise ValueError("El cuerpo debe ser un objeto JSON.")
    return data
