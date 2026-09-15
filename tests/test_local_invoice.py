"""Cerebro local: propuesta, corrección, confirmación y aislamiento sin APIs."""
import json
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from noesis import config, db, local_invoice
from noesis.web import chat
from tests import test_conversation_safety as fixtures

ORDER = "Crea una factura para Marta López con 2 horas de trabajo a 35 euros y 3 piezas a 12,50 euros, más IVA del 21%"


class LocalInvoiceTests(unittest.TestCase):
    setUp = fixtures.ConversationSafetyTests.setUp
    tearDown = fixtures.ConversationSafetyTests.tearDown
    say = fixtures.ConversationSafetyTests.say

    def enable(self):
        self.stack.enter_context(patch.object(config, "LOCAL_PLANNER_ENABLED", True))

    def test_parser_is_precise_and_has_no_effects(self):
        plan = local_invoice.parse(ORDER)
        self.assertEqual(plan.client, "Marta López")
        self.assertEqual(str(plan.lines[1].unit_price), "12.50")
        self.assertEqual(len(plan.lines), 2)
        self.assertEqual(db.list_invoices(self.bid), [])
        for invalid in (ORDER + " y envíala a otro cliente", ORDER.replace("35 euros", "-35 euros"),
                        ORDER.replace("más IVA del 21%", "IVA incluido"),
                        ORDER.replace("2 horas", "2e3 horas"), "No " + ORDER,
                        ORDER.replace("21%", "13%"), ORDER.replace("35 euros", "NaN euros")):
            with self.subTest(invalid=invalid):
                self.assertIsNone(local_invoice.parse(invalid))

    def test_disabled_default_preserves_guard(self):
        with patch.object(config, "LOCAL_PLANNER_ENABLED", False):
            self.assertFalse(local_invoice.enabled())
            self.assertNotIn("confirmation_required", self.say(ORDER))
            self.assertEqual(db.list_invoices(self.bid), [])
        self.enable()
        with patch.object(config, "ASSISTANT_REVIEW_ENABLED", False):
            self.assertFalse(local_invoice.enabled())
            self.say(ORDER)
            self.assertEqual(db.list_invoices(self.bid), [])

    def test_proposal_correction_and_confirmation_keep_exact_lines(self):
        self.enable()
        first = self.say(ORDER)
        self.assertTrue(first["confirmation_required"])
        self.assertIn("130,08", first["reply"])
        self.assertEqual(db.list_invoices(self.bid), [])
        revised = self.say("No, las piezas eran 4")
        self.assertTrue(revised["confirmation_required"])
        self.assertNotEqual(first["proposal_id"], revised["proposal_id"])
        self.assertIn("145,20", revised["reply"])
        self.assertEqual(db.list_invoices(self.bid), [])
        self.say("sí")
        invoice = db.list_invoices(self.bid)[0]
        self.assertEqual(invoice["total"], 145.2)
        self.assertEqual(invoice["status"], "borrador")
        lines = db.get_invoice_lines(invoice["id"], self.bid)
        self.assertEqual([x["quantity"] for x in lines], [2, 4])
        self.say("sí")
        self.assertEqual(len(db.list_invoices(self.bid)), 1)

    def test_explicit_price_revision_and_unknown_line(self):
        self.enable()
        self.say(ORDER)
        revised = self.say("cambia la linea 2 precio a 15 euros")
        self.assertIn("139,15", revised["reply"])
        self.say("cambia linea 9 cantidad a 2")
        self.say("sí")
        self.assertEqual(db.list_invoices(self.bid), [])

    def test_client_change_resolves_existing_identity(self):
        self.enable()
        other = db.add_client("Ana Ruiz", business_id=self.bid)
        self.say(ORDER)
        revised = self.say("cambia el cliente a Ana Ruiz")
        self.assertIn("Ana Ruiz", revised["reply"])
        self.say("sí")
        self.assertEqual(db.list_invoices(self.bid)[0]["client_id"], other["id"])

    def test_unknown_customer_never_creates_a_customer(self):
        self.enable()
        self.say(ORDER.replace("Marta López", "Desconocida"))
        self.say("sí")
        self.assertEqual(len(db.list_clients(self.bid)), 1)
        self.assertEqual(db.list_invoices(self.bid), [])

    def test_correction_cannot_cross_actors_or_businesses(self):
        self.enable()
        first = self.say(ORDER, actor="alice")
        self.say("No, las piezas eran 4", actor="bob")
        self.say("sí", actor="bob")
        other = db.create_business("Otra", "other@example.invalid")["id"]
        chat.handle(other, "sí", actor_id="alice")
        self.assertIsNone(db.revise_pending_action(other, "web:alice", first["proposal_id"], {}))
        self.assertIsNone(db.revise_pending_action(self.bid, "web:bob", first["proposal_id"], {}))
        self.say("sí", actor="alice")
        self.assertEqual(db.list_invoices(self.bid)[0]["total"], 130.08)
        self.assertEqual(db.list_invoices(other), [])

    def test_old_revision_cannot_replace_current_proposal(self):
        self.enable()
        first = self.say(ORDER)
        payload = json.loads(db.get_pending_action(self.bid, "web:owner")["payload"])
        second = self.say("No, las piezas eran 4")
        self.assertIsNone(db.revise_pending_action(self.bid, "web:owner", first["proposal_id"], payload))
        db.discard_pending_action_version(self.bid, "web:owner", first["proposal_id"])
        self.assertEqual(db.get_pending_action(self.bid, "web:owner")["id"], second["proposal_id"])

    def test_concurrent_confirmations_create_only_one_invoice(self):
        self.enable()
        self.say(ORDER)
        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(lambda _: self.say("sí"), range(2)))
        self.assertEqual(len(db.list_invoices(self.bid)), 1)

    def test_whatsapp_shared_chat_keeps_proposal_and_correction(self):
        self.enable()
        kwargs = {"channel": "whatsapp", "actor_phone": "34600111222"}
        result = chat.handle(self.bid, ORDER, **kwargs)
        self.assertTrue(result["confirmation_required"])
        chat.handle(self.bid, "No, las piezas eran 4", **kwargs)
        chat.handle(self.bid, "sí", **kwargs)
        self.assertEqual(db.list_invoices(self.bid)[0]["total"], 145.2)

    def test_catalan_and_ticket_limit(self):
        self.enable()
        result = self.say("Fes una factura per a Marta López amb 2 hores a 35 euros i 3 peces a 12,50 euros més IVA del 21%")
        self.assertIn("130,08", result["reply"])
        self.say("no")
        result = self.say(ORDER.replace("factura", "ticket").replace("35 euros", "350 euros"))
        self.assertNotIn("confirmation_required", result)
        self.say("sí")
        self.assertEqual(db.list_invoices(self.bid), [])

    def test_web_pdf_and_issue_use_scoped_document(self):
        self.enable()
        self.say(ORDER)
        self.say("sí")
        invoice = db.list_invoices(self.bid)[0]
        reply = self.say("pásame el PDF")
        self.assertEqual(reply["pdf_url"], f"/api/{self.bid}/invoices/{invoice['id']}/pdf")
        self.assertIn("borrador", reply["reply"])
        other_actor = self.say("pásame el PDF", actor="another")
        self.assertNotIn("pdf_url", other_actor)
        self.assertNotIn("pdf_url", self.say("pásame el PDF de la factura 999999"))
        proposed = self.say("emítela")
        self.assertTrue(proposed["confirmation_required"])
        self.assertEqual(db.get_invoice(invoice["id"], self.bid)["status"], "borrador")

    def test_expired_focus_does_not_use_any_other_invoice(self):
        self.enable()
        self.say(ORDER)
        self.say("sí")
        with db.get_conn() as conn:
            conn.execute("UPDATE whatsapp_pending_actions SET expires_at=? WHERE business_id=? AND phone=?",
                         ("2000-01-01T00:00:00", self.bid, "local-invoice:web:owner"))
        self.assertNotIn("pdf_url", self.say("pásame el PDF"))

    def test_correction_expiry_is_not_extended(self):
        self.enable()
        self.say(ORDER)
        old = db.get_pending_action(self.bid, "web:owner")
        self.say("No, las piezas eran 4")
        new = db.get_pending_action(self.bid, "web:owner")
        self.assertEqual(new["expires_at"], old["expires_at"])

    def test_failed_confirmation_is_not_retried(self):
        self.enable()
        self.say(ORDER)
        with patch("noesis.tools.run_tool", side_effect=ValueError("fallo simulado")):
            self.assertEqual(self.say("sí")["action_result"], "failed")
        self.say("sí")
        self.assertEqual(db.list_invoices(self.bid), [])

    def test_whatsapp_transport_keeps_invoice_focus_after_confirmation(self):
        from noesis.web import whatsapp
        self.enable()
        db.set_whatsapp_status(self.bid, "conectado", phone="600111222")
        with patch.object(whatsapp, "send") as send:
            for index, text in enumerate((ORDER, "No, las piezas eran 4", "sí")):
                whatsapp.handle_inbound({"from": "34600111222", "id": f"local-{index}", "text": text})
        invoice = db.list_invoices(self.bid)[0]
        self.assertEqual(invoice["total"], 145.2)
        self.assertEqual(send.call_args.kwargs["invoice_id"], invoice["id"])
