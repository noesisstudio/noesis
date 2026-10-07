"""Migration78 aditiva; prueba E append-only y autorización ligada a conexión/TX."""

from noesis.financial_history.schema import guard
from noesis.financial_history.import_schema import _drop
import re

EXPORTS = "financial_export_manifests"
POLICIES = "financial_retention_policies"
INVENTORIES = "financial_retention_inventories"
PLANS = "financial_closure_plans"
AUTHORIZATIONS = "financial_closure_authorizations"
RECEIPTS = "financial_closure_receipts"
TOMBSTONES = "financial_privacy_tombstones"
RESTORED = "financial_restore_suppressions"
CLIENT_ERASURES = "financial_client_erasure_receipts"
TABLES = (EXPORTS, POLICIES, INVENTORIES, PLANS, AUTHORIZATIONS, RECEIPTS, CLIENT_ERASURES, TOMBSTONES)


def closed_sql(alias="NEW"):
    return (f"EXISTS(SELECT 1 FROM {AUTHORIZATIONS} ca WHERE ca.business_id={alias}.business_id) "
            f"OR EXISTS(SELECT 1 FROM {RECEIPTS} cr WHERE cr.business_id={alias}.business_id) "
            f"OR EXISTS(SELECT 1 FROM {RESTORED} rs WHERE rs.business_id={alias}.business_id AND rs.scope='account_local_access')")


def body_field(pg, path):
    return "NEW.body_canonical::jsonb #>> '{" + path.replace(".", ",") + "}'" if pg else "json_extract(NEW.body_canonical,'$." + path + "')"


def upgrade(conn):
    pg = conn.dialect == "postgres"
    ref, uid = ("BIGINT", "UUID") if pg else ("INTEGER", "TEXT")
    if pg:
        # Metadatos E/restore son infraestructura administrativa, no dinero.
        # Mismo HMAC/backend/TX, sólo los dos kinds cerrados de privacidad.
        # El verificador D original y su restricción de login quedan intactos.
        definition = conn.execute_exact("SELECT pg_get_functiondef('noesis_execution_context()'::regprocedure) AS body").fetchone()["body"]
        definition = definition.replace("noesis_execution_context()", "noesis_privacy_context()", 1)
        definition, removed = re.subn(r"IF has_table_privilege\(session_user,.*?THEN RETURN '\{\}'::jsonb; END IF;", "", definition, count=1, flags=re.S)
        if removed != 1:
            raise ValueError("Verificador D inesperado; no instalar restore E.")
        definition = definition.replace("RETURN proof;", "IF proof->>'kind' NOT IN ('financial_privacy','financial_privacy_restore') THEN RETURN '{}'::jsonb; END IF; RETURN proof;")
        conn.execute_exact(definition)
    conn.execute(f"CREATE TABLE {RESTORED}(business_id {ref} NOT NULL REFERENCES businesses(id),evidence_uuid {uid} NOT NULL,scope TEXT NOT NULL CHECK(scope IN ('account_local_access','client_contact')),client_id {ref},body_canonical TEXT NOT NULL,content_hash TEXT NOT NULL CHECK(length(content_hash)=64),PRIMARY KEY(business_id,evidence_uuid),FOREIGN KEY(business_id,client_id) REFERENCES clients(business_id,id),CHECK((scope='account_local_access' AND client_id IS NULL) OR (scope='client_contact' AND client_id IS NOT NULL)))")
    guard(conn, RESTORED + "_immutable", RESTORED, "UPDATE", "TRUE")
    guard(conn, RESTORED + "_retain", RESTORED, "DELETE", "TRUE")
    field = lambda k: f"noesis_privacy_context()->>'{k}'" if pg else f"json_extract(noesis_execution_context(),'$.{k}')"
    sha = "encode(sha256(convert_to(NEW.body_canonical,'UTF8')),'hex')" if pg else "noesis_sha256(NEW.body_canonical)"
    guard(conn, RESTORED + "_insert", RESTORED, "INSERT", f"{field('kind')} IS DISTINCT FROM 'financial_privacy_restore' OR CAST({field('business_id')} AS TEXT) IS DISTINCT FROM CAST(NEW.business_id AS TEXT) OR {field('evidence_uuid')} IS DISTINCT FROM CAST(NEW.evidence_uuid AS TEXT) OR {field('content_hash')} IS DISTINCT FROM NEW.content_hash OR {sha}<>NEW.content_hash OR {body_field(pg, 'scope')} IS DISTINCT FROM NEW.scope OR CAST({body_field(pg, 'selector.business_id')} AS TEXT) IS DISTINCT FROM CAST(NEW.business_id AS TEXT) OR CAST({body_field(pg, 'selector.client_id')} AS TEXT) IS DISTINCT FROM CAST(NEW.client_id AS TEXT)")
    # Body sólo contiene metadata/counts/hashes/refs. Nunca contenido del export.
    for table in TABLES:
        extra = ""
        if table == EXPORTS:
            extra = ", context_hash TEXT NOT NULL CHECK(length(context_hash)=64)"
        elif table == POLICIES:
            extra = ", status TEXT NOT NULL CHECK(status IN ('provisional','approved_for_operation'))"
        elif table == INVENTORIES:
            extra = f", policy_uuid {uid} NOT NULL, FOREIGN KEY(business_id,policy_uuid) REFERENCES {POLICIES}(business_id,evidence_uuid)"
        elif table == PLANS:
            extra = f", inventory_uuid {uid} NOT NULL, privacy_request_id {ref} NOT NULL, FOREIGN KEY(business_id,inventory_uuid) REFERENCES {INVENTORIES}(business_id,evidence_uuid), FOREIGN KEY(privacy_request_id) REFERENCES privacy_requests(id)"
        elif table == AUTHORIZATIONS:
            extra = f", plan_uuid {uid} NOT NULL, approved_hash TEXT NOT NULL, UNIQUE(business_id,plan_uuid), UNIQUE(business_id), FOREIGN KEY(business_id,plan_uuid) REFERENCES {PLANS}(business_id,evidence_uuid)"
        elif table == RECEIPTS:
            extra = f", plan_uuid {uid} NOT NULL, authorization_uuid {uid} NOT NULL, UNIQUE(business_id,plan_uuid), UNIQUE(business_id), FOREIGN KEY(business_id,plan_uuid) REFERENCES {PLANS}(business_id,evidence_uuid), FOREIGN KEY(business_id,authorization_uuid) REFERENCES {AUTHORIZATIONS}(business_id,evidence_uuid)"
        elif table == TOMBSTONES:
            extra = f", receipt_uuid {uid}, client_erasure_uuid {uid}, CHECK((receipt_uuid IS NOT NULL AND client_erasure_uuid IS NULL) OR (receipt_uuid IS NULL AND client_erasure_uuid IS NOT NULL)), FOREIGN KEY(business_id,receipt_uuid) REFERENCES {RECEIPTS}(business_id,evidence_uuid), FOREIGN KEY(business_id,client_erasure_uuid) REFERENCES {CLIENT_ERASURES}(business_id,evidence_uuid)"
        elif table == CLIENT_ERASURES:
            extra = f", client_id {ref} NOT NULL, policy_uuid {uid} NOT NULL, privacy_request_id {ref} NOT NULL, FOREIGN KEY(business_id,client_id) REFERENCES clients(business_id,id), FOREIGN KEY(business_id,policy_uuid) REFERENCES {POLICIES}(business_id,evidence_uuid), FOREIGN KEY(privacy_request_id) REFERENCES privacy_requests(id)"
        conn.execute(f"""CREATE TABLE {table} (
            business_id {ref} NOT NULL REFERENCES businesses(id), evidence_uuid {uid} NOT NULL,
            contract_version INTEGER NOT NULL CHECK(contract_version=1),
            created_by {ref} NOT NULL, session_version INTEGER NOT NULL CHECK(session_version>=0),
            created_at TEXT NOT NULL, body_canonical TEXT NOT NULL,
            content_hash TEXT NOT NULL CHECK(length(content_hash)=64){extra},
            PRIMARY KEY(business_id,evidence_uuid), FOREIGN KEY(business_id,created_by) REFERENCES users(business_id,id))""")
        guard(conn, table + "_immutable", table, "UPDATE", "TRUE")
        guard(conn, table + "_retain", table, "DELETE", "TRUE")
        field = lambda k: f"noesis_privacy_context()->>'{k}'" if pg else f"json_extract(noesis_execution_context(),'$.{k}')"
        sha = "encode(sha256(convert_to(NEW.body_canonical,'UTF8')),'hex')" if pg else "noesis_sha256(NEW.body_canonical)"
        condition = (f"{field('kind')} IS DISTINCT FROM 'financial_privacy' OR "
                     f"{field('table')} IS DISTINCT FROM '{table}' OR "
                     f"CAST({field('business_id')} AS TEXT) IS DISTINCT FROM CAST(NEW.business_id AS TEXT) OR "
                     f"{field('evidence_uuid')} IS DISTINCT FROM CAST(NEW.evidence_uuid AS TEXT) OR "
                     f"{field('content_hash')} IS DISTINCT FROM NEW.content_hash OR {sha}<>NEW.content_hash OR "
                     f"CAST({field('created_by')} AS TEXT) IS DISTINCT FROM CAST(NEW.created_by AS TEXT) OR "
                     f"CAST({field('session_version')} AS TEXT) IS DISTINCT FROM CAST(NEW.session_version AS TEXT) OR "
                     f"{field('created_at')} IS DISTINCT FROM NEW.created_at OR "
                     "NOT EXISTS(SELECT 1 FROM users u WHERE u.id=NEW.created_by AND u.business_id=NEW.business_id "
                     "AND u.session_version=NEW.session_version)")
        guard(conn, table + "_insert", table, "INSERT", condition)
        # No basta con un hash válido: columnas relacionales y cuerpo firmado
        # deben describir la misma entidad/tenant/autorización.
        bindings = {
            EXPORTS: {"evidence_uuid": "export_uuid", "business_id": "business_id", "context_hash": "context_hash"},
            POLICIES: {"evidence_uuid": "policy.policy_uuid", "status": "policy.status"},
            INVENTORIES: {"evidence_uuid": "inventory_uuid", "business_id": "business_id", "policy_uuid": "policy_uuid"},
            PLANS: {"evidence_uuid": "plan_uuid", "business_id": "business_id", "inventory_uuid": "inventory_uuid", "privacy_request_id": "privacy_request_id"},
            AUTHORIZATIONS: {"evidence_uuid": "authorization_uuid", "business_id": "business_id", "plan_uuid": "plan_uuid", "approved_hash": "approved_hash", "created_by": "actor_user_id", "session_version": "session_version"},
            RECEIPTS: {"evidence_uuid": "receipt_uuid", "business_id": "business_id", "plan_uuid": "plan_uuid", "authorization_uuid": "authorization_uuid", "created_by": "actor_user_id", "session_version": "session_version"},
            CLIENT_ERASURES: {"business_id": "business_id", "client_id": "client_id", "policy_uuid": "policy_uuid", "privacy_request_id": "privacy_request_id", "created_by": "actor_user_id", "session_version": "session_version"},
            TOMBSTONES: {"business_id": "business_id", "receipt_uuid": "closure_uuid", "client_erasure_uuid": "suppression_uuid"},
        }[table]
        guard(conn, table + "_body", table, "INSERT", " OR ".join(f"CAST({body_field(pg, path)} AS TEXT) IS DISTINCT FROM CAST(NEW.{column} AS TEXT)" for column, path in bindings.items()))
    # FK existente privacy_requests(id) no es compuesta: tenant se comprueba explícitamente.
    guard(conn, PLANS + "_scope", PLANS, "INSERT",
          "NOT EXISTS(SELECT 1 FROM privacy_requests p WHERE p.id=NEW.privacy_request_id AND p.business_id=NEW.business_id AND p.request_type='account_closure')")
    guard(conn, AUTHORIZATIONS + "_scope", AUTHORIZATIONS, "INSERT",
          f"NOT EXISTS(SELECT 1 FROM {PLANS} p WHERE p.business_id=NEW.business_id AND p.evidence_uuid=NEW.plan_uuid AND p.content_hash=NEW.approved_hash AND p.created_by=NEW.created_by AND p.session_version=NEW.session_version)")
    guard(conn, RECEIPTS + "_scope", RECEIPTS, "INSERT",
          f"NOT EXISTS(SELECT 1 FROM {AUTHORIZATIONS} a WHERE a.business_id=NEW.business_id AND a.evidence_uuid=NEW.authorization_uuid AND a.plan_uuid=NEW.plan_uuid AND a.created_by=NEW.created_by AND a.session_version=NEW.session_version)")
    guard(conn, CLIENT_ERASURES + "_scope", CLIENT_ERASURES, "INSERT",
          "NOT EXISTS(SELECT 1 FROM privacy_requests p WHERE p.id=NEW.privacy_request_id AND p.business_id=NEW.business_id AND p.request_type='erasure')")
    # Autorización formal/aplicación bloquean nuevas operaciones, epoch y resume;
    # una privacy_request administrativa no participa en este predicado.
    for table in ("financial_operations", "financial_history_epochs", "financial_activation_requests"):
        guard(conn, "privacy_closed_" + table, table, "INSERT", "(" + closed_sql() + ")")
    guard(conn, "privacy_closed_control", "financial_activation_control", "UPDATE",
          "(" + closed_sql() + ") AND NEW.state IN ('enabled','ready','validating')")
    # No nueva escritura legacy final ni destrucción de prueba durante/después del cierre.
    sources = ("invoices", "invoice_lines", "invoice_payments", "received_invoices", "expenses", "bank_transactions", "invoice_records", "invoice_cancellation_records", "documents")
    for table in sources:
        for action in ("INSERT", "UPDATE", "DELETE"):
            alias = "OLD" if action == "DELETE" else "NEW"
            condition = "(" + closed_sql(alias) + ")"
            if action == "UPDATE":
                # Cambiar business_id no permite sacar una fuente de una cuenta
                # cerrada hacia otra abierta: comprobar ambos lados del UPDATE.
                condition += " OR (" + closed_sql("OLD") + ")"
            guard(conn, "privacy_closed_" + table + "_" + action.lower(), table, action, condition)


def downgrade(conn):
    if any(conn.execute(f"SELECT 1 FROM {t} LIMIT 1").fetchone() for t in TABLES + (RESTORED,)):
        raise ValueError("Migration78 conserva evidencia E; downgrade bloqueado.")
    for table in ("financial_operations", "financial_history_epochs", "financial_activation_requests"):
        _drop(conn, "privacy_closed_" + table, table)
    _drop(conn, "privacy_closed_control", "financial_activation_control")
    for table in ("invoices", "invoice_lines", "invoice_payments", "received_invoices", "expenses", "bank_transactions", "invoice_records", "invoice_cancellation_records", "documents"):
        for action in ("insert", "update", "delete"):
            _drop(conn, "privacy_closed_" + table + "_" + action, table)
    for table in reversed(TABLES):
        for suffix in ("insert", "body", "immutable", "retain") + (("scope",) if table in (PLANS, AUTHORIZATIONS, RECEIPTS, CLIENT_ERASURES) else ()):
            _drop(conn, table + "_" + suffix, table)
        conn.execute("DROP TABLE " + table)
    for suffix in ("insert", "immutable", "retain"):
        _drop(conn, RESTORED + "_" + suffix, RESTORED)
    conn.execute("DROP TABLE " + RESTORED)
    if conn.dialect == "postgres":
        conn.execute("DROP FUNCTION noesis_privacy_context()")
