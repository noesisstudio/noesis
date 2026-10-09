"""Guards comunes de efectos finales; borradores/documentación siguen permitidos."""

from noesis.financial_history.schema import guard, literals
from noesis.financial_history.import_schema import _drop
from noesis.financial_history.cut_scope import guarded_columns
from noesis.financial_operations.contracts import CommandType
from .capabilities import capability_for_command
from .handoff_schema import context_field, GRANTS


def _mapping(alias="NEW"):
    # C es la única autoridad del mapping; no mantener otra tabla command/capability.
    return f"CASE {alias}.command_type " + " ".join("WHEN '" + command.value + "' THEN '" + capability_for_command(command).value + "'" for command in CommandType) + " ELSE NULL END"


def _ever(ref):
    return f"EXISTS(SELECT 1 FROM financial_activation_control a WHERE a.business_id={ref}.business_id AND a.ever_enabled=TRUE)"


def json_value(conn, expression, *path):
    return f"({expression}::jsonb #>> '{{{','.join(path)}}}')" if conn.dialect == 'postgres' else f"json_extract({expression},'$.{'.'.join(path)}')"


def target_scope(conn, table, action, ref):
    target = json_value(conn, 'o.request_canonical', 'target_id')
    equal = lambda field: f"CAST({target} AS BIGINT)={ref}.{field}"
    invoice = json_value(conn, 'o.request_canonical', 'parameters', 'invoice_id')
    invoice_target = f"CAST(CASE WHEN o.command_type='bank_transaction.match' THEN {invoice} ELSE {target} END AS BIGINT)"
    if action == 'DELETE':
        return 'FALSE'  # Ningún command del catálogo tiene semántica de borrar hechos.
    if table in ('expenses', 'received_invoices'):
        domain = 'expense' if table == 'expenses' else 'supplier_invoice'
        if action == 'INSERT':
            return f"o.command_type='{domain}.confirm' AND {target} IS NULL"
        return f"o.command_type IN ('{domain}.void'" + (",'supplier_invoice.correct'" if domain == 'supplier_invoice' else '') + f") AND {equal('id')} AND o.expected_revision=OLD._financial_revision"
    if table == 'bank_transactions':
        if action == 'INSERT':
            return f"o.command_type='bank_transaction.import' AND {target} IS NULL"
        return f"o.command_type='bank_transaction.match' AND {equal('id')} AND o.expected_revision=OLD._financial_revision"
    if table == 'invoices':
        scope = f'{invoice_target}={ref}.id'
        if action == 'UPDATE':
            equal_fields = [f for f in surfaces()['invoices'] if f not in ('status', 'paid_at')]
            same = ' AND '.join(f'NEW.{f} IS NOT DISTINCT FROM OLD.{f}' if conn.dialect == 'postgres' else f'NEW.{f} IS OLD.{f}' for f in equal_fields)
            scope += f" AND ((o.command_type IN ('invoice.issue','invoice.rectify') AND OLD.status='borrador' AND NEW.status='enviada' AND NEW.paid_at IS NULL) OR (o.command_type IN ('customer_payment.record','bank_transaction.match') AND NEW.status IN ('parcial','cobrada') AND ({same})))"
        return scope
    if table in ('invoice_lines', 'invoice_records', 'invoice_payments', 'invoice_economic_coverage', 'payment_economic_coverage', 'invoice_cancellation_records', 'invoice_fiscal_cancellation_coverage', 'verifactu_outbox', 'verifactu_cancellation_outbox', 'invoice_events'):
        return f'{invoice_target}={ref}.invoice_id'
    if table in ('bank_match_coverage', 'bank_payment_links'):
        return equal('bank_transaction_id')
    if table in ('supplier_invoice_economic_coverage', 'expense_economic_coverage'):
        return f'({target} IS NULL OR ({equal("source_id")}))'
    if table == 'economic_event_links':
        relations = context_field(conn, 'event_relations')
        members = f'jsonb_array_elements(({relations})::jsonb) item(value)' if conn.dialect == 'postgres' else f'json_each({relations}) item'
        kind = json_value(conn, 'item.value', 'kind')
        target_event = json_value(conn, 'item.value', 'target_event_uuid')
        return f"{context_field(conn, 'event_uuid')}=CAST({ref}.event_uuid AS TEXT) AND EXISTS(SELECT 1 FROM {members} WHERE {kind}={ref}.relation_type AND {target_event}=CAST({ref}.target_event_uuid AS TEXT))"
    if table == 'economic_events':
        events = {
            'invoice.issue': ('invoice.issued',), 'invoice.rectify': ('invoice.rectified',),
            'customer_payment.record': ('customer_payment.received',),
            'supplier_invoice.confirm': ('supplier_invoice.confirmed',),
            'supplier_invoice.correct': ('supplier_invoice.corrected',),
            'supplier_invoice.void': ('supplier_invoice.voided',), 'expense.confirm': ('expense.confirmed',),
            'expense.void': ('expense.voided',), 'bank_transaction.import': ('bank_transaction.imported',),
            'bank_transaction.match': ('customer_payment.received', 'bank_transaction.matched'),
            'invoice.fiscal_cancel': ('invoice.fiscal_cancellation_registered',),
        }
        hashed = f"encode(sha256(convert_to({ref}.canonical_event,'UTF8')),'hex')" if conn.dialect == 'postgres' else f'noesis_sha256({ref}.canonical_event)'
        return f"{ref}.origin='live' AND {context_field(conn, 'event_uuid')}=CAST({ref}.event_uuid AS TEXT) AND {context_field(conn, 'event_hash')}={ref}.content_hash AND {hashed}={ref}.content_hash AND (" + ' OR '.join(f"(o.command_type='{cmd}' AND {ref}.event_type IN ({literals(kinds)}))" for cmd, kinds in events.items()) + ')'
    return 'TRUE'  # Contadores y reservas: su op/command/grant ya están ligados.


def _context(conn, ref, commands=None, *, operation_field=None, table=None, action=None):
    c = lambda key: context_field(conn, key)
    allowed = "" if commands is None else f" AND o.command_type IN ({literals(commands)})"
    if operation_field:
        allowed += f" AND CAST(o.operation_uuid AS TEXT)=CAST({ref}.{operation_field} AS TEXT)"
    if table is not None:
        allowed += ' AND (' + target_scope(conn, table, action, ref) + ')'
    expiry = 'm.expires_at>clock_timestamp()' if conn.dialect == 'postgres' else "julianday(m.expires_at)>julianday('now')"
    return f"""COALESCE(({c('kind')}='effect' AND CAST({c('business_id')} AS TEXT)=CAST({ref}.business_id AS TEXT)
      AND CAST({c('availability')} AS TEXT) IN ('true','1') AND EXISTS(
      SELECT 1 FROM financial_operations o JOIN financial_activation_control a ON a.business_id=o.business_id
      JOIN {GRANTS} g ON g.business_id=o.business_id AND g.activation_generation=o.activation_generation AND g.capability=o.activation_capability
      JOIN financial_authorizations au ON au.business_id=o.business_id AND au.authorization_uuid=o.authorization_uuid AND au.operation_uuid=o.operation_uuid
      WHERE o.business_id={ref}.business_id AND CAST(o.operation_uuid AS TEXT)={c('operation_uuid')} AND o.state='approved'
      AND a.state='enabled' AND a.ever_enabled=TRUE AND a.activation_generation=o.activation_generation
      AND CAST({c('generation')} AS BIGINT)=a.activation_generation AND {c('capability')}=g.capability
      AND o.activation_capability=({_mapping('o')}) AND au.activation_generation=o.activation_generation AND au.activation_capability=o.activation_capability
      AND au.kind IN ('human_confirmation','mandate') AND au.revoked_at IS NULL AND au.approved_request_hash=o.request_hash
      AND EXISTS(SELECT 1 FROM users u WHERE u.business_id=o.business_id AND u.id=au.actor_user_id AND u.is_active=TRUE AND u.session_version=au.actor_session_version)
      AND (au.mandate_uuid IS NULL OR EXISTS(SELECT 1 FROM financial_authorizations m WHERE m.business_id=o.business_id AND m.authorization_uuid=au.mandate_uuid AND m.kind='mandate' AND m.operation_uuid IS NULL AND m.revoked_at IS NULL AND {expiry} AND m.activation_generation=o.activation_generation AND m.activation_capability=o.activation_capability AND m.approved_request_hash=o.request_hash AND m.actor_user_id=au.actor_user_id AND m.actor_session_version=au.actor_session_version)) {allowed})),FALSE)"""


def surfaces():
    columns = guarded_columns()
    # No son hechos económicos finales. Su confirmación escribe en tablas finales.
    for table in ("documents", "document_classifications", "document_profiles", "suppliers", "invoice_series", "recurring_invoices", "recurring_invoice_runs"):
        columns.pop(table, None)
    columns["invoice_fiscal_cancellation_coverage"] = ("business_id", "operation_uuid")
    return columns


def _scope(conn, table, action, fields):
    pg = conn.dialect == "postgres"
    eq = "IS DISTINCT FROM" if pg else "IS NOT"
    ref = "OLD" if action == "DELETE" else "NEW"
    scope = "TRUE" if action != "UPDATE" else "(" + " OR ".join(f"NEW.{f} {eq} OLD.{f}" for f in fields) + ")"
    if table == "invoices":
        scope += f" AND ({ref}.status<>'borrador'" + (" OR OLD.status<>'borrador'" if action == "UPDATE" else "") + ")"
    elif table in ("invoice_lines", "invoice_profiles"):
        parents = f"(i.business_id={ref}.business_id AND i.id={ref}.invoice_id)"
        if action == 'UPDATE':
            parents += ' OR (i.business_id=OLD.business_id AND i.id=OLD.invoice_id)'
        scope += f" AND EXISTS(SELECT 1 FROM invoices i WHERE ({parents}) AND i.status<>'borrador')"
    elif table == "invoice_events":
        scope += f" AND {ref}.event_type IN ('emision','rectificacion','anulacion')"
    elif table == "document_sequences":
        scope += f" AND ({ref}.kind='invoice' OR substr({ref}.kind,1,15)='invoice_series:')"
    elif table == 'bank_transactions' and action == 'UPDATE':
        # Sugerir/descartar un candidato no importa ni concilia dinero. La
        # transición confirmed y cualquier cambio del hecho importado sí.
        operational = {'status', 'suggested_invoice_id', 'match_score', 'match_reason', '_financial_revision'}
        immutable = [f for f in fields if f not in operational]
        scope = '(' + ' OR '.join(f'NEW.{f} {eq} OLD.{f}' for f in immutable) + " OR NEW.status='confirmed' OR OLD.status='confirmed')"
    elif table in ("verifactu_outbox", "verifactu_cancellation_outbox"):
        # UPDATE de respuestas/estado/contadores de transporte no crea el hecho fiscal.
        # INSERT y datos del envío están protegidos; F cerrará política de dispatch.
        if action == "UPDATE":
            transport = {"status", "sent_at", "completed_at", "updated_at", "attempts"}
            identity = [f for f in fields if f not in transport]
            scope = "(" + " OR ".join(f"NEW.{f} {eq} OLD.{f}" for f in identity) + ")"
    return scope


def commands_for(table):
    if table in ("invoices",):
        return ("invoice.issue", "invoice.rectify", "customer_payment.record", "bank_transaction.match")
    if table in ("invoice_lines", "invoice_profiles", "invoice_records", "verifactu_outbox", "invoice_economic_coverage", "document_sequences"):
        return ("invoice.issue", "invoice.rectify")
    if table in ("invoice_payments", "payment_economic_coverage"):
        return ("customer_payment.record", "bank_transaction.match")
    if table in ("invoice_cancellation_records", "verifactu_cancellation_outbox", "invoice_fiscal_cancellation_coverage"):
        return ("invoice.fiscal_cancel",)
    if table in ("bank_transactions", "bank_import_coverage", "bank_match_coverage", "bank_payment_links"):
        return ("bank_transaction.import", "bank_transaction.match")
    if table in ("received_invoices", "supplier_invoice_economic_coverage"):
        return ("supplier_invoice.confirm", "supplier_invoice.correct", "supplier_invoice.void")
    if table in ("expenses", "expense_economic_coverage"):
        return ("expense.confirm", "expense.void")
    return tuple(c.value for c in CommandType)


def install(conn):
    pg = conn.dialect == "postgres"
    c = lambda key: context_field(conn, key)
    # Inmutabilidad de los bindings incluso para filas anteriores con NULL.
    eq = "IS DISTINCT FROM" if pg else "IS NOT"
    for table in ("financial_operations", "financial_authorizations"):
        guard(conn, "activation_binding_immutable_" + table, table, "UPDATE",
              f"NEW.activation_generation {eq} OLD.activation_generation OR NEW.activation_capability {eq} OLD.activation_capability")
    valid = f"""EXISTS(SELECT 1 FROM financial_activation_control a JOIN {GRANTS} g ON g.business_id=a.business_id AND g.activation_generation=a.activation_generation
      WHERE a.business_id=NEW.business_id AND a.ever_enabled=TRUE AND a.state='enabled' AND g.capability=NEW.activation_capability
      AND NEW.activation_generation=a.activation_generation AND NEW.activation_capability=({_mapping()})
      AND {c('kind')}='prepare' AND CAST({c('business_id')} AS TEXT)=CAST(NEW.business_id AS TEXT)
      AND {c('operation_uuid')}=CAST(NEW.operation_uuid AS TEXT) AND {c('request_hash')}=NEW.request_hash
      AND CAST({c('generation')} AS BIGINT)=NEW.activation_generation AND {c('capability')}=NEW.activation_capability
      AND CAST({c('availability')} AS TEXT) IN ('true','1'))"""
    guard(conn, "activation_operation_insert", "financial_operations", "INSERT",
          f"({_ever('NEW')} AND (NEW.entry_namespace='historical' OR NOT COALESCE(({valid}),FALSE))) OR (NOT ({_ever('NEW')}) AND (NEW.activation_generation IS NOT NULL OR NEW.activation_capability IS NOT NULL))")
    for state in ("approved", "committed"):
        if state == "committed":
            proof = _context(conn, "NEW", operation_field="operation_uuid")
        else:
            proof = f"""COALESCE(({c('kind')}='authorize' AND {c('operation_uuid')}=CAST(NEW.operation_uuid AS TEXT)
              AND CAST({c('generation')} AS BIGINT)=NEW.activation_generation AND {c('capability')}=NEW.activation_capability
              AND EXISTS(SELECT 1 FROM financial_activation_control a JOIN {GRANTS} g ON g.business_id=a.business_id AND g.activation_generation=a.activation_generation
                WHERE a.business_id=NEW.business_id AND a.state='enabled' AND a.ever_enabled=TRUE AND a.activation_generation=NEW.activation_generation AND g.capability=NEW.activation_capability)
              AND EXISTS(SELECT 1 FROM financial_authorizations au WHERE au.business_id=NEW.business_id AND au.authorization_uuid=NEW.authorization_uuid AND au.operation_uuid=NEW.operation_uuid AND au.activation_generation=NEW.activation_generation AND au.activation_capability=NEW.activation_capability)),FALSE)"""
        guard(conn, "activation_operation_" + state, "financial_operations", "UPDATE",
              f"({_ever('NEW')}) AND NEW.state='{state}' AND NOT ({proof})")
    authorization = f"""EXISTS(SELECT 1 FROM financial_activation_control a JOIN {GRANTS} g ON g.business_id=a.business_id AND g.activation_generation=a.activation_generation
      WHERE a.business_id=NEW.business_id AND a.state='enabled' AND a.ever_enabled=TRUE AND a.activation_generation=NEW.activation_generation
      AND g.capability=NEW.activation_capability AND CAST({c('generation')} AS BIGINT)=NEW.activation_generation
      AND CAST({c('business_id')} AS TEXT)=CAST(NEW.business_id AS TEXT) AND {c('capability')}=NEW.activation_capability
      AND {c('request_hash')}=NEW.approved_request_hash AND {c('kind')} IN ('authorize','mandate')
      AND CAST({c('availability')} AS TEXT) IN ('true','1')
      AND (NEW.operation_uuid IS NULL OR EXISTS(SELECT 1 FROM financial_operations o WHERE o.business_id=NEW.business_id AND o.operation_uuid=NEW.operation_uuid AND o.activation_generation=NEW.activation_generation AND o.activation_capability=NEW.activation_capability)))"""
    guard(conn, "activation_authorization_insert", "financial_authorizations", "INSERT",
          f"({_ever('NEW')} AND (NEW.kind='historical_unknown' OR NOT COALESCE(({authorization}),FALSE))) OR (NOT ({_ever('NEW')}) AND (NEW.activation_generation IS NOT NULL OR NEW.activation_capability IS NOT NULL))")
    for table, fields in surfaces().items():
        for action in ("INSERT", "UPDATE", "DELETE"):
            ref = "OLD" if action == "DELETE" else "NEW"
            scope = _scope(conn, table, action, fields)
            field = "operation_uuid" if table.endswith("coverage") or table in ("economic_events", "economic_event_links") else None
            # economic_event_links no tiene operation_uuid; validar por evento padre.
            if table == "economic_event_links":
                field = None
            proof = _context(conn, ref, commands_for(table), operation_field=field, table=table, action=action)
            tenants = f"({_ever(ref)})"
            if action == "UPDATE":
                tenants += f" OR ({_ever('OLD')})"
                scope += f" OR NEW.business_id {eq} OLD.business_id"
            guard(conn, "activation_live_" + table + "_" + action.lower(), table, action,
                  f"({scope}) AND ({tenants}) AND NOT ({proof})")
            if action == 'UPDATE':
                guard(conn, 'activation_tenant_' + table, table, action,
                      f'NEW.business_id {eq} OLD.business_id AND ({tenants})')


def uninstall(conn):
    for table in ("financial_operations", "financial_authorizations"):
        _drop(conn, "activation_binding_immutable_" + table, table)
    for name, table in (("activation_operation_insert", "financial_operations"), ("activation_operation_approved", "financial_operations"), ("activation_operation_committed", "financial_operations"), ("activation_authorization_insert", "financial_authorizations")):
        _drop(conn, name, table)
    for table in surfaces():
        _drop(conn, 'activation_tenant_' + table, table)
        for action in ("insert", "update", "delete"):
            _drop(conn, "activation_live_" + table + "_" + action, table)
