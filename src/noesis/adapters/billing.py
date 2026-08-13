"""Adaptador de cobro de la suscripción (Stripe), solo stdlib (urllib).

No añadimos la librería oficial de Stripe para mantener Noesis ligero: hablamos con
la API REST de Stripe por HTTPS. Dos implementaciones:

  - StripeBillingProvider -> Checkout real cuando hay STRIPE_SECRET_KEY.
  - ManualBillingProvider -> sin Stripe: el alta entra en PRUEBA gratuita y el cobro
                             se gestiona a mano (útil en local y en los primeros
                             pilotos antes de activar Stripe).

Se activa poniendo STRIPE_SECRET_KEY + los price_id en el entorno.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import urllib.parse
import urllib.request
from typing import Protocol

from .. import config

log = logging.getLogger("noesis.billing")
_API = "https://api.stripe.com/v1"

# Catálogo de planes: fuente única de verdad. El precio se comunica siempre + IVA;
# el modelo reproducible y sus márgenes están en docs/Unit-economics-y-cerebro-interno.md.
PLANS = {
    "autonomo": {"name": "Autónomo", "price": 29, "credits": 75},
    "pro": {"name": "Negocio", "price": 49, "credits": 300},
    "premium": {"name": "Premium", "price": 99, "credits": 1500},
}
PLAN_PRICES = {key: plan["price"] for key, plan in PLANS.items()}
ANNUAL_MONTHS_CHARGED = 11
PLAN_ANNUAL_PRICES = {
    key: price * ANNUAL_MONTHS_CHARGED for key, price in PLAN_PRICES.items()
}
PLAN_ANNUAL_SAVINGS = {
    key: price * (12 - ANNUAL_MONTHS_CHARGED) for key, price in PLAN_PRICES.items()
}

# Capacidades vendidas por plan. La prueba y la demo muestran el producto completo;
# una cuenta de pago recibe solo lo contratado. Mantener este catálogo en servidor
# evita que ocultar un botón sea el único control comercial.
ENTITLEMENT_PROJECTS = "projects"
ENTITLEMENT_TEAM = "team"
ENTITLEMENT_GESTORIA = "gestoria"
ENTITLEMENT_ADVANCED_ANALYSIS = "advanced_analysis"
ENTITLEMENTS = frozenset({
    ENTITLEMENT_PROJECTS,
    ENTITLEMENT_TEAM,
    ENTITLEMENT_GESTORIA,
    ENTITLEMENT_ADVANCED_ANALYSIS,
})
PLAN_ENTITLEMENTS = {
    "autonomo": frozenset(),
    "pro": ENTITLEMENTS,
    "premium": ENTITLEMENTS,
}
ENTITLEMENT_MINIMUM_PLAN = {
    ENTITLEMENT_PROJECTS: "pro",
    ENTITLEMENT_TEAM: "pro",
    ENTITLEMENT_GESTORIA: "pro",
    ENTITLEMENT_ADVANCED_ANALYSIS: "pro",
}
ENTITLEMENT_LABELS = {
    ENTITLEMENT_PROJECTS: "Proyectos, costes y rentabilidad",
    ENTITLEMENT_TEAM: "Equipo y registro de jornada",
    ENTITLEMENT_GESTORIA: "Gestoría conectada",
    ENTITLEMENT_ADVANCED_ANALYSIS: "Análisis financiero avanzado",
}


def effective_plan(business: dict | None) -> str:
    """Devuelve el nivel aplicable sin convertir datos heredados en acceso total."""
    if not business:
        return "autonomo"
    if business.get("is_demo") or business.get("subscription_status") == "trial":
        return "premium"
    plan = str(business.get("plan") or "")
    return plan if plan in PLAN_ENTITLEMENTS else "autonomo"


def entitlements_for(business: dict | None) -> frozenset[str]:
    return PLAN_ENTITLEMENTS[effective_plan(business)]


def has_entitlement(business: dict | None, entitlement: str) -> bool:
    if entitlement not in ENTITLEMENTS:
        return False
    return entitlement in entitlements_for(business)


def minimum_plan_for(entitlement: str) -> str:
    return ENTITLEMENT_MINIMUM_PLAN.get(entitlement, "premium")


class BillingProvider(Protocol):
    def available(self) -> bool: ...
    def checkout_url(self, business: dict, plan: str,
                     success_url: str, cancel_url: str,
                     billing_period: str = "monthly") -> str | None: ...
    def portal_url(self, business: dict, return_url: str) -> str | None: ...
    def subscription_snapshot(self, business: dict) -> dict | None: ...


def _price_id(plan: str, billing_period: str = "monthly") -> str:
    catalog = {
        "monthly": {
            "autonomo": config.STRIPE_PRICE_AUTONOMO,
            "pro": config.STRIPE_PRICE_PRO,
            "premium": config.STRIPE_PRICE_PREMIUM,
        },
        "annual": {
            "autonomo": config.STRIPE_PRICE_AUTONOMO_ANNUAL,
            "pro": config.STRIPE_PRICE_PRO_ANNUAL,
            "premium": config.STRIPE_PRICE_PREMIUM_ANNUAL,
        },
    }
    return catalog.get(billing_period, {}).get(plan, "")


def plan_for_price_id(price_id: str | None) -> str | None:
    """Resuelve el plan contratado desde el catálogo configurado en Stripe."""
    if not price_id:
        return None
    for billing_period in ("monthly", "annual"):
        for plan in PLANS:
            if _price_id(plan, billing_period) == price_id:
                return plan
    return None


class StripeBillingProvider:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    def available(self) -> bool:
        return True

    def _post(self, path: str, data: dict) -> dict:
        body = urllib.parse.urlencode(data, doseq=True).encode()
        req = urllib.request.Request(f"{_API}/{path}", data=body, method="POST")
        req.add_header("Authorization", f"Bearer {self.secret_key}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())

    def _get(self, path: str) -> dict:
        req = urllib.request.Request(f"{_API}/{path}", method="GET")
        req.add_header("Authorization", f"Bearer {self.secret_key}")
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())

    def checkout_url(self, business, plan, success_url, cancel_url,
                     billing_period="monthly") -> str | None:
        price = _price_id(plan, billing_period)
        if not price:
            log.error(
                "Falta el precio Stripe para plan=%s periodo=%s.",
                plan, billing_period,
            )
            return None
        data = {
            "mode": "subscription",
            "line_items[0][price]": price,
            "line_items[0][quantity]": 1,
            "automatic_tax[enabled]": (
                "true" if config.STRIPE_AUTOMATIC_TAX else "false"
            ),
            "tax_id_collection[enabled]": "true",
            "billing_address_collection": "required",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "client_reference_id": str(business["id"]),
            "metadata[business_id]": str(business["id"]),
            "metadata[plan]": plan,
            "metadata[billing_period]": billing_period,
            "subscription_data[metadata][business_id]": str(business["id"]),
            "subscription_data[metadata][plan]": plan,
            "subscription_data[metadata][billing_period]": billing_period,
        }
        if business.get("stripe_customer_id"):
            data["customer"] = business["stripe_customer_id"]
            data["customer_update[address]"] = "auto"
            data["customer_update[name]"] = "auto"
        elif business.get("owner_email"):
            data["customer_email"] = business["owner_email"]
        try:
            return self._post("checkout/sessions", data).get("url")
        except Exception as e:  # noqa: BLE001
            log.error("Stripe checkout falló: %s", e)
            return None

    def portal_url(self, business, return_url) -> str | None:
        cid = business.get("stripe_customer_id")
        if not cid:
            return None
        try:
            return self._post("billing_portal/sessions",
                              {"customer": cid, "return_url": return_url}).get("url")
        except Exception as e:  # noqa: BLE001
            log.error("Stripe portal falló: %s", e)
            return None


    def subscription_snapshot(self, business: dict) -> dict | None:
        """Consulta la suscripcion enlazada sin confiar en datos del navegador."""
        subscription_id = str(business.get("stripe_subscription_id") or "")
        if not subscription_id:
            return None
        try:
            safe_id = urllib.parse.quote(subscription_id, safe="")
            return self._get(f"subscriptions/{safe_id}")
        except Exception as e:  # noqa: BLE001
            log.error("Stripe no pudo reconciliar la suscripcion: %s", e)
            return None


class ManualBillingProvider:
    """Sin Stripe: no hay pago automático; el alta queda en prueba."""

    def available(self) -> bool:
        return False

    def checkout_url(self, business, plan, success_url, cancel_url,
                     billing_period="monthly") -> str | None:
        return None

    def portal_url(self, business, return_url) -> str | None:
        return None

    def subscription_snapshot(self, business: dict) -> dict | None:
        return None


def subscription_evidence(
    business: dict, snapshot: dict | None,
) -> dict | None:
    """Valida una lectura autenticada de Stripe antes de conceder el plan."""
    if not isinstance(snapshot, dict):
        return None
    subscription_id = str(snapshot.get("id") or "")
    expected_subscription = str(business.get("stripe_subscription_id") or "")
    if not subscription_id or subscription_id != expected_subscription:
        return None
    customer_id = str(snapshot.get("customer") or "")
    expected_customer = str(business.get("stripe_customer_id") or "")
    if not customer_id or (expected_customer and customer_id != expected_customer):
        return None
    metadata = snapshot.get("metadata") or {}
    if not isinstance(metadata, dict):
        return None
    if str(metadata.get("business_id") or "") != str(business.get("id") or ""):
        return None
    status = str(snapshot.get("status") or "")
    if status not in {"active", "trialing"}:
        return None
    price_ids: list[str] = []
    for item in ((snapshot.get("items") or {}).get("data") or []):
        if not isinstance(item, dict):
            continue
        price = item.get("price")
        price_id = str(price.get("id") if isinstance(price, dict) else price or "")
        if price_id:
            price_ids.append(price_id)
    plans = {plan_for_price_id(price_id) for price_id in price_ids}
    plans.discard(None)
    if len(plans) != 1:
        return None
    return {
        "status": status,
        "plan": plans.pop(),
        "customer_id": customer_id,
        "subscription_id": subscription_id,
    }


def get_provider() -> BillingProvider:
    if config.STRIPE_SECRET_KEY:
        return StripeBillingProvider(config.STRIPE_SECRET_KEY)
    return ManualBillingProvider()


def verify_webhook(payload: bytes, sig_header: str) -> dict | None:
    """Verifica la firma del webhook de Stripe (esquema t=..,v1=..) con stdlib y
    devuelve el evento si es válido. Sin secreto configurado, devuelve None."""
    secret = config.STRIPE_WEBHOOK_SECRET
    if not secret or not sig_header:
        return None
    parts = [p.split("=", 1) for p in sig_header.split(",") if "=" in p]
    ts = next((value for key, value in parts if key == "t"), None)
    signatures = [value for key, value in parts if key == "v1"]
    if not ts or not signatures:
        return None
    try:
        timestamp = int(ts)
    except ValueError:
        return None
    if abs(time.time() - timestamp) > 300:  # rechaza eventos viejos (anti-replay)
        return None
    signed = f"{ts}.".encode() + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, signature) for signature in signatures):
        return None
    try:
        event = json.loads(payload.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return event if isinstance(event, dict) else None
