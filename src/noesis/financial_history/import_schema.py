"""Migración72: intents exactos y registro histórico; no modifica migración71."""

from .schema import guard

VERSION2 = "CHECK(payload_version=1 OR (payload_version=2 AND event_type IN ('invoice.issued','invoice.rectified')))"

TABLES = ("financial_history_import_batches", "financial_history_import_items")
V2_TYPES = "'supplier_invoice.confirmed','expense.confirmed','bank_transaction.imported'"
VERSION72 = (
    "CHECK(payload_version=1 OR (payload_version=2 AND origin='live' AND event_type IN "
    "('invoice.issued','invoice.rectified')) OR (payload_version=2 AND origin='historical' "
    f"AND event_type IN ({V2_TYPES})))"
)


def json_at(pg, expression, path):
    return (
        f"({expression}::jsonb #>> '{{{path.replace('.', ',')}}}')"
        if pg
        else f"json_extract({expression},'$.{path}')"
    )


def _versions(conn, upgrade):
    old, new = (VERSION2, VERSION72) if upgrade else (VERSION72, VERSION2)
    if conn.dialect == "postgres":
        conn.execute(
            "ALTER TABLE economic_events DROP CONSTRAINT economic_events_payload_version_check"
        )
        conn.execute(
            "ALTER TABLE economic_events ADD CONSTRAINT economic_events_payload_version_check "
            + new
        )
        definition = conn.execute(
            "SELECT pg_get_functiondef('capture_event()'::regprocedure) AS ddl"
        ).fetchone()["ddl"]
        before = "NEW.payload_version=2 AND NOT"
        after = "NEW.event_type IN ('invoice.issued','invoice.rectified') AND NEW.payload_version=2 AND NOT"
        conn.execute(
            definition.replace(before, after) if upgrade else definition.replace(after, before)
        )
        return
    if not conn.raw.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    ddl = conn.execute("SELECT sql FROM sqlite_master WHERE name='economic_events'").fetchone()[
        "sql"
    ]
    if ddl.count(old) != 1:
        raise ValueError("Matriz de versiones inesperada; no alterar.")
    # Solo cambia CHECK; ningún contenido físico ni FK. Procedimiento SQLite
    # para cambios de esquema sin reescribir filas: lang_altertable.html, §8.
    # DROP del target acumularía violaciones de las FK diferidas de coverage.
    schema_version = conn.execute("PRAGMA schema_version").fetchone()["schema_version"]
    conn.execute("PRAGMA writable_schema=ON")
    try:
        conn.execute(
            "UPDATE sqlite_master SET sql=? WHERE type='table' AND name='economic_events'",
            (ddl.replace(old, new),),
        )
        conn.execute(f"PRAGMA schema_version={schema_version + 1}")
    finally:
        conn.execute("PRAGMA writable_schema=OFF")
    trigger = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='capture_event'"
    ).fetchone()["sql"]
    before = "NEW.payload_version=2 AND NOT"
    after = (
        "NEW.event_type IN ('invoice.issued','invoice.rectified') AND NEW.payload_version=2 AND NOT"
    )
    conn.execute("DROP TRIGGER capture_event")
    conn.execute(trigger.replace(before, after) if upgrade else trigger.replace(after, before))
    if [row["integrity_check"] for row in conn.execute("PRAGMA integrity_check").fetchall()] != [
        "ok"
    ]:
        raise ValueError("Integridad inconsistente tras cambiar matriz durable.")
    if conn.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("FK inconsistente tras ampliar matriz durable.")


def boundary(pg, alias="b"):
    return f"""EXISTS(SELECT 1 FROM financial_history_cut_manifests m
        JOIN financial_history_manifests base ON base.business_id=m.business_id AND base.manifest_uuid=m.manifest_uuid
        JOIN financial_history_epochs e ON e.business_id=m.business_id AND e.epoch_uuid=m.epoch_uuid AND e.generation=m.generation
        JOIN financial_history_control c ON c.business_id=e.business_id AND c.epoch_uuid=e.epoch_uuid AND c.generation=e.generation
        WHERE m.business_id={alias}.business_id AND m.manifest_uuid={alias}.manifest_uuid
        AND m.epoch_uuid={alias}.epoch_uuid AND m.generation={alias}.generation
        AND e.state='fenced' AND e.fence_enabled=TRUE AND c.fence_enabled=TRUE
        AND m.mode='certifiable_inventory' AND m.status='frozen' AND m.certifiable=TRUE
        AND m.boundary_current=TRUE AND m.eligible_for_import=FALSE
        AND m.source_scope_version=1 AND m.source_scope_canonical=e.source_scope_canonical
        AND base.status='frozen' AND base.reader_version=1 AND base.classifier_version=1 AND base.canonical_version=1
        AND m.source_set_hash={alias}.source_set_hash AND base.source_set_hash={alias}.source_set_hash
        AND m.comparison_source_set_hash=m.source_set_hash AND base.comparison_source_set_hash=m.source_set_hash
        AND m.plan_hash={alias}.plan_hash AND base.plan_hash={alias}.plan_hash)"""


def verified_dependencies(pg):
    """Cada edge congelado apunta al evento exacto, nunca a amount/date/proximidad."""
    deps = (
        "jsonb_array_elements(i.dependency_canonical::jsonb) AS dep(value)"
        if pg
        else "json_each(i.dependency_canonical) dep"
    )
    relations = (
        "jsonb_array_elements(x.expected_event_canonical::jsonb->'relations') AS rel(value)"
        if pg
        else "json_each(json_extract(x.expected_event_canonical,'$.relations')) rel"
    )

    def d(path):
        return json_at(pg, "dep.value", path)

    def r(path):
        return json_at(pg, "rel.value", path)

    def p(path):
        return json_at(pg, "p.existing_coverage_canonical", "value." + path)

    target = "dep.value::jsonb->'target'" if pg else "json_extract(dep.value,'$.target')"
    candidate_identity = (
        "p.candidate_canonical::jsonb#>'{value,identity}'"
        if pg
        else "json_extract(p.candidate_canonical,'$.value.identity')"
    )
    coverage_identity = (
        "p.existing_coverage_canonical::jsonb#>'{value,identity}'"
        if pg
        else "json_extract(p.existing_coverage_canonical,'$.value.identity')"
    )
    imported_identity = (
        "proof.identity_canonical::jsonb->'value'"
        if pg
        else "json_extract(proof.identity_canonical,'$.value')"
    )
    cast = "::text" if pg else ""
    source_text_suffix = "" if pg else " || ''"
    count = "jsonb_array_length" if pg else "json_array_length"
    expected_relations = (
        "x.expected_event_canonical::jsonb->'relations'"
        if pg
        else "json_extract(x.expected_event_canonical,'$.relations')"
    )
    return f"""i.unresolved_dependency_canonical='[]'
        AND {count}({expected_relations})={count}(i.dependency_canonical{"::jsonb" if pg else ""})
        AND NOT EXISTS(SELECT 1 FROM {deps} WHERE NOT COALESCE((
          {d("parent_assessment.classification")}='A' AND {d("parent_assessment.severity")}<>'blocking'
          AND {d("parent_assessment.disposition")} IN ('candidate','covered_existing')
          AND EXISTS(SELECT 1 FROM financial_history_items p JOIN economic_events t ON t.business_id=p.business_id
            AND t.source_type={d("target.source.source_type")} AND t.source_id{cast}={d("target.source.source_id")}
            AND t.source_revision{cast}={d("target.revision.value")} AND t.event_type={d("target.event_type")}
            WHERE p.business_id=i.business_id AND p.manifest_uuid=i.manifest_uuid
            AND p.source_type={d("target.source.source_type")} AND p.source_id={d("target.source.source_id")}{source_text_suffix}
            AND p.fact_slot={d("target.fact_slot")} AND p.classification='A' AND p.severity<>'blocking'
            AND ((p.disposition='covered_existing' AND {coverage_identity}={target}
                  AND {p("event_uuid")}=t.event_uuid{cast} AND {p("event_content_hash")}=t.content_hash)
              OR (p.disposition='candidate' AND {candidate_identity}={target} AND EXISTS(
                  SELECT 1 FROM financial_history_import_items proof WHERE proof.business_id=t.business_id
                  AND proof.event_uuid=t.event_uuid AND proof.state='recorded' AND proof.candidate_hash=p.candidate_hash
                  AND {imported_identity}={target} AND proof.content_hash=t.content_hash AND proof.record_hash=t.record_hash)))
            AND EXISTS(SELECT 1 FROM {relations} WHERE {r("kind")}={d("relation")} AND {r("target_event_id")}=t.event_uuid{cast}))),FALSE))"""


def valid_intent(pg, extra="TRUE"):
    # Esta consulta se ejecuta dentro de la TX del writer, no autoriza por objeto Python.
    def j(path):
        return json_at(pg, "i.candidate_canonical", "value." + path)

    def expected(path):
        return json_at(pg, "x.expected_event_canonical", path)

    candidate_identity = (
        "i.candidate_canonical::jsonb#>'{value,identity}'"
        if pg
        else "json_extract(i.candidate_canonical,'$.value.identity')"
    )
    intent_identity = (
        "x.identity_canonical::jsonb->'value'"
        if pg
        else "json_extract(x.identity_canonical,'$.value')"
    )
    candidate_payload = (
        "i.candidate_canonical::jsonb#>'{value,event_payload,payload}'"
        if pg
        else "json_extract(i.candidate_canonical,'$.value.event_payload.payload')"
    )
    intent_payload = (
        "x.expected_event_canonical::jsonb->'payload'"
        if pg
        else "json_extract(x.expected_event_canonical,'$.payload')"
    )
    identity_fields = " AND ".join(
        f"{expected(field)}={j('identity.' + path)}"
        for field, path in (
            ("business_id", "source.business_id"),
            ("source_type", "source.source_type"),
            ("source_id", "source.source_id"),
            ("source_revision", "revision.value"),
            ("event_type", "event_type"),
        )
    )
    value_fields = " AND ".join(
        f"{expected(field)}={j('event_payload.' + field)}"
        for field in ("event_type", "payload_version", "currency")
    )
    expected_uuid = "x.expected_event_uuid::text" if pg else "x.expected_event_uuid"
    request_candidate = json_at(pg, "x.expected_request_canonical", "parameters.candidate_hash")
    request_identity = json_at(pg, "x.expected_request_canonical", "parameters.identity_hash")
    return f"""EXISTS(SELECT 1 FROM financial_history_import_items x
        JOIN financial_history_import_batches b ON b.business_id=x.business_id AND b.batch_uuid=x.batch_uuid AND b.manifest_uuid=x.manifest_uuid
        JOIN financial_history_items i ON i.business_id=x.business_id AND i.manifest_uuid=x.manifest_uuid AND i.item_uuid=x.item_uuid
        JOIN users u ON u.business_id=x.business_id AND u.id=x.recorded_by
        WHERE x.state='recording' AND b.state='running' AND b.importer_version=1
        AND x.candidate_hash=i.candidate_hash AND x.raw_hash=i.raw_hash
        AND {candidate_identity}={intent_identity} AND {candidate_payload}={intent_payload}
        AND ({identity_fields}) AND ({value_fields}) AND {expected("event_id")}={expected_uuid}
        AND {request_candidate}=x.candidate_hash AND {request_identity}=x.identity_hash
        AND ({verified_dependencies(pg)})
        AND i.classification IN ('A','B') AND i.disposition='candidate' AND i.candidate_canonical IS NOT NULL
        AND (i.terminal_result='planned_diagnostic' AND i.severity<>'blocking'
          OR (i.terminal_result='not_durably_supported' AND {j("event_payload.payload_version")}={"2" if not pg else "'2'"}
              AND {j("event_payload.event_type")} IN ({V2_TYPES})))
        AND NOT EXISTS(SELECT 1 FROM financial_history_incidences n WHERE n.business_id=i.business_id
          AND n.manifest_uuid=i.manifest_uuid AND n.item_uuid=i.item_uuid AND n.severity='blocking')
        AND u.is_active=TRUE AND u.session_version=x.session_version
        AND ({boundary(pg)}) AND ({extra}))"""


def _drop(conn, name, table):
    conn.execute(
        "DROP TRIGGER IF EXISTS " + name + (" ON " + table if conn.dialect == "postgres" else "")
    )
    if conn.dialect == "postgres":
        conn.execute("DROP FUNCTION IF EXISTS " + name + "()")


def _fence_guard(conn, table, action, allow):
    name = f"aaa_history_fence_{table}_{action.lower()}"
    _drop(conn, name, table)
    fenced = "EXISTS(SELECT 1 FROM financial_history_control WHERE business_id=NEW.business_id AND fence_enabled=TRUE)"
    acquire = "PERFORM noesis_history_gate(NEW.business_id);"
    if action == "UPDATE":
        fenced += " OR EXISTS(SELECT 1 FROM financial_history_control WHERE business_id=OLD.business_id AND fence_enabled=TRUE)"
        acquire += " PERFORM noesis_history_gate(OLD.business_id);"
    if conn.dialect == "postgres":
        conn.execute(f"""CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
            {acquire}
            IF ({fenced})
              AND NOT ({allow}) THEN RAISE EXCEPTION 'NOESIS_HISTORY_FENCE_ACTIVE' USING ERRCODE='23514'; END IF;
            RETURN NEW; END $$""")
        conn.execute(
            f"CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION {name}()"
        )
    else:
        conn.execute(
            f"CREATE TRIGGER {name} BEFORE {action} ON {table} WHEN ({fenced}) AND NOT ({allow}) BEGIN SELECT RAISE(ABORT,'NOESIS_HISTORY_FENCE_ACTIVE'); END"
        )


def upgrade(conn):
    _versions(conn, True)
    pg = conn.dialect == "postgres"
    uid, ref, stamp = ("UUID", "BIGINT", "TIMESTAMPTZ") if pg else ("TEXT", "INTEGER", "TEXT")
    conn.execute(f"""CREATE TABLE {TABLES[0]} (
        business_id {ref} NOT NULL, batch_uuid {uid} NOT NULL, manifest_uuid {uid} NOT NULL,
        epoch_uuid {uid} NOT NULL, generation BIGINT NOT NULL, importer_version INTEGER NOT NULL CHECK(importer_version=1),
        source_set_hash TEXT NOT NULL CHECK(length(source_set_hash)=64), plan_hash TEXT NOT NULL CHECK(length(plan_hash)=64),
        created_by {ref} NOT NULL, created_at {stamp} NOT NULL, updated_at {stamp} NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('prepared','running','completed','blocked','partial')),
        blocking_code TEXT CHECK(length(blocking_code) BETWEEN 1 AND 64), blocking_item_uuid {uid},
        PRIMARY KEY(business_id,batch_uuid), UNIQUE(business_id,batch_uuid,manifest_uuid),
        FOREIGN KEY(business_id,manifest_uuid) REFERENCES financial_history_cut_manifests(business_id,manifest_uuid),
        FOREIGN KEY(business_id,epoch_uuid,generation) REFERENCES financial_history_epochs(business_id,epoch_uuid,generation),
        FOREIGN KEY(business_id,created_by) REFERENCES users(business_id,id),
        FOREIGN KEY(business_id,manifest_uuid,blocking_item_uuid) REFERENCES financial_history_items(business_id,manifest_uuid,item_uuid))""")
    conn.execute(f"""CREATE TABLE {TABLES[1]} (
        business_id {ref} NOT NULL, batch_uuid {uid} NOT NULL, manifest_uuid {uid} NOT NULL, item_uuid {uid} NOT NULL,
        candidate_hash TEXT, raw_hash TEXT NOT NULL CHECK(length(raw_hash)=64), identity_hash TEXT,
        identity_canonical TEXT, expected_event_uuid {uid}, expected_operation_uuid {uid},
        expected_authorization_uuid {uid}, expected_event_canonical TEXT, expected_request_canonical TEXT,
        expected_sequence BIGINT CHECK(expected_sequence>0), recorded_by {ref} NOT NULL, session_version INTEGER NOT NULL CHECK(session_version>=0),
        state TEXT NOT NULL CHECK(state IN ('recording','recorded','existing','covered_existing','blocked','skipped')),
        completion_key TEXT NOT NULL CHECK(completion_key IN ('recorded','existing','covered_existing','blocked','skipped')),
        event_uuid {uid}, operation_uuid {uid}, authorization_uuid {uid}, content_hash TEXT, record_hash TEXT,
        result_canonical TEXT, reason TEXT, created_at {stamp} NOT NULL, completed_at {stamp},
        PRIMARY KEY(business_id,batch_uuid,item_uuid), UNIQUE(business_id,batch_uuid,item_uuid,state),
        FOREIGN KEY(business_id,batch_uuid,manifest_uuid) REFERENCES {TABLES[0]}(business_id,batch_uuid,manifest_uuid),
        FOREIGN KEY(business_id,manifest_uuid,item_uuid) REFERENCES financial_history_items(business_id,manifest_uuid,item_uuid),
        FOREIGN KEY(business_id,recorded_by) REFERENCES users(business_id,id),
        FOREIGN KEY(business_id,batch_uuid,item_uuid,completion_key) REFERENCES {TABLES[1]}(business_id,batch_uuid,item_uuid,state) DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY(business_id,event_uuid) REFERENCES economic_events(business_id,event_uuid) DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY(business_id,operation_uuid) REFERENCES financial_operations(business_id,operation_uuid) DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY(business_id,authorization_uuid) REFERENCES financial_authorizations(business_id,authorization_uuid) DEFERRABLE INITIALLY DEFERRED,
        CHECK((state='recording' AND completion_key='recorded' AND expected_event_uuid IS NOT NULL AND expected_operation_uuid IS NOT NULL
          AND expected_authorization_uuid IS NOT NULL AND expected_event_canonical IS NOT NULL AND expected_request_canonical IS NOT NULL
          AND expected_sequence IS NOT NULL AND candidate_hash IS NOT NULL AND identity_hash IS NOT NULL AND identity_canonical IS NOT NULL
          AND result_canonical IS NULL AND completed_at IS NULL)
          OR (state<>'recording' AND completion_key=state AND result_canonical IS NOT NULL AND completed_at IS NOT NULL)),
        CHECK(state NOT IN ('recorded','existing','covered_existing') OR (event_uuid IS NOT NULL AND content_hash IS NOT NULL AND record_hash IS NOT NULL)))""")
    conn.execute(
        f"CREATE UNIQUE INDEX idx_history_recording_tenant ON {TABLES[1]}(business_id) WHERE state='recording'"
    )
    conn.execute(
        f"CREATE INDEX idx_history_import_identity ON {TABLES[1]}(business_id,identity_hash,state)"
    )
    conn.execute(
        f"CREATE INDEX idx_history_import_event ON {TABLES[1]}(business_id,event_uuid,state)"
    )
    conn.execute(
        f"CREATE INDEX idx_history_import_operation ON {TABLES[1]}(business_id,expected_operation_uuid)"
    )
    conn.execute(
        "CREATE INDEX idx_history_frozen_source ON financial_history_items(business_id,manifest_uuid,source_type,source_id,fact_slot)"
    )
    conn.execute(
        f"CREATE INDEX idx_history_batch_manifest ON {TABLES[0]}(business_id,manifest_uuid)"
    )
    for table in TABLES:
        guard(conn, table + "_retain", table, "DELETE", "TRUE")
    eq = "IS DISTINCT FROM" if pg else "IS NOT"
    batch_identity = (
        "business_id",
        "batch_uuid",
        "manifest_uuid",
        "epoch_uuid",
        "generation",
        "importer_version",
        "source_set_hash",
        "plan_hash",
        "created_by",
        "created_at",
    )
    guard(
        conn,
        TABLES[0] + "_insert",
        TABLES[0],
        "INSERT",
        "NEW.state<>'prepared' OR NOT (" + boundary(pg, "NEW") + ")",
    )
    guard(
        conn,
        TABLES[0] + "_update",
        TABLES[0],
        "UPDATE",
        " OR ".join(f"NEW.{f} {eq} OLD.{f}" for f in batch_identity),
    )
    guard(
        conn,
        TABLES[1] + "_immutable",
        TABLES[1],
        "UPDATE",
        "OLD.state<>'recording' OR NEW.state<>'recorded' OR "
        + " OR ".join(
            f"NEW.{f} {eq} OLD.{f}"
            for f in (
                "business_id",
                "batch_uuid",
                "manifest_uuid",
                "item_uuid",
                "candidate_hash",
                "raw_hash",
                "identity_hash",
                "identity_canonical",
                "expected_event_uuid",
                "expected_operation_uuid",
                "expected_authorization_uuid",
                "expected_event_canonical",
                "expected_request_canonical",
                "expected_sequence",
                "recorded_by",
                "session_version",
                "created_at",
                "completion_key",
            )
        ),
    )
    # BEFORE INSERT necesita validar NEW, no una fila todavía ausente. Reusa consulta cerrada con un CTE de una fila.
    columns = (
        "business_id",
        "batch_uuid",
        "manifest_uuid",
        "item_uuid",
        "candidate_hash",
        "raw_hash",
        "recorded_by",
        "session_version",
        "state",
        "expected_event_canonical",
        "identity_canonical",
        "expected_event_uuid",
        "identity_hash",
        "expected_request_canonical",
    )
    intent_insert = valid_intent(pg).replace(
        "FROM financial_history_import_items x",
        "FROM (SELECT " + ",".join(f"NEW.{f} AS {f}" for f in columns) + ") x",
    )
    guard(
        conn,
        TABLES[1] + "_intent",
        TABLES[1],
        "INSERT",
        f"NEW.state='recording' AND NOT ({intent_insert})",
    )
    guard(conn, TABLES[1] + "_no_direct_recorded", TABLES[1], "INSERT", "NEW.state='recorded'")
    if pg:
        conn.execute("""CREATE FUNCTION aaa_history_import_gate() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
            PERFORM noesis_history_gate(NEW.business_id);
            PERFORM id FROM users WHERE business_id=NEW.business_id AND id=NEW.recorded_by FOR SHARE;
            PERFORM id FROM businesses WHERE id=NEW.business_id FOR SHARE;
            RETURN NEW; END $$""")
        conn.execute(
            f"CREATE TRIGGER aaa_history_import_gate BEFORE INSERT ON {TABLES[1]} FOR EACH ROW EXECUTE FUNCTION aaa_history_import_gate()"
        )
    guard(
        conn,
        TABLES[1] + "_result",
        TABLES[1],
        "UPDATE",
        "NOT EXISTS(SELECT 1 FROM economic_events e WHERE e.business_id=NEW.business_id AND e.event_uuid=NEW.event_uuid AND e.event_uuid=NEW.expected_event_uuid AND e.operation_uuid=NEW.operation_uuid AND e.operation_uuid=NEW.expected_operation_uuid AND e.authorization_uuid=NEW.authorization_uuid AND e.authorization_uuid=NEW.expected_authorization_uuid AND e.historical_batch_uuid=NEW.batch_uuid AND e.content_hash=NEW.content_hash AND e.record_hash=NEW.record_hash)",
    )
    event_allowed = valid_intent(
        pg,
        "x.business_id=NEW.business_id AND x.expected_event_uuid=NEW.event_uuid AND x.expected_operation_uuid=NEW.operation_uuid AND x.expected_authorization_uuid=NEW.authorization_uuid AND x.batch_uuid=NEW.historical_batch_uuid AND x.expected_event_canonical=NEW.canonical_event AND x.expected_sequence=NEW.business_sequence AND NEW.origin='historical'",
    )
    _fence_guard(conn, "economic_events", "INSERT", event_allowed)
    # Los guards base63 siguen comprobando tipo, target y sellado de todo el conjunto.
    relation_array = (
        "x.expected_event_canonical::jsonb->'relations'"
        if pg
        else "json_extract(x.expected_event_canonical,'$.relations')"
    )
    relation_rows = (
        f"jsonb_array_elements({relation_array}) rel" if pg else f"json_each({relation_array}) rel"
    )
    rel_kind = "rel->>'kind'" if pg else "json_extract(rel.value,'$.kind')"
    rel_target = "rel->>'target_event_id'" if pg else "json_extract(rel.value,'$.target_event_id')"
    target = "NEW.target_event_uuid::text" if pg else "NEW.target_event_uuid"
    link_allowed = valid_intent(
        pg,
        f"x.business_id=NEW.business_id AND x.expected_event_uuid=NEW.event_uuid AND EXISTS(SELECT 1 FROM {relation_rows} WHERE {rel_kind}=NEW.relation_type AND {rel_target}={target})",
    )
    _fence_guard(conn, "economic_event_links", "INSERT", link_allowed)
    sequence_allowed = valid_intent(
        pg,
        "x.business_id=NEW.business_id AND NEW.last_sequence=0 AND x.expected_sequence=COALESCE((SELECT last_sequence FROM economic_event_sequences WHERE business_id=NEW.business_id),0)+1",
    )
    _fence_guard(conn, "economic_event_sequences", "INSERT", sequence_allowed)
    sequence_update = valid_intent(
        pg,
        "x.business_id=NEW.business_id AND NEW.business_id=OLD.business_id AND NEW.last_sequence=OLD.last_sequence+1 AND NEW.last_sequence=x.expected_sequence AND NOT EXISTS(SELECT 1 FROM economic_events WHERE business_id=x.business_id AND event_uuid=x.expected_event_uuid)",
    )
    _fence_guard(conn, "economic_event_sequences", "UPDATE", sequence_update)
    guard(
        conn,
        "history_event_intent",
        "economic_events",
        "INSERT",
        "NEW.origin='historical' AND NOT (" + event_allowed + ")",
    )
    # Permite conservar operaciones contractuales previas fuera del fence, pero ninguna promoción.
    historical = "NEW.entry_namespace='historical' OR EXISTS(SELECT 1 FROM financial_authorizations WHERE business_id=NEW.business_id AND operation_uuid=NEW.operation_uuid AND kind='historical_unknown')"
    for action in ("INSERT", "UPDATE"):
        guard(
            conn,
            "history_operation_" + action.lower(),
            "financial_operations",
            action,
            f"({historical}) AND (NEW.entry_namespace<>'historical' OR NEW.state IN ('approved','committed') OR NEW.result_canonical IS NOT NULL OR NEW.committed_at IS NOT NULL OR (NEW.state<>'prepared' AND EXISTS(SELECT 1 FROM financial_history_import_items WHERE business_id=NEW.business_id AND expected_operation_uuid=NEW.operation_uuid)))",
        )
    guard(
        conn,
        "history_authorization_insert",
        "financial_authorizations",
        "INSERT",
        "(NEW.kind='historical_unknown' AND (NEW.channel<>'historical' OR NOT EXISTS(SELECT 1 FROM financial_operations o WHERE o.business_id=NEW.business_id AND o.operation_uuid=NEW.operation_uuid AND o.entry_namespace='historical' AND o.state='prepared' AND o.created_by=NEW.recorded_by))) OR (NEW.kind<>'historical_unknown' AND EXISTS(SELECT 1 FROM financial_operations o WHERE o.business_id=NEW.business_id AND o.operation_uuid=NEW.operation_uuid AND o.entry_namespace='historical'))",
    )
    conn.execute(
        "CREATE UNIQUE INDEX idx_history_single_authorization ON financial_authorizations(business_id,operation_uuid) WHERE kind='historical_unknown'"
    )
    operation_allowed = valid_intent(
        pg,
        "x.business_id=NEW.business_id AND x.expected_operation_uuid=NEW.operation_uuid AND x.identity_hash=NEW.entry_key AND x.recorded_by=NEW.created_by AND x.expected_request_canonical=NEW.request_canonical",
    )
    guard(
        conn,
        "history_operation_fence",
        "financial_operations",
        "INSERT",
        "NEW.entry_namespace='historical' AND EXISTS(SELECT 1 FROM financial_history_control WHERE business_id=NEW.business_id AND fence_enabled=TRUE) AND NOT ("
        + operation_allowed
        + ")",
    )
    authorization_allowed = valid_intent(
        pg,
        "x.business_id=NEW.business_id AND x.expected_operation_uuid=NEW.operation_uuid AND x.expected_authorization_uuid=NEW.authorization_uuid AND x.recorded_by=NEW.recorded_by",
    )
    guard(
        conn,
        "history_authorization_fence",
        "financial_authorizations",
        "INSERT",
        "NEW.kind='historical_unknown' AND EXISTS(SELECT 1 FROM financial_history_control WHERE business_id=NEW.business_id AND fence_enabled=TRUE) AND NOT ("
        + authorization_allowed
        + ")",
    )


def downgrade(conn):
    if (
        any(conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() for table in TABLES)
        or conn.execute(
            "SELECT 1 FROM economic_events WHERE origin='historical' AND payload_version=2 LIMIT 1"
        ).fetchone()
    ):
        raise ValueError("Conservar evidencia de importación histórica; bajada72 bloqueada.")
    for table, names in {
        TABLES[0]: (TABLES[0] + "_retain", TABLES[0] + "_insert", TABLES[0] + "_update"),
        TABLES[1]: (
            TABLES[1] + "_retain",
            TABLES[1] + "_immutable",
            TABLES[1] + "_intent",
            TABLES[1] + "_result",
            TABLES[1] + "_no_direct_recorded",
        ),
        "economic_events": ("history_event_intent",),
        "financial_operations": (
            "history_operation_insert",
            "history_operation_update",
            "history_operation_fence",
        ),
        "financial_authorizations": ("history_authorization_insert", "history_authorization_fence"),
    }.items():
        for name in names:
            _drop(conn, name, table)
    if conn.dialect == "postgres":
        _drop(conn, "aaa_history_import_gate", TABLES[1])
    conn.execute("DROP INDEX idx_history_single_authorization")
    conn.execute("DROP INDEX idx_history_frozen_source")
    conn.execute("DROP TABLE " + TABLES[1])
    conn.execute("DROP TABLE " + TABLES[0])
    # Restituir exactamente los guards71 antes de volver a CHECK65.
    from .cut_schema import _source_guards

    _source_guards(conn, False)
    _source_guards(conn, True)
    _versions(conn, False)
