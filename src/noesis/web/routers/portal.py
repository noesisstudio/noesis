"""Portales publicos por token."""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from ... import db
from .. import auth
from ..deps import TEMPLATES, _read_json

router = APIRouter()


def _subscription_required(business: dict | None) -> JSONResponse | None:
    if db.subscription_allows_access(business):
        return None
    return JSONResponse(
        {
            "error": (
                "La cuenta está en modo consulta. El titular debe activar Noesis "
                "antes de registrar cambios."
            ),
            "code": "subscription_required",
        },
        status_code=402,
    )


def _signer_ip_hash(request: Request, token: str) -> str:
    value = f"{token}:{auth.client_ip(request)}".encode()
    return hashlib.sha256(value).hexdigest()

# ====================================================== PORTAL DEL CLIENTE === #
# Enlace privado SIN contraseña (estilo "client hub" de Jobber). Es público a
# propósito: el cliente del autónomo no tiene cuenta. El token va ligado a un único
# (negocio, cliente) y solo da acceso a SUS presupuestos y facturas — nunca a los de
# otro cliente. Las rutas /p/ quedan FUERA del auth_guard (no son /b/ ni /api/).
def _token_scan_blocked(request: Request, kind: str) -> bool:
    """Frena el escaneo de enlaces públicos: cada token inválido cuenta contra la IP.
    Los tokens son de 192 bits (imposibles de adivinar); esto solo corta el ruido."""
    return auth.is_rate_limited(f"token-scan:{kind}:{auth.client_ip(request)}")


def _record_token_miss(request: Request, kind: str) -> None:
    auth.record_failed_attempt(f"token-scan:{kind}:{auth.client_ip(request)}")


@router.get("/p/{token}", response_class=HTMLResponse)
def portal_home(request: Request, token: str, ok: str = ""):
    if _token_scan_blocked(request, "portal"):
        return Response("Demasiados intentos. Espera unos minutos.", status_code=429)
    ref = db.resolve_portal_token(token)
    if not ref:
        _record_token_miss(request, "portal")
        return TEMPLATES.TemplateResponse(
            request, "portal.html", {"token": token, "data": None, "ok": ""},
            status_code=404)
    data = db.client_portal_view(ref["business_id"], ref["client_id"])
    if data is None:
        return TEMPLATES.TemplateResponse(
            request, "portal.html", {"token": token, "data": None, "ok": ""},
            status_code=404)
    return TEMPLATES.TemplateResponse(
        request, "portal.html", {"token": token, "data": data, "ok": ok})


@router.post("/p/{token}/quotes/{quote_id}/accept")
def portal_accept_quote(request: Request, token: str, quote_id: int):
    ref = db.resolve_portal_token(token)
    if not ref:
        return RedirectResponse(f"/p/{token}", status_code=303)
    blocked = _subscription_required(db.get_business(ref["business_id"]))
    if blocked:
        return blocked
    q = db.get_quote(quote_id, ref["business_id"])
    if not q or q.get("client_id") != ref["client_id"]:
        return RedirectResponse(f"/p/{token}?ok=nojusto", status_code=303)
    try:
        db.accept_quote(quote_id, ref["business_id"])
    except ValueError:
        return RedirectResponse(f"/p/{token}?ok=error", status_code=303)
    return RedirectResponse(f"/p/{token}?ok=aceptado", status_code=303)


@router.post("/p/{token}/quotes/{quote_id}/reject")
def portal_reject_quote(request: Request, token: str, quote_id: int):
    ref = db.resolve_portal_token(token)
    if not ref:
        return RedirectResponse(f"/p/{token}", status_code=303)
    blocked = _subscription_required(db.get_business(ref["business_id"]))
    if blocked:
        return blocked
    q = db.get_quote(quote_id, ref["business_id"])
    if not q or q.get("client_id") != ref["client_id"]:
        return RedirectResponse(f"/p/{token}?ok=nojusto", status_code=303)
    db.reject_quote(quote_id, ref["business_id"])
    return RedirectResponse(f"/p/{token}?ok=rechazado", status_code=303)


@router.post("/p/{token}/jobs/{job_id}/completion")
async def portal_confirm_job(request: Request, token: str, job_id: int):
    if _token_scan_blocked(request, "portal"):
        return JSONResponse({"error": "Espera unos minutos."}, status_code=429)
    ref = db.resolve_portal_token(token)
    if not ref:
        _record_token_miss(request, "portal")
        return JSONResponse({"error": "Enlace no válido o caducado."}, status_code=404)
    blocked = _subscription_required(db.get_business(ref["business_id"]))
    if blocked:
        return blocked
    try:
        body = await _read_json(request)
        result = db.confirm_job_completion(
            job_id, ref["client_id"], business_id=ref["business_id"],
            accepted=bool(body.get("accepted")),
            customer_name=body.get("customer_name"),
            customer_note=body.get("customer_note"),
            signature_data=body.get("signature_data"),
            signer_ip_hash=_signer_ip_hash(request, token),
            signer_user_agent=request.headers.get("user-agent"),
        )
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"ok": True, "completion": result}


@router.get("/p/{token}/invoices/{invoice_id}/pdf")
def portal_invoice_pdf(request: Request, token: str, invoice_id: int):
    if _token_scan_blocked(request, "portal"):
        return Response("Demasiados intentos. Espera unos minutos.", status_code=429)
    ref = db.resolve_portal_token(token)
    if not ref:
        _record_token_miss(request, "portal")
        return JSONResponse({"error": "Enlace no válido o caducado."}, status_code=404)
    inv = db.get_invoice(invoice_id, ref["business_id"])
    if not inv or inv.get("client_id") != ref["client_id"]:
        return JSONResponse({"error": "Factura no encontrada."}, status_code=404)
    if inv.get("status") not in {"enviada", "parcial", "cobrada"}:
        return JSONResponse({"error": "La factura aún no está disponible."},
                            status_code=404)
    from ..invoice_pdf import build_invoice_pdf
    data = build_invoice_pdf(invoice_id, ref["business_id"])
    if data is None:
        return JSONResponse({"error": "Factura no encontrada."}, status_code=404)
    business = db.get_business(ref["business_id"])
    if not (business and business.get("is_demo")):
        db.record_invoice_communication(
            invoice_id,
            ref["business_id"],
            "visualizacion",
            details="descarga_portal_cliente",
        )
    name = f"factura_{inv.get('number') or invoice_id}.pdf"
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{name}"'})


# ====================================================== PORTAL DE GESTORÍA === #
# Enlace privado para la gestoría del negocio: lista los períodos cerrados y
# descarga el paquete (facturas PDF+CSV, gastos con justificantes, resumen).
# Público a propósito (la gestoría no tiene cuenta); token revocable de 192 bits
# con el mismo freno anti-escaneo que el portal del cliente.
@router.get("/g/{token}", response_class=HTMLResponse)
def gestoria_home(request: Request, token: str):
    if _token_scan_blocked(request, "gestoria"):
        return Response("Demasiados intentos. Espera unos minutos.",
                        status_code=429)
    business = db.resolve_gestoria_token(token)
    if not business:
        _record_token_miss(request, "gestoria")
        return TEMPLATES.TemplateResponse(
            request, "gestoria.html",
            {"token": token, "business": None, "periods": []},
            status_code=404)
    return TEMPLATES.TemplateResponse(request, "gestoria.html", {
        "token": token,
        "business": business,
        "periods": db.gestoria_periods(business["id"]),
        "requests": db.list_gestoria_requests(business["id"]),
    })


@router.post("/g/{token}/solicitud")
async def gestoria_new_request(request: Request, token: str,
                               mensaje: str = Form("")):
    """La gestoría pide documentación al autónomo desde su enlace privado."""
    if _token_scan_blocked(request, "gestoria"):
        return Response("Demasiados intentos. Espera unos minutos.",
                        status_code=429)
    business = db.resolve_gestoria_token(token)
    if not business:
        _record_token_miss(request, "gestoria")
        return JSONResponse({"error": "Enlace no válido."}, status_code=404)
    blocked = _subscription_required(business)
    if blocked:
        return blocked
    try:
        db.add_gestoria_request(mensaje, requested_by="gestoria",
                                business_id=business["id"])
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return RedirectResponse(f"/g/{token}", status_code=303)


@router.get("/g/{token}/paquete/{label}")
def gestoria_package(request: Request, token: str, label: str):
    if _token_scan_blocked(request, "gestoria"):
        return Response("Demasiados intentos. Espera unos minutos.",
                        status_code=429)
    business = db.resolve_gestoria_token(token)
    if not business:
        _record_token_miss(request, "gestoria")
        return JSONResponse({"error": "Enlace no válido."}, status_code=404)
    blocked = _subscription_required(business)
    if blocked:
        return blocked
    from .. import gestoria as gestoria_service
    try:
        package = gestoria_service.build_package(business["id"], label)
    except ValueError:
        return JSONResponse({"error": "Período no válido."}, status_code=404)
    if not package:
        return JSONResponse({"error": "Período no válido."}, status_code=404)
    data, meta = package
    db.mark_gestoria_delivery(business["id"], label, "downloaded")
    db.record_product_event(
        business["id"], "gestoria_package_downloaded",
        json.dumps(
            {"label": label, "version": meta["version"]},
            separators=(",", ":"),
        ),
    )
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition":
                f'attachment; filename="noesis-{label}.zip"'
        },
    )


# ======================================================== PORTAL DE FICHAJE === #
def _worker_token_verified(request: Request, token: str) -> bool:
    expected = hashlib.sha256(token.encode()).hexdigest()
    return request.session.get("worker_token_hash") == expected


def _worker_portal_context(request: Request, token: str) -> dict:
    ref = db.resolve_worker_token(token)
    if not ref:
        return {"token": token, "data": None}
    worker = ref["worker"]
    business = ref["business"]
    pin_required = bool(worker.get("pin_hash"))
    unlocked = not pin_required or _worker_token_verified(request, token)
    safe_worker = {
        key: worker.get(key)
        for key in ("id", "name", "color", "business_id", "has_pin")
    }
    initials = "".join(
        part[0].upper() for part in (business.get("name") or "N").split()[:2]
    )
    # El logo subido en Ajustes también viste el portal del trabajador.
    logo = None
    if business.get("logo_data") and business.get("logo_mime"):
        logo = f"data:{business['logo_mime']};base64,{business['logo_data']}"
    jobs = (
        db.jobs_for_worker(worker["id"], business["id"], date.today().isoformat())
        if unlocked else []
    )
    for job in jobs:
        field = db.job_field_view(job["id"], business["id"]) or {}
        completion = dict(field.get("completion") or {})
        completion.pop("signature_data", None)
        job["field"] = {
            "materials": field.get("materials", []),
            "material_cost": field.get("material_cost", 0),
            "updates": field.get("updates", []),
            "completion": completion or None,
        }
    data = {
        "worker": safe_worker,
        "business": {
            "name": business.get("name"),
            "brand_color": db.business_brand_color(business),
            "initials": initials or "N",
            "logo": logo,
        },
        "pin_required": pin_required,
        "unlocked": unlocked,
        "jobs": jobs,
        "tasks": (
            db.project_tasks_for_worker(worker["id"], business["id"])
            if unlocked else []
        ),
        "open_shift": (
            db.worker_open_shift(worker["id"], business["id"]) if unlocked else None
        ),
        "history": (
            db.worker_clockin_history(
                worker["id"],
                business["id"],
                from_day=(date.today() - timedelta(days=29)).isoformat(),
                to_day=date.today().isoformat(),
            )
            if unlocked else []
        ),
        "clockin_policy": business.get("clockin_policy"),
        "info_ack": request.session.get("clockin_info_ack") == hashlib.sha256(
            token.encode()
        ).hexdigest(),
        "subscription_read_only": not db.subscription_allows_access(business),
    }
    return {"token": token, "data": data}


@router.get("/t/{token}", response_class=HTMLResponse)
def worker_portal(request: Request, token: str):
    if _token_scan_blocked(request, "fichaje"):
        return Response("Demasiados intentos. Espera unos minutos.", status_code=429)
    context = _worker_portal_context(request, token)
    if not context["data"]:
        _record_token_miss(request, "fichaje")
    return TEMPLATES.TemplateResponse(
        request,
        "fichaje.html",
        context,
        status_code=200 if context["data"] else 404,
    )


@router.post("/t/{token}/pin")
async def worker_portal_pin(request: Request, token: str):
    ref = db.resolve_worker_token(token)
    if not ref:
        return JSONResponse({"error": "Enlace no válido o caducado."}, status_code=404)
    worker = ref["worker"]
    if not worker.get("pin_hash"):
        request.session["worker_token_hash"] = hashlib.sha256(token.encode()).hexdigest()
        return {"ok": True}
    key = f"worker-pin:{worker['id']}:{auth.client_ip(request)}"
    if auth.is_rate_limited(key):
        return JSONResponse(
            {"error": "Demasiados intentos. Espera unos minutos."}, status_code=429
        )
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if not auth.verify_password(str(body.get("pin") or ""), worker["pin_hash"]):
        auth.record_failed_attempt(key)
        return JSONResponse({"error": "PIN incorrecto."}, status_code=401)
    auth.clear_attempts(key)
    request.session["worker_token_hash"] = hashlib.sha256(token.encode()).hexdigest()
    return {"ok": True}


@router.post("/t/{token}/clock")
async def worker_portal_clock(request: Request, token: str):
    ref = db.resolve_worker_token(token)
    if not ref:
        return JSONResponse({"error": "Enlace no válido o caducado."}, status_code=404)
    blocked = _subscription_required(ref["business"])
    if blocked:
        return blocked
    worker = ref["worker"]
    if worker.get("pin_hash") and not _worker_token_verified(request, token):
        return JSONResponse({"error": "Introduce tu PIN primero."}, status_code=403)
    try:
        body = await _read_json(request)
        job_id = body.get("job_id")
        if job_id in ("", None):
            job_id = None
        else:
            job_id = int(job_id)
        clockin = db.clock_worker(
            ref["business"]["id"],
            worker["id"],
            str(body.get("action") or ""),
            "web",
            job_id=job_id,
            lat=body.get("lat"),
            lng=body.get("lng"),
            accuracy=body.get("accuracy"),
        )
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"ok": True, "clockin": clockin}


@router.post("/t/{token}/ack")
def worker_portal_ack(request: Request, token: str):
    ref = db.resolve_worker_token(token)
    if not ref:
        return JSONResponse({"error": "Enlace no válido o caducado."}, status_code=404)
    blocked = _subscription_required(ref["business"])
    if blocked:
        return blocked
    worker = ref["worker"]
    if worker.get("pin_hash") and not _worker_token_verified(request, token):
        return JSONResponse({"error": "Introduce tu PIN primero."}, status_code=403)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    db.record_product_event(
        ref["business"]["id"],
        "fichaje_info_ack",
        json.dumps(
            {"worker_id": worker["id"], "ack_at": date.today().isoformat()},
            ensure_ascii=False,
        ),
    )
    request.session["clockin_info_ack"] = token_hash
    return {"ok": True}


@router.post("/t/{token}/tasks/{task_id}")
async def worker_portal_task(
    request: Request, token: str, task_id: int
):
    ref = db.resolve_worker_token(token)
    if not ref:
        return JSONResponse({"error": "Enlace no válido o caducado."}, status_code=404)
    blocked = _subscription_required(ref["business"])
    if blocked:
        return blocked
    worker = ref["worker"]
    if worker.get("pin_hash") and not _worker_token_verified(request, token):
        return JSONResponse({"error": "Introduce tu PIN primero."}, status_code=403)
    try:
        body = await _read_json(request)
        task = db.update_project_task(
            task_id,
            business_id=ref["business"]["id"],
            status=body.get("status"),
            actor_worker_id=worker["id"],
        )
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if not task:
        return JSONResponse({"error": "Tarea no encontrada."}, status_code=404)
    return {"ok": True, "task": task}


def _worker_ref(request: Request, token: str):
    ref = db.resolve_worker_token(token)
    if not ref:
        return None, JSONResponse(
            {"error": "Enlace no válido o caducado."}, status_code=404
        )
    blocked = _subscription_required(ref["business"])
    if blocked:
        return None, blocked
    if ref["worker"].get("pin_hash") and not _worker_token_verified(request, token):
        return None, JSONResponse(
            {"error": "Introduce tu PIN primero."}, status_code=403
        )
    return ref, None


@router.post("/t/{token}/jobs/{job_id}/materials")
async def worker_job_material(request: Request, token: str, job_id: int):
    ref, error = _worker_ref(request, token)
    if error:
        return error
    try:
        body = await _read_json(request)
        material = db.add_job_material(
            job_id, body.get("description"), body.get("quantity"),
            body.get("unit_cost"), business_id=ref["business"]["id"],
            worker_id=ref["worker"]["id"],
        )
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"ok": True, "material": material}


@router.post("/t/{token}/jobs/{job_id}/updates")
async def worker_job_update(request: Request, token: str, job_id: int):
    ref, error = _worker_ref(request, token)
    if error:
        return error
    try:
        body = await _read_json(request)
        update = db.add_job_update(
            job_id, body.get("kind"), body.get("body"),
            business_id=ref["business"]["id"],
            worker_id=ref["worker"]["id"],
        )
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"ok": True, "update": update}


@router.post("/t/{token}/jobs/{job_id}/photos")
async def worker_job_photo(
    request: Request, token: str, job_id: int,
    file: UploadFile = File(...), note: str = Form(""),
):
    ref, error = _worker_ref(request, token)
    if error:
        return error
    from ... import config
    from ...documents import service as docservice

    max_bytes = config.MAX_UPLOAD_MB * 1024 * 1024
    payload = await file.read(max_bytes + 1)
    if len(payload) > max_bytes:
        return JSONResponse(
            {"error": f"La foto supera el límite de {config.MAX_UPLOAD_MB} MB."},
            status_code=413,
        )
    job = db.get_job(job_id, ref["business"]["id"])
    if not job:
        return JSONResponse({"error": "Trabajo no encontrado."}, status_code=404)
    try:
        document = docservice.upload(
            ref["business"]["id"], file.filename or "evidencia.jpg", payload,
            client_id=job.get("client_id"), project_id=job.get("project_id"),
            note=note, run_ocr=False,
        )
        update = db.add_job_update(
            job_id, "foto", note, business_id=ref["business"]["id"],
            worker_id=ref["worker"]["id"], document_id=document["id"],
        )
    except (docservice.UploadError, TypeError, ValueError) as exc:
        if "document" in locals():
            docservice.delete(ref["business"]["id"], document["id"])
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"ok": True, "update": update}


@router.post("/t/{token}/jobs/{job_id}/complete")
async def worker_job_complete(request: Request, token: str, job_id: int):
    ref, error = _worker_ref(request, token)
    if error:
        return error
    try:
        body = await _read_json(request)
        signature_data = body.get("signature_data")
        completion = db.complete_job(
            job_id, business_id=ref["business"]["id"],
            worker_id=ref["worker"]["id"], summary=body.get("summary"),
            customer_name=body.get("customer_name"),
            signature_data=signature_data,
            source="presencial" if signature_data else "trabajador",
            signer_ip_hash=(
                _signer_ip_hash(request, token) if signature_data else None
            ),
            signer_user_agent=request.headers.get("user-agent"),
        )
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    safe = dict(completion)
    safe.pop("signature_data", None)
    return {"ok": True, "completion": safe}
