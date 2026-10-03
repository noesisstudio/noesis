"""Cobro, importación, conciliación y fallos reales en ambos motores."""

from dataclasses import replace
from datetime import date
from decimal import Decimal, localcontext
from unittest.mock import patch
from types import SimpleNamespace
from uuid import uuid4

from noesis import banking, config, db, migrations
from noesis.bank_capture.service import BankCapture
from noesis.core.persistence import FinancialSession
from noesis.economic_events.contracts import CATALOG, EventType, FutureImpact
from noesis.economic_events.service import EconomicEvents
from noesis.financial_operations.contracts import AccessDenied, ConflictError, EntryIdentity, StateError
from noesis.financial_operations.repository import OperationsRepository
from noesis.financial_writers import payments
from noesis.financial_writers.boundary import WriterConnection
from noesis.payment_capture.service import PaymentCapture, reserve_payment
from tests.invoice_capture_contract import InvoiceCaptureContract

TABLES = ('invoice_payments','invoice_events','invoices','bank_transactions','bank_payment_links',
    'payment_economic_coverage','bank_import_coverage','bank_match_coverage','economic_events',
    'economic_event_links','economic_event_sequences','financial_operations','financial_authorizations')


class PaymentBankCaptureContract:
    seed = InvoiceCaptureContract.seed
    draft = InvoiceCaptureContract.draft
    approve = InvoiceCaptureContract.approve
    captured = InvoiceCaptureContract.captured
    migration_scope = InvoiceCaptureContract.migration_scope

    def setup_capture(self):
        InvoiceCaptureContract.setup_capture(self)
        self.pay = PaymentCapture(self.bid)
        self.bank = BankCapture(self.bid)

    def invoice(self):
        return self.captured().result['invoice_id']

    def approved(self, service, request, identity=None):
        if identity is None:
            identity = (EntryIdentity.imported(request.parameters['batch'], request.parameters['row'])
                        if request.command_type.value == 'bank_transaction.import' else EntryIdentity.web_api(uuid4()))
        op = service.prepare(self.principal, identity, request)
        return service.authorize(self.principal, op.operation_uuid, channel=identity.namespace,
            approved_hash=request.request_hash, approved_revision=request.expected_revision)

    def payment(self, iid, amount='10.00', **kwargs):
        op = self.approved(self.pay, self.pay.review(self.principal, iid, amount=amount, **kwargs))
        return self.pay.execute(self.principal, op.operation_uuid)

    def imported(self, amount='10.00', **kwargs):
        args = dict(batch_uuid=uuid4(), row_key='1', account_scope='account-a', statement_hash=uuid4().hex * 2,
                    booked_on=date.today().isoformat(), amount=amount)
        args.update(kwargs)
        op = self.approved(self.bank, self.bank.review_import(self.principal, **args))
        return self.bank.execute(self.principal, op.operation_uuid)

    def match_operation(self):
        iid = self.invoice()
        imported = self.imported('20.00', reference=uuid4().hex)
        tid = imported.result['bank_transaction_id']
        db.suggest_bank_transaction(tid, self.bid, iid)
        op = self.approved(self.bank, self.bank.review_match(self.principal, tid))
        return iid, tid, imported, op

    def test_delete_legacy_payment_and_captured_guards_after_fresh_install(self):
        self.assertEqual(migrations.current_version(), migrations.LATEST_VERSION)
        legacy = db.issue_invoice(self.draft()['id'], self.bid)
        payment = db.add_invoice_payment(legacy['id'], '1.00', business_id=self.bid)
        with db.get_conn() as conn:
            removed = conn.execute('DELETE FROM invoice_payments WHERE business_id=? AND id=? RETURNING id',
                                   (self.bid, payment['id'])).fetchone()
            self.assertEqual(removed['id'], payment['id'])
        done = self.payment(self.invoice())
        before = self.state()
        for sql in ('DELETE FROM invoice_payments WHERE business_id=? AND id=?',
                    "UPDATE invoice_payments SET amount=11 WHERE business_id=? AND id=?"):
            with self.assertRaises(Exception), db.get_conn() as conn:
                conn.execute(sql, (self.bid, done.result['payment_id']))
        self.assertEqual(self.state(), before)

    def test_migration_69_repairs_existing_68_without_changing_evidence(self):
        with self.migration_scope():
            done = self.payment(self.invoice())
            before = self.state()
            migrations.downgrade(68)
            with db.get_conn() as conn:
                if conn.dialect == 'postgres':
                    # Reproduce exactamente la función instalada por el antiguo 66.
                    conn.execute("CREATE OR REPLACE FUNCTION cash_payment_delete() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF EXISTS(SELECT 1 FROM payment_economic_coverage c WHERE c.business_id=OLD.business_id AND c.payment_id=OLD.id) THEN RAISE EXCEPTION 'Cobertura de cobro/banco incoherente' USING ERRCODE='23514'; END IF; RETURN NEW; END $$")
            self.assertEqual(migrations.upgrade(69), 69)
            self.assertEqual(self.state(), before)
            legacy = db.issue_invoice(self.draft()['id'], self.bid)
            payment = db.add_invoice_payment(legacy['id'], '1.00', business_id=self.bid)
            with db.get_conn() as conn:
                deleted = conn.execute('DELETE FROM invoice_payments WHERE business_id=? AND id=? RETURNING id',
                                       (self.bid, payment['id'])).fetchone()
                self.assertEqual(deleted['id'], payment['id'])
            for sql in ('DELETE FROM invoice_payments WHERE business_id=? AND id=?',
                        "UPDATE invoice_payments SET amount=11 WHERE business_id=? AND id=?"):
                with self.assertRaises(Exception), db.get_conn() as conn:
                    conn.execute(sql, (self.bid, done.result['payment_id']))
            self.assertEqual(self.state()['payment_economic_coverage'], before['payment_economic_coverage'])

    def state(self):
        with db.get_conn() as conn:
            return {t: [dict(r) for r in conn.execute(f'SELECT * FROM {t} WHERE business_id=? ORDER BY 1,2',
                                                     (self.bid,)).fetchall()] for t in TABLES}

    def event(self, uuid):
        with db.get_conn() as conn:
            return EconomicEvents(FinancialSession(conn), self.bid).read(self.principal, uuid).event

    def test_partial_ten_several_and_exact_actual_source(self):
        iid = self.invoice()
        for amount in ('10.00','10.00','100.00','1.00'):
            result = self.payment(iid, amount, method='transferencia', paid_at='2026-10-01T09:12:34')
            event = self.event(result.result['event_uuid'])
            self.assertEqual(event.amount, Decimal(amount))
            self.assertEqual(event.payload_version, 1)
            self.assertEqual(event.payload['received_on'], '2026-10-01')
            self.assertEqual(event.payload['method'], 'transferencia')
            self.assertEqual(event.source_id, result.result['payment_id'])
            self.assertEqual(event.relations[0].kind.value, 'settles')
            self.assertIn('legacy_binary_storage', self.state()['economic_events'][-1]['provenance'])
        state = self.state()
        self.assertEqual(len(state['invoice_payments']), 4)
        self.assertEqual(len(state['payment_economic_coverage']), 4)
        self.assertEqual(db.get_invoice(iid, self.bid)['status'], 'cobrada')

    def test_full_remaining_frozen_and_complete(self):
        for mode in ('full','remaining'):
            iid = self.invoice()
            self.payment(iid, '21.00')
            req = self.pay.review(self.principal, iid, mode=mode)
            self.assertEqual(req.amount, Decimal('100.00'))
            op = self.approved(self.pay, req)
            done = self.pay.execute(self.principal, op.operation_uuid)
            self.assertEqual(self.event(done.result['event_uuid']).amount, Decimal('100.00'))
            self.assertEqual(db.get_invoice(iid, self.bid)['status'], 'cobrada')

    def test_full_stale_after_intervening_equal_payment(self):
        iid = self.invoice()
        op = self.approved(self.pay, self.pay.review(self.principal, iid, mode='full'))
        self.payment(iid)
        before = self.state()
        with self.assertRaises(StateError):
            self.pay.execute(self.principal, op.operation_uuid)
        self.assertEqual(self.state(), before)

    def test_partial_capacity_allows_distinct_equal_approved_operations(self):
        iid = self.invoice()
        ops = [self.approved(self.pay, self.pay.review(self.principal, iid, amount='10.00')) for _ in range(2)]
        for op in ops:
            self.pay.execute(self.principal, op.operation_uuid)
        self.assertEqual(len(self.state()['invoice_payments']), 2)
        stale = self.approved(self.pay, self.pay.review(self.principal, iid, amount='100.00'))
        self.payment(iid, '10.00')
        before = self.state()
        with self.assertRaises(StateError):
            self.pay.execute(self.principal, stale.operation_uuid)
        self.assertEqual(self.state(), before)

    def test_invalid_amounts_dates_methods_currency_no_effect(self):
        iid = self.invoice()
        before = self.state()
        for amount in ('0','-1','122','0.001','NaN','Infinity',10.0,True):
            with self.subTest(amount=amount), self.assertRaises((ValueError,TypeError,StateError)):
                self.pay.review(self.principal, iid, amount=amount)
        for kwargs in ({'method': 4}, {'method':'x'*51}, {'paid_at':'2026-02-30'}, {'paid_at':'bad'},
                       {'paid_at':'2026-10-01T00:00:00+02:00'}, {'note': 'x'*501}):
            with self.subTest(kwargs=kwargs), self.assertRaises((ValueError,TypeError)):
                self.pay.review(self.principal, iid, amount='10', **kwargs)
        req = self.pay.review(self.principal, iid, amount='10')
        with self.assertRaises(ValueError):
            replace(req, currency='USD')
        self.assertEqual(self.state(), before)

    def test_low_decimal_context_does_not_round_approved_amount(self):
        iid = self.invoice()
        with localcontext() as ctx:
            ctx.prec = 2
            done = self.payment(iid, '100.01')
        self.assertEqual(self.event(done.result['event_uuid']).amount, Decimal('100.01'))

    def test_uncaptured_invoice_no_history_and_rectified_settles(self):
        legacy = db.issue_invoice(self.draft()['id'], self.bid)
        before = self.state()
        with self.assertRaises(StateError):
            self.pay.review(self.principal, legacy['id'], amount='10')
        self.assertEqual(self.state(), before)
        parent = self.invoice()
        rect = db.create_rectifying_invoice(parent, self.bid, concept='Ajuste', base='10', reason='Diferencia')
        issued = self.capture.execute(self.principal, self.approve(rect['id']).operation_uuid)
        result = self.payment(rect['id'], '1')
        relation = self.event(result.result['event_uuid']).relations[0]
        self.assertEqual(relation.target_event_type, EventType.INVOICE_RECTIFIED)
        self.assertEqual(str(relation.target_event_id), issued.result['event_uuid'])

    def test_payment_replay_double_click_timeout_identity_conflict(self):
        iid = self.invoice()
        identity = EntryIdentity.web_api(uuid4())
        req = self.pay.review(self.principal, iid, amount='10')
        op = self.approved(self.pay, req, identity)
        done = self.pay.execute(self.principal, op.operation_uuid)
        before = self.state()
        self.assertEqual(self.pay.execute(self.principal, op.operation_uuid), done)
        self.assertEqual(self.pay.prepare(self.principal, identity, req), done)
        with self.assertRaises(ConflictError):
            self.pay.prepare(self.principal, identity, replace(req, amount='11'))
        self.assertEqual(self.state(), before)

    def test_import_positive_negative_and_no_supplier_inference(self):
        for amount in ('10.01','-10.01'):
            done = self.imported(amount)
            event = self.event(done.result['event_uuid'])
            self.assertEqual(event.amount, Decimal(amount))
            self.assertEqual(event.payload_version, 1)
        self.assertFalse(self.state()['invoice_payments'])
        self.assertEqual(len(self.state()['bank_transactions']), 2)
        self.assertEqual(len(self.state()['bank_import_coverage']), 2)
        with self.assertRaises(StateError):
            self.bank.review_match(self.principal, done.result['bank_transaction_id'])

    def test_import_invalid_zero_float_fraction_date_and_unknown_currency(self):
        before = self.state()
        for amount in ('0','0.001','-0.001',1.0,'NaN'):
            with self.assertRaises((ValueError,TypeError)):
                self.bank.review_import(self.principal, batch_uuid=uuid4(), row_key='1', account_scope='a',
                    statement_hash='a'*64, booked_on=date.today().isoformat(), amount=amount)
        with self.assertRaises(ValueError):
            self.imported(booked_on='2026-02-30')
        self.assertEqual(self.state(), before)

    def test_import_csv_retry_identical_rows_different_identities(self):
        content = b'fecha;importe;concepto\n01/10/2026;10,00;igual\n01/10/2026;10,00;igual\n'
        batch = uuid4()
        pairs = self.bank.review_csv(self.principal, content, batch_uuid=batch, account_scope='account-a')
        done = [self.bank.execute(self.principal, self.approved(self.bank, req, ident).operation_uuid) for ident,req in pairs]
        self.assertNotEqual(done[0].result['bank_transaction_id'], done[1].result['bank_transaction_id'])
        before = self.state()
        for (identity, req), expected in zip(pairs, done, strict=True):
            self.assertEqual(self.bank.prepare(self.principal, identity, req), expected)
            self.assertEqual(self.bank.execute(self.principal, expected.operation_uuid), expected)
        self.assertEqual(self.state(), before)
        class NextDay(date):
            @classmethod
            def today(cls):
                return cls(2026,10,3)
        with patch('noesis.bank_capture.service.date',NextDay):
            repeated = self.bank.review_csv(self.principal,content,batch_uuid=batch,account_scope='account-a')
            for (identity,req),expected in zip(repeated,done,strict=True):
                self.assertEqual(self.bank.prepare(self.principal,identity,req),expected)
        for bad in (b'fecha;importe\n01/10/2026;1,001\n', b'fecha;importe\n01/10/2026;abc10\n',
                    b'fecha valor;importe\n01/10/2026;10,00\n'):
            with self.assertRaises(ValueError):
                self.bank.review_csv(self.principal, bad, batch_uuid=uuid4(), account_scope='a')

    def test_import_cross_statement_ambiguity_human_resolution_different_accounts(self):
        self.imported('10', description='igual')
        before = self.state()
        with self.assertRaisesRegex(StateError, 'ambiguo'):
            self.imported('10', description='igual')
        self.assertEqual(self.state(), before)
        done = self.imported('10', description='igual', distinct_reason='Dos abonos legítimos según titular')
        self.assertEqual(len(done.request.parameters['ambiguity_candidates']), 1)
        self.imported('10', description='igual', account_scope='account-b')
        self.assertEqual(len(self.state()['bank_transactions']), 3)

    def test_import_batch_account_and_file_binding(self):
        batch = uuid4()
        self.imported(batch_uuid=batch, statement_hash='a'*64)
        before = self.state()
        for kwargs in ({'account_scope':'other','statement_hash':'a'*64}, {'statement_hash':'b'*64}):
            with self.assertRaises(StateError):
                self.imported(batch_uuid=batch, row_key='2', **kwargs)
        self.assertEqual(self.state(), before)

    def test_import_ambiguity_changes_before_execute_stale(self):
        req = self.bank.review_import(self.principal, batch_uuid=uuid4(), row_key='1', account_scope='account-a',
            statement_hash='a'*64, booked_on=date.today().isoformat(), amount='10')
        op = self.approved(self.bank, req)
        self.imported('10')
        before = self.state()
        with self.assertRaises(StateError):
            self.bank.execute(self.principal, op.operation_uuid)
        self.assertEqual(self.state(), before)

    def test_match_two_events_one_payment_durable_links_and_later_revision(self):
        iid, tid, imported, op = self.match_operation()
        imported_before = self.event(imported.result['event_uuid'])
        done = self.bank.execute(self.principal, op.operation_uuid)
        payment, match = self.event(done.result['event_uuid']), self.event(done.result['match_event_uuid'])
        self.assertEqual(payment.source_id, done.result['payment_id'])
        self.assertEqual(payment.amount, Decimal('20'))
        self.assertEqual(match.amount, payment.amount)
        self.assertEqual({r.kind.value:str(r.target_event_id) for r in match.relations},
                         {'matches': done.result['event_uuid'], 'evidence_for': imported.result['event_uuid']})
        self.assertEqual(match.payload['invoice_payment_id'], payment.source_id)
        state = self.state()
        self.assertEqual(len(state['invoice_payments']), 1)
        self.assertEqual(state['bank_payment_links'][0]['payment_id'], payment.source_id)
        self.assertEqual(state['bank_payment_links'][0]['bank_transaction_id'], tid)
        self.assertEqual(db.get_invoice(iid, self.bid)['status'], 'parcial')
        self.assertGreater(match.source_revision, imported_before.source_revision)
        self.assertEqual(self.event(imported.result['event_uuid']), imported_before)

    def test_semantics_cash_only_once_no_consumer(self):
        self.assertEqual(CATALOG[EventType.BANK_TRANSACTION_MATCHED].future_impacts, (FutureImpact.EVIDENCE,))
        self.assertNotIn(FutureImpact.GL, CATALOG[EventType.BANK_TRANSACTION_IMPORTED].future_impacts)
        self.assertIn(FutureImpact.GL, CATALOG[EventType.CUSTOMER_PAYMENT_RECEIVED].future_impacts)

    def test_match_replay_other_operation_conflict_and_legacy_fail_closed(self):
        _, tid, _, op = self.match_operation()
        other = self.approved(self.bank, op.request)
        done = self.bank.execute(self.principal, op.operation_uuid)
        before = self.state()
        self.assertEqual(self.bank.execute(self.principal, op.operation_uuid), done)
        with self.assertRaises(StateError):
            self.bank.execute(self.principal, other.operation_uuid)
        self.assertEqual(self.state(), before)
        legacy = db.add_bank_transaction(self.bid, import_hash=uuid4().hex*2,
            booked_on=date.today().isoformat(), amount=10)
        db.suggest_bank_transaction(legacy['id'], self.bid, self.invoice())
        before = self.state()
        with self.assertRaises(StateError):
            self.bank.review_match(self.principal, legacy['id'])
        self.assertEqual(self.state(), before)
        self.assertEqual(db.get_bank_transaction(tid, self.bid)['status'], 'confirmed')

    def test_match_revision_changed_stale(self):
        iid, tid, _, op = self.match_operation()
        db.suggest_bank_transaction(tid, self.bid, iid, reason='Otra revisión')
        before = self.state()
        with self.assertRaises(StateError):
            self.bank.execute(self.principal, op.operation_uuid)
        self.assertEqual(self.state(), before)

    def test_eight_match_failures_full_rollback_and_retry(self):
        original_execute = WriterConnection.execute
        real_append, real_transition = EconomicEvents.append, OperationsRepository.transition
        def sql_failure(fragment):
            def execute(proxy, sql, params=()):
                result = original_execute(proxy, sql, params)
                if fragment in sql:
                    raise RuntimeError('Fallo inyectado')
                return result
            return execute
        def after(fn):
            def fail(*args, **kwargs):
                fn(*args, **kwargs)
                raise RuntimeError('Fallo inyectado')
            return fail
        def event_failure(typ):
            def append(service, principal, event, **kwargs):
                result = real_append(service, principal, event, **kwargs)
                if event.event_type == typ:
                    raise RuntimeError('Fallo inyectado')
                return result
            return append
        injections = [patch.object(WriterConnection,'execute',sql_failure('SELECT * FROM bank_transactions WHERE id=?')),
            patch.object(db,'_insert_invoice_payment',after(db._insert_invoice_payment)),
            patch.object(db,'_set_invoice_payment_state',after(db._set_invoice_payment_state)),
            patch.object(WriterConnection,'execute',sql_failure("UPDATE bank_transactions SET status='confirmed'")),
            patch.object(WriterConnection,'execute',sql_failure('INSERT INTO bank_payment_links')),
            patch.object(EconomicEvents,'append',event_failure(EventType.CUSTOMER_PAYMENT_RECEIVED)),
            patch.object(EconomicEvents,'append',event_failure(EventType.BANK_TRANSACTION_MATCHED)),
            patch.object(OperationsRepository,'transition',after(real_transition))]
        for injection in injections:
            _, _, _, op = self.match_operation()
            before = self.state()
            with injection, self.assertRaisesRegex(RuntimeError,'inyectado'):
                self.bank.execute(self.principal, op.operation_uuid)
            self.assertEqual(self.state(), before)
            self.bank.execute(self.principal, op.operation_uuid)

    def test_manual_failures_payment_invoice_legacy_event_ee_result(self):
        def after(fn):
            def fail(*args, **kwargs):
                fn(*args, **kwargs)
                raise RuntimeError('Fallo inyectado')
            return fail
        for obj, name in ((db,'_insert_invoice_payment'),(db,'_set_invoice_payment_state'),
                          (db,'_record_invoice_event'),(EconomicEvents,'append'),(OperationsRepository,'transition')):
            op = self.approved(self.pay, self.pay.review(self.principal, self.invoice(), amount='10'))
            before = self.state()
            with patch.object(obj,name,after(getattr(obj,name))), self.assertRaises(RuntimeError):
                self.pay.execute(self.principal, op.operation_uuid)
            self.assertEqual(self.state(), before)

    def test_import_failure_after_row_before_event_rollback(self):
        req = self.bank.review_import(self.principal, batch_uuid=uuid4(), row_key='1', account_scope='a',
            statement_hash='a'*64, booked_on=date.today().isoformat(), amount='-10')
        op = self.approved(self.bank, req)
        before = self.state()
        with patch.object(EconomicEvents,'append',side_effect=RuntimeError('Fallo inyectado')), self.assertRaises(RuntimeError):
            self.bank.execute(self.principal, op.operation_uuid)
        self.assertEqual(self.state(), before)
        self.bank.execute(self.principal, op.operation_uuid)

    def test_structural_missing_event_and_unreserved_executor_cannot_commit(self):
        iid = self.invoice()
        op = self.approved(self.pay, self.pay.review(self.principal, iid, amount='10'))
        before = self.state()
        with self.assertRaises(db.IntegrityError):
            with self.pay.operations._transaction(self.principal) as (session, _):
                reserve_payment(session, self.bid, op.operation_uuid, iid, op.request.parameters['invoice_event'])
                payments.add_invoice_payment(session,iid,op.request.amount,business_id=self.bid)
                # Aunque el llamador capture un error, COMMIT de la reserva sin evento falla por FK.
        self.assertEqual(self.state(), before)
        def bypass(session, request):
            payments.add_invoice_payment(session,iid,request.amount,business_id=self.bid)
            return {'captured':True, 'currency':'EUR'}
        with self.assertRaises(db.IntegrityError):
            self.pay.operations.execute(self.principal,op.operation_uuid,bypass,revision_reader=lambda s,r:r.expected_revision)
        self.assertEqual(self.state(), before)

    def test_each_required_event_omitted_cannot_commit(self):
        real_append = EconomicEvents.append
        for typ in (EventType.CUSTOMER_PAYMENT_RECEIVED,EventType.BANK_TRANSACTION_IMPORTED,EventType.BANK_TRANSACTION_MATCHED):
            if typ == EventType.CUSTOMER_PAYMENT_RECEIVED:
                service = self.pay
                op = self.approved(service,service.review(self.principal,self.invoice(),amount='10'))
            elif typ == EventType.BANK_TRANSACTION_MATCHED:
                service = self.bank
                _,_,_,op = self.match_operation()
            else:
                service = self.bank
                req = service.review_import(self.principal,batch_uuid=uuid4(),row_key='1',account_scope='a',
                    statement_hash='a'*64,booked_on=date.today().isoformat(),amount='-10')
                op = self.approved(service,req)
            def omit(events,principal,event,**kwargs):
                if event.event_type == typ:
                    return SimpleNamespace(event=event)
                return real_append(events,principal,event,**kwargs)
            before = self.state()
            with patch.object(EconomicEvents,'append',omit), self.assertRaises(db.IntegrityError):
                service.execute(self.principal,op.operation_uuid)
            self.assertEqual(self.state(),before)

    def test_captured_import_cannot_be_confirmed_through_legacy(self):
        _,tid,_,_ = self.match_operation()
        before = self.state()
        with self.assertRaises(db.IntegrityError):
            db.confirm_bank_transaction(tid,self.bid)
        self.assertEqual(self.state(),before)

    def test_full_amount_cannot_be_mutated_and_approved_as_remaining(self):
        req = self.pay.review(self.principal,self.invoice(),mode='full')
        before = self.state()
        with self.assertRaises(StateError):
            self.approved(self.pay,replace(req,amount='10'))
        self.assertEqual(self.state(),before)

    def test_no_public_float_normalisation_in_capture(self):
        iid = self.invoice()
        op = self.approved(self.pay,self.pay.review(self.principal,iid,amount='10.01'))
        with patch.object(db,'_normalise_row',side_effect=AssertionError('Normalización pública usada')):
            # La observación legacy, si está habilitada, es posterior al commit y best effort.
            done = self.pay.execute(self.principal,op.operation_uuid)
        self.assertEqual(self.event(done.result['event_uuid']).amount,Decimal('10.01'))

    def test_immutable_sources_link_coverage_and_cross_tenant(self):
        _, tid, _, op = self.match_operation()
        done = self.bank.execute(self.principal, op.operation_uuid)
        before = self.state()
        for sql in ("UPDATE bank_payment_links SET payment_id=payment_id WHERE business_id=?",
                    "DELETE FROM bank_payment_links WHERE business_id=?",
                    "UPDATE payment_economic_coverage SET source_fingerprint='bad' WHERE business_id=?",
                    "UPDATE invoice_payments SET amount=1 WHERE business_id=?",
                    "UPDATE bank_transactions SET amount=1 WHERE business_id=?",
                    "UPDATE bank_transactions SET status='imported' WHERE business_id=?"):
            with self.assertRaises(Exception), db.get_conn() as conn:
                conn.execute(sql,(self.bid,))
        self.assertEqual(self.state(), before)
        other = db.create_business('Otro',uuid4().hex+'@example.test')['id']
        with self.assertRaises(Exception), db.get_conn() as conn:
            conn.execute('INSERT INTO bank_payment_links(business_id,bank_transaction_id,payment_id) VALUES (?,?,?)',
                         (other,tid,done.result['payment_id']))
        with self.assertRaises(AccessDenied):
            PaymentCapture(other).review(self.principal,done.result['invoice_id'],amount='1')

    def test_no_authority_or_capture_fallback_and_flags_off(self):
        iid = self.invoice()
        with self.assertRaises(AccessDenied):
            self.pay.review(None,iid,amount='10')
        calls = [lambda: db.add_invoice_payment(iid,'10',business_id=self.bid,capture_requested=True),
                 lambda: db.mark_invoice_paid(iid,self.bid,capture_requested=True),
                 lambda: db.confirm_bank_transaction(1,self.bid,capture_requested=True),
                 lambda: banking.import_csv(self.bid,b'',capture_requested=True),
                 lambda: db.add_bank_transaction(self.bid,import_hash='a'*64,booked_on=date.today().isoformat(),amount=10,capture_requested=True)]
        before = self.state()
        for call in calls:
            with self.assertRaises(StateError):
                call()
        self.assertEqual(self.state(), before)
        self.assertFalse(config.FINANCIAL_CORE_ENABLED)

    def test_downgrade_empty_then_blocked_with_evidence(self):
        with self.migration_scope():
            migrations.downgrade(65)
            migrations.upgrade()
            self.payment(self.invoice())
            before = self.state()
            with self.assertRaises(ValueError):
                migrations.downgrade(65)
            self.assertEqual(migrations.current_version(),migrations.LATEST_VERSION)
            self.assertEqual(self.state(),before)

    def test_legacy_confirmation_preserves_response_and_real_link(self):
        iid = db.issue_invoice(self.draft()['id'],self.bid)['id']
        tid = db.add_bank_transaction(self.bid,import_hash=uuid4().hex*2,
                                     booked_on=date.today().isoformat(),amount=10)['id']
        db.suggest_bank_transaction(tid,self.bid,iid)
        result = db.confirm_bank_transaction(tid,self.bid)
        self.assertEqual(result['status'],'confirmed')
        self.assertNotIn('confirmed_payment_id',result)
        self.assertIsInstance(result['amount'],float)
        before = self.state()
        replay = db.confirm_bank_transaction(tid,self.bid)
        self.assertEqual(replay,{k:v for k,v in result.items() if k not in {'invoice_number','invoice_total','client_name'}})
        self.assertEqual(self.state(),before)
        self.assertEqual(len(before['bank_payment_links']),1)
        self.assertFalse(before['economic_events'])
