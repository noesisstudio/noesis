"""Migration77: control plane, generaciones y frontera histórica/live protegidos."""

import json

from noesis.financial_history.schema import guard
from noesis.financial_history.import_schema import _drop
from . import context_schema
from .contracts import canonical, digest

REQUESTS = "financial_activation_requests"
AUTHORIZATIONS = "financial_activation_authorizations"
TRANSITIONS = "financial_activation_transitions"
REVISIONS = "financial_activation_revisions"
GENERATIONS = "financial_activation_generations"
GRANTS = "financial_activation_grants"
BASELINE = "financial_activation_schema_baseline"
TABLES = (REQUESTS, AUTHORIZATIONS, REVISIONS, TRANSITIONS, GENERATIONS, GRANTS)
PARENTS = ("financial_activation_control", "financial_history_epochs", "financial_history_cut_manifests")


def context_field(conn, name):
    if name not in ("kind", "business_id", "request_uuid", "request_hash", "operation_uuid", "generation", "capability", "stage", "availability", "event_uuid", "event_hash", "event_relations"):
        raise ValueError("Campo de contexto SQL desconocido.")
    return f"(noesis_execution_context()->>'{name}')" if conn.dialect == "postgres" else f"json_extract(noesis_execution_context(),'$.{name}')"


def _metadata(conn, table):
    if conn.dialect == "sqlite":
        return dict(
            ddl=conn.execute_exact("SELECT sql FROM sqlite_master WHERE name=? AND type='table'", (table,)).fetchone()["sql"],
            objects=[dict(r) for r in conn.execute_exact("SELECT name,sql,type FROM sqlite_master WHERE tbl_name=? AND type IN ('trigger','index') AND sql IS NOT NULL ORDER BY name", (table,)).fetchall()],
        )
    return dict(
        checks=[dict(r) for r in conn.execute_exact("SELECT conname AS name,pg_get_constraintdef(oid) AS sql FROM pg_constraint WHERE conrelid=?::regclass AND contype='c' ORDER BY conname", (table,)).fetchall()],
        functions=[dict(r) for r in conn.execute_exact("SELECT DISTINCT p.proname AS name,pg_get_functiondef(p.oid) AS sql FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid WHERE t.tgrelid=?::regclass AND NOT t.tgisinternal ORDER BY p.proname", (table,)).fetchall()],
    )


def _rebuild_sqlite(conn, table, ddl, objects):
    # No rename de parent ni PRAGMA foreign_keys=OFF. Las FKs conservan el nombre.
    if not conn.raw.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    if conn.execute_exact("PRAGMA foreign_keys").fetchone()["foreign_keys"] != 1:
        raise ValueError("Foreign keys activas requeridas.")
    conn.execute("PRAGMA defer_foreign_keys=ON")
    columns = [r["name"] for r in conn.execute_exact("PRAGMA table_info(" + table + ")").fetchall()]
    fields = ",".join(columns)
    conn.execute("CREATE TEMP TABLE activation_rebuild_copy AS SELECT " + fields + " FROM " + table)
    conn.execute("DROP TABLE " + table)
    conn.execute(ddl)
    conn.execute("INSERT INTO " + table + " (" + fields + ") SELECT " + fields + " FROM activation_rebuild_copy")
    conn.execute("DROP TABLE activation_rebuild_copy")
    for obj in objects:
        conn.execute(obj["sql"])


def _new_check(text, table, pg):
    if table == "financial_activation_control":
        if pg:
            if "state" in text and "off" in text and "validating" in text:
                return "CHECK(state IN ('off','validating','ready','enabled','paused'))"
            if "activation_generation" in text:
                return "CHECK(activation_generation>=0)"
            if "ever_enabled" in text:
                return "CHECK(ever_enabled IS NOT NULL)"
        return text.replace("state IN ('off','validating')", "state IN ('off','validating','ready','enabled','paused')").replace("CHECK(activation_generation=0)", "CHECK(activation_generation>=0)").replace("CHECK(ever_enabled=0)", "CHECK(ever_enabled IN (0,1))")
    if table == "financial_history_epochs":
        if pg:
            if "state" in text and "fenced" in text and "released" in text and "fence_enabled" not in text:
                return "CHECK(state IN ('fenced','invalidated','released','handed_off'))"
            if "fence_enabled" in text and "released_at" in text:
                return "CHECK((state IN ('fenced','invalidated') AND fence_enabled=TRUE AND released_at IS NULL AND released_by IS NULL AND release_reason IS NULL) OR (state='released' AND fence_enabled=FALSE AND released_at>=t0 AND released_by IS NOT NULL AND length(release_reason) BETWEEN 1 AND 256) OR (state='handed_off' AND fence_enabled=FALSE AND released_at IS NULL AND released_by IS NULL AND release_reason IS NULL))"
        text = text.replace("state IN ('fenced','invalidated','released')", "state IN ('fenced','invalidated','released','handed_off')")
        return text.replace("AND length(release_reason) BETWEEN 1 AND 256)),", "AND length(release_reason) BETWEEN 1 AND 256) OR (state='handed_off' AND fence_enabled=0 AND released_at IS NULL AND released_by IS NULL AND release_reason IS NULL)),")
    if table == "financial_history_cut_manifests":
        if pg and "certifiable" in text and "boundary_current" in text and "source_set_hash" in text:
            return "CHECK(certifiable=FALSE OR (status='frozen' AND length(source_set_hash)=64 AND length(plan_hash)=64 AND source_set_hash=comparison_source_set_hash AND completed_at IS NOT NULL))"
        return text.replace("status='frozen' AND boundary_current=1 AND length(source_set_hash)", "status='frozen' AND length(source_set_hash)")
    return text


def _parents(conn, originals):
    pg = conn.dialect == "postgres"
    for table in PARENTS:
        metadata = originals[table]
        if pg:
            for c in metadata["checks"]:
                replacement = _new_check(c["sql"], table, True)
                if replacement != c["sql"]:
                    conn.execute(f"ALTER TABLE {table} DROP CONSTRAINT {c['name']}")
                    conn.execute(f"ALTER TABLE {table} ADD CONSTRAINT {c['name']} {replacement}")
        else:
            _rebuild_sqlite(conn, table, _new_check(metadata["ddl"], table, False), metadata["objects"])
    uid = "UUID" if pg else "TEXT"
    conn.execute(f"ALTER TABLE financial_activation_control ADD COLUMN current_transition_uuid {uid}")
    conn.execute(f"ALTER TABLE financial_history_epochs ADD COLUMN handoff_uuid {uid}")
    for table in ("financial_operations", "financial_authorizations"):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN activation_generation BIGINT")
        conn.execute(f"ALTER TABLE {table} ADD COLUMN activation_capability TEXT")


def upgrade(conn):
    pg = conn.dialect == "postgres"
    if not pg and not conn.raw.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    originals = {t: _metadata(conn, t) for t in PARENTS}
    conn.execute(f"CREATE TABLE {BASELINE} (id INTEGER PRIMARY KEY CHECK(id=1), metadata_canonical TEXT NOT NULL, content_hash TEXT NOT NULL CHECK(length(content_hash)=64))")
    conn.execute(f"INSERT INTO {BASELINE} VALUES (1,?,?)", (canonical(originals), digest(originals)))
    for action in ("INSERT", "UPDATE", "DELETE"):
        guard(conn, BASELINE + "_" + action.lower(), BASELINE, action, "TRUE")
    context_schema.install(conn)
    _parents(conn, originals)
    uid, ref, stamp = ("UUID", "BIGINT", "TIMESTAMPTZ") if pg else ("TEXT", "INTEGER", "TEXT")
    conn.execute(f"""CREATE TABLE {REQUESTS} (
      business_id {ref} NOT NULL REFERENCES businesses(id), request_uuid {uid} NOT NULL,
      request_version INTEGER NOT NULL CHECK(request_version=1), action TEXT NOT NULL CHECK(action IN ('enable','abort','pause','resume')),
      expected_state TEXT NOT NULL CHECK(expected_state IN ('off','validating','ready','enabled','paused')),
      expected_control_revision BIGINT NOT NULL CHECK(expected_control_revision>=0),
      proposed_generation BIGINT NOT NULL CHECK(proposed_generation>=0),
      evaluation_uuid {uid} NOT NULL, evaluation_hash TEXT NOT NULL CHECK(length(evaluation_hash)=64),
      profile_canonical TEXT NOT NULL, profile_hash TEXT NOT NULL CHECK(length(profile_hash)=64),
      capabilities_canonical TEXT NOT NULL, grant_hash TEXT NOT NULL CHECK(length(grant_hash)=64),
      actor_user_id {ref} NOT NULL, actor_session_version BIGINT NOT NULL CHECK(actor_session_version>=0),
      permission TEXT NOT NULL CHECK(permission='financial.activation.manage'),
      created_at {stamp} NOT NULL, expires_at {stamp} NOT NULL CHECK(expires_at>created_at),
      request_canonical TEXT NOT NULL, request_hash TEXT NOT NULL CHECK(length(request_hash)=64),
      PRIMARY KEY(business_id,request_uuid), UNIQUE(business_id,request_uuid,request_hash),
      FOREIGN KEY(business_id,actor_user_id) REFERENCES users(business_id,id),
      FOREIGN KEY(business_id,evaluation_uuid) REFERENCES financial_readiness_evaluations(business_id,evaluation_uuid))""")
    conn.execute(f"""CREATE TABLE {AUTHORIZATIONS} (
      business_id {ref} NOT NULL, authorization_uuid {uid} NOT NULL, request_uuid {uid} NOT NULL,
      approved_hash TEXT NOT NULL CHECK(length(approved_hash)=64), actor_user_id {ref} NOT NULL,
      actor_session_version BIGINT NOT NULL CHECK(actor_session_version>=0),
      kind TEXT NOT NULL CHECK(kind='human_confirmation'), permission TEXT NOT NULL CHECK(permission='financial.activation.manage'),
      authorized_at {stamp} NOT NULL, PRIMARY KEY(business_id,authorization_uuid), UNIQUE(business_id,request_uuid),
      FOREIGN KEY(business_id,request_uuid,approved_hash) REFERENCES {REQUESTS}(business_id,request_uuid,request_hash),
      FOREIGN KEY(business_id,actor_user_id) REFERENCES users(business_id,id))""")
    conn.execute(f"""CREATE TABLE {REVISIONS} (
      business_id {ref} NOT NULL, control_revision BIGINT NOT NULL CHECK(control_revision>0),
      state TEXT NOT NULL CHECK(state IN ('off','validating','ready','enabled','paused')),
      activation_generation BIGINT NOT NULL CHECK(activation_generation>=0), receipt_uuid {uid} NOT NULL,
      PRIMARY KEY(business_id,control_revision), UNIQUE(business_id,control_revision,state,activation_generation))""")
    conn.execute(f"""CREATE TABLE {TRANSITIONS} (
      business_id {ref} NOT NULL, receipt_uuid {uid} NOT NULL, request_uuid {uid} NOT NULL,
      authorization_uuid {uid} NOT NULL, stage TEXT NOT NULL CHECK(stage IN ('validating','ready','enabled','paused','off')),
      previous_state TEXT NOT NULL, final_state TEXT NOT NULL CHECK(final_state=stage),
      previous_revision BIGINT NOT NULL CHECK(previous_revision>=0), final_revision BIGINT NOT NULL CHECK(final_revision=previous_revision+1),
      activation_generation BIGINT NOT NULL CHECK(activation_generation>=0),
      recorded_at {stamp} NOT NULL, receipt_canonical TEXT NOT NULL, content_hash TEXT NOT NULL CHECK(length(content_hash)=64),
      PRIMARY KEY(business_id,receipt_uuid), UNIQUE(business_id,request_uuid,stage),
      FOREIGN KEY(business_id,request_uuid) REFERENCES {REQUESTS}(business_id,request_uuid),
      FOREIGN KEY(business_id,authorization_uuid) REFERENCES {AUTHORIZATIONS}(business_id,authorization_uuid),
      FOREIGN KEY(business_id,final_revision,final_state,activation_generation) REFERENCES {REVISIONS}(business_id,control_revision,state,activation_generation) DEFERRABLE INITIALLY DEFERRED)""")
    conn.execute(f"""CREATE TABLE {GENERATIONS} (
      business_id {ref} NOT NULL, activation_generation BIGINT NOT NULL CHECK(activation_generation>0),
      previous_generation BIGINT NOT NULL CHECK(previous_generation=activation_generation-1),
      origin TEXT NOT NULL CHECK(origin IN ('handoff','recovery')), receipt_uuid {uid} NOT NULL,
      request_uuid {uid} NOT NULL, evaluation_uuid {uid} NOT NULL,
      profile_hash TEXT NOT NULL CHECK(length(profile_hash)=64), grant_hash TEXT NOT NULL CHECK(length(grant_hash)=64),
      created_at {stamp} NOT NULL, PRIMARY KEY(business_id,activation_generation), UNIQUE(business_id,receipt_uuid),
      FOREIGN KEY(business_id,receipt_uuid) REFERENCES {TRANSITIONS}(business_id,receipt_uuid) DEFERRABLE INITIALLY DEFERRED,
      FOREIGN KEY(business_id,request_uuid) REFERENCES {REQUESTS}(business_id,request_uuid),
      FOREIGN KEY(business_id,evaluation_uuid) REFERENCES financial_readiness_evaluations(business_id,evaluation_uuid))""")
    conn.execute(f"""CREATE TABLE {GRANTS} (
      business_id {ref} NOT NULL, activation_generation BIGINT NOT NULL, capability TEXT NOT NULL,
      evaluation_uuid {uid} NOT NULL, profile_hash TEXT NOT NULL CHECK(length(profile_hash)=64),
      closure_canonical TEXT NOT NULL, proof_canonical TEXT NOT NULL, proof_hash TEXT NOT NULL CHECK(length(proof_hash)=64),
      grant_hash TEXT NOT NULL CHECK(length(grant_hash)=64), receipt_uuid {uid} NOT NULL,
      PRIMARY KEY(business_id,activation_generation,capability),
      FOREIGN KEY(business_id,activation_generation) REFERENCES {GENERATIONS}(business_id,activation_generation),
      FOREIGN KEY(business_id,evaluation_uuid,capability) REFERENCES financial_readiness_capabilities(business_id,evaluation_uuid,capability),
      FOREIGN KEY(business_id,receipt_uuid) REFERENCES {TRANSITIONS}(business_id,receipt_uuid) DEFERRABLE INITIALLY DEFERRED)""")
    for table in TABLES:
        guard(conn, table + "_retain", table, "DELETE", "TRUE")
        guard(conn, table + "_immutable", table, "UPDATE", "TRUE")
    _control_guards(conn)
    _history_guards(conn, originals)
    from .live_schema import install
    install(conn)
    from .commit_schema import install as install_commit
    install_commit(conn)
    from .gate_schema import install as install_gate
    install_gate(conn)
    if not pg and conn.execute_exact("PRAGMA foreign_key_check").fetchall():
        raise ValueError("Migration77: foreign key check falló.")


def _control_guards(conn):
    pg = conn.dialect == "postgres"
    eq = "IS DISTINCT FROM" if pg else "IS NOT"
    c = lambda field: context_field(conn, field)
    signed = f"{c('kind')}='control' AND {c('business_id')}=CAST(NEW.business_id AS TEXT) AND {c('request_uuid')}=CAST(NEW.request_uuid AS TEXT)"
    # SQLite JSON conserva enteros; comparar business mediante CAST en ambos lados.
    signed = signed.replace(c('business_id') + "=", "CAST(" + c('business_id') + " AS TEXT)=")
    for table in (REQUESTS, AUTHORIZATIONS, TRANSITIONS):
        guard(conn, table + "_insert", table, "INSERT", "NOT COALESCE((" + signed + "),FALSE)")
    for table, column, fingerprint in ((REQUESTS, 'request_canonical', 'request_hash'), (TRANSITIONS, 'receipt_canonical', 'content_hash')):
        hashed = f"encode(sha256(convert_to(NEW.{column},'UTF8')),'hex')" if pg else f'noesis_sha256(NEW.{column})'
        guard(conn, table + '_hash', table, 'INSERT', f'NEW.{fingerprint}<>{hashed}')
    expires = 'r.expires_at>clock_timestamp()' if pg else "julianday(r.expires_at)>julianday('now')"
    actor = "EXISTS(SELECT 1 FROM users u WHERE u.business_id=r.business_id AND u.id=r.actor_user_id AND u.session_version=r.actor_session_version AND u.is_active=TRUE)"
    request = f"EXISTS(SELECT 1 FROM {REQUESTS} r WHERE r.business_id=NEW.business_id AND r.request_uuid=NEW.request_uuid AND r.request_hash={c('request_hash')} AND {actor} AND {expires})"
    guard(conn, AUTHORIZATIONS + '_scope', AUTHORIZATIONS, 'INSERT', f"NOT COALESCE(({c('stage')}='authorize' AND {request} AND EXISTS(SELECT 1 FROM {REQUESTS} r WHERE r.business_id=NEW.business_id AND r.request_uuid=NEW.request_uuid AND r.actor_user_id=NEW.actor_user_id AND r.actor_session_version=NEW.actor_session_version)),FALSE)")
    guard(conn, TRANSITIONS + '_scope', TRANSITIONS, 'INSERT', f"NOT COALESCE(({request} AND {c('stage')}=NEW.stage AND EXISTS(SELECT 1 FROM {AUTHORIZATIONS} a JOIN {REQUESTS} r ON r.business_id=a.business_id AND r.request_uuid=a.request_uuid WHERE a.business_id=NEW.business_id AND a.authorization_uuid=NEW.authorization_uuid AND a.request_uuid=NEW.request_uuid AND a.approved_hash=r.request_hash AND ((r.action IN ('enable','resume') AND NEW.stage IN ('validating','ready','enabled')) OR (r.action='pause' AND NEW.stage='paused') OR (r.action='abort' AND NEW.stage='off')))),FALSE)")
    guard(conn, REQUESTS + '_scope', REQUESTS, 'INSERT', f"NOT COALESCE(({c('stage')}='prepare' AND {c('request_hash')}=NEW.request_hash AND EXISTS(SELECT 1 FROM financial_readiness_evaluations e JOIN users u ON u.business_id=e.business_id AND u.id=NEW.actor_user_id WHERE e.business_id=NEW.business_id AND e.evaluation_uuid=NEW.evaluation_uuid AND e.state='final' AND e.result='fully_eligible' AND e.content_hash=NEW.evaluation_hash AND e.profile_canonical=NEW.profile_canonical AND e.profile_hash=NEW.profile_hash AND u.is_active=TRUE AND u.session_version=NEW.actor_session_version)),FALSE)")
    for table in (GENERATIONS, GRANTS):
        condition = f"{c('kind')}='control' AND CAST({c('business_id')} AS TEXT)=CAST(NEW.business_id AS TEXT) AND CAST({c('generation')} AS BIGINT)=NEW.activation_generation"
        guard(conn, table + "_insert", table, "INSERT", "NOT COALESCE((" + condition + "),FALSE)")
    guard(conn, GENERATIONS + '_scope', GENERATIONS, 'INSERT', f"NOT EXISTS(SELECT 1 FROM {REQUESTS} r JOIN financial_activation_control a ON a.business_id=r.business_id WHERE r.business_id=NEW.business_id AND r.request_uuid=NEW.request_uuid AND r.request_hash={c('request_hash')} AND r.proposed_generation=NEW.activation_generation AND r.evaluation_uuid=NEW.evaluation_uuid AND r.profile_hash=NEW.profile_hash AND r.grant_hash=NEW.grant_hash AND a.state='ready' AND a.activation_generation=NEW.previous_generation AND ((NEW.origin='handoff' AND NEW.activation_generation=1 AND a.ever_enabled=FALSE AND r.action='enable') OR (NEW.origin='recovery' AND NEW.activation_generation>1 AND a.ever_enabled=TRUE AND r.action='resume')))")
    member = "EXISTS(SELECT 1 FROM jsonb_array_elements_text(r.capabilities_canonical::jsonb) item(capability) WHERE item.capability=NEW.capability)" if pg else "EXISTS(SELECT 1 FROM json_each(r.capabilities_canonical) item WHERE item.value=NEW.capability)"
    guard(conn, GRANTS + '_scope', GRANTS, 'INSERT', f"NOT EXISTS(SELECT 1 FROM {GENERATIONS} g JOIN {REQUESTS} r ON r.business_id=g.business_id AND r.request_uuid=g.request_uuid JOIN financial_readiness_capabilities p ON p.business_id=g.business_id AND p.evaluation_uuid=g.evaluation_uuid AND p.capability=NEW.capability WHERE g.business_id=NEW.business_id AND g.activation_generation=NEW.activation_generation AND g.receipt_uuid=NEW.receipt_uuid AND p.result='eligible' AND p.proof_canonical=NEW.proof_canonical AND p.proof_hash=NEW.proof_hash AND r.request_hash={c('request_hash')} AND NEW.evaluation_uuid=g.evaluation_uuid AND NEW.profile_hash=g.profile_hash AND NEW.grant_hash=g.grant_hash AND NEW.closure_canonical=r.capabilities_canonical AND {member})")
    count = "jsonb_array_length(r.capabilities_canonical::jsonb)" if pg else "json_array_length(r.capabilities_canonical)"
    from .live_schema import json_value
    epoch_ref = json_value(conn, 'r.request_canonical', 'history', 'epoch_uuid')
    manifest_ref = json_value(conn, 'r.request_canonical', 'history', 'manifest_uuid')
    history = f"""EXISTS(SELECT 1 FROM financial_history_epochs e
      JOIN financial_history_control hc ON hc.business_id=e.business_id AND hc.epoch_uuid=e.epoch_uuid AND hc.generation=e.generation
      JOIN financial_history_cut_manifests cut ON cut.business_id=e.business_id AND cut.epoch_uuid=e.epoch_uuid AND cut.generation=e.generation
      JOIN {GENERATIONS} firstgen ON firstgen.business_id=e.business_id AND firstgen.activation_generation=1 AND firstgen.origin='handoff' AND firstgen.receipt_uuid=e.handoff_uuid
      WHERE e.business_id=NEW.business_id AND CAST(e.epoch_uuid AS TEXT)={epoch_ref} AND CAST(cut.manifest_uuid AS TEXT)={manifest_ref}
      AND e.state='handed_off' AND e.fence_enabled=FALSE AND hc.fence_enabled=FALSE AND cut.certifiable=TRUE AND cut.boundary_current=FALSE)"""
    granted = f"""EXISTS(SELECT 1 FROM {GENERATIONS} g JOIN {REQUESTS} r ON r.business_id=g.business_id AND r.request_uuid=g.request_uuid
      WHERE g.business_id=NEW.business_id AND g.activation_generation=NEW.activation_generation AND g.receipt_uuid=NEW.current_transition_uuid
      AND r.profile_canonical=NEW.current_profile AND r.evaluation_uuid=NEW.current_evaluation_uuid AND g.grant_hash=r.grant_hash
      AND (SELECT COUNT(*) FROM {GRANTS} x WHERE x.business_id=g.business_id AND x.activation_generation=g.activation_generation)={count}
      AND EXISTS(SELECT 1 FROM {GRANTS} x WHERE x.business_id=g.business_id AND x.activation_generation=g.activation_generation AND substr(x.capability,1,8)<>'channel.' AND substr(x.capability,1,9)<>'provider.') AND {history})"""
    for suffix in ("update",):
        _drop(conn, "financial_activation_control_" + suffix, "financial_activation_control")
    identity = " OR ".join(f"NEW.{f} {eq} OLD.{f}" for f in ("business_id", "created_by", "created_at", "provenance"))
    metadata_only = f"""OLD.ever_enabled=FALSE AND NEW.ever_enabled=FALSE AND OLD.activation_generation=0 AND NEW.activation_generation=0
      AND NEW.state=OLD.state AND NEW.state IN ('off','validating') AND NEW.current_transition_uuid {('IS NOT DISTINCT FROM' if pg else 'IS')} OLD.current_transition_uuid
      AND EXISTS(SELECT 1 FROM financial_readiness_evaluations e WHERE e.business_id=NEW.business_id AND e.evaluation_uuid=NEW.current_evaluation_uuid AND e.state='final' AND e.profile_canonical=NEW.current_profile)"""
    transition = f"""EXISTS(SELECT 1 FROM {TRANSITIONS} t JOIN {AUTHORIZATIONS} a ON a.business_id=t.business_id AND a.authorization_uuid=t.authorization_uuid
      JOIN {REQUESTS} r ON r.business_id=t.business_id AND r.request_uuid=t.request_uuid
      WHERE t.business_id=NEW.business_id AND t.receipt_uuid=NEW.current_transition_uuid AND t.previous_state=OLD.state AND t.final_state=NEW.state
      AND t.previous_revision=OLD.control_revision AND t.final_revision=NEW.control_revision AND t.activation_generation=NEW.activation_generation
      AND a.request_uuid=r.request_uuid AND a.approved_hash=r.request_hash AND a.actor_user_id=r.actor_user_id AND a.actor_session_version=r.actor_session_version
      AND CAST(r.request_uuid AS TEXT)={c('request_uuid')} AND r.request_hash={c('request_hash')}
      AND EXISTS(SELECT 1 FROM users u WHERE u.business_id=NEW.business_id AND u.id=a.actor_user_id AND u.is_active=TRUE AND u.session_version=a.actor_session_version))"""
    lifecycle = """((OLD.state='off' AND NEW.state='validating' AND OLD.ever_enabled=FALSE)
      OR (OLD.state='paused' AND NEW.state='validating' AND OLD.ever_enabled=TRUE)
      OR (OLD.state='validating' AND NEW.state='ready') OR (OLD.state='ready' AND NEW.state='enabled')
      OR (OLD.state='enabled' AND NEW.state='paused') OR (OLD.state IN ('validating','ready') AND NEW.state='off' AND OLD.ever_enabled=FALSE))"""
    context = f"{c('kind')}='control' AND CAST({c('business_id')} AS TEXT)=CAST(NEW.business_id AS TEXT) AND {c('stage')}=NEW.state"
    generation = """((NEW.state='enabled' AND NEW.activation_generation=OLD.activation_generation+1 AND NEW.ever_enabled=TRUE)
       OR (NEW.state<>'enabled' AND NEW.activation_generation=OLD.activation_generation AND NEW.ever_enabled=OLD.ever_enabled))"""
    guard(conn, "financial_activation_control_update", "financial_activation_control", "UPDATE",
          identity + " OR NEW.control_revision<>OLD.control_revision+1 OR (OLD.ever_enabled=TRUE AND NEW.ever_enabled=FALSE) OR NOT ((" + metadata_only + ") OR (COALESCE((" + context + "),FALSE) AND (" + transition + ") AND " + lifecycle + " AND " + generation + f" AND (NEW.state<>'enabled' OR ({granted}))))")
    revision = f"""EXISTS(SELECT 1 FROM financial_activation_control a WHERE a.business_id=NEW.business_id AND a.control_revision=NEW.control_revision
        AND a.state=NEW.state AND a.activation_generation=NEW.activation_generation AND a.current_transition_uuid=NEW.receipt_uuid)
        AND {c('kind')}='control' AND {c('stage')}=NEW.state AND CAST({c('business_id')} AS BIGINT)=NEW.business_id"""
    guard(conn, REVISIONS + "_insert", REVISIONS, "INSERT", "NOT COALESCE((" + revision + "),FALSE)")
    statement = f"INSERT INTO {REVISIONS}(business_id,control_revision,state,activation_generation,receipt_uuid) VALUES (NEW.business_id,NEW.control_revision,NEW.state,NEW.activation_generation,NEW.current_transition_uuid);"
    if pg:
        conn.execute(f"CREATE FUNCTION activation_revision_record() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN {statement} RETURN NEW; END $$")
        conn.execute("CREATE TRIGGER activation_revision_record AFTER UPDATE ON financial_activation_control FOR EACH ROW WHEN (NEW.current_transition_uuid IS DISTINCT FROM OLD.current_transition_uuid) EXECUTE FUNCTION activation_revision_record()")
    else:
        conn.execute(f"CREATE TRIGGER activation_revision_record AFTER UPDATE ON financial_activation_control WHEN NEW.current_transition_uuid IS NOT OLD.current_transition_uuid BEGIN {statement} END")


def _history_guards(conn, originals):
    pg = conn.dialect == "postgres"
    for table, name in (("financial_history_epochs", "financial_history_epochs_immutable"), ("financial_history_cut_manifests", "financial_history_cut_manifests_immutable")):
        source = next(o["sql"] for o in originals[table]["functions" if pg else "objects"] if o["name"] == name)
        _drop(conn, name, table)
        if table == "financial_history_epochs":
            source = source.replace("OLD.state='released'", "OLD.state IN ('released','handed_off')").replace("NEW.state IN ('invalidated','released')", "NEW.state IN ('invalidated','released','handed_off')")
        else:
            # Copiar la semántica previa y permitir SOLO revocación del boundary,
            # conservando certifiable/hashes bajo el recibo explícito handed_off.
            marker = "OLD.status='frozen' AND NEW.status='frozen'"
            source = source.replace(marker, marker + " AND NOT EXISTS(SELECT 1 FROM financial_history_epochs WHERE business_id=NEW.business_id AND epoch_uuid=NEW.epoch_uuid AND state='handed_off')")
            allowed = """OLD.status='frozen' AND NEW.status='frozen' AND NEW.boundary_current=FALSE AND NEW.certifiable=OLD.certifiable
              AND EXISTS(SELECT 1 FROM financial_history_epochs e WHERE e.business_id=NEW.business_id AND e.epoch_uuid=NEW.epoch_uuid AND e.state='handed_off' AND e.handoff_uuid IS NOT NULL)
              AND NEW.source_set_hash=OLD.source_set_hash AND NEW.comparison_source_set_hash=OLD.comparison_source_set_hash AND NEW.plan_hash=OLD.plan_hash AND NEW.completed_at=OLD.completed_at AND NEW.result=OLD.result"""
            # La condición original es identity OR NOT(transiciones permitidas).
            source = source.replace("OR NOT ((", "OR NOT ((" + allowed + ") OR (")
        if pg:
            conn.execute(source)
            conn.execute(f"CREATE TRIGGER {name} BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION {name}()")
        else:
            conn.execute(source)
    _drop(conn, "history_epoch_revoke", "financial_history_epochs")
    statements = """UPDATE financial_history_cut_manifests SET certifiable=CASE WHEN NEW.state='handed_off' THEN certifiable ELSE FALSE END,boundary_current=FALSE
        WHERE business_id=NEW.business_id AND epoch_uuid=NEW.epoch_uuid AND status='frozen' AND boundary_current=TRUE;
      UPDATE financial_history_cut_manifests SET status='aborted',result='BLOCKED',boundary_current=FALSE,completed_at=NEW.updated_at
        WHERE business_id=NEW.business_id AND epoch_uuid=NEW.epoch_uuid AND status='scanning';
      UPDATE financial_history_control SET fence_enabled=FALSE,updated_at=NEW.updated_at
        WHERE business_id=NEW.business_id AND epoch_uuid=NEW.epoch_uuid AND NEW.state IN ('released','handed_off');"""
    if pg:
        conn.execute(f"CREATE FUNCTION history_epoch_revoke() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN {statements} RETURN NEW; END $$")
        conn.execute("CREATE TRIGGER history_epoch_revoke AFTER UPDATE ON financial_history_epochs FOR EACH ROW WHEN (NEW.state<>OLD.state) EXECUTE FUNCTION history_epoch_revoke()")
    else:
        conn.execute(f"CREATE TRIGGER history_epoch_revoke AFTER UPDATE ON financial_history_epochs WHEN NEW.state<>OLD.state BEGIN {statements} END")
    c = lambda field: context_field(conn, field)
    valid = f"""{c('kind')}='control' AND {c('stage')}='enabled' AND
      EXISTS(SELECT 1 FROM {TRANSITIONS} t JOIN {GENERATIONS} g ON g.business_id=t.business_id AND g.receipt_uuid=t.receipt_uuid
      WHERE t.business_id=NEW.business_id AND t.receipt_uuid=NEW.handoff_uuid AND t.stage='enabled' AND g.activation_generation=1 AND g.origin='handoff')"""
    guard(conn, "activation_history_handoff", "financial_history_epochs", "UPDATE", "NEW.state='handed_off' AND NOT COALESCE((" + valid + "),FALSE)")
    ever = "EXISTS(SELECT 1 FROM financial_activation_control WHERE business_id=NEW.business_id AND ever_enabled=TRUE)"
    for table in ("financial_history_epochs", "financial_history_cut_manifests", "financial_history_import_batches", "financial_history_reconciliations"):
        guard(conn, "activation_no_new_" + table, table, "INSERT", ever)


def downgrade(conn):
    from .commit_schema import TABLE as COMMITS, source_tables
    if any(conn.execute_exact('SELECT 1 FROM ' + table + ' LIMIT 1').fetchone() for table in (COMMITS,) + source_tables()):
        raise ValueError('Conservar testigos de efectos live; downgrade77 bloqueado.')
    if any(conn.execute_exact("SELECT 1 FROM " + t + " LIMIT 1").fetchone() for t in TABLES):
        raise ValueError("Conservar evidencia D; downgrade77 bloqueado.")
    if conn.execute_exact("SELECT 1 FROM financial_activation_control WHERE ever_enabled=TRUE OR activation_generation<>0 OR state NOT IN ('off','validating') LIMIT 1").fetchone():
        raise ValueError("No volver a legacy después de activar.")
    for table in ("financial_operations", "financial_authorizations"):
        if conn.execute_exact("SELECT 1 FROM " + table + " WHERE activation_generation IS NOT NULL OR activation_capability IS NOT NULL LIMIT 1").fetchone():
            raise ValueError("Conservar vínculos de generación.")
    row = conn.execute_exact(f"SELECT * FROM {BASELINE} WHERE id=1").fetchone()
    originals = json.loads(row["metadata_canonical"])
    if digest(originals) != row["content_hash"]:
        raise ValueError("Baseline de esquema corrupto; no retirar guards.")
    from .live_schema import uninstall
    from .gate_schema import uninstall as uninstall_gate
    uninstall_gate(conn)
    from .commit_schema import uninstall as uninstall_commit
    uninstall_commit(conn)
    uninstall(conn)
    pg = conn.dialect == "postgres"
    _drop(conn, "activation_revision_record", "financial_activation_control")
    _drop(conn, "activation_history_handoff", "financial_history_epochs")
    for table in ("financial_history_epochs", "financial_history_cut_manifests", "financial_history_import_batches", "financial_history_reconciliations"):
        _drop(conn, "activation_no_new_" + table, table)
    for table in TABLES:
        for suffix in ("retain", "immutable", "insert", "scope", "hash"):
            _drop(conn, table + "_" + suffix, table)
    _drop(conn, "financial_activation_control_update", "financial_activation_control")
    for table in ("financial_operations", "financial_authorizations"):
        conn.execute(f"ALTER TABLE {table} DROP COLUMN activation_capability")
        conn.execute(f"ALTER TABLE {table} DROP COLUMN activation_generation")
    if pg:
        conn.execute("ALTER TABLE financial_activation_control DROP COLUMN current_transition_uuid")
        conn.execute("ALTER TABLE financial_history_epochs DROP COLUMN handoff_uuid")
        for table in PARENTS:
            current = _metadata(conn, table)
            for check in current["checks"]:
                conn.execute(f"ALTER TABLE {table} DROP CONSTRAINT {check['name']}")
            for check in originals[table]["checks"]:
                conn.execute(f"ALTER TABLE {table} ADD CONSTRAINT {check['name']} {check['sql']}")
            for function in originals[table]["functions"]:
                conn.execute(function["sql"])
        for table, name in (("financial_activation_control", "financial_activation_control_update"),):
            conn.execute(f"CREATE TRIGGER {name} BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION {name}()")
    else:
        # El guard del cut referencia epoch.handoff_uuid. Retirarlo dentro de la
        # misma TX de downgrade antes de retirar esa columna; se restaura su
        # definición original junto con la tabla cut, con FKs siempre activas.
        _drop(conn, "financial_history_cut_manifests_immutable", "financial_history_cut_manifests")
        for table in PARENTS:
            # Restaurar columnas originales, sin normalización de sus valores.
            original = originals[table]
            for column in ("current_transition_uuid", "handoff_uuid"):
                columns = {r["name"] for r in conn.execute_exact("PRAGMA table_info(" + table + ")").fetchall()}
                if column in columns:
                    conn.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
            _rebuild_sqlite(conn, table, original["ddl"], original["objects"])
    for table in reversed(TABLES):
        conn.execute("DROP TABLE " + table)
    context_schema.uninstall(conn)
    for action in ("insert", "update", "delete"):
        _drop(conn, BASELINE + "_" + action, BASELINE)
    conn.execute("DROP TABLE " + BASELINE)
