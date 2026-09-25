"""Entrada persistente: orden, duplicados, caída incierta y aislamiento de rutas."""
import unittest
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from starlette.requests import Request

from noesis import config, db, migrations
from noesis.web import whatsapp_inbox as inbox
from noesis.web.routers import webhooks
from tests import test_conversation_safety as fixtures


class WhatsappInboxTests(unittest.TestCase):
    setUp = fixtures.ConversationSafetyTests.setUp
    tearDown = fixtures.ConversationSafetyTests.tearDown

    def payload(self, identifier="m1", phone="34600111222"):
        return {"id": identifier, "from": phone, "text": "hola"}

    def rows(self):
        with db.get_conn() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM whatsapp_ingress ORDER BY id").fetchall()]

    def test_ack_only_persists_then_worker_processes_once(self):
        with patch.object(inbox.whatsapp, "handle_inbound", return_value={}) as handle:
            self.assertEqual(inbox.accept(self.payload())["accepted"], 1)
            self.assertEqual(inbox.accept(self.payload())["accepted"], 0)
            handle.assert_not_called()
            with patch.object(config, "WHATSAPP_INBOX_ENABLED", True):
                self.assertEqual(inbox.process(), 1)
                self.assertEqual(inbox.process(), 0)
            handle.assert_called_once()
        self.assertEqual(self.rows()[0]["payload"], "{}")

    def test_flag_off_does_not_consume(self):
        inbox.accept(self.payload())
        with patch.object(config, "WHATSAPP_INBOX_ENABLED", False):
            self.assertEqual(inbox.process(), 0)
        self.assertEqual(self.rows()[0]["status"], "queued")

    def test_recovery_is_admin_scoped_audited_and_never_replays_uncertain_work(self):
        user = db.create_user("operator@example.test", "unused", self.bid)
        with patch.object(inbox, "_business", return_value=self.bid):
            inbox.accept(self.payload())
        row = db.claim_whatsapp_inbound()
        db.finish_whatsapp_inbound(row["id"], error_code="routing_changed")
        with self.assertRaises(ValueError):
            db.recover_whatsapp_inbound(self.bid, row["id"], operator_id=user["id"])
        with db.get_conn() as conn:
            conn.execute("UPDATE users SET is_admin=1 WHERE id=?", (user["id"],))
        with self.assertRaises(ValueError):
            db.recover_whatsapp_inbound(self.bid + 1, row["id"], operator_id=user["id"])
        db.recover_whatsapp_inbound(self.bid, row["id"], operator_id=user["id"])
        self.assertEqual(self.rows()[0]["status"], "queued")
        self.assertTrue(db.list_security_events(event_types=("admin.whatsapp_recovery_requested",)))
        row = db.claim_whatsapp_inbound()
        db.finish_whatsapp_inbound(row["id"], error_code="processing_failed")
        with self.assertRaises(ValueError):
            db.recover_whatsapp_inbound(self.bid, row["id"], operator_id=user["id"])
        self.assertEqual(self.rows()[0]["status"], "review")

    def test_diagnostics_are_scoped_private_and_read_only(self):
        with patch.object(inbox, "_business", return_value=self.bid):
            inbox.accept(self.payload("m1"))
            inbox.accept(self.payload("m2"))
        row = db.claim_whatsapp_inbound()
        db.finish_whatsapp_inbound(row["id"], error_code="processing_failed")
        before = self.rows()
        report = db.whatsapp_ingress_diagnostics(self.bid)
        self.assertEqual(report["counts"], {"queued": 1, "review": 1})
        self.assertEqual(report["incidents"][0]["waiting_after"], 1)
        encoded = json.dumps(report)
        for private in ("34600111222", "hola", "payload", "conversation_key", "event_key"):
            self.assertNotIn(private, encoded)
        self.assertEqual(db.whatsapp_ingress_diagnostics(self.bid + 10000)["incidents"], [])
        self.assertEqual(before, self.rows())
        self.assertEqual(db.whatsapp_ingress_diagnostics(self.bid, limit=10000)["limit"], 200)

    def test_capacity_accepts_duplicates_and_rolls_back_new_batch(self):
        events = [{"business_id": self.bid, "event_key": f"capacity-{i}",
                   "conversation_key": "capacity", "payload": {}} for i in range(10000)]
        self.assertEqual(db.enqueue_whatsapp_inbound(events), 10000)
        self.assertEqual(db.enqueue_whatsapp_inbound(events[:2]), 0)
        with self.assertRaisesRegex(ValueError, "saturada"):
            db.enqueue_whatsapp_inbound([{**events[0], "event_key": "overflow"}])
        self.assertEqual(len(self.rows()), 10000)

    def test_uncertain_failure_blocks_only_its_conversation(self):
        for identifier, phone in (("m1", "111"), ("m2", "111"), ("m3", "222")):
            inbox.accept(self.payload(identifier, phone))
        with patch.object(config, "WHATSAPP_INBOX_ENABLED", True), patch.object(
            inbox.whatsapp, "handle_inbound", side_effect=[RuntimeError("secret"), {}]
        ) as handle:
            self.assertEqual(inbox.process(), 2)
            self.assertEqual(handle.call_count, 2)
        rows = self.rows()
        self.assertEqual([row["status"] for row in rows], ["review", "queued", "done"])
        self.assertNotIn("secret", rows[0]["error_code"])
        self.assertTrue(any("entrada(s)" in a["text"] for a in db.admin_alerts()))

    def test_two_consumers_cannot_claim_same_conversation(self):
        inbox.accept(self.payload("m1"))
        inbox.accept(self.payload("m2"))
        with ThreadPoolExecutor(max_workers=2) as pool:
            claimed = list(pool.map(lambda _: db.claim_whatsapp_inbound(), range(2)))
        self.assertEqual(sum(row is not None for row in claimed), 1)

    def test_abandoned_claim_is_reviewed_not_retried(self):
        inbox.accept(self.payload())
        row = db.claim_whatsapp_inbound()
        with db.get_conn() as conn:
            conn.execute("UPDATE whatsapp_ingress SET locked_at=? WHERE id=?", ("2000-01-01T00:00:00", row["id"]))
        self.assertIsNone(db.claim_whatsapp_inbound())
        self.assertEqual(self.rows()[0]["status"], "review")

    def test_pending_queue_blocks_rollback(self):
        inbox.accept(self.payload())
        with self.assertRaisesRegex(ValueError, "pendiente"):
            migrations.downgrade(59)
        self.assertEqual(migrations.current_version(), 60)

    def test_same_message_different_recipient_is_not_coalesced(self):
        inbox.accept({**self.payload(), "recipient_phone_id": "one"})
        inbox.accept({**self.payload(), "recipient_phone_id": "two"})
        self.assertEqual(len(self.rows()), 2)

    def test_missing_id_is_not_acknowledged(self):
        with self.assertRaises(ValueError):
            inbox.accept(self.payload(""))
        self.assertEqual(self.rows(), [])

    def test_routing_change_is_not_delivered_to_new_business(self):
        with patch.object(inbox, "_business", return_value=self.bid):
            inbox.accept(self.payload())
        with patch.object(config, "WHATSAPP_INBOX_ENABLED", True), patch.object(
            inbox, "_business", return_value=None
        ), patch.object(inbox.whatsapp, "handle_inbound") as handle:
            inbox.process()
            handle.assert_not_called()
        self.assertEqual(self.rows()[0]["error_code"], "routing_changed")

    def request(self):
        async def receive():
            return {"type": "http.request", "body": json.dumps(self.payload()).encode()}
        return Request({"type": "http", "method": "POST", "headers": []}, receive)

    def test_invalid_signature_never_enters_queue(self):
        with patch.object(config, "WHATSAPP_INBOX_ENABLED", True), patch.object(
            inbox.whatsapp, "verify_signature", return_value=False
        ):
            response = asyncio.run(webhooks.whatsapp_inbound(self.request()))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.rows(), [])

    def test_router_acknowledges_only_after_persistence(self):
        with patch.object(config, "WHATSAPP_INBOX_ENABLED", True), patch.object(
            inbox.whatsapp, "verify_signature", return_value=True
        ), patch.object(inbox.whatsapp, "handle_inbound") as handle:
            result = asyncio.run(webhooks.whatsapp_inbound(self.request()))
            self.assertEqual(result["status"], "queued")
            handle.assert_not_called()
        self.assertEqual(len(self.rows()), 1)

    def test_router_keeps_legacy_path_when_flag_disabled(self):
        with patch.object(config, "WHATSAPP_INBOX_ENABLED", False), patch.object(
            inbox.whatsapp, "verify_signature", return_value=True
        ), patch.object(inbox.whatsapp, "handle_inbound", return_value={"processed": 1}) as handle:
            result = asyncio.run(webhooks.whatsapp_inbound(self.request()))
            self.assertEqual(result["processed"], 1)
            handle.assert_called_once()
        self.assertEqual(self.rows(), [])

    def test_meta_envelope_preserves_document_and_reply_context(self):
        payload = {"entry": [{"id": "waba", "changes": [{"value": {
            "metadata": {"phone_number_id": "destination"},
            "messages": [{"id": "mid", "from": "111", "type": "document",
                          "context": {"id": "previous"},
                          "document": {"id": "media", "mime_type": "application/pdf", "filename": "a.pdf"}}]
        }}]}]}
        inbox.accept(payload)
        with patch.object(config, "WHATSAPP_INBOX_ENABLED", True), patch.object(
            inbox.whatsapp, "handle_inbound", return_value={}
        ) as handle:
            inbox.process()
        message = handle.call_args.args[0]
        self.assertEqual(message["reply_to"], "previous")
        self.assertEqual(message["media_document_id"], "media")
        self.assertEqual(message["waba_id"], "waba")
