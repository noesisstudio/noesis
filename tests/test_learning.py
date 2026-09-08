"""El aprendizaje mejora interpretación, nunca permisos ni autonomía."""
import json
import unittest
from unittest.mock import patch

from noesis import config, db, learning, agent
from noesis.web import chat, whatsapp
from tests import test_conversation_safety as fixtures


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ConversationSafetyTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.bid = self.fixture.bid
        self.client = self.fixture.client
        self.patch = patch.object(config, "ASSISTANT_LEARNING_ENABLED", True)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def say(self, text, actor="owner"):
        return chat.handle(self.bid, text, actor_id=actor)

    def offer(self, actor="owner"):
        self.say("lo del carburante de siempre", actor)
        self.say("corregir: gasté 35 euros en gasolina", actor)
        return self.say("sí", actor)

    def teach(self):
        self.offer()
        return self.say("aprender")

    def test_unknown_is_honest_and_never_writes(self):
        result = self.say("lo del carburante de siempre")
        self.assertTrue(result["needs_clarification"])
        self.assertEqual(db.list_expenses(self.bid), [])
        self.assertEqual(learning.rules(self.bid), [])

    def test_correction_only_offers_learning_after_successful_confirmation(self):
        self.say("lo del carburante de siempre")
        self.say("corregir: gasté 35 euros en gasolina")
        self.say("aprender")
        self.assertEqual(learning.rules(self.bid), [])
        self.assertEqual(db.list_expenses(self.bid), [])

    def test_completed_action_does_not_silently_create_memory(self):
        result = self.offer()
        self.assertIn("APRENDER", result["reply"])
        self.assertEqual(learning.rules(self.bid), [])
        self.assertEqual(len(db.list_expenses(self.bid)), 1)

    def test_approved_expression_still_requires_confirmation_each_time(self):
        self.teach()
        result = self.say("lo del carburante de siempre")
        self.assertTrue(result["confirmation_required"])
        self.assertIn("expresión que aprobaste", result["reply"])
        self.assertEqual(len(db.list_expenses(self.bid)), 1)
        self.say("sí")
        self.say("sí")
        self.assertEqual(len(db.list_expenses(self.bid)), 2)

    def test_no_discards_offer(self):
        self.offer()
        self.say("no")
        self.say("aprender")
        self.assertEqual(learning.rules(self.bid), [])

    def test_rules_are_private_and_another_actor_cannot_approve(self):
        self.offer("alice")
        self.say("aprender", "bob")
        self.assertEqual(learning.rules(self.bid), [])
        self.say("aprender", "alice")
        other = db.create_business("Other", "other-learning@example.test")["id"]
        response = chat.handle(other, "lo del carburante de siempre")
        self.assertTrue(response["needs_clarification"])
        self.assertEqual(learning.rules(other), [])

    def test_forget_is_scoped_and_stops_reuse(self):
        self.teach()
        row = learning.rules(self.bid)[0]
        other = db.create_business("Other", "forget@example.test")["id"]
        chat.handle(other, f"olvidar expresión {row['id']}")
        self.assertEqual(len(learning.rules(self.bid)), 1)
        self.say(f"olvidar expresión {row['id']}")
        self.assertEqual(learning.rules(self.bid), [])
        self.assertTrue(self.say("lo del carburante de siempre")["needs_clarification"])

    def test_expired_offer_cannot_be_approved(self):
        self.offer()
        with db.get_conn() as conn:
            conn.execute("UPDATE whatsapp_pending_actions SET expires_at='2000-01-01' WHERE business_id=?", (self.bid,))
        self.say("aprender")
        self.assertEqual(learning.rules(self.bid), [])

    def test_refusals_and_existing_commands_cannot_be_overridden(self):
        for phrase, command in (("borra el gasto 5", "gasté 5 euros"), ("gasté 5 euros", "gasté 99 euros"), ("llama al banco", "transferir 500 euros")):
            with self.assertRaises(ValueError):
                learning._validate(phrase, command)

    def test_relative_dates_and_money_confirmation_are_not_learned(self):
        for command in ("agenda a Marta mañana para revisar", "emitir factura 1", "Marta ha pagado factura 1"):
            with self.assertRaises(ValueError):
                learning._validate("expresión desconocida", command)

    def test_corrupt_or_changed_rule_does_not_execute(self):
        self.teach()
        row = db.list_memories(self.bid, scope_type=learning.SCOPE)[0]
        payload = json.loads(row["memory_value"])
        payload["command"] = "gasté 999 euros en gasolina"
        db.remember(self.bid, row["memory_key"], json.dumps(payload), scope_type=learning.SCOPE, user_confirmed=True)
        result = self.say("lo del carburante de siempre")
        self.assertTrue(result["needs_clarification"])
        self.assertEqual(len(db.list_expenses(self.bid)), 1)

    def test_language_rules_never_enter_model_system_prompt(self):
        self.teach()
        prompt = agent._system_with_business_context(self.bid, db.get_business(self.bid))
        self.assertNotIn("carburante", prompt)
        self.assertNotIn("phrase_", prompt)

    def test_feature_flags_preserve_legacy_and_never_learn_without_review(self):
        with patch.object(config, "ASSISTANT_REVIEW_ENABLED", False):
            self.assertFalse(learning.enabled())
            self.say("lo del carburante de siempre")
        with patch.object(config, "ASSISTANT_LEARNING_ENABLED", False):
            self.assertFalse(learning.enabled())
            self.assertNotIn("needs_clarification", self.say("lo del carburante de siempre"))
        self.assertEqual(learning.rules(self.bid), [])

    def test_report_has_no_message_contents_or_fake_accuracy(self):
        self.teach()
        result = learning.report(self.bid)
        self.assertEqual(result["events"]["completed"], 1)
        self.assertEqual(result["events"]["rule_approved"], 1)
        self.assertNotIn("carburante", json.dumps(result))
        with db.get_conn() as conn:
            rows = conn.execute("SELECT event_data FROM product_events WHERE business_id=? AND event_name LIKE 'assistant_learning_%'", (self.bid,)).fetchall()
        self.assertTrue(all(row["event_data"] == '{"version":1}' for row in rows))

    def test_telemetry_failure_does_not_repeat_action(self):
        self.say("gasté 35 euros en gasolina")
        with patch.object(learning, "observe", side_effect=RuntimeError("telemetry")):
            self.say("sí")
        self.say("sí")
        self.assertEqual(len(db.list_expenses(self.bid)), 1)

    def test_guided_invoice_preserves_client_concept_and_gross_total(self):
        self.assertIn("qué cliente", self.say("quiero una factura")["reply"])
        self.say("Marta López")
        self.say("reparar la caldera")
        bad = self.say("121")
        self.assertTrue(bad["needs_clarification"])
        result = self.say("121 euros IVA incluido")
        self.assertTrue(result["confirmation_required"])
        self.assertEqual(db.list_invoices(self.bid), [])
        self.say("sí")
        invoice = db.list_invoices(self.bid)[0]
        self.assertEqual(invoice["client_id"], self.client["id"])
        self.assertEqual(invoice["concept"], "reparar la caldera")
        self.assertEqual(float(invoice["total"]), 121)

    def test_guided_invoice_ambiguity_never_chooses_customer(self):
        db.add_client("Marta García", business_id=self.bid)
        self.say("quiero una factura")
        result = self.say("Marta")
        self.assertIn("varios clientes", result["reply"])
        self.say("sí")
        self.assertEqual(db.list_invoices(self.bid), [])

    def test_guided_state_isolated_between_actors_and_cancelled(self):
        self.say("quiero una factura", "alice")
        result = self.say("Marta López", "bob")
        self.assertNotIn("Qué trabajo", result["reply"])
        self.say("no", "alice")
        self.assertIsNone(db.get_pending_action(self.bid, "clarify:web:alice"))

    def test_whatsapp_learning_uses_same_contract(self):
        db.set_whatsapp_status(self.bid, "conectado", phone="600000000")
        with patch.object(whatsapp, "send"):
            for i, text in enumerate(("lo del carburante de siempre", "corregir: gasté 35 euros en gasolina", "sí", "aprender", "lo del carburante de siempre", "no")):
                whatsapp.handle_inbound({"from": "34600000000", "id": f"learn-qa-{i}", "text": text})
        self.assertEqual(len(learning.rules(self.bid)), 1)
        self.assertEqual(len(db.list_expenses(self.bid)), 1)
