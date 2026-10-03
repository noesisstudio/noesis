"""Migración70: diagnóstico no certificable, cuatro tablas sin efectos financieros."""

from .contracts import DecisionKind, IncidenceCode, ReasonCode, RuleId
from .sources import SOURCES

TABLES = ('financial_history_manifests', 'financial_history_items',
          'financial_history_incidences', 'financial_history_decisions')


def literals(values):
    return ','.join("'" + getattr(v, 'value', v) + "'" for v in values)


def guard(conn, name, table, action, condition):
    if conn.dialect == 'postgres':
        conn.execute(f"""CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF {condition} THEN RAISE EXCEPTION 'Evidencia diagnóstica inmutable'
            USING ERRCODE = '23514'; END IF;
            IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END $$""")
        conn.execute(f'CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION {name}()')
    else:
        conn.execute(f"CREATE TRIGGER {name} BEFORE {action} ON {table} WHEN {condition} "
                     "BEGIN SELECT RAISE(ABORT,'Evidencia diagnóstica inmutable'); END")


def upgrade(conn):
    pg = conn.dialect == 'postgres'
    uid, ref, stamp, boolean = ('UUID', 'BIGINT', 'TIMESTAMPTZ', 'BOOLEAN') if pg else ('TEXT', 'INTEGER', 'TEXT', 'INTEGER')
    false = 'FALSE' if pg else '0'
    conn.execute(f"""CREATE TABLE financial_history_manifests (
        business_id {ref} NOT NULL REFERENCES businesses(id), manifest_uuid {uid} NOT NULL,
        mode TEXT NOT NULL DEFAULT 'diagnostic' CHECK(mode='diagnostic'),
        eligible_for_import {boolean} NOT NULL DEFAULT {false} CHECK(eligible_for_import={false}),
        certifiable {boolean} NOT NULL DEFAULT {false} CHECK(certifiable={false}),
        schema_version INTEGER NOT NULL CHECK(schema_version=70), repository_version TEXT NOT NULL CHECK(length(repository_version) BETWEEN 1 AND 128),
        reader_version INTEGER NOT NULL CHECK(reader_version=1), classifier_version INTEGER NOT NULL CHECK(classifier_version=1),
        canonical_version INTEGER NOT NULL CHECK(canonical_version=1), scope_version INTEGER NOT NULL CHECK(scope_version=1),
        scope_canonical TEXT NOT NULL, environment_identity TEXT,
        created_by {ref} NOT NULL, validated_permission TEXT NOT NULL CHECK(validated_permission='historical.record'),
        started_at {stamp} NOT NULL, completed_at {stamp}, frozen_at {stamp},
        status TEXT NOT NULL CHECK(status IN ('scanning','planning','frozen')),
        result TEXT CHECK(result IN ('READY_FOR_REVIEW','BLOCKED')),
        source_set_hash TEXT CHECK(length(source_set_hash)=64), plan_hash TEXT CHECK(length(plan_hash)=64),
        comparison_source_set_hash TEXT CHECK(length(comparison_source_set_hash)=64), summary_canonical TEXT,
        PRIMARY KEY(business_id,manifest_uuid),
        FOREIGN KEY(business_id,created_by) REFERENCES users(business_id,id),
        CHECK((status='frozen' AND result IS NOT NULL AND source_set_hash IS NOT NULL AND plan_hash IS NOT NULL
          AND summary_canonical IS NOT NULL AND completed_at IS NOT NULL AND frozen_at IS NOT NULL)
          OR (status<>'frozen' AND result IS NULL AND frozen_at IS NULL AND completed_at IS NULL)))""")
    conn.execute(f"""CREATE TABLE financial_history_items (
        business_id {ref} NOT NULL, manifest_uuid {uid} NOT NULL, item_uuid {uid} NOT NULL,
        source_type TEXT NOT NULL CHECK(source_type IN ({literals(SOURCES)})), source_id TEXT NOT NULL,
        source_key TEXT NOT NULL, source_sort_key TEXT NOT NULL, revision_canonical TEXT NOT NULL,
        fact_slot TEXT NOT NULL CHECK(length(fact_slot) BETWEEN 1 AND 64),
        proposed_event_type TEXT, raw_canonical TEXT NOT NULL CHECK(length(raw_canonical)<=131072), raw_hash TEXT NOT NULL CHECK(length(raw_hash)=64),
        assessment_canonical TEXT, classification TEXT CHECK(classification IN ('A','B','C','D')),
        disposition TEXT CHECK(disposition IN ('candidate','covered_existing','out_of_scope','excluded','pending_incidence')),
        severity TEXT CHECK(severity IN ('info','warning','blocking')), rule_id TEXT CHECK(rule_id IN ({literals(RuleId)})),
        rule_version INTEGER CHECK(rule_version=1), candidate_canonical TEXT CHECK(length(candidate_canonical)<=131072),
        candidate_hash TEXT CHECK(length(candidate_hash)=64), dependency_canonical TEXT, unresolved_dependency_canonical TEXT,
        existing_coverage_canonical TEXT,
        terminal_result TEXT CHECK(terminal_result IN ('covered_existing','out_of_scope','excluded','blocked','not_durably_supported','planned_diagnostic')),
        PRIMARY KEY(business_id,manifest_uuid,item_uuid),
        UNIQUE(business_id,manifest_uuid,source_type,source_key,fact_slot),
        FOREIGN KEY(business_id,manifest_uuid) REFERENCES financial_history_manifests(business_id,manifest_uuid),
        CHECK((candidate_canonical IS NULL AND candidate_hash IS NULL) OR
              (candidate_canonical IS NOT NULL AND candidate_hash IS NOT NULL AND classification IN ('A','B') AND disposition='candidate')),
        CHECK((terminal_result IS NULL AND assessment_canonical IS NULL AND classification IS NULL AND disposition IS NULL
          AND severity IS NULL AND rule_id IS NULL AND rule_version IS NULL AND dependency_canonical IS NULL)
          OR (terminal_result IS NOT NULL AND assessment_canonical IS NOT NULL AND classification IS NOT NULL AND disposition IS NOT NULL
          AND severity IS NOT NULL AND rule_id IS NOT NULL AND rule_version IS NOT NULL AND dependency_canonical IS NOT NULL
          AND unresolved_dependency_canonical IS NOT NULL)))""")
    conn.execute('CREATE INDEX idx_history_source ON financial_history_items(business_id,manifest_uuid,source_type,source_id,fact_slot)')
    conn.execute('CREATE INDEX idx_history_source_order ON financial_history_items(business_id,manifest_uuid,source_type,source_sort_key)')
    from .repository import field_expr
    for field in ('id','invoice_id','source_id','payment_id','bank_transaction_id','event_uuid','document_id','document_profile_id'):
        conn.execute(f'CREATE INDEX idx_history_ref_{field} ON financial_history_items(business_id,manifest_uuid,source_type,({field_expr(conn.dialect,field)}))')
    conn.execute(f"""CREATE TABLE financial_history_incidences (
        business_id {ref} NOT NULL, manifest_uuid {uid} NOT NULL, item_uuid {uid} NOT NULL, incidence_uuid {uid} NOT NULL,
        code TEXT NOT NULL CHECK(code IN ({literals(IncidenceCode)})), severity TEXT NOT NULL CHECK(severity IN ('info','warning','blocking')),
        evidence_hash TEXT NOT NULL CHECK(length(evidence_hash)=64), rule_version INTEGER NOT NULL CHECK(rule_version=1),
        status TEXT NOT NULL CHECK(status='open'), created_at {stamp} NOT NULL,
        PRIMARY KEY(business_id,manifest_uuid,incidence_uuid), UNIQUE(business_id,manifest_uuid,item_uuid,code),
        UNIQUE(business_id,manifest_uuid,item_uuid,incidence_uuid),
        FOREIGN KEY(business_id,manifest_uuid,item_uuid) REFERENCES financial_history_items(business_id,manifest_uuid,item_uuid))""")
    conn.execute(f"""CREATE TABLE financial_history_decisions (
        business_id {ref} NOT NULL, manifest_uuid {uid} NOT NULL, item_uuid {uid} NOT NULL, incidence_uuid {uid} NOT NULL,
        decision_uuid {uid} NOT NULL, recorded_by {ref} NOT NULL,
        validated_permission TEXT NOT NULL CHECK(validated_permission='historical.record'),
        decision_type TEXT NOT NULL CHECK(decision_type IN ({literals(DecisionKind)})),
        evidence_canonical TEXT NOT NULL, reason_code TEXT NOT NULL CHECK(reason_code IN ({literals(ReasonCode)})),
        interpretation_hash TEXT CHECK(length(interpretation_hash)=64), previous_decision_uuid {uid}, decided_at {stamp} NOT NULL,
        PRIMARY KEY(business_id,manifest_uuid,decision_uuid), UNIQUE(business_id,manifest_uuid,item_uuid,incidence_uuid,decision_uuid),
        FOREIGN KEY(business_id,recorded_by) REFERENCES users(business_id,id),
        FOREIGN KEY(business_id,manifest_uuid,item_uuid,incidence_uuid) REFERENCES financial_history_incidences(business_id,manifest_uuid,item_uuid,incidence_uuid),
        FOREIGN KEY(business_id,manifest_uuid,item_uuid,incidence_uuid,previous_decision_uuid)
          REFERENCES financial_history_decisions(business_id,manifest_uuid,item_uuid,incidence_uuid,decision_uuid),
        CHECK(previous_decision_uuid IS NULL OR previous_decision_uuid<>decision_uuid),
        CHECK((decision_type='select_supported_interpretation' AND interpretation_hash IS NOT NULL)
           OR (decision_type<>'select_supported_interpretation' AND interpretation_hash IS NULL)))""")
    for table in TABLES:
        guard(conn, table + '_retain', table, 'DELETE', 'TRUE')
    equal = 'IS DISTINCT FROM' if pg else 'IS NOT'
    manifest_identity = ('business_id','manifest_uuid','mode','eligible_for_import','certifiable','schema_version','repository_version',
                         'reader_version','classifier_version','canonical_version','scope_version','scope_canonical','environment_identity',
                         'created_by','validated_permission','started_at')
    incomplete = "EXISTS(SELECT 1 FROM financial_history_items i WHERE i.business_id=NEW.business_id AND i.manifest_uuid=NEW.manifest_uuid AND i.terminal_result IS NULL)"
    blocked_items = "EXISTS(SELECT 1 FROM financial_history_items i WHERE i.business_id=NEW.business_id AND i.manifest_uuid=NEW.manifest_uuid AND (i.terminal_result IN ('blocked','not_durably_supported') OR i.severity='blocking'))"
    blocked_incidences = "EXISTS(SELECT 1 FROM financial_history_incidences i WHERE i.business_id=NEW.business_id AND i.manifest_uuid=NEW.manifest_uuid AND i.severity='blocking')"
    guard(conn, TABLES[0] + '_immutable', TABLES[0], 'UPDATE', "OLD.status='frozen' OR "
        + ' OR '.join(f'NEW.{key} {equal} OLD.{key}' for key in manifest_identity)
        + " OR NOT (OLD.status='scanning' AND NEW.status='planning' OR OLD.status='planning' AND NEW.status='frozen')"
        + f" OR (NEW.status='frozen' AND ({incomplete} OR (NEW.result='READY_FOR_REVIEW' AND ({blocked_items} OR {blocked_incidences}))))")
    guard(conn, TABLES[0] + '_insert', TABLES[0], 'INSERT', "NEW.status<>'scanning'")
    item_identity = ('business_id','manifest_uuid','item_uuid','source_type','source_id','source_key','source_sort_key','revision_canonical',
                     'fact_slot','proposed_event_type','raw_canonical','raw_hash')
    guard(conn, TABLES[1] + '_immutable', TABLES[1], 'UPDATE', 'OLD.terminal_result IS NOT NULL OR '
        + ' OR '.join(f'NEW.{key} {equal} OLD.{key}' for key in item_identity)
        + " OR NOT EXISTS(SELECT 1 FROM financial_history_manifests m WHERE m.business_id=OLD.business_id "
        "AND m.manifest_uuid=OLD.manifest_uuid AND m.status='planning')")
    for table in TABLES[2:]:
        guard(conn, table + '_immutable', table, 'UPDATE', 'TRUE')
    for table in TABLES[1:3]:
        allowed = "('scanning','planning')" if table == TABLES[1] else "('planning')"
        guard(conn, table + '_insert', table, 'INSERT', "NOT EXISTS(SELECT 1 FROM financial_history_manifests m "
            f"WHERE m.business_id=NEW.business_id AND m.manifest_uuid=NEW.manifest_uuid AND m.status IN {allowed})")
    guard(conn, TABLES[3] + '_insert', TABLES[3], 'INSERT', "NOT EXISTS(SELECT 1 FROM financial_history_manifests m "
        "WHERE m.business_id=NEW.business_id AND m.manifest_uuid=NEW.manifest_uuid AND m.status='frozen')")


def downgrade(conn):
    # No permitir pérdida ni siquiera de una exploración parcial con operador.
    for table in TABLES:
        if conn.execute(f'SELECT 1 FROM {table} LIMIT 1').fetchone():
            raise ValueError('No retirar inventario histórico con evidencia diagnóstica.')
    for table in reversed(TABLES):
        if conn.dialect == 'postgres':
            for suffix in ('retain', 'immutable', 'insert'):
                conn.execute(f'DROP TRIGGER IF EXISTS {table}_{suffix} ON {table}')
                conn.execute(f'DROP FUNCTION IF EXISTS {table}_{suffix}()')
        conn.execute(f'DROP TABLE {table}')
