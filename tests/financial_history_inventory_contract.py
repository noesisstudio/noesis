"""Fixtures sintéticos compartidos SQLite/PG, sin datos ni conexiones productivas."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import struct
import tempfile
from unittest.mock import patch
from uuid import uuid4

from noesis import config, db, migrations
from noesis.core.persistence import FinancialSession
from noesis.economic_events.contracts import EventType
from noesis.financial_history.classifier import (
    DiagnosticContext, classify, fact_slots, item_uuid,
)
from noesis.financial_history.contracts import (
    Classification, DecisionKind, EvidenceReference, EvidenceSource, IncidenceCode, ReasonCode,
)
from noesis.financial_history.raw import observe_money
from noesis.financial_history.readers import RawReader
from noesis.financial_history.repository import HistoryRepository
from noesis.financial_history.service import FLAGS, HistoryDiagnostics
from noesis.financial_history.sources import SOURCES
from noesis.financial_operations.contracts import AccessDenied, ConflictError, Principal
from tests.borrowed_writers_contract import BorrowedWritersContract

NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


class HistoryInventoryContract:
    seed = BorrowedWritersContract.seed
    draft = BorrowedWritersContract.draft
    issued = BorrowedWritersContract.issued
    document = BorrowedWritersContract.document
    movement = BorrowedWritersContract.movement

    def setup_history(self):
        self.seed()
        self.user = db.create_user(uuid4().hex + '@example.test', 'hash fixture', self.bid)
        self.principal = Principal(self.user['id'], 0)
        self.history = HistoryDiagnostics(self.bid, page_size=8)
        flags = patch.multiple(config, **dict.fromkeys(FLAGS, False))
        flags.start()
        self.addCleanup(flags.stop)

    def run_history(self, run=None, **kwargs):
        return self.history.run(self.principal, run or uuid4(), repository_version='fixture-code-v1',
                                environment_identity='synthetic-fixture', **kwargs)

    def items(self, manifest, kind=None):
        with db.get_conn() as connection:
            sql = 'SELECT * FROM financial_history_items WHERE business_id=? AND manifest_uuid=?'
            args = [self.bid, str(manifest['manifest_uuid'])]
            if kind:
                sql += ' AND source_type=?'
                args.append(kind)
            return connection.execute_exact(sql + ' ORDER BY source_type,source_key,fact_slot', tuple(args)).fetchall()

    def codes(self, manifest):
        return set(json.loads(manifest['summary_canonical'])['incidences'])

    def raw(self, kind, source_id):
        with db.get_conn() as connection:
            reader = RawReader(connection, self.bid, page_size=256)
            after = None
            while sources := reader.page(kind, after):
                for source in sources:
                    if source.source_id == str(source_id):
                        return source
                after = sources[-1].key
        raise AssertionError('Source fixture ausente.')

    def exact_source(self, kind, source_id):
        source = self.raw(kind, source_id)
        money = {}
        for key, observation in source.money.items():
            value = observation.evidence
            if value is None or value.binary_decimal is None:
                money[key] = observation
                continue
            # Fixture exacto declarado, NO conversión de datos del reader para el servicio.
            amount = Decimal('121.00') if key == 'total' else Decimal('12.10') if key == 'amount' else Decimal('0.00')
            money[key] = observe_money('sqlite', format(amount,'f'), 'text', format(amount,'f'))
        return replace(source, money=money)

    def unchanged(self):
        tables = sorted({s.table for s in SOURCES.values()} | {'financial_operations','financial_authorizations',
                         'economic_event_sequences','financial_channel_proposals','financial_channel_receipts'})
        with db.get_conn() as connection:
            result = {}
            for table in tables:
                tenant = 'id' if table=='businesses' else 'business_id'
                rows = connection.execute_exact(f'SELECT * FROM {table} WHERE {tenant}=? ORDER BY 1,2', (self.bid,)).fetchall()
                result[table] = repr([dict(row) for row in rows])
        result['flags'] = tuple(getattr(config,f) for f in FLAGS)
        return result

    @contextmanager
    def empty_database(self, target=69):
        if not config.DATABASE_URL:
            with tempfile.TemporaryDirectory() as root, patch.object(config, 'DB_PATH', Path(root)/'empty.db'):
                migrations.upgrade(target)
                yield
        else:
            from urllib.parse import quote
            schema = 'history_empty_' + uuid4().hex
            current = config.DATABASE_URL
            with db.get_conn() as connection:
                connection.execute(f'CREATE SCHEMA {schema}')
            base = current.split('?')[0]
            try:
                with patch.object(config, 'DATABASE_URL', base + '?options=' + quote('-csearch_path=' + schema)):
                    migrations.upgrade(target)
                    yield
            finally:
                db.close_pool()
                with db.get_conn() as connection:
                    connection.execute(f'DROP SCHEMA {schema} CASCADE')
                db.close_pool()

    def test_migration_clean_69_70_empty_downgrade_reupgrade(self):
        for initial in (0, 69):
            with self.subTest(initial=initial), self.empty_database(initial):
                self.assertEqual(migrations.upgrade(70), 70)
                self.assertEqual(migrations.downgrade(69), 69)
                self.assertEqual(migrations.upgrade(70), 70)
                if not config.DATABASE_URL:
                    self.assertEqual(migrations.downgrade(0), 0)
                    self.assertEqual(migrations.upgrade(70), 70)

    def test_downgrade_evidence_keeps_62_70(self):
        self.run_history()
        before = self.unchanged()
        with self.assertRaisesRegex(ValueError, 'evidencia'):
            db.delete_business_cascade(self.bid)
        self.assertEqual(before,self.unchanged())
        with self.assertRaisesRegex(ValueError, 'evidencia'):
            migrations.downgrade(69)
        self.assertEqual(migrations.current_version(), migrations.LATEST_VERSION)
        with db.get_conn() as connection:
            self.assertEqual([r['version'] for r in connection.execute('SELECT version FROM schema_migrations WHERE version>=62 ORDER BY version').fetchall()], list(range(62,migrations.LATEST_VERSION+1)))

    def test_empty_and_draft_are_review_only_not_importable(self):
        self.draft()
        manifest = self.run_history()
        self.assertEqual(manifest['status'], 'frozen')
        self.assertEqual(manifest['result'], 'READY_FOR_REVIEW')
        self.assertFalse(manifest['eligible_for_import'])
        self.assertFalse(manifest['certifiable'])
        invoice = self.items(manifest, 'invoice')[0]
        self.assertEqual(invoice['disposition'], 'out_of_scope')
        self.assertNotEqual(invoice['classification'], 'D')

    def test_legacy_invoice_raw_line_profile_absent_fiscal(self):
        invoice = self.issued()
        manifest = self.run_history()
        self.assertEqual(manifest['result'], 'BLOCKED')
        self.assertTrue({'SOURCE_HISTORY_LOST','MIGRATED_DOCUMENT_PROFILE','MONEY_BINARY_UNCORROBORATED'} <= self.codes(manifest))
        self.assertEqual(len(self.items(manifest,'invoice')), 1)
        self.assertIsNone(self.items(manifest,'invoice')[0]['candidate_hash'])
        raw = self.raw('invoice_line', db.get_invoice_lines(invoice['id'],self.bid)[0]['id'])
        self.assertEqual(raw.provenance['source_origin'], 'unknown')

    def test_fiscal_mismatch_and_paid_without_payment(self):
        db.update_verifactu_mode(self.bid,True)
        invoice = self.issued()
        with db.get_conn() as connection:
            # Datos inconsistentes sintéticos sin tocar guards: fiscal extraño por INSERT.
            row = connection.execute('SELECT id FROM invoice_records WHERE business_id=? AND invoice_id=?', (self.bid,invoice['id'])).fetchone()
            self.assertIsNotNone(row)
            # La factura admite únicamente transición de estado operacional.
            connection.execute("UPDATE invoices SET status='cobrada' WHERE business_id=? AND id=?", (self.bid,invoice['id']))
        raw = self.raw('invoice', invoice['id'])
        record = self.raw('invoice_record', row['id'])
        changed = replace(record, money=dict(record.money) | {'invoice_total':observe_money('sqlite','120.00','text','120.00')})
        result = classify(raw,*fact_slots(raw)[0],DiagnosticContext((changed,)),NOW)
        self.assertIn(IncidenceCode.FISCAL_AMOUNT_MISMATCH,result.incidences)
        self.assertIn(IncidenceCode.PAID_WITHOUT_PAYMENT,result.incidences)

    def test_rectification_missing_and_explicit_parent(self):
        original = self.issued()
        rect = db.create_rectifying_invoice(original['id'],self.bid,concept='Corrección',reason='Corrección',base='10')
        db.issue_invoice(rect['id'],self.bid)
        raw = self.raw('invoice',rect['id'])
        slot,event = fact_slots(raw)[0]
        self.assertEqual(event,EventType.INVOICE_RECTIFIED)
        missing = classify(raw,slot,event,DiagnosticContext(),NOW)
        self.assertIn(IncidenceCode.RECTIFICATION_PARENT_MISSING,missing.incidences)
        found = classify(raw,slot,event,DiagnosticContext((self.raw('invoice',original['id']),)),NOW)
        self.assertNotIn(IncidenceCode.RECTIFICATION_PARENT_MISSING,found.incidences)
        self.assertEqual(found.dependencies[0].target.source.source_id,original['id'])

    def test_payment_real_synthetic_over_duplicate_no_status_invention(self):
        invoice = self.issued()
        first = db.add_invoice_payment(invoice['id'],'10',business_id=self.bid,method='efectivo',paid_at='2026-09-01')
        with db.get_conn() as connection:
            for method,amount in (('efectivo','10'),('registro_anterior','500')):
                connection.execute('INSERT INTO invoice_payments (business_id,invoice_id,amount,method,paid_at,created_at) VALUES (?,?,?,?,?,?)',
                    (self.bid,invoice['id'],amount,method,'2026-09-01','2026-09-01'))
        before = self.unchanged()
        manifest = self.run_history()
        self.assertEqual(before,self.unchanged())
        self.assertTrue({'SYNTHETIC_LEGACY_PAYMENT','PAYMENT_OVER_TOTAL','POSSIBLE_DUPLICATE_PAYMENT'} <= self.codes(manifest))
        self.assertEqual(len(self.items(manifest,'invoice_payment')),3)
        self.assertIsNotNone(first)

    def test_bank_suggestion_and_confirmed_without_link(self):
        invoice = self.issued()
        bank = self.movement(invoice['id'])
        with db.get_conn() as connection:
            connection.execute("UPDATE bank_transactions SET status='confirmed',confirmed_at=? WHERE business_id=? AND id=?",
                               ('2026-09-01',self.bid,bank))
        manifest = self.run_history()
        self.assertEqual({i['fact_slot'] for i in self.items(manifest,'bank_transaction')},{'import','match'})
        self.assertIn('BANK_LINK_AMBIGUOUS',self.codes(manifest))
        self.assertEqual(self.unchanged()['flags'],(False,)*5)

    def test_bank_valid_link_is_explicit_but_dependency_blocked(self):
        invoice = self.issued()
        bank = self.movement(invoice['id'])
        db.confirm_bank_transaction(bank,self.bid)
        manifest = self.run_history()
        match = next(i for i in self.items(manifest,'bank_transaction') if i['fact_slot']=='match')
        self.assertNotIn('BANK_LINK_AMBIGUOUS',self.codes(manifest))
        self.assertEqual(match['terminal_result'],'blocked')
        dependencies = json.loads(match['dependency_canonical'])
        self.assertEqual({d['relation'] for d in dependencies},{'matches','evidence_for'})

    def test_received_observed_revision_three_not_reconstructed_and_unknown_vat(self):
        received = db.add_received_invoice('121',business_id=self.bid,concept='Material')
        raw = self.exact_source('received_invoice',received['id'])
        # Revisión observada; un estado actual consistente no acredita correcciones.
        fields = dict(raw.fields) | {'_financial_revision':3}
        raw = replace(raw,fields=fields)
        result = classify(raw,*fact_slots(raw)[0],DiagnosticContext(),NOW)
        self.assertEqual(result.assessment.classification,Classification.OBSERVED_STATE)
        self.assertEqual(result.terminal_result,'not_durably_supported')
        self.assertIn(IncidenceCode.SOURCE_HISTORY_LOST,result.incidences)
        self.assertIsNone(result.candidate.event_payload.payload['vat_amount'])
        self.assertFalse(result.candidate.importable)
        self.assertEqual(result.candidate.event_payload.payload['confirmed_on'],None)

    def test_expense_observed_and_subcent(self):
        expense = db.add_expense('Material','12.10',business_id=self.bid,spent_on='2026-09-01')
        raw = self.exact_source('expense',expense['id'])
        valid = classify(raw,*fact_slots(raw)[0],DiagnosticContext(),NOW)
        self.assertEqual(valid.assessment.classification,Classification.OBSERVED_STATE)
        self.assertIsNotNone(valid.candidate)
        invalid = replace(raw,money=dict(raw.money)|{'amount':observe_money('sqlite','12.105','text','12.105')})
        result = classify(invalid,*fact_slots(invalid)[0],DiagnosticContext(),NOW)
        self.assertIn(IncidenceCode.MONEY_SUBCENT,result.incidences)
        self.assertIsNone(result.candidate)

    def test_candidate_hash_stable_observation_clock_and_changed_content(self):
        received = db.add_received_invoice('121',business_id=self.bid)
        raw = self.exact_source('received_invoice',received['id'])
        first = classify(raw,*fact_slots(raw)[0],DiagnosticContext(),NOW)
        second = classify(raw,*fact_slots(raw)[0],DiagnosticContext(),NOW.replace(hour=13))
        self.assertEqual(first.candidate.content_hash,second.candidate.content_hash)
        self.assertEqual(first.candidate.canonical_bytes(),second.candidate.canonical_bytes())
        changed = replace(raw,money=dict(raw.money)|{'total':observe_money('sqlite','122.00','text','122.00')})
        other = classify(changed,*fact_slots(changed)[0],DiagnosticContext(),NOW)
        self.assertNotEqual(first.candidate.content_hash,other.candidate.content_hash)
        self.assertEqual(item_uuid(raw,'observed'),item_uuid(changed,'observed'))

    def test_retry_new_run_hashes_and_membership_change(self):
        self.draft()
        run = uuid4()
        first = self.run_history(run)
        retry = self.run_history(run)
        second = self.run_history()
        self.assertEqual(first['plan_hash'],retry['plan_hash'])
        self.assertEqual(first['source_set_hash'],second['source_set_hash'])
        self.assertEqual(first['plan_hash'],second['plan_hash'])
        self.assertEqual([str(r['item_uuid']) for r in self.items(first)],[str(r['item_uuid']) for r in self.items(second)])
        self.draft()
        third = self.run_history()
        self.assertNotEqual(first['source_set_hash'],third['source_set_hash'])
        with self.assertRaises(ConflictError):
            self.history.run(self.principal,run,repository_version='other-code',environment_identity='synthetic-fixture')

    def test_source_content_and_delete_change_hash(self):
        draft = self.draft()
        first = self.run_history()
        with db.get_conn() as connection:
            connection.execute('UPDATE invoices SET concept=? WHERE business_id=? AND id=?',('Concepto cambiado',self.bid,draft['id']))
        second = self.run_history()
        self.assertNotEqual(first['source_set_hash'],second['source_set_hash'])
        db.delete_invoice(draft['id'],self.bid)
        third = self.run_history()
        self.assertNotEqual(second['source_set_hash'],third['source_set_hash'])

    def test_drift_between_scan_and_freeze(self):
        draft = self.draft()
        original = RawReader.page
        changed = False
        def mutate(reader,kind,after=None):
            nonlocal changed
            if kind == 'invoice' and not changed:
                with db.get_conn() as connection:
                    row = connection.execute('SELECT 1 FROM financial_history_manifests WHERE business_id=? AND status=?',
                                              (self.bid,'planning')).fetchone()
                if row:
                    with db.get_conn() as connection:
                        connection.execute('UPDATE invoices SET concept=? WHERE business_id=? AND id=?',('Cambio concurrente sintético',self.bid,draft['id']))
                    changed = True
            return original(reader,kind,after)
        with patch.object(RawReader,'page',mutate):
            manifest = self.run_history()
        self.assertTrue(changed)
        self.assertEqual(manifest['result'],'BLOCKED')
        self.assertIn('SOURCE_DRIFT',self.codes(manifest))
        self.assertNotEqual(manifest['source_set_hash'],manifest['comparison_source_set_hash'])

    def test_sql_guards_diagnostic_frozen_delete_and_cross_business(self):
        self.issued()
        manifest = self.run_history()
        uid = str(manifest['manifest_uuid'])
        commands = [
            ("UPDATE financial_history_manifests SET eligible_for_import=? WHERE business_id=? AND manifest_uuid=?",(True,self.bid,uid)),
            ("UPDATE financial_history_manifests SET mode='certified' WHERE business_id=? AND manifest_uuid=?",(self.bid,uid)),
            ("UPDATE financial_history_manifests SET result='READY_FOR_IMPORT' WHERE business_id=? AND manifest_uuid=?",(self.bid,uid)),
            ("UPDATE financial_history_manifests SET plan_hash=? WHERE business_id=? AND manifest_uuid=?",('a'*64,self.bid,uid)),
            ("UPDATE financial_history_items SET raw_hash=? WHERE business_id=? AND manifest_uuid=?",('a'*64,self.bid,uid)),
            ("UPDATE financial_history_incidences SET status='resolved' WHERE business_id=? AND manifest_uuid=?",(self.bid,uid)),
        ]
        commands += [(f'DELETE FROM {table} WHERE business_id=? AND manifest_uuid=?',(self.bid,uid)) for table in (
            'financial_history_incidences','financial_history_items','financial_history_manifests')]
        for sql,args in commands:
            with self.subTest(sql=sql),self.assertRaises(Exception),db.get_conn() as connection:
                connection.execute(sql,args)
        other = db.create_business('Ajeno','other@example.test')
        with self.assertRaises(AccessDenied):
            HistoryDiagnostics(other['id']).run(self.principal,uuid4(),repository_version='fixture')

    def test_authentication_current_operator_no_financial_authorization(self):
        with self.assertRaises(AccessDenied):
            self.history.run(Principal(self.user['id'],999),uuid4(),repository_version='fixture')
        with self.assertRaises(AccessDenied):
            self.history.run(None,uuid4(),repository_version='fixture')
        before = self.unchanged()
        manifest = self.run_history()
        self.assertEqual(manifest['created_by'],self.user['id'])
        self.assertEqual(manifest['validated_permission'],'historical.record')
        self.assertEqual(before,self.unchanged())

    def test_decisions_append_retry_previous_no_reclassification(self):
        self.issued()
        manifest = self.run_history()
        with db.get_conn() as connection:
            incidence = connection.execute('SELECT * FROM financial_history_incidences WHERE business_id=? AND manifest_uuid=? '
                'AND item_uuid=? ORDER BY code LIMIT 1',(self.bid,str(manifest['manifest_uuid']),str(self.items(manifest,'invoice')[0]['item_uuid']))).fetchone()
        decision_id = uuid4()
        kwargs = dict(decision_uuid=decision_id,decision_type=DecisionKind.KEEP_BLOCKED,reason_code=ReasonCode.INCIDENCE)
        before = self.items(manifest)
        first = self.history.review(self.principal,manifest['manifest_uuid'],incidence['incidence_uuid'],**kwargs)
        replay = self.history.review(self.principal,manifest['manifest_uuid'],incidence['incidence_uuid'],**kwargs)
        self.assertEqual(first,replay)
        second = self.history.review(self.principal,manifest['manifest_uuid'],incidence['incidence_uuid'],
            decision_uuid=uuid4(),decision_type=DecisionKind.EXCLUDE,reason_code=ReasonCode.EXCLUDED,previous_decision_uuid=decision_id)
        self.assertEqual(str(second['previous_decision_uuid']),str(decision_id))
        self.assertEqual(before,self.items(manifest))
        with self.assertRaises(ConflictError):
            self.history.review(self.principal,manifest['manifest_uuid'],incidence['incidence_uuid'],**(kwargs|{'decision_type':DecisionKind.EXCLUDE}))
        for action in ('DELETE','UPDATE'):
            with self.assertRaises(Exception),db.get_conn() as connection:
                connection.execute(('DELETE FROM financial_history_decisions' if action=='DELETE' else "UPDATE financial_history_decisions SET reason_code='excluded'")
                    + ' WHERE business_id=? AND manifest_uuid=?',(self.bid,str(manifest['manifest_uuid'])))

    def test_add_evidence_checks_durable_tenant_hash(self):
        self.issued()
        doc_id = self.document()
        with db.get_conn() as connection:
            connection.execute('UPDATE documents SET content_sha256=? WHERE business_id=? AND id=?',('a'*64,self.bid,doc_id))
        manifest = self.run_history()
        with db.get_conn() as connection:
            inc = connection.execute('SELECT incidence_uuid FROM financial_history_incidences WHERE business_id=? AND manifest_uuid=? '
                'AND item_uuid=? LIMIT 1',(self.bid,str(manifest['manifest_uuid']),str(self.items(manifest,'invoice')[0]['item_uuid']))).fetchone()['incidence_uuid']
        ref = EvidenceReference(self.bid,EvidenceSource.DOCUMENT,doc_id,'a'*64)
        self.history.review(self.principal,manifest['manifest_uuid'],inc,decision_uuid=uuid4(),
                            decision_type=DecisionKind.ADD_EVIDENCE,evidence=(ref,))
        with self.assertRaises(AccessDenied):
            self.history.review(self.principal,manifest['manifest_uuid'],inc,decision_uuid=uuid4(),
                decision_type=DecisionKind.ADD_EVIDENCE,evidence=(replace(ref,business_id=self.bid+999),))
        with self.assertRaises((AccessDenied,ValueError)):
            self.history.review(self.principal,manifest['manifest_uuid'],inc,decision_uuid=uuid4(),
                decision_type=DecisionKind.ADD_EVIDENCE,evidence=(replace(ref,evidence_hash='b'*64),))

    def test_raw_physical_matrix(self):
        with db.get_conn() as connection:
            pg = connection.dialect == 'postgres'
            connection.execute('CREATE TABLE IF NOT EXISTS phase19b_money (id INTEGER, exact_value '
                + ('NUMERIC' if pg else 'TEXT') + ', binary_value ' + ('DOUBLE PRECISION' if pg else 'REAL') + ')')
            for index,value in enumerate((0.1,2.675,12.340000000000002,12.345,-0.0,0.0,float('nan'),float('inf'),1e308)):
                connection.execute_exact('INSERT INTO phase19b_money VALUES (?,?,?)',(index,'12.105',value))
                sql = ('SELECT exact_value,binary_value,pg_typeof(exact_value)::text AS et,pg_typeof(binary_value)::text AS bt,'
                       "exact_value::text AS es,binary_value::text AS bs,encode(float8send(binary_value),'hex') AS bits FROM phase19b_money WHERE id=?" if pg else
                       'SELECT exact_value,binary_value,typeof(exact_value) AS et,typeof(binary_value) AS bt,CAST(exact_value AS TEXT) AS es,CAST(binary_value AS TEXT) AS bs FROM phase19b_money WHERE id=?')
                row = connection.execute_exact(sql,(index,)).fetchone()
                exact = observe_money(connection.dialect,row['exact_value'],row['et'],row['es'])
                self.assertEqual(exact.evidence.exact_decimal,Decimal('12.105'))
                binary = observe_money(connection.dialect,row['binary_value'],row['bt'].replace(' ','_'),row['bs'],row.get('bits'))
                if row['binary_value'] is None:
                    self.assertIsNone(binary.evidence.exact_decimal)
                else:
                    self.assertEqual(binary.evidence.binary_representation,struct.pack('!d',row['binary_value']).hex())
                    self.assertIsNone(binary.evidence.exact_decimal)
                connection.execute('DELETE FROM phase19b_money WHERE id=?',(index,))

    def test_large_fixture_keyset_bounded_queries_and_no_effects(self):
        with db.get_conn() as connection:
            for index in range(240):
                connection.execute('INSERT INTO expenses (business_id,concept,amount,created_at) VALUES (?,?,?,?)',
                    (self.bid,f'Material {index}','0.10','2026-09-01'))
        before = self.unchanged()
        sizes = []
        context_sizes = []
        statements = []
        original = RawReader.page
        original_context = HistoryRepository.context
        original_execute = FinancialSession.execute
        def page(reader,kind,after=None):
            result = original(reader,kind,after)
            if kind=='expense':
                sizes.append(len(result))
            return result
        def context(repository,rows):
            result = original_context(repository,rows)
            context_sizes.append(len(result.sources))
            return result
        def execute(session,sql,params=()):
            statements.append(sql)
            return original_execute(session,sql,params)
        import tracemalloc
        tracemalloc.start()
        with patch.object(RawReader,'page',page),patch.object(HistoryRepository,'context',context),patch.object(FinancialSession,'execute',execute):
            manifest = self.run_history()
        _,peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertEqual(before,self.unchanged())
        self.assertEqual(len(self.items(manifest,'expense')),240)
        self.assertTrue(all(size<=8 for size in sizes))
        self.assertEqual(sum(sizes),480)
        self.assertLessEqual(max(context_sizes),8)
        self.assertLess(peak,16*1024*1024)
        self.assertFalse(any(' OFFSET ' in sql.upper() for sql in statements))
        # Solo INSERT/UPDATE por item. Auxiliares/parent/hash se consultan por lote.
        lookups = [sql for sql in statements if sql.startswith('SELECT * FROM financial_history_items') and ' IN (' in sql]
        self.assertLess(len(lookups),240)
        print(f'QA1.9B {"PG" if config.DATABASE_URL else "SQLite"}: sources=240 page=8 peak_bytes={peak} grouped_lookups={len(lookups)}')
        self.assertFalse(manifest['certifiable'])

    def approve_capture(self, service, request):
        from noesis.financial_operations.contracts import EntryIdentity
        entry = (EntryIdentity.imported(request.parameters['batch'],request.parameters['row'])
                 if request.command_type.value=='bank_transaction.import' else EntryIdentity.web_api(uuid4()))
        operation = service.prepare(self.principal,entry,request)
        approved = service.authorize(self.principal,operation.operation_uuid,channel=entry.namespace,
            approved_hash=request.request_hash,approved_revision=request.expected_revision)
        return service.execute(self.principal,approved.operation_uuid)

    def captured_invoice(self):
        from noesis.invoice_capture.service import InvoiceCapture
        service = InvoiceCapture(self.bid)
        db.update_verifactu_mode(self.bid,True)
        draft = self.draft()
        return self.approve_capture(service,service.review(self.principal,draft['id'])).result['invoice_id']

    def test_existing_invoice_payment_and_bank_coverage_not_duplicated(self):
        from noesis.payment_capture.service import PaymentCapture
        from noesis.bank_capture.service import BankCapture
        iid = self.captured_invoice()
        payment = PaymentCapture(self.bid)
        self.approve_capture(payment,payment.review(self.principal,iid,amount='10',method='efectivo'))
        bank = BankCapture(self.bid)
        imported = self.approve_capture(bank,bank.review_import(self.principal,amount='20',account_scope='fixture-account',
            batch_uuid=uuid4(),row_key='row-1',statement_hash='a'*64,booked_on='2026-09-01'))
        tid = imported.result['bank_transaction_id']
        db.suggest_bank_transaction(tid,self.bid,iid)
        self.approve_capture(bank,bank.review_match(self.principal,tid))
        before = self.unchanged()
        manifest = self.run_history()
        self.assertEqual(before,self.unchanged())
        for kind in ('invoice','invoice_payment','bank_transaction'):
            for item in self.items(manifest,kind):
                self.assertEqual(item['disposition'],'covered_existing',(kind,item['assessment_canonical']))
                self.assertIsNone(item['candidate_hash'])

    def test_existing_purchasing_revision_and_void_coverage(self):
        from noesis.purchasing_capture import SupplierInvoiceCapture, ExpenseCapture
        supplier,expense = SupplierInvoiceCapture(self.bid),ExpenseCapture(self.bid)
        result = self.approve_capture(supplier,supplier.review_confirm(self.principal,total='121'))
        source_id = result.result['source_id']
        self.approve_capture(supplier,supplier.review_correct(self.principal,source_id,reason='Importe confirmado',total='122'))
        expense_result = self.approve_capture(expense,expense.review_confirm(self.principal,amount='12.10',concept='Material'))
        self.approve_capture(expense,expense.review_void(self.principal,expense_result.result['source_id'],reason='Retirada'))
        before = self.unchanged()
        manifest = self.run_history()
        self.assertEqual(before,self.unchanged())
        for kind in ('received_invoice','expense'):
            item = self.items(manifest,kind)[0]
            self.assertEqual(item['disposition'],'covered_existing',item['assessment_canonical'])
            self.assertIsNone(item['candidate_hash'])

    def test_existing_conflict_is_blocked_never_repaired(self):
        self.captured_invoice()
        from noesis.purchasing_capture import SupplierInvoiceCapture
        supplier = SupplierInvoiceCapture(self.bid)
        self.approve_capture(supplier,supplier.review_confirm(self.principal,total='121'))
        original = RawReader._source
        def contradictory(reader,kind,row):
            if kind=='economic_event':
                row = dict(row)|{'content_hash':'f'*64,
                    'payload_canonical':'{"evidence":"NO_COPIAR_PAYLOAD_INVALIDO","total":"121.00"}'}
            elif kind=='supplier_coverage':
                row = dict(row)|{'after_state':'{"evidence":"NO_COPIAR_SNAPSHOT_INVALIDO"}'}
            return original(reader,kind,row)
        before = self.unchanged()
        with patch.object(RawReader,'_source',contradictory):
            manifest = self.run_history()
        self.assertEqual(before,self.unchanged())
        self.assertIn('EXISTING_EVENT_CONFLICT',self.codes(manifest))
        self.assertEqual(manifest['result'],'BLOCKED')
        event_raw = self.items(manifest,'economic_event')[0]['raw_canonical']
        self.assertNotIn('NO_COPIAR_PAYLOAD_INVALIDO',event_raw)
        self.assertIn('invalid_payload_hash',event_raw)
        coverage_raw = self.items(manifest,'supplier_coverage')[0]['raw_canonical']
        self.assertNotIn('NO_COPIAR_SNAPSHOT_INVALIDO',coverage_raw)
        self.assertIn('invalid_projection',coverage_raw)

    def test_cancellation_coherent_and_missing_original_no_runtime_effects(self):
        db.update_verifactu_mode(self.bid,True)
        invoice = self.issued()
        with db.get_conn() as connection:
            connection.execute("UPDATE verifactu_outbox SET status='aceptado' WHERE business_id=? AND invoice_id=?",(self.bid,invoice['id']))
        cancellation = db.create_invoice_cancellation_record(invoice['id'],self.bid,reason='Error confirmado')
        raw = self.raw('invoice_cancellation_record',cancellation['id'])
        original = self.raw('invoice_record',raw.fields['original_record_id'])
        parent = self.raw('invoice',invoice['id'])
        parent = replace(parent,money=dict(parent.money)|{'total':observe_money('sqlite','121.00','text','121.00')})
        valid = classify(raw,*fact_slots(raw)[0],DiagnosticContext((original,parent)),NOW)
        self.assertNotIn(IncidenceCode.REQUIRED_VALUE_UNKNOWN,valid.incidences)
        missing = classify(raw,*fact_slots(raw)[0],DiagnosticContext((parent,)),NOW)
        self.assertIn(IncidenceCode.REQUIRED_VALUE_UNKNOWN,missing.incidences)
        before = self.unchanged()
        manifest = self.run_history()
        self.assertEqual(before,self.unchanged())
        self.assertEqual(len(self.items(manifest,'invoice_cancellation_record')),1)

    def test_partial_scan_crash_recovers_without_duplicate_items(self):
        self.issued()
        run = uuid4()
        original = RawReader.page
        failed = False
        def crash(reader,kind,after=None):
            nonlocal failed
            if kind=='invoice_payment' and not failed:
                failed = True
                raise RuntimeError('Caída sintética después de páginas durables')
            return original(reader,kind,after)
        with patch.object(RawReader,'page',crash),self.assertRaises(RuntimeError):
            self.run_history(run)
        manifest = self.run_history(run)
        self.assertEqual(manifest['status'],'frozen')
        rows = self.items(manifest)
        self.assertEqual(len(rows),len({str(row['item_uuid']) for row in rows}))

    def test_context_of_other_business_rejected_and_same_manifest_uuid_is_scoped(self):
        received = db.add_received_invoice('121',business_id=self.bid)
        source = self.raw('received_invoice',received['id'])
        with self.assertRaises(ValueError):
            classify(source,*fact_slots(source)[0],DiagnosticContext((replace(source,business_id=self.bid+999),)),NOW)
        other = db.create_business('Ajeno','other@example.test')
        db.set_trial(other['id'],days=14)
        other_user = db.create_user(uuid4().hex+'@example.test','fixture',other['id'])
        run = uuid4()
        first = self.run_history(run)
        second = HistoryDiagnostics(other['id']).run(Principal(other_user['id'],0),run,repository_version='fixture-code-v1',environment_identity='synthetic-fixture')
        self.assertEqual(str(first['manifest_uuid']),str(second['manifest_uuid']))
        self.assertNotEqual(first['source_set_hash'],second['source_set_hash'])

    def test_c_d_and_b_parent_never_importable(self):
        expense = db.add_expense('Material','12.10',business_id=self.bid)
        source = self.raw('expense',expense['id'])
        blocked = classify(source,*fact_slots(source)[0],DiagnosticContext(),NOW)
        self.assertEqual(blocked.assessment.classification,Classification.AMBIGUOUS)
        self.assertIsNone(blocked.candidate)
        from noesis.financial_history.contracts import HistoricalDependency
        from noesis.economic_events.contracts import RelationType
        exact = self.exact_source('expense',expense['id'])
        candidate = classify(exact,*fact_slots(exact)[0],DiagnosticContext(),NOW).candidate
        dependency = HistoricalDependency(RelationType.VOIDS,candidate.identity,candidate.assessment)
        self.assertFalse(dependency.satisfied)

    def test_scope_and_raw_money_without_legacy_normalization(self):
        expense = db.add_expense('Material','0.10',business_id=self.bid)
        with patch.object(db,'_normalise_row',side_effect=AssertionError('No usar salida legacy')):
            source = self.raw('expense',expense['id'])
        self.assertEqual(source.money['amount'].evidence.binary_decimal,Decimal.from_float(0.1))
        self.assertEqual(source.money['amount'].evidence.binary_representation,struct.pack('!d',0.1).hex())
        self.assertEqual(source.money['amount'].storage_class,'double_precision' if config.DATABASE_URL else 'real')

    def test_raw_invalid_exact_null_zero_negative_zero_and_range(self):
        for engine,kind in (('sqlite','text'),('postgres','numeric')):
            for value in ('NaN','Infinity','-Infinity','abc'):
                observation = observe_money(engine,value,kind,value)
                self.assertIsNone(observation.evidence)
                self.assertEqual(observation.invalid_reason,'invalid_exact_storage')
            unknown = observe_money(engine,None,'null',None)
            zero = observe_money(engine,'0.00',kind,'0.00')
            self.assertNotEqual(unknown.content_hash,zero.content_hash)
            negative = observe_money(engine,-0.0,'real' if engine=='sqlite' else 'double_precision','0')
            self.assertEqual(negative.evidence.binary_representation,'8000000000000000')
            huge = observe_money(engine,'1'+'0'*80,kind,'1'+'0'*80)
            self.assertEqual(huge.evidence.exact_decimal,Decimal('1'+'0'*80))

    def test_minimal_documents_ignore_ocr_and_auxiliary_outboxes_never_produce(self):
        document = self.document()
        with db.get_conn() as connection:
            connection.execute('UPDATE documents SET ocr_text=?,note=? WHERE business_id=? AND id=?',
                ('DATOS-PRIVADOS-OCR','NOTA-PRIVADA',self.bid,document))
        manifest = self.run_history()
        doc = self.items(manifest,'document')[0]
        self.assertNotIn('DATOS-PRIVADOS',doc['raw_canonical'])
        self.assertNotIn('NOTA-PRIVADA',doc['raw_canonical'])
        self.assertIsNone(doc['proposed_event_type'])
        self.assertIsNone(doc['candidate_canonical'])

    def test_migration_adds_exactly_four_tables_and_preserves_old_columns(self):
        from noesis.financial_history.schema import TABLES
        with self.empty_database(69):
            with db.get_conn() as connection:
                if connection.dialect=='sqlite':
                    names = [r['name'] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
                    before = {name:tuple((r['name'],r['type'],r['notnull']) for r in connection.execute(f'PRAGMA table_info({name})').fetchall()) for name in names}
                else:
                    names = [r['table_name'] for r in connection.execute('SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema()').fetchall()]
                    before = {name:tuple((r['column_name'],r['data_type'],r['is_nullable']) for r in connection.execute('SELECT column_name,data_type,is_nullable '
                        'FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=? ORDER BY ordinal_position',(name,)).fetchall()) for name in names}
            migrations.upgrade(70)
            with db.get_conn() as connection:
                if connection.dialect=='sqlite':
                    after_names = {r['name'] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
                    after = {name:tuple((r['name'],r['type'],r['notnull']) for r in connection.execute(f'PRAGMA table_info({name})').fetchall()) for name in names}
                else:
                    after_names = {r['table_name'] for r in connection.execute('SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema()').fetchall()}
                    after = {name:tuple((r['column_name'],r['data_type'],r['is_nullable']) for r in connection.execute('SELECT column_name,data_type,is_nullable '
                        'FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=? ORDER BY ordinal_position',(name,)).fetchall()) for name in names}
            self.assertEqual(after_names-set(names),set(TABLES))
            self.assertEqual(before,after)

    def test_reader_closed_scope_cursor_page_and_raw_float_json_rejected(self):
        with db.get_conn() as connection:
            for size in (0,257,True):
                with self.assertRaises(ValueError):
                    RawReader(connection,self.bid,page_size=size)
            reader = RawReader(connection,self.bid)
            for kind in ('quote.accepted','job.completed','supplier_payment.made'):
                with self.assertRaises(KeyError):
                    reader.page(kind)
            with self.assertRaises(ValueError):
                reader.page('invoice',('bad','cursor'))
        expense = db.add_expense('Material','12.10',business_id=self.bid)
        raw = self.raw('expense',expense['id'])
        with self.assertRaises((ValueError,TypeError)):
            replace(raw,fields=dict(raw.fields)|{'amount':1.1})
        with self.assertRaises(ValueError):
            replace(raw,reader_version=2)
        from noesis.financial_history.readers import RawSource
        self.assertEqual(raw.content_hash,RawSource.from_canonical(raw.canonical_bytes().decode()).content_hash)

    def test_invoice_verified_raw_stays_blocked_without_historical_v2_contract(self):
        db.update_verifactu_mode(self.bid,True)
        draft = self.draft(lines=[{'description':'A','quantity':'1','unit_price':'50','vat_rate':21},
                                {'description':'B','quantity':'1','unit_price':'50','vat_rate':21}])
        invoice = db.issue_invoice(draft['id'],self.bid)
        source = self.raw('invoice',invoice['id'])
        money = dict(source.money)
        for field,value in {'base':'100.00','vat_amount':'21.00','irpf_amount':'0.00','total':'121.00'}.items():
            money[field] = observe_money('sqlite',value,'text',value)
        source = replace(source,money=money)
        profile = self.raw('document_profile',source.fields['document_profile_id'])
        profile = replace(profile,fields=dict(profile.fields)|{'version':2})
        with db.get_conn() as connection:
            lines = [self.raw('invoice_line',r['id']) for r in connection.execute('SELECT id FROM invoice_lines WHERE business_id=? AND invoice_id=?',(self.bid,invoice['id'])).fetchall()]
            record_id = connection.execute('SELECT id FROM invoice_records WHERE business_id=? AND invoice_id=?',(self.bid,invoice['id'])).fetchone()['id']
        record = self.raw('invoice_record',record_id)
        record = replace(record,money={key:observe_money('sqlite',value,'text',value) for key,value in {'vat_total':'21.00','invoice_total':'121.00'}.items()})
        result = classify(source,*fact_slots(source)[0],DiagnosticContext((profile,record,*lines)),NOW)
        self.assertEqual(result.assessment.classification,Classification.VERIFIED_HISTORY)
        self.assertEqual(result.terminal_result,'not_durably_supported')
        self.assertIsNone(result.candidate)

    def test_readonly_business_and_flags_on_cannot_register(self):
        with patch.object(config,'FINANCIAL_CORE_ENABLED',True),self.assertRaises(AccessDenied):
            self.run_history()
        with db.get_conn() as connection:
            connection.execute("UPDATE businesses SET subscription_status='inactive',trial_ends_at=NULL WHERE id=?",(self.bid,))
        with self.assertRaises(AccessDenied):
            self.run_history()

    def test_decision_requires_evidence_and_selection_hash(self):
        self.issued()
        manifest = self.run_history()
        with db.get_conn() as connection:
            inc = connection.execute('SELECT incidence_uuid FROM financial_history_incidences WHERE business_id=? AND manifest_uuid=? LIMIT 1',
                (self.bid,str(manifest['manifest_uuid']))).fetchone()['incidence_uuid']
        for kind in (DecisionKind.ADD_EVIDENCE,DecisionKind.SELECT_SUPPORTED_INTERPRETATION):
            with self.assertRaises(ValueError):
                self.history.review(self.principal,manifest['manifest_uuid'],inc,decision_uuid=uuid4(),decision_type=kind)
        with self.assertRaises(AccessDenied):
            self.history.review(self.principal,manifest['manifest_uuid'],inc,decision_uuid=uuid4(),decision_type=DecisionKind.KEEP_BLOCKED,
                previous_decision_uuid=uuid4())

    def test_sql_composite_scope_rejects_actor_and_incidence_of_other_business(self):
        self.issued()
        manifest = self.run_history()
        other = db.create_business('Ajeno','other@example.test')
        user = db.create_user(uuid4().hex+'@example.test','fixture',other['id'])
        with db.get_conn() as connection:
            inc = connection.execute('SELECT * FROM financial_history_incidences WHERE business_id=? AND manifest_uuid=? LIMIT 1',
                (self.bid,str(manifest['manifest_uuid']))).fetchone()
        for actor,manifest_uuid in ((user['id'],manifest['manifest_uuid']),(self.user['id'],uuid4())):
            with self.assertRaises(Exception),db.get_conn() as connection:
                connection.execute("INSERT INTO financial_history_decisions (business_id,manifest_uuid,item_uuid,incidence_uuid,decision_uuid,recorded_by,"
                    "validated_permission,decision_type,evidence_canonical,reason_code,decided_at) VALUES (?,?,?,?,?,?,'historical.record','keep_blocked','[]','incidence',?)",
                    (self.bid,str(manifest_uuid),str(inc['item_uuid']),str(inc['incidence_uuid']),str(uuid4()),actor,NOW.isoformat()))
