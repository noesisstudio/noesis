"""Contrato y concurrencia real con conexiones e intérpretes separados."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from tests.postgres_financial_operations import FinancialOperationsPostgres
from tests.purchasing_capture_contract import PurchasingCaptureContract


class PurchasingCapturePostgres(PurchasingCaptureContract, unittest.TestCase):
    setUpClass = classmethod(FinancialOperationsPostgres.setUpClass.__func__)
    tearDownClass = classmethod(FinancialOperationsPostgres.tearDownClass.__func__)

    def setUp(self):
        self.setup_capture()

    def race(self, operations, mode='supplier'):
        env = dict(os.environ, NOESIS_DATABASE_URL=self.scoped_url, DATABASE_URL=self.scoped_url)
        children = [subprocess.Popen([sys.executable, '-m', 'tests.purchasing_capture_worker', json.dumps({
            'mode': mode, 'business_id': self.bid, 'user_id': self.user['id'], 'operation_uuid': op.operation_uuid})],
            cwd=Path(__file__).parents[1], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for op in operations]
        try:
            for child in children:
                self.assertEqual(child.stdout.readline().strip(), 'READY')
            for child in children:
                child.stdin.write('go\n')
                child.stdin.flush()
            results = []
            for child in children:
                out, error = child.communicate(timeout=45)
                self.assertEqual(child.returncode, 0, error)
                results.append(json.loads(out.strip()))
            return results
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate()

    def test_processes_same_supplier_confirmation_one_source_event(self):
        op = self.approved(self.supplier, self.supplier.review_confirm(self.principal, total='121'))
        results = self.race([op, op])
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(self.state()['received_invoices']), 1)
        self.assertEqual(len(self.state()['economic_events']), 1)

    def test_processes_supplier_corrections_stale_one_winner(self):
        source = self.confirm().result['source_id']
        ops = [self.approved(self.supplier, self.supplier.review_correct(self.principal, source, reason='Importe', total=amount))
               for amount in ('130', '140')]
        results = self.race(ops)
        self.assertEqual(sum('conflict' in r for r in results), 1)
        self.assertEqual(len(self.state()['economic_events']), 2)

    def test_processes_supplier_correction_and_void_one_winner(self):
        source = self.confirm().result['source_id']
        ops = [self.approved(self.supplier, self.supplier.review_correct(self.principal, source, reason='Importe', total='140')),
               self.approved(self.supplier, self.supplier.review_void(self.principal, source, reason='Retirada'))]
        results = self.race(ops)
        self.assertEqual(sum('conflict' in r for r in results), 1)
        self.assertEqual(len(self.state()['economic_events']), 2)

    def test_processes_same_expense_confirmation_one_source_event(self):
        op = self.approved(self.expense, self.expense.review_confirm(self.principal, amount='12.10', concept='Material'))
        results = self.race([op, op], 'expense')
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(self.state()['expenses']), 1)
        self.assertEqual(len(self.state()['economic_events']), 1)

    def test_processes_distinct_equal_expenses_both_legitimate(self):
        ops = [self.approved(self.expense, self.expense.review_confirm(self.principal, amount='12.10', concept='Material')) for _ in range(2)]
        results = self.race(ops, 'expense')
        self.assertFalse(any('conflict' in r for r in results))
        self.assertEqual(len(self.state()['expenses']), 2)
        self.assertEqual(len(self.state()['economic_events']), 2)

    def test_processes_expense_two_voids_stale_one_winner(self):
        source = self.confirm(self.expense).result['source_id']
        ops = [self.approved(self.expense, self.expense.review_void(self.principal, source, reason='Retirada')) for _ in range(2)]
        results = self.race(ops, 'expense')
        self.assertEqual(sum('conflict' in r for r in results), 1)
        self.assertEqual(len(self.state()['expenses']), 1)
        self.assertEqual(len(self.state()['economic_events']), 2)
