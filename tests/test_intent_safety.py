"""Corpus sintético de incidentes: sin proveedores ni datos de clientes."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from noesis import config, db, nlu
from noesis.intent_safety import inspect_money_intent
from noesis.web import chat


class IntentSafetyTest(unittest.TestCase):
    def test_expense_preserves_explicit_included_tax(self):
        tool, args = nlu.parse("Gasté 121 euros IVA incluido al 21% en herramientas")
        self.assertEqual(tool, "registrar_gasto")
        self.assertEqual(args, {"concepto": "herramientas", "importe": 121, "iva": 21})
        for message in ("Gasté 100 euros más IVA en herramientas",
                        "Gasté 121 euros IVA no incluido al 21% en herramientas",
                        "Gasté 121 euros IVA incluido al 21,5% en herramientas",
                        "Gasté 121 euros IVA incluido al 13% en herramientas"):
            self.assertEqual(nlu.parse(message)[0], nlu.NEED_REVIEW)

    def test_client_identity_is_not_contaminated_by_tax_connector(self):
        tool, args = nlu.parse("Factura a Pedro QA por mantenimiento 100 euros con IVA del 10%")
        self.assertEqual(tool, "crear_factura")
        self.assertEqual(args["cliente"], "Pedro QA")
        self.assertEqual(args["concepto"], "mantenimiento")
        self.assertEqual(args["base"], 100)
        self.assertEqual(args["iva"], 10)

    def test_explicit_client_names_keep_only_the_name(self):
        for message, expected in (
            ("Crea un cliente llamado Jana QA", "Jana QA"),
            ("Nuevo cliente: Jana QA Dos", "Jana QA Dos"),
            ("crear cliente Ana Ruiz", "Ana Ruiz"),
        ):
            with self.subTest(message=message):
                self.assertEqual(nlu.parse(message), ("crear_cliente", {"nombre": expected}))

    def test_signed_money_is_not_converted_into_a_positive_charge(self):
        messages = [
            "Factura a Pedro QA por reparación -50 euros",
            "Gasté -10 euros en material",
            "Fes un tiquet per Jana de −50 euros",
            "Factura a Ana - 50 euros",
            "Factura a Ana reparación-50 euros",
            "Factura a Ana －50 euros",
            "Factura a Ana menos 50 euros",
            "Gasté (10 euros) en material",
        ]
        for message in messages:
            with self.subTest(message=message):
                self.assertEqual(inspect_money_intent(message).code, "signed_amount")
                self.assertEqual(nlu.parse(message)[0], nlu.NEED_REVIEW)

    def test_multiline_cannot_be_silently_reduced_to_first_number(self):
        messages = [
            "Crea una factura para Pedro con 2 horas a 35 euros y 3 piezas a 12,50 euros, más IVA del 21%",
            "Factura a Pedro 2 horas a 35 euros",
            "Factura a Pedro 2 filtros a 35 euros",
            "Factura a Pedro 2 x 35 euros",
            "Presupuesto a Ana 100 euros con descuento de 20 euros",
        ]
        for message in messages:
            with self.subTest(message=message):
                self.assertEqual(inspect_money_intent(message).code, "multiple_amounts")
                self.assertEqual(nlu.parse(message)[0], nlu.NEED_REVIEW)

    def test_guard_has_no_business_or_provider_effects_in_both_channels(self):
        for channel in ("web", "whatsapp"):
            with self.subTest(channel=channel), patch.object(chat, "run_tool") as tool, \
                    patch.object(chat.internal_brain, "prepare_response") as brain:
                result = chat._handle(987654, "Gasté -10 euros en material", channel=channel)
                self.assertIn("negativo", result["reply"])
                self.assertEqual(result["source"], "local")
                tool.assert_not_called()
                brain.assert_not_called()

    def test_simple_commands_and_references_are_preserved(self):
        for message in (
            "Factura a Ana por revisión 1.250,50 euros IVA 21% IRPF 15%",
            "Gasté 45 euros en gasolina",
            "Envíame el PDF de la factura DEMO-2026-008",
            "Factura a Ana por revisión 100 euros el 2026-09-15",
            "agenda a Ana mañana a las 10",
        ):
            with self.subTest(message=message):
                self.assertIsNone(inspect_money_intent(message))

    def test_real_local_chat_preserves_database_on_unsafe_orders(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(config, "DATABASE_URL", ""), \
                patch.object(config, "DB_PATH", Path(directory) / "test.db"), \
                patch.object(config, "DOCS_PATH", Path(directory) / "docs"), \
                patch.object(config, "ANTHROPIC_API_KEY", ""), \
                patch.object(config, "ASSISTANT_REVIEW_ENABLED", False), \
                patch.object(config, "ASSISTANT_LEARNING_ENABLED", False):
            db.init_db()
            business = db.create_business("Ensayo local", "qa@example.invalid")
            bid = business["id"]
            for message in ("Gasté -10 euros en material",
                            "Factura a Pedro por reparación -50 euros",
                            "Factura a Pedro con 2 horas a 35 euros y 3 piezas a 12,50 euros"):
                reply = chat.handle(bid, message)
                self.assertEqual(reply["source"], "local")
            self.assertEqual(db.list_invoices(bid), [])
            self.assertEqual(db.list_expenses(bid), [])
            self.assertEqual(db.list_clients(bid), [])
            chat.handle(bid, "Crea un cliente llamado Jana QA")
            self.assertEqual([c["name"] for c in db.list_clients(bid)], ["Jana QA"])
            chat.handle(bid, "Gasté 121 euros IVA incluido al 21% en herramientas")
            expense = db.list_expenses(bid)[0]
            self.assertEqual(expense["vat_rate"], 21)
            summary = db.month_billing(business_id=bid)
            self.assertEqual(summary["expense_base"], 100)
            self.assertEqual(summary["vat_input"], 21)


if __name__ == "__main__":
    unittest.main()
