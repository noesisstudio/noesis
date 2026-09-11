"""Rutas de salud y webhooks."""

from __future__ import annotations

import hmac
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
    # Un token vacío nunca verifica: si faltara la variable, `hub.verify_token=`
    # vacío coincidiría con ella. Comparación en tiempo constante.
    if (
        expected
        and params.get("hub.mode") == "subscribe"
        and hmac.compare_digest(
            params.get("hub.verify_token", "").encode(), expected.encode()
        )
    ):
        return Response(
            content=params.get("hub.challenge", ""), media_type="text/plain"
        )
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


def _stripe_object_id(value) -> str | None:
    if isinstance(value, dict):
        value = value.get("id")
    return str(value) if value else None


def _stripe_metadata(obj: dict) -> dict:
    """Lee metadata de objetos Stripe antiguos y de las versiones recientes."""
    candidates = [
        obj.get("metadata"),
        (obj.get("subscription_details") or {}).get("metadata"),
        ((obj.get("parent") or {}).get("subscription_details") or {}).get("metadata"),
    ]
    merged: dict = {}
    for candidate in candidates:
        if isinstance(candidate, dict):
            merged.update(candidate)
    return merged


def _stripe_subscription_id(obj: dict) -> str | None:
    candidates = [
        obj.get("subscription"),
        (obj.get("subscription_details") or {}).get("subscription"),
        ((obj.get("parent") or {}).get("subscription_details") or {}).get(
            "subscription"
        ),
    ]
    return next(
        (identifier for value in candidates
         if (identifier := _stripe_object_id(value))),
        None,
    )


def _stripe_price_ids(obj: dict) -> list[str]:
    """Extrae precios de suscripciones y facturas en varias versiones de Stripe."""
    identifiers: list[str] = []
    for container_name in ("items", "lines"):
        container = obj.get(container_name) or {}
        for item in container.get("data") or []:
            if not isinstance(item, dict):
                continue
            candidates = [
                item.get("price"),
                ((item.get("pricing") or {}).get("price_details") or {}).get(
                    "price"
                ),
            ]
            for candidate in candidates:
                identifier = _stripe_object_id(candidate)
                if identifier and identifier not in identifiers:
                    identifiers.append(identifier)
    return identifiers


def _stripe_plan(obj: dict, metadata: dict) -> str | None:
    price_ids = _stripe_price_ids(obj)
    for price_id in price_ids:
        if plan := billing_adapter.plan_for_price_id(price_id):
            return plan
    if price_ids:
        # Un precio de suscripción ajeno al catálogo no puede heredar por accidente
        # los permisos del plan anterior. El webhook se reintentará tras corregir
        # el catálogo o el producto de Stripe.
        raise ValueError("El precio de Stripe no pertenece al catálogo de Bynoesis.")
    plan = metadata.get("plan")
    if plan and plan not in billing_adapter.PLANS:
        raise ValueError("Plan de Stripe no reconocido.")
    return plan or None


def _stripe_business(obj: dict, metadata: dict) -> dict | None:
    """Resuelve la cuenta sin permitir cruces entre metadata y customer."""
    raw_bid = metadata.get("business_id") or obj.get("client_reference_id")
    try:
        bid = int(raw_bid) if raw_bid else None
    except (TypeError, ValueError):
        raise ValueError("Identificador de negocio Stripe no valido.") from None
    customer_id = _stripe_object_id(obj.get("customer"))
    by_id = db.get_business(bid) if bid else None
    by_customer = (
        db.get_business_by_stripe_customer(customer_id) if customer_id else None
    )
    if by_id and by_customer and by_id["id"] != by_customer["id"]:
        raise ValueError("El evento de Stripe mezcla dos cuentas.")
    business = by_customer or by_id
    if (
        business
        and business.get("stripe_customer_id")
        and customer_id
        and business["stripe_customer_id"] != customer_id
    ):
        raise ValueError("El cliente de Stripe no coincide con la cuenta.")
    return business


def _apply_stripe_state(
    event: dict,
    obj: dict,
    *,
    status: str,
    priority: int,
    allow_subscription_change: bool = False,
    apply_plan: bool = True,
) -> tuple[dict | None, bool]:
    metadata = _stripe_metadata(obj)
    plan = _stripe_plan(obj, metadata)
    business = _stripe_business(obj, metadata)
    if not business:
        return None, False
    result = db.apply_stripe_subscription_event(
        business["id"],
        status=status,
        event_created_at=event.get("created") or 0,
        event_priority=priority,
        event_id=str(event.get("id") or ""),
        # Checkout solo prepara la relacion con Stripe. El plan vendido no se
        # concede hasta que una suscripcion verificada lo confirme.
        plan=(plan or None) if apply_plan else None,
        customer_id=_stripe_object_id(obj.get("customer")),
        subscription_id=(
            _stripe_object_id(obj.get("id"))
            if str(event.get("type") or "").startswith("customer.subscription.")
            else _stripe_subscription_id(obj)
        ),
        allow_subscription_change=allow_subscription_change,
    )
    return business, bool(result["applied"])


def _apply_stripe_event(event: dict) -> None:
    """Aplica un evento verificado sin confiar en el orden de entrega de Stripe."""
    obj = event.get("data", {}).get("object", {})
    if not isinstance(obj, dict):
        raise ValueError("Objeto Stripe no valido.")
    etype = str(event.get("type") or "")
    business: dict | None = None
    applied = False
    product_event = ""

    if etype == "checkout.session.completed":
        # Completar Checkout no demuestra por si solo que la primera factura este
        # pagada. Conserva los ids, pero la activacion llega con invoice.paid o con
        # una suscripcion que Stripe confirme como active/trialing.
        checkout_business = _stripe_business(obj, _stripe_metadata(obj))
        current_status = str(
            (checkout_business or {}).get("subscription_status") or "pending"
        )
        checkout_status = (
            current_status
            if current_status in {"active", "trialing"}
            or (
                current_status == "trial"
                and db.subscription_allows_access(checkout_business)
            )
            else "pending"
        )
        business, applied = _apply_stripe_state(
            event, obj, status=checkout_status, priority=10,
            allow_subscription_change=True,
            apply_plan=False,
        )
        product_event = "subscription_checkout_completed"
    elif etype in ("customer.subscription.created", "customer.subscription.updated"):
        stripe_status = str(obj.get("status") or "unknown")
        status = {
            "active": "active",
            "trialing": "trialing",
            "past_due": "past_due",
            "unpaid": "unpaid",
            "incomplete": "incomplete",
            "incomplete_expired": "canceled",
            "paused": "paused",
            "canceled": "canceled",
        }.get(stripe_status, "unknown")
        business, applied = _apply_stripe_state(
            event, obj, status=status, priority=40,
            allow_subscription_change=(etype == "customer.subscription.created"),
        )
        product_event = (
            "subscription_active"
            if status in {"active", "trialing"}
            else f"subscription_{status}"
        )
    elif etype == "customer.subscription.deleted":
        business, applied = _apply_stripe_state(
            event, obj, status="canceled", priority=80,
        )
        product_event = "subscription_canceled"
    elif etype in ("invoice.payment_failed", "invoice.payment_action_required"):
        # Una factura aislada no gobierna la suscripcion del SaaS.
        if _stripe_subscription_id(obj):
            status = "incomplete" if etype.endswith("action_required") else "past_due"
            business, applied = _apply_stripe_state(
                event, obj, status=status, priority=50,
            )
            product_event = "subscription_payment_failed"
    elif etype in ("invoice.paid", "invoice.payment_succeeded"):
        if _stripe_subscription_id(obj):
            business, applied = _apply_stripe_state(
                event, obj, status="active", priority=60,
            )
            product_event = "subscription_invoice_paid"

    if business and applied and product_event:
        db.record_product_event(business["id"], product_event)
