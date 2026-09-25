"""Correcciones completas, atómicas y sin llamadas a proveedores."""
import unittest

from noesis import action_review, db
from tests import test_correcciones as fixtures


class CompoundCorrectionsTests(unittest.TestCase):
    setUp = fixtures._Base.setUp
    tearDown = fixtures._Base.tearDown
    wa = fixtures._Base.wa
    propuesta = fixtures._Base.propuesta

    def test_amount_customer_concept_and_tax_are_one_proposal(self):
        self.propuesta()
        reply = self.wa("no, eran 120,50 euros y el cliente es Pedro; concepto: reparación; IVA 10%; IRPF 15%")
        self.assertIn("Pedro", reply)
        self.assertEqual(db.list_invoices(self.bid), [])
        self.wa("sí")
        invoice = db.list_invoices(self.bid)[0]
        self.assertEqual(invoice["base"], 120.5)
        self.assertEqual(invoice["total"], 114.47)
        self.assertEqual(db.get_invoice_lines(invoice["id"], self.bid)[0]["description"], "reparación")
        self.assertEqual(db.get_client(invoice["client_id"], self.bid)["name"], "Pedro")

    def test_unsupported_part_cannot_confirm_old_amount(self):
        self.propuesta()
        reply = self.wa("no, eran 120; IVA 13%")
        self.assertIn("todos los cambios", reply)
        self.wa("sí")
        self.assertEqual(db.list_invoices(self.bid), [])

    def test_tax_question_does_not_change_pending_proposal(self):
        self.propuesta()
        before = db.get_pending_action(self.bid, "wa:34600111222")
        self.wa("¿Por qué IVA 10%?")
        after = db.get_pending_action(self.bid, "wa:34600111222")
        self.assertEqual(before["payload"], after["payload"])

    def test_tax_fragment_in_instruction_is_not_a_correction(self):
        for text in ("envía la factura con IVA 10% a Pedro", "qué significa IVA incluido",
                     "no pongas IVA 10%", "IVA 10% y borra la factura", "¿IVA 10%?"):
            with self.subTest(text=text):
                self.assertIsNone(action_review._correccion(text, "crear_factura", {"base": 100}))

    def test_name_conjunction_and_decimal_remain_intact(self):
        result = action_review._correccion("es para Pedro y Ana", "crear_factura", {"base": 100})
        self.assertEqual(result["cliente"], "Pedro y Ana")
        result = action_review._correccion("120,50 euros y IVA 10%", "crear_factura", {})
        self.assertEqual(result["base"], 120.5)
        self.assertEqual(result["iva"], 10)

    def test_other_actor_cannot_correct_the_proposal(self):
        self.propuesta()
        result = action_review.respond(self.bid, "wa:34600999999", "120 euros y IVA 10%")
        self.assertIsNone(result)
        self.wa("sí")
        self.assertEqual(db.list_invoices(self.bid)[0]["base"], 100)
