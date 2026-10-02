"""Migración 62: solo operaciones/autorizaciones; sin tablas de Economic Events."""


def _uuid_check(column, pg):
    nonzero = f"{column}<>'00000000-0000-0000-0000-000000000000'"
    if pg:
        shape = nonzero
    else:
        shape = (f"length({column})=36 AND {column}=lower({column}) AND "
                 f"length(replace({column},'-',''))=32 AND "
                 f"replace({column},'-','') NOT GLOB '*[^0-9a-f]*' AND "
                 + " AND ".join(f"substr({column},{pos},1)='-'" for pos in (9, 14, 19, 24))
                 + f" AND {nonzero}")
    return f"CHECK({column} IS NULL OR ({shape}))"


def upgrade(conn):
    pg = conn.dialect == "postgres"
    ident = "UUID" if pg else "TEXT"
    ref = "BIGINT" if pg else "INTEGER"
    stamp = "TIMESTAMPTZ" if pg else "TEXT"
    # El actor se enlaza por negocio sin añadir columnas a usuarios legacy.
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_financial_users_scope ON users(business_id, id)")
    conn.execute(f"""CREATE TABLE financial_operations (
        business_id {ref} NOT NULL REFERENCES businesses(id),
        operation_uuid {ident} NOT NULL,
        entry_namespace TEXT NOT NULL CHECK(entry_namespace IN
            ('web_api','chat','whatsapp','document_review','recurring','import','historical')),
        entry_key TEXT NOT NULL CHECK(length(entry_key)=64),
        created_by {ref} NOT NULL,
        command_type TEXT NOT NULL CHECK(command_type IN ('invoice.issue','invoice.rectify',
            'customer_payment.record','supplier_invoice.confirm','supplier_invoice.correct',
            'supplier_invoice.void','expense.confirm','expense.void','bank_transaction.import',
            'bank_transaction.match','invoice.fiscal_cancel')),
        command_version INTEGER NOT NULL CHECK(command_version=1),
        request_canonical TEXT NOT NULL CHECK(length(request_canonical)<=65536),
        request_hash TEXT NOT NULL CHECK(length(request_hash)=64),
        expected_revision {ref} CHECK(expected_revision>0),
        state TEXT NOT NULL DEFAULT 'prepared'
            CHECK(state IN ('prepared','approved','committed','rejected','cancelled')),
        authorization_uuid {ident},
        result_version INTEGER CHECK(result_version=1),
        result_canonical TEXT CHECK(length(result_canonical)<=65536),
        result_hash TEXT CHECK(length(result_hash)=64),
        created_at {stamp} NOT NULL, updated_at {stamp} NOT NULL, committed_at {stamp},
        PRIMARY KEY(business_id, operation_uuid), UNIQUE(operation_uuid),
        UNIQUE(business_id, entry_namespace, entry_key),
        UNIQUE(business_id, operation_uuid, request_hash),
        FOREIGN KEY(business_id, created_by) REFERENCES users(business_id, id),
        CHECK((state='committed' AND authorization_uuid IS NOT NULL AND result_version IS NOT NULL
               AND result_canonical IS NOT NULL AND result_hash IS NOT NULL AND committed_at IS NOT NULL)
           OR (state<>'committed' AND result_version IS NULL AND result_canonical IS NULL
               AND result_hash IS NULL AND committed_at IS NULL)),
        CHECK(state NOT IN ('approved','committed') OR authorization_uuid IS NOT NULL)
        ,{_uuid_check('operation_uuid', pg)}, {_uuid_check('authorization_uuid', pg)}
    )""")
    conn.execute(f"""CREATE TABLE financial_authorizations (
        business_id {ref} NOT NULL REFERENCES businesses(id),
        authorization_uuid {ident} NOT NULL,
        operation_uuid {ident},
        kind TEXT NOT NULL CHECK(kind IN ('human_confirmation','mandate','historical_unknown')),
        actor_user_id {ref}, recorded_by {ref} NOT NULL,
        actor_session_version INTEGER CHECK(actor_session_version>=0),
        validated_permission TEXT NOT NULL CHECK(validated_permission IN
            ('financial.authorize','financial.mandate','historical.record')),
        approved_request_hash TEXT NOT NULL CHECK(length(approved_request_hash)=64),
        approved_revision {ref} CHECK(approved_revision>0),
        channel TEXT NOT NULL CHECK(channel IN
            ('web_api','chat','whatsapp','document_review','recurring','import','historical')),
        mandate_uuid {ident}, authorized_at {stamp} NOT NULL,
        expires_at {stamp}, revoked_at {stamp},
        PRIMARY KEY(business_id, authorization_uuid), UNIQUE(authorization_uuid),
        UNIQUE(business_id, operation_uuid, authorization_uuid, approved_request_hash),
        FOREIGN KEY(business_id, recorded_by) REFERENCES users(business_id, id),
        FOREIGN KEY(business_id, actor_user_id) REFERENCES users(business_id, id),
        FOREIGN KEY(business_id, operation_uuid, approved_request_hash)
            REFERENCES financial_operations(business_id, operation_uuid, request_hash),
        FOREIGN KEY(business_id, mandate_uuid)
            REFERENCES financial_authorizations(business_id, authorization_uuid),
        CHECK((kind='historical_unknown' AND actor_user_id IS NULL AND actor_session_version IS NULL
               AND validated_permission='historical.record' AND operation_uuid IS NOT NULL)
           OR (kind<>'historical_unknown' AND actor_user_id IS NOT NULL AND actor_session_version IS NOT NULL)),
        CHECK(operation_uuid IS NOT NULL OR (kind='mandate' AND expires_at IS NOT NULL)),
        CHECK(mandate_uuid IS NULL OR (kind='mandate' AND operation_uuid IS NOT NULL)),
        CHECK(kind<>'human_confirmation' OR validated_permission='financial.authorize'),
        CHECK(kind<>'mandate' OR validated_permission='financial.mandate'),
        CHECK(operation_uuid IS NULL OR (expires_at IS NULL AND revoked_at IS NULL)),
        CHECK(kind='mandate' OR mandate_uuid IS NULL)
        ,{_uuid_check('authorization_uuid', pg)}, {_uuid_check('operation_uuid', pg)}, {_uuid_check('mandate_uuid', pg)}
    )""")
    if pg:
        conn.execute("""ALTER TABLE financial_operations ADD CONSTRAINT financial_operation_authorization
            FOREIGN KEY(business_id, operation_uuid, authorization_uuid, request_hash)
            REFERENCES financial_authorizations(business_id, operation_uuid, authorization_uuid, approved_request_hash)
            DEFERRABLE INITIALLY DEFERRED""")
    # SQLite no admite ADD CONSTRAINT: la equivalencia se impone con trigger.
    conn.execute("CREATE INDEX idx_financial_operations_state ON financial_operations(business_id, state, created_at)")
    conn.execute("CREATE INDEX idx_financial_authorizations_operation ON financial_authorizations(business_id, operation_uuid)")
    _guards(conn)


def _guards(conn):
    pg = conn.dialect == "postgres"
    identity = ("business_id", "operation_uuid", "entry_namespace", "entry_key", "created_by",
                "command_type", "command_version", "request_canonical", "request_hash",
                "expected_revision", "created_at")
    auth_identity = ("business_id", "authorization_uuid", "operation_uuid", "kind", "actor_user_id",
                     "recorded_by", "actor_session_version", "validated_permission", "approved_request_hash",
                     "approved_revision", "channel", "mandate_uuid", "authorized_at", "expires_at")
    distinct = "IS DISTINCT FROM" if pg else "IS NOT"
    immutable = " OR ".join(f"NEW.{key} {distinct} OLD.{key}" for key in identity)
    auth_immutable = " OR ".join(f"NEW.{key} {distinct} OLD.{key}" for key in auth_identity)
    equal = "IS NOT DISTINCT FROM" if pg else "IS"
    authorization = f"""NOT EXISTS (SELECT 1 FROM financial_authorizations a
        WHERE a.business_id=NEW.business_id AND a.operation_uuid=NEW.operation_uuid
        AND a.authorization_uuid=NEW.authorization_uuid AND a.approved_request_hash=NEW.request_hash
        AND a.approved_revision {equal} NEW.expected_revision
        AND (NEW.state IN ('prepared','cancelled','rejected') AND a.kind='historical_unknown'
             OR NEW.state<>'prepared' AND a.kind IN ('human_confirmation','mandate')))"""
    update_invalid = f"""({immutable}) OR OLD.state IN ('committed','rejected','cancelled') OR
        NOT (OLD.state='prepared' AND NEW.state IN ('prepared','approved','rejected','cancelled')
          OR OLD.state='approved' AND NEW.state IN ('committed','rejected','cancelled')) OR
        (OLD.state='approved' AND NEW.authorization_uuid {distinct} OLD.authorization_uuid) OR
        (NEW.authorization_uuid IS NOT NULL AND ({authorization}))"""
    auth_invalid = f"""({auth_immutable}) OR OLD.operation_uuid IS NOT NULL OR
        OLD.revoked_at IS NOT NULL OR NEW.revoked_at IS NULL"""
    if pg:
        for name, body, table in (
            ("financial_operation_guard", f"""
                IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Registro financiero durable' USING ERRCODE = '23514'; END IF;
                IF TG_OP='INSERT' THEN
                    IF NEW.state<>'prepared' OR NEW.authorization_uuid IS NOT NULL THEN
                        RAISE EXCEPTION 'Operación nueva debe estar prepared' USING ERRCODE = '23514'; END IF;
                ELSE
                    IF {update_invalid} THEN RAISE EXCEPTION 'Transición financiera inválida' USING ERRCODE = '23514'; END IF;
                END IF; RETURN NEW;""", "financial_operations"),
            ("financial_authorization_guard", f"""
                IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Autorización durable' USING ERRCODE = '23514'; END IF;
                IF {auth_invalid} THEN RAISE EXCEPTION 'Evidencia inmutable' USING ERRCODE = '23514'; END IF;
                RETURN NEW;""", "financial_authorizations"),
        ):
            conn.execute(f"CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN {body} END $$")
            events = "INSERT OR UPDATE OR DELETE" if table == "financial_operations" else "UPDATE OR DELETE"
            conn.execute(f"CREATE TRIGGER {name} BEFORE {events} ON {table} FOR EACH ROW EXECUTE FUNCTION {name}()")
    else:
        for name, action, table, condition, message in (
            ("financial_operation_insert", "INSERT", "financial_operations",
             "NEW.state<>'prepared' OR NEW.authorization_uuid IS NOT NULL", "Operación nueva debe estar prepared"),
            ("financial_operation_update", "UPDATE", "financial_operations", update_invalid, "Transición financiera inválida"),
            ("financial_operation_delete", "DELETE", "financial_operations", "1=1", "Registro financiero durable"),
            ("financial_authorization_update", "UPDATE", "financial_authorizations", auth_invalid, "Evidencia inmutable"),
            ("financial_authorization_delete", "DELETE", "financial_authorizations", "1=1", "Autorización durable"),
        ):
            conn.execute(f"CREATE TRIGGER {name} BEFORE {action} ON {table} WHEN {condition} "
                         f"BEGIN SELECT RAISE(ABORT, '{message}'); END")


def downgrade(conn):
    if conn.execute("SELECT 1 FROM financial_operations LIMIT 1").fetchone() or conn.execute(
            "SELECT 1 FROM financial_authorizations LIMIT 1").fetchone():
        raise ValueError("Migración 62 conserva operaciones/autorizaciones durables; no revertir con datos.")
    if conn.dialect == "postgres":
        conn.execute("ALTER TABLE financial_operations DROP CONSTRAINT financial_operation_authorization")
    conn.execute("DROP TABLE financial_authorizations")
    conn.execute("DROP TABLE financial_operations")
    if conn.dialect == "postgres":
        conn.execute("DROP FUNCTION financial_authorization_guard()")
        conn.execute("DROP FUNCTION financial_operation_guard()")
    conn.execute("DROP INDEX idx_financial_users_scope")
