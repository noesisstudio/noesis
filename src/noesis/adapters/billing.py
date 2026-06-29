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

PLAN_PRICES = {"autonomo": 29, "pro": 39}


class BillingProvider(Protocol):
    def available(self) -> bool: ...
    def checkout_url(self, business: dict, plan: str,
                     success_url: str, cancel_url: str) -> str | None: ...
    def portal_url(self, business: dict, return_url: str) -> str | None: ...


def _price_id(plan: str) -> str:
    return {"autonomo": config.STRIPE_PRICE_AUTONOMO,
            "pro": config.STRIPE_PRICE_PRO}.get(plan, "")


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

    def checkout_url(self, business, plan, success_url, cancel_url) -> str | None:
        price = _price_id(plan)
        if not price:
            log.error("Falta STRIPE_PRICE_%s para crear el checkout.", plan.upper())
            return None
        data = {
            "mode": "subscription",
            "line_items[0][price]": price,
            "line_items[0][quantity]": 1,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "client_reference_id": str(business["id"]),
            "metadata[business_id]": str(business["id"]),
            "metadata[plan]": plan,
            "subscription_data[metadata][business_id]": str(business["id"]),
        }
        if business.get("stripe_customer_id"):
            data["customer"] = business["stripe_customer_id"]
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


class ManualBillingProvider:
    """Sin Stripe: no hay pago automático; el alta queda en prueba."""

    def available(self) -> bool:
        return False

    def checkout_url(self, business, plan, success_url, cancel_url) -> str | None:
        return None

    def portal_url(self, business, return_url) -> str | None:
        return None


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
    parts = dict(p.split("=", 1) for p in sig_header.split(",") if "=" in p)
    ts, v1 = parts.get("t"), parts.get("v1")
    if not ts or not v1:
        return None
    if abs(time.time() - int(ts)) > 300:  # rechaza eventos viejos (anti-replay)
        return None
    signed = f"{ts}.".encode() + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, v1):
        return None
    return json.loads(payload.decode())
