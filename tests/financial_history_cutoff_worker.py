"""Procesos independientes de QA; stdout de barreras, sin proveedores ni datos reales."""

from datetime import datetime, timezone
import json
import sys

from noesis import db
from noesis.core.persistence import FinancialSession
from noesis.financial_history.cutoff import HistoryCutoff
from noesis.financial_history.fence import assert_writable
from noesis.financial_operations.contracts import Principal


def emit(value):
    print(json.dumps(value), flush=True)


def main():
    args = json.loads(sys.argv[1])
    bid = args["business_id"]
    principal = Principal(args["user_id"], 0)
    emit("READY")
    sys.stdin.readline()
    try:
        mode = args["mode"]
        if mode == "hold":
            with db.get_conn() as conn:
                conn.execute("BEGIN IMMEDIATE")
                assert_writable(conn, bid)
                conn.execute(
                    "INSERT INTO expenses (business_id,concept,amount,spent_on,created_at) VALUES (?,'fixture process',10,'2026-10-04','2026-10-04T00:00:00')",
                    (bid,),
                )
                emit("LOCKED")
                command = sys.stdin.readline().strip()
                before = datetime.now(timezone.utc).isoformat()
                if command == "rollback":
                    conn.rollback()
            emit({"result": "writer_finished", "before_commit": before})
        elif mode == "open":
            emit("OPENING")
            epoch = HistoryCutoff(bid).open(
                principal,
                args["epoch_uuid"],
                repository_version="fixture-code",
                environment_identity="synthetic-local",
            )
            emit({"result": "opened", "t0": str(epoch["t0"]), "generation": epoch["generation"]})
        elif mode == "release":
            emit("RELEASING")
            epoch = HistoryCutoff(bid).release(principal, args["epoch_uuid"], reason="race_end")
            emit({"result": "released", "generation": epoch["generation"]})
        elif mode == "operations":
            from noesis.financial_operations.service import FinancialOperations

            FinancialOperations(bid).recover(principal, args["operation_uuid"])
            emit({"result": "recovered"})
        elif mode == "ee_gate":
            from noesis.economic_events.service import EconomicEvents

            with db.get_conn() as conn:
                EconomicEvents(FinancialSession(conn), bid).append(principal, None)
            emit({"result": "wrote"})
        elif mode == "revoke":
            emit("REVOKING")
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE users SET session_version=session_version+1 WHERE business_id=? AND id=?",
                    (bid, principal.user_id),
                )
            emit({"result": "revoked"})
        elif mode == "capture":
            from noesis.invoice_capture.service import InvoiceCapture
            from noesis.payment_capture.service import PaymentCapture
            from noesis.bank_capture.service import BankCapture
            from noesis.purchasing_capture import SupplierInvoiceCapture, ExpenseCapture

            services = {
                "InvoiceCapture": InvoiceCapture,
                "PaymentCapture": PaymentCapture,
                "BankCapture": BankCapture,
                "SupplierInvoiceCapture": SupplierInvoiceCapture,
                "ExpenseCapture": ExpenseCapture,
            }
            services[args["capture"]](bid).execute(principal, args["operation_uuid"])
            emit({"result": "wrote"})
        elif mode == "ee":
            from noesis.economic_events.service import EconomicEvents

            with db.get_conn() as conn:
                conn.execute("BEGIN IMMEDIATE")
                service = EconomicEvents(FinancialSession(conn), bid)
                service.append(principal, service.read(principal, args["event_uuid"]).event)
            emit({"result": "wrote"})
        elif mode == "sql":
            with db.get_conn() as conn:
                conn.execute(
                    "INSERT INTO expenses (business_id,concept,amount,spent_on,created_at) VALUES (?,'SQL fixture',10,'2026-10-04','2026-10-04T00:00:00')",
                    (bid,),
                )
            emit({"result": "wrote"})
        else:
            db.add_expense("fixture process", "10.00", business_id=bid)
            emit({"result": "wrote"})
    except Exception as exc:
        emit({"error": type(exc).__name__})


if __name__ == "__main__":
    main()
