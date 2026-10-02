"""DDL: eventos/relaciones append-only y contador, sin productores."""

from .contracts import CATALOG, RelationType
from noesis.financial_operations.schema import _uuid_check

SOURCES = {
    "invoice": ("invoices", "invoice_id"),
    "invoice_payment": ("invoice_payments", "invoice_payment_id"),
    "received_invoice": ("received_invoices", "received_invoice_id"),
    "expense": ("expenses", "expense_id"),
    "bank_transaction": ("bank_transactions", "bank_transaction_id"),
    "invoice_cancellation_record": (
        "invoice_cancellation_records",
        "invoice_cancellation_record_id",
    ),
}


def upgrade(conn):
    pg = conn.dialect == "postgres"
    ref, uid, stamp = ("BIGINT", "UUID", "TIMESTAMPTZ") if pg else ("INTEGER", "TEXT", "TEXT")
    for table, _ in SOURCES.values():
        conn.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS idx_econ_{table}_scope ON {table}(business_id, id)"
        )
    conn.execute(
        "CREATE UNIQUE INDEX idx_econ_authorization_scope ON financial_authorizations(business_id, operation_uuid, authorization_uuid)"
    )
    conn.execute(f"""CREATE TABLE economic_event_sequences (
        business_id {ref} PRIMARY KEY REFERENCES businesses(id),
        last_sequence {ref} NOT NULL DEFAULT 0 CHECK(last_sequence BETWEEN 0 AND 9223372036854775807))""")
    source_columns = ",".join(f"{col} {ref}" for _, col in SOURCES.values())
    source_fks = ",".join(
        f"FOREIGN KEY(business_id,{col}) REFERENCES {table}(business_id,id)"
        for table, col in SOURCES.values()
    )
    source_checks = " OR ".join(
        "(source_type='"
        + source
        + "' AND source_id="
        + col
        + " AND "
        + col
        + " IS NOT NULL AND "
        + " AND ".join(other + " IS NULL" for _, other in SOURCES.values() if other != col)
        + ")"
        for source, (_, col) in SOURCES.items()
    )
    types = ",".join("'" + kind.value + "'" for kind in CATALOG)
    compatibility = " OR ".join(
        f"(event_type='{kind.value}' AND source_type='{spec.source_type.value}')"
        for kind, spec in CATALOG.items()
    )
    money = "NUMERIC" if pg else "TEXT"
    # Sin typmod: ningún cast NUMERIC(20,4) puede redondear antes del CHECK.
    amount_check = (
        "amount BETWEEN -9999999999999999.99 AND 9999999999999999.99 AND amount=trunc(amount,2)"
        if pg
        else "typeof(amount)='text' AND length(amount)<=20"
    )
    conn.execute(f"""CREATE TABLE economic_events (
        id {"BIGSERIAL" if pg else "INTEGER"} PRIMARY KEY,
        business_id {ref} NOT NULL REFERENCES businesses(id),
        event_uuid {uid} NOT NULL, business_sequence {ref} NOT NULL CHECK(business_sequence>0),
        event_type TEXT NOT NULL CHECK(event_type IN ({types})), payload_version INTEGER NOT NULL CHECK(payload_version=1),
        operation_uuid {uid}, event_slot TEXT NOT NULL CHECK(length(event_slot) BETWEEN 1 AND 64),
        idempotency_key TEXT NOT NULL CHECK(length(idempotency_key)=64),
        source_type TEXT NOT NULL, source_id {ref} NOT NULL CHECK(source_id>0),
        source_revision {ref} NOT NULL CHECK(source_revision>0), {source_columns},
        occurred_at {stamp}, observed_at {stamp} NOT NULL,
        economic_date {"DATE" if pg else "TEXT"}, date_precision TEXT NOT NULL CHECK(date_precision IN ('instant','day','unknown')),
        date_provenance TEXT NOT NULL CHECK(length(date_provenance) BETWEEN 1 AND 256),
        currency TEXT NOT NULL CHECK(currency='EUR'), amount {money}, authorization_uuid {uid},
        origin TEXT NOT NULL CHECK(origin IN ('live','historical')), historical_batch_uuid {uid},
        provenance TEXT NOT NULL CHECK(length(provenance) BETWEEN 1 AND 256),
        canonical_version INTEGER NOT NULL CHECK(canonical_version=1),
        payload_canonical TEXT NOT NULL, canonical_event TEXT NOT NULL,
        content_hash TEXT NOT NULL CHECK(length(content_hash)=64), record_hash TEXT NOT NULL CHECK(length(record_hash)=64),
        recorded_at {stamp} NOT NULL,
        UNIQUE(business_id,event_uuid), UNIQUE(event_uuid), UNIQUE(business_id,business_sequence),
        UNIQUE(business_id,operation_uuid,event_slot), UNIQUE(business_id,idempotency_key),
        UNIQUE(business_id,source_type,source_id,source_revision,event_type),
        {source_fks},
        FOREIGN KEY(business_id) REFERENCES economic_event_sequences(business_id),
        FOREIGN KEY(business_id,operation_uuid) REFERENCES financial_operations(business_id,operation_uuid),
        FOREIGN KEY(business_id,operation_uuid,authorization_uuid)
            REFERENCES financial_authorizations(business_id,operation_uuid,authorization_uuid),
        CHECK({source_checks}), CHECK({compatibility}), CHECK(amount IS NULL OR ({amount_check})),
        CHECK((origin='live' AND operation_uuid IS NOT NULL AND authorization_uuid IS NOT NULL AND historical_batch_uuid IS NULL)
           OR (origin='historical' AND historical_batch_uuid IS NOT NULL AND
               ((operation_uuid IS NULL AND authorization_uuid IS NULL) OR (operation_uuid IS NOT NULL AND authorization_uuid IS NOT NULL)))),
        CHECK((date_precision='instant' AND occurred_at IS NOT NULL) OR
              (date_precision='day' AND occurred_at IS NULL AND economic_date IS NOT NULL) OR
              (date_precision='unknown' AND occurred_at IS NULL AND economic_date IS NULL)),
        {_uuid_check("event_uuid", pg)}, {_uuid_check("operation_uuid", pg)},
        {_uuid_check("authorization_uuid", pg)}, {_uuid_check("historical_batch_uuid", pg)}
    )""")
    relations = ",".join("'" + kind.value + "'" for kind in RelationType)
    conn.execute(f"""CREATE TABLE economic_event_links (
        business_id {ref} NOT NULL, event_uuid {uid} NOT NULL, target_event_uuid {uid} NOT NULL,
        relation_type TEXT NOT NULL CHECK(relation_type IN ({relations})), recorded_at {stamp} NOT NULL,
        PRIMARY KEY(business_id,event_uuid,relation_type), CHECK(event_uuid<>target_event_uuid),
        FOREIGN KEY(business_id,event_uuid) REFERENCES economic_events(business_id,event_uuid) DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY(business_id,target_event_uuid) REFERENCES economic_events(business_id,event_uuid),
        {_uuid_check("event_uuid", pg)}, {_uuid_check("target_event_uuid", pg)}
    )""")
    conn.execute(
        "CREATE INDEX idx_econ_source ON economic_events(business_id,source_type,source_id)"
    )
    conn.execute(
        "CREATE INDEX idx_econ_links_target ON economic_event_links(business_id,target_event_uuid)"
    )
    _guards(conn)


def _guards(conn):
    pg = conn.dialect == "postgres"

    def json_value(path):
        return (
            "(NEW.canonical_event::jsonb #>> '{" + path.replace(".", ",") + "}')"
            if pg
            else "json_extract(NEW.canonical_event,'$." + path + "')"
        )

    eq = "IS NOT DISTINCT FROM" if pg else "IS"
    text_cast = "::text" if pg else ""
    tests = [
        f"{json_value(key)} {eq} NEW.{col}{text_cast}"
        for key, col in (
            ("event_id", "event_uuid"),
            ("business_id", "business_id"),
            ("event_type", "event_type"),
            ("source_type", "source_type"),
            ("source_id", "source_id"),
            ("source_revision", "source_revision"),
            ("payload_version", "payload_version"),
            ("currency", "currency"),
        )
    ]
    # SQLite devuelve enteros JSON: no convertir los campos numéricos a texto.
    amounts, dates, counts = [], [], []
    for kind, spec in CATALOG.items():
        path = None if spec.amount_path is None else "payload." + ".".join(spec.amount_path)
        value = "NULL" if path is None else json_value(path)
        if pg and path is not None:
            value += "::numeric"
        amounts.append(f"(NEW.event_type='{kind.value}' AND NEW.amount {eq} {value})")
        date_value = json_value("payload." + spec.economic_date_field) + ("::date" if pg else "")
        dates.append(f"(NEW.event_type='{kind.value}' AND NEW.economic_date {eq} {date_value})")
        counts.append(
            f"(NEW.event_type='{kind.value}' AND (SELECT COUNT(*) FROM economic_event_links l "
            f"WHERE l.business_id=NEW.business_id AND l.event_uuid=NEW.event_uuid)={len(spec.relations)})"
        )
    payload_equal = (
        "NEW.payload_canonical::jsonb=NEW.canonical_event::jsonb->'payload'"
        if pg
        else "json(NEW.payload_canonical)=json_extract(NEW.canonical_event,'$.payload')"
    )
    auth = """(NEW.operation_uuid IS NULL OR EXISTS (SELECT 1 FROM financial_operations o
        JOIN financial_authorizations a ON a.business_id=o.business_id AND a.operation_uuid=o.operation_uuid
            AND a.authorization_uuid=NEW.authorization_uuid
        WHERE o.business_id=NEW.business_id AND o.operation_uuid=NEW.operation_uuid
            AND o.authorization_uuid=a.authorization_uuid AND a.approved_request_hash=o.request_hash
            AND ((NEW.origin='live' AND o.state IN ('approved','committed') AND a.kind IN ('human_confirmation','mandate'))
              OR (NEW.origin='historical' AND a.kind='historical_unknown'))))"""
    valid = " AND ".join(
        tests
        + [
            payload_equal,
            "(" + " OR ".join(amounts) + ")",
            "(" + " OR ".join(dates) + ")",
            "(" + " OR ".join(counts) + ")",
            auth,
            f"NEW.business_sequence {eq} (SELECT last_sequence FROM economic_event_sequences WHERE business_id=NEW.business_id)",
        ]
    )
    # Los links se preinsertan con FK diferida; al incorporar el evento se verifica el conjunto completo.
    rules = []
    for kind, spec in CATALOG.items():
        for rule in spec.relations:
            targets = ",".join("'" + t.value + "'" for t in rule.targets)
            same = (
                " AND s.source_type=t.source_type AND s.source_id=t.source_id AND s.source_revision>t.source_revision"
                if rule.kind in (RelationType.CORRECTS, RelationType.VOIDS)
                else ""
            )
            rules.append(
                f"(s.event_type='{kind.value}' AND l.relation_type='{rule.kind.value}' AND t.event_type IN ({targets}){same})"
            )
    allowed = "(" + " OR ".join(rules) + ")"
    bad_links = f"""EXISTS(SELECT 1 FROM economic_event_links l JOIN economic_events s
        ON s.business_id=l.business_id AND s.event_uuid=l.event_uuid
        JOIN economic_events t ON t.business_id=l.business_id AND t.event_uuid=l.target_event_uuid
        WHERE l.business_id=NEW.business_id AND l.event_uuid=NEW.event_uuid AND NOT {allowed})"""
    if pg:
        declared = """EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.canonical_event::jsonb->'relations') r
            WHERE r->>'kind'=l.relation_type AND r->>'target_event_id'=l.target_event_uuid::text
            AND r->>'target_event_type'=t.event_type AND r->>'business_id'=l.business_id::text)"""
    else:
        declared = """EXISTS(SELECT 1 FROM json_each(NEW.canonical_event,'$.relations') r
            WHERE json_extract(r.value,'$.kind')=l.relation_type
            AND json_extract(r.value,'$.target_event_id')=l.target_event_uuid
            AND json_extract(r.value,'$.target_event_type')=t.event_type
            AND json_extract(r.value,'$.business_id')=l.business_id)"""
    valid += (
        " AND NOT ("
        + bad_links
        + ") AND NOT EXISTS(SELECT 1 FROM economic_event_links l JOIN economic_events t ON t.business_id=l.business_id AND t.event_uuid=l.target_event_uuid WHERE l.business_id=NEW.business_id AND l.event_uuid=NEW.event_uuid AND NOT ("
        + declared
        + "))"
    )

    cycle = """EXISTS(WITH RECURSIVE trail(event_uuid) AS (
        SELECT NEW.target_event_uuid UNION SELECT l.target_event_uuid FROM economic_event_links l JOIN trail t
        ON l.event_uuid=t.event_uuid WHERE l.business_id=NEW.business_id AND l.relation_type IN ('corrects','voids','rectifies'))
        SELECT 1 FROM trail WHERE event_uuid=NEW.event_uuid)"""
    sealed = "EXISTS(SELECT 1 FROM economic_events WHERE business_id=NEW.business_id AND event_uuid=NEW.event_uuid)"
    if pg:
        definitions = [
            (
                "econ_sequence_insert",
                "economic_event_sequences",
                "BEFORE INSERT",
                "IF NEW.last_sequence<>0 THEN RAISE EXCEPTION 'Contador inicial cero' USING ERRCODE = '23514'; END IF;",
            ),
            (
                "econ_event_insert",
                "economic_events",
                "AFTER INSERT",
                f"IF NOT ({valid}) THEN RAISE EXCEPTION 'Evento incoherente' USING ERRCODE = '23514'; END IF;",
            ),
            (
                "econ_link_insert",
                "economic_event_links",
                "BEFORE INSERT",
                f"IF NEW.relation_type IN ('corrects','voids','rectifies') AND {cycle} THEN RAISE EXCEPTION 'Ciclo correctivo' USING ERRCODE = '23514'; END IF; IF {sealed} THEN RAISE EXCEPTION 'Relaciones selladas' USING ERRCODE = '23514'; END IF;",
            ),
            (
                "econ_sequence_update",
                "economic_event_sequences",
                "BEFORE UPDATE",
                "IF NEW.business_id<>OLD.business_id OR NEW.last_sequence<>OLD.last_sequence+1 THEN RAISE EXCEPTION 'Secuencia inválida' USING ERRCODE = '23514'; END IF;",
            ),
        ]
        for name, table, event, body in definitions:
            conn.execute(
                f"CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN {body} RETURN NEW; END $$"
            )
            conn.execute(
                f"CREATE TRIGGER {name} {event} ON {table} FOR EACH ROW EXECUTE FUNCTION {name}()"
            )
        conn.execute(
            "CREATE FUNCTION econ_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Economic Event append-only' USING ERRCODE = '23514'; END $$"
        )
        for table in ("economic_events", "economic_event_links"):
            conn.execute(
                f"CREATE TRIGGER econ_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION econ_immutable()"
            )
    else:
        for name, table, action, condition in (
            (
                "econ_sequence_insert",
                "economic_event_sequences",
                "BEFORE INSERT",
                "NEW.last_sequence<>0",
            ),
            ("econ_event_insert", "economic_events", "AFTER INSERT", f"NOT ({valid})"),
            (
                "econ_link_insert",
                "economic_event_links",
                "BEFORE INSERT",
                f"(NEW.relation_type IN ('corrects','voids','rectifies') AND {cycle}) OR {sealed}",
            ),
            (
                "econ_sequence_update",
                "economic_event_sequences",
                "BEFORE UPDATE",
                "NEW.business_id<>OLD.business_id OR NEW.last_sequence<>OLD.last_sequence+1",
            ),
        ):
            conn.execute(
                f"CREATE TRIGGER {name} {action} ON {table} WHEN {condition} BEGIN SELECT RAISE(ABORT,'Invariante económica'); END"
            )
        for table in ("economic_events", "economic_event_links"):
            for action in ("UPDATE", "DELETE"):
                conn.execute(
                    f"CREATE TRIGGER {table}_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'Economic Event append-only'); END"
                )


def downgrade(conn):
    if any(
        conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
        for table in ("economic_events", "economic_event_links")
    ):
        raise ValueError("No retirar Economic Events durables; conservar esquema y datos.")
    for table in ("economic_event_links", "economic_events", "economic_event_sequences"):
        conn.execute(f"DROP TABLE {table}")
    if conn.dialect == "postgres":
        for name in (
            "econ_sequence_insert",
            "econ_event_insert",
            "econ_link_insert",
            "econ_sequence_update",
            "econ_immutable",
        ):
            conn.execute(f"DROP FUNCTION {name}()")
    conn.execute("DROP INDEX idx_econ_authorization_scope")
    for table, _ in SOURCES.values():
        conn.execute(f"DROP INDEX idx_econ_{table}_scope")
