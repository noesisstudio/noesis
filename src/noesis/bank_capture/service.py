"""Evidencia bancaria; el match no constituye un segundo cobro."""

from datetime import date, datetime, timezone
from uuid import UUID

from noesis import banking
from noesis.core.locks import lock_business
from noesis.economic_events.contracts import EconomicEvent, EventRelation, EventType, RelationType, SourceType
from noesis.economic_events.service import EconomicEvents
from noesis.financial_operations.contracts import CommandType, ConflictError, EntryIdentity, FinancialRequest, Operation, StateError, canonical_json
from noesis.financial_writers import bank
from noesis.financial_writers.boundary import revision_reader, snapshot
from noesis.invoice_capture.service import _decimal_context, fingerprint
from noesis.payment_capture.service import (
    PaymentCapture, append_payment, event_id, exact_amount, invoice_context, observe_after_commit, reserve_payment, text,
)


class BankCapture:
    # Solo reutiliza el workflow de aprobación; coberturas y efectos son específicos.
    __init__ = PaymentCapture.__init__
    authorize = PaymentCapture.authorize

    def _batch(self, session, parameters):
        rows = session.execute('SELECT account_scope,statement_hash FROM bank_import_coverage '
            'WHERE business_id=? AND batch_uuid=?', (self.business_id, parameters['batch'])).fetchall()
        if any(r['account_scope'] != parameters['account_scope'] or r['statement_hash'] != parameters['statement_hash'] for r in rows):
            raise StateError('Batch vinculado a otra cuenta o extracto; no reinterpretar identidad.')
        return [r['bank_transaction_id'] for r in session.execute(
            'SELECT bank_transaction_id FROM bank_import_coverage WHERE business_id=? AND account_scope=? '
            'AND content_fingerprint=? AND batch_uuid<>? ORDER BY bank_transaction_id',
            (self.business_id, parameters['account_scope'], fingerprint(parameters['movement']), parameters['batch'])).fetchall()]

    @_decimal_context
    def review_import(self, principal, *, batch_uuid, row_key, account_scope, statement_hash,
                      booked_on, amount, description=None, counterparty=None, reference=None,
                      distinct_reason=None):
        batch = str(UUID(str(batch_uuid)))
        if UUID(batch).int == 0 or not isinstance(row_key, str) or not row_key.strip() or len(row_key) > 128:
            raise ValueError('UUID batch y fila estable acotada requeridos.')
        if not isinstance(account_scope, str) or not account_scope.strip() or len(account_scope) > 128:
            raise ValueError('Scope opaco de cuenta requerido, sin credenciales bancarias.')
        if not isinstance(statement_hash, str) or len(statement_hash) != 64 or any(c not in '0123456789abcdef' for c in statement_hash):
            raise ValueError('SHA-256 del extracto requerido.')
        when = date.fromisoformat(booked_on).isoformat()
        if when != booked_on:
            raise ValueError('Fecha ISO exacta requerida.')
        number = exact_amount(amount, positive=False)
        p = {'batch': batch, 'row': row_key, 'account_scope': account_scope, 'statement_hash': statement_hash,
             'movement': {'booked_on': when, 'description': text(description, 500),
                          'counterparty': text(counterparty, 200), 'reference': text(reference, 200),
                          'amount': format(number, '.2f')}, 'ambiguity_candidates': [],
             'distinct_reason': text(distinct_reason, 500)}
        with self.operations._transaction(principal) as (session, repo):
            lock_business(session, self.business_id)
            prior = session.execute('SELECT operation_uuid FROM bank_import_coverage WHERE business_id=? AND batch_uuid=? AND row_key=?',
                (self.business_id,batch,row_key)).fetchone()
            if prior:
                approved = Operation.from_row(repo.load(prior['operation_uuid'],principal.user_id)).request
                relevant = {'batch','row','account_scope','statement_hash','movement','distinct_reason'}
                if canonical_json({k:p[k] for k in relevant}) != canonical_json({k:approved.parameters[k] for k in relevant}):
                    raise ConflictError('Batch/fila ya capturados con otro contenido o resolución.')
                return approved  # Recupera también fecha y candidatos originalmente aprobados.
            p['ambiguity_candidates'] = self._batch(session, p)
            if p['ambiguity_candidates'] and not p['distinct_reason']:
                raise StateError('Contenido coincidente entre extractos: ambiguo, requiere resolución humana explícita.')
            return FinancialRequest(CommandType.BANK_TRANSACTION_IMPORT, None, number, when, None, None, p)

    def review_csv(self, principal, content, *, batch_uuid, account_scope, distinct_reasons=None):
        """Requests exactos por fila; no crea movimientos ni aprueba automáticamente."""
        digest, rows = banking.capture_csv_rows(content)
        return [(EntryIdentity.imported(batch_uuid, row_key), self.review_import(principal,
            batch_uuid=batch_uuid, row_key=row_key, account_scope=account_scope, statement_hash=digest,
            distinct_reason=(distinct_reasons or {}).get(row_key), **row)) for row_key, row in rows]

    def _match_context(self, session, principal, transaction_id):
        lock_business(session, self.business_id)
        source = snapshot(session.borrowed_connection, self.business_id, 'bank_transaction', transaction_id)
        row = session.execute('SELECT event_uuid FROM bank_import_coverage WHERE business_id=? AND bank_transaction_id=?',
                              (self.business_id, transaction_id)).fetchone()
        if not source or not row:
            raise StateError('Movimiento sin importación capturada; no reconstruir historia.')
        if source.data['status'] != 'suggested' or not source.data['suggested_invoice_id'] or source.amounts['amount'] <= 0:
            raise StateError('Movimiento no conciliable; confirmado por otra operación o sin sugerencia positiva.')
        imported = EconomicEvents(session, self.business_id).read(principal, row['event_uuid']).event
        if imported.event_type != EventType.BANK_TRANSACTION_IMPORTED or imported.source_id != transaction_id or imported.amount != source.amounts['amount']:
            raise StateError('Evidencia de importación incoherente.')
        invoice, original, remaining, _ = invoice_context(session, principal, self.business_id, source.data['suggested_invoice_id'])
        if source.amounts['amount'] > remaining:
            raise StateError('Movimiento supera saldo pendiente.')
        return source, invoice, original, imported

    @_decimal_context
    def review_match(self, principal, transaction_id):
        with self.operations._transaction(principal) as (session, _):
            source, invoice, original, imported = self._match_context(session, principal, transaction_id)
            return FinancialRequest(CommandType.BANK_TRANSACTION_MATCH, transaction_id, source.amounts['amount'],
                date.today().isoformat(), source.revision, None, {'bank_fingerprint': source.fingerprint,
                    'invoice_id': invoice.source_id, 'invoice_fingerprint': invoice.fingerprint,
                    'invoice_event': str(original.event_id), 'imported_event': str(imported.event_id)})

    def _contract(self, session, request):
        p = request.parameters
        if request.reason is not None:
            raise StateError('Motivo fuera del contrato bancario; usar resolución explícita del request.')
        if request.command_type == CommandType.BANK_TRANSACTION_IMPORT:
            if (set(p) != {'batch', 'row', 'account_scope', 'statement_hash', 'movement', 'ambiguity_candidates', 'distinct_reason'}
                    or request.target_id is not None or request.expected_revision is not None
                    or set(p['movement']) != {'amount', 'booked_on', 'description', 'counterparty', 'reference'}):
                raise StateError('Request cerrado de importación requerido.')
            exact_amount(request.amount, positive=False)
            # Revalidar forma también cuando el request procede de almacenamiento.
            if (str(UUID(p['batch'])) != p['batch'] or UUID(p['batch']).int == 0
                    or not p['row'].strip() or len(p['row']) > 128
                    or not p['account_scope'].strip() or len(p['account_scope']) > 128
                    or len(p['statement_hash']) != 64 or any(c not in '0123456789abcdef' for c in p['statement_hash'])
                    or p['movement']['amount'] != format(request.amount, '.2f')
                    or date.fromisoformat(p['movement']['booked_on']).isoformat() != p['movement']['booked_on']):
                raise StateError('Identidad/importe de importación inválidos.')
            for field, limit in (('description', 500), ('counterparty', 200), ('reference', 200)):
                if text(p['movement'][field], limit) != p['movement'][field]:
                    raise StateError('Movimiento no canónico.')
            if text(p['distinct_reason'], 500) != p['distinct_reason']:
                raise StateError('Resolución no canónica.')
        elif request.command_type == CommandType.BANK_TRANSACTION_MATCH:
            if (set(p) != {'bank_fingerprint', 'invoice_id', 'invoice_fingerprint', 'invoice_event', 'imported_event'}
                    or request.target_id is None or request.expected_revision is None):
                raise StateError('Request cerrado de conciliación requerido.')
            exact_amount(request.amount)
        else:
            raise StateError('Comando no bancario.')

    @_decimal_context
    def _validate(self, session, request, principal):
        self._contract(session, request)
        lock_business(session, self.business_id)
        p = request.parameters
        if request.command_type == CommandType.BANK_TRANSACTION_IMPORT:
            if request.effective_on != p['movement']['booked_on']:
                raise StateError('Fecha de contabilización bancaria diferente de la aprobada.')
            candidates = self._batch(session, p)
            if canonical_json(candidates) != canonical_json(p['ambiguity_candidates']) or (candidates and not p['distinct_reason']):
                raise StateError('Ambigüedad cambiada/no resuelta; revisar de nuevo.')
            return None
        if request.effective_on != date.today().isoformat():
            raise StateError('Fecha de revisión bancaria stale.')
        source, invoice, original, imported = self._match_context(session, principal, request.target_id)
        actual = {'bank_fingerprint': source.fingerprint, 'invoice_id': invoice.source_id,
                  'invoice_fingerprint': invoice.fingerprint, 'invoice_event': str(original.event_id),
                  'imported_event': str(imported.event_id)}
        if canonical_json(p) != canonical_json(actual) or request.amount != source.amounts['amount']:
            raise StateError('Revisión de conciliación stale.')
        return source.revision

    def prepare(self, principal, identity, request, *, preparation_recorder=None):
        if request.command_type == CommandType.BANK_TRANSACTION_IMPORT and identity != EntryIdentity.imported(request.parameters['batch'], request.parameters['row']):
            raise StateError('Identidad de operación debe coincidir con batch/fila.')
        return PaymentCapture.prepare(self, principal, identity, request, preparation_recorder=preparation_recorder)

    @_decimal_context
    def execute(self, principal, operation_uuid):
        observations = []
        def effect(session, request):
            self._validate(session, request, principal)
            if request.command_type == CommandType.BANK_TRANSACTION_IMPORT:
                result, writer = self._import(session, principal, operation_uuid, request)
            else:
                result, writer = self._match(session, principal, operation_uuid, request)
            observations.append(writer)
            return result
        result = self.operations.execute(principal, operation_uuid, effect, request_validator=self._contract,
            revision_reader=lambda s, r: self._validate(s, r, principal))
        for writer in observations:
            observe_after_commit(writer)
        return result

    def _import(self, session, principal, operation_uuid, request):
        p = request.parameters
        eid = event_id(operation_uuid, 'import')
        session.execute('INSERT INTO bank_import_coverage (business_id,operation_uuid,event_uuid,batch_uuid,row_key,'
            'account_scope,statement_hash,content_fingerprint) VALUES (?,?,?,?,?,?,?,?)',
            (self.business_id, operation_uuid, eid, p['batch'], p['row'], p['account_scope'],
             p['statement_hash'], fingerprint(p['movement'])))
        args = dict(p['movement'])
        args['amount'] = request.amount
        writer = bank.add_bank_transaction(session, self.business_id,
            import_hash=fingerprint([p['account_scope'], p['batch'], p['row']]), **args)
        if not writer.snapshots:
            raise StateError('Identidad bancaria ya existente fuera de la cobertura; no inferir retry.')
        source = writer.snapshots[0]
        if source.amounts['amount'] != request.amount or source.data['currency'] != 'EUR':
            raise StateError('Movimiento no coincide con el importe aprobado.')
        session.execute('UPDATE bank_import_coverage SET bank_transaction_id=?,source_revision=?,source_fingerprint=? '
            'WHERE business_id=? AND operation_uuid=?',
            (source.source_id, source.revision, source.fingerprint, self.business_id, operation_uuid))
        stored = EconomicEvents(session, self.business_id).append(principal, EconomicEvent(eid, self.business_id,
            EventType.BANK_TRANSACTION_IMPORTED, SourceType.BANK_TRANSACTION, source.source_id, source.revision,
            None, datetime.now(timezone.utc), {'amount': source.amounts['amount'], 'booked_on': source.data['booked_on'],
                'imported_on': str(source.data['created_at'])[:10], 'value_on': None, 'bank_reference': source.data['reference']}),
            operation_uuid=operation_uuid, event_slot='import', revision_reader=revision_reader(self.business_id),
            provenance='bank_capture.v1:legacy_binary_storage:' + source.fingerprint, date_provenance='bank_transaction.booked_on')
        return {'bank_transaction_id': source.source_id, 'event_uuid': str(stored.event.event_id),
            'content_hash': stored.event.content_hash, 'amount': format(source.amounts['amount'], '.2f'),
            'source_revision': source.revision, 'currency': 'EUR', 'captured': True}, writer

    def _match(self, session, principal, operation_uuid, request):
        p = request.parameters
        reserve_payment(session, self.business_id, operation_uuid, p['invoice_id'], p['invoice_event'])
        session.execute('INSERT INTO bank_match_coverage (business_id,bank_transaction_id,operation_uuid,'
            'imported_event_uuid,payment_event_uuid,event_uuid) VALUES (?,?,?,?,?,?)',
            (self.business_id, request.target_id, operation_uuid, p['imported_event'],
             event_id(operation_uuid, 'payment'), event_id(operation_uuid, 'match')))
        writer = bank.confirm_bank_transaction(session, request.target_id, self.business_id, expected_revision=request.expected_revision)
        payment = append_payment(session, principal, self.business_id, operation_uuid, request, writer)
        source = next(s for s in writer.snapshots if s.source_type == 'bank_transaction')
        if str(source.data['confirmed_at'])[:10] != request.effective_on:
            raise StateError('Fecha de confirmación distinta de la revisada; revertir.')
        session.execute('UPDATE bank_match_coverage SET payment_id=?,source_revision=? WHERE business_id=? AND operation_uuid=?',
                        (writer.payment_id, source.revision, self.business_id, operation_uuid))
        stored = EconomicEvents(session, self.business_id).append(principal, EconomicEvent(event_id(operation_uuid, 'match'),
            self.business_id, EventType.BANK_TRANSACTION_MATCHED, SourceType.BANK_TRANSACTION, source.source_id, source.revision,
            None, datetime.now(timezone.utc), {'amount': source.amounts['amount'], 'invoice_payment_id': writer.payment_id,
                'matched_on': str(source.data['confirmed_at'])[:10]}, relations=(
                EventRelation(RelationType.MATCHES, payment['event_uuid'], EventType.CUSTOMER_PAYMENT_RECEIVED, self.business_id),
                EventRelation(RelationType.EVIDENCE_FOR, p['imported_event'], EventType.BANK_TRANSACTION_IMPORTED, self.business_id))),
            operation_uuid=operation_uuid, event_slot='match', revision_reader=revision_reader(self.business_id),
            provenance='bank_capture.v1:legacy_binary_storage:' + source.fingerprint, date_provenance='bank_transaction.confirmed_at')
        return {**payment, 'bank_transaction_id': source.source_id, 'match_event_uuid': str(stored.event.event_id),
                'match_content_hash': stored.event.content_hash, 'imported_event_uuid': p['imported_event'],
                'source_revision': source.revision}, writer
