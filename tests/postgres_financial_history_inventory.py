"""Mismo contrato1.9B en PostgreSQL local descartable, nunca Railway."""

import unittest

from tests.financial_history_inventory_contract import HistoryInventoryContract
from tests.postgres_financial_operations import FinancialOperationsPostgres


class HistoryInventoryPostgres(HistoryInventoryContract, unittest.TestCase):
    setUpClass = classmethod(FinancialOperationsPostgres.setUpClass.__func__)
    tearDownClass = classmethod(FinancialOperationsPostgres.tearDownClass.__func__)

    def setUp(self):
        self.setup_history()


if __name__ == '__main__':
    unittest.main()
