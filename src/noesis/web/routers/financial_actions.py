"""API de revisión humana autenticada; ningún dispatch arbitrario de ejecutores."""

from dataclasses import replace
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from noesis import config
from noesis.bank_capture.service import BankCapture
from noesis.financial_channels import ChannelContext, FinancialChannels
from noesis.financial_operations.contracts import (
    AccessDenied,
    EntryIdentity,
    Principal,
    strict_json,
)
from noesis.web.deps import _read_json

router = APIRouter()


def context(request, bid, action_uuid):
    return ChannelContext.web(
        bid, Principal(request.session["uid"], request.session.get("sv", 0)), action_uuid
    )


async def body_exact(request):
    await _read_json(request)  # Tamaño y objeto; el segundo parse rechaza floats/duplicados.
    return strict_json((await request.body()).decode("utf-8"))


def error(exc):
    return JSONResponse(
        {"error": str(exc)}, status_code=403 if isinstance(exc, PermissionError) else 409
    )


@router.post("/api/{business_id}/financial-actions/prepare")
async def prepare(business_id: int, request: Request):
    try:
        if not config.FINANCIAL_CORE_ENABLED:
            raise AccessDenied("El Financial Core permanece apagado.")
        body = await body_exact(request)
        if set(body) - {"action_uuid", "intent", "document_review"} or not {
            "action_uuid",
            "intent",
        } <= set(body):
            raise ValueError("Acción UUID e intención cerrada requeridas.")
        ctx = context(request, business_id, body["action_uuid"])
        intent = body["intent"]
        if "document_review" in body:
            review = body["document_review"]
            if set(review) != {"review_uuid", "document_id", "item", "revision"}:
                raise ValueError("Revisión documental UUID/documento/item/revisión requerida.")
            if (
                intent["command"] not in {"supplier_invoice.confirm", "expense.confirm"}
                or intent["fields"].get("document_id") != review["document_id"]
            ):
                raise ValueError("Documento e intención no coinciden.")
            ctx = replace(
                ctx,
                identity=EntryIdentity.reviewed_document(
                    review["review_uuid"], review["document_id"], review["item"], review["revision"]
                ),
                transport_identity=ctx.identity,
            )
        return await run_in_threadpool(
            lambda: FinancialChannels(ctx).propose(intent)
        )
    except (ValueError, TypeError, KeyError, PermissionError) as exc:
        return error(exc)


@router.post("/api/{business_id}/financial-actions/confirm")
async def confirm(business_id: int, request: Request):
    try:
        if not config.FINANCIAL_CORE_ENABLED:
            raise AccessDenied("El Financial Core permanece apagado.")
        body = await body_exact(request)
        if set(body) != {"action_uuid", "operation_uuid", "request_hash", "revision", "decision"}:
            raise ValueError("Confirmación cerrada de la propuesta exacta requerida.")
        ctx = context(request, business_id, body["action_uuid"])
        return await run_in_threadpool(
            lambda: FinancialChannels(ctx).confirm(
                body["operation_uuid"],
                approved_hash=body["request_hash"],
                approved_revision=body["revision"],
                decision=body["decision"],
            )
        )
    except (ValueError, TypeError, KeyError, PermissionError) as exc:
        return error(exc)


@router.get("/api/{business_id}/financial-actions/{operation_uuid}")
def recover(business_id: int, operation_uuid: str, request: Request):
    try:
        # Consulta, jamás ejecuta ni vuelve a autorizar.
        ctx = context(request, business_id, "00000000-0000-4000-8000-000000000001")
        bridge = FinancialChannels(ctx)
        return bridge.response(bridge.operations.recover(ctx.principal, operation_uuid))
    except (ValueError, TypeError, PermissionError) as exc:
        return error(exc)


@router.post("/api/{business_id}/financial-actions/bank-csv")
async def bank_csv(business_id: int, request: Request):
    try:
        if not config.FINANCIAL_CORE_ENABLED:
            raise AccessDenied("El Financial Core permanece apagado.")
        body = await body_exact(request)
        if set(body) != {"batch_uuid", "account_scope", "content"}:
            raise ValueError("Batch UUID, cuenta y CSV requeridos; subir no autoriza.")
        if not isinstance(body["content"], str):
            raise ValueError("El CSV debe ser texto.")
        ctx = context(request, business_id, body["batch_uuid"])

        def review_rows():
            rows = BankCapture(business_id).review_csv(
                ctx.principal,
                body["content"].encode(),
                batch_uuid=body["batch_uuid"],
                account_scope=body["account_scope"],
            )
            result = []
            for identity, reviewed in rows:
                p = reviewed.parameters
                fields = dict(p["movement"]) | {
                    "batch_uuid": p["batch"],
                    "row_key": p["row"],
                    "account_scope": p["account_scope"],
                    "statement_hash": p["statement_hash"],
                    "distinct_reason": p["distinct_reason"],
                }
                row_ctx = replace(ctx, identity=identity)
                result.append(
                    FinancialChannels(row_ctx).propose(
                        {"command": "bank_transaction.import", "target_id": None, "fields": fields}
                    )
                )
            return {"rows": result, "confirmation_required": True}

        return await run_in_threadpool(review_rows)
    except (ValueError, TypeError, KeyError, PermissionError) as exc:
        return error(exc)
