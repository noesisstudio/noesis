"""RecoveryReadiness sobre SQLite descartable."""
import unittest
from tests.financial_recovery_readiness_contract import RecoveryContract
from tests import test_financial_pilot_verification as fixtures


class RecoverySQLite(RecoveryContract, unittest.TestCase):
    setUpClass = classmethod(fixtures.PilotVerificationSQLite.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.PilotVerificationSQLite.tearDownClass.__func__)
    setUp = fixtures.PilotVerificationSQLite.setUp
