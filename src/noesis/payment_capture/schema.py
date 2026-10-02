"""Coberturas específicas de 1.6, reservas transitorias y vínculo bancario."""

TABLES = ('bank_match_coverage', 'bank_import_coverage', 'payment_economic_coverage', 'bank_payment_links')
INDICES = ('idx_cash_invoice_event', 'idx_cash_payment_event', 'idx_cash_bank_event')


def _trigger(conn, name, table, event, condition):
    if conn.dialect == 'postgres':
        conn.execute(f"CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF {condition} THEN RAISE EXCEPTION 'Cobertura de cobro/banco incoherente' USING ERRCODE = '23514'; END IF; RETURN NEW; END $$")
        conn.execute(f'CREATE TRIGGER {name} {event} ON {table} FOR EACH ROW EXECUTE FUNCTION {name}()')
    else:
        conn.execute(f"CREATE TRIGGER {name} {event} ON {table} WHEN {condition} BEGIN SELECT RAISE(ABORT,'Cobertura de cobro/banco incoherente'); END")


def _definitions(conn):
    pg = conn.dialect == 'postgres'
    def val(column, path, prefix='NEW'):
        return f"({prefix}.{column}::jsonb->>'{path}')" if pg else f"json_extract({prefix}.{column},'$.{path}')"
    cast = '::text' if pg else ''
    target = val('request_canonical', 'target_id', 'o')
    amount = val('request_canonical', 'amount', 'o')
    truth = "'true'" if pg else '1'
    legacy_amount = f"{amount}{'::double precision' if pg else ''}"
    if not pg:
        legacy_amount = "CAST(" + val('request_canonical', 'amount', 'o') + " AS REAL)"
    result = lambda key: val('result_canonical', key)
    eq = lambda a, b: f'{a} IS NOT DISTINCT FROM {b}' if pg else f'{a} IS {b}'
    def op(command, more=''):
        return f"EXISTS(SELECT 1 FROM financial_operations o WHERE o.business_id=NEW.business_id AND o.operation_uuid=NEW.operation_uuid AND o.state='approved' AND o.command_type IN ({command}) {more})"
    defs = []
    defs.append(('cash_payment_reserve', 'payment_economic_coverage', 'BEFORE INSERT',
        f"NEW.payment_id IS NOT NULL OR NEW.source_fingerprint IS NOT NULL OR NOT {op(chr(39)+'customer_payment.record'+chr(39)+','+chr(39)+'bank_transaction.match'+chr(39))}"))
    defs.append(('cash_import_reserve', 'bank_import_coverage', 'BEFORE INSERT',
        f"NEW.bank_transaction_id IS NOT NULL OR NEW.source_revision IS NOT NULL OR NEW.source_fingerprint IS NOT NULL OR NOT {op(chr(39)+'bank_transaction.import'+chr(39))} OR EXISTS(SELECT 1 FROM bank_import_coverage c WHERE c.business_id=NEW.business_id AND c.batch_uuid=NEW.batch_uuid AND (c.account_scope<>NEW.account_scope OR c.statement_hash<>NEW.statement_hash))"))
    defs.append(('cash_match_reserve', 'bank_match_coverage', 'BEFORE INSERT',
        f"NEW.payment_id IS NOT NULL OR NEW.source_revision IS NOT NULL OR NOT {op(chr(39)+'bank_transaction.match'+chr(39), f'AND {target}=NEW.bank_transaction_id{cast}')}"))
    immutable = {
        'payment_economic_coverage': ('payment_id', ('business_id','operation_uuid','invoice_id','invoice_event_uuid','event_uuid','event_type','operation_state')),
        'bank_import_coverage': ('bank_transaction_id', ('business_id','operation_uuid','event_uuid','event_type','operation_state','batch_uuid','row_key','account_scope','statement_hash','content_fingerprint')),
        'bank_match_coverage': ('payment_id', ('business_id','bank_transaction_id','operation_uuid','event_uuid','event_type','operation_state','imported_event_uuid','payment_event_uuid')),
    }
    for table, (attach, fields) in immutable.items():
        changed = ' OR '.join(f'NOT ({eq("NEW."+f, "OLD."+f)})' for f in fields)
        extras = ' OR NEW.source_fingerprint IS NULL OR length(NEW.source_fingerprint)<>64' if table != 'bank_match_coverage' else ''
        if table != 'payment_economic_coverage':
            extras += ' OR NEW.source_revision IS NULL OR NEW.source_revision<=0'
        defs.append((table + '_attach', table, 'BEFORE UPDATE', f'OLD.{attach} IS NOT NULL OR NEW.{attach} IS NULL OR {changed}{extras}'))
        defs.append((table + '_retain', table, 'BEFORE DELETE', 'TRUE'))
    defs.append(('cash_link_insert', 'bank_payment_links', 'BEFORE INSERT',
        "NOT EXISTS(SELECT 1 FROM bank_transactions b JOIN invoice_payments p ON p.business_id=b.business_id AND p.id=NEW.payment_id WHERE b.business_id=NEW.business_id AND b.id=NEW.bank_transaction_id AND b.status='confirmed' AND b.suggested_invoice_id=p.invoice_id AND b.amount=p.amount AND b.amount>0)"))
    for action in ('UPDATE', 'DELETE'):
        defs.append(('cash_link_' + action.lower(), 'bank_payment_links', 'BEFORE ' + action, 'TRUE'))
        defs.append(('cash_payment_' + action.lower(), 'invoice_payments', 'BEFORE ' + action,
            'EXISTS(SELECT 1 FROM payment_economic_coverage c WHERE c.business_id=OLD.business_id AND c.payment_id=OLD.id)'))
    fixed = ('amount','currency','booked_on','description','counterparty','reference','import_hash','created_at')
    changed = ' OR '.join(f'NOT ({eq("NEW."+f,"OLD."+f)})' for f in fixed)
    defs.append(('cash_bank_origin', 'bank_transactions', 'BEFORE UPDATE',
        f'({changed}) AND EXISTS(SELECT 1 FROM bank_import_coverage c WHERE c.business_id=OLD.business_id AND c.bank_transaction_id=OLD.id)'))
    confirmed = ('status','suggested_invoice_id','confirmed_at')
    changed = ' OR '.join(f'NOT ({eq("NEW."+f,"OLD."+f)})' for f in fixed + confirmed)
    defs.append(('cash_bank_confirmed', 'bank_transactions', 'BEFORE UPDATE',
        f"OLD.status='confirmed' AND ({changed}) AND EXISTS(SELECT 1 FROM bank_payment_links l WHERE l.business_id=OLD.business_id AND l.bank_transaction_id=OLD.id)"))
    defs.append(('cash_bank_match_required', 'bank_transactions', 'BEFORE UPDATE',
        "NEW.status='confirmed' AND OLD.status<>'confirmed' AND EXISTS(SELECT 1 FROM bank_import_coverage i WHERE i.business_id=NEW.business_id AND i.bank_transaction_id=NEW.id) AND NOT EXISTS(SELECT 1 FROM bank_match_coverage c JOIN financial_operations o ON o.business_id=c.business_id AND o.operation_uuid=c.operation_uuid WHERE c.business_id=NEW.business_id AND c.bank_transaction_id=NEW.id AND o.state='approved' AND o.command_type='bank_transaction.match')"))
    payment_links = "EXISTS(SELECT 1 FROM economic_event_links l WHERE l.business_id=c.business_id AND l.event_uuid=c.event_uuid AND l.relation_type='settles' AND l.target_event_uuid=c.invoice_event_uuid)"
    payment_payload = (f"{val('payload_canonical','invoice_id','e')}=p.invoice_id{cast} AND "
        f"{val('payload_canonical','received_on','e')}=substr(p.paid_at{cast},1,10) AND "
        + eq(val('payload_canonical','method','e'), 'p.method'))
    payment_valid = f"""EXISTS(SELECT 1 FROM payment_economic_coverage c JOIN invoice_payments p ON p.business_id=c.business_id AND p.id=c.payment_id
        JOIN economic_events e ON e.business_id=c.business_id AND e.event_uuid=c.event_uuid
        JOIN financial_operations o ON o.business_id=c.business_id AND o.operation_uuid=c.operation_uuid
        WHERE c.business_id=NEW.business_id AND c.operation_uuid=NEW.operation_uuid AND c.payment_id IS NOT NULL
        AND c.invoice_id=p.invoice_id AND e.invoice_payment_id=c.payment_id AND e.operation_uuid=c.operation_uuid AND p.amount={legacy_amount} AND {payment_payload}
        AND e.event_slot='payment' AND e.payload_version=1 AND e.event_type='customer_payment.received'
        AND e.currency='EUR' AND e.amount={amount}{'::numeric' if pg else ''} AND {payment_links}
        AND {result('payment_id')}=c.payment_id{cast} AND {result('invoice_id')}=c.invoice_id{cast}
        AND {result('event_uuid')}=c.event_uuid{cast} AND {result('content_hash')}=e.content_hash
        AND {result('source_fingerprint')}=c.source_fingerprint AND {result('amount')}={amount})"""
    imported_valid = f"""EXISTS(SELECT 1 FROM bank_import_coverage c JOIN economic_events e ON e.business_id=c.business_id AND e.event_uuid=c.event_uuid
        JOIN bank_transactions b ON b.business_id=c.business_id AND b.id=c.bank_transaction_id
        JOIN financial_operations o ON o.business_id=c.business_id AND o.operation_uuid=c.operation_uuid
        WHERE c.business_id=NEW.business_id AND c.operation_uuid=NEW.operation_uuid AND c.bank_transaction_id IS NOT NULL
        AND e.bank_transaction_id=c.bank_transaction_id AND e.source_revision=c.source_revision AND c.source_revision=1
        AND e.operation_uuid=c.operation_uuid AND e.event_slot='import' AND e.event_type='bank_transaction.imported' AND e.payload_version=1
        AND e.amount={amount}{'::numeric' if pg else ''} AND b.amount={legacy_amount} AND b.currency='EUR' AND e.currency='EUR'
        AND {val('payload_canonical','booked_on','e')}=b.booked_on
        AND {val('payload_canonical','imported_on','e')}=substr(b.created_at{cast},1,10)
        AND {result('bank_transaction_id')}=c.bank_transaction_id{cast} AND {result('event_uuid')}=c.event_uuid{cast}
        AND {result('content_hash')}=e.content_hash AND {result('source_revision')}=c.source_revision{cast} AND {result('amount')}={amount})"""
    match_valid = f"""EXISTS(SELECT 1 FROM bank_match_coverage c JOIN economic_events e ON e.business_id=c.business_id AND e.event_uuid=c.event_uuid
        JOIN bank_payment_links b ON b.business_id=c.business_id AND b.bank_transaction_id=c.bank_transaction_id AND b.payment_id=c.payment_id
        JOIN bank_import_coverage i ON i.business_id=c.business_id AND i.bank_transaction_id=c.bank_transaction_id AND i.event_uuid=c.imported_event_uuid
        JOIN payment_economic_coverage p ON p.business_id=c.business_id AND p.operation_uuid=c.operation_uuid AND p.payment_id=c.payment_id AND p.event_uuid=c.payment_event_uuid
        JOIN economic_events pe ON pe.business_id=p.business_id AND pe.event_uuid=p.event_uuid
        JOIN bank_transactions m ON m.business_id=c.business_id AND m.id=c.bank_transaction_id
        WHERE c.business_id=NEW.business_id AND c.operation_uuid=NEW.operation_uuid AND c.payment_id IS NOT NULL
        AND e.bank_transaction_id=c.bank_transaction_id AND e.source_revision=c.source_revision AND c.source_revision>i.source_revision
        AND e.operation_uuid=c.operation_uuid AND e.event_slot='match' AND e.payload_version=1 AND e.event_type='bank_transaction.matched'
        AND e.amount=pe.amount AND e.currency='EUR' AND m.status='confirmed' AND c.source_revision=m._financial_revision
        AND {val('payload_canonical','invoice_payment_id','e')}=c.payment_id{cast}
        AND {val('payload_canonical','matched_on','e')}=substr(m.confirmed_at{cast},1,10)
        AND EXISTS(SELECT 1 FROM economic_event_links l WHERE l.business_id=c.business_id AND l.event_uuid=c.event_uuid AND l.relation_type='matches' AND l.target_event_uuid=c.payment_event_uuid)
        AND EXISTS(SELECT 1 FROM economic_event_links l WHERE l.business_id=c.business_id AND l.event_uuid=c.event_uuid AND l.relation_type='evidence_for' AND l.target_event_uuid=c.imported_event_uuid)
        AND {result('bank_transaction_id')}=c.bank_transaction_id{cast} AND {result('match_event_uuid')}=c.event_uuid{cast}
        AND {result('match_content_hash')}=e.content_hash AND {result('imported_event_uuid')}=c.imported_event_uuid{cast}
        AND {result('source_revision')}=c.source_revision{cast})"""
    count = '(SELECT COUNT(*) FROM economic_events e WHERE e.business_id=NEW.business_id AND e.operation_uuid=NEW.operation_uuid)'
    result_valid = f"{result('captured')}={truth} AND {result('currency')}='EUR'"
    for command, valid, n in (('customer_payment.record', payment_valid, 1), ('bank_transaction.import', imported_valid, 1), ('bank_transaction.match', f'{payment_valid} AND {match_valid}', 2)):
        suffix = command.replace('.', '_')
        defs.append(('cash_result_' + suffix, 'financial_operations', 'BEFORE UPDATE',
            f"NEW.state='committed' AND NEW.command_type='{command}' AND NOT COALESCE(({valid}) AND ({result_valid}) AND {count}={n},FALSE)"))
    return defs


def upgrade(conn):
    pg = conn.dialect == 'postgres'
    ref, uid = ('BIGINT','UUID') if pg else ('INTEGER','TEXT')
    conn.execute('CREATE UNIQUE INDEX idx_cash_invoice_event ON invoice_economic_coverage(business_id,invoice_id,event_uuid)')
    conn.execute('CREATE UNIQUE INDEX idx_cash_payment_event ON economic_events(business_id,event_uuid,invoice_payment_id,event_type,operation_uuid)')
    conn.execute('CREATE UNIQUE INDEX idx_cash_bank_event ON economic_events(business_id,event_uuid,bank_transaction_id,source_revision,event_type,operation_uuid)')
    committed = "FOREIGN KEY(business_id,operation_uuid,operation_state) REFERENCES financial_operations(business_id,operation_uuid,state) DEFERRABLE INITIALLY DEFERRED"
    state_column = "operation_state TEXT NOT NULL DEFAULT 'committed' CHECK(operation_state='committed'),"
    conn.execute(f"""CREATE TABLE bank_payment_links (
        business_id {ref} NOT NULL, bank_transaction_id {ref} NOT NULL, payment_id {ref} NOT NULL,
        PRIMARY KEY(business_id,bank_transaction_id), UNIQUE(business_id,payment_id), UNIQUE(business_id,bank_transaction_id,payment_id),
        FOREIGN KEY(business_id,bank_transaction_id) REFERENCES bank_transactions(business_id,id),
        FOREIGN KEY(business_id,payment_id) REFERENCES invoice_payments(business_id,id))""")
    conn.execute(f"""CREATE TABLE payment_economic_coverage (
        business_id {ref} NOT NULL, operation_uuid {uid} NOT NULL UNIQUE, invoice_id {ref} NOT NULL,
        invoice_event_uuid {uid} NOT NULL, payment_id {ref}, source_fingerprint TEXT,
        event_uuid {uid} NOT NULL UNIQUE, event_type TEXT NOT NULL DEFAULT 'customer_payment.received' CHECK(event_type='customer_payment.received'),
        {state_column}
        PRIMARY KEY(business_id,operation_uuid), UNIQUE(business_id,payment_id), UNIQUE(business_id,payment_id,event_uuid,operation_uuid),
        FOREIGN KEY(business_id,invoice_id,invoice_event_uuid) REFERENCES invoice_economic_coverage(business_id,invoice_id,event_uuid),
        FOREIGN KEY(business_id,payment_id) REFERENCES invoice_payments(business_id,id),
        FOREIGN KEY(business_id,event_uuid,payment_id,event_type,operation_uuid) REFERENCES economic_events(business_id,event_uuid,invoice_payment_id,event_type,operation_uuid) DEFERRABLE INITIALLY DEFERRED,
        {committed})""")
    conn.execute(f"""CREATE TABLE bank_import_coverage (
        business_id {ref} NOT NULL, operation_uuid {uid} NOT NULL UNIQUE, bank_transaction_id {ref}, source_revision {ref}, source_fingerprint TEXT,
        event_uuid {uid} NOT NULL UNIQUE, event_type TEXT NOT NULL DEFAULT 'bank_transaction.imported' CHECK(event_type='bank_transaction.imported'),
        batch_uuid {uid} NOT NULL, row_key TEXT NOT NULL CHECK(length(row_key) BETWEEN 1 AND 128),
        account_scope TEXT NOT NULL CHECK(length(account_scope) BETWEEN 1 AND 128), statement_hash TEXT NOT NULL CHECK(length(statement_hash)=64),
        content_fingerprint TEXT NOT NULL CHECK(length(content_fingerprint)=64),
        {state_column}
        PRIMARY KEY(business_id,operation_uuid), UNIQUE(business_id,bank_transaction_id), UNIQUE(business_id,batch_uuid,row_key), UNIQUE(business_id,bank_transaction_id,event_uuid),
        FOREIGN KEY(business_id,bank_transaction_id) REFERENCES bank_transactions(business_id,id),
        FOREIGN KEY(business_id,event_uuid,bank_transaction_id,source_revision,event_type,operation_uuid) REFERENCES economic_events(business_id,event_uuid,bank_transaction_id,source_revision,event_type,operation_uuid) DEFERRABLE INITIALLY DEFERRED,
        {committed})""")
    conn.execute(f"""CREATE TABLE bank_match_coverage (
        business_id {ref} NOT NULL, bank_transaction_id {ref} NOT NULL, operation_uuid {uid} NOT NULL UNIQUE,
        payment_id {ref}, source_revision {ref}, imported_event_uuid {uid} NOT NULL, payment_event_uuid {uid} NOT NULL,
        event_uuid {uid} NOT NULL UNIQUE, event_type TEXT NOT NULL DEFAULT 'bank_transaction.matched' CHECK(event_type='bank_transaction.matched'),
        {state_column}
        PRIMARY KEY(business_id,bank_transaction_id),
        FOREIGN KEY(business_id,bank_transaction_id,imported_event_uuid) REFERENCES bank_import_coverage(business_id,bank_transaction_id,event_uuid),
        FOREIGN KEY(business_id,bank_transaction_id,payment_id) REFERENCES bank_payment_links(business_id,bank_transaction_id,payment_id),
        FOREIGN KEY(business_id,payment_id,payment_event_uuid,operation_uuid) REFERENCES payment_economic_coverage(business_id,payment_id,event_uuid,operation_uuid),
        FOREIGN KEY(business_id,event_uuid,bank_transaction_id,source_revision,event_type,operation_uuid) REFERENCES economic_events(business_id,event_uuid,bank_transaction_id,source_revision,event_type,operation_uuid) DEFERRABLE INITIALLY DEFERRED,
        {committed})""")
    for args in _definitions(conn):
        _trigger(conn, *args)


def downgrade(conn):
    if any(conn.execute(f'SELECT 1 FROM {table} LIMIT 1').fetchone() for table in TABLES):
        raise ValueError('Conservar coberturas y vínculos durables de cobro/banco; bajada bloqueada.')
    for name, table, _, _ in _definitions(conn):
        conn.execute(f'DROP TRIGGER {name}' + (f' ON {table}' if conn.dialect == 'postgres' else ''))
        if conn.dialect == 'postgres':
            conn.execute(f'DROP FUNCTION {name}()')
    for table in TABLES:
        conn.execute(f'DROP TABLE {table}')
    for index in INDICES:
        conn.execute(f'DROP INDEX {index}')
