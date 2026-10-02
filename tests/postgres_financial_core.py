"""Contrato exacto contra PostgreSQL local: esquema aislado, sin datos reales.

DATABASE_URL debe apuntar a localhost/noesis_ci. No se ejecuta en producción.
"""

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
from uuid import uuid4

from noesis import config, db
from noesis.core.persistence import FinancialSession
from tests.financial_core_contract import PersistenceContract


class FinancialPostgresTestCase(PersistenceContract, unittest.TestCase):
    def setUp(self):
        url = urlsplit(config.DATABASE_URL)
        if url.hostname not in {"localhost", "127.0.0.1", "::1"} or url.path != "/noesis_ci" or config.IS_PRODUCTION:
            raise RuntimeError("Solo PostgreSQL local descartable /noesis_ci, nunca producción.")
        self.original = db.get_conn
        self.schema = "phase0_" + uuid4().hex
        with self.original() as conn:
            conn.execute(f"CREATE SCHEMA {self.schema}")

        @contextmanager
        def scoped():
            with self.original() as conn:
                conn.execute(f"SET LOCAL search_path TO {self.schema}")
                yield conn

        self.scoped = patch.object(db, "get_conn", scoped)
        self.scoped.start()

    def tearDown(self):
        self.scoped.stop()
        with self.original() as conn:
            conn.execute(f"DROP SCHEMA {self.schema} CASCADE")

    def test_native_decimal_dates_and_nested_binary_json(self):
        with db.get_conn() as conn:
            exact = FinancialSession(conn)
            row = exact.execute("SELECT CAST(? AS NUMERIC(20,4)) AS amount, CAST(? AS DATE) AS day",
                                (Decimal("1234.5678"), "2026-10-02")).fetchone()
            self.assertEqual(row["amount"], Decimal("1234.5678"))
            self.assertEqual(row["day"], date(2026, 10, 2))
            legacy = conn.execute("SELECT CAST(? AS DATE) AS day", ("2026-10-02",)).fetchone()
            self.assertEqual(legacy["day"], "2026-10-02")
            self.assertEqual(exact.execute("SELECT CAST(? AS JSONB) AS data",
                                          ('{"amount":"0.10"}',)).fetchone()["data"], {"amount": "0.10"})
            with self.assertRaises(TypeError):
                exact.execute("SELECT CAST(? AS JSONB) AS data", ('{"amount":0.1}',)).fetchone()


if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        db.close_pool()
