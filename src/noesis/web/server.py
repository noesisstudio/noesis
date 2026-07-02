"""Servidor web de Noesis (FastAPI) — app multipágina.

Un único proceso, fácil de desplegar 24/7, sirve:
  1. Las PÁGINAS del producto (resumen, ingresos, costes, facturas, cobros,
     agenda, clientes, asistente, ajustes) — cada una su propia vista en detalle.
  2. La API JSON que las alimenta (y que mañana usará la app móvil).
  3. El ONBOARDING (alta de negocio + conexión de WhatsApp).
  4. El CHATBOT interno (cerebro local + IA opcional).
  5. El WEBHOOK de WhatsApp (stub, listo para Meta Cloud API).

Arrancar:   noesis-web
Producción: uvicorn noesis.web.server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import BackgroundTasks, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.concurrency import run_in_threadpool

from .. import config, db
from ..adapters import billing as billing_adapter
from ..adapters import email as email_adapter
from ..tools import run_tool
from . import auth, chat, reports, whatsapp
from .scheduler import start_scheduler

HERE = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=str(HERE / "templates"))


def _asset_version() -> str:
    """Versión de los assets a partir de su fecha de modificación, para romper la
    caché del navegador automáticamente cada vez que cambian CSS/JS (clave en
    producción: si no, los usuarios verían estilos viejos tras un despliegue)."""
    paths = [HERE / "static" / "app.css", HERE / "static" / "app.js"]
    try:
        return str(int(max(p.stat().st_mtime for p in paths if p.exists())))
    except ValueError:
        return "1"


# Disponible en todas las plantillas como {{ asset_v }}.
TEMPLATES.env.globals["asset_v"] = _asset_version()

app = FastAPI(title="Noesis", version="0.3.0")
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")


# --- Guardia de seguridad: protege /b/ y /api/ y comprueba que el usuario sea
#     dueño del negocio que pide (aislamiento entre clientes). Se define ANTES de
#     añadir SessionMiddleware para que éste quede por fuera y la sesión exista aquí.
@app.middleware("http")
async def auth_guard(request: Request, call_next):
    path = request.url.path
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not path.startswith(
        "/webhook/"
    ):
        origin = request.headers.get("origin")
        fetch_site = request.headers.get("sec-fetch-site", "")
        if fetch_site == "cross-site":
            return JSONResponse({"error": "petición cross-site rechazada"}, status_code=403)
        if origin:
            origin_url = urlsplit(origin)
            if origin_url.netloc.lower() != request.headers.get("host", "").lower():
                return JSONResponse({"error": "origen no autorizado"}, status_code=403)

    if path.startswith("/b/") or path.startswith("/api/"):
        user = auth.current_user(request)
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


app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY,
                   max_age=60 * 60 * 24 * 14,        # 14 días
                   same_site="lax", https_only=config.HTTPS_ONLY)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), geolocation=(), payment=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; font-src 'self'; "
        "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; "
        "form-action 'self' https://checkout.stripe.com"
    )
    if config.HTTPS_ONLY:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    if request.url.path.startswith(("/b/", "/api/", "/admin")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.on_event("startup")
def _startup() -> None:
    import logging
    log = logging.getLogger("uvicorn.error")
    if config.IS_PRODUCTION and config.SECRET_KEY == "dev-secret-cambiar-en-produccion":
        raise RuntimeError(
            "NOESIS_SECRET es obligatoria en producción y debe ser larga y aleatoria."
        )
    if config.IS_PRODUCTION and not config.BASE_URL.startswith("https://"):
        log.error(
            "NOESIS_BASE_URL no usa HTTPS. La app continuará disponible, pero los "
            "enlaces de recuperación y Stripe pueden ser incorrectos. Configura "
            "NOESIS_BASE_URL o habilita un dominio público en Railway."
        )
    if config.IS_PRODUCTION and os.getenv("WHATSAPP_TOKEN") and not config.WHATSAPP_APP_SECRET:
        raise RuntimeError(
            "WHATSAPP_APP_SECRET es obligatorio al activar WhatsApp en producción."
        )
    if config.IS_PRODUCTION and config.STRIPE_SECRET_KEY and not config.STRIPE_WEBHOOK_SECRET:
        raise RuntimeError(
            "STRIPE_WEBHOOK_SECRET es obligatorio al activar Stripe en producción."
        )
    if config.RESET_DB:
        # Reinicio de UN SOLO USO: borra todo una vez y deja un marcador, para que
        # aunque olvides quitar la variable NO se vuelva a borrar en cada despliegue.
        marker = Path(config.DB_PATH).parent / ".db_reset_done"
        if marker.exists():
            db.init_db()
            log.info("NOESIS_RESET_DB presente, pero ya se reinició antes: no se borra.")
        else:
            db.reset_db()
            try:
                marker.write_text("done")
            except OSError:
                pass
            log.warning("NOESIS_RESET_DB: base de datos REINICIADA (una sola vez).")
    else:
        db.init_db()
    # Datos demo solo si se piden explícitamente (producción arranca limpia y real).
    if config.SEED_DEMO:
        if not db.list_clients():
            from .. import demo
            demo.seed()
        if not db.get_user_by_email("demo@bynoesis.com"):
            db.create_user("demo@bynoesis.com", auth.hash_password("demo1234"), 1)
    start_scheduler()


# ============================================================== PÁGINAS ===== #
_PAGES = {
    "resumen": "Resumen", "analisis": "Análisis", "ingresos": "Ingresos",
    "costes": "Costes", "presupuestos": "Presupuestos", "facturas": "Facturas",
    "cobros": "Cobros", "impuestos": "Impuestos", "agenda": "Agenda",
    "clientes": "Clientes", "documentos": "Documentos",
    "asistente": "Asistente", "ajustes": "Ajustes",
}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    bid = request.session.get("bid")
    return TEMPLATES.TemplateResponse(request, "landing.html", {"business_id": bid})


@app.get("/sw.js")
def service_worker():
    # Servido desde la raíz para que el service worker controle toda la app (scope /).
    return Response(content=(HERE / "static" / "sw.js").read_text(encoding="utf-8"),
                    media_type="application/javascript")


@app.get("/privacidad", response_class=HTMLResponse)
def privacidad(request: Request):
    return TEMPLATES.TemplateResponse(request, "privacidad.html", {})


@app.get("/terminos", response_class=HTMLResponse)
def terminos(request: Request):
    return TEMPLATES.TemplateResponse(request, "terminos.html", {})


# ================================================================ AUTH ====== #
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    return TEMPLATES.TemplateResponse(request, "login.html", {"error": error})


@app.post("/login")
def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    key = f"login:{auth.client_ip(request)}"
    if auth.is_rate_limited(key):
        return RedirectResponse("/login?error=throttle", status_code=303)
    user = db.get_user_by_email((email or "").strip().lower())
    if not user or not auth.verify_password(password, user["password_hash"]):
        auth.record_failed_attempt(key)
        return RedirectResponse("/login?error=1", status_code=303)
    auth.clear_attempts(key)
    request.session.clear()
    request.session["uid"] = user["id"]
    request.session["bid"] = user["business_id"]
    request.session["sv"] = user.get("session_version", 0)
    return RedirectResponse(f"/b/{user['business_id']}/resumen", status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/b/{business_id}/suscripcion", response_class=HTMLResponse)
def subscription_page(request: Request, business_id: int, status: str = ""):
    # Definida ANTES de la ruta genérica /b/{id}/{page} para que no la capture ésta.
    biz = db.get_business(business_id)
    return TEMPLATES.TemplateResponse(request, "suscripcion.html", {
        "business": biz, "active": "ajustes", "page_title": "Suscripción",
        "status": status, "billing_on": billing_adapter.get_provider().available(),
        "prices": billing_adapter.PLAN_PRICES})


@app.get("/b/{business_id}/{page}", response_class=HTMLResponse)
def page(request: Request, business_id: int, page: str):
    if page not in _PAGES:
        return RedirectResponse(f"/b/{business_id}/resumen")
    biz = db.get_business(business_id) or db.get_business(1)
    ctx = {"business": biz, "active": page, "page_title": _PAGES[page]}
    # En Ajustes, si el WhatsApp aún no está conectado, generamos un código de
    # vinculación fresco para que el autónomo pueda conectarlo desde aquí (no solo
    # durante el onboarding). El código caduca a los 30 min; se regenera en cada visita.
    if page == "ajustes" and biz and biz.get("whatsapp_status") != "conectado":
        ctx["wa"] = whatsapp.start_link(biz["id"])
    return TEMPLATES.TemplateResponse(request, f"{page}.html", ctx)


# ================================================================= API ====== #
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


@app.get("/api/{business_id}/summary")
def api_summary(business_id: int):
    m = db.month_billing(business_id=business_id)
    pend = db.pending_payments(business_id)
    today = date.today().isoformat()
    return {**m,
            "clients": len(db.list_clients(business_id)),
            "jobs_today": len(db.jobs_for_date(today, business_id)),
            "pending_count": len(pend),
            "pending_total": round(sum(p["total"] for p in pend), 2)}


@app.get("/api/{business_id}/series")
def api_series(business_id: int):
    return db.monthly_series(business_id)


@app.get("/api/{business_id}/analysis")
def api_analysis(business_id: int):
    return {**db.financial_analysis(business_id),
            "series": db.monthly_series(business_id, months=12)}


@app.get("/api/{business_id}/clients")
def api_clients(business_id: int):
    return db.list_clients(business_id)


@app.get("/api/{business_id}/clients/stats")
def api_clients_stats(business_id: int):
    return db.client_stats(business_id)


@app.get("/api/{business_id}/invoices")
def api_invoices(business_id: int):
    return db.list_invoices(business_id)


@app.get("/api/{business_id}/expenses")
def api_expenses(business_id: int):
    return db.list_expenses(business_id)


@app.post("/api/{business_id}/expenses")
async def api_add_expense(business_id: int, request: Request):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    concept = (body.get("concept") or "").strip()
    try:
        amount = float(body.get("amount"))
    except (TypeError, ValueError):
        amount = 0
    if not concept or amount <= 0:
        return JSONResponse({"error": "Concepto e importe (>0) son obligatorios."},
                            status_code=400)
    try:
        return db.add_expense(concept, amount, vat_rate=body.get("vat_rate"),
                              category=body.get("category"), business_id=business_id)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.delete("/api/{business_id}/expenses/{expense_id}")
def api_delete_expense(business_id: int, expense_id: int):
    db.delete_expense(expense_id, business_id)
    return {"ok": True}


@app.post("/api/{business_id}/clients")
async def api_create_client(business_id: int, request: Request):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    name = (body.get("name") or "").strip()
    if not name:
        return JSONResponse({"error": "El nombre es obligatorio."}, status_code=400)
    return db.add_client(name, phone=body.get("phone"), address=body.get("address"),
                         zone=body.get("zone"), nif=body.get("nif"),
                         email=body.get("email"), business_id=business_id)


@app.post("/api/{business_id}/clients/{client_id}")
async def api_update_client(business_id: int, client_id: int, request: Request):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if not (body.get("name") or "").strip():
        return JSONResponse({"error": "El nombre es obligatorio."}, status_code=400)
    client = db.update_client(
        client_id, business_id, name=body.get("name"), phone=body.get("phone"),
        address=body.get("address"), zone=body.get("zone"), nif=body.get("nif"),
        email=body.get("email"),
    )
    if client is None:
        return JSONResponse({"error": "Cliente no encontrado."}, status_code=404)
    return client


@app.delete("/api/{business_id}/clients/{client_id}")
def api_delete_client(business_id: int, client_id: int):
    try:
        db.delete_client(client_id, business_id)
    except sqlite3.IntegrityError:
        return JSONResponse(
            {"error": "El cliente tiene datos asociados y no se puede borrar así."},
            status_code=409,
        )
    return {"ok": True}


@app.delete("/api/{business_id}/invoices/{invoice_id}")
def api_delete_invoice(business_id: int, invoice_id: int):
    if not db.delete_invoice(invoice_id, business_id):
        return JSONResponse(
            {"error": "Solo se pueden borrar facturas en borrador."},
            status_code=409,
        )
    return {"ok": True}


@app.delete("/api/{business_id}/jobs/{job_id}")
def api_delete_job(business_id: int, job_id: int):
    db.delete_job(job_id, business_id)
    return {"ok": True}


@app.get("/api/{business_id}/invoices/{invoice_id}/pdf")
def api_invoice_pdf(business_id: int, invoice_id: int):
    from .invoice_pdf import build_invoice_pdf
    data = build_invoice_pdf(invoice_id, business_id)
    if data is None:
        return JSONResponse({"error": "Factura no encontrada."}, status_code=404)
    inv = db.get_invoice(invoice_id, business_id)
    name = f"factura_{inv.get('number') or invoice_id}.pdf"
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{name}"'})


@app.get("/api/{business_id}/costs/breakdown")
def api_costs_breakdown(business_id: int):
    return db.expenses_by_category(business_id)


@app.get("/api/{business_id}/income/by-client")
def api_income_by_client(business_id: int):
    return db.income_by_client(business_id)


@app.get("/api/{business_id}/pending")
def api_pending(business_id: int):
    return db.pending_payments(business_id)


@app.get("/api/{business_id}/agenda")
def api_agenda(business_id: int, week: bool = False, start: str = "", end: str = ""):
    if start and end:
        return db.jobs_between(start, end, business_id)
    if week:
        today = date.today()
        return db.jobs_between(today.isoformat(),
                               (today + timedelta(days=6)).isoformat(), business_id)
    return db.jobs_for_date(date.today().isoformat(), business_id)


@app.post("/api/{business_id}/invoices/{invoice_id}/pay")
def api_mark_paid(business_id: int, invoice_id: int):
    inv = db.mark_invoice_paid(invoice_id, business_id)
    if inv is None:
        return JSONResponse(
            {"error": "Solo se puede cobrar una factura emitida."}, status_code=409
        )
    return inv


@app.post("/api/{business_id}/invoices/{invoice_id}/send")
def api_send_invoice(business_id: int, invoice_id: int):
    # Emite una factura borrador desde la web (mismo flujo que el chat, aislado).
    result = json.loads(run_tool("enviar_factura",
                                 {"factura_id": invoice_id}, business_id))
    if not result.get("ok"):
        return JSONResponse({"error": result.get("error", "No se pudo enviar.")},
                            status_code=400)
    return result["factura"]


# ----------------------------------------------------------- Presupuestos ---
@app.get("/api/{business_id}/quotes")
def api_quotes(business_id: int):
    return db.list_quotes(business_id)


@app.post("/api/{business_id}/quotes")
async def api_add_quote(business_id: int, request: Request):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    cliente = (body.get("cliente") or "").strip()
    concepto = (body.get("concepto") or "").strip()
    try:
        base = float(body.get("base"))
    except (TypeError, ValueError):
        base = 0
    if not cliente or not concepto or base <= 0:
        return JSONResponse({"error": "Cliente, concepto e importe (>0) son obligatorios."},
                            status_code=400)
    args = {"cliente": cliente, "concepto": concepto, "base": base}
    if body.get("iva") is not None:
        args["iva"] = body["iva"]
    if body.get("irpf") is not None:
        args["irpf"] = body["irpf"]
    result = json.loads(run_tool("crear_presupuesto", args, business_id))
    if not result.get("ok"):
        return JSONResponse({"error": result.get("error", "No se pudo crear.")},
                            status_code=400)
    return result["presupuesto"]


@app.post("/api/{business_id}/quotes/{quote_id}/send")
def api_send_quote(business_id: int, quote_id: int):
    try:
        q = db.mark_quote_sent(quote_id, business_id)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)
    if q is None:
        return JSONResponse({"error": "Presupuesto no encontrado."}, status_code=404)
    return q


@app.post("/api/{business_id}/quotes/{quote_id}/accept")
def api_accept_quote(business_id: int, quote_id: int):
    try:
        res = db.accept_quote(quote_id, business_id)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)
    if res is None:
        return JSONResponse({"error": "Presupuesto no encontrado."}, status_code=404)
    return res


@app.post("/api/{business_id}/quotes/{quote_id}/reject")
def api_reject_quote(business_id: int, quote_id: int):
    q = db.reject_quote(quote_id, business_id)
    if q is None:
        return JSONResponse({"error": "Presupuesto no encontrado."}, status_code=404)
    return q


@app.delete("/api/{business_id}/quotes/{quote_id}")
def api_delete_quote(business_id: int, quote_id: int):
    if not db.delete_quote(quote_id, business_id):
        return JSONResponse(
            {"error": "Solo se pueden borrar presupuestos en borrador."},
            status_code=409,
        )
    return {"ok": True}


# -------------------------------------------------------------- Impuestos ---
@app.get("/api/{business_id}/taxes")
def api_taxes(business_id: int, year: int = 0, quarter: int = 0):
    today = date.today()
    year = year or today.year
    quarter = quarter or (today.month - 1) // 3 + 1
    try:
        return {**db.tax_quarter(year, quarter, business_id),
                "current_year": today.year}
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.post("/api/{business_id}/chat")
async def api_chat(business_id: int, request: Request):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    message = str(body.get("message") or "").strip()
    if not message or len(message) > config.MAX_CHAT_CHARS:
        return JSONResponse(
            {"error": "El mensaje está vacío o es demasiado largo."}, status_code=400
        )
    return await run_in_threadpool(chat.handle, business_id, message)


@app.post("/api/{business_id}/chat/audio")
async def api_chat_audio(business_id: int, audio: UploadFile = File(...)):
    # Nota de voz -> texto (Whisper local, sin coste por uso) -> cerebro local.
    from ..adapters import transcription
    tr = transcription.get_transcriber()
    if tr is None:
        return JSONResponse(
            {"error": "Transcripción de voz no disponible en este servidor."},
            status_code=503)
    data = await audio.read(config.MAX_AUDIO_BYTES + 1)
    if len(data) > config.MAX_AUDIO_BYTES:
        return JSONResponse({"error": "El audio es demasiado grande."}, status_code=413)
    try:
        text = await run_in_threadpool(
            tr.transcribe, data, audio.filename or "audio"
        )
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "No he podido entender el audio."}, status_code=422)
    if not text:
        return JSONResponse({"error": "El audio estaba vacío o no se entendió."},
                            status_code=422)
    result = await run_in_threadpool(chat.handle, business_id, text)
    return {"transcription": text, **result}


# ============================================================= INFORMES ===== #
def _csv_response(text: str, filename: str) -> Response:
    return Response(content="﻿" + text,
                    media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/{business_id}/reports/costs.csv")
def report_costs(business_id: int):
    return _csv_response(reports.costs_csv(business_id), "noesis_costes.csv")


@app.get("/api/{business_id}/reports/invoices.csv")
def report_invoices(business_id: int):
    return _csv_response(reports.invoices_csv(business_id), "noesis_facturas.csv")


# =========================================================== DOCUMENTOS ===== #
@app.get("/api/{business_id}/documents")
def api_documents(business_id: int, client_id: int = 0):
    from ..documents import repo as docrepo
    return docrepo.list_for_business(business_id, client_id or None)


@app.get("/api/{business_id}/documents/ocr-status")
def api_ocr_status(business_id: int):
    """Indica si la lectura de fotos (OCR) está activa en este servidor."""
    from ..documents import ocr
    return {"ocr": ocr.available()}


@app.post("/api/{business_id}/documents")
async def api_upload_document(business_id: int, file: UploadFile = File(...),
                              kind: str = Form("documento"),
                              client_id: str = Form(""), invoice_id: str = Form(""),
                              note: str = Form("")):
    from ..documents import service as docservice
    data = await file.read()

    def _opt_int(v):
        try:
            return int(v) if str(v).strip() else None
        except (TypeError, ValueError):
            return None

    try:
        doc = docservice.upload(business_id, file.filename or "documento", data,
                                kind=kind, client_id=_opt_int(client_id),
                                invoice_id=_opt_int(invoice_id), note=note or None)
    except docservice.UploadError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return doc


@app.get("/api/{business_id}/documents/{doc_id}/file")
def api_document_file(business_id: int, doc_id: int):
    from ..documents import service as docservice
    got = docservice.file_bytes(business_id, doc_id)
    if got is None:
        return JSONResponse({"error": "Documento no encontrado."}, status_code=404)
    data, mime, filename = got
    return Response(content=data, media_type=mime,
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


@app.delete("/api/{business_id}/documents/{doc_id}")
def api_delete_document(business_id: int, doc_id: int):
    from ..documents import service as docservice
    if not docservice.delete(business_id, doc_id):
        return JSONResponse({"error": "Documento no encontrado."}, status_code=404)
    return {"ok": True}


@app.post("/api/{business_id}/documents/{doc_id}/to-expense")
async def api_document_to_expense(business_id: int, doc_id: int, request: Request):
    """Convierte un ticket/factura escaneada en un gasto (usa el importe del OCR)."""
    from ..documents import service as docservice
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    amount = body.get("amount")
    try:
        amount = float(amount) if amount not in (None, "") else None
    except (TypeError, ValueError):
        amount = None
    gasto = docservice.convert_ticket_to_expense(
        business_id, doc_id, concept=body.get("concept"), amount=amount)
    if gasto is None:
        return JSONResponse(
            {"error": "No hay importe para registrar. Indica uno o sube una foto legible."},
            status_code=400)
    return gasto


# ================================================================ RGPD ====== #
def _json_download(data: dict, filename: str) -> Response:
    return Response(content=json.dumps(data, ensure_ascii=False, indent=2, default=str),
                    media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/{business_id}/export")
def api_export_account(business_id: int):
    """Portabilidad RGPD: descarga TODOS los datos de la cuenta en JSON."""
    return _json_download(db.export_business_data(business_id),
                          "noesis_datos_cuenta.json")


@app.get("/api/{business_id}/clients/{client_id}/export")
def api_export_client(business_id: int, client_id: int):
    data = db.export_client_data(client_id, business_id)
    if data is None:
        return JSONResponse({"error": "Cliente no encontrado."}, status_code=404)
    return _json_download(data, f"noesis_cliente_{client_id}.json")


@app.delete("/api/{business_id}/clients/{client_id}/erase")
def api_erase_client(business_id: int, client_id: int):
    """Borra datos prescindibles y conserva lo sujeto a obligación fiscal."""
    ok = db.delete_client_cascade(client_id, business_id)
    if not ok:
        return JSONResponse({"error": "Cliente no encontrado."}, status_code=404)
    return {"ok": True}


@app.post("/b/{business_id}/account/delete")
def delete_account(request: Request, business_id: int, confirm: str = Form(""),
                   password: str = Form("")):
    """Baja total de la cuenta del autónomo (RGPD). Pide escribir BORRAR."""
    if confirm.strip().upper() != "BORRAR":
        return RedirectResponse(f"/b/{business_id}/ajustes?error=confirma", status_code=303)
    user = auth.current_user(request)
    if not user or not auth.verify_password(password, user["password_hash"]):
        return RedirectResponse(
            f"/b/{business_id}/ajustes?error=password", status_code=303
        )
    try:
        db.delete_business_cascade(business_id)
    except ValueError:
        return RedirectResponse(
            f"/b/{business_id}/ajustes?error=conservacion_fiscal", status_code=303
        )
    request.session.clear()
    return RedirectResponse("/?bye=1", status_code=303)


# =========================================================== ONBOARDING ===== #
@app.get("/onboarding", response_class=HTMLResponse)
def onboarding(request: Request, error: str = ""):
    return TEMPLATES.TemplateResponse(request, "onboarding.html", {"error": error})


@app.post("/onboarding/signup")
def onboarding_signup(request: Request, name: str = Form(...),
                      email: str = Form(...), password: str = Form(...),
                      sector: str = Form("")):
    key = f"signup:{auth.client_ip(request)}"
    if auth.is_rate_limited(key):
        return RedirectResponse("/onboarding?error=throttle", status_code=303)
    email = (email or "").strip().lower()
    name = (name or "").strip()
    if not name:
        return RedirectResponse("/onboarding?error=name", status_code=303)
    if not auth.valid_email(email):
        return RedirectResponse("/onboarding?error=email_format", status_code=303)
    if len(password) < 12 or len(password) > 1024:
        auth.record_failed_attempt(key)
        return RedirectResponse("/onboarding?error=password", status_code=303)
    if db.get_user_by_email(email):
        return RedirectResponse("/onboarding?error=email", status_code=303)
    try:
        biz, user = db.create_account(
            name, email, auth.hash_password(password), sector or None,
            trial_days=config.TRIAL_DAYS,
        )
    except (ValueError, sqlite3.IntegrityError):
        auth.record_failed_attempt(key)
        return RedirectResponse("/onboarding?error=email", status_code=303)
    auth.clear_attempts(key)
    request.session.clear()
    request.session["uid"] = user["id"]
    request.session["bid"] = biz["id"]
    request.session["sv"] = user.get("session_version", 0)
    return RedirectResponse(f"/onboarding/whatsapp/{biz['id']}", status_code=303)


@app.get("/onboarding/whatsapp/{business_id}", response_class=HTMLResponse)
def onboarding_whatsapp(request: Request, business_id: int):
    # Aislamiento: solo el dueño de ESTE negocio puede ver su onboarding.
    if request.session.get("bid") != business_id:
        return RedirectResponse("/login", status_code=303)
    biz = db.get_business(business_id)
    link = whatsapp.start_link(business_id)
    return TEMPLATES.TemplateResponse(request, "whatsapp_connect.html",
                                      {"business": biz, "wa": link})


@app.post("/b/{business_id}/fiscal")
def update_fiscal(business_id: int, name: str = Form(""), nif: str = Form(""),
                  address: str = Form(""), default_vat: float = Form(21),
                  default_irpf: float = Form(0)):
    try:
        db.update_fiscal(business_id, name=name or None, nif=nif or None,
                         address=address or None, default_vat=default_vat,
                         default_irpf=default_irpf)
    except ValueError:
        return RedirectResponse(
            f"/b/{business_id}/ajustes?error=fiscal", status_code=303
        )
    return RedirectResponse(f"/b/{business_id}/ajustes", status_code=303)


@app.post("/onboarding/whatsapp/{business_id}/connect")
def onboarding_whatsapp_connect(request: Request, business_id: int):
    # La vinculación real solo ocurre al recibir el código desde ese WhatsApp.
    if request.session.get("bid") != business_id:
        return RedirectResponse("/login", status_code=303)
    business = db.get_business(business_id)
    if not business or business.get("whatsapp_status") != "conectado":
        db.set_whatsapp_status(business_id, "no_conectado")
    db.finish_onboarding(business_id)
    return RedirectResponse(f"/b/{business_id}/resumen", status_code=303)


# ============================================================== WEBHOOK ===== #
@app.get("/webhook/whatsapp")
def whatsapp_verify(request: Request):
    # Verificación del webhook de Meta: devuelve el challenge solo si el token coincide.
    params = request.query_params
    expected = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == expected:
        return Response(content=params.get("hub.challenge", ""))
    if not expected and not config.IS_PRODUCTION:
        return Response(content=params.get("hub.challenge", "ok"))
    return JSONResponse({"error": "token inválido"}, status_code=403)


@app.post("/webhook/whatsapp")
async def whatsapp_inbound(request: Request, background_tasks: BackgroundTasks):
    # Enruta el mensaje entrante: vincula por código o lo pasa al cerebro del negocio.
    raw = await request.body()
    if len(raw) > config.MAX_JSON_BYTES:
        return JSONResponse({"error": "payload demasiado grande"}, status_code=413)
    if not whatsapp.verify_signature(
        raw, request.headers.get("x-hub-signature-256", "")
    ):
        return JSONResponse({"error": "firma inválida"}, status_code=401)
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JSONResponse({"error": "JSON inválido"}, status_code=400)
    background_tasks.add_task(whatsapp.handle_inbound, payload)
    return {"status": "accepted"}


# ============================================================ SUSCRIPCIÓN === #
@app.post("/b/{business_id}/suscripcion/checkout")
def subscription_checkout(request: Request, business_id: int, plan: str = Form("autonomo")):
    if plan not in billing_adapter.PLAN_PRICES:
        return RedirectResponse(
            f"/b/{business_id}/suscripcion?status=invalid", status_code=303
        )
    biz = db.get_business(business_id)
    provider = billing_adapter.get_provider()
    base = f"{config.BASE_URL}/b/{business_id}/suscripcion"
    url = provider.checkout_url(biz, plan, f"{base}?status=ok", f"{base}?status=cancel")
    if not url:
        # Sin Stripe configurado: deja constancia de la intención (alta manual).
        return RedirectResponse(f"{base}?status=manual", status_code=303)
    return RedirectResponse(url, status_code=303)


@app.post("/b/{business_id}/suscripcion/portal")
def subscription_portal(request: Request, business_id: int):
    biz = db.get_business(business_id)
    url = billing_adapter.get_provider().portal_url(
        biz, f"{config.BASE_URL}/b/{business_id}/suscripcion")
    if not url:
        return RedirectResponse(f"/b/{business_id}/suscripcion?status=noportal",
                                status_code=303)
    return RedirectResponse(url, status_code=303)


@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Recibe eventos de Stripe y actualiza el estado de la suscripción del negocio."""
    payload = await request.body()
    event = billing_adapter.verify_webhook(payload, request.headers.get("stripe-signature", ""))
    if event is None:
        return JSONResponse({"error": "firma inválida"}, status_code=400)
    event_id = str(event.get("id") or "")
    if not event_id:
        return JSONResponse({"error": "evento sin id"}, status_code=400)
    if not db.claim_webhook_event("stripe", event_id):
        return {"received": True, "duplicate": True}
    obj = event.get("data", {}).get("object", {})
    etype = event.get("type", "")
    bid = (obj.get("metadata") or {}).get("business_id") or obj.get("client_reference_id")
    try:
        bid = int(bid) if bid else None
    except (TypeError, ValueError):
        bid = None
    if etype == "checkout.session.completed" and bid:
        db.set_subscription(bid, "active",
                            plan=(obj.get("metadata") or {}).get("plan"),
                            customer_id=obj.get("customer"),
                            subscription_id=obj.get("subscription"))
    elif etype in ("customer.subscription.created", "customer.subscription.updated"):
        biz = db.get_business_by_stripe_customer(obj.get("customer"))
        if not biz and bid:
            biz = db.get_business(bid)
        if biz:
            stripe_status = obj.get("status")
            status = {
                "active": "active", "trialing": "active",
                "past_due": "past_due", "unpaid": "past_due",
                "canceled": "canceled", "incomplete_expired": "canceled",
            }.get(stripe_status, "trial")
            db.set_subscription(
                biz["id"], status,
                plan=(obj.get("metadata") or {}).get("plan"),
                customer_id=obj.get("customer"),
                subscription_id=obj.get("id"),
            )
    elif etype == "customer.subscription.deleted":
        biz = db.get_business_by_stripe_customer(obj.get("customer"))
        if biz:
            db.set_subscription(biz["id"], "canceled")
    elif etype == "invoice.payment_failed":
        biz = db.get_business_by_stripe_customer(obj.get("customer"))
        if biz:
            db.set_subscription(biz["id"], "past_due")
    elif etype in ("invoice.paid", "invoice.payment_succeeded"):
        biz = db.get_business_by_stripe_customer(obj.get("customer"))
        if biz:
            db.set_subscription(biz["id"], "active")
    return {"received": True}


# ========================================================= ADMIN (fundador) = #
def _is_admin(request: Request) -> bool:
    user = auth.current_user(request)
    if not user:
        return False
    if user.get("is_admin"):
        return True
    return bool(config.ADMIN_EMAIL) and user["email"].lower() == config.ADMIN_EMAIL


@app.get("/admin", response_class=HTMLResponse)
def admin_panel(request: Request):
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    return TEMPLATES.TemplateResponse(request, "admin.html",
                                      {"data": db.admin_overview()})


# ===================================================== RESET DE CONTRASEÑA == #
import hashlib  # noqa: E402
import secrets  # noqa: E402


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@app.get("/recuperar", response_class=HTMLResponse)
def forgot_page(request: Request, sent: str = ""):
    return TEMPLATES.TemplateResponse(request, "forgot.html", {"sent": sent})


@app.post("/recuperar")
def forgot_submit(request: Request, email: str = Form(...)):
    key = f"forgot:{auth.client_ip(request)}"
    if auth.is_rate_limited(key):
        return RedirectResponse("/recuperar?sent=1", status_code=303)
    auth.record_failed_attempt(key)
    email = (email or "").strip().lower()
    user = db.get_user_by_email(email)
    if user:  # Si no existe, no lo revelamos (respuesta idéntica).
        token = secrets.token_urlsafe(32)
        db.create_password_reset(user["id"], _hash_token(token), ttl_minutes=60)
        link = f"{config.BASE_URL}/restablecer?token={token}"
        email_adapter.send_email(
            email, "Restablecer tu contraseña de Noesis",
            f"Hola,\n\nPara crear una contraseña nueva, abre este enlace (válido 1 hora):\n"
            f"{link}\n\nSi no lo has pedido tú, ignora este correo.\n\n— Noesis")
    return RedirectResponse("/recuperar?sent=1", status_code=303)


@app.get("/restablecer", response_class=HTMLResponse)
def reset_page(request: Request, token: str = "", error: str = ""):
    return TEMPLATES.TemplateResponse(request, "reset.html",
                                      {"token": token, "error": error})


@app.post("/restablecer")
def reset_submit(request: Request, token: str = Form(...), password: str = Form(...)):
    if len(password) < 12 or len(password) > 1024:
        return RedirectResponse(f"/restablecer?token={token}&error=password",
                                status_code=303)
    row = db.use_password_reset(_hash_token(token))
    if not row:
        return RedirectResponse("/restablecer?error=token", status_code=303)
    db.set_password(row["user_id"], auth.hash_password(password))
    return RedirectResponse("/login?error=reset_ok", status_code=303)


def main() -> None:
    import os
    import uvicorn
    # En local: 127.0.0.1:8000. En producción el host (Railway/Render) inyecta
    # PORT y necesita escuchar en 0.0.0.0.
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("noesis.web.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
