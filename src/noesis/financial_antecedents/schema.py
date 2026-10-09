"""Migración75 aditiva. Evidencia append-only; ninguna transición financiera."""

from noesis.financial_history.schema import guard, literals
from .contracts import CATALOG, FIELDS, Origin, Outcome, Permission, Purpose, Quality, Reason

TABLE = "financial_antecedent_resolutions"
SOURCES = {
    "invoice": "invoices",
    "invoice_payment": "invoice_payments",
    "received_invoice": "received_invoices",
    "expense": "expenses",
    "bank_transaction": "bank_transactions",
    "cancellation_record": "invoice_cancellation_records",
}


def upgrade(conn):
    pg = conn.dialect == "postgres"
    ref, uid, stamp = ("BIGINT", "UUID", "TIMESTAMPTZ") if pg else ("INTEGER", "TEXT", "TEXT")
    columns, foreign, checks = [], [], []
    for source, table in SOURCES.items():
        column = (
            "invoice_cancellation_record_id" if source == "cancellation_record" else source + "_id"
        )
        columns.append(f"{column} {ref}")
        foreign.append(f"FOREIGN KEY(business_id,{column}) REFERENCES {table}(business_id,id)")
        checks.append(
            f"CHECK((source_type='{source}' AND {column}=source_id AND {column} IS NOT NULL) OR (source_type<>'{source}' AND {column} IS NULL))"
        )
    conn.execute(f"""CREATE TABLE {TABLE} (
        business_id {ref} NOT NULL REFERENCES businesses(id),resolution_uuid {uid} NOT NULL,
        resolution_version INTEGER NOT NULL CHECK(resolution_version=1),
        purpose TEXT NOT NULL CHECK(purpose IN ({literals(Purpose)})),
        source_type TEXT NOT NULL CHECK(source_type IN ({literals(SOURCES)})),source_id {ref} NOT NULL CHECK(source_id>0),
        source_revision BIGINT NOT NULL CHECK(source_revision>0),
        outcome TEXT NOT NULL CHECK(outcome IN ({literals(Outcome)})),
        origin TEXT CHECK(origin IN ({literals(Origin)})),quality TEXT CHECK(quality IN ({literals(Quality)})),
        event_uuid {uid}, operation_uuid {uid},authorization_uuid {uid},
        batch_uuid {uid},manifest_uuid {uid},item_uuid {uid},reconciliation_uuid {uid},
        created_by {ref} NOT NULL,session_version INTEGER NOT NULL CHECK(session_version>=0),
        validated_permission TEXT NOT NULL CHECK(validated_permission='{Permission.RESOLVE.value}'),
        known_unknown_canonical TEXT NOT NULL,source_hash TEXT NOT NULL CHECK(length(source_hash)=64),
        event_content_hash TEXT CHECK(length(event_content_hash)=64),event_record_hash TEXT CHECK(length(event_record_hash)=64),
        context_hash TEXT NOT NULL CHECK(length(context_hash)=64),result_canonical TEXT NOT NULL,
        content_hash TEXT NOT NULL CHECK(length(content_hash)=64),created_at {stamp} NOT NULL,
        revalidation TEXT NOT NULL CHECK(revalidation='every_use'),
        {",".join(columns)},PRIMARY KEY(business_id,resolution_uuid),
        FOREIGN KEY(business_id,created_by) REFERENCES users(business_id,id),
        FOREIGN KEY(business_id,event_uuid) REFERENCES economic_events(business_id,event_uuid),
        FOREIGN KEY(business_id,operation_uuid) REFERENCES financial_operations(business_id,operation_uuid),
        FOREIGN KEY(business_id,authorization_uuid) REFERENCES financial_authorizations(business_id,authorization_uuid),
        FOREIGN KEY(business_id,batch_uuid,manifest_uuid) REFERENCES financial_history_import_batches(business_id,batch_uuid,manifest_uuid),
        FOREIGN KEY(business_id,manifest_uuid,item_uuid) REFERENCES financial_history_items(business_id,manifest_uuid,item_uuid),
        FOREIGN KEY(business_id,reconciliation_uuid) REFERENCES financial_history_reconciliations(business_id,reconciliation_uuid),
        {",".join(foreign + checks)},
        CHECK(outcome='blocked' OR (event_uuid IS NOT NULL AND operation_uuid IS NOT NULL AND authorization_uuid IS NOT NULL
            AND origin IS NOT NULL AND quality IS NOT NULL AND event_content_hash IS NOT NULL AND event_record_hash IS NOT NULL
            AND (purpose='inspect_evidence' OR quality='verified_fact')
            AND (origin='live' OR (batch_uuid IS NOT NULL AND manifest_uuid IS NOT NULL AND item_uuid IS NOT NULL AND reconciliation_uuid IS NOT NULL)))))""")
    conn.execute(
        f"CREATE INDEX idx_antecedent_source ON {TABLE}(business_id,source_type,source_id,source_revision)"
    )
    # Una futura FK de hijo podrá exigir outcome/purpose/quality/origin exactos.
    # Ningún writer existente consume esta clave ni se elimina ninguna FK anterior.
    conn.execute(
        f"CREATE UNIQUE INDEX idx_antecedent_protected_scope ON {TABLE}(business_id,resolution_uuid,outcome,purpose,quality,origin,event_uuid)"
    )
    guard(conn, TABLE + "_immutable", TABLE, "UPDATE", "TRUE")
    guard(conn, TABLE + "_retain", TABLE, "DELETE", "TRUE")

    def value(field):
        return (
            f"(NEW.result_canonical::jsonb->>'{field}')"
            if pg
            else f"json_extract(NEW.result_canonical,'$.{field}')"
        )

    cast = "::text" if pg else ""
    reasons = (
        "jsonb_array_elements_text(NEW.result_canonical::jsonb->'reasons') r(value)"
        if pg
        else "json_each(NEW.result_canonical,'$.reasons') r"
    )
    count = (
        "jsonb_array_length(NEW.result_canonical::jsonb->'reasons')"
        if pg
        else "json_array_length(NEW.result_canonical,'$.reasons')"
    )
    event = """EXISTS(SELECT 1 FROM economic_events e WHERE e.business_id=NEW.business_id AND e.event_uuid=NEW.event_uuid
        AND e.source_type=NEW.source_type AND e.source_id=NEW.source_id AND e.source_revision=NEW.source_revision
        AND e.origin=NEW.origin AND e.content_hash=NEW.event_content_hash AND e.record_hash=NEW.event_record_hash
        AND e.operation_uuid=NEW.operation_uuid AND e.authorization_uuid=NEW.authorization_uuid)"""
    live = """EXISTS(SELECT 1 FROM financial_operations o JOIN financial_authorizations a ON a.business_id=o.business_id
        AND a.authorization_uuid=o.authorization_uuid WHERE o.business_id=NEW.business_id AND o.operation_uuid=NEW.operation_uuid
        AND o.state='committed' AND o.entry_namespace<>'historical' AND a.authorization_uuid=NEW.authorization_uuid
        AND a.kind='human_confirmation' AND a.channel<>'historical' AND a.actor_user_id IS NOT NULL
        AND a.validated_permission='financial.authorize' AND a.approved_request_hash=o.request_hash
        AND a.revoked_at IS NULL)"""
    historical = """EXISTS(SELECT 1 FROM financial_history_import_items p
        JOIN financial_history_items i ON i.business_id=p.business_id AND i.manifest_uuid=p.manifest_uuid AND i.item_uuid=p.item_uuid
        JOIN financial_history_reconciliations r ON r.business_id=p.business_id AND r.batch_uuid=p.batch_uuid
        JOIN financial_operations o ON o.business_id=p.business_id AND o.operation_uuid=p.operation_uuid
        JOIN financial_authorizations a ON a.business_id=p.business_id AND a.authorization_uuid=p.authorization_uuid
        WHERE p.business_id=NEW.business_id AND p.batch_uuid=NEW.batch_uuid AND p.manifest_uuid=NEW.manifest_uuid
        AND p.item_uuid=NEW.item_uuid AND p.state='recorded' AND p.event_uuid=NEW.event_uuid
        AND p.operation_uuid=NEW.operation_uuid AND p.authorization_uuid=NEW.authorization_uuid
        AND r.reconciliation_uuid=NEW.reconciliation_uuid AND r.state='frozen' AND r.result='PASS'
        AND o.state='prepared' AND o.entry_namespace='historical' AND a.kind='historical_unknown'
        AND a.actor_user_id IS NULL AND a.actor_session_version IS NULL
        AND ((i.classification='A' AND NEW.quality='verified_fact') OR (i.classification='B' AND NEW.quality='observed_state')))"""
    actor = "EXISTS(SELECT 1 FROM users u WHERE u.business_id=NEW.business_id AND u.id=NEW.created_by AND u.is_active=TRUE AND u.session_version=NEW.session_version)"
    consistency = " AND ".join(
        f"{value(f)}=NEW.{f}{cast if f in ('business_id', 'event_uuid', 'operation_uuid', 'authorization_uuid') else ''}"
        for f in ("business_id", "outcome", "source_hash", "context_hash")
    )

    def proof_value(field, part):
        return (
            f"(NEW.known_unknown_canonical::jsonb #>> '{{{field},{part}}}')"
            if pg
            else f"json_extract(NEW.known_unknown_canonical,'$.{field}.{part}')"
        )

    proof_valid = " AND ".join(
        f"COALESCE({proof_value(f, 'state')} IN ('known','unknown'),FALSE) AND "
        + f"(({proof_value(f, 'state')}='unknown' AND {proof_value(f, 'value_hash')} IS NULL) OR ({proof_value(f, 'state')}='known' AND length({proof_value(f, 'value_hash')})=64))"
        for f in FIELDS
    )
    purpose_type = " OR ".join(
        "(NEW.purpose='" + p.value + "' AND NEW.source_type='" + kind + "')"
        for p, (kind, _) in CATALOG.items()
        if kind is not None
    )
    coverage = " OR ".join(
        "(NEW.source_type='"
        + kind
        + "' AND EXISTS(SELECT 1 FROM "
        + table
        + " c WHERE c.business_id=NEW.business_id AND c.event_uuid=NEW.event_uuid AND c.operation_uuid=NEW.operation_uuid AND c.operation_state='committed'))"
        for kind, table in (
            ("invoice", "invoice_economic_coverage"),
            ("invoice_payment", "payment_economic_coverage"),
            ("received_invoice", "supplier_invoice_economic_coverage"),
            ("expense", "expense_economic_coverage"),
            ("bank_transaction", "bank_import_coverage"),
        )
    )
    guard(
        conn,
        TABLE + "_insert",
        TABLE,
        "INSERT",
        f"NOT ({actor}) OR NOT COALESCE(({consistency}),FALSE) OR "
        + f"NOT COALESCE(({proof_valid}),FALSE) OR (NEW.outcome='resolved' AND NEW.purpose<>'inspect_evidence' AND NOT ({purpose_type})) OR "
        + f"EXISTS(SELECT 1 FROM {reasons} WHERE r.value NOT IN ({literals(Reason)})) OR "
        + f"(NEW.outcome='resolved' AND ({count}<>0 OR NOT ({event}) OR NOT ((NEW.origin='live' AND NEW.quality='verified_fact' AND {live} AND ({coverage})) OR (NEW.origin='historical' AND {historical})))) "
        + f"OR (NEW.outcome='blocked' AND {count}=0) OR (NEW.event_uuid IS NOT NULL AND NOT EXISTS(SELECT 1 FROM economic_events e WHERE e.business_id=NEW.business_id AND e.event_uuid=NEW.event_uuid AND e.origin=NEW.origin))",
    )


def downgrade(conn):
    if conn.execute(f"SELECT 1 FROM {TABLE} LIMIT 1").fetchone():
        raise ValueError("Conservar resoluciones de antecedentes; bajada75 bloqueada.")
    from noesis.financial_history.import_schema import _drop

    for name in ("immutable", "retain", "insert"):
        _drop(conn, TABLE + "_" + name, TABLE)
    conn.execute("DROP TABLE " + TABLE)
