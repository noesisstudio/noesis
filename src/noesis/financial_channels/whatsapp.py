"""Referencia comprobada del mensaje financiero saliente; ninguna autoridad IA."""

from dataclasses import replace
from noesis import db
from noesis.financial_operations.contracts import uuid_text
from .service import FinancialChannels

PREFIX = "financial-review:"


def bind_reply(context, reply_to):
    target = None
    if reply_to:
        outgoing = db.find_whatsapp_message_by_meta_id(reply_to)
        if (
            outgoing
            and outgoing["business_id"] == context.business_id
            and outgoing["to_phone"] == context.actor[3:]
        ):
            key = outgoing.get("idempotency_key") or ""
            if key.startswith(PREFIX):
                op, hash_value = key[len(PREFIX) :].split(":", 1)
                operation = FinancialChannels(context).operations.recover(
                    context.principal, uuid_text(op)
                )
                if operation.request.request_hash != hash_value:
                    raise ValueError("Mensaje financiero de otra revisión.")
                target = (operation.operation_uuid, hash_value, operation.request.expected_revision)
    # La referencia exacta se guarda en el recibo; el texto/quote se hash-ea.
    return replace(context, confirmation_target=target, reply_to=reply_to or "")


def review_key(response):
    if (
        response.get("confirmation_required")
        and response.get("operation_uuid")
        and response.get("request_hash")
    ):
        return PREFIX + response["operation_uuid"] + ":" + response["request_hash"]
    return None
