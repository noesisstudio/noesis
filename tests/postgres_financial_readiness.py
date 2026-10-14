"""Contrato A en PostgreSQL local /noesis_ci y esquema descartable."""

import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from urllib.parse import quote
from uuid import uuid4

from noesis import config, db
from tests.financial_readiness_contract import ReadinessContract
from tests import postgres_financial_operations as operations_pg
from tests.test_financial_readiness_migrations import migration_cycle


class ReadinessPostgres(ReadinessContract, unittest.TestCase):
    setUpClass = classmethod(operations_pg.FinancialOperationsPostgres.setUpClass.__func__)
    tearDownClass = classmethod(operations_pg.FinancialOperationsPostgres.tearDownClass.__func__)

    def setUp(self):
        self.setup_readiness()

    def test_two_connections_same_uuid_exact_context(self):
        self.cut()
        uid = uuid4()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.evaluate(uid=uid), range(2)))
        self.assertEqual(results[0], results[1])
        with db.get_conn() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM financial_readiness_evaluations WHERE business_id=?",
                    (self.bid,),
                ).fetchone()["n"],
                1,
            )

    def test_empty_migration_cycles_on_separate_schema(self):
        name = "readiness_cycle_" + uuid4().hex
        with db.get_conn() as c:
            c.execute("CREATE SCHEMA " + name)
        url = (
            self.original_url
            + ("&" if "?" in self.original_url else "?")
            + "options="
            + quote("-csearch_path=" + name)
        )
        db.close_pool()
        try:
            with patch.object(config, "DATABASE_URL", url):
                migration_cycle(self)
                db.close_pool()
        finally:
            with db.get_conn() as c:
                c.execute("DROP SCHEMA " + name + " CASCADE")


if __name__ == "__main__":
    unittest.main()
