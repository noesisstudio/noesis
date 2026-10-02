"""Solo enlaces de propuesta y recibos mínimos; autoridad en operaciones1.2."""


def _guard(conn, name, table, event):
    if conn.dialect == "postgres":
        conn.execute(
            f"CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            "RAISE EXCEPTION 'Evidencia de canal inmutable' USING ERRCODE = '23514'; END $$"
        )
        conn.execute(
            f"CREATE TRIGGER {name} BEFORE {event} ON {table} FOR EACH ROW EXECUTE FUNCTION {name}()"
        )
    else:
        conn.execute(
            f"CREATE TRIGGER {name} BEFORE {event} ON {table} BEGIN "
            "SELECT RAISE(ABORT,'Evidencia de canal inmutable'); END"
        )


def upgrade(conn):
    conn.execute("ALTER TABLE recurring_invoice_runs ADD COLUMN financial_template_hash TEXT")
    uuid = "UUID" if conn.dialect == "postgres" else "TEXT"
    integer = "BIGINT" if conn.dialect == "postgres" else "INTEGER"
    conn.execute(f"""CREATE TABLE financial_channel_proposals (
        business_id {integer} NOT NULL, operation_uuid {uuid} NOT NULL,
        request_hash TEXT NOT NULL CHECK(length(request_hash)=64),
        actor_session_version INTEGER NOT NULL CHECK(actor_session_version>=0),
        channel TEXT NOT NULL CHECK(channel IN ('web_api','chat','whatsapp','document_review','recurring','import')),
        actor_key TEXT NOT NULL CHECK(length(actor_key)=64),
        intent_canonical TEXT NOT NULL, intent_hash TEXT NOT NULL CHECK(length(intent_hash)=64),
        preview TEXT NOT NULL, expires_at TEXT NOT NULL, created_at TEXT NOT NULL,
        recurring_context TEXT, origin_message_hash TEXT, origin_channel TEXT NOT NULL, origin_key TEXT NOT NULL,
        PRIMARY KEY(business_id,operation_uuid),
        UNIQUE(business_id,operation_uuid,request_hash),
        UNIQUE(business_id,origin_channel,origin_key),
        FOREIGN KEY(business_id,operation_uuid,request_hash)
          REFERENCES financial_operations(business_id,operation_uuid,request_hash)
    )""")
    conn.execute(f"""CREATE TABLE financial_channel_receipts (
        business_id {integer} NOT NULL, channel TEXT NOT NULL,
        receipt_key TEXT NOT NULL CHECK(length(receipt_key)=64),
        operation_uuid {uuid} NOT NULL, request_hash TEXT NOT NULL,
        decision TEXT NOT NULL CHECK(decision IN ('review','yes','no')),
        authorization_uuid {uuid}, recorded_at TEXT NOT NULL, message_hash TEXT,
        PRIMARY KEY(business_id,channel,receipt_key),
        CHECK((decision='yes' AND authorization_uuid IS NOT NULL) OR
              (decision IN ('review','no') AND authorization_uuid IS NULL)),
        FOREIGN KEY(business_id,operation_uuid,request_hash)
          REFERENCES financial_channel_proposals(business_id,operation_uuid,request_hash),
        FOREIGN KEY(business_id,operation_uuid,authorization_uuid,request_hash)
          REFERENCES financial_authorizations(business_id,operation_uuid,authorization_uuid,approved_request_hash)
    )""")
    for table in ("financial_channel_proposals", "financial_channel_receipts"):
        for event in ("UPDATE", "DELETE"):
            _guard(conn, table + "_immutable_" + event.lower(), table, event)
    conn.execute(
        "CREATE INDEX idx_financial_channel_actor ON financial_channel_proposals "
        "(business_id,channel,actor_key,created_at)"
    )


def downgrade(conn):
    for table in ("financial_channel_receipts", "financial_channel_proposals"):
        if conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
            raise ValueError(
                "Conservar propuestas/recibos financieros; no borrar evidencia para bajar."
            )
    for table in ("financial_channel_receipts", "financial_channel_proposals"):
        conn.execute(f"DROP TABLE {table}")
        if conn.dialect == "postgres":
            for event in ("update", "delete"):
                conn.execute(f"DROP FUNCTION {table}_immutable_{event}()")
    conn.execute("ALTER TABLE recurring_invoice_runs DROP COLUMN financial_template_hash")
