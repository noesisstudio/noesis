"""Proceso de prueba: solo PostgreSQL local/noesis_ci y tabla sintética aislada."""

import json
import os
import sys
from urllib.parse import urlsplit
from uuid import uuid4

from noesis import config, db
from noesis.financial_operations.contracts import (
    ConflictError, EntryIdentity, FinancialRequest, Principal,
)
from noesis.financial_operations.service import FinancialOperations


def main():
    url = urlsplit(config.DATABASE_URL)
    if url.hostname not in {"localhost", "127.0.0.1", "::1"} or url.path != "/noesis_ci" or config.IS_PRODUCTION:
        raise RuntimeError("Worker de pruebas exclusivamente local descartable.")
    args = json.loads(sys.argv[1])
    principal = Principal(args["user_id"], 0)
    service = FinancialOperations(args["business_id"])
    print("READY", flush=True)
    if sys.stdin.readline().strip() != "go":
        raise RuntimeError("Falta barrera de prueba.")
    def effect(session, request):
        session.execute("INSERT INTO phase12_test_effects VALUES (?, ?, ?)",
                        (str(uuid4()), args["business_id"], request.amount))
        if args["mode"] == "crash":
            os._exit(17)
        return {"resource_id": 1, "amount": request.amount, "currency": "EUR"}
    try:
        if args["mode"] == "prepare":
            request = FinancialRequest.from_canonical(args["request"])
            op = service.prepare(principal, EntryIdentity.web_api(args["entry_uuid"]), request)
        else:
            op = service.execute(principal, args["operation_uuid"], effect)
        print(json.dumps({"operation_uuid": op.operation_uuid, "state": op.state.value,
                          "amount": None if op.result is None else op.result["amount"]}), flush=True)
    except ConflictError:
        print(json.dumps({"conflict": True}), flush=True)
    finally:
        db.close_pool()


if __name__ == "__main__":
    main()
