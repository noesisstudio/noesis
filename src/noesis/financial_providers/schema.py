"""M79 aditiva: evidencia F inmutable y guards tenant/conexión/TX."""

import re
from noesis.financial_history.schema import guard, literals
from noesis.financial_history.import_schema import _drop
from noesis.financial_privacy.schema import closed_sql
from .contracts import Provider, Implementation, Level, Environment, Result, DispatchResult, Observation

ATTESTATIONS = "financial_provider_attestations"
RUNS = "financial_provider_preflight_runs"
BINDINGS = "financial_activation_preflight_bindings"
OUTBOX_BINDINGS = "financial_provider_outbox_bindings"
ATTEMPTS = "financial_provider_dispatch_attempts"
STARTS = "financial_provider_dispatch_starts"
RESULTS = "financial_provider_dispatch_results"
OBSERVATIONS = "financial_operational_observations"
TABLES = (ATTESTATIONS, RUNS, BINDINGS, OUTBOX_BINDINGS, ATTEMPTS, STARTS, RESULTS, OBSERVATIONS)
OUTBOXES = ("verifactu_outbox", "verifactu_cancellation_outbox", "email_outbox", "whatsapp_outbox")


def upgrade(conn):
    pg = conn.dialect == "postgres"
    uid, ref = ("UUID", "BIGINT") if pg else ("TEXT", "INTEGER")
    if pg:
        definition = conn.execute_exact("SELECT pg_get_functiondef('noesis_privacy_context()'::regprocedure) AS body").fetchone()["body"]
        definition = definition.replace("noesis_privacy_context()", "noesis_provider_context()", 1)
        definition, count = re.subn("NOT IN \\('financial_privacy','financial_privacy_restore'\\)", "NOT IN ('financial_provider')", definition, count=1)
        if count != 1:
            raise ValueError("Verificador E inesperado; no instalar F.")
        conn.execute_exact(definition)
    ctx = "noesis_provider_context()" if pg else "noesis_execution_context()"
    get = lambda field: f"({ctx}->>'{field}')" if pg else f"json_extract({ctx},'$.{field}')"
    def body(field):
        return f"(NEW.body_canonical::jsonb->>'{field}')" if pg else f"json_extract(NEW.body_canonical,'$.{field}')"
    specs = {
        ATTESTATIONS: f"""provider TEXT NOT NULL CHECK(provider IN ({literals(Provider)})),
            implementation TEXT NOT NULL CHECK(implementation IN ({literals(Implementation)})), capability TEXT NOT NULL,
            environment TEXT NOT NULL CHECK(environment IN ({literals(Environment)})), level TEXT NOT NULL CHECK(level IN ({literals(Level)})),
            configuration_fingerprint TEXT NOT NULL CHECK(length(configuration_fingerprint)=64),
            credential_fingerprint TEXT NOT NULL CHECK(length(credential_fingerprint)=64),
            expires_at TEXT NOT NULL, result TEXT NOT NULL CHECK(result IN ({literals(Result)})), source_attempt_uuid {uid},
            CHECK((level='production_observed' AND source_attempt_uuid IS NOT NULL) OR (level<>'production_observed' AND source_attempt_uuid IS NULL))""",
        RUNS: f"""evaluation_uuid {uid} NOT NULL, context_hash TEXT NOT NULL CHECK(length(context_hash)=64),
            result TEXT NOT NULL CHECK(result IN ({literals(Result)})), expires_at TEXT NOT NULL,
            FOREIGN KEY(business_id,evaluation_uuid) REFERENCES financial_readiness_evaluations(business_id,evaluation_uuid)""",
        BINDINGS: f"""request_uuid {uid} NOT NULL, preflight_uuid {uid} NOT NULL, preflight_hash TEXT NOT NULL CHECK(length(preflight_hash)=64),
            UNIQUE(business_id,request_uuid),
            FOREIGN KEY(business_id,request_uuid) REFERENCES financial_activation_requests(business_id,request_uuid),
            FOREIGN KEY(business_id,preflight_uuid) REFERENCES {RUNS}(business_id,evidence_uuid)""",
        OUTBOX_BINDINGS: f"""outbox_type TEXT NOT NULL CHECK(outbox_type IN ({literals(OUTBOXES)})), outbox_id {ref} NOT NULL,
            operation_uuid {uid} NOT NULL, activation_generation INTEGER NOT NULL CHECK(activation_generation>0),
            capability TEXT NOT NULL, provider TEXT NOT NULL CHECK(provider IN ({literals(Provider)})),
            request_fingerprint TEXT NOT NULL CHECK(length(request_fingerprint)=64),
            UNIQUE(business_id,outbox_type,outbox_id),
            FOREIGN KEY(business_id,operation_uuid) REFERENCES financial_operations(business_id,operation_uuid),
            FOREIGN KEY(business_id,activation_generation,capability) REFERENCES financial_activation_grants(business_id,activation_generation,capability)""",
        ATTEMPTS: f"""binding_uuid {uid} NOT NULL, attestation_uuid {uid} NOT NULL,
            operation_uuid {uid} NOT NULL, activation_generation INTEGER NOT NULL, capability TEXT NOT NULL,
            provider TEXT NOT NULL CHECK(provider IN ({literals(Provider)})), request_fingerprint TEXT NOT NULL,
            idempotency_fingerprint TEXT NOT NULL CHECK(length(idempotency_fingerprint)=64),
            UNIQUE(business_id,binding_uuid),
            FOREIGN KEY(business_id,binding_uuid) REFERENCES {OUTBOX_BINDINGS}(business_id,evidence_uuid),
            FOREIGN KEY(business_id,attestation_uuid) REFERENCES {ATTESTATIONS}(business_id,evidence_uuid),
            FOREIGN KEY(business_id,operation_uuid) REFERENCES financial_operations(business_id,operation_uuid),
            FOREIGN KEY(business_id,activation_generation,capability) REFERENCES financial_activation_grants(business_id,activation_generation,capability)""",
        STARTS: f"""attempt_uuid {uid} NOT NULL, UNIQUE(business_id,attempt_uuid),
            FOREIGN KEY(business_id,attempt_uuid) REFERENCES {ATTEMPTS}(business_id,evidence_uuid)""",
        RESULTS: f"""attempt_uuid {uid} NOT NULL, result TEXT NOT NULL CHECK(result IN ({literals(DispatchResult)})),
            UNIQUE(business_id,attempt_uuid), FOREIGN KEY(business_id,attempt_uuid) REFERENCES {ATTEMPTS}(business_id,evidence_uuid)""",
        OBSERVATIONS: f"kind TEXT NOT NULL CHECK(kind IN ({literals(Observation)}))",
    }
    if not pg:
        specs[ATTESTATIONS] += f",FOREIGN KEY(business_id,source_attempt_uuid) REFERENCES {ATTEMPTS}(business_id,evidence_uuid)"
    for table, extra in specs.items():
        conn.execute_exact(f"""CREATE TABLE {table} (
            business_id {ref} NOT NULL REFERENCES businesses(id), evidence_uuid {uid} NOT NULL,
            contract_version INTEGER NOT NULL CHECK(contract_version=1), created_by {ref} NOT NULL,
            session_version INTEGER NOT NULL CHECK(session_version>=0), created_at TEXT NOT NULL,
            body_canonical TEXT NOT NULL, content_hash TEXT NOT NULL CHECK(length(content_hash)=64), {extra},
            PRIMARY KEY(business_id,evidence_uuid),
            FOREIGN KEY(business_id,created_by) REFERENCES users(business_id,id))""")
        for action in ("UPDATE", "DELETE"):
            guard(conn, "fp_immutable_" + table + "_" + action.lower(), table, action, "TRUE")
        conditions = [f"COALESCE({get('kind')},'')<>'financial_provider'",
                      f"COALESCE({get('table')},'')<>'{table}'",
                      f"COALESCE({get('business_id')},'0')<>CAST(NEW.business_id AS TEXT)",
                      f"COALESCE({get('evidence_uuid')},'')<>CAST(NEW.evidence_uuid AS TEXT)",
                      f"COALESCE({get('content_hash')},'')<>NEW.content_hash",
                      f"COALESCE({get('actor_user_id')},'0')<>CAST(NEW.created_by AS TEXT)",
                      f"COALESCE({get('actor_session_version')},'-1')<>CAST(NEW.session_version AS TEXT)",
                      f"COALESCE({get('created_at')},'')<>NEW.created_at",
                      f"{body('business_id')}<>CAST(NEW.business_id AS TEXT)",
                      ("encode(sha256(convert_to(NEW.body_canonical,'UTF8')),'hex')<>NEW.content_hash" if pg else "noesis_sha256(NEW.body_canonical)<>NEW.content_hash"),
                      (f"NOT EXISTS(SELECT 1 FROM users u WHERE u.business_id=NEW.business_id AND u.id=NEW.created_by AND u.is_active=TRUE AND u.session_version=NEW.session_version) AND NOT EXISTS(SELECT 1 FROM {ATTEMPTS} a JOIN {STARTS} st ON st.business_id=a.business_id AND st.attempt_uuid=a.evidence_uuid WHERE a.business_id=NEW.business_id AND a.evidence_uuid=NEW.attempt_uuid AND a.created_by=NEW.created_by AND a.session_version=NEW.session_version)" if table == RESULTS else
                       "NOT EXISTS(SELECT 1 FROM users u WHERE u.business_id=NEW.business_id AND u.id=NEW.created_by AND u.is_active=TRUE AND u.session_version=NEW.session_version)")]
        # SQLite JSON integers se comparan como texto explícito, igual que PostgreSQL.
        if not pg:
            for k in ("business_id", "actor_user_id", "actor_session_version"):
                conditions = [c.replace(get(k), "CAST(" + get(k) + " AS TEXT)") for c in conditions]
            conditions = [c.replace(body("business_id"), "CAST(" + body("business_id") + " AS TEXT)") for c in conditions]
        fields = {
            ATTESTATIONS: ("provider", "implementation", "capability", "environment", "level", "configuration_fingerprint", "credential_fingerprint", "expires_at", "result"),
            RUNS: ("evaluation_uuid", "context_hash", "result", "expires_at"),
            BINDINGS: ("request_uuid", "preflight_uuid", "preflight_hash"),
            OUTBOX_BINDINGS: ("outbox_type", "outbox_id", "operation_uuid", "activation_generation", "capability", "provider", "request_fingerprint"),
            ATTEMPTS: ("binding_uuid", "attestation_uuid", "operation_uuid", "activation_generation", "capability", "provider", "request_fingerprint", "idempotency_fingerprint"),
            STARTS: ("attempt_uuid",), RESULTS: ("attempt_uuid", "result"), OBSERVATIONS: ("kind",),
        }[table]
        conditions += [f"COALESCE(CAST({body(f)} AS TEXT),'')<>CAST(NEW.{f} AS TEXT)" for f in fields]
        if table == ATTESTATIONS:
            conditions += [f"COALESCE(CAST({body('source_attempt_uuid')} AS TEXT),'')<>COALESCE(CAST(NEW.source_attempt_uuid AS TEXT),'')"]
        if table in (ATTEMPTS, OUTBOX_BINDINGS, STARTS):
            conditions.append("(" + closed_sql() + ")")
        guard(conn, "fp_context_" + table, table, "INSERT", " OR ".join(conditions))
    if pg:
        # La prueba observed apunta a un intento que a su vez usa una prueba.
        # Sólo la restauración íntegra difiere esta FK; cada TX normal la exige.
        conn.execute_exact(f'ALTER TABLE {ATTESTATIONS} ADD CONSTRAINT fp_observed_attempt_fk FOREIGN KEY(business_id,source_attempt_uuid) REFERENCES {ATTEMPTS}(business_id,evidence_uuid) DEFERRABLE INITIALLY IMMEDIATE')
    _domain_guards(conn, body)
    synthetic = "(a.body_canonical::jsonb #>> '{evidence,synthetic}')='false'" if pg else "json_extract(a.body_canonical,'$.evidence.synthetic')=0"
    real_io = "(r.body_canonical::jsonb->>'real_io')='true'" if pg else "json_extract(r.body_canonical,'$.real_io')=1"
    guard(conn, "fp_observed_only_real_success", ATTESTATIONS, "INSERT", f"NEW.level='production_observed' AND NOT EXISTS(SELECT 1 FROM {ATTEMPTS} t JOIN {RESULTS} r ON r.business_id=t.business_id AND r.attempt_uuid=t.evidence_uuid JOIN {ATTESTATIONS} a ON a.business_id=t.business_id AND a.evidence_uuid=t.attestation_uuid WHERE t.business_id=NEW.business_id AND t.evidence_uuid=NEW.source_attempt_uuid AND r.result='SUCCEEDED' AND {real_io} AND {synthetic} AND a.provider=NEW.provider AND a.capability=NEW.capability AND a.environment='production' AND a.configuration_fingerprint=NEW.configuration_fingerprint AND a.credential_fingerprint=NEW.credential_fingerprint)")


def _domain_guards(conn, body):
    # Cada nuevo intento exige obligación committed, grant vigente y attestation exacta.
    sql = f"""NOT EXISTS(SELECT 1 FROM {OUTBOX_BINDINGS} b
        JOIN financial_operations o ON o.business_id=b.business_id AND o.operation_uuid=b.operation_uuid
        JOIN financial_activation_control c ON c.business_id=b.business_id
        JOIN {ATTESTATIONS} a ON a.business_id=b.business_id AND a.evidence_uuid=NEW.attestation_uuid
        WHERE b.business_id=NEW.business_id AND b.evidence_uuid=NEW.binding_uuid
        AND b.operation_uuid=NEW.operation_uuid AND b.activation_generation=NEW.activation_generation
        AND b.capability=NEW.capability AND b.provider=NEW.provider AND b.request_fingerprint=NEW.request_fingerprint
        AND (o.state='committed' OR b.provider<>'AEAT_VERIFACTU') AND o.activation_generation=b.activation_generation
        AND c.ever_enabled=TRUE AND c.activation_generation=b.activation_generation
        AND (c.state='enabled' OR (c.state='paused' AND b.provider='AEAT_VERIFACTU'))
        AND a.provider=b.provider AND a.capability=b.capability AND a.result='PASS'
        AND a.content_hash={body('attestation_hash')}
        AND a.environment='production' AND a.level IN ('production_config_verified','production_observed')
        AND a.expires_at>NEW.created_at)"""
    guard(conn, "fp_claim_proof", ATTEMPTS, "INSERT", sql)
    guard(conn, "fp_start_proof", STARTS, "INSERT", f"NOT EXISTS(SELECT 1 FROM {ATTEMPTS} a WHERE a.business_id=NEW.business_id AND a.evidence_uuid=NEW.attempt_uuid) OR EXISTS(SELECT 1 FROM {RESULTS} r WHERE r.business_id=NEW.business_id AND r.attempt_uuid=NEW.attempt_uuid)")
    guard(conn, 'fp_start_current_generation', STARTS, 'INSERT', f"NOT EXISTS(SELECT 1 FROM {ATTEMPTS} a JOIN financial_activation_control c ON c.business_id=a.business_id JOIN {ATTESTATIONS} p ON p.business_id=a.business_id AND p.evidence_uuid=a.attestation_uuid WHERE a.business_id=NEW.business_id AND a.evidence_uuid=NEW.attempt_uuid AND c.activation_generation=a.activation_generation AND (c.state='enabled' OR (c.state='paused' AND a.provider='AEAT_VERIFACTU')) AND p.result='PASS' AND p.expires_at>NEW.created_at) OR EXISTS(SELECT 1 FROM financial_history_control h WHERE h.business_id=NEW.business_id AND h.fence_enabled=TRUE)")
    guard(conn, "fp_result_started", RESULTS, "INSERT", f"NEW.result<>'ABORTED_BEFORE_IO' AND NOT EXISTS(SELECT 1 FROM {STARTS} s WHERE s.business_id=NEW.business_id AND s.attempt_uuid=NEW.attempt_uuid)")
    for table in OUTBOXES:
        guard(conn, "fp_binding_exists_" + table, OUTBOX_BINDINGS, "INSERT", f"NEW.outbox_type='{table}' AND NOT EXISTS(SELECT 1 FROM {table} q WHERE q.business_id=NEW.business_id AND q.id=NEW.outbox_id)")
    for table, coverage, records, join in (
        ('verifactu_outbox', 'invoice_economic_coverage', 'invoice_records', 'c.invoice_id=q.invoice_id'),
        ('verifactu_cancellation_outbox', 'invoice_fiscal_cancellation_coverage', 'invoice_cancellation_records', 'c.cancellation_record_id=q.record_id')):
        guard(conn, 'fp_binding_coverage_' + table, OUTBOX_BINDINGS, 'INSERT', f"NEW.outbox_type='{table}' AND NOT EXISTS(SELECT 1 FROM {table} q JOIN {coverage} c ON c.business_id=q.business_id AND {join} JOIN {records} r ON r.business_id=q.business_id AND r.id=q.record_id AND r.invoice_id=q.invoice_id WHERE q.business_id=NEW.business_id AND q.id=NEW.outbox_id AND c.operation_uuid=NEW.operation_uuid)")
    guard(conn, "fp_binding_operation", OUTBOX_BINDINGS, "INSERT", "NOT EXISTS(SELECT 1 FROM financial_operations o JOIN financial_activation_control c ON c.business_id=o.business_id WHERE o.business_id=NEW.business_id AND o.operation_uuid=NEW.operation_uuid AND (o.state='committed' OR NEW.provider<>'AEAT_VERIFACTU') AND o.entry_namespace<>'historical' AND o.activation_generation=NEW.activation_generation AND c.ever_enabled=TRUE AND c.state='enabled' AND c.activation_generation=NEW.activation_generation)")
    guard(conn, "fp_activation_binding", BINDINGS, "INSERT", f"NOT EXISTS(SELECT 1 FROM {RUNS} f JOIN financial_activation_requests r ON r.business_id=f.business_id AND r.evaluation_uuid=f.evaluation_uuid WHERE f.business_id=NEW.business_id AND f.evidence_uuid=NEW.preflight_uuid AND f.content_hash=NEW.preflight_hash AND f.result='PASS' AND f.expires_at>NEW.created_at AND r.request_uuid=NEW.request_uuid AND r.actor_user_id=NEW.created_by AND r.actor_session_version=NEW.session_version AND r.action IN ('enable','resume'))")
    expiry = "f.expires_at::timestamptz>NEW.updated_at" if conn.dialect == "postgres" else "f.expires_at>NEW.updated_at"
    guard(conn, "fp_control_preflight", "financial_activation_control", "UPDATE", f"NEW.state IN ('validating','ready','enabled') AND NOT EXISTS(SELECT 1 FROM financial_activation_transitions t JOIN {BINDINGS} b ON b.business_id=t.business_id AND b.request_uuid=t.request_uuid JOIN {RUNS} f ON f.business_id=b.business_id AND f.evidence_uuid=b.preflight_uuid WHERE t.business_id=NEW.business_id AND t.receipt_uuid=NEW.current_transition_uuid AND f.result='PASS' AND f.content_hash=b.preflight_hash AND {expiry})")


def downgrade(conn):
    if any(conn.execute_exact("SELECT 1 FROM " + table + " LIMIT 1").fetchone() for table in TABLES):
        raise ValueError("M79 contiene evidencia F; downgrade bloqueado, conservar prueba.")
    _drop(conn, "fp_control_preflight", "financial_activation_control")
    if conn.dialect == 'postgres':
        conn.execute_exact(f'ALTER TABLE {ATTESTATIONS} DROP CONSTRAINT fp_observed_attempt_fk')
    for table in reversed(TABLES):
        # PostgreSQL DROP TABLE retira triggers, pero también sus funciones propias.
        if conn.dialect == "postgres":
            names = conn.execute_exact("SELECT t.tgname FROM pg_trigger t WHERE t.tgrelid=?::regclass AND NOT t.tgisinternal AND t.tgname LIKE ?", (table, 'fp_%')).fetchall()
        else:
            names = conn.execute_exact("SELECT name AS tgname FROM sqlite_master WHERE type='trigger' AND tbl_name=? AND name LIKE 'fp_%'", (table,)).fetchall()
        for row in names:
            _drop(conn, row["tgname"], table)
        conn.execute_exact("DROP TABLE " + table)
    if conn.dialect == "postgres":
        conn.execute_exact("DROP FUNCTION noesis_provider_context()")
