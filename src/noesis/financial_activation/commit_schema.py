"""Testigo SQL de commit para impedir efectos confirmados sin Operation COMMITTED.

PostgreSQL permite COMMIT al cliente dentro de un executor. Una FK diferida
vincula cada escritura final a la transición committed de la misma generación.
SQLite añade la misma prueba estructural además del authorizer de conexión.
"""

from noesis.financial_history.schema import guard
from noesis.financial_history.import_schema import _drop
from .handoff_schema import context_field

TABLE = 'financial_activation_effect_commits'
SOURCE_PROOFS = (
    ('expenses', 'expense_economic_coverage', 'source_id', ('INSERT', 'UPDATE')),
    ('received_invoices', 'supplier_invoice_economic_coverage', 'source_id', ('INSERT', 'UPDATE')),
    ('invoice_payments', 'payment_economic_coverage', 'payment_id', ('INSERT',)),
    ('bank_transactions', 'bank_import_coverage', 'bank_transaction_id', ('INSERT',)),
    ('bank_transactions', 'bank_match_coverage', 'bank_transaction_id', ('UPDATE',)),
)


def source_tables():
    return tuple(_source_table(coverage) for _, coverage, _, _ in SOURCE_PROOFS)


def _source_table(coverage):
    # Todos los identificadores, también los triggers, caben en 63 bytes PG.
    return 'financial_activation_source_' + coverage.removesuffix('_coverage').removesuffix('_economic')


def _install_sources(conn):
    """Cada fila final debe tener su propia cobertura de la operación exacta.

    El testigo committed por sí solo no prueba qué filas produjo la operación.
    La FK diferida permite reservar la cobertura después del INSERT legacy,
    pero impide confirmar filas huérfanas o dos orígenes con una sola autoridad.
    """
    from .live_schema import surfaces, _scope
    pg = conn.dialect == 'postgres'
    uid, ref = ('UUID', 'BIGINT') if pg else ('TEXT', 'INTEGER')
    for source, coverage, key, actions in SOURCE_PROOFS:
        table = _source_table(coverage)
        conn.execute(f'CREATE UNIQUE INDEX {table}_reference ON {coverage}(business_id,{key},operation_uuid)')
        conn.execute(f'''CREATE TABLE {table} (
            business_id {ref} NOT NULL, operation_uuid {uid} NOT NULL,
            activation_generation BIGINT NOT NULL CHECK(activation_generation>0), source_id {ref} NOT NULL,
            PRIMARY KEY(business_id,operation_uuid),
            FOREIGN KEY(business_id,source_id,operation_uuid)
            REFERENCES {coverage}(business_id,{key},operation_uuid) DEFERRABLE INITIALLY DEFERRED)''')
        for action in ('UPDATE', 'DELETE'):
            guard(conn, table + '_' + action.lower(), table, action, 'TRUE')
        c = lambda k: context_field(conn, k)
        guard(conn, table + '_insert', table, 'INSERT', f"""NOT COALESCE((
            {c('kind')}='effect' AND CAST({c('business_id')} AS BIGINT)=NEW.business_id
            AND {c('operation_uuid')}=CAST(NEW.operation_uuid AS TEXT)
            AND CAST({c('generation')} AS BIGINT)=NEW.activation_generation),FALSE)
            OR EXISTS(SELECT 1 FROM {table} p WHERE p.business_id=NEW.business_id
                AND p.operation_uuid=NEW.operation_uuid AND p.source_id<>NEW.source_id)""")
        for action in actions:
            scope = _scope(conn, source, action, surfaces()[source])
            ever = 'EXISTS(SELECT 1 FROM financial_activation_control WHERE business_id=NEW.business_id AND ever_enabled=TRUE)'
            name = table + '_' + action.lower() + '_source'
            op = c('operation_uuid') + ('::uuid' if pg else '')
            statement = f"INSERT INTO {table}(business_id,operation_uuid,activation_generation,source_id) VALUES(NEW.business_id,{op},CAST({c('generation')} AS BIGINT),NEW.id) ON CONFLICT DO NOTHING;"
            if pg:
                conn.execute(f'''CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN IF ({scope}) AND ({ever}) THEN {statement} END IF; RETURN NEW; END $$''')
                conn.execute(f'CREATE TRIGGER {name} AFTER {action} ON {source} FOR EACH ROW EXECUTE FUNCTION {name}()')
            else:
                conn.execute(f'CREATE TRIGGER {name} AFTER {action} ON {source} WHEN ({scope}) AND ({ever}) BEGIN {statement} END')


def install(conn):
    pg = conn.dialect == 'postgres'
    uid, ref = ('UUID', 'BIGINT') if pg else ('TEXT', 'INTEGER')
    conn.execute('CREATE UNIQUE INDEX idx_activation_operation_commit ON financial_operations(business_id,operation_uuid,activation_generation,state)')
    conn.execute(f'''CREATE TABLE {TABLE} (
        business_id {ref} NOT NULL, operation_uuid {uid} NOT NULL, activation_generation BIGINT NOT NULL,
        state TEXT NOT NULL CHECK(state='committed'),
        PRIMARY KEY(business_id,operation_uuid,activation_generation),
        FOREIGN KEY(business_id,operation_uuid,activation_generation,state)
        REFERENCES financial_operations(business_id,operation_uuid,activation_generation,state) DEFERRABLE INITIALLY DEFERRED)''')
    for action in ('UPDATE', 'DELETE'):
        guard(conn, TABLE + '_' + action.lower(), TABLE, action, 'TRUE')
    def field(key):
        return context_field(conn, key)
    guard(conn, TABLE + '_insert', TABLE, 'INSERT', f"NOT COALESCE(({field('kind')}='effect' AND CAST({field('business_id')} AS BIGINT)=NEW.business_id AND {field('operation_uuid')}=CAST(NEW.operation_uuid AS TEXT) AND CAST({field('generation')} AS BIGINT)=NEW.activation_generation),FALSE)")
    from .live_schema import surfaces, _scope
    for table, fields in surfaces().items():
        for action in ('INSERT', 'UPDATE', 'DELETE'):
            ref = 'OLD' if action == 'DELETE' else 'NEW'
            scope = _scope(conn, table, action, fields)
            ever = f'EXISTS(SELECT 1 FROM financial_activation_control WHERE business_id={ref}.business_id AND ever_enabled=TRUE)'
            name = 'activation_commit_' + table + '_' + action.lower()
            op = field('operation_uuid') + ('::uuid' if pg else '')
            statement = f"INSERT INTO {TABLE}(business_id,operation_uuid,activation_generation,state) VALUES ({ref}.business_id,{op},CAST({field('generation')} AS BIGINT),'committed') ON CONFLICT DO NOTHING;"
            if pg:
                conn.execute(f'''CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN IF ({scope}) AND ({ever}) THEN {statement} END IF;
                    IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END $$''')
                conn.execute(f'CREATE TRIGGER {name} AFTER {action} ON {table} FOR EACH ROW EXECUTE FUNCTION {name}()')
            else:
                conn.execute(f'CREATE TRIGGER {name} AFTER {action} ON {table} WHEN ({scope}) AND ({ever}) BEGIN {statement} END')
    _install_sources(conn)


def uninstall(conn):
    from .live_schema import surfaces
    for table in surfaces():
        for action in ('insert', 'update', 'delete'):
            _drop(conn, 'activation_commit_' + table + '_' + action, table)
    for action in ('insert', 'update', 'delete'):
        _drop(conn, TABLE + '_' + action, TABLE)
    conn.execute('DROP TABLE ' + TABLE)
    conn.execute('DROP INDEX idx_activation_operation_commit')
    for source, coverage, _, actions in SOURCE_PROOFS:
        table = _source_table(coverage)
        for action in actions:
            _drop(conn, table + '_' + action.lower() + '_source', source)
        for action in ('insert', 'update', 'delete'):
            _drop(conn, table + '_' + action, table)
        conn.execute('DROP TABLE ' + table)
        conn.execute(f'DROP INDEX {table}_reference')
