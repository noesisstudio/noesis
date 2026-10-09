"""Medición E reproducible sin SLO: fixture sintético, nunca copia real.

python -m tests.financial_privacy_benchmark (SQLite)
DATABASE_URL local /noesis_ci python -m tests.financial_privacy_benchmark postgres
Sólo imprime tiempos, memoria, tamaños y recuentos; nunca contenido exportado.
"""

import json
import sys
import time
import tracemalloc
from uuid import uuid4

from noesis import db
from noesis.financial_history.service import HistoryDiagnostics
from noesis.financial_privacy.contracts import canonical
from noesis.financial_privacy.export import verify_export
from noesis.purchasing_capture import ExpenseCapture
from tests.test_financial_privacy import PrivacySQLite


def main():
    pg = len(sys.argv) > 1 and sys.argv[1] == "postgres"
    if pg:
        from tests.postgres_financial_privacy import PrivacyPostgres
        case_type = PrivacyPostgres
        case_type.setUpClass()
    else:
        case_type = PrivacySQLite
    case = case_type("test_export_closed_purpose")
    try:
        case.setUp()
        # El clasificador también conserva una fila de identidad fiscal: 63
        # fuentes + esa identidad forman exactamente 64 items diagnósticos.
        for n in range(63):
            db.add_expense("Histórico sintético " + str(n), "1.00", business_id=case.bid)
        HistoryDiagnostics(case.bid).run(case.principal, uuid4(), repository_version="synthetic-benchmark", environment_identity="synthetic-only")
        expense = ExpenseCapture(case.bid)
        started = time.monotonic()
        for n in range(1000):
            reviewed = expense.review_confirm(case.principal, concept="EE sintético " + str(n), amount="12.10")
            op = case.approved(expense, reviewed)
            expense.execute(case.principal, op.operation_uuid)
            if n and n % 200 == 0:
                print("SYNTHETIC_EE", n, flush=True)
        preparation = time.monotonic() - started
        with db.get_conn() as c:
            for n in range(501):
                c.execute("INSERT INTO bank_transactions(business_id,import_hash,booked_on,amount,currency,description,status,created_at) VALUES (?,?,'2026-10-07','1.00','EUR','Sintético','imported',?)", (case.bid, str(uuid4()), db._now()))
                c.execute("INSERT INTO email_outbox(business_id,to_email,subject,text_body,idempotency_key,status,next_attempt_at,created_at,updated_at) VALUES (?,'fixture@example.test','Prueba','No exportar',?,'queued',?,?,?)", (case.bid, str(uuid4()), db._now(), db._now(), db._now()))
        tracemalloc.start()
        started = time.monotonic()
        export = case.exporter.export(case.principal, uuid4(), include_legacy=True)
        duration = time.monotonic() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert verify_export(export)
        counts = {t: export["manifest"]["sections"][t]["count"] for t in ("financial_history_items", "economic_events", "bank_transactions", "email_outbox")}
        assert counts == dict(financial_history_items=64, economic_events=1000, bank_transactions=501, email_outbox=501), counts
        print(json.dumps(dict(engine="postgresql16" if pg else "sqlite", counts=counts,
                              export_seconds=round(duration, 6), peak_python_bytes=peak,
                              canonical_export_bytes=len(canonical(export).encode()), fixture_seconds=round(preparation, 3))), flush=True)
    finally:
        case.doCleanups()
        if pg:
            case_type.tearDownClass()


if __name__ == "__main__":
    main()
