"""Contrato común de persistencia; se ejecuta en SQLite y PostgreSQL real."""

from decimal import Decimal

from noesis import db
from noesis.core.money import Money, parse_money
from noesis.core.persistence import FinancialSession


class PersistenceContract:
    """La clase concreta proporciona una base/esquema descartable por prueba."""

    def create_probe(self):
        with db.get_conn() as conn:
            amount_type = "NUMERIC(20, 4)" if conn.dialect == "postgres" else "TEXT"
            conn.execute(
                f"CREATE TABLE phase0_probe (business_id INTEGER NOT NULL, "
                f"id INTEGER NOT NULL, amount {amount_type} NOT NULL, "
                "PRIMARY KEY (business_id, id))"
            )

    def test_exact_roundtrip_and_legacy_are_independent(self):
        self.create_probe()
        expected = Money.parse("9999999999999999.99")
        with db.get_conn() as conn:
            session = FinancialSession(conn)
            session.execute(
                "INSERT INTO phase0_probe VALUES (?, ?, ?)", (1, 1, expected.amount)
            )
            session.execute("INSERT INTO phase0_probe VALUES (?, ?, ?)", (2, 1, Decimal("0.10")))
            exact = session.execute(
                "SELECT amount FROM phase0_probe WHERE business_id=?", (1,)
            ).fetchone()
            self.assertEqual(parse_money(exact["amount"]), expected.amount)
            self.assertEqual(exact[0], exact["amount"])
            legacy = conn.execute("SELECT amount FROM phase0_probe WHERE business_id=?", (1,)).fetchone()
            if conn.dialect == "postgres":
                self.assertIsInstance(exact["amount"], Decimal)
                self.assertIsInstance(legacy["amount"], float)
                self.assertNotEqual(Decimal(str(legacy["amount"])), expected.amount)
            else:
                self.assertIsInstance(exact["amount"], str)
            rows = session.execute("SELECT amount FROM phase0_probe WHERE business_id=?", (2,)).fetchall()
            self.assertEqual([parse_money(row["amount"]) for row in rows], [Decimal("0.10")])
            self.assertIsNone(session.execute("SELECT * FROM phase0_probe WHERE business_id=3").fetchone())

    def test_legacy_and_exact_writes_rollback_together(self):
        self.create_probe()
        with self.assertRaisesRegex(RuntimeError, "fallo posterior"):
            with db.get_conn() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("INSERT INTO phase0_probe VALUES (?, ?, ?)", (1, 1, "1.00"))
                FinancialSession(conn).execute(
                    "INSERT INTO phase0_probe VALUES (?, ?, ?)", (1, 2, Decimal("2.00"))
                )
                self.assertEqual(conn.execute("SELECT COUNT(*) AS n FROM phase0_probe").fetchone()["n"], 2)
                raise RuntimeError("fallo posterior")
        with db.get_conn() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS n FROM phase0_probe").fetchone()["n"], 0)

    def test_commit_is_owned_by_existing_context(self):
        self.create_probe()
        with db.get_conn() as conn:
            session = FinancialSession(conn)
            self.assertFalse(hasattr(session, "commit"))
            self.assertFalse(hasattr(session, "rollback"))
            self.assertFalse(hasattr(session, "close"))
            self.assertEqual(session.execute(
                "INSERT INTO phase0_probe VALUES (?, ?, ?)", (1, 1, Decimal("1234.5678"))
            ).rowcount, 1)
        with db.get_conn() as conn:
            value = FinancialSession(conn).execute("SELECT amount FROM phase0_probe").fetchone()["amount"]
            self.assertEqual(parse_money(value), Decimal("1234.5678"))

    def test_invalid_parameters_leave_no_writes(self):
        self.create_probe()
        with db.get_conn() as conn:
            session = FinancialSession(conn)
            for value in (0.1, float("nan"), float("inf"), Decimal("NaN"), Decimal("Infinity")):
                with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                    session.execute("INSERT INTO phase0_probe VALUES (?, ?, ?)", (1, 1, value))
            self.assertEqual(conn.execute("SELECT COUNT(*) AS n FROM phase0_probe").fetchone()["n"], 0)

    def test_binary_results_are_rejected_without_changing_legacy(self):
        with db.get_conn() as conn:
            cast = "DOUBLE PRECISION" if conn.dialect == "postgres" else "REAL"
            sql = f"SELECT CAST(0.1 AS {cast}) AS amount"
            self.assertIsInstance(conn.execute(sql).fetchone()["amount"], float)
            with self.assertRaises(TypeError):
                FinancialSession(conn).execute(sql).fetchone()
            with self.assertRaises(TypeError):
                FinancialSession(conn).execute(sql).fetchall()
