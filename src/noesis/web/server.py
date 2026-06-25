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

from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .. import config, db
from . import auth, chat, reports
from .scheduler import start_scheduler

HERE = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=str(HERE / "templates"))

app = FastAPI(title="Noesis", version="0.3.0")
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")


# --- Guardia de seguridad: protege /b/ y /api/ y comprueba que el usuario sea
#     dueño del negocio que pide (aislamiento entre clientes). Se define ANTES de
#     añadir SessionMiddleware para que éste quede por fuera y la sesión exista aquí.
@app.middleware("http")
async def auth_guard(request: Request, call_next):
    path = request.url.path
    if path.startswith("/b/") or path.startswith("/api/"):
        uid = request.session.get("uid")
        if not uid:
            if path.startswith("/api/"):
                return JSONResponse({"error": "no autenticado"}, status_code=401)
            return RedirectResponse("/login")
        parts = path.split("/")
        try:
            wanted = int(parts[2])
        except (IndexError, ValueError):
            wanted = None
        if wanted is not None and request.session.get("bid") != wanted:
            if path.startswith("/api/"):
                return JSONResponse({"error": "no autorizado"}, status_code=403)
            return RedirectResponse(f"/b/{request.session.get('bid')}/resumen")
    return await call_next(request)


app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY,
                   max_age=60 * 60 * 24 * 14)  # 14 días


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    if not db.list_clients():
        from .. import demo
        demo.seed()
    # Usuario de demostración para el negocio 1 (para que puedas entrar y probar).
    if not db.get_user_by_email("demo@bynoesis.com"):
        db.create_user("demo@bynoesis.com", auth.hash_password("demo1234"), 1)
    start_scheduler()


# ============================================================== PÁGINAS ===== #
_PAGES = {
    "resumen": "Resumen", "ingresos": "Ingresos", "costes": "Costes",
    "facturas": "Facturas", "cobros": "Cobros", "agenda": "Agenda",
    "clientes": "Clientes", "asistente": "Asistente", "ajustes": "Ajustes",
}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    bid = request.session.get("bid")
    return TEMPLATES.TemplateResponse(request, "landing.html", {"business_id": bid})


# ================================================================ AUTH ====== #
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    return TEMPLATES.TemplateResponse(request, "login.html", {"error": error})


@app.post("/login")
def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    user = db.get_user_by_email(email)
    if not user or not auth.verify_password(password, user["password_hash"]):
        return RedirectResponse("/login?error=1", status_code=303)
    request.session["uid"] = user["id"]
    request.session["bid"] = user["business_id"]
    return RedirectResponse(f"/b/{user['business_id']}/resumen", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/b/{business_id}/{page}", response_class=HTMLResponse)
def page(request: Request, business_id: int, page: str):
    if page not in _PAGES:
        return RedirectResponse(f"/b/{business_id}/resumen")
    biz = db.get_business(business_id) or db.get_business(1)
    return TEMPLATES.TemplateResponse(
        request, f"{page}.html",
        {"business": biz, "active": page, "page_title": _PAGES[page]},
    )


# ================================================================= API ====== #
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
    body = await request.json()
    concept = (body.get("concept") or "").strip()
    try:
        amount = float(body.get("amount"))
    except (TypeError, ValueError):
        amount = 0
    if not concept or amount <= 0:
        return JSONResponse({"error": "Concepto e importe (>0) son obligatorios."},
                            status_code=400)
    return db.add_expense(concept, amount, vat_rate=body.get("vat_rate"),
                          category=body.get("category"), business_id=business_id)


@app.delete("/api/{business_id}/expenses/{expense_id}")
def api_delete_expense(business_id: int, expense_id: int):
    db.delete_expense(expense_id, business_id)
    return {"ok": True}


@app.post("/api/{business_id}/clients/{client_id}")
async def api_update_client(business_id: int, client_id: int, request: Request):
    body = await request.json()
    if not (body.get("name") or "").strip():
        return JSONResponse({"error": "El nombre es obligatorio."}, status_code=400)
    return db.update_client(client_id, business_id, name=body.get("name"),
                            phone=body.get("phone"), zone=body.get("zone"))


@app.delete("/api/{business_id}/clients/{client_id}")
def api_delete_client(business_id: int, client_id: int):
    db.delete_client(client_id, business_id)
    return {"ok": True}


@app.delete("/api/{business_id}/invoices/{invoice_id}")
def api_delete_invoice(business_id: int, invoice_id: int):
    db.delete_invoice(invoice_id, business_id)
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
    inv = db.get_invoice(invoice_id)
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
def api_agenda(business_id: int, week: bool = False):
    if week:
        start = date.today()
        return db.jobs_between(start.isoformat(),
                               (start + timedelta(days=6)).isoformat(), business_id)
    return db.jobs_for_date(date.today().isoformat(), business_id)


@app.post("/api/{business_id}/invoices/{invoice_id}/pay")
def api_mark_paid(business_id: int, invoice_id: int):
    return db.mark_invoice_paid(invoice_id)


@app.post("/api/{business_id}/chat")
async def api_chat(business_id: int, request: Request):
    body = await request.json()
    return chat.handle(business_id, body.get("message", ""))


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


# =========================================================== ONBOARDING ===== #
@app.get("/onboarding", response_class=HTMLResponse)
def onboarding(request: Request, error: str = ""):
    return TEMPLATES.TemplateResponse(request, "onboarding.html", {"error": error})


@app.post("/onboarding/signup")
def onboarding_signup(request: Request, name: str = Form(...),
                      email: str = Form(...), password: str = Form(...),
                      sector: str = Form("")):
    if len(password) < 6:
        return RedirectResponse("/onboarding?error=password", status_code=303)
    if db.get_user_by_email(email):
        return RedirectResponse("/onboarding?error=email", status_code=303)
    biz = db.create_business(name, owner_email=email, sector=sector or None)
    user = db.create_user(email, auth.hash_password(password), biz["id"])
    request.session["uid"] = user["id"]
    request.session["bid"] = biz["id"]
    return RedirectResponse(f"/onboarding/whatsapp/{biz['id']}", status_code=303)


@app.get("/onboarding/whatsapp/{business_id}", response_class=HTMLResponse)
def onboarding_whatsapp(request: Request, business_id: int):
    biz = db.get_business(business_id)
    return TEMPLATES.TemplateResponse(request, "whatsapp_connect.html", {"business": biz})


@app.post("/b/{business_id}/fiscal")
def update_fiscal(business_id: int, name: str = Form(""), nif: str = Form(""),
                  address: str = Form(""), default_vat: float = Form(21),
                  default_irpf: float = Form(0)):
    db.update_fiscal(business_id, name=name or None, nif=nif or None,
                     address=address or None, default_vat=default_vat,
                     default_irpf=default_irpf)
    return RedirectResponse(f"/b/{business_id}/ajustes", status_code=303)


@app.post("/onboarding/whatsapp/{business_id}/connect")
def onboarding_whatsapp_connect(business_id: int, phone: str = Form(...)):
    db.set_whatsapp_status(business_id, "conectado", phone=phone)
    db.finish_onboarding(business_id)
    return RedirectResponse(f"/b/{business_id}/resumen", status_code=303)


# ============================================================== WEBHOOK ===== #
@app.get("/webhook/whatsapp")
def whatsapp_verify(hub_challenge: str = ""):
    return Response(content=hub_challenge or "ok")


@app.post("/webhook/whatsapp")
async def whatsapp_inbound(request: Request):
    payload = await request.json()
    # TODO: identificar negocio por número y enrutar a chat.handle(...).
    return {"status": "received", "echo": payload}


def main() -> None:
    import uvicorn
    uvicorn.run("noesis.web.server:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
