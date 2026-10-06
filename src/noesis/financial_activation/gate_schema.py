"""Gate SQL común antes de consultar lifecycle D; orden ascendente entre tenants."""

from noesis.financial_history.import_schema import _drop


def tables():
    from .handoff_schema import TABLES, PARENTS
    from .live_schema import surfaces
    return sorted(set(TABLES) | set(PARENTS) | set(surfaces()) | {'financial_operations', 'financial_authorizations', 'financial_history_control', 'financial_history_import_batches', 'financial_history_reconciliations'})


def install(conn):
    if conn.dialect != 'postgres':
        return
    for table in tables():
        from .handoff_schema import TABLES
        for action in ('INSERT', 'UPDATE', 'DELETE'):
            name = 'aa0_activation_gate_' + table + '_' + action.lower()
            if action == 'UPDATE':
                acquire = 'PERFORM noesis_history_gate(LEAST(OLD.business_id,NEW.business_id)); IF OLD.business_id<>NEW.business_id THEN PERFORM noesis_history_gate(GREATEST(OLD.business_id,NEW.business_id)); END IF;'
            else:
                acquire = f"PERFORM noesis_history_gate({'OLD' if action == 'DELETE' else 'NEW'}.business_id);"
            # Antes del primer enable, conservar el orden probado por C: sus
            # propios guards adquieren el gate después de las barreras previas.
            # Adelantarlo en legacy puede crear un ciclo Python/SQL con otro
            # advisory lock. Durante el handoff sigue protegiendo el fence C.
            ref = 'OLD' if action == 'DELETE' else 'NEW'
            tenants = f'business_id={ref}.business_id'
            if action == 'UPDATE':
                tenants += ' OR business_id=OLD.business_id'
            active = 'TRUE' if table in TABLES else f'EXISTS(SELECT 1 FROM financial_activation_control WHERE ({tenants}) AND ever_enabled=TRUE)'
            if table == 'financial_activation_control' and action != 'DELETE':
                active += ' OR NEW.ever_enabled=TRUE'
            conn.execute(f'''CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN IF ({active}) THEN {acquire} END IF;
                IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END $$''')
            conn.execute(f'CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION {name}()')


def uninstall(conn):
    if conn.dialect == 'postgres':
        for table in tables():
            for action in ('insert', 'update', 'delete'):
                _drop(conn, 'aa0_activation_gate_' + table + '_' + action, table)
