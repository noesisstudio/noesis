"""Migración73: dos tablas de auditoría, sin tocar migraciones63–72."""

from .import_schema import boundary
from .reconciliation_contracts import FindingCode, HASH_FIELDS
from .schema import guard, literals

RUNS = "financial_history_reconciliations"
FINDINGS = "financial_history_reconciliation_findings"


def upgrade(conn):
    pg = conn.dialect == "postgres"
    uid, ref, timestamp = ("UUID", "BIGINT", "TIMESTAMPTZ") if pg else ("TEXT", "INTEGER", "TEXT")
    hashes = ",".join(f"{f} TEXT CHECK(length({f})=64)" for f in (*HASH_FIELDS, "result_hash"))
    conn.execute(f"""CREATE TABLE {RUNS} (
        business_id {ref} NOT NULL, reconciliation_uuid {uid} NOT NULL,
        epoch_uuid {uid} NOT NULL, generation INTEGER NOT NULL,
        manifest_uuid {uid} NOT NULL, batch_uuid {uid} NOT NULL,
        reconciliation_version INTEGER NOT NULL CHECK(reconciliation_version=1),
        created_by {ref} NOT NULL, session_version INTEGER NOT NULL CHECK(session_version>=0),
        started_at {timestamp} NOT NULL, completed_at {timestamp},
        state TEXT NOT NULL CHECK(state IN ('running','frozen')),
        result TEXT CHECK(result IN ('PASS','BLOCKED')), {hashes}, result_canonical TEXT,
        PRIMARY KEY(business_id,reconciliation_uuid),
        FOREIGN KEY(business_id,created_by) REFERENCES users(business_id,id),
        FOREIGN KEY(business_id,epoch_uuid,generation) REFERENCES financial_history_epochs(business_id,epoch_uuid,generation),
        FOREIGN KEY(business_id,batch_uuid,manifest_uuid) REFERENCES financial_history_import_batches(business_id,batch_uuid,manifest_uuid),
        CHECK((state='running' AND result IS NULL AND completed_at IS NULL AND result_canonical IS NULL AND result_hash IS NULL)
          OR (state='frozen' AND result IS NOT NULL AND completed_at IS NOT NULL AND result_canonical IS NOT NULL
            AND {" AND ".join(f+" IS NOT NULL" for f in (*HASH_FIELDS,'result_hash'))})))""")
    conn.execute(f"""CREATE TABLE {FINDINGS} (
        business_id {ref} NOT NULL, reconciliation_uuid {uid} NOT NULL,
        finding_uuid {uid} NOT NULL, manifest_uuid {uid} NOT NULL, item_uuid {uid},
        code TEXT NOT NULL CHECK(code IN ({literals(FindingCode)})),
        severity TEXT NOT NULL CHECK(severity='blocking'), finding_version INTEGER NOT NULL CHECK(finding_version=1),
        expected_hash TEXT CHECK(length(expected_hash)=64), actual_hash TEXT CHECK(length(actual_hash)=64),
        expected_ref TEXT CHECK(length(expected_ref) BETWEEN 1 AND 160), actual_ref TEXT CHECK(length(actual_ref) BETWEEN 1 AND 160),
        evidence_canonical TEXT NOT NULL, finding_hash TEXT NOT NULL CHECK(length(finding_hash)=64),
        created_at {timestamp} NOT NULL,
        PRIMARY KEY(business_id,reconciliation_uuid,finding_uuid), UNIQUE(business_id,reconciliation_uuid,finding_hash),
        FOREIGN KEY(business_id,reconciliation_uuid) REFERENCES {RUNS}(business_id,reconciliation_uuid),
        FOREIGN KEY(business_id,manifest_uuid,item_uuid) REFERENCES financial_history_items(business_id,manifest_uuid,item_uuid))""")
    conn.execute(f"CREATE UNIQUE INDEX idx_reconciliation_running ON {RUNS}(business_id,batch_uuid) WHERE state='running'")
    conn.execute(f"CREATE INDEX idx_reconciliation_batch ON {RUNS}(business_id,batch_uuid,state)")
    conn.execute(f"CREATE INDEX idx_reconciliation_findings ON {FINDINGS}(business_id,reconciliation_uuid,finding_hash)")
    terminal = "EXISTS(SELECT 1 FROM financial_history_import_batches b WHERE b.business_id=NEW.business_id AND b.batch_uuid=NEW.batch_uuid AND b.manifest_uuid=NEW.manifest_uuid AND b.state IN ('completed','partial','blocked'))"
    guard(conn, RUNS+"_insert", RUNS, "INSERT", "NEW.state<>'running' OR NOT ("+boundary(pg,"NEW")+") OR NOT ("+terminal+")")
    immutable = ("business_id","reconciliation_uuid","epoch_uuid","generation","manifest_uuid","batch_uuid",
                 "reconciliation_version","created_by","session_version","started_at","source_set_hash","plan_hash")
    eq = "IS DISTINCT FROM" if pg else "IS NOT"
    guard(conn,RUNS+"_update",RUNS,"UPDATE","OLD.state<>'running' OR NEW.state<>'frozen' OR "+
          " OR ".join(f"NEW.{f} {eq} OLD.{f}" for f in immutable)+
          " OR (NEW.result='PASS' AND (NOT ("+boundary(pg,"NEW")+") OR NOT ("+terminal+") OR EXISTS(SELECT 1 FROM "+FINDINGS+" f WHERE f.business_id=NEW.business_id AND f.reconciliation_uuid=NEW.reconciliation_uuid)))")
    for table in (RUNS,FINDINGS):
        guard(conn,table+"_retain",table,"DELETE","TRUE")
    guard(conn,FINDINGS+"_immutable",FINDINGS,"UPDATE","TRUE")
    guard(conn,FINDINGS+"_insert",FINDINGS,"INSERT",f"NOT EXISTS(SELECT 1 FROM {RUNS} r WHERE r.business_id=NEW.business_id AND r.reconciliation_uuid=NEW.reconciliation_uuid AND r.manifest_uuid=NEW.manifest_uuid AND r.state='running')")
    # Un batch terminal admite retry de resultados previos, no un nuevo intent.
    guard(conn,"history_terminal_batch_no_reopen","financial_history_import_batches","UPDATE",
          "OLD.state IN ('completed','partial','blocked') AND NEW.state IN ('prepared','running')")


def downgrade(conn):
    if conn.execute(f"SELECT 1 FROM {RUNS} LIMIT 1").fetchone() or conn.execute(f"SELECT 1 FROM {FINDINGS} LIMIT 1").fetchone():
        raise ValueError("Conservar reconciliación durable; bajada73 bloqueada.")
    from .import_schema import _drop
    _drop(conn,"history_terminal_batch_no_reopen","financial_history_import_batches")
    for table,names in ((FINDINGS,("retain","immutable","insert")),(RUNS,("retain","insert","update"))):
        for suffix in names:
            _drop(conn,table+"_"+suffix,table)
        conn.execute("DROP TABLE "+table)
