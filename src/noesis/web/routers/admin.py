"""Rutas de administracion interna."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from ... import config, db, readiness
from .. import auth, backups
from ..deps import TEMPLATES

router = APIRouter()

# ========================================================= ADMIN (fundador) = #
def _is_admin(request: Request) -> bool:
    user = auth.current_user(request)
    if not user:
        return False
    allowed = bool(user.get("is_admin")) or (
        bool(config.ADMIN_EMAIL) and user["email"].lower() == config.ADMIN_EMAIL
    )
    if not allowed:
        return False
    if config.ADMIN_REQUIRE_GOOGLE_OAUTH:
        return request.session.get("auth_provider") == "google"
    return True


@router.get("/admin", response_class=HTMLResponse)
def admin_panel(request: Request):
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    data = db.admin_overview()
    data["backup"] = backups.admin_backup_status()
    data["readiness"] = readiness.collect_readiness(check_database=False)
    return TEMPLATES.TemplateResponse(request, "admin.html",
                                      {"data": data})


@router.get("/admin/backups/latest")
def admin_download_latest_backup(request: Request):
    if not _is_admin(request):
        return Response("No autorizado.", status_code=403)
    path = backups.latest_verified_backup()
    if not path:
        return Response("No hay ninguna copia verificada disponible.", status_code=404)
    media_type = (
        "application/gzip"
        if path.name.endswith((".gz", ".dump"))
        else "application/vnd.sqlite3"
    )
    return FileResponse(path, media_type=media_type, filename=path.name)
