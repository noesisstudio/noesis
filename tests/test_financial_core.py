"""Fundamentos monetarios y conexión exacta; no crean dominios futuros."""

from dataclasses import FrozenInstanceError
from decimal import Decimal, Inexact, ROUND_DOWN, localcontext
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

from noesis import config, db
from noesis.core.money import Currency, Money, parse_money, quantize_currency
from noesis.core.persistence import FinancialSession
from tests.financial_core_contract import PersistenceContract


class MoneyTestCase(unittest.TestCase):
    def test_parse_preserves_precision_until_explicit_rounding(self):
        self.assertEqual(parse_money("1234.567891"), Decimal("1234.567891"))
        self.assertEqual(parse_money(12), Decimal("12"))
        self.assertEqual(parse_money(Decimal("0.10")), Decimal("0.10"))
        self.assertEqual(quantize_currency("1234.567891"), Decimal("1234.57"))

    def test_commercial_rounding_with_positive_and_negative_ties(self):
        for raw, expected in (("1.005", "1.01"), ("-1.005", "-1.01"),
                              ("2.675", "2.68"), ("-0.004", "0.00"),
                              ("0.005", "0.01"), ("999.995", "1000.00")):
            with self.subTest(raw=raw):
                self.assertEqual(Money.parse(raw).to_decimal_string(), expected)

    def test_binary_and_implicit_types_are_not_money(self):
        for raw in (0.1, True, False, None, [], {}, b"1.00"):
            with self.subTest(raw=raw), self.assertRaises(TypeError):
                parse_money(raw)
        with self.assertRaises(TypeError):
            Money("1.00")

    def test_invalid_and_localised_text_is_rejected(self):
        for raw in ("", "1,20", "1.000,00", "1e2", "NaN", "Infinity", " 1", "1 ",
                    "€1", "1_000", "١٢", ".1", "1.", "1" * 65):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_money(raw)

    def test_non_finite_and_out_of_range_decimals(self):
        for raw in ("NaN", "sNaN", "Infinity", "-Infinity", "1E100000", "1E-100000",
                    "10000000000000000", "-10000000000000000"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_money(Decimal(raw))
        self.assertEqual(parse_money("9999999999999999.9999"), Decimal("9999999999999999.9999"))
        for raw in ("9999999999999999.995", "-9999999999999999.995"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                quantize_currency(raw)

    def test_money_is_immutable_and_currency_is_explicit(self):
        money = Money.parse("1.2", "EUR")
        self.assertIs(money.currency, Currency.EUR)
        self.assertEqual(money.to_decimal_string(), "1.20")
        with self.assertRaises(FrozenInstanceError):
            money.amount = Decimal("2")
        for currency in ("USD", "eur", "XXX", "", None):
            with self.subTest(currency=currency), self.assertRaises(ValueError):
                Money.parse("1", currency)

    def test_arithmetic_and_rounding_ignore_ambient_decimal_context(self):
        with localcontext() as ctx:
            ctx.prec = 3
            ctx.rounding = ROUND_DOWN
            ctx.traps[Inexact] = True
            self.assertEqual(Money.parse("123456.785").to_decimal_string(), "123456.79")
            value = Money.parse("9999999999999999.98") + Money.parse("0.01")
            self.assertEqual(value.to_decimal_string(), "9999999999999999.99")
            self.assertEqual((value - Money.parse("0.01")).to_decimal_string(), "9999999999999999.98")
            self.assertEqual(ctx.prec, 3)
            self.assertTrue(ctx.traps[Inexact])
        self.assertEqual((Money.parse("0.1") + Money.parse("0.2")).to_decimal_string(), "0.30")
        with self.assertRaises(ValueError):
            Money.parse("9999999999999999.99") + Money.parse("0.01")
        with self.assertRaises(TypeError):
            Money.parse("1") + 0.1

    def test_cent_roundtrip_for_signed_range(self):
        for cents in range(-10000, 10001, 7):
            amount = Decimal(cents).scaleb(-2)
            self.assertEqual(Money.parse(Money(amount).to_decimal_string()).amount, amount)


class FinancialSQLiteTestCase(PersistenceContract, unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = patch.multiple(config, DATABASE_URL="", DB_PATH=Path(self.temp.name) / "core.db")
        self.settings.start()

    def tearDown(self):
        self.settings.stop()
        self.temp.cleanup()

    def test_sqlite_numeric_affinity_is_not_an_exact_storage_contract(self):
        with db.get_conn() as conn:
            conn.execute("CREATE TABLE bad_amount (amount NUMERIC)")
            session = FinancialSession(conn)
            session.execute("INSERT INTO bad_amount VALUES (?)", (Decimal("0.1"),))
            with self.assertRaises(TypeError):
                session.execute("SELECT amount FROM bad_amount").fetchone()


class FinancialFlagsTestCase(unittest.TestCase):
    names = ("FINANCIAL_CORE_ENABLED", "LEDGER_REPORTING_ENABLED", "OPEN_ITEMS_ENABLED",
             "NEW_TAX_ENGINE_ENABLED", "NEW_BANK_RECONCILIATION_ENABLED")

    def read_config(self, values):
        with patch.dict(os.environ, values, clear=True), patch("dotenv.load_dotenv"):
            return runpy.run_path(config.__file__)

    def test_defaults_off_and_explicit_values(self):
        for text, expected in ((None, False), ("false", False), ("0", False), ("true", True)):
            values = {} if text is None else {"NOESIS_" + name: text for name in self.names}
            loaded = self.read_config(values)
            self.assertEqual([loaded[name] for name in self.names], [expected] * len(self.names))

    def test_invalid_flag_fails_configuration(self):
        for name in self.names:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.read_config({"NOESIS_" + name: "quizas"})
