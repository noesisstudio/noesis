"""Historia económica y protección real compartidas por SQLite/PostgreSQL."""

from dataclasses import replace
from datetime import date
from decimal import Decimal, localcontext
import json
from unittest.mock import patch
from uuid import uuid4

from noesis import config, db, migrations
from noesis.core.persistence import FinancialSession
from noesis.documents import repo, service as document_service
from noesis.economic_events.contracts import CATALOG, EventType
from noesis.economic_events.service import EconomicEvents
from noesis.financial_operations.contracts import AccessDenied, ConflictError, EntryIdentity, StateError
from noesis.financial_operations.repository import OperationsRepository
from noesis.financial_writers import purchasing
from noesis.purchasing_capture import ExpenseCapture, SupplierInvoiceCapture
from tests.borrowed_writers_contract import BorrowedWritersContract
from tests.invoice_capture_contract import InvoiceCaptureContract

TABLES = ('received_invoices', 'expenses', 'documents', 'document_classifications', 'suppliers',
          'supplier_invoice_economic_coverage', 'expense_economic_coverage', 'economic_events',
          'economic_event_links', 'economic_event_sequences', 'financial_operations', 'financial_authorizations')


class PurchasingCaptureContract:
    seed = BorrowedWritersContract.seed
    document = BorrowedWritersContract.document
    migration_scope = InvoiceCaptureContract.migration_scope

    def setup_capture(self):
        self.seed()
        self.user = db.create_user(uuid4().hex + '@example.test', 'hash fixture', self.bid)
        from noesis.financial_operations.contracts import Principal
        self.principal = Principal(self.user['id'], 0)
        self.supplier = SupplierInvoiceCapture(self.bid)
        self.expense = ExpenseCapture(self.bid)

    def approved(self, service, request, identity=None):
        identity = identity or EntryIdentity.web_api(uuid4())
        op = service.prepare(self.principal, identity, request)
        return service.authorize(self.principal, op.operation_uuid, channel=identity.namespace,
                                 approved_hash=request.request_hash, approved_revision=request.expected_revision)

    def confirm(self, service=None, **fields):
        service = service or self.supplier
        fields = ({'total': '121.00'} if service.kind == 'received_invoice' else {'amount': '12.10', 'concept': 'Material'}) | fields
        op = self.approved(service, service.review_confirm(self.principal, **fields))
        return service.execute(self.principal, op.operation_uuid)

    def state(self):
        with db.get_conn() as conn:
            return {t: [dict(r) for r in conn.execute_exact(f'SELECT * FROM {t} WHERE business_id=? ORDER BY 1,2',
                                                          (self.bid,)).fetchall()] for t in TABLES}

    def event(self, result):
        with db.get_conn() as conn:
            return EconomicEvents(FinancialSession(conn), self.bid).read(self.principal, result.result['event_uuid']).event

    def void(self, service, result):
        op = self.approved(service, service.review_void(self.principal, result.result['source_id'], reason='Retirada confirmada'))
        return service.execute(self.principal, op.operation_uuid)

    def test_supplier_manual_unknown_components_dates(self):
        result = self.confirm()
        event = self.event(result)
        self.assertEqual(event.event_type, EventType.SUPPLIER_INVOICE_CONFIRMED)
        self.assertEqual(event.amount, Decimal('121.00'))
        for field in ('base', 'vat_amount', 'irpf_amount', 'issued_on', 'due_on', 'invoice_number'):
            self.assertIsNone(event.payload[field])
        self.assertIsNone(event.economic_date)
        self.assertIsNone(event.occurred_at)
        self.assertEqual(event.payload['confirmed_on'], date.today().isoformat())
        self.assertIn('legacy_binary_storage', self.state()['economic_events'][0]['provenance'])

    def test_supplier_full_components_irpf_and_dates(self):
        supplier = db.add_supplier('Proveedor', business_id=self.bid)
        result = self.confirm(total='106', base='100', vat_amount='21', irpf_amount='15', vat_rate='21',
                              supplier_id=supplier['id'], number='P-1', issued_on='2026-09-01', due_on='2026-10-01')
        event = self.event(result)
        self.assertEqual(event.payload['irpf_amount'], Decimal('15'))
        self.assertEqual(event.economic_date.isoformat(), '2026-09-01')
        self.assertEqual(event.payload['invoice_number'], 'P-1')
        coverage = self.state()['supplier_invoice_economic_coverage'][0]
        self.assertEqual(json.loads(coverage['after_state'])['supplier_id'], supplier['id'])

    def test_supplier_partial_components_not_inferred(self):
        result = self.confirm(total='121', base='100')
        self.assertIsNone(self.event(result).payload['vat_amount'])
        result = self.confirm(total='121', vat_amount='21', irpf_amount='0')
        self.assertIsNone(self.event(result).payload['base'])
        self.assertEqual(self.event(result).payload['irpf_amount'], Decimal('0'))

    def test_supplier_document_link_classification_same_commit(self):
        doc = self.document()
        result = self.confirm(document_id=doc, supplier_name='Proveedor documental')
        state = self.state()
        self.assertEqual(state['documents'][0]['received_invoice_id'], result.result['source_id'])
        self.assertEqual(state['documents'][0]['doc_status'], 'revisado')
        self.assertEqual(state['document_classifications'][0]['confirmed_kind'], 'factura_recibida')
        self.assertEqual(len(state['suppliers']), 1)
        self.assertEqual(len(state['economic_events']), 1)

    def test_ocr_upload_classification_never_produce_events(self):
        self.document()
        self.assertFalse(self.state()['economic_events'])
        self.assertFalse(self.state()['received_invoices'])
        self.assertFalse(self.state()['expenses'])

    def test_supplier_four_events_chain_immutable(self):
        result = self.confirm()
        original = self.state()['economic_events'][0]
        chain = [result]
        supplier = db.add_supplier('Otro proveedor', business_id=self.bid)
        for changes in ({'total': '140', 'issued_on': '2026-09-05'}, {'supplier_id': supplier['id'], 'number': 'C-2'}):
            op = self.approved(self.supplier, self.supplier.review_correct(self.principal, result.result['source_id'],
                                                                        reason='Dato confirmado', **changes))
            result = self.supplier.execute(self.principal, op.operation_uuid)
            chain.append(result)
        chain.append(self.void(self.supplier, result))
        state = self.state()
        self.assertEqual(len(state['economic_events']), 4)
        self.assertEqual(state['economic_events'][0], original)
        self.assertEqual(len(state['supplier_invoice_economic_coverage']), 4)
        for i, item in enumerate(chain[1:], 1):
            event = self.event(item)
            self.assertEqual(str(event.relations[0].target_event_id), chain[i-1].result['event_uuid'])
            self.assertEqual(event.relations[0].kind.value, 'voids' if i == 3 else 'corrects')
        self.assertEqual(self.event(chain[1]).payload['before']['total'], Decimal('121'))
        self.assertEqual(self.event(chain[2]).payload['before']['total'], Decimal('140'))
        self.assertEqual(len(state['received_invoices']), 1)
        self.assertIsNone(db.get_received_invoice(result.result['source_id'], self.bid))
        self.assertEqual(db.list_received_invoices(self.bid), [])

    def test_supplier_confirm_void_preserves_document_evidence(self):
        doc = self.document()
        confirmed = self.confirm(document_id=doc)
        result = self.void(self.supplier, confirmed)
        self.assertEqual(self.event(result).payload['before']['total'], Decimal('121'))
        state = self.state()
        self.assertEqual(state['documents'][0]['received_invoice_id'], result.result['source_id'])
        self.assertEqual(len(state['received_invoices']), 1)
        self.assertEqual(len(state['economic_events']), 2)

    def test_expense_known_and_unknown_vat(self):
        for quota in (None, '2.10', '0.00'):
            result = self.confirm(self.expense, vat_amount=quota, spent_on='2026-09-12')
            event = self.event(result)
            self.assertEqual(event.payload['vat_amount'], Decimal(quota) if quota is not None else None)
            self.assertEqual(event.payload['spent_on'], '2026-09-12')
            self.assertEqual(event.payload['description'], 'Material')
        result = self.confirm(self.expense, vat_rate='21')
        self.assertIsNone(self.event(result).payload['vat_amount'])
        self.assertIsNone(self.event(result).payload['spent_on'])

    def test_expense_ticket_confirmation_and_void(self):
        doc = self.document()
        result = self.confirm(self.expense, document_id=doc, vat_amount='2.10')
        self.assertEqual(self.state()['documents'][0]['expense_id'], result.result['source_id'])
        self.assertEqual(self.state()['document_classifications'][0]['confirmed_kind'], 'ticket')
        voided = self.void(self.expense, result)
        self.assertEqual(str(self.event(voided).relations[0].target_event_id), result.result['event_uuid'])
        self.assertEqual(db.list_expenses(self.bid), [])
        self.assertEqual(len(self.state()['expenses']), 1)
        self.assertEqual(len(self.state()['economic_events']), 2)

    def test_supplier_and_expense_retry_after_void_no_new_effect(self):
        for service in (self.supplier, self.expense):
            result = self.confirm(service)
            self.void(service, result)
            before = self.state()
            self.assertEqual(service.execute(self.principal, result.operation_uuid), result)
            self.assertEqual(before, self.state())

    def test_identity_conflict_and_equal_intentions_allowed(self):
        request = self.supplier.review_confirm(self.principal, total='121')
        identity = EntryIdentity.web_api(uuid4())
        op = self.approved(self.supplier, request, identity)
        done = self.supplier.execute(self.principal, op.operation_uuid)
        self.assertEqual(self.supplier.prepare(self.principal, identity, request).operation_uuid, done.operation_uuid)
        with self.assertRaises(ConflictError):
            self.supplier.prepare(self.principal, identity, self.supplier.review_confirm(self.principal, total='122'))
        self.confirm()
        self.assertEqual(len(self.state()['received_invoices']), 2)

    def test_supplier_stale_correction_and_void(self):
        result = self.confirm()
        source_id = result.result['source_id']
        stale = self.approved(self.supplier, self.supplier.review_correct(self.principal, source_id, reason='Primera', total='130'))
        other = self.approved(self.supplier, self.supplier.review_correct(self.principal, source_id, reason='Segunda', total='140'))
        void = self.approved(self.supplier, self.supplier.review_void(self.principal, source_id, reason='Retirada'))
        self.supplier.execute(self.principal, stale.operation_uuid)
        before = self.state()
        for op in (other, void):
            with self.assertRaises(StateError):
                self.supplier.execute(self.principal, op.operation_uuid)
        self.assertEqual(before, self.state())

    def test_operational_pagada_note_revision_without_payment(self):
        result = self.confirm()
        source_id = result.result['source_id']
        db.set_received_invoice_status(source_id, 'pagada', business_id=self.bid)
        with db.get_conn() as conn:
            conn.execute('UPDATE received_invoices SET note=? WHERE business_id=? AND id=?', ('Nota', self.bid, source_id))
        op = self.approved(self.supplier, self.supplier.review_correct(self.principal, source_id, reason='Importe', total='122'))
        self.supplier.execute(self.principal, op.operation_uuid)
        self.assertEqual(len(self.state()['economic_events']), 2)
        self.assertEqual(self.state()['received_invoices'][0]['status'], 'pagada')
        with db.get_conn() as conn:
            self.assertIsNone(conn.execute('SELECT 1 FROM invoice_payments WHERE business_id=?', (self.bid,)).fetchone())

    def test_legacy_sql_and_api_bypass_economic_and_delete_rejected(self):
        supplier = self.confirm()
        expense = self.confirm(self.expense)
        for table, result, update, delete in (
            ('received_invoices', supplier, lambda: db.update_received_invoice(supplier.result['source_id'], business_id=self.bid, total=5),
             lambda: db.delete_received_invoice(supplier.result['source_id'], self.bid)),
            ('expenses', expense, None, lambda: db.delete_expense(expense.result['source_id'], self.bid))):
            before = self.state()
            funcs = [delete] + ([update] if update else [])
            for func in funcs:
                with self.assertRaises(Exception):
                    func()
                self.assertEqual(before, self.state())
            for sql in (f'UPDATE {table} SET '+('total' if table == 'received_invoices' else 'amount')+'=5 WHERE business_id=? AND id=?',
                        f'DELETE FROM {table} WHERE business_id=? AND id=?'):
                with self.assertRaises(Exception):
                    with db.get_conn() as conn:
                        conn.execute(sql, (self.bid, result.result['source_id']))
                self.assertEqual(before, self.state())

    def test_all_economic_columns_and_void_reactivation_sql_protected(self):
        result = self.confirm()
        sid = result.result['source_id']
        for field, value in {'number': 'Alterado', 'supplier_id': self.client['id'], 'concept': 'Otro', 'category': 'Otra',
                             'issued_on': '2026-01-01', 'due_on': '2026-01-02', 'base': 1, 'vat_rate': 4,
                             'vat_amount': 1, 'irpf_amount': 1, 'voided_at': '2026-01-01', 'created_at': '2026-01-01'}.items():
            with self.subTest(field=field), self.assertRaises(Exception):
                with db.get_conn() as conn:
                    conn.execute(f'UPDATE received_invoices SET {field}=? WHERE business_id=? AND id=?', (value, self.bid, sid))
        self.void(self.supplier, result)
        with self.assertRaises(Exception):
            with db.get_conn() as conn:
                conn.execute('UPDATE received_invoices SET voided_at=NULL,void_reason=NULL WHERE business_id=? AND id=?', (self.bid, sid))

    def test_non_captured_legacy_behavior_preserved(self):
        received = db.add_received_invoice(2.675, business_id=self.bid, base=2.675)
        self.assertEqual(received['total'], 2.68)
        self.assertEqual(received['base'], 2.67)
        db.update_received_invoice(received['id'], business_id=self.bid, total=5)
        db.set_received_invoice_status(received['id'], 'pagada', business_id=self.bid)
        db.delete_received_invoice(received['id'], self.bid)
        expense = db.add_expense('Legacy', 2.675, business_id=self.bid)
        db.delete_expense(expense['id'], self.bid)
        self.assertFalse(self.state()['economic_events'])
        self.assertFalse(self.state()['received_invoices'])
        self.assertFalse(self.state()['expenses'])

    def test_float_subcent_invalid_amount_and_components(self):
        for service, args in ((self.supplier, {'total': '121'}), (self.expense, {'amount': '12.10', 'concept': 'Material'})):
            amount_field = service.amount_field
            for value in (2.1, '2.675', '-1', '0', 'NaN', 'Infinity', True):
                with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                    service.review_confirm(self.principal, **(args | {amount_field: value}))
        with self.assertRaises(ValueError):
            self.supplier.review_confirm(self.principal, total='100', base='100', vat_amount='21', irpf_amount='0')
        with self.assertRaises(ValueError):
            self.expense.review_confirm(self.principal, amount='10', concept='Material', vat_amount='11')

    def test_low_decimal_context_independent(self):
        with localcontext() as context:
            context.prec = 3
            result = self.confirm(total='12345.67')
        self.assertEqual(self.event(result).amount, Decimal('12345.67'))

    def test_void_reason_required_no_expense_corrected(self):
        result = self.confirm(self.expense)
        for reason in ('', None, '   '):
            with self.assertRaises((ValueError, StateError)):
                self.expense.review_void(self.principal, result.result['source_id'], reason=reason)
        self.assertNotIn('expense.corrected', {e.value for e in CATALOG})
        self.assertNotIn('supplier_payment.made', {e.value for e in CATALOG})

    def test_multi_business_source_document_supplier_operation_authorization(self):
        other = db.create_business('Otro', uuid4().hex + '@example.test')
        other_id = other['id']
        supplier = db.add_supplier('Ajeno', business_id=other_id)
        source = db.add_received_invoice(1, business_id=other_id)
        doc = repo.add(other_id, filename='otro.pdf', stored_name='otro.pdf', mime='application/pdf', size=1)
        for fields in ({'supplier_id': supplier['id']}, {'document_id': doc['id']}):
            with self.assertRaises((StateError, ValueError)):
                self.supplier.review_confirm(self.principal, total='121', **fields)
        with self.assertRaises(StateError):
            self.supplier.review_void(self.principal, source['id'], reason='Ajeno')
        op = self.approved(self.supplier, self.supplier.review_confirm(self.principal, total='121'))
        with self.assertRaises(AccessDenied):
            SupplierInvoiceCapture(other_id).execute(self.principal, op.operation_uuid)
        with self.assertRaises(Exception):
            with db.get_conn() as conn:
                conn.execute('UPDATE financial_operations SET authorization_uuid=? WHERE business_id=? AND operation_uuid=?',
                             (str(uuid4()), self.bid, op.operation_uuid))

    def test_coverage_and_history_immutable_cross_business_antecedent(self):
        result = self.confirm()
        for sql in ('UPDATE supplier_invoice_economic_coverage SET source_revision=source_revision+1 WHERE business_id=?',
                    'DELETE FROM supplier_invoice_economic_coverage WHERE business_id=?',
                    "UPDATE economic_events SET provenance='otra' WHERE business_id=?", 'DELETE FROM economic_events WHERE business_id=?'):
            with self.assertRaises(Exception):
                with db.get_conn() as conn:
                    conn.execute(sql, (self.bid,))
        request = self.supplier.review_void(self.principal, result.result['source_id'], reason='Motivo')
        other = self.confirm()
        altered = replace(request, parameters=dict(request.parameters) | {'antecedent': other.result['event_uuid']})
        with self.assertRaises(StateError):
            self.approved(self.supplier, altered)

    def test_omitted_event_or_coverage_cannot_commit_even_caught_append_error(self):
        for omit in ('event', 'coverage'):
            req = self.supplier.review_confirm(self.principal, total='121')
            op = self.approved(self.supplier, req)
            before = self.state()
            if omit == 'event':
                with patch('noesis.purchasing_capture.service.EconomicEvents.append', side_effect=RuntimeError('fallo')):
                    with self.assertRaises(RuntimeError):
                        self.supplier.execute(self.principal, op.operation_uuid)
            else:
                with patch.object(self.supplier, '_reserve', return_value=None):
                    with self.assertRaises(Exception):
                        self.supplier.execute(self.principal, op.operation_uuid)
            self.assertEqual(before, self.state())
            self.supplier.execute(self.principal, op.operation_uuid)

    def test_custom_executor_without_producer_cannot_mark_committed(self):
        req = self.expense.review_confirm(self.principal, amount='12.10', concept='Sin evento')
        op = self.approved(self.expense, req)
        before = self.state()
        def bypass(session, request):
            purchasing.add_expense(session, concept='Sin evento', amount='12.10', business_id=self.bid)
            return {'captured': True, 'currency': 'EUR'}
        with self.assertRaises(Exception):
            self.expense.operations.execute(self.principal, op.operation_uuid, bypass)
        self.assertEqual(before, self.state())

    def test_failures_correction_void_all_boundaries_rollback_retry(self):
        for service, command in ((self.supplier, 'correct'), (self.supplier, 'void'), (self.expense, 'void')):
            for stage in ('lock', 'before', 'mutation', 'revision', 'coverage', 'event', 'link', 'result'):
                with self.subTest(command=command, stage=stage):
                    result = self.confirm(service)
                    req = (service.review_correct(self.principal, result.result['source_id'], reason='Corrección', total='122')
                           if command == 'correct' else service.review_void(self.principal, result.result['source_id'], reason='Retirada'))
                    op = self.approved(service, req)
                    before = self.state()
                    if stage == 'result':
                        original = OperationsRepository.transition
                        def fail_result(repo, *args, **kwargs):
                            original(repo, *args, **kwargs)
                            raise RuntimeError('result')
                        context = patch.object(OperationsRepository, 'transition', fail_result)
                    else:
                        def fail(at):
                            if at == stage:
                                raise RuntimeError(stage)
                        context = patch('noesis.purchasing_capture.service.checkpoint', side_effect=fail)
                    with context, self.assertRaises(RuntimeError):
                        service.execute(self.principal, op.operation_uuid)
                    self.assertEqual(before, self.state())
                    service.execute(self.principal, op.operation_uuid)

    def test_document_failure_reverts_supplier_source_links_classification(self):
        for service in (self.supplier, self.expense):
            doc = self.document()
            fields = {'total': '121', 'supplier_name': 'Nuevo'} if service == self.supplier else {'amount': '12.10', 'concept': 'Ticket'}
            req = service.review_confirm(self.principal, document_id=doc, **fields)
            op = self.approved(service, req)
            before = self.state()
            with patch('noesis.purchasing_capture.service.checkpoint', side_effect=lambda stage: (_ for _ in ()).throw(RuntimeError(stage)) if stage == 'event' else None):
                with self.assertRaises(RuntimeError):
                    service.execute(self.principal, op.operation_uuid)
            self.assertEqual(before, self.state())
            service.execute(self.principal, op.operation_uuid)

    def test_document_stale_and_no_ocr_fallback(self):
        doc = self.document()
        req = self.expense.review_confirm(self.principal, document_id=doc, amount='12.10', concept='Aprobado')
        op = self.approved(self.expense, req)
        with db.get_conn() as conn:
            conn.execute('UPDATE documents SET ocr_amount=999 WHERE business_id=? AND id=?', (self.bid, doc))
        with self.assertRaises(StateError):
            self.expense.execute(self.principal, op.operation_uuid)
        with self.assertRaises((ValueError, TypeError)):
            self.expense.review_confirm(self.principal, document_id=doc, concept='No aprobado')

    def test_readers_hide_voids_lists_costs_tax_exports_gestoria(self):
        supplier = self.confirm(issued_on=date.today().isoformat(), category='Material')
        expense = self.confirm(self.expense, spent_on=date.today().isoformat())
        self.void(self.supplier, supplier)
        self.void(self.expense, expense)
        self.assertEqual(db.expenses_between('2000-01-01', '2099-12-31', self.bid), [])
        self.assertEqual(db.list_received_invoices(self.bid), [])
        self.assertEqual(db.gestoria_received_in(self.bid, '2000-01-01', '2099-12-31'), [])
        self.assertEqual(db.gestoria_expenses_in(self.bid, '2000-01-01', '2099-12-31'), [])
        self.assertEqual(db.month_billing(business_id=self.bid)['expenses'], 0)
        self.assertEqual(db.expenses_by_category(self.bid), [])
        self.assertEqual(db.profit_and_loss(self.bid)['expense_count'], 0)
        self.assertEqual(db.export_business_data(self.bid)['received_invoices'], [])
        self.assertEqual(db.export_business_data(self.bid)['expenses'], [])
        quarter = (date.today().month - 1)//3 + 1
        self.assertEqual(db.tax_quarter(date.today().year, quarter, self.bid)['gastos'], 0)
        self.assertEqual(len(self.state()['economic_events']), 4)

    def test_flags_off_capture_requested_no_fallback(self):
        self.assertFalse(config.FINANCIAL_CORE_ENABLED)
        for call in (lambda: db.add_received_invoice(1, business_id=self.bid, capture_requested=True),
                     lambda: db.add_expense('Gasto', 1, business_id=self.bid, capture_requested=True),
                     lambda: document_service.record_received_invoice(self.bid, total=1, capture_requested=True),
                     lambda: document_service.confirm_received_invoice(self.bid, self.document(), total=1, capture_requested=True),
                     lambda: document_service.convert_ticket_to_expense(self.bid, self.document(), amount=1, capture_requested=True)):
            with self.assertRaises(StateError):
                call()
        self.assertFalse(self.state()['economic_events'])

    def test_captured_account_and_migration_downgrade_blocked(self):
        self.confirm()
        before = self.state()
        with self.assertRaises(ValueError):
            db.delete_business_cascade(self.bid)
        with self.assertRaises(ValueError):
            migrations.downgrade(66)
        self.assertEqual(before, self.state())

    def test_migration_empty_down_up_preserves_legacy(self):
        with self.migration_scope():
            source = db.add_received_invoice(7, business_id=self.bid)
            migrations.downgrade(66)
            with db.get_conn() as conn:
                self.assertEqual(conn.execute('SELECT total FROM received_invoices WHERE business_id=? AND id=?',
                                             (self.bid, source['id'])).fetchone()['total'], 7)
            self.assertEqual(migrations.upgrade(), migrations.LATEST_VERSION)
            self.assertEqual(db.get_received_invoice(source['id'], self.bid)['total'], 7)

    def test_economic_discontinuity_fails_closed_without_reconstructing_before(self):
        result = self.confirm()
        # Simula una escritura de una versión anterior/superusuario que omitiese el guard.
        from noesis.purchasing_capture.schema import _definitions, _trigger
        with db.get_conn() as conn:
            suffix = ' ON received_invoices' if conn.dialect == 'postgres' else ''
            conn.execute('DROP TRIGGER supplier_invoice_source_update' + suffix)
            if conn.dialect == 'postgres':
                conn.execute('DROP FUNCTION supplier_invoice_source_update()')
            conn.execute('UPDATE received_invoices SET total=999 WHERE business_id=? AND id=?',
                         (self.bid, result.result['source_id']))
            definition = next(args for args in _definitions(conn) if args[0] == 'supplier_invoice_source_update')
            _trigger(conn, *definition)
        before = self.state()
        for call in (lambda: self.supplier.review_correct(self.principal, result.result['source_id'], reason='No reconstruir', total='1000'),
                     lambda: self.supplier.review_void(self.principal, result.result['source_id'], reason='No reconstruir')):
            with self.assertRaisesRegex(StateError, 'Discontinuidad'):
                call()
        self.assertEqual(before, self.state())

    def test_expense_operational_revision_stale_and_all_fields_protected(self):
        result = self.confirm(self.expense)
        sid = result.result['source_id']
        for field, value in {'concept': 'Otro', 'vat_rate': 4, '_captured_vat_amount': '1.00', 'category': 'Otra',
                             'spent_on': '2026-01-01', 'project_id': 123, 'created_at': '2026-01-01'}.items():
            with self.subTest(field=field), self.assertRaises(Exception):
                with db.get_conn() as conn:
                    conn.execute(f'UPDATE expenses SET {field}=? WHERE business_id=? AND id=?', (value, self.bid, sid))
        op = self.approved(self.expense, self.expense.review_void(self.principal, sid, reason='Retirada'))
        with db.get_conn() as conn:
            conn.execute('UPDATE expenses SET _financial_revision=_financial_revision+1 WHERE business_id=? AND id=?', (self.bid, sid))
        with self.assertRaises(StateError):
            self.expense.execute(self.principal, op.operation_uuid)

    def test_document_evidence_cannot_unlink_delete_or_reclassify_after_capture(self):
        for service in (self.supplier, self.expense):
            doc = self.document()
            self.confirm(service, document_id=doc)
            before = self.state()
            field = 'received_invoice_id' if service == self.supplier else 'expense_id'
            for sql in (f'UPDATE documents SET {field}=NULL WHERE business_id=? AND id=?',
                        'DELETE FROM documents WHERE business_id=? AND id=?',
                        "UPDATE document_classifications SET confirmed_kind='otro' WHERE business_id=? AND document_id=?",
                        'DELETE FROM document_classifications WHERE business_id=? AND document_id=?'):
                with self.assertRaises(Exception):
                    with db.get_conn() as conn:
                        conn.execute(sql, (self.bid, doc))
                self.assertEqual(before, self.state())

    def test_no_secondary_connection_or_public_money_normalization(self):
        doc = self.document()
        with db.get_conn() as conn:
            conn.execute('UPDATE documents SET ocr_amount=12.10 WHERE business_id=? AND id=?', (self.bid, doc))
        req = self.supplier.review_confirm(self.principal, document_id=doc, total='121', supplier_name='Proveedor')
        op = self.approved(self.supplier, req)
        original = self.supplier._validate
        def validate(session, request, principal):
            # El propietario ya abrió TX; prohibir otra conexión durante validación/writer/evento.
            with patch.object(db, 'get_conn', side_effect=AssertionError('Segunda conexión')):
                return original(session, request, principal)
        original_normalizer = db._normalise_value
        def normalize(value):
            if isinstance(value, (float, Decimal)):
                raise AssertionError('Normalización monetaria pública')
            return original_normalizer(value)
        with patch.object(self.supplier, '_validate', side_effect=validate), patch.object(db, '_normalise_value', side_effect=normalize):
            result = self.supplier.execute(self.principal, op.operation_uuid)
        self.assertEqual(self.event(result).amount, Decimal('121'))

    def test_pending_correction_reservation_cannot_commit_without_new_event(self):
        result = self.confirm()
        req = self.supplier.review_correct(self.principal, result.result['source_id'], reason='Importe', total='122')
        op = self.approved(self.supplier, req)
        before = self.state()
        with self.assertRaises(Exception):
            with db.get_conn() as conn:
                conn.execute('BEGIN IMMEDIATE')
                session = FinancialSession(conn)
                self.supplier._reserve(session, op.operation_uuid, req, req.target_id, req.expected_revision+1,
                                       EventType.SUPPLIER_INVOICE_CORRECTED)
                conn.execute('UPDATE received_invoices SET total=122 WHERE business_id=? AND id=?', (self.bid, req.target_id))
                # Aunque el llamador se trague un error de append, FK/commit impiden la mutación parcial.
        self.assertEqual(before, self.state())

    def test_explicit_quota_is_exact_storage_not_binary_or_rounding(self):
        result = self.confirm(self.expense, vat_amount='2.10')
        stored = self.state()['expenses'][0]['_captured_vat_amount']
        self.assertNotIsInstance(stored, float)
        self.assertEqual(Decimal(str(stored)), Decimal('2.10'))
        with self.assertRaises(Exception):
            with db.get_conn() as conn:
                conn.execute("INSERT INTO expenses(business_id,concept,amount,created_at,_captured_vat_amount) VALUES (?,'Inválido',10,?,'2.675')",
                             (self.bid, db._now()))
        self.assertEqual(self.event(result).payload['vat_amount'], Decimal('2.10'))

    def test_multi_business_coverage_and_real_authorization_and_prior_event_rejected(self):
        other = db.create_business('Ajeno', uuid4().hex+'@example.test')
        db.set_trial(other['id'], days=14)
        user = db.create_user(uuid4().hex+'@example.test', 'hash', other['id'])
        from noesis.financial_operations.contracts import Principal
        principal = Principal(user['id'], 0)
        service = SupplierInvoiceCapture(other['id'])
        req = service.review_confirm(principal, total='10')
        op = service.prepare(principal, EntryIdentity.web_api(uuid4()), req)
        op = service.authorize(principal, op.operation_uuid, channel='web_api', approved_hash=req.request_hash, approved_revision=None)
        foreign = service.execute(principal, op.operation_uuid)
        result = self.confirm()
        request = self.supplier.review_void(self.principal, result.result['source_id'], reason='Motivo')
        with self.assertRaises(StateError):
            self.approved(self.supplier, replace(request, parameters=dict(request.parameters)|{'antecedent':foreign.result['event_uuid']}))
        with self.assertRaises(AccessDenied):
            with db.get_conn() as conn:
                EconomicEvents(FinancialSession(conn), self.bid).read(self.principal, foreign.result['event_uuid'])
        own = self.approved(self.supplier, self.supplier.review_confirm(self.principal, total='10'))
        with self.assertRaises(Exception):
            with db.get_conn() as conn:
                conn.execute('UPDATE financial_operations SET authorization_uuid=? WHERE business_id=? AND operation_uuid=?',
                             (op.authorization_uuid, self.bid, own.operation_uuid))
        with self.assertRaises(Exception):
            with db.get_conn() as conn:
                conn.execute("INSERT INTO supplier_invoice_economic_coverage(business_id,source_id,source_revision,operation_uuid,event_uuid,event_type) VALUES (?,?,1,?,?,'supplier_invoice.confirmed')",
                             (self.bid,foreign.result['source_id'],own.operation_uuid,str(uuid4())))

    def test_project_readers_exclude_void_expense_keep_audit_counts(self):
        project = db.add_project('Obra', 1000, business_id=self.bid)
        result = self.confirm(self.expense, project_id=project['id'])
        self.assertEqual(db.get_project(project['id'], self.bid)['expense_cost'], 12.10)
        self.void(self.expense, result)
        workspace = db.get_project(project['id'], self.bid)
        self.assertEqual(workspace['expense_cost'], 0)
        self.assertEqual(workspace['expenses'], [])
        self.assertEqual(db.list_projects(self.bid)[0]['expense_cost'], 0)
