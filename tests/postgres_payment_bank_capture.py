"""Contrato compartido y carreras con dos intérpretes y conexiones PostgreSQL."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from noesis import db
from tests.payment_bank_capture_contract import PaymentBankCaptureContract
from tests.postgres_financial_operations import FinancialOperationsPostgres


class PaymentBankCapturePostgres(PaymentBankCaptureContract, unittest.TestCase):
    setUpClass = classmethod(FinancialOperationsPostgres.setUpClass.__func__)
    tearDownClass = classmethod(FinancialOperationsPostgres.tearDownClass.__func__)

    def setUp(self):
        self.setup_capture()

    def race(self, operations, mode='payment'):
        env = dict(os.environ,NOESIS_DATABASE_URL=self.scoped_url,DATABASE_URL=self.scoped_url)
        children = [subprocess.Popen([sys.executable,'-m','tests.payment_bank_capture_worker',json.dumps({
            'mode':mode,'business_id':self.bid,'user_id':self.user['id'],'operation_uuid':op.operation_uuid})],
            cwd=Path(__file__).parents[1],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            for op in operations]
        try:
            for child in children:
                self.assertEqual(child.stdout.readline().strip(),'READY')
            for child in children:
                child.stdin.write('go\n')
                child.stdin.flush()
            results = []
            for child in children:
                out,error = child.communicate(timeout=45)
                self.assertEqual(child.returncode,0,error)
                results.append(json.loads(out.strip()))
            return results
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate()

    def test_processes_same_operation_one_payment(self):
        op = self.approved(self.pay,self.pay.review(self.principal,self.invoice(),amount='10'))
        results = self.race([op,op])
        self.assertEqual(results[0],results[1])
        self.assertEqual(len(self.state()['invoice_payments']),1)
        self.assertEqual(len(self.state()['payment_economic_coverage']),1)

    def test_processes_two_partials_both_if_capacity(self):
        iid = self.invoice()
        ops = [self.approved(self.pay,self.pay.review(self.principal,iid,amount='10')) for _ in range(2)]
        results = self.race(ops)
        self.assertFalse(any('conflict' in r for r in results))
        self.assertEqual(len(self.state()['invoice_payments']),2)

    def test_processes_overlapping_partials_never_overpay(self):
        iid = self.invoice()
        ops = [self.approved(self.pay,self.pay.review(self.principal,iid,amount='70')) for _ in range(2)]
        results = self.race(ops)
        self.assertEqual(sum('conflict' in r for r in results),1)
        self.assertEqual(len(self.state()['invoice_payments']),1)

    def test_processes_partial_and_full_only_one_valid_context(self):
        iid = self.invoice()
        ops = [self.approved(self.pay,self.pay.review(self.principal,iid,amount='10')),
               self.approved(self.pay,self.pay.review(self.principal,iid,mode='full'))]
        results = self.race(ops)
        self.assertEqual(sum('conflict' in r for r in results),1)
        self.assertEqual(len(self.state()['invoice_payments']),1)

    def test_processes_two_full_one_payment(self):
        iid = self.invoice()
        ops = [self.approved(self.pay,self.pay.review(self.principal,iid,mode='full')) for _ in range(2)]
        results = self.race(ops)
        self.assertEqual(sum('conflict' in r for r in results),1)
        self.assertEqual(len(self.state()['invoice_payments']),1)

    def test_processes_match_distinct_operations_only_one_winner(self):
        _,_,_,op = self.match_operation()
        other = self.approved(self.bank,op.request)
        results = self.race([op,other],mode='bank')
        self.assertEqual(sum('conflict' in r for r in results),1)
        self.assertEqual(len(self.state()['invoice_payments']),1)
        self.assertEqual(len(self.state()['bank_match_coverage']),1)
        self.assertEqual(len(self.state()['economic_events']),4)

    def test_processes_match_same_operation_recovers_two_events(self):
        _,_,_,op = self.match_operation()
        results = self.race([op,op],mode='bank')
        self.assertEqual(results[0],results[1])
        self.assertEqual(len(self.state()['invoice_payments']),1)
        self.assertEqual(len(self.state()['economic_events']),4)

    def test_processes_import_same_operation_one_movement(self):
        from datetime import date
        from uuid import uuid4
        op = self.approved(self.bank,self.bank.review_import(self.principal,batch_uuid=uuid4(),row_key='1',
            account_scope='a',statement_hash='a'*64,booked_on=date.today().isoformat(),amount='10'))
        results = self.race([op,op],mode='bank')
        self.assertEqual(results[0],results[1])
        self.assertEqual(len(self.state()['bank_transactions']),1)

    def test_saved_binary_origin_and_exact_new_event_column(self):
        done = self.payment(self.invoice(),'10.01')
        with db.get_conn() as conn:
            row = conn.execute_exact('SELECT amount,pg_typeof(amount)::text AS typ FROM economic_events '
                                     'WHERE business_id=? AND event_uuid=?',(self.bid,done.result['event_uuid'])).fetchone()
        from decimal import Decimal
        self.assertIsInstance(row['amount'],Decimal)
        self.assertEqual(row['typ'],'numeric')
