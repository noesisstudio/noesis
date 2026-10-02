"""Confirmación/corrección/retirada con evidencia en el commit del propietario."""

from datetime import date, datetime, timezone
from decimal import Decimal
import json

from noesis import db
from noesis.core.locks import lock_business
from noesis.core.money import parse_money
from noesis.economic_events.contracts import EconomicEvent, EventRelation, EventType, RelationType, SourceType, canonical_payload
from noesis.economic_events.service import EconomicEvents
from noesis.financial_operations.contracts import CommandType, EntryIdentity, FinancialRequest, OperationState, StateError, positive_id
from noesis.financial_operations.service import FinancialOperations, _now
from noesis.financial_writers import documents, purchasing
from noesis.financial_writers.boundary import _json, freeze, revision_reader, snapshot
from noesis.invoice_capture.service import _decimal_context, fingerprint
from noesis.payment_capture.service import event_id, observe_after_commit

SUPPLIER_FIELDS = ('supplier_id', 'number', 'concept', 'issued_on', 'due_on', 'base',
                   'vat_rate', 'vat_amount', 'irpf_amount', 'total', 'category')
EXPENSE_FIELDS = ('concept', 'amount', 'vat_rate', '_captured_vat_amount', 'category', 'spent_on', 'project_id')
MONEY = {'base', 'vat_amount', 'irpf_amount', 'total', 'amount', '_captured_vat_amount'}


@_decimal_context
def cents(value, *, positive=False):
    if value is None:
        return None
    number = parse_money(value)
    if number != number.quantize(Decimal('.01')) or number < 0 or number > Decimal('10000000'):
        raise ValueError('Importe no negativo y exacto en céntimos requerido.')
    if positive and number <= 0:
        raise ValueError('Importe positivo requerido.')
    return format(number, '.2f')


def canonical(value):
    return json.dumps(_json(freeze(value)), sort_keys=True, separators=(',', ':'), ensure_ascii=False)


@_decimal_context
def projection(source):
    """No redondear subcéntimos históricos ni llamar a la normalización pública."""
    fields = SUPPLIER_FIELDS if source.source_type == 'received_invoice' else EXPENSE_FIELDS
    result = {}
    for key in fields:
        value = source.data.get(key)
        if key in MONEY:
            value = cents(value, positive=key in {'total', 'amount'})
        elif key == 'vat_rate' and value is not None:
            value = format(parse_money(value).normalize(), 'f')
        elif key == 'spent_on' and value is not None:
            # Legacy PG usa TIMESTAMP para una fecha civil. Solo medianoche sin zona.
            when = datetime.fromisoformat(value) if len(value) > 10 else None
            if when is not None and (when.tzinfo is not None or when.time() != datetime.min.time()):
                raise StateError('Fecha de gasto legacy ambigua; no inventar fecha/zona.')
            value = value[:10]
        result[key] = value
    result['voided_at'] = source.data.get('voided_at')
    result['void_reason'] = source.data.get('void_reason')
    return result


def payload_state(state, kind):
    if kind == 'received_invoice':
        return {'total': state['total'], 'issued_on': state['issued_on'], 'invoice_number': state['number'],
                'due_on': state['due_on'], 'base': state['base'], 'vat_amount': state['vat_amount'],
                'irpf_amount': state['irpf_amount']}
    return {'total': state['amount'], 'spent_on': state['spent_on'], 'description': state['concept'],
            'vat_amount': state['_captured_vat_amount']}


def checkpoint(stage):
    """Frontera local para comprobar rollback; no I/O ni extensión de canales."""


class _PurchasingCapture:
    def __init__(self, business_id):
        self.operations = FinancialOperations(business_id)
        self.business_id = self.operations.business_id

    def _document(self, session, doc_id):
        if doc_id is None:
            return None
        positive_id(doc_id)
        row = session.borrowed_connection.execute_exact('SELECT * FROM documents WHERE business_id=? AND id=?' +
                              (' FOR UPDATE' if session.dialect == 'postgres' else ''),
                              (self.business_id, doc_id)).fetchone()
        if not row or any(row[k] is not None for k in ('invoice_id', 'received_invoice_id', 'expense_id')):
            raise StateError('Documento ausente, ajeno o ya confirmado.')
        classes = session.borrowed_connection.execute_exact('SELECT * FROM document_classifications WHERE business_id=? AND document_id=? ORDER BY id',
                                  (self.business_id, doc_id)).fetchall()
        if any(r['method'] == 'pdf_batch' for r in classes):
            raise StateError('El lote documental no es un origen confirmable.')
        return fingerprint({'document': _json(freeze(row)), 'classifications': _json(freeze(classes))})

    def _latest(self, session, principal, source_id):
        row = session.execute(f'SELECT * FROM {self.coverage} WHERE business_id=? AND source_id=? '
                              'ORDER BY source_revision DESC LIMIT 1', (self.business_id, source_id)).fetchone()
        if not row or row['after_state'] is None:
            raise StateError('Origen sin último estado económico cubierto; no reconstruir historia.')
        event = EconomicEvents(session, self.business_id).read(principal, row['event_uuid']).event
        return row, event

    def _context(self, session, principal, source_id):
        positive_id(source_id)
        lock_business(session, self.business_id)
        checkpoint('lock')
        source = snapshot(session.borrowed_connection, self.business_id, self.kind, source_id)
        if not source or source.data.get('voided_at') is not None:
            raise StateError('Origen ausente, ajeno o retirado.')
        row, event = self._latest(session, principal, source_id)
        state = projection(source)
        if (canonical(state) != row['after_state'] or event.source_id != source_id
                or event.source_revision != row['source_revision'] or event.event_type.value != row['event_type']):
            raise StateError('Discontinuidad económica; diagnóstico/backfill posterior requerido.')
        checkpoint('before')
        return source, state, event

    def _fields(self, raw):
        allowed = set(SUPPLIER_FIELDS) | {'note', 'supplier_name', 'supplier_nif'} if self.kind == 'received_invoice' else (
            set(EXPENSE_FIELDS) - {'_captured_vat_amount'} | {'vat_amount'})
        if set(raw) - allowed:
            raise ValueError('Campos de captura desconocidos.')
        result = {key: raw.get(key) for key in allowed}
        if self.kind == 'expense':
            result['vat_amount'] = cents(result['vat_amount'])
        for key in MONEY & allowed:
            result[key] = cents(result[key], positive=key in {'total', 'amount'})
        for key in ('supplier_id', 'project_id'):
            if key in result and result[key] is not None:
                positive_id(result[key])
        for key in ('issued_on', 'due_on', 'spent_on'):
            if key in result:
                result[key] = db._optional_date(result[key], 'La fecha')
        if result.get('vat_rate') is not None:
            rate = parse_money(result['vat_rate'])
            if rate not in {Decimal(0), Decimal(4), Decimal(10), Decimal(21)}:
                raise ValueError('Tipo de IVA desconocido.')
            result['vat_rate'] = format(rate.normalize(), 'f')
        for key, limit in {'number': 50, 'concept': 500, 'category': 100, 'note': 2000,
                           'supplier_name': 200, 'supplier_nif': 30}.items():
            if key in result and result[key] is not None:
                value = result[key]
                if not isinstance(value, str) or len(value.strip()) > limit:
                    raise ValueError('Texto de captura inválido.')
                result[key] = value.strip() or None
        if self.kind == 'received_invoice':
            if result['supplier_id'] is not None and (result['supplier_name'] or result['supplier_nif']):
                raise ValueError('Proveedor por ID o datos explícitos, sin ambigüedad.')
            state = {**result, 'voided_at': None, 'void_reason': None}
        else:
            if not result['concept']:
                raise ValueError('Descripción obligatoria.')
            state = {**result, '_captured_vat_amount': result['vat_amount']}
        # Valida suma si todos los componentes son conocidos, sin inferir los demás.
        canonical_payload(self.confirm_event, {**payload_state(state, self.kind), 'confirmed_on': date.today().isoformat()})
        return result

    @_decimal_context
    def review_confirm(self, principal, *, document_id=None, **fields):
        fields = self._fields(fields)
        with self.operations._transaction(principal) as (session, _):
            lock_business(session, self.business_id)
            doc = self._document(session, document_id)
            if self.kind == 'expense' and document_id is not None:
                current_doc = session.execute('SELECT project_id FROM documents WHERE business_id=? AND id=?',
                                              (self.business_id, document_id)).fetchone()
                if fields['project_id'] is None:
                    fields['project_id'] = current_doc['project_id']
                if fields['category'] is None:
                    fields['category'] = 'Ticket'
            request = FinancialRequest(self.confirm_command, None, fields[self.amount_field], date.today().isoformat(), None, None,
                {'fields': fields, 'document_id': document_id, 'document_fingerprint': doc,
                 'before': None, 'antecedent': None, 'source_fingerprint': None})
            self._validate(session, request, principal)
            return request

    @_decimal_context
    def review_void(self, principal, source_id, *, reason):
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 2048:
            raise ValueError('Motivo de retirada obligatorio y acotado.')
        with self.operations._transaction(principal) as (session, _):
            source, state, prior = self._context(session, principal, source_id)
            return FinancialRequest(self.void_command, source_id, state[self.amount_field], date.today().isoformat(),
                source.revision, reason, {'fields': {}, 'document_id': None, 'document_fingerprint': None,
                'before': state, 'antecedent': str(prior.event_id), 'source_fingerprint': source.fingerprint})

    def _contract(self, session, request):
        commands = {self.confirm_command, self.void_command}
        if self.kind == 'received_invoice':
            commands.add(CommandType.SUPPLIER_INVOICE_CORRECT)
        if (request.command_type not in commands or set(request.parameters) !=
                {'fields', 'document_id', 'document_fingerprint', 'before', 'antecedent', 'source_fingerprint'}):
            raise StateError('Request cerrado de recibidas/gastos requerido.')
        if request.command_type == self.confirm_command:
            if (request.target_id is not None or request.expected_revision is not None or request.reason is not None
                    or any(request.parameters[k] is not None for k in ('before', 'antecedent', 'source_fingerprint'))):
                raise StateError('Confirmación nueva sin origen previo requerida.')
        elif (request.target_id is None or request.expected_revision is None or not request.reason
                or len(request.reason) > 2048 or any(request.parameters[k] is None for k in ('before', 'antecedent', 'source_fingerprint'))
                or request.parameters['document_id'] is not None or request.parameters['document_fingerprint'] is not None):
            raise StateError('Corrección/retirada requiere motivo, estado previo y revisión.')
        if request.amount is None or request.effective_on is None:
            raise StateError('Importe y fecha explícitos requeridos.')

    @_decimal_context
    def _validate(self, session, request, principal):
        self._contract(session, request)
        lock_business(session, self.business_id)
        if request.effective_on != date.today().isoformat():
            raise StateError('La fecha de confirmación/corrección/retirada requiere nueva revisión.')
        fields = request.parameters['fields']
        if request.command_type == self.confirm_command:
            if canonical(self._fields(fields)) != canonical(fields) or cents(request.amount) != fields[self.amount_field]:
                raise StateError('Campos/importe no canónicos.')
            if self._document(session, request.parameters['document_id']) != request.parameters['document_fingerprint']:
                raise StateError('Documento cambiado desde revisión.')
            for key, table in (('supplier_id', 'suppliers'), ('project_id', 'projects')):
                target = fields.get(key)
                if target is not None and not session.execute(f'SELECT id FROM {table} WHERE business_id=? AND id=?',
                                                              (self.business_id, target)).fetchone():
                    raise StateError('Referencia de otro negocio o inexistente.')
            return None
        source, state, prior = self._context(session, principal, request.target_id)
        if (source.revision != request.expected_revision or source.fingerprint != request.parameters['source_fingerprint']
                or canonical(state) != canonical(request.parameters['before']) or str(prior.event_id) != request.parameters['antecedent']):
            raise StateError('Revisión/estado económico antiguo; revisar de nuevo.')
        if request.command_type == self.void_command:
            if fields or cents(request.amount) != state[self.amount_field]:
                raise StateError('Retirada incoherente.')
        else:
            if canonical(self._fields(fields)) != canonical(fields) or cents(request.amount) != fields['total']:
                raise StateError('Corrección incoherente.')
            supplier = fields['supplier_id']
            if supplier is not None and not session.execute('SELECT id FROM suppliers WHERE business_id=? AND id=?',
                                                          (self.business_id, supplier)).fetchone():
                raise StateError('Proveedor ajeno o inexistente.')
        return source.revision

    def prepare(self, principal, identity, request, *, preparation_recorder=None):
        if not isinstance(identity, EntryIdentity) or not isinstance(request, FinancialRequest):
            raise TypeError('Identidad/request tipados requeridos.')
        with self.operations._transaction(principal) as (session, repo):
            self._contract(session, request)
            op = repo.prepare(principal, identity, request, _now())
            if op.state == OperationState.PREPARED:
                self._validate(session, request, principal)
            if preparation_recorder is not None:
                preparation_recorder(session, op)
            return op

    def authorize(self, principal, operation_uuid, **approval):
        return self.operations.authorize(principal, operation_uuid,
            revision_reader=lambda s, r: self._validate(s, r, principal),
            request_validator=lambda s, r: self._validate(s, r, principal), **approval)

    def _reserve(self, session, operation_uuid, request, source_id, revision, event_type):
        session.execute(f'INSERT INTO {self.coverage} '
            '(business_id,source_id,source_revision,operation_uuid,event_uuid,event_type,before_state,antecedent_uuid) '
            'VALUES (?,?,?,?,?,?,?,?)', (self.business_id, source_id, revision, operation_uuid,
            event_id(operation_uuid, 'purchasing'), event_type.value,
            canonical(request.parameters['before']) if request.parameters['before'] is not None else None,
            request.parameters['antecedent']))

    @_decimal_context
    def execute(self, principal, operation_uuid):
        observations = []
        def effect(session, request):
            self._validate(session, request, principal)
            is_confirm = request.command_type == self.confirm_command
            is_void = request.command_type == self.void_command
            event_type = self.confirm_event if is_confirm else self.void_event if is_void else EventType.SUPPLIER_INVOICE_CORRECTED
            before = request.parameters['before']
            if not is_confirm:
                self._reserve(session, operation_uuid, request, request.target_id, request.expected_revision + 1, event_type)
            if is_void:
                writer = (purchasing.void_received_invoice if self.kind == 'received_invoice' else purchasing.void_expense)(
                    session, request.target_id, datetime.now().isoformat(timespec='seconds'), request.reason, business_id=self.business_id,
                    expected_revision=request.expected_revision)
            elif is_confirm:
                fields = dict(request.parameters['fields'])
                doc = request.parameters['document_id']
                if self.kind == 'received_invoice':
                    if doc is not None:
                        writer = documents.confirm_received_invoice(session, self.business_id, doc, **fields)
                    elif fields['supplier_id'] is None:
                        fields.pop('supplier_id')
                        writer = documents.record_received_invoice(session, self.business_id, **fields)
                    else:
                        fields.pop('supplier_name')
                        fields.pop('supplier_nif')
                        writer = purchasing.add_received_invoice(session, business_id=self.business_id, **fields)
                elif doc is not None:
                    # Importe/fecha/descripción explícitos aprobados, sin fallback a OCR.
                    writer = documents.convert_ticket_to_expense(session, self.business_id, doc,
                        concept=fields['concept'], amount=fields['amount'], vat_rate=fields['vat_rate'],
                        spent_on=fields['spent_on'], vat_amount=fields['vat_amount'],
                        category=fields['category'], project_id=fields['project_id'])
                else:
                    writer = purchasing.add_expense(session, business_id=self.business_id, **fields)
            else:
                fields = dict(request.parameters['fields'])
                fields.pop('supplier_name')
                fields.pop('supplier_nif')
                writer = purchasing.update_received_invoice(session, request.target_id, business_id=self.business_id,
                    expected_revision=request.expected_revision, **fields)
            checkpoint('mutation')
            source = writer.snapshots[0]
            state = projection(source)
            checkpoint('revision')
            if (source.revision != (1 if is_confirm else request.expected_revision + 1)
                    or (not is_void and cents(request.amount) != state[self.amount_field])):
                raise StateError('Snapshot no coincide con revisión/importe aprobado.')
            if not is_confirm and not is_void:
                desired = {k: v for k, v in request.parameters['fields'].items() if k in SUPPLIER_FIELDS}
                if any(state[k] != v for k, v in desired.items()):
                    raise StateError('Writer modificó campos aprobados; no ajustar silenciosamente.')
            if is_confirm:
                desired = request.parameters['fields']
                pairs = {k: v for k, v in desired.items() if k in (SUPPLIER_FIELDS if self.kind == 'received_invoice' else EXPENSE_FIELDS)}
                if self.kind == 'expense':
                    pairs['_captured_vat_amount'] = desired['vat_amount']
                elif desired['supplier_id'] is None and (desired['supplier_name'] or desired['supplier_nif']):
                    pairs.pop('supplier_id')
                if any(state[k] != v for k, v in pairs.items()):
                    raise StateError('Snapshot no coincide con campos aprobados; rollback sin corrección implícita.')
            if is_confirm:
                self._reserve(session, operation_uuid, request, source.source_id, source.revision, event_type)
            session.execute(f'UPDATE {self.coverage} SET after_state=?,source_fingerprint=? '
                            'WHERE business_id=? AND operation_uuid=?',
                            (canonical(state), source.fingerprint, self.business_id, operation_uuid))
            checkpoint('coverage')
            if is_confirm:
                payload = {**payload_state(state, self.kind), 'confirmed_on': request.effective_on}
            elif is_void:
                payload = {'before': payload_state(before, self.kind), 'voided_on': request.effective_on, 'reason': request.reason}
            else:
                payload = {'before': payload_state(before, self.kind), 'after': payload_state(state, self.kind),
                           'corrected_on': request.effective_on, 'reason': request.reason}
            relations = ()
            if not is_confirm:
                prior = EconomicEvents(
                    session, self.business_id).read(principal, request.parameters['antecedent']).event
                relations = (EventRelation(RelationType.VOIDS if is_void else RelationType.CORRECTS,
                                           prior.event_id, prior.event_type, self.business_id),)
            event = EconomicEvent(event_id(operation_uuid, 'purchasing'), self.business_id, event_type,
                SourceType(self.kind), source.source_id, source.revision, None, datetime.now(timezone.utc), payload,
                relations=relations)
            stored = EconomicEvents(session, self.business_id).append(principal, event, operation_uuid=operation_uuid,
                event_slot='purchasing', revision_reader=revision_reader(self.business_id),
                provenance='purchasing_capture.v1:legacy_binary_storage:' + source.fingerprint,
                date_provenance=self.kind + ':civil_day_or_unknown')
            checkpoint('event')
            checkpoint('link')
            observations.append(writer)
            return {'source_id': source.source_id, 'source_revision': source.revision,
                    'event_uuid': str(stored.event.event_id), 'event_type': event_type.value,
                    'content_hash': event.content_hash, 'source_fingerprint': source.fingerprint,
                    'amount': cents(request.amount), 'currency': 'EUR', 'captured': True}
        result = self.operations.execute(principal, operation_uuid, effect,
            request_validator=self._contract, revision_reader=lambda s, r: self._validate(s, r, principal))
        for writer in observations:
            observe_after_commit(writer)
        return result


class SupplierInvoiceCapture(_PurchasingCapture):
    kind, coverage, amount_field = 'received_invoice', 'supplier_invoice_economic_coverage', 'total'
    confirm_command, void_command = CommandType.SUPPLIER_INVOICE_CONFIRM, CommandType.SUPPLIER_INVOICE_VOID
    confirm_event, void_event = EventType.SUPPLIER_INVOICE_CONFIRMED, EventType.SUPPLIER_INVOICE_VOIDED

    @_decimal_context
    def review_correct(self, principal, source_id, *, reason, **changes):
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 2048:
            raise ValueError('Motivo de corrección obligatorio y acotado.')
        if not changes or set(changes) - set(SUPPLIER_FIELDS):
            raise ValueError('Corrección económica explícita requerida.')
        with self.operations._transaction(principal) as (session, _):
            source, state, prior = self._context(session, principal, source_id)
            fields = self._fields({**{k: state[k] for k in SUPPLIER_FIELDS}, **changes, 'note': source.data['note']})
            if all(fields[k] == state[k] for k in SUPPLIER_FIELDS):
                raise ValueError('No hay cambio económico que corregir.')
            return FinancialRequest(CommandType.SUPPLIER_INVOICE_CORRECT, source_id, fields['total'], date.today().isoformat(),
                source.revision, reason, {'fields': fields, 'document_id': None, 'document_fingerprint': None,
                    'before': state, 'antecedent': str(prior.event_id), 'source_fingerprint': source.fingerprint})


class ExpenseCapture(_PurchasingCapture):
    kind, coverage, amount_field = 'expense', 'expense_economic_coverage', 'amount'
    confirm_command, void_command = CommandType.EXPENSE_CONFIRM, CommandType.EXPENSE_VOID
    confirm_event, void_event = EventType.EXPENSE_CONFIRMED, EventType.EXPENSE_VOIDED
