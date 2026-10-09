"""Carreras/crash C de procesos sintéticos: solo localhost/noesis_ci."""

from contextlib import ExitStack
import json
import os
import sys
from unittest.mock import patch
from urllib.parse import urlsplit

from noesis import config, db
from noesis.core.persistence import FinancialSession
from noesis.economic_events.service import EconomicEvents
from noesis.financial_history.service import FLAGS
from noesis.financial_operations.contracts import Principal, StateError, OperationState
from noesis.financial_operations.repository import OperationsRepository
from noesis.financial_writers import invoices
from noesis.financial_writers.boundary import WriterConnection
from noesis.fiscal_cancellation_capture import FiscalCancellationCapture


def main():
    url = urlsplit(config.DATABASE_URL)
    if url.hostname not in {"localhost", "127.0.0.1", "::1"} or url.path != "/noesis_ci" or config.IS_PRODUCTION:
        raise RuntimeError("Solo PostgreSQL sintético local.")
    args = json.loads(sys.argv[1])
    point = args.get("point")
    writer, execute, append, transition, commit = (
        WriterConnection.execute, FinancialSession.execute, EconomicEvents.append,
        OperationsRepository.transition, db.Connection.commit,
    )

    def write(conn, sql, params=()):
        result = writer(conn, sql, params)
        if (point == "after_record" and sql.startswith("INSERT INTO invoice_cancellation_records")
                or point == "after_outbox" and sql.startswith("INSERT INTO verifactu_cancellation_outbox")):
            os._exit(17)
        return result

    def sql(session, statement, params=()):
        result = execute(session, statement, params)
        if point == "after_coverage" and statement.startswith("INSERT INTO invoice_fiscal_cancellation_coverage"):
            os._exit(17)
        return result

    def event(*a, **kw):
        result = append(*a, **kw)
        if point == "after_event":
            os._exit(17)
        return result

    def finish(repo, row, state, *a, **kw):
        if point == "before_result" and state == OperationState.COMMITTED:
            os._exit(17)
        return transition(repo, row, state, *a, **kw)

    def committed(conn):
        result = commit(conn)
        if point == "after_commit":
            os._exit(17)
        return result

    with ExitStack() as stack:
        stack.enter_context(patch.multiple(config, VERIFACTU_PRODUCER_NIF="B87654321",  # pragma: allowlist secret
                                          **dict.fromkeys(FLAGS, False)))
        stack.enter_context(patch("urllib.request.urlopen", side_effect=AssertionError("Red prohibida")))
        stack.enter_context(patch("noesis.verifactu_client.submit_records", side_effect=AssertionError("AEAT prohibida")))
        for cls, name, replacement in ((WriterConnection, "execute", write),
                (FinancialSession, "execute", sql), (EconomicEvents, "append", event),
                (OperationsRepository, "transition", finish), (db.Connection, "commit", committed)):
            stack.enter_context(patch.object(cls, name, replacement))
        if point == "before_writer":
            stack.enter_context(patch.object(invoices, "create_invoice_cancellation_record", side_effect=lambda *a, **k: os._exit(17)))
        print("READY", flush=True)
        if sys.stdin.readline().strip() != "go":
            raise RuntimeError("Barrera de procesos requerida.")
        try:
            op = FiscalCancellationCapture(args["business_id"]).execute(
                Principal(args["user_id"], 0), args["operation_uuid"])
            print(json.dumps(dict(op.result)), flush=True)
        except StateError:
            print(json.dumps({"conflict": True}), flush=True)
        finally:
            db.close_pool()


if __name__ == "__main__":
    main()
