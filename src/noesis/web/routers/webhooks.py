"""Rutas de salud y webhooks."""

from __future__ import annotations

import json
import logging
import os

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response

from ... import config, db
from ...adapters import billing as billing_adapter
from .. import whatsapp

router = APIRouter()


@router.get("/health")
def health(request: Request):
    """Liveness para el proveedor cloud: el proceso HTTP esta respondiendo."""
    return {
        "status": "ok",
        "service": "noesis",
        "version": request.app.version,
        "release": config.RELEASE_ID,
    }


@router.get("/ready")
def readiness():
    """Readiness: comprueba que el almacenamiento esta inicializado y accesible."""
    try:
        from ... import migrations

        current = migrations.current_version()
        expected = migrations.LATEST_VERSION
        ready = current == expected
    except db.DatabaseError:
        current = None
        expected = None
        ready = False
    if not ready:
        return JSONResponse(
            {
                "status": "not_ready",
                "release": config.RELEASE_ID,
                "schema": current,
                "expected_schema": expected,
            },
            status_code=503,
        )
    return {
        "status": "ready",
        "release": config.RELEASE_ID,
        "schema": current,
    }


# ============================================================== WEBHOOK ===== #
@router.get("/webhook/whatsapp")
def whatsapp_verify(request: Request):
    # Verificación del webhook de Meta: devuelve el challenge solo si el token coincide.
    params = request.query_params
    expected = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == expected:
        return Response(content=params.get("hub.challenge", ""))
    if not expected and not config.IS_PRODUCTION:
        return Response(content=params.get("hub.challenge", "ok"))
    return JSONResponse({"error": "token inválido"}, status_code=403)


@router.post("/webhook/whatsapp")
async def whatsapp_inbound(request: Request):
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
    try:
        result = await run_in_threadpool(whatsapp.handle_inbound, payload)
    except whatsapp.WebhookInProgress:
        return JSONResponse(
            {"error": "evento todavía en proceso"}, status_code=503
        )
    except Exception:
        logging.getLogger("uvicorn.error").exception(
            "Falló el procesamiento del webhook de WhatsApp."
        )
        return JSONResponse({"error": "procesamiento fallido"}, status_code=500)
    return {"status": "processed", **result}


@router.post("/webhook/stripe")
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
        claimed = db.webhook_event("stripe", event_id) or {}
        if claimed.get("status") == "processing":
            return JSONResponse(
                {"error": "evento todavía en proceso"}, status_code=503
            )
        return {"received": True, "duplicate": True}
    try:
        _apply_stripe_event(event)
    except Exception as exc:
        db.fail_webhook_event("stripe", event_id, str(exc))
        logging.getLogger("uvicorn.error").exception(
            "Falló el procesamiento del webhook de Stripe %s.", event_id
        )
        return JSONResponse({"error": "procesamiento fallido"}, status_code=500)
    db.complete_webhook_event("stripe", event_id)
    return {"received": True}


def _apply_stripe_event(event: dict) -> None:
    """Aplica un evento ya verificado; el endpoint gestiona su ciclo idempotente."""
    obj = event.get("data", {}).get("object", {})
    etype = event.get("type", "")
    bid = (obj.get("metadata") or {}).get("business_id") or obj.get("client_reference_id")
    try:
        bid = int(bid) if bid else None
    except (TypeError, ValueError):
        bid = None
    if etype == "checkout.session.completed" and bid:
        biz = db.get_business(bid)
        if biz:
            db.set_subscription(
                bid,
                "active",
                plan=(obj.get("metadata") or {}).get("plan"),
                customer_id=obj.get("customer"),
                subscription_id=obj.get("subscription"),
            )
            db.record_product_event(bid, "subscription_activated")
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
            if status == "active":
                db.record_product_event(biz["id"], "subscription_active")
    elif etype == "customer.subscription.deleted":
        biz = db.get_business_by_stripe_customer(obj.get("customer"))
        if biz:
            db.set_subscription(biz["id"], "canceled")
    elif etype == "invoice.payment_failed":
        biz = db.get_business_by_stripe_customer(obj.get("customer"))
        if biz:
            db.set_subscription(biz["id"], "past_due")
            db.record_product_event(biz["id"], "subscription_payment_failed")
    elif etype in ("invoice.paid", "invoice.payment_succeeded"):
        biz = db.get_business_by_stripe_customer(obj.get("customer"))
        if biz:
            db.set_subscription(biz["id"], "active")
            db.record_product_event(biz["id"], "subscription_invoice_paid")
