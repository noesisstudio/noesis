"""Adaptador cerrado de intención; la IA no recibe identidad ni aprobación."""

import re

from noesis import db
from noesis.financial_operations.contracts import (
    AccessDenied,
    OperationState,
    StateError,
    canonical_json,
)
from .service import FinancialChannels, current

CAPTURED_TOOLS = {"enviar_factura", "registrar_pago", "registrar_gasto"}


def propose_tool(bid, name, args):
    context = current.get()
    if context is None or context.business_id != bid:
        raise AccessDenied("Esta acción necesita un mensaje autenticado y revisión financiera.")
    allowed = {
        "enviar_factura": {"factura_id"},
        "registrar_pago": {"factura_id"},
        "registrar_gasto": {"concepto", "importe", "iva", "categoria", "proyecto_id"},
    }[name]
    if set(args) - allowed:
        raise ValueError("La herramienta no admite identidad, autoridad ni campos adicionales.")
    args = dict(args)
    # El NLU histórico devuelve float. Solo recuperar el lexema monetario del
    # mensaje humano original, nunca convertir el float del modelo en dinero.
    if name == "registrar_gasto" and isinstance(args.get("importe"), float):
        tokens = re.findall(
            r"(?<![\w.,])([0-9]+(?:[.,][0-9]{1,2})?)\s*(?:€|euros?\b)", context.message, re.I
        )
        if len(tokens) != 1:
            raise ValueError("Indica un único importe decimal en euros para revisarlo.")
        args["importe"] = tokens[0].replace(",", ".")
    canonical_json(args)
    if name == "enviar_factura":
        invoice = db.get_invoice(args["factura_id"], bid)
        command = (
            "invoice.rectify"
            if invoice and str(invoice["invoice_type"]).startswith("R")
            else "invoice.issue"
        )
        intent = {"command": command, "target_id": args["factura_id"], "fields": {}}
    elif name == "registrar_pago":
        intent = {
            "command": "customer_payment.record",
            "target_id": args["factura_id"],
            "fields": {"mode": "remaining"},
        }
    else:
        fields = {
            dest: args[src]
            for src, dest in (
                ("concepto", "concept"),
                ("importe", "amount"),
                ("iva", "vat_rate"),
                ("categoria", "category"),
                ("proyecto_id", "project_id"),
            )
            if src in args
        }
        intent = {"command": "expense.confirm", "target_id": None, "fields": fields}
    result = FinancialChannels(context).propose(intent, pending_actor=context.actor)
    from noesis import action_review

    state = action_review.context.get()
    if state is not None:
        state["proposal"] = result
    return result


def respond(bid, actor, text):
    """Confirmación ligada al pending exacto; corrección produce otro request."""
    from noesis import nlu
    from noesis.financial_operations.contracts import strict_json

    context = current.get()
    pending = db.get_pending_action(bid, actor)
    norm = nlu._norm(text)
    yes, no = nlu.es_confirmacion(text), norm in {"no", "descartar", "cancelar", "ahora no"}
    if (
        context
        and context.business_id == bid
        and context.actor == actor
        and context.confirmation_target
        and (yes or no)
    ):
        op, request_hash, revision = context.confirmation_target
        bridge = FinancialChannels(context)
        recovered = bridge.operations.recover(context.principal, op)
        if (
            recovered.request.request_hash != request_hash
            or recovered.request.expected_revision != revision
        ):
            raise StateError("Referencia de otra revisión.")
        # Otro SÍ citado recupera la misma aprobación; no consume otro pending.
        if yes and recovered.state in {OperationState.APPROVED, OperationState.COMMITTED}:
            return bridge.confirm(op, approved_hash=request_hash, approved_revision=revision)
        if no and recovered.state == OperationState.REJECTED:
            return bridge.confirm(
                op, approved_hash=request_hash, approved_revision=revision, decision="no"
            )
    if not pending or pending["kind"] != "financial_capture":
        if context and context.confirmation_target and (yes or no):
            raise StateError("La propuesta indicada ya no está pendiente. Revisa otra vez.")
        return None
    if context is None or context.business_id != bid or context.actor != actor:
        raise AccessDenied("Falta contexto autenticado de esta conversación.")
    bridge = FinancialChannels(context)
    payload = strict_json(pending["payload"])
    if yes or no:
        target = context.confirmation_target
        expected = (payload["operation_uuid_ref"], payload["request_hash"], payload["revision"])
        if target != expected:
            raise StateError(
                "Esta confirmación no identifica la propuesta mostrada. Vuelve a abrirla; en WhatsApp responde citándola."
            )
        return bridge.confirm(
            payload["operation_uuid_ref"],
            approved_hash=payload["request_hash"],
            approved_revision=payload["revision"],
            decision="yes" if yes else "no",
            pending_actor=actor,
            pending_id=pending["id"],
        )
    correction = re.fullmatch(
        r"(?:s[ií],?\s*pero\s+)?(?:no,?\s*)?(?:son|eran|es|importe|corregir:?)\s+([0-9]+(?:[.,][0-9]{1,2})?)\s*(?:€|euros?)?",
        text.strip(),
        re.I,
    )
    if correction:
        if context.confirmation_target != (
            payload["operation_uuid_ref"],
            payload["request_hash"],
            payload["revision"],
        ):
            raise StateError("Corrige la propuesta mostrada; en WhatsApp responde citándola.")
        with bridge.operations._transaction(context.principal, write=False) as (session, _):
            intent = strict_json(
                bridge._link(session, payload["operation_uuid_ref"])["intent_canonical"]
            )
        command = intent["command"]
        if command not in {
            "customer_payment.record",
            "expense.confirm",
            "supplier_invoice.confirm",
        }:
            return {
                "reply": "Corrige primero el borrador y solicita otra revisión. No he emitido nada.",
                "source": "local",
            }
        intent["fields"]["total" if command == "supplier_invoice.confirm" else "amount"] = (
            correction[1].replace(",", ".")
        )
        if command == "customer_payment.record":
            intent["fields"]["mode"] = "partial"
        return bridge.propose(
            intent,
            pending_actor=actor,
            expected_pending_id=pending["id"],
            replaces=payload["operation_uuid_ref"],
        )
    return None


def legacy_financial_path(path, method):
    """Endpoints anteriores sin contrato de confirmación: bloquear antes de parsear."""
    if method not in {"POST", "PATCH", "DELETE"}:
        return False
    suffix = re.sub(r"^/api/[0-9]+", "", path)
    return bool(
        re.fullmatch(
            r"/(?:invoices/[0-9]+/(?:send|pay|payments|cancel-verifactu)|expenses(?:/[0-9]+)?|received-invoices(?:/[0-9]+)?|documents/[0-9]+/to-expense|bank-import|bank-transactions/[0-9]+/confirm)",
            suffix,
        )
    )
