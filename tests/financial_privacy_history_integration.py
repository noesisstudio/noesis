"""Fixture E history→import→reconcile→B→D→export/cierre, sólo datos sintéticos.

Se ejecuta con python -m tests.financial_privacy_history_integration [postgres].
La elegibilidad FULL es un fixture estructural D, no readiness real ni piloto.
"""

import json
import sys
from unittest.mock import patch
from uuid import uuid4

from noesis import config, db
from noesis.core.persistence import FinancialSession
from noesis.financial_activation.handoff import FinancialActivation
from noesis.financial_antecedents.contracts import AntecedentRef, ResolutionRequest, Purpose
from noesis.financial_antecedents.resolver import AntecedentResolver
from noesis.financial_operations.contracts import Principal
from noesis.financial_privacy.export import verify_export
from tests.financial_history_import_contract import HistoryImportContract
from tests.test_financial_privacy import PrivacySQLite


def exercise(case):
    # Ajustar almacenamiento sólo en la DB/esquema privado recién creado del
    # fixture: ninguna conversión de fuentes legacy del producto.
    if config.DATABASE_URL:
        db.close_pool()
        with patch.object(config, "DATABASE_URL", case.admin_scoped):
            HistoryImportContract.exact_storage(case)
            db.close_pool()
    else:
        HistoryImportContract.exact_storage(case)
    with db.get_conn() as c:
        c.execute("INSERT INTO expenses(business_id,concept,amount,created_at) VALUES (?,'Histórico sintético','12.10','2026-09-01T00:00:00+00:00')", (case.bid,))
    assert case.cut()["result"] == "PASS"
    with db.get_conn() as c:
        c.execute("BEGIN IMMEDIATE")
        event = c.execute_exact("SELECT * FROM economic_events WHERE business_id=? AND source_type='expense'", (case.bid,)).fetchone()
        request = ResolutionRequest(AntecedentRef("expense", event["source_id"], event["source_revision"], str(event["event_uuid"])), Purpose.INSPECT)
        original = AntecedentResolver(FinancialSession(c), case.bid).persist_resolution(case.principal, uuid4(), request)
    assert original["result"]["outcome"] == "resolved"
    case.api = FinancialActivation(case.bid, code_version="fixture")
    case.enable()
    exported = case.exporter.export(case.principal, uuid4(), "audit")
    assert verify_export(exported)
    sections = exported["sections"]
    for name in ("financial_history_manifests", "financial_history_cut_manifests", "financial_history_import_batches",
                 "financial_history_import_items", "financial_history_reconciliations", "financial_antecedent_resolutions",
                 "financial_activation_generations", "financial_activation_grants", "financial_activation_transitions", "economic_events"):
        assert sections[name], name
    epoch = sections["financial_history_epochs"][0]
    assert epoch["state"] == "handed_off"
    assert str(event["event_uuid"]) in {str(row["event_uuid"]) for row in sections["economic_events"]}
    assert json.loads(sections["financial_antecedent_resolutions"][0]["result_canonical"]) == original["result"]
    with db.get_conn() as c:
        c.execute("BEGIN IMMEDIATE")
        assert AntecedentResolver(FinancialSession(c), case.bid).verify_resolution(case.principal, original) == original
    pause = case.approved_request(action="pause", pause_reason="operator_request")
    case.api.advance(case.principal, pause.body["request_uuid"], "paused")
    before = case.exporter.export(case.principal, uuid4(), "audit")
    case.applied()
    after = case.exporter.export(Principal(case.user["id"], 1), uuid4(), "audit", closure_read=True)
    assert verify_export(after)
    for table in before["sections"]:
        if table.startswith(("financial_history_", "financial_activation_", "economic_")) or table in ("financial_operations", "financial_authorizations", "financial_antecedent_resolutions", "expenses"):
            assert before["sections"][table] == after["sections"][table], table
    print("E_HISTORY_IMPORT_RECONCILIATION_B_D_HANDOFF_EXPORT_PAUSE_CLOSURE_PROOF_PASS", flush=True)


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
        exercise(case)
    finally:
        case.doCleanups()
        if pg:
            case_type.tearDownClass()


if __name__ == "__main__":
    main()
