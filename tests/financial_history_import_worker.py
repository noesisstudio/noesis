"""Procesos QA1.9D con barreras reales; bases locales sintéticas exclusivamente."""

import json
import sys
from urllib.parse import urlsplit

from noesis import config, db
from noesis.financial_history.importer import HistoryImporter
from noesis.financial_operations.contracts import Principal


def emit(value):
    print(json.dumps(value), flush=True)


def main():
    if config.DATABASE_URL:
        url = urlsplit(config.DATABASE_URL)
        if (
            url.hostname not in ("localhost", "127.0.0.1", "::1")
            or url.path != "/noesis_ci"
            or config.IS_PRODUCTION
        ):
            raise RuntimeError("Solo PG sintético local.")
    args = json.loads(sys.argv[1])
    bid = args["business_id"]
    principal = Principal(args["user_id"], 0)
    importer = HistoryImporter(bid)
    emit("READY")
    sys.stdin.readline()
    mode = args["mode"]
    emit("STARTING")
    try:
        if mode == "import":
            if args.get("hold"):

                def checkpoint(step):
                    if step == args.get("stage", "authorization"):
                        emit("LOCKED")
                        if sys.stdin.readline().strip() == "crash":
                            import os

                            os._exit(73)

                importer._checkpoint = checkpoint
            result = importer.record_item(principal, args["batch_uuid"], args["item_uuid"])
            emit(result)
        elif mode in ("release", "invalidate"):
            result = getattr(importer, mode)(
                principal, args["epoch_uuid"], reason="import_fixture_race"
            )
            emit({"state": result["state"]})
        elif mode == "sql":
            with db.get_conn() as conn:
                conn.execute(
                    "INSERT INTO expenses (business_id,concept,amount,spent_on,created_at) VALUES (?,'sql fixture',1,'2026-09-01','2026-09-01T00:00:00')",
                    (bid,),
                )
            emit({"state": "wrote"})
        elif mode == "live":
            db.add_expense("fixture", "1.00", business_id=bid)
            emit({"state": "wrote"})
    except Exception as error:
        emit({"error": type(error).__name__})


if __name__ == "__main__":
    main()
