import unittest
from tests.financial_channels_contract import ChannelsContract
from tests.postgres_financial_operations import FinancialOperationsPostgres


class FinancialChannelsPostgres(ChannelsContract, unittest.TestCase):
    setUpClass = classmethod(FinancialOperationsPostgres.setUpClass.__func__)
    tearDownClass = classmethod(FinancialOperationsPostgres.tearDownClass.__func__)

    def setUp(self):
        self.setup_channels()
