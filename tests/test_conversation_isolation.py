"""Memoria por actor, sin asignar el pasado ni mezclar canales."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from starlette.requests import Request

from noesis import agent, config, db, migrations
from noesis.conversation_context import current
from noesis.web import chat
from noesis.web.routers.assistant import api_chat_history
from tests import test_conversation_safety as fixtures


class ConversationIsolationTests(unittest.TestCase):
    setUp = fixtures.ConversationSafetyTests.setUp
    tearDown = fixtures.ConversationSafetyTests.tearDown

    def enable(self):
        self.stack.enter_context(patch.object(config, "CONVERSATION_ISOLATION_ENABLED", True))

    def test_old_history_remains_available_but_is_not_attributed(self):
        db.add_assistant_message(self.bid, "user", "Histórico sin propietario")
        self.enable()
        self.assertEqual(db.list_conversation_messages(self.bid, actor="web:owner"), [])
        self.assertEqual(len(db.list_assistant_messages(self.bid)), 1)

    def test_web_and_whatsapp_history_stays_separate(self):
        self.enable()
        chat.handle(self.bid, "qué tengo hoy", actor_id="alice")
        chat.handle(self.bid, "cuánto me deben", channel="whatsapp", actor_phone="34600111222")
        web = db.list_conversation_messages(self.bid, actor="web:alice")
        wa = db.list_conversation_messages(self.bid, actor="wa:34600111222")
        self.assertEqual(len(web), 2)
        self.assertEqual(len(wa), 2)
        self.assertEqual(web[0]["content"], "qué tengo hoy")
        self.assertEqual(wa[0]["content"], "cuánto me deben")
        self.assertIsNone(current.get())

    def test_client_reference_uses_only_current_actor(self):
        self.enable()
        db.add_client("Ana Ruiz", business_id=self.bid)
        db.add_assistant_message(self.bid, "user", "Marta López", actor="web:alice")
        db.add_assistant_message(self.bid, "user", "Ana Ruiz", actor="web:bob")
        token = current.set((self.bid, "web:alice"))
        try:
            self.assertEqual(chat._client_from_conversation(self.bid)["id"], self.client["id"])
            first = chat._conversation_agent_key(self.bid)
        finally:
            current.reset(token)
        token = current.set((self.bid, "web:bob"))
        try:
            self.assertNotEqual(chat._conversation_agent_key(self.bid), first)
        finally:
            current.reset(token)

    def test_empty_context_clears_cached_agent_history(self):
        self.enable()
        cached = SimpleNamespace(business_id=self.bid, messages=[{"role": "user", "content": "otro"}])
        agent._refresh_conversation(cached)
        self.assertEqual(cached.messages, [])

    def test_two_named_clients_are_ambiguous(self):
        self.enable()
        db.add_client("Ana Ruiz", business_id=self.bid)
        db.add_assistant_message(self.bid, "user", "Marta López y Ana Ruiz", actor="web:alice")
        token = current.set((self.bid, "web:alice"))
        try:
            self.assertIsNone(chat._client_from_conversation(self.bid))
        finally:
            current.reset(token)

    def test_business_scope_is_required_even_with_same_actor(self):
        self.enable()
        other = db.create_business("Otro", "other@example.test")["id"]
        db.add_assistant_message(self.bid, "user", "privado", actor="web:alice")
        self.assertEqual(db.list_conversation_messages(other, actor="web:alice"), [])

    def test_flag_off_preserves_legacy_history(self):
        db.add_assistant_message(self.bid, "user", "anterior", actor="web:bob")
        with patch.object(config, "CONVERSATION_ISOLATION_ENABLED", False):
            self.assertEqual(len(db.list_conversation_messages(self.bid, actor="web:alice")), 1)

    def test_history_route_uses_authenticated_session(self):
        self.enable()
        db.add_assistant_message(self.bid, "user", "mío", actor="web:7:2")
        db.add_assistant_message(self.bid, "user", "otro", actor="web:8:2")
        request = Request({"type": "http", "session": {"uid": 7, "sv": 2}})
        self.assertEqual([r["content"] for r in api_chat_history(self.bid, request)["items"]], ["mío"])

    def test_disposable_database_can_downgrade_to_zero_and_upgrade(self):
        self.assertEqual(migrations.downgrade(0), 0)
        self.assertEqual(migrations.upgrade(), migrations.LATEST_VERSION)

    def test_rollback_keeps_actor_and_allows_upgrade(self):
        db.add_assistant_message(self.bid, "user", "conservado", actor="web:alice")
        migrations.downgrade(58)
        self.assertEqual(db.list_assistant_messages(self.bid)[0]["actor"], "web:alice")
        migrations.upgrade()
        self.enable()
        self.assertEqual(len(db.list_conversation_messages(self.bid, actor="web:alice")), 1)
