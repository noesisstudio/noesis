"""Migration76: cobertura fiscal live inmutable, sin backfill ni dispatch."""

TABLE = "invoice_fiscal_cancellation_coverage"
TRIGGERS = (("fiscal_cancel_coverage_insert", TABLE),
            ("fiscal_cancel_event_insert", "economic_events"),
            ("fiscal_cancel_result", "financial_operations"),
            ("fiscal_cancel_coverage_update", TABLE),
            ("fiscal_cancel_coverage_delete", TABLE))
INDICES = ("idx_fiscal_cancel_record_invoice", "idx_fiscal_cancel_original_event",
           "idx_fiscal_cancel_event_scope")


def _guard(conn, name, table, action, condition):
    if conn.dialect == "postgres":
        conn.execute(f"""CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF {condition} THEN RAISE EXCEPTION 'Captura fiscal incoherente'
            USING ERRCODE = '23514'; END IF;
            IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END $$""")
        conn.execute(f"CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION {name}()")
    else:
        conn.execute(f"CREATE TRIGGER {name} BEFORE {action} ON {table} WHEN {condition} "
                     "BEGIN SELECT RAISE(ABORT,'Captura fiscal incoherente'); END")


def upgrade(conn):
    pg = conn.dialect == "postgres"
    ref, uid = ("BIGINT", "UUID") if pg else ("INTEGER", "TEXT")
    conn.execute("CREATE UNIQUE INDEX idx_fiscal_cancel_record_invoice ON invoice_cancellation_records(business_id,id,invoice_id)")
    conn.execute("CREATE UNIQUE INDEX idx_fiscal_cancel_original_event ON economic_events(business_id,event_uuid,invoice_id,event_type)")
    conn.execute("CREATE UNIQUE INDEX idx_fiscal_cancel_event_scope ON economic_events(business_id,event_uuid,invoice_cancellation_record_id,source_revision,event_type,operation_uuid)")
    conn.execute(f"""CREATE TABLE {TABLE} (
        business_id {ref} NOT NULL,invoice_id {ref} NOT NULL,cancellation_record_id {ref} NOT NULL,
        antecedent_resolution_uuid {uid} NOT NULL,
        antecedent_outcome TEXT NOT NULL DEFAULT 'resolved' CHECK(antecedent_outcome='resolved'),
        antecedent_purpose TEXT NOT NULL DEFAULT 'fiscal_cancel_invoice' CHECK(antecedent_purpose='fiscal_cancel_invoice'),
        antecedent_quality TEXT NOT NULL DEFAULT 'verified_fact' CHECK(antecedent_quality='verified_fact'),
        antecedent_origin TEXT NOT NULL DEFAULT 'live' CHECK(antecedent_origin='live'),
        original_invoice_event_uuid {uid} NOT NULL,original_event_type TEXT NOT NULL CHECK(original_event_type IN ('invoice.issued','invoice.rectified')),
        event_uuid {uid} NOT NULL,operation_uuid {uid} NOT NULL,
        event_type TEXT NOT NULL CHECK(event_type='invoice.fiscal_cancellation_registered'),
        source_revision BIGINT NOT NULL CHECK(source_revision>0),
        source_fingerprint TEXT NOT NULL CHECK(length(source_fingerprint)=64),
        resolution_content_hash TEXT NOT NULL CHECK(length(resolution_content_hash)=64),
        resolution_context_hash TEXT NOT NULL CHECK(length(resolution_context_hash)=64),
        operation_state TEXT NOT NULL DEFAULT 'committed' CHECK(operation_state='committed'),
        PRIMARY KEY(business_id,invoice_id),UNIQUE(business_id,cancellation_record_id),
        UNIQUE(business_id,operation_uuid),UNIQUE(business_id,event_uuid),
        FOREIGN KEY(business_id,invoice_id) REFERENCES invoices(business_id,id),
        FOREIGN KEY(business_id,cancellation_record_id,invoice_id) REFERENCES invoice_cancellation_records(business_id,id,invoice_id),
        FOREIGN KEY(business_id,antecedent_resolution_uuid,antecedent_outcome,antecedent_purpose,antecedent_quality,antecedent_origin,original_invoice_event_uuid)
            REFERENCES financial_antecedent_resolutions(business_id,resolution_uuid,outcome,purpose,quality,origin,event_uuid),
        FOREIGN KEY(business_id,original_invoice_event_uuid,invoice_id,original_event_type)
            REFERENCES economic_events(business_id,event_uuid,invoice_id,event_type),
        FOREIGN KEY(business_id,event_uuid,cancellation_record_id,source_revision,event_type,operation_uuid)
            REFERENCES economic_events(business_id,event_uuid,invoice_cancellation_record_id,source_revision,event_type,operation_uuid) DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY(business_id,operation_uuid,operation_state)
            REFERENCES financial_operations(business_id,operation_uuid,state) DEFERRABLE INITIALLY DEFERRED)""")

    cast = "::text" if pg else ""

    def json_value(column, path):
        return (f"({column}::jsonb #>> '{{{path.replace('.', ',')}}}')" if pg
                else f"json_extract({column},'$.{path}')")

    request = lambda path: json_value("o.request_canonical", path)
    coverage_valid = f"""EXISTS(SELECT 1 FROM financial_operations o
        JOIN financial_authorizations a ON a.business_id=o.business_id AND a.authorization_uuid=o.authorization_uuid
        JOIN financial_antecedent_resolutions r ON r.business_id=o.business_id AND r.resolution_uuid=NEW.antecedent_resolution_uuid
        JOIN invoice_cancellation_records f ON f.business_id=r.business_id AND f.id=NEW.cancellation_record_id AND f.invoice_id=NEW.invoice_id
        JOIN verifactu_cancellation_outbox q ON q.business_id=f.business_id AND q.record_id=f.id AND q.invoice_id=f.invoice_id
        JOIN verifactu_outbox original ON original.business_id=f.business_id AND original.record_id=f.original_record_id AND original.invoice_id=f.invoice_id
        WHERE o.business_id=NEW.business_id AND o.operation_uuid=NEW.operation_uuid AND o.state='approved'
        AND o.command_type='invoice.fiscal_cancel' AND o.entry_namespace<>'historical'
        AND a.operation_uuid=o.operation_uuid AND a.kind='human_confirmation'
        AND a.approved_request_hash=o.request_hash AND a.actor_user_id=o.created_by
        AND a.validated_permission='financial.authorize'
        AND a.channel<>'historical' AND a.revoked_at IS NULL
        AND r.source_type='invoice' AND r.source_id=NEW.invoice_id
        AND r.outcome='resolved' AND r.purpose='fiscal_cancel_invoice' AND r.quality='verified_fact' AND r.origin='live'
        AND r.event_uuid=NEW.original_invoice_event_uuid AND r.created_by=o.created_by AND r.session_version=a.actor_session_version
        AND r.content_hash=NEW.resolution_content_hash AND r.context_hash=NEW.resolution_context_hash
        AND {request('target_id')}=NEW.invoice_id{cast} AND {request('amount')} IS NULL
        AND {request('expected_revision')}=r.source_revision{cast}
        AND {request('reason')}=f.reason AND length(f.reason) BETWEEN 5 AND 1000
        AND {request('parameters.antecedent_resolution_uuid')}=r.resolution_uuid{cast}
        AND {request('parameters.resolution_content_hash')}=r.content_hash
        AND {request('parameters.resolution_context_hash')}=r.context_hash
        AND {request('parameters.invoice_event_uuid')}=r.event_uuid{cast}
        AND {request('parameters.invoice_event_content_hash')}=r.event_content_hash
        AND {request('parameters.invoice_event_record_hash')}=r.event_record_hash
        AND {request('parameters.fiscal_record_id')}=f.original_record_id{cast}
        AND q.status='pendiente' AND q.attempts=0
        AND original.status IN ('aceptado','aceptado_con_errores')
        AND NOT EXISTS(SELECT 1 FROM invoice_cancellation_records x WHERE x.business_id=f.business_id AND x.invoice_id=f.invoice_id AND x.id<>f.id))"""
    _guard(conn, "fiscal_cancel_coverage_insert", TABLE, "INSERT", f"NOT COALESCE(({coverage_valid}),FALSE)")

    payload = lambda field: json_value("NEW.payload_canonical", field)
    total = json_value("original.payload_canonical", "total")
    payload_shape = ("jsonb_typeof(NEW.payload_canonical::jsonb->'original_total')='string' "
                     "AND (SELECT count(*) FROM jsonb_object_keys(NEW.payload_canonical::jsonb))=5" if pg
                     else "json_type(NEW.payload_canonical,'$.original_total')='text' "
                     "AND (SELECT count(*) FROM json_each(NEW.payload_canonical))=5")
    event_valid = f"""EXISTS(SELECT 1 FROM {TABLE} c
        JOIN invoice_cancellation_records f ON f.business_id=c.business_id AND f.id=c.cancellation_record_id
        JOIN economic_events original ON original.business_id=c.business_id AND original.event_uuid=c.original_invoice_event_uuid
        WHERE c.business_id=NEW.business_id AND c.event_uuid=NEW.event_uuid AND c.operation_uuid=NEW.operation_uuid
        AND c.cancellation_record_id=NEW.source_id AND c.source_revision=NEW.source_revision
        AND NEW.source_type='invoice_cancellation_record' AND NEW.origin='live' AND NEW.event_slot='primary'
        AND NEW.amount IS NULL AND NEW.currency='EUR' AND NEW.payload_version=1
        AND {payload_shape}
        AND NEW.provenance='fiscal_cancellation_capture.v1:' || c.source_fingerprint
        AND {payload('invoice_id')}=c.invoice_id{cast} AND {payload('invoice_number')}=f.invoice_number
        AND {payload('reason')}=f.reason AND {payload('original_total')}={total}
        AND {payload('registered_on')}=substr(f.generated_at{cast},1,10)
        AND EXISTS(SELECT 1 FROM economic_event_links l WHERE l.business_id=c.business_id AND l.event_uuid=c.event_uuid
            AND l.relation_type='evidence_for' AND l.target_event_uuid=c.original_invoice_event_uuid))"""
    _guard(conn, "fiscal_cancel_event_insert", "economic_events", "INSERT",
           f"NEW.event_type='invoice.fiscal_cancellation_registered' AND NEW.origin='live' AND NOT COALESCE(({event_valid}),FALSE)")

    result = lambda field: json_value("NEW.result_canonical", field)
    truth = "'true'" if pg else "1"
    count = ("(SELECT count(*) FROM jsonb_object_keys(NEW.result_canonical::jsonb))" if pg
             else "(SELECT count(*) FROM json_each(NEW.result_canonical))")
    null_amount = ("NEW.result_canonical::jsonb->'amount'='null'::jsonb" if pg
                   else "json_type(NEW.result_canonical,'$.amount')='null'")
    total_string = ("jsonb_typeof(NEW.result_canonical::jsonb->'original_total')='string'" if pg
                    else "json_type(NEW.result_canonical,'$.original_total')='text'")
    bool_captured = ("NEW.result_canonical::jsonb->'captured'='true'::jsonb" if pg
                     else "json_type(NEW.result_canonical,'$.captured')='true'")
    result_valid = f"""EXISTS(SELECT 1 FROM {TABLE} c JOIN economic_events e ON e.business_id=c.business_id AND e.event_uuid=c.event_uuid
        WHERE c.business_id=NEW.business_id AND c.operation_uuid=NEW.operation_uuid
        AND {result('invoice_id')}=c.invoice_id{cast}
        AND {result('cancellation_record_id')}=c.cancellation_record_id{cast}
        AND {result('antecedent_resolution_uuid')}=c.antecedent_resolution_uuid{cast}
        AND {result('original_invoice_event_uuid')}=c.original_invoice_event_uuid{cast}
        AND {result('event_uuid')}=c.event_uuid{cast} AND {result('event_type')}=e.event_type
        AND {result('content_hash')}=e.content_hash AND {result('source_revision')}=c.source_revision{cast}
        AND {result('source_fingerprint')}=c.source_fingerprint
        AND {result('original_total')}={json_value('e.payload_canonical', 'original_total')}
        AND {result('amount')} IS NULL AND {result('currency')}='EUR' AND {result('captured')}={truth}
        AND {null_amount} AND {total_string} AND {bool_captured} AND {count}=13)"""
    _guard(conn, "fiscal_cancel_result", "financial_operations", "UPDATE",
           f"NEW.state='committed' AND NEW.command_type='invoice.fiscal_cancel' AND NOT COALESCE(({result_valid}),FALSE)")
    _guard(conn, "fiscal_cancel_coverage_update", TABLE, "UPDATE", "TRUE")
    _guard(conn, "fiscal_cancel_coverage_delete", TABLE, "DELETE", "TRUE")


def downgrade(conn):
    if (conn.execute(f"SELECT 1 FROM {TABLE} LIMIT 1").fetchone()
            or conn.execute("SELECT 1 FROM economic_events WHERE origin='live' AND event_type='invoice.fiscal_cancellation_registered' LIMIT 1").fetchone()
            or conn.execute("SELECT 1 FROM financial_operations WHERE state='committed' AND command_type='invoice.fiscal_cancel' LIMIT 1").fetchone()):
        raise ValueError("Conservar evidencia de captura fiscal; bajada76 bloqueada.")
    for name, table in reversed(TRIGGERS):
        conn.execute(f"DROP TRIGGER {name}" + (f" ON {table}" if conn.dialect == "postgres" else ""))
        if conn.dialect == "postgres":
            conn.execute(f"DROP FUNCTION {name}()")
    conn.execute(f"DROP TABLE {TABLE}")
    for name in reversed(INDICES):
        conn.execute(f"DROP INDEX {name}")
