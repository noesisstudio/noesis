"""Procesos E QA; solo PostgreSQL local sintético y barreras por pipe."""

import json
import os
import sys
from urllib.parse import urlsplit

from noesis import config, db
from noesis.financial_history.reconciliation import HistoryReconciliation
from noesis.financial_history.importer import HistoryImporter
from noesis.financial_operations.contracts import Principal


def emit(value):
    print(json.dumps(value),flush=True)


def main():
    url = urlsplit(config.DATABASE_URL)
    if url.hostname not in ("localhost","127.0.0.1","::1") or url.path != "/noesis_ci" or config.IS_PRODUCTION:
        raise RuntimeError("Solo fixture PG local /noesis_ci.")
    args = json.loads(sys.argv[1])
    bid, principal = args["business_id"], Principal(args["user_id"],0)
    emit("READY")
    sys.stdin.readline()
    emit("STARTING")
    try:
        service = HistoryReconciliation(bid,page_size=8)
        def checkpoint(step):
            if args.get("hold") and step == args.get("stage","before_freeze"):
                emit("LOCKED")
                if sys.stdin.readline().strip() == "crash":
                    os._exit(73)
        service._checkpoint = checkpoint
        mode = args["mode"]
        if mode == "reconcile":
            emit(service.reconcile(principal,args["epoch_uuid"],args["manifest_uuid"],args["batch_uuid"],args["reconciliation_uuid"]))
        elif mode in ("release","invalidate"):
            result = getattr(HistoryImporter(bid),mode)(principal,args["epoch_uuid"],reason="reconciliation_fixture")
            emit({"state":result["state"]})
        elif mode == "import":
            emit(HistoryImporter(bid).record_item(principal,args["batch_uuid"],args["item_uuid"]))
        elif mode == "live":
            db.add_expense("Fixture","1.00",business_id=bid)
            emit({"state":"wrote"})
    except Exception as error:
        emit({"error":type(error).__name__})


if __name__ == "__main__":
    main()
