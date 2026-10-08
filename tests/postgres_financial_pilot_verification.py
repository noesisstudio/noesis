"""G sobre PostgreSQL nativo descartable, rol runtime restringido y sin red provider."""
import unittest
from tests.financial_pilot_verification_contract import PilotVerificationContract
from tests import postgres_financial_providers as fixtures
from tests.financial_recovery_readiness_contract import RecoveryContract


class PilotVerificationPostgres(PilotVerificationContract, unittest.TestCase):
    setUpClass = classmethod(fixtures.ProviderPostgres.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.ProviderPostgres.tearDownClass.__func__)
    seed = fixtures.ProviderPostgres.seed
    setUp = fixtures.ProviderPostgres.setUp

    def test_gate_in_repeatable_read_read_only_transaction(self):
        from noesis import db
        from noesis.core.persistence import FinancialSession
        from noesis.financial_pilot.gate import PilotGate
        self.gate_fixture()
        with db.get_conn() as c:
            c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            api = self.verifiers(FinancialSession(c))
            result = PilotGate(api).decide(self.all_evidence(api))
            self.assertEqual(result.body['result'], 'PILOT_READY', result.body)
            self.assertFalse(result.body['activation_authorized'])


class RecoveryPostgres(RecoveryContract, unittest.TestCase):
    setUpClass = classmethod(fixtures.ProviderPostgres.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.ProviderPostgres.tearDownClass.__func__)
    seed = fixtures.ProviderPostgres.seed
    setUp = fixtures.ProviderPostgres.setUp


if __name__ == '__main__':
    unittest.main()
