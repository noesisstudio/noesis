"""Cartera autenticada para gestorías con acceso explícito por empresa."""

from __future__ import annotations

import time

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from ... import config, db
from ...documents import repo as docrepo, service as docservice
from .. import auth
from ..deps import TEMPLATES

router = APIRouter()


def _start_session(request: Request, account: dict) -> None:
    request.session.clear()
    request.session.update({
        "gid": account["id"],
        "gsv": account.get("session_version", 0),
        "gseen": int(time.time()),
    })


def _current_account(request: Request) -> dict | None:
    account = db.get_gestoria_account(request.session.get("gid"))
    if not account or not account.get("is_active"):
        return None
    if request.session.get("gsv", 0) != account.get("session_version", 0):
        return None
    now = int(time.time())
    seen = int(request.session.get("gseen") or now)
    if now - seen > config.SESSION_IDLE_MINUTES * 60:
        request.session.clear()
        return None
    if now - seen >= 300 or "gseen" not in request.session:
        request.session["gseen"] = now
    return account


def _require_account(request: Request) -> dict | RedirectResponse:
    account = _current_account(request)
    if account:
        return account
    request.session.clear()
    return RedirectResponse("/gestoria/login", status_code=303)


def _business_for(request: Request, business_id: int) -> tuple[dict, dict] | None:
    account = _current_account(request)
    if not account:
        return None
    business = db.gestoria_business_for_account(account["id"], business_id)
    return (account, business) if business else None


@router.get("/gestoria/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    if _current_account(request):
        return RedirectResponse("/gestoria", status_code=303)
    return TEMPLATES.TemplateResponse(request, "gestoria_login.html", {
        "error": error,
    })


@router.post("/gestoria/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    email = (email or "").strip().lower()
    keys = (
        f"gestoria-login-ip:{auth.client_ip(request)}",
        f"gestoria-login-account:{email}",
    )
    if any(auth.is_rate_limited(key) for key in keys):
        return RedirectResponse("/gestoria/login?error=throttle", status_code=303)
    account = db.get_gestoria_account_by_email(email)
    if not account or not auth.verify_password(password, account["password_hash"]):
        for key in keys:
            auth.record_failed_attempt(key)
        return RedirectResponse("/gestoria/login?error=1", status_code=303)
    for key in keys:
        auth.clear_attempts(key)
    db.mark_gestoria_login(account["id"])
    _start_session(request, account)
    return RedirectResponse("/gestoria", status_code=303)


@router.post("/gestoria/logout")
def logout(request: Request):
    request.session.clear()
    response = RedirectResponse("/gestoria/login", status_code=303)
    response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage"'
    return response


@router.get("/gestoria/accept/{token}", response_class=HTMLResponse)
def accept_page(request: Request, token: str):
    invitation = db.resolve_gestoria_invitation(auth.hash_token(token))
    account = (
        db.get_gestoria_account_by_email(invitation["email"])
        if invitation else None
    )
    return TEMPLATES.TemplateResponse(
        request, "gestoria_accept.html",
        {"token": token, "invitation": invitation,
         "existing_account": bool(account), "error": ""},
        status_code=200 if invitation else 404,
    )


@router.post("/gestoria/accept/{token}")
def accept(request: Request, token: str, password: str = Form(...),
           firm_name: str = Form("")):
    key = f"gestoria-invite:{auth.client_ip(request)}"
    if auth.is_rate_limited(key):
        return RedirectResponse(
            f"/gestoria/accept/{token}?error=throttle", status_code=303
        )
    invitation = db.resolve_gestoria_invitation(auth.hash_token(token))
    if not invitation:
        auth.record_failed_attempt(key)
        return TEMPLATES.TemplateResponse(
            request, "gestoria_accept.html",
            {"token": token, "invitation": None, "existing_account": False,
             "error": "invite"}, status_code=404,
        )
    account = db.get_gestoria_account_by_email(invitation["email"])
    error = ""
    if account:
        if not auth.verify_password(password, account["password_hash"]):
            error = "password"
    elif len(password) < 12 or len(password) > 1024:
        error = "weak"
    else:
        try:
            account = db.create_gestoria_account(
                invitation["email"], auth.hash_password(password), firm_name
            )
        except ValueError:
            error = "firm"
    if error:
        auth.record_failed_attempt(key)
        return TEMPLATES.TemplateResponse(
            request, "gestoria_accept.html",
            {"token": token, "invitation": invitation,
             "existing_account": bool(db.get_gestoria_account_by_email(
                 invitation["email"])), "error": error}, status_code=400,
        )
    access = db.accept_gestoria_invitation(invitation["id"], account["id"])
    if not access:
        return TEMPLATES.TemplateResponse(
            request, "gestoria_accept.html",
            {"token": token, "invitation": None, "existing_account": False,
             "error": "invite"}, status_code=409,
        )
    auth.clear_attempts(key)
    db.mark_gestoria_login(account["id"])
    _start_session(request, account)
    return RedirectResponse(
        f"/gestoria/cliente/{invitation['business_id']}?ok=connected",
        status_code=303,
    )


@router.get("/gestoria", response_class=HTMLResponse)
def portfolio(request: Request, q: str = ""):
    account = _require_account(request)
    if isinstance(account, RedirectResponse):
        return account
    businesses = db.list_gestoria_businesses(account["id"])
    term = (q or "").strip().lower()[:120]
    if term:
        businesses = [business for business in businesses if term in (
            f"{business.get('name') or ''} {business.get('nif') or ''}"
        ).lower()]
    return TEMPLATES.TemplateResponse(request, "gestoria_portfolio.html", {
        "account": account, "businesses": businesses, "q": term,
        "pending_total": sum(int(b.get("pending_documents") or 0)
                             for b in businesses),
        "requests_total": sum(int(b.get("open_requests") or 0)
                              for b in businesses),
    })


@router.get("/gestoria/cliente/{business_id}", response_class=HTMLResponse)
def client_detail(request: Request, business_id: int):
    allowed = _business_for(request, business_id)
    if not allowed:
        return RedirectResponse("/gestoria/login", status_code=303)
    account, business = allowed
    documents = docrepo.list_for_business(business_id)
    return TEMPLATES.TemplateResponse(request, "gestoria_client.html", {
        "account": account, "business": business,
        "documents": documents,
        "pending_documents": [d for d in documents
                              if d.get("doc_status") == "pendiente_revisar"],
        "periods": db.gestoria_periods(business_id),
        "requests": db.list_gestoria_requests(business_id),
        "clients": db.list_clients(business_id),
        "projects": db.list_projects(business_id),
    })


@router.get("/gestoria/cliente/{business_id}/documento/{doc_id}")
def document_file(request: Request, business_id: int, doc_id: int):
    if not _business_for(request, business_id):
        return JSONResponse({"error": "no autorizado"}, status_code=403)
    payload = docservice.file_bytes(business_id, doc_id)
    if not payload:
        return JSONResponse({"error": "Documento no encontrado."}, status_code=404)
    data, mime, filename = payload
    safe_name = "".join(char if char.isalnum() or char in " ._-" else "_"
                        for char in filename)[:120]
    return Response(data, media_type=mime, headers={
        "Content-Disposition": f'inline; filename="{safe_name}"',
    })


@router.post("/gestoria/cliente/{business_id}/documento/{doc_id}/revisar")
def review_document(request: Request, business_id: int, doc_id: int,
                    kind: str = Form(""), client_id: str = Form(""),
                    project_id: str = Form(""), review_note: str = Form("")):
    allowed = _business_for(request, business_id)
    if not allowed:
        return JSONResponse({"error": "no autorizado"}, status_code=403)
    if not db.subscription_allows_access(allowed[1]):
        return JSONResponse({"error": "cuenta en modo consulta"}, status_code=402)
    try:
        docrepo.set_context(
            doc_id, business_id, client_id=client_id or None,
            project_id=project_id or None,
        )
        saved = docrepo.set_review(
            doc_id, business_id, kind=kind or None, doc_status="validado",
            review_note=review_note or None,
        )
        if kind:
            docrepo.confirm_classification(doc_id, business_id, kind)
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if not saved:
        return JSONResponse({"error": "Documento no encontrado."}, status_code=404)
    db.record_product_event(business_id, "document_validated_by_gestoria")
    return RedirectResponse(
        f"/gestoria/cliente/{business_id}?ok=reviewed", status_code=303
    )


@router.post("/gestoria/cliente/{business_id}/solicitud")
def request_document(request: Request, business_id: int,
                     message: str = Form("")):
    allowed = _business_for(request, business_id)
    if not allowed:
        return JSONResponse({"error": "no autorizado"}, status_code=403)
    if not db.subscription_allows_access(allowed[1]):
        return JSONResponse({"error": "cuenta en modo consulta"}, status_code=402)
    try:
        db.add_gestoria_request(
            message, requested_by="gestoria", business_id=business_id
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return RedirectResponse(
        f"/gestoria/cliente/{business_id}?ok=requested", status_code=303
    )


@router.get("/gestoria/cliente/{business_id}/paquete/{label}")
def package(request: Request, business_id: int, label: str):
    allowed = _business_for(request, business_id)
    if not allowed:
        return JSONResponse({"error": "no autorizado"}, status_code=403)
    is_demo = bool(allowed[1].get("is_demo"))
    if not is_demo and not db.subscription_allows_access(allowed[1]):
        return JSONResponse({"error": "cuenta en modo consulta"}, status_code=402)
    from .. import gestoria as gestoria_service
    try:
        built = gestoria_service.build_package(
            business_id, label, record_delivery=not is_demo
        )
    except ValueError:
        built = None
    if not built:
        return JSONResponse({"error": "Período no válido."}, status_code=404)
    data, meta = built
    if not is_demo:
        db.mark_gestoria_delivery(business_id, label, "downloaded")
        db.record_product_event(
            business_id, "gestoria_package_downloaded",
            f"label={label};version={meta['version']}",
        )
    return Response(data, media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="noesis-{label}.zip"',
    })
