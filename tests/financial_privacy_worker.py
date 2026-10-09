"""Crashes E de procesos reales, exclusivamente PostgreSQL sintético loopback."""

import json
import os
import sys
from urllib.parse import urlsplit

from noesis import config, db
from noesis.financial_operations.contracts import Principal
from noesis.financial_privacy.closure import FinancialClosure


def main():
    target = urlsplit(config.DATABASE_URL)
    if target.hostname not in ("127.0.0.1", "localhost", "::1") or target.path != "/noesis_ci" or config.IS_PRODUCTION:
        raise RuntimeError("Worker E limitado a noesis_ci sintético local.")
    args = json.loads(sys.argv[1])
    from noesis.financial_history.service import FLAGS
    if any(getattr(config, name) for name in FLAGS):
        raise RuntimeError("Cinco flags OFF requeridos.")
    api = FinancialClosure(args["business_id"])
    principal = Principal(args["user_id"], args["session_version"])
    def checkpoint(point, session):
        if point == args["crash_point"]:
            os._exit(17)
    if args["action"] == "plan":
        result = api.plan(principal, args["plan_uuid"], privacy_request_id=args["privacy_request_id"],
                          policy_uuid=args["policy_uuid"], checkpoint=checkpoint)
    elif args["action"] == "authorize":
        result = api.authorize(principal, args["plan_uuid"], approved_hash=args["approved_hash"], checkpoint=checkpoint)
    else:
        result = api.apply(principal, args["plan_uuid"], authorization_uuid=args["authorization_uuid"], checkpoint=checkpoint)
    print(json.dumps({"result": result.get("final_state", "committed")}), flush=True)
    db.close_pool()


if __name__ == "__main__":
    main()
