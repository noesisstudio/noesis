"""Migración71: cut/control y certificado separado; migración70 intacta."""

from .cut_scope import guarded_columns
from .schema import guard

TABLES = ('financial_history_epochs', 'financial_history_control', 'financial_history_cut_manifests',
          'financial_history_epoch_audit')


def _source_guards(conn, create=True):
    pg = conn.dialect == 'postgres'
    equal = 'IS DISTINCT FROM' if pg else 'IS NOT'
    for table, fields in guarded_columns().items():
        for action in ('INSERT', 'UPDATE', 'DELETE'):
            name = f'aaa_history_fence_{table}_{action.lower()}'
            if not create:
                conn.execute(f'DROP TRIGGER IF EXISTS {name}' + (f' ON {table}' if pg else ''))
                if pg:
                    conn.execute(f'DROP FUNCTION IF EXISTS {name}()')
                continue
            ref = 'OLD' if action == 'DELETE' else 'NEW'
            scope = 'TRUE'
            if action == 'UPDATE':
                scope = '(' + ' OR '.join(f'NEW.{f} {equal} OLD.{f}' for f in fields) + ')'
            if table == 'document_sequences':
                select = "({r}.kind='invoice' OR substr({r}.kind,1,15)='invoice_series:')"
                scope += ' AND (' + select.format(r=ref) + ((' OR ' + select.format(r='OLD')) if action == 'UPDATE' else '') + ')'
            if table in ('verifactu_outbox', 'verifactu_cancellation_outbox') and action == 'UPDATE':
                # Respuestas/retry de algo ya enviado son transporte; nuevo envío no.
                scope = f'({scope} OR NEW.attempts {equal} OLD.attempts OR NEW.sent_at {equal} OLD.sent_at OR (NEW.status=\'enviado\' AND OLD.status<>\'enviado\'))'
            if table == 'invoice_events' and action == 'INSERT':
                scope += " AND NEW.event_type NOT IN ('aceptacion','rechazo')"
            tenants = [f'{ref}.business_id']
            if action == 'UPDATE':
                tenants += ['OLD.business_id']
            if pg:
                acquire = '\n'.join(f'PERFORM noesis_history_gate({t});' for t in tenants)
                exists = ' OR '.join(f'EXISTS(SELECT 1 FROM financial_history_control WHERE business_id={t} AND fence_enabled)' for t in tenants)
                conn.execute(f"""CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN IF {scope} THEN {acquire}
                    IF {exists} THEN RAISE EXCEPTION 'NOESIS_HISTORY_FENCE_ACTIVE' USING ERRCODE = '23514'; END IF;
                    END IF; IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END $$""")
                conn.execute(f'CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION {name}()')
            else:
                exists = ' OR '.join(f'EXISTS(SELECT 1 FROM financial_history_control WHERE business_id={t} AND fence_enabled=1)' for t in tenants)
                conn.execute(f"CREATE TRIGGER {name} BEFORE {action} ON {table} WHEN ({scope}) AND ({exists}) BEGIN SELECT RAISE(ABORT,'NOESIS_HISTORY_FENCE_ACTIVE'); END")
    name = 'history_fence_business_delete'
    if create:
        guard(conn, name, 'businesses', 'DELETE', 'EXISTS(SELECT 1 FROM financial_history_epochs WHERE business_id=OLD.id)')
        guard(conn, 'history_fence_business_identity', 'businesses', 'UPDATE', f'NEW.id {equal} OLD.id AND EXISTS(SELECT 1 FROM financial_history_epochs WHERE business_id=OLD.id)')
    else:
        for name in (name, 'history_fence_business_identity'):
            conn.execute(f'DROP TRIGGER IF EXISTS {name}' + (' ON businesses' if pg else ''))
            if pg:
                conn.execute(f'DROP FUNCTION IF EXISTS {name}()')


def upgrade(conn):
    pg = conn.dialect == 'postgres'
    uid, ref, stamp, boolean = ('UUID','BIGINT','TIMESTAMPTZ','BOOLEAN') if pg else ('TEXT','INTEGER','TEXT','INTEGER')
    true, false = ('TRUE','FALSE') if pg else ('1','0')
    eq = 'IS DISTINCT FROM' if pg else 'IS NOT'
    conn.execute(f"""CREATE TABLE financial_history_epochs (
        business_id {ref} NOT NULL REFERENCES businesses(id), epoch_uuid {uid} NOT NULL,
        generation BIGINT NOT NULL CHECK(generation>0), state TEXT NOT NULL CHECK(state IN ('fenced','invalidated','released')),
        opened_by {ref} NOT NULL, opened_at {stamp} NOT NULL, t0 {stamp} NOT NULL,
        fence_enabled {boolean} NOT NULL, fence_version INTEGER NOT NULL CHECK(fence_version=1),
        source_scope_version INTEGER NOT NULL CHECK(source_scope_version=1), source_scope_canonical TEXT NOT NULL,
        created_from_repository_version TEXT NOT NULL CHECK(length(created_from_repository_version) BETWEEN 1 AND 128),
        environment_identity TEXT NOT NULL CHECK(length(environment_identity) BETWEEN 1 AND 128),
        invalidated_at {stamp}, invalidated_by {ref}, invalidation_reason TEXT,
        released_at {stamp}, released_by {ref}, release_reason TEXT, updated_at {stamp} NOT NULL,
        PRIMARY KEY(business_id,epoch_uuid), UNIQUE(business_id,generation), UNIQUE(business_id,epoch_uuid,generation),
        FOREIGN KEY(business_id,opened_by) REFERENCES users(business_id,id),
        FOREIGN KEY(business_id,invalidated_by) REFERENCES users(business_id,id),
        FOREIGN KEY(business_id,released_by) REFERENCES users(business_id,id),
        CHECK(t0=opened_at), CHECK(updated_at>=t0),
        CHECK((invalidated_at IS NULL AND invalidated_by IS NULL AND invalidation_reason IS NULL)
          OR (invalidated_at>=t0 AND invalidated_by IS NOT NULL AND length(invalidation_reason) BETWEEN 1 AND 256)),
        CHECK((state IN ('fenced','invalidated') AND fence_enabled={true} AND released_at IS NULL AND released_by IS NULL AND release_reason IS NULL)
          OR (state='released' AND fence_enabled={false} AND released_at>=t0 AND released_by IS NOT NULL AND length(release_reason) BETWEEN 1 AND 256)),
        CHECK(state<>'invalidated' OR invalidated_at IS NOT NULL))""")
    conn.execute("CREATE UNIQUE INDEX idx_history_active_epoch ON financial_history_epochs(business_id) WHERE state<>'released'")
    conn.execute(f"""CREATE TABLE financial_history_control (
        business_id {ref} PRIMARY KEY REFERENCES businesses(id), epoch_uuid {uid} NOT NULL,
        generation BIGINT NOT NULL, fence_enabled {boolean} NOT NULL, fence_version INTEGER NOT NULL CHECK(fence_version=1),
        updated_at {stamp} NOT NULL,
        FOREIGN KEY(business_id,epoch_uuid,generation) REFERENCES financial_history_epochs(business_id,epoch_uuid,generation))""")
    conn.execute(f"""CREATE TABLE financial_history_cut_manifests (
        business_id {ref} NOT NULL, manifest_uuid {uid} NOT NULL, epoch_uuid {uid} NOT NULL, generation BIGINT NOT NULL,
        mode TEXT NOT NULL CHECK(mode='certifiable_inventory'), source_scope_version INTEGER NOT NULL CHECK(source_scope_version=1),
        source_scope_canonical TEXT NOT NULL, environment_identity TEXT NOT NULL CHECK(length(environment_identity) BETWEEN 1 AND 128),
        t0 {stamp} NOT NULL, started_at {stamp} NOT NULL, completed_at {stamp},
        status TEXT NOT NULL CHECK(status IN ('scanning','frozen','aborted')), result TEXT CHECK(result IN ('READY_FOR_REVIEW','BLOCKED')),
        certifiable {boolean} NOT NULL DEFAULT {false}, eligible_for_import {boolean} NOT NULL DEFAULT {false} CHECK(eligible_for_import={false}),
        boundary_current {boolean} NOT NULL DEFAULT {true}, source_set_hash TEXT, comparison_source_set_hash TEXT, plan_hash TEXT,
        PRIMARY KEY(business_id,manifest_uuid),
        FOREIGN KEY(business_id,manifest_uuid) REFERENCES financial_history_manifests(business_id,manifest_uuid),
        FOREIGN KEY(business_id,epoch_uuid,generation) REFERENCES financial_history_epochs(business_id,epoch_uuid,generation),
        CHECK(started_at>=t0), CHECK(status<>'scanning' OR (completed_at IS NULL AND certifiable={false} AND result IS NULL)),
        CHECK(status<>'aborted' OR (certifiable={false} AND result='BLOCKED' AND boundary_current={false})),
        CHECK(certifiable={false} OR (status='frozen' AND boundary_current={true} AND length(source_set_hash)=64 AND length(plan_hash)=64
            AND source_set_hash=comparison_source_set_hash AND completed_at IS NOT NULL)))""")
    conn.execute('CREATE INDEX idx_history_cut_epoch ON financial_history_cut_manifests(business_id,epoch_uuid)')
    conn.execute('CREATE INDEX idx_cut_item_terminal ON financial_history_items(business_id,manifest_uuid,terminal_result)')
    conn.execute('CREATE INDEX idx_cut_item_severity ON financial_history_items(business_id,manifest_uuid,severity)')
    conn.execute('CREATE INDEX idx_cut_incidence_code ON financial_history_incidences(business_id,manifest_uuid,code)')
    conn.execute(f"""CREATE TABLE financial_history_epoch_audit (
        business_id {ref} NOT NULL, epoch_uuid {uid} NOT NULL, audit_uuid {uid} NOT NULL,
        action TEXT NOT NULL CHECK(action IN ('opened','invalidated','released','manifest_frozen','scan_aborted')),
        recorded_by {ref} NOT NULL, recorded_at {stamp} NOT NULL, reason TEXT NOT NULL CHECK(length(reason) BETWEEN 1 AND 256),
        PRIMARY KEY(business_id,audit_uuid), FOREIGN KEY(business_id,epoch_uuid) REFERENCES financial_history_epochs(business_id,epoch_uuid),
        FOREIGN KEY(business_id,recorded_by) REFERENCES users(business_id,id))""")
    for table in TABLES:
        guard(conn, table+'_retain', table, 'DELETE', 'TRUE')
    guard(conn, TABLES[3]+'_immutable', TABLES[3], 'UPDATE', 'TRUE')
    identity = ('business_id','epoch_uuid','generation','opened_by','opened_at','t0','fence_version','source_scope_version',
                'source_scope_canonical','created_from_repository_version','environment_identity')
    guard(conn, TABLES[0]+'_immutable', TABLES[0], 'UPDATE',
          ' OR '.join(f'NEW.{f} {eq} OLD.{f}' for f in identity)
          + " OR OLD.state='released' OR NOT ((OLD.state='fenced' AND NEW.state IN ('invalidated','released')) OR (OLD.state='invalidated' AND NEW.state='released'))"
          + f' OR (OLD.invalidated_at IS NOT NULL AND (NEW.invalidated_at {eq} OLD.invalidated_at OR NEW.invalidated_by {eq} OLD.invalidated_by OR NEW.invalidation_reason {eq} OLD.invalidation_reason))')
    guard(conn, TABLES[0]+'_actor', TABLES[0], 'UPDATE',
          "NOT EXISTS(SELECT 1 FROM users u WHERE u.business_id=OLD.business_id AND u.id=OLD.opened_by AND u.is_active=TRUE)"
          + " OR (NEW.state='invalidated' AND NEW.invalidated_by<>OLD.opened_by)"
          + " OR (NEW.state='released' AND NEW.released_by<>OLD.opened_by)")
    # Generación no depende de MAX(id). Control durable y contador por tenant.
    nextgen = '(SELECT generation+1 FROM financial_history_control WHERE business_id=NEW.business_id)'
    guard(conn, TABLES[0]+'_insert', TABLES[0], 'INSERT', "NEW.state<>'fenced' OR NEW.invalidated_at IS NOT NULL OR "
          + f'NEW.generation<>COALESCE({nextgen},1)')
    control_valid = 'EXISTS(SELECT 1 FROM financial_history_epochs e WHERE e.business_id=NEW.business_id AND e.epoch_uuid=NEW.epoch_uuid AND e.generation=NEW.generation AND e.fence_enabled=NEW.fence_enabled)'
    guard(conn, TABLES[1]+'_insert', TABLES[1], 'INSERT', f'NOT ({control_valid})')
    guard(conn, TABLES[1]+'_immutable', TABLES[1], 'UPDATE', f'NEW.business_id {eq} OLD.business_id OR NOT ({control_valid})'
          + " OR NOT ((NEW.epoch_uuid=OLD.epoch_uuid AND NEW.generation=OLD.generation AND OLD.fence_enabled="+true+' AND NEW.fence_enabled='+false+')'
          + ' OR (OLD.fence_enabled='+false+' AND NEW.fence_enabled='+true+' AND NEW.generation=OLD.generation+1))')
    valid_epoch = 'EXISTS(SELECT 1 FROM financial_history_epochs e JOIN financial_history_control c ON c.business_id=e.business_id AND c.epoch_uuid=e.epoch_uuid AND c.generation=e.generation '
    valid_epoch += f"WHERE e.business_id=NEW.business_id AND e.epoch_uuid=NEW.epoch_uuid AND e.generation=NEW.generation AND e.state='fenced' AND e.fence_enabled={true} AND c.fence_enabled={true} AND e.t0=NEW.t0 AND e.source_scope_canonical=NEW.source_scope_canonical AND e.environment_identity=NEW.environment_identity)"
    fresh_base = "EXISTS(SELECT 1 FROM financial_history_manifests m WHERE m.business_id=NEW.business_id AND m.manifest_uuid=NEW.manifest_uuid AND m.status='scanning' AND m.started_at=NEW.started_at) AND NOT EXISTS(SELECT 1 FROM financial_history_items i WHERE i.business_id=NEW.business_id AND i.manifest_uuid=NEW.manifest_uuid)"
    guard(conn, TABLES[2]+'_insert', TABLES[2], 'INSERT', f"NEW.status<>'scanning' OR NEW.certifiable={true} OR NEW.boundary_current={false} OR NOT ({valid_epoch}) OR NOT ({fresh_base})")
    cut_identity = ('business_id','manifest_uuid','epoch_uuid','generation','mode','source_scope_version','source_scope_canonical',
                    'environment_identity','t0','started_at','eligible_for_import')
    valid_base = "EXISTS(SELECT 1 FROM financial_history_manifests m WHERE m.business_id=NEW.business_id AND m.manifest_uuid=NEW.manifest_uuid AND m.status='frozen' AND m.source_set_hash=NEW.source_set_hash AND m.comparison_source_set_hash=NEW.comparison_source_set_hash AND m.plan_hash=NEW.plan_hash AND m.result=NEW.result)"
    no_drift = "NOT EXISTS(SELECT 1 FROM financial_history_incidences WHERE business_id=NEW.business_id AND manifest_uuid=NEW.manifest_uuid AND code='SOURCE_DRIFT')"
    revoked = "EXISTS(SELECT 1 FROM financial_history_epochs WHERE business_id=NEW.business_id AND epoch_uuid=NEW.epoch_uuid AND state<>'fenced')"
    condition = ' OR '.join(f'NEW.{f} {eq} OLD.{f}' for f in cut_identity)
    condition += f" OR NOT ((OLD.status='scanning' AND NEW.status='frozen' AND ({valid_epoch}) AND ({valid_base}) AND (NEW.certifiable={false} OR ({no_drift})))"
    condition += f" OR (OLD.status='scanning' AND NEW.status='aborted' AND ({revoked}))"
    condition += f" OR (OLD.status='frozen' AND NEW.status='frozen' AND ({revoked}) AND NEW.certifiable={false} AND NEW.boundary_current={false}"
    condition += ' AND ' + ' AND '.join(f'NOT (NEW.{f} {eq} OLD.{f})' for f in ('source_set_hash','comparison_source_set_hash','plan_hash','completed_at','result')) + '))'
    guard(conn, TABLES[2]+'_immutable', TABLES[2], 'UPDATE', condition)
    # Revocación durable también si un administrador escribe estado por SQL:
    # no puede conservar certifiable/boundary_current ni descoordinar el control.
    statements = f"""
        UPDATE financial_history_cut_manifests SET certifiable={false},boundary_current={false}
          WHERE business_id=NEW.business_id AND epoch_uuid=NEW.epoch_uuid AND status='frozen' AND boundary_current={true};
        UPDATE financial_history_cut_manifests SET status='aborted',result='BLOCKED',boundary_current={false},completed_at=NEW.updated_at
          WHERE business_id=NEW.business_id AND epoch_uuid=NEW.epoch_uuid AND status='scanning';
        UPDATE financial_history_control SET fence_enabled={false},updated_at=NEW.updated_at
          WHERE business_id=NEW.business_id AND epoch_uuid=NEW.epoch_uuid AND NEW.state='released';
    """
    if pg:
        conn.execute(f"CREATE FUNCTION history_epoch_revoke() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN {statements} RETURN NEW; END $$")
        conn.execute("CREATE TRIGGER history_epoch_revoke AFTER UPDATE ON financial_history_epochs FOR EACH ROW WHEN (NEW.state<>OLD.state) EXECUTE FUNCTION history_epoch_revoke()")
    else:
        conn.execute(f"CREATE TRIGGER history_epoch_revoke AFTER UPDATE ON financial_history_epochs WHEN NEW.state<>OLD.state BEGIN {statements} END")
    if pg:
        # Misma clave SHA256 que core.locks.lock_key, sin extensión pgcrypto.
        conn.execute("""CREATE FUNCTION noesis_history_gate(bid bigint) RETURNS void LANGUAGE plpgsql AS $$
            DECLARE k bigint; BEGIN
            IF current_setting('transaction_isolation')<>'read committed' THEN
              RAISE EXCEPTION 'NOESIS_HISTORY_WRITER_BUSY' USING ERRCODE = '23514'; END IF;
            k := ('x'||substr(encode(sha256(convert_to('financial-writer','UTF8')||decode('00','hex')||convert_to(bid::text,'UTF8')),'hex'),1,16))::bit(64)::bigint;
            IF NOT pg_try_advisory_xact_lock(k) THEN RAISE EXCEPTION 'NOESIS_HISTORY_WRITER_BUSY' USING ERRCODE = '23514'; END IF;
            END $$""")
    _source_guards(conn)


def downgrade(conn):
    for table in TABLES:
        if conn.execute(f'SELECT 1 FROM {table} LIMIT 1').fetchone():
            raise ValueError('No retirar epoch/fence/certificado con evidencia durable.')
    _source_guards(conn, create=False)
    conn.execute('DROP TRIGGER IF EXISTS history_epoch_revoke' + (' ON financial_history_epochs' if conn.dialect == 'postgres' else ''))
    if conn.dialect == 'postgres':
        conn.execute('DROP FUNCTION IF EXISTS history_epoch_revoke()')
        conn.execute('DROP TRIGGER IF EXISTS financial_history_epochs_actor ON financial_history_epochs')
        conn.execute('DROP FUNCTION IF EXISTS financial_history_epochs_actor()')
    for index in ('idx_cut_item_terminal','idx_cut_item_severity','idx_cut_incidence_code'):
        conn.execute(f'DROP INDEX {index}')
    for table in reversed(TABLES):
        if conn.dialect == 'postgres':
            for suffix in ('retain','immutable','insert'):
                conn.execute(f'DROP TRIGGER IF EXISTS {table}_{suffix} ON {table}')
                conn.execute(f'DROP FUNCTION IF EXISTS {table}_{suffix}()')
        conn.execute(f'DROP TABLE {table}')
    if conn.dialect == 'postgres':
        conn.execute('DROP FUNCTION noesis_history_gate(bigint)')
