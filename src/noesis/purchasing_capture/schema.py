"""Cobertura por revisión y conservación exclusivamente de recibidas/gastos."""

DOMAINS = (
    ('received_invoices', 'supplier_invoice_economic_coverage', 'received_invoice_id', 'supplier_invoice',
     ('supplier_id', 'number', 'concept', 'issued_on', 'due_on', 'base', 'vat_rate', 'vat_amount', 'irpf_amount', 'total', 'category')),
    ('expenses', 'expense_economic_coverage', 'expense_id', 'expense',
     ('concept', 'amount', 'vat_rate', '_captured_vat_amount', 'category', 'spent_on', 'project_id')),
)
MONEY = {'base', 'vat_amount', 'irpf_amount', 'total', 'amount', '_captured_vat_amount', 'vat_rate'}
IDS = {'supplier_id', 'project_id'}


def _trigger(conn, name, table, event, condition):
    if conn.dialect == 'postgres':
        conn.execute(f"CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF {condition} THEN RAISE EXCEPTION 'Cobertura de recibida/gasto incoherente' USING ERRCODE = '23514'; END IF; IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END $$")
        conn.execute(f'CREATE TRIGGER {name} {event} ON {table} FOR EACH ROW EXECUTE FUNCTION {name}()')
    else:
        conn.execute(f"CREATE TRIGGER {name} {event} ON {table} WHEN {condition} BEGIN SELECT RAISE(ABORT,'Cobertura de recibida/gasto incoherente'); END")


def _definitions(conn):
    pg = conn.dialect == 'postgres'
    cast = '::text' if pg else ''
    eq = lambda a, b: f'{a} IS NOT DISTINCT FROM {b}' if pg else f'{a} IS {b}'
    def val(column, path, prefix='NEW'):
        if pg:
            return f"({prefix}.{column}::jsonb#>>'{{{path.replace('.', ',')}}}')"
        return f"json_extract({prefix}.{column},'$.{path}')"
    def numeric(expr, kind='numeric'):
        return f'({expr})::{kind}' if pg else f'CAST({expr} AS NUMERIC)'
    def state_match(column, state_prefix, row_prefix, fields):
        clauses = []
        for field in fields + ('voided_at', 'void_reason'):
            a = val(column, field, state_prefix)
            b = f'{row_prefix}.{field}'
            if field in MONEY:
                # Únicamente comparar con columna binaria existente; ningún cálculo financiero SQL.
                a = numeric(a, 'double precision' if field != '_captured_vat_amount' else 'numeric')
            elif field in IDS:
                b += cast
            else:
                b += cast
            if field == 'spent_on':
                b = f'substr({b},1,10)'
            clauses.append(eq(a, b))
        return ' AND '.join(clauses)
    def payload_match(column, state_prefix, event_prefix, fields, path=''):
        mapping = ({'total': 'total', 'issued_on': 'issued_on', 'invoice_number': 'number', 'due_on': 'due_on',
                    'base': 'base', 'vat_amount': 'vat_amount', 'irpf_amount': 'irpf_amount'}
                   if 'supplier_id' in fields else {'total': 'amount', 'spent_on': 'spent_on',
                                                   'description': 'concept', 'vat_amount': '_captured_vat_amount'})
        return ' AND '.join(eq(val('payload_canonical', path + key, event_prefix), val(column, value, state_prefix))
                            for key, value in mapping.items())
    defs = []
    captured_doc = ('EXISTS(SELECT 1 FROM supplier_invoice_economic_coverage c WHERE c.business_id=OLD.business_id '
                    'AND c.source_id=OLD.received_invoice_id) OR EXISTS(SELECT 1 FROM expense_economic_coverage c '
                    'WHERE c.business_id=OLD.business_id AND c.source_id=OLD.expense_id)')
    doc_changed = ' OR '.join(f'NOT ({eq("NEW."+f,"OLD."+f)})' for f in ('business_id', 'id', 'received_invoice_id', 'expense_id'))
    defs.append(('purchasing_document_retain', 'documents', 'BEFORE DELETE', captured_doc))
    defs.append(('purchasing_document_links', 'documents', 'BEFORE UPDATE', f'({captured_doc}) AND ({doc_changed})'))
    captured_class = ('EXISTS(SELECT 1 FROM documents d WHERE d.business_id=OLD.business_id AND d.id=OLD.document_id AND '
        '(EXISTS(SELECT 1 FROM supplier_invoice_economic_coverage c WHERE c.business_id=d.business_id AND c.source_id=d.received_invoice_id) '
        'OR EXISTS(SELECT 1 FROM expense_economic_coverage c WHERE c.business_id=d.business_id AND c.source_id=d.expense_id)))')
    class_changed = ' OR '.join(f'NOT ({eq("NEW."+f,"OLD."+f)})' for f in ('business_id', 'id', 'document_id', 'confirmed_kind', 'confirmed_at'))
    defs.append(('purchasing_class_retain', 'document_classifications', 'BEFORE DELETE', captured_class))
    defs.append(('purchasing_class_freeze', 'document_classifications', 'BEFORE UPDATE', f'({captured_class}) AND ({class_changed})'))
    for table, coverage, fk, domain, fields in DOMAINS:
        commands = ('confirm', 'correct', 'void') if domain == 'supplier_invoice' else ('confirm', 'void')
        base = domain.replace('.', '_')
        prior = (f'(SELECT MAX(p.source_revision) FROM {coverage} p WHERE p.business_id=NEW.business_id '
                 'AND p.source_id=NEW.source_id)')
        # Reserva solo de comando aprobado; no mutación económica sin antes cubierto real.
        confirm = (f"NEW.event_type='{domain}.confirmed' AND NEW.source_revision=1 AND NEW.before_state IS NULL "
                   f'AND NEW.antecedent_uuid IS NULL AND o.expected_revision IS NULL AND {val("request_canonical", "target_id", "o")} IS NULL '
                   f'AND NOT EXISTS(SELECT 1 FROM {coverage} p WHERE p.business_id=NEW.business_id AND p.source_id=NEW.source_id)')
        corrective = (f"NEW.event_type IN ('{domain}.voided'" + (f",'{domain}.corrected'" if domain == 'supplier_invoice' else '') + ')'
            f' AND NEW.source_revision=s._financial_revision+1 AND s.voided_at IS NULL '
            f'AND o.expected_revision=s._financial_revision AND {val("request_canonical", "target_id", "o")}=s.id{cast} '
            f'AND EXISTS(SELECT 1 FROM {coverage} p WHERE p.business_id=NEW.business_id AND p.source_id=NEW.source_id '
            f'AND p.source_revision={prior} AND p.event_uuid=NEW.antecedent_uuid AND p.after_state=NEW.before_state '
            f"AND p.event_type IN ('{domain}.confirmed'" + (f",'{domain}.corrected'" if domain == 'supplier_invoice' else '') + ')'
            f' AND {state_match("after_state", "p", "s", fields)})')
        pairs = ' OR '.join(f"(o.command_type='{domain}.{c}' AND NEW.event_type='{domain}.{'confirmed' if c == 'confirm' else 'corrected' if c == 'correct' else 'voided'}')" for c in commands)
        defs.append((base + '_reserve', coverage, 'BEFORE INSERT',
            f"NEW.after_state IS NOT NULL OR NEW.source_fingerprint IS NOT NULL OR NOT EXISTS(SELECT 1 FROM financial_operations o "
            f'JOIN {table} s ON s.business_id=NEW.business_id AND s.id=NEW.source_id '
            f"WHERE o.business_id=NEW.business_id AND o.operation_uuid=NEW.operation_uuid AND o.state='approved' "
            f'AND ({pairs}) AND (({confirm}) OR ({corrective})))'))
        fixed = ('business_id', 'source_id', 'source_revision', 'operation_uuid', 'event_uuid', 'event_type',
                 'before_state', 'antecedent_uuid', 'operation_state')
        defs.append((base + '_attach', coverage, 'BEFORE UPDATE',
            'OLD.after_state IS NOT NULL OR NEW.after_state IS NULL OR NEW.source_fingerprint IS NULL '
            'OR length(NEW.source_fingerprint)<>64 OR ' + ' OR '.join(f'NOT ({eq("NEW."+f,"OLD."+f)})' for f in fixed)))
        defs.append((base + '_retain', coverage, 'BEFORE DELETE', 'TRUE'))
        captured = f'EXISTS(SELECT 1 FROM {coverage} c WHERE c.business_id=OLD.business_id AND c.source_id=OLD.id)'
        economic = fields + ('business_id', 'id', 'created_at', 'voided_at', 'void_reason')
        changed = ' OR '.join(f'NOT ({eq("NEW."+f,"OLD."+f)})' for f in economic)
        reservation = (f'EXISTS(SELECT 1 FROM {coverage} c JOIN financial_operations o '
            'ON o.business_id=c.business_id AND o.operation_uuid=c.operation_uuid '
            'WHERE c.business_id=OLD.business_id AND c.source_id=OLD.id AND c.source_revision=OLD._financial_revision+1 '
            f"AND c.after_state IS NULL AND o.state='approved' AND o.expected_revision=OLD._financial_revision "
            'AND NEW.business_id=OLD.business_id AND NEW.id=OLD.id AND ' + eq('NEW.created_at', 'OLD.created_at') + ')')
        retired_changed = changed + (' OR NOT (' + eq('NEW.status', 'OLD.status') + ') OR NOT (' + eq('NEW.note', 'OLD.note') + ')' if domain == 'supplier_invoice' else '')
        defs.append((base + '_source_update', table, 'BEFORE UPDATE',
                     f'{captured} AND ((OLD.voided_at IS NOT NULL AND ({retired_changed})) OR (({changed}) AND NOT {reservation}))'))
        defs.append((base + '_source_delete', table, 'BEFORE DELETE', captured))
        defs.append((base + '_source_void_insert', table, 'BEFORE INSERT', 'NEW.voided_at IS NOT NULL OR NEW.void_reason IS NOT NULL'))
        defs.append((base + '_source_void_update', table, 'BEFORE UPDATE',
            f'((NOT ({eq("NEW.voided_at", "OLD.voided_at")})) OR (NOT ({eq("NEW.void_reason", "OLD.void_reason")}))) AND NOT {reservation}'))
        for command in commands:
            event_type = 'confirmed' if command == 'confirm' else 'corrected' if command == 'correct' else 'voided'
            valid_payload = (payload_match('after_state', 'c', 'e', fields) if command == 'confirm' else
                             payload_match('before_state', 'c', 'e', fields, 'before.'))
            if command == 'correct':
                valid_payload += ' AND ' + payload_match('after_state', 'c', 'e', fields, 'after.')
            day = {'confirm': 'confirmed_on', 'correct': 'corrected_on', 'void': 'voided_on'}[command]
            valid_payload += ' AND ' + eq(val('payload_canonical', day, 'e'), val('request_canonical', 'effective_on', 'o'))
            if command != 'confirm':
                valid_payload += ' AND ' + eq(val('payload_canonical', 'reason', 'e'), val('request_canonical', 'reason', 'o'))
                relation = 'voids' if command == 'void' else 'corrects'
                valid_payload += (f" AND EXISTS(SELECT 1 FROM economic_event_links l WHERE l.business_id=c.business_id "
                                  f"AND l.event_uuid=c.event_uuid AND l.target_event_uuid=c.antecedent_uuid AND l.relation_type='{relation}')")
            mark = 's.voided_at IS NOT NULL AND s.void_reason IS NOT NULL' if command == 'void' else 's.voided_at IS NULL AND s.void_reason IS NULL'
            if command == 'void':
                mark += ' AND substr(s.voided_at' + cast + ',1,10)=' + val('payload_canonical', 'voided_on', 'e')
            actual_amount = val('after_state', 'total' if domain == 'supplier_invoice' else 'amount', 'c')
            amount = val('request_canonical', 'amount', 'o')
            valid = (f'EXISTS(SELECT 1 FROM {coverage} c JOIN {table} s ON s.business_id=c.business_id AND s.id=c.source_id '
                'JOIN economic_events e ON e.business_id=c.business_id AND e.event_uuid=c.event_uuid '
                'JOIN financial_operations o ON o.business_id=c.business_id AND o.operation_uuid=c.operation_uuid '
                f'WHERE c.business_id=NEW.business_id AND c.operation_uuid=NEW.operation_uuid AND c.after_state IS NOT NULL '
                f'AND c.source_revision=s._financial_revision AND e.{fk}=c.source_id AND e.source_revision=c.source_revision '
                f"AND e.operation_uuid=c.operation_uuid AND e.event_type='{domain}.{event_type}' AND e.event_slot='purchasing' "
                f"AND e.payload_version=1 AND e.currency='EUR' AND {eq('e.amount', numeric(amount) if pg else amount)} "
                f'AND {eq(actual_amount, amount)} AND {state_match("after_state", "c", "s", fields)} '
                f'AND {valid_payload} AND {mark} AND {val("result_canonical", "source_id")}=c.source_id{cast} '
                f'AND {val("result_canonical", "source_revision")}=c.source_revision{cast} '
                f'AND {val("result_canonical", "event_uuid")}=c.event_uuid{cast} '
                f'AND {val("result_canonical", "content_hash")}=e.content_hash '
                f'AND {val("result_canonical", "event_type")}=e.event_type '
                f'AND {val("result_canonical", "source_fingerprint")}=c.source_fingerprint '
                f'AND {val("result_canonical", "amount")}={amount})')
            extra = (f'{val("result_canonical", "captured")}=' + ("'true'" if pg else '1') +
                     f" AND {val('result_canonical', 'currency')}='EUR' "
                     'AND (SELECT COUNT(*) FROM economic_events e WHERE e.business_id=NEW.business_id AND e.operation_uuid=NEW.operation_uuid)=1')
            defs.append((base + '_result_' + command, 'financial_operations', 'BEFORE UPDATE',
                         f"NEW.state='committed' AND NEW.command_type='{domain}.{command}' AND NOT COALESCE(({valid}) AND ({extra}),FALSE)"))
    return defs


def refresh_revisions(conn):
    from noesis.financial_writers import schema
    if conn.dialect == 'sqlite':
        for table, *_ in DOMAINS:
            conn.execute(f'DROP TRIGGER {table}_revision_bump')
    schema.upgrade(conn)


def upgrade(conn):
    pg = conn.dialect == 'postgres'
    ref, uid = ('BIGINT', 'UUID') if pg else ('INTEGER', 'TEXT')
    # Fecha local explícita como texto ISO: no inventar zona de legacy.
    for table, *_ in DOMAINS:
        conn.execute(f'ALTER TABLE {table} ADD COLUMN voided_at TEXT')
        conn.execute(f'ALTER TABLE {table} ADD COLUMN void_reason TEXT')
    money = 'NUMERIC' if pg else 'TEXT'
    quota_check = ('_captured_vat_amount>=0 AND _captured_vat_amount<=10000000 AND _captured_vat_amount=trunc(_captured_vat_amount,2)'
                   if pg else "typeof(_captured_vat_amount)='text' AND _captured_vat_amount NOT GLOB '*[^0-9.]*' AND length(_captured_vat_amount)-length(replace(_captured_vat_amount,'.',''))=1 AND _captured_vat_amount GLOB '*.[0-9][0-9]' AND CAST(_captured_vat_amount AS NUMERIC) BETWEEN 0 AND 10000000")
    conn.execute(f'ALTER TABLE expenses ADD COLUMN _captured_vat_amount {money} CHECK(_captured_vat_amount IS NULL OR ({quota_check}))')
    for table, coverage, fk, domain, _ in DOMAINS:
        conn.execute(f'CREATE UNIQUE INDEX {coverage}_event ON economic_events(business_id,event_uuid,{fk},source_revision,event_type,operation_uuid)')
        types = f"'{domain}.confirmed','{domain}.voided'" + (f",'{domain}.corrected'" if domain == 'supplier_invoice' else '')
        conn.execute(f'''CREATE TABLE {coverage} (
            business_id {ref} NOT NULL, source_id {ref} NOT NULL, source_revision {ref} NOT NULL CHECK(source_revision>0),
            operation_uuid {uid} NOT NULL UNIQUE, event_uuid {uid} NOT NULL UNIQUE,
            event_type TEXT NOT NULL CHECK(event_type IN ({types})), before_state TEXT, after_state TEXT,
            source_fingerprint TEXT, antecedent_uuid {uid},
            operation_state TEXT NOT NULL DEFAULT 'committed' CHECK(operation_state='committed'),
            PRIMARY KEY(business_id,source_id,source_revision),
            UNIQUE(business_id,source_id,event_uuid),
            FOREIGN KEY(business_id,source_id) REFERENCES {table}(business_id,id),
            FOREIGN KEY(business_id,source_id,antecedent_uuid) REFERENCES {coverage}(business_id,source_id,event_uuid),
            FOREIGN KEY(business_id,event_uuid,source_id,source_revision,event_type,operation_uuid)
                REFERENCES economic_events(business_id,event_uuid,{fk},source_revision,event_type,operation_uuid) DEFERRABLE INITIALLY DEFERRED,
            FOREIGN KEY(business_id,operation_uuid,operation_state)
                REFERENCES financial_operations(business_id,operation_uuid,state) DEFERRABLE INITIALLY DEFERRED)''')
    refresh_revisions(conn)
    for args in _definitions(conn):
        _trigger(conn, *args)


def downgrade(conn):
    for table, coverage, *_ in DOMAINS:
        if conn.execute(f'SELECT 1 FROM {coverage} LIMIT 1').fetchone() or conn.execute(
                f'SELECT 1 FROM {table} WHERE voided_at IS NOT NULL OR void_reason IS NOT NULL LIMIT 1').fetchone():
            raise ValueError('Conservar evidencia de recibidas/gastos; bajada bloqueada.')
    if conn.execute('SELECT 1 FROM expenses WHERE _captured_vat_amount IS NOT NULL LIMIT 1').fetchone():
        raise ValueError('Conservar cuota explícita de gasto; bajada bloqueada.')
    for name, table, _, _ in _definitions(conn):
        conn.execute(f'DROP TRIGGER {name}' + (f' ON {table}' if conn.dialect == 'postgres' else ''))
        if conn.dialect == 'postgres':
            conn.execute(f'DROP FUNCTION {name}()')
    for table, coverage, *_ in DOMAINS:
        conn.execute(f'DROP TABLE {coverage}')
        conn.execute(f'DROP INDEX {coverage}_event')
        if conn.dialect == 'sqlite':
            conn.execute(f'DROP TRIGGER {table}_revision_bump')
        else:
            conn.execute(f'DROP TRIGGER {table}_revision_bump ON {table}')
            conn.execute(f'DROP FUNCTION {table}_revision_bump()')
        conn.execute(f'ALTER TABLE {table} DROP COLUMN voided_at')
        conn.execute(f'ALTER TABLE {table} DROP COLUMN void_reason')
    conn.execute('ALTER TABLE expenses DROP COLUMN _captured_vat_amount')
    from noesis.financial_writers import schema
    schema.upgrade(conn)
