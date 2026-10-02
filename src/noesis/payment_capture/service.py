"""Cobros reales y evidencia v1 en la transacción del propietario."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid5

from noesis import db
from noesis.core.locks import lock_business
from noesis.core.money import parse_money
from noesis.economic_events.contracts import EconomicEvent, EventRelation, EventType, RelationType, SourceType
from noesis.economic_events.service import EconomicEvents
from noesis.financial_operations.contracts import (
    CommandType, EntryIdentity, FinancialRequest, OperationState, StateError,
)
from noesis.financial_operations.service import FinancialOperations, _now
from noesis.financial_writers import payments
from noesis.financial_writers.boundary import _json, freeze, observe, revision_reader, snapshot
from noesis.invoice_capture.service import _decimal_context, fingerprint


def event_id(operation_uuid, slot):
    return str(uuid5(UUID(str(operation_uuid)), slot))


@_decimal_context
def exact_amount(value, *, positive=True):
    number = parse_money(value)
    if number != number.quantize(Decimal('0.01')) or abs(number) > Decimal('10000000'):
        raise ValueError('Importe exacto en céntimos dentro del límite requerido.')
    if number == 0 or (positive and number < 0):
        raise ValueError('Importe positivo requerido.' if positive else 'Importe no nulo requerido.')
    return number.quantize(Decimal('0.01'))


def text(value, limit):
    if value is not None and (not isinstance(value, str) or len(value.strip()) > limit):
        raise ValueError('Texto opcional acotado requerido.')
    return value.strip() or None if value is not None else None


def payment_date(value):
    value = db._payment_paid_at(value)
    if datetime.fromisoformat(value).tzinfo is not None:
        raise ValueError('El origen legacy guarda fecha local sin zona; no convertir un instante implícitamente.')
    return value


def invoice_context(session, principal, business_id, invoice_id):
    lock_business(session, business_id)
    source = snapshot(session.borrowed_connection, business_id, 'invoice', invoice_id)
    row = session.execute('SELECT event_uuid FROM invoice_economic_coverage WHERE business_id=? AND invoice_id=?',
                          (business_id, invoice_id)).fetchone()
    if not source or not row or source.data['status'] not in {'enviada', 'parcial', 'cobrada'}:
        raise StateError('Factura sin evidencia capturada válida; no reconstruir historia.')
    stored = EconomicEvents(session, business_id).read(principal, row['event_uuid'])
    if (stored.event.source_id != invoice_id or stored.event.payload_version != 2
            or stored.event.event_type not in {EventType.INVOICE_ISSUED, EventType.INVOICE_RECTIFIED}
            or stored.event.payload['evidence']['source_fingerprint'] != source.fingerprint
            or source.data['currency'] != 'EUR'):
        raise StateError('Evidencia de factura incoherente.')
    rows = session.borrowed_connection.execute_exact(
        'SELECT * FROM invoice_payments WHERE business_id=? AND invoice_id=? ORDER BY id',
        (business_id, invoice_id)).fetchall()
    # Procedencia binaria explícita; no SUM sobre REAL/DOUBLE ni respuesta pública.
    paid = sum((Decimal(str(r['amount'])).quantize(Decimal('0.01')) for r in rows), Decimal('0.00'))
    remaining = source.amounts['total'] - paid
    context = {'invoice_fingerprint': source.fingerprint, 'payments': _json(freeze(rows)),
               'status': source.data['status'], 'paid_at': source.data['paid_at'],
               'remaining': format(remaining, '.2f')}
    return source, stored.event, remaining, fingerprint(context)


def reserve_payment(session, business_id, operation_uuid, invoice_id, original_uuid):
    session.execute('INSERT INTO payment_economic_coverage '
        '(business_id,operation_uuid,invoice_id,invoice_event_uuid,event_uuid) VALUES (?,?,?,?,?)',
        (business_id, operation_uuid, invoice_id, str(original_uuid), event_id(operation_uuid, 'payment')))


def append_payment(session, principal, business_id, operation_uuid, request, writer):
    """Único productor compartido por cobro manual y conciliación bancaria."""
    sources = [s for s in writer.snapshots if s.source_type == 'invoice_payment']
    if len(sources) != 1 or sources[0].source_id != writer.payment_id or writer.input_provenance != 'exact_input':
        raise StateError('Un pago recién creado con snapshot exacto requerido.')
    source = sources[0]
    if source.amounts['amount'] != request.amount:
        raise StateError('El writer no creó el importe aprobado; revertir.')
    coverage = session.execute('SELECT invoice_id,invoice_event_uuid FROM payment_economic_coverage '
                              'WHERE business_id=? AND operation_uuid=?', (business_id, operation_uuid)).fetchone()
    if source.data['invoice_id'] != coverage['invoice_id']:
        raise StateError('Snapshot de otra factura.')
    original = EconomicEvents(session, business_id).read(principal, coverage['invoice_event_uuid']).event
    session.execute('UPDATE payment_economic_coverage SET payment_id=?,source_fingerprint=? '
                    'WHERE business_id=? AND operation_uuid=?',
                    (source.source_id, source.fingerprint, business_id, operation_uuid))
    event = EconomicEvent(event_id(operation_uuid, 'payment'), business_id, EventType.CUSTOMER_PAYMENT_RECEIVED,
        SourceType.INVOICE_PAYMENT, source.source_id, source.revision, None, datetime.now(timezone.utc),
        {'invoice_id': source.data['invoice_id'], 'amount': source.amounts['amount'],
         'received_on': str(source.data['paid_at'])[:10], 'method': source.data['method']},
        relations=(EventRelation(RelationType.SETTLES, original.event_id, original.event_type, business_id),))
    stored = EconomicEvents(session, business_id).append(principal, event, operation_uuid=operation_uuid,
        event_slot='payment', revision_reader=revision_reader(business_id),
        provenance='payment_capture.v1:legacy_binary_storage:' + source.fingerprint,
        date_provenance='invoice_payment.paid_at:local_day')
    return {'payment_id': source.source_id, 'invoice_id': source.data['invoice_id'],
        'event_uuid': str(stored.event.event_id), 'content_hash': stored.event.content_hash,
        'source_fingerprint': source.fingerprint, 'amount': format(source.amounts['amount'], '.2f'),
        'currency': 'EUR', 'captured': True}


class PaymentCapture:
    """Solo servidor autenticado: review → prepare → authorize → execute."""

    def __init__(self, business_id):
        self.operations = FinancialOperations(business_id)
        self.business_id = self.operations.business_id

    @_decimal_context
    def review(self, principal, invoice_id, *, amount=None, mode='partial', method=None, paid_at=None, note=None):
        if mode not in {'partial', 'full', 'remaining'} or (mode != 'partial' and amount is not None):
            raise ValueError('Modo parcial con importe, o full/remaining sin importe.')
        with self.operations._transaction(principal) as (session, _):
            source, original, remaining, settlement = invoice_context(session, principal, self.business_id, invoice_id)
            number = exact_amount(amount if mode == 'partial' else remaining)
            if number > remaining:
                raise StateError('El cobro supera el saldo pendiente.')
            when = payment_date(paid_at)
            return FinancialRequest(CommandType.CUSTOMER_PAYMENT_RECORD, invoice_id, number, when[:10],
                source.revision, None, {'mode': mode, 'method': text(method, 50), 'paid_at': when,
                    'note': text(note, 500), 'invoice_event': str(original.event_id),
                    'invoice_fingerprint': source.fingerprint, 'settlement_fingerprint': settlement})

    def _contract(self, session, request):
        fields = {'mode', 'method', 'paid_at', 'note', 'invoice_event', 'invoice_fingerprint', 'settlement_fingerprint'}
        if (request.command_type != CommandType.CUSTOMER_PAYMENT_RECORD or set(request.parameters) != fields
                or request.target_id is None or request.expected_revision is None
                or request.reason is not None or request.parameters['mode'] not in {'partial', 'full', 'remaining'}):
            raise StateError('Request cerrado de PaymentCapture requerido.')
        exact_amount(request.amount)
        if (payment_date(request.parameters['paid_at']) != request.parameters['paid_at']
                or request.effective_on != request.parameters['paid_at'][:10]
                or text(request.parameters['method'], 50) != request.parameters['method']
                or text(request.parameters['note'], 500) != request.parameters['note']):
            raise StateError('Fecha/método/nota no canónicos.')

    @_decimal_context
    def _validate(self, session, request, principal):
        self._contract(session, request)
        source, original, remaining, settlement = invoice_context(session, principal, self.business_id, request.target_id)
        if (str(original.event_id) != request.parameters['invoice_event']
                or source.fingerprint != request.parameters['invoice_fingerprint']
                or request.amount > remaining
                or (request.parameters['mode'] != 'partial' and
                    (settlement != request.parameters['settlement_fingerprint'] or request.amount != remaining))):
            raise StateError('Contexto de liquidación stale; revisar de nuevo.')
        return source.revision

    def prepare(self, principal, identity, request, *, preparation_recorder=None):
        if not isinstance(identity, EntryIdentity) or not isinstance(request, FinancialRequest):
            raise TypeError('Identidad y request tipados requeridos.')
        with self.operations._transaction(principal) as (session, repo):
            self._contract(session, request)
            operation = repo.prepare(principal, identity, request, _now())
            if operation.state == OperationState.PREPARED:
                self._validate(session, request, principal)
            if preparation_recorder is not None:
                preparation_recorder(session, operation)
            return operation

    def authorize(self, principal, operation_uuid, **approval):
        return self.operations.authorize(principal, operation_uuid,
            revision_reader=lambda s, r: self._validate(s, r, principal),
            request_validator=lambda s, r: self._validate(s, r, principal), **approval)

    @_decimal_context
    def execute(self, principal, operation_uuid):
        observations = []
        def effect(session, request):
            self._validate(session, request, principal)
            reserve_payment(session, self.business_id, operation_uuid, request.target_id, request.parameters['invoice_event'])
            writer = payments.add_invoice_payment(session, request.target_id, request.amount,
                business_id=self.business_id, method=request.parameters['method'], paid_at=request.parameters['paid_at'],
                note=request.parameters['note'], expected_revision=request.expected_revision)
            result = append_payment(session, principal, self.business_id, operation_uuid, request, writer)
            observations.append(writer)
            return result
        result = self.operations.execute(principal, operation_uuid, effect, request_validator=self._contract,
            revision_reader=lambda s, r: self._validate(s, r, principal))
        for writer in observations:
            observe_after_commit(writer)
        return result


def observe_after_commit(writer):
    try:
        observe(writer)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('Observación no disponible después del commit')
