"""Cobertura obligatoria/inmutable de emisión capturada; sin backfill."""

from noesis.economic_events.schema import _guards
import re

VERSION1 = "CHECK(payload_version=1)"
VERSION2 = "CHECK(payload_version=1 OR (payload_version=2 AND event_type IN ('invoice.issued','invoice.rectified')))"
GUARDS = {"econ_sequence_insert": "economic_event_sequences", "econ_event_insert": "economic_events",
          "econ_link_insert": "economic_event_links", "econ_sequence_update": "economic_event_sequences"}


def _versions(conn, *, upgrade):
    old, new = (VERSION1, VERSION2) if upgrade else (VERSION2, VERSION1)
    if conn.dialect == "postgres":
        conn.execute("ALTER TABLE economic_events DROP CONSTRAINT economic_events_payload_version_check")
        conn.execute("ALTER TABLE economic_events ADD CONSTRAINT economic_events_payload_version_check " + new)
        return
    # Rebuild transaccional: conserva filas, UUID, hashes, links y secuencias v1.
    # Rehacer también links evita el contador diferido falso de DROP/recrear padre
    # en SQLite. No apagar FKs; copia SQL local, sin cargar la historia en memoria.
    if not conn.raw.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    ddl = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='economic_events'").fetchone()["sql"]
    link_ddl = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='economic_event_links'").fetchone()["sql"]
    if old not in ddl:
        raise ValueError("CHECK de versión inesperado; no reconstruir silenciosamente.")
    indices = conn.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='economic_events' AND sql IS NOT NULL").fetchall()
    link_indices = conn.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='economic_event_links' AND sql IS NOT NULL").fetchall()
    for name in GUARDS:
        conn.execute(f"DROP TRIGGER {name}")
    for table in ("economic_events", "economic_event_links"):
        for action in ("update", "delete"):
            conn.execute(f"DROP TRIGGER {table}_{action}")
    rebuilt = re.sub(r'^CREATE TABLE "?economic_events"?', 'CREATE TABLE economic_events_v65', ddl, count=1)
    conn.execute(rebuilt.replace(old, new))
    conn.execute("INSERT INTO economic_events_v65 SELECT * FROM economic_events")
    conn.execute("CREATE TEMP TABLE capture_links_copy AS SELECT * FROM economic_event_links")
    conn.execute("DROP TABLE economic_event_links")
    conn.execute("DROP TABLE economic_events")
    conn.execute("ALTER TABLE economic_events_v65 RENAME TO economic_events")
    conn.execute(link_ddl)
    conn.execute("INSERT INTO economic_event_links SELECT * FROM capture_links_copy")
    conn.execute("DROP TABLE capture_links_copy")
    for row in link_indices:
        conn.execute(row["sql"])
    for row in indices:
        conn.execute(row["sql"])
    _guards(conn)
    if conn.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("FK incoherente tras migrar versiones; revertir todo.")


def upgrade(conn):
    _versions(conn, upgrade=True)
    pg = conn.dialect == "postgres"
    ref, uid = ("BIGINT", "UUID") if pg else ("INTEGER", "TEXT")
    conn.execute("CREATE UNIQUE INDEX idx_capture_event_scope ON economic_events(business_id,event_uuid,invoice_id,event_type,operation_uuid)")
    conn.execute("CREATE UNIQUE INDEX idx_capture_operation_state ON financial_operations(business_id,operation_uuid,state)")
    conn.execute(f"""CREATE TABLE invoice_economic_coverage (
        business_id {ref} NOT NULL, invoice_id {ref} NOT NULL,
        event_uuid {uid} NOT NULL UNIQUE, event_type TEXT NOT NULL CHECK(event_type IN ('invoice.issued','invoice.rectified')),
        operation_uuid {uid} NOT NULL UNIQUE, operation_state TEXT NOT NULL DEFAULT 'committed' CHECK(operation_state='committed'),
        PRIMARY KEY(business_id,invoice_id),
        FOREIGN KEY(business_id,invoice_id) REFERENCES invoices(business_id,id),
        FOREIGN KEY(business_id,event_uuid,invoice_id,event_type,operation_uuid)
            REFERENCES economic_events(business_id,event_uuid,invoice_id,event_type,operation_uuid) DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY(business_id,operation_uuid,operation_state)
            REFERENCES financial_operations(business_id,operation_uuid,state) DEFERRABLE INITIALLY DEFERRED
    )""")
    request_target = "(o.request_canonical::jsonb->>'target_id')::bigint" if pg else "json_extract(o.request_canonical,'$.target_id')"
    capture_valid = f"""EXISTS(SELECT 1 FROM invoices i JOIN financial_operations o ON o.business_id=i.business_id
        WHERE i.business_id=NEW.business_id AND i.id=NEW.invoice_id AND i.status='borrador' AND i.number IS NULL
        AND o.operation_uuid=NEW.operation_uuid AND o.state='approved' AND {request_target}=i.id
        AND ((NEW.event_type='invoice.issued' AND i.invoice_type IN ('F1','F2') AND o.command_type='invoice.issue')
          OR (NEW.event_type='invoice.rectified' AND i.invoice_type IN ('R1','R2','R3','R4','R5') AND o.command_type='invoice.rectify')))"""
    event_valid = """EXISTS(SELECT 1 FROM invoice_economic_coverage c JOIN invoices i ON i.business_id=c.business_id AND i.id=c.invoice_id
        WHERE c.business_id=NEW.business_id AND c.event_uuid=NEW.event_uuid AND c.invoice_id=NEW.source_id
        AND c.operation_uuid=NEW.operation_uuid AND c.event_type=NEW.event_type
        AND NEW.origin='live' AND NEW.event_slot='primary' AND i.status IN ('enviada','parcial','cobrada')
        AND i.number IS NOT NULL AND i.issued_at IS NOT NULL
        AND ((NEW.event_type='invoice.issued' AND i.invoice_type IN ('F1','F2')) OR
          (NEW.event_type='invoice.rectified' AND i.invoice_type IN ('R1','R2','R3','R4','R5') AND EXISTS(
            SELECT 1 FROM economic_event_links l JOIN economic_events t ON t.business_id=l.business_id AND t.event_uuid=l.target_event_uuid
            WHERE l.business_id=NEW.business_id AND l.event_uuid=NEW.event_uuid AND l.relation_type='rectifies'
            AND t.invoice_id=i.rectifies_invoice_id))))"""
    def value(path):
        return "(NEW.result_canonical::jsonb #>> '{" + path + "}')" if pg else "json_extract(NEW.result_canonical,'$." + path + "')"
    cast = "::text" if pg else ""
    payload_total = "(e.payload_canonical::jsonb->>'total')" if pg else "json_extract(e.payload_canonical,'$.total')"
    payload_number = "(e.payload_canonical::jsonb->>'invoice_number')" if pg else "json_extract(e.payload_canonical,'$.invoice_number')"
    result_valid = f"""NOT EXISTS(SELECT 1 FROM invoice_economic_coverage c JOIN economic_events e
        ON e.business_id=c.business_id AND e.event_uuid=c.event_uuid
        WHERE c.business_id=NEW.business_id AND c.operation_uuid=NEW.operation_uuid
        AND NOT ({value('invoice_id')}=c.invoice_id{cast} AND {value('event_uuid')}=c.event_uuid{cast}
          AND {value('event_type')}=c.event_type AND {value('content_hash')}=e.content_hash
          AND {value('amount')}={payload_total} AND {value('number')}={payload_number} AND {value('currency')}='EUR'))"""
    # NULL de JSON incompleto tampoco puede aprobar un resultado.
    truth = "'true'" if pg else "1"
    result_valid = f"({value('captured')}={truth} AND {value('invoice_id')} IS NOT NULL AND {value('event_uuid')} IS NOT NULL AND {value('event_type')} IS NOT NULL AND {value('content_hash')} IS NOT NULL AND {value('amount')} IS NOT NULL AND {value('number')} IS NOT NULL AND {value('currency')} IS NOT NULL AND {result_valid})"
    definitions = [
        ("capture_insert", "invoice_economic_coverage", "BEFORE INSERT", f"NOT ({capture_valid})"),
        ("capture_event", "economic_events", "AFTER INSERT", f"NEW.payload_version=2 AND NOT ({event_valid})"),
        ("capture_result", "financial_operations", "BEFORE UPDATE", "NEW.state='committed' AND NEW.command_type IN ('invoice.issue','invoice.rectify') AND (NOT EXISTS(SELECT 1 FROM invoice_economic_coverage c JOIN economic_events e ON e.business_id=c.business_id AND e.event_uuid=c.event_uuid WHERE c.business_id=NEW.business_id AND c.operation_uuid=NEW.operation_uuid AND e.payload_version=2) OR NOT COALESCE(" + result_valid + ", FALSE))"),
    ]
    for name, table, event, condition in definitions:
        if pg:
            conn.execute(f"CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF {condition} THEN RAISE EXCEPTION 'Emisión capturada incoherente' USING ERRCODE = '23514'; END IF; RETURN NEW; END $$")
            conn.execute(f"CREATE TRIGGER {name} {event} ON {table} FOR EACH ROW EXECUTE FUNCTION {name}()")
        else:
            conn.execute(f"CREATE TRIGGER {name} {event} ON {table} WHEN {condition} BEGIN SELECT RAISE(ABORT,'Emisión capturada incoherente'); END")
    if pg:
        conn.execute("CREATE TRIGGER capture_immutable BEFORE UPDATE OR DELETE ON invoice_economic_coverage FOR EACH ROW EXECUTE FUNCTION econ_immutable()")
    else:
        for action in ("UPDATE", "DELETE"):
            conn.execute(f"CREATE TRIGGER capture_{action.lower()} BEFORE {action} ON invoice_economic_coverage BEGIN SELECT RAISE(ABORT,'Cobertura inmutable'); END")


def downgrade(conn):
    if conn.execute("SELECT 1 FROM invoice_economic_coverage LIMIT 1").fetchone() or conn.execute("SELECT 1 FROM economic_events WHERE payload_version=2 LIMIT 1").fetchone():
        raise ValueError("Conservar cobertura/eventos de emisión capturada; bajada bloqueada.")
    for name, table in (("capture_insert", "invoice_economic_coverage"), ("capture_event", "economic_events"), ("capture_result", "financial_operations")):
        conn.execute(f"DROP TRIGGER {name}" + (f" ON {table}" if conn.dialect == "postgres" else ""))
        if conn.dialect == "postgres":
            conn.execute(f"DROP FUNCTION {name}()")
    conn.execute("DROP TABLE invoice_economic_coverage")
    conn.execute("DROP INDEX idx_capture_event_scope")
    conn.execute("DROP INDEX idx_capture_operation_state")
    _versions(conn, upgrade=False)
