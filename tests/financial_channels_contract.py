"""Contratos de canal real compartidos entre SQLite y PostgreSQL."""

from dataclasses import replace
from datetime import date
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
from uuid import uuid4

from noesis import config, db, action_review
from noesis.documents import repo, review
from noesis.financial_channels import ChannelContext, FinancialChannels, current
from noesis.financial_operations.contracts import (
    AccessDenied,
    ConflictError,
    EntryIdentity,
    OperationState,
    Principal,
    StateError,
)
from noesis.tools import run_tool
from noesis.web import chat, whatsapp, whatsapp_documents
from tests.borrowed_writers_contract import BorrowedWritersContract


class ChannelsContract:
    seed = BorrowedWritersContract.seed
    draft = BorrowedWritersContract.draft
    document = BorrowedWritersContract.document
    schedule = BorrowedWritersContract.schedule

    def setup_channels(self):
        self.seed()
        self.user = db.create_user(uuid4().hex + "@example.test", "hash fixture", self.bid)
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE businesses SET owner_email=? WHERE id=?", (self.user["email"], self.bid)
            )
        self.principal = Principal(self.user["id"], 0)
        self.flags = patch.object(config, "FINANCIAL_CORE_ENABLED", True)
        self.flags.start()
        self.addCleanup(self.flags.stop)

    def ctx(self, *, wa=False, message="", identity=None):
        ctx = (
            ChannelContext.whatsapp(
                self.bid,
                self.principal,
                "wamid." + uuid4().hex,
                "recipient",
                "34600111222",
                message=message,
            )
            if wa
            else ChannelContext.web(self.bid, self.principal, str(uuid4()), message=message)
        )
        return replace(ctx, identity=identity) if identity else ctx

    def intent(self, amount="12.10", **fields):
        return {
            "command": "expense.confirm",
            "target_id": None,
            "fields": {"concept": "Material", "amount": amount} | fields,
        }

    def propose(self, ctx=None, intent=None, pending=False):
        ctx = ctx or self.ctx()
        return ctx, FinancialChannels(ctx).propose(
            intent or self.intent(), pending_actor=ctx.actor if pending else None
        )

    def confirm(self, ctx, result, decision="yes", pending=None):
        return FinancialChannels(ctx).confirm(
            result["operation_uuid"],
            approved_hash=result["request_hash"],
            approved_revision=result["revision"],
            decision=decision,
            **({"pending_actor": ctx.actor, "pending_id": pending["id"]} if pending else {}),
        )

    def referencing(self, ctx, proposal):
        return replace(
            ctx,
            confirmation_target=(
                proposal["operation_uuid"],
                proposal["request_hash"],
                proposal["revision"],
            ),
        )

    def count(self, table):
        with db.get_conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) n FROM " + table + " WHERE business_id=?", (self.bid,)
            ).fetchone()["n"]

    def test_web_prepare_confirm_duplicate_refresh(self):
        ctx, p = self.propose()
        self.assertEqual(self.count("expenses"), 0)
        self.assertEqual(FinancialChannels(ctx).propose(self.intent()), p)
        yes = self.ctx()
        done = self.confirm(yes, p)
        self.assertEqual(self.confirm(yes, p), done)
        self.assertEqual(FinancialChannels(yes).replay(), done)
        self.assertEqual(self.count("financial_authorizations"), 1)
        self.assertEqual(self.count("economic_events"), 1)
        self.assertEqual(self.count("expenses"), 1)
        self.assertNotIn(p["request_hash"], p["reply"])

    def test_request_uuid_different_content_conflicts(self):
        ctx, p = self.propose()
        with self.assertRaises(ConflictError):
            FinancialChannels(ctx).propose(self.intent("13"))
        self.assertEqual(self.count("financial_operations"), 1)
        self.assertEqual(self.count("expenses"), 0)

    def test_authorization_failure_keeps_pending_and_no_authority(self):
        ctx, p = self.propose(self.ctx(wa=True, message="gasto"), pending=True)
        pending = db.get_pending_action(self.bid, ctx.actor)

        def fail(stage):
            if stage == "authorization_recorded":
                raise RuntimeError("fallo de persistencia")

        with (
            patch("noesis.financial_channels.service.checkpoint", side_effect=fail),
            self.assertRaises(RuntimeError),
        ):
            self.confirm(self.ctx(wa=True, message="sí"), p, pending=pending)
        self.assertEqual(db.get_pending_action(self.bid, ctx.actor)["id"], pending["id"])
        self.assertEqual(self.count("financial_authorizations"), 0)
        self.assertEqual(self.count("expenses"), 0)

    def test_execute_failure_after_authority_reuses_operation_without_pending(self):
        ctx, p = self.propose(self.ctx(wa=True, message="gasto"), pending=True)
        pending = db.get_pending_action(self.bid, ctx.actor)
        yes = self.ctx(wa=True, message="sí")

        def fail(stage):
            if stage == "authorization_committed":
                raise RuntimeError("crash antes del efecto")

        with (
            patch("noesis.financial_channels.service.checkpoint", side_effect=fail),
            self.assertRaises(RuntimeError),
        ):
            self.confirm(yes, p, pending=pending)
        self.assertIsNone(db.get_pending_action(self.bid, ctx.actor))
        self.assertEqual(self.count("financial_authorizations"), 1)
        self.assertEqual(self.count("expenses"), 0)
        self.assertEqual(FinancialChannels(yes).replay()["action_result"], "completed")
        self.assertEqual(self.count("financial_operations"), 1)

    def test_timeout_after_commit_recovers_result(self):
        _, p = self.propose()
        yes = self.ctx()

        def fail(stage):
            if stage == "effect_committed":
                raise RuntimeError("respuesta perdida")

        with (
            patch("noesis.financial_channels.service.checkpoint", side_effect=fail),
            self.assertRaises(RuntimeError),
        ):
            self.confirm(yes, p)
        self.assertEqual(self.count("expenses"), 1)
        self.assertEqual(FinancialChannels(yes).replay()["action_result"], "completed")
        self.assertEqual(self.count("expenses"), 1)

    def test_no_terminal_no_effect(self):
        ctx, p = self.propose(self.ctx(wa=True), pending=True)
        yes = self.ctx(wa=True, message="no")
        pending = db.get_pending_action(self.bid, ctx.actor)
        self.confirm(yes, p, "no", pending)
        self.assertEqual(FinancialChannels(yes).replay()["action_result"], "discarded")
        self.assertEqual(self.count("financial_authorizations"), 0)
        self.assertEqual(self.count("expenses"), 0)

    def test_revision_and_hash_exact_no_consume(self):
        ctx, p = self.propose(self.ctx(wa=True), pending=True)
        for key, value in [("approved_hash", "0" * 64), ("approved_revision", 99)]:
            args = {
                "approved_hash": p["request_hash"],
                "approved_revision": p["revision"],
                key: value,
            }
            with self.assertRaises(StateError):
                FinancialChannels(self.ctx(wa=True)).confirm(p["operation_uuid"], **args)
        self.assertIsNotNone(db.get_pending_action(self.bid, ctx.actor))

    def test_other_actor_business_channel_and_revoked_session_denied(self):
        ctx, p = self.propose()
        other = db.create_user(uuid4().hex + "@example.test", "hash fixture", self.bid)
        foreign = replace(ctx, principal=Principal(other["id"], 0), actor=f"web:{other['id']}:0")
        with self.assertRaises(AccessDenied):
            self.confirm(foreign, p)
        with self.assertRaises(AccessDenied):
            self.confirm(self.ctx(wa=True), p)
        with db.get_conn() as conn:
            conn.execute("UPDATE users SET session_version=1 WHERE id=?", (self.user["id"],))
        with self.assertRaises(AccessDenied):
            self.confirm(ctx, p)
        self.assertEqual(self.count("expenses"), 0)

    def test_closed_input_float_and_model_authority_rejected(self):
        for fields in (
            {"amount": 12.1},
            {"operation_uuid": str(uuid4())},
            {"approved_by_ai": True},
            {"unknown": "x"},
        ):
            with self.subTest(fields=fields), self.assertRaises((ValueError, TypeError)):
                self.propose(intent=self.intent(**fields))
        self.assertEqual(self.count("financial_operations"), 0)

    def test_tools_prepare_only_and_cannot_pick_identity_or_writer(self):
        ctx = self.ctx(wa=True, message="gasto 12.10 euros")
        token = current.set(ctx)
        try:
            result = json.loads(
                run_tool("registrar_gasto", {"concepto": "Material", "importe": "12.10"}, self.bid)
            )
            self.assertTrue(result["confirmation_required"])
            self.assertEqual(self.count("expenses"), 0)
            for name, args in [
                (
                    "registrar_gasto",
                    {"concepto": "M", "importe": "30", "operation_uuid": str(uuid4())},
                ),
                ("financial_writers.purchasing.add_expense", {}),
                ("FinancialOperations.execute", {}),
            ]:
                self.assertIn("error", json.loads(run_tool(name, args, self.bid)))
        finally:
            current.reset(token)
        self.assertIn(
            "error",
            json.loads(run_tool("registrar_gasto", {"concepto": "M", "importe": "30"}, self.bid)),
        )

    def test_correction_new_request_cancels_old_new_approval(self):
        ctx, p = self.propose(self.ctx(wa=True, message="gasto"), pending=True)
        correction = self.referencing(self.ctx(wa=True, message="sí, pero son 120 €"), p)
        token = current.set(correction)
        try:
            revised = action_review.respond(self.bid, ctx.actor, correction.message)
        finally:
            current.reset(token)
        self.assertNotEqual(revised["operation_uuid"], p["operation_uuid"])
        self.assertNotEqual(revised["request_hash"], p["request_hash"])
        self.assertIn("120.00", revised["reply"])
        self.assertEqual(
            FinancialChannels(ctx).operations.recover(self.principal, p["operation_uuid"]).state,
            OperationState.CANCELLED,
        )
        self.assertEqual(self.count("financial_authorizations"), 0)
        yes = self.referencing(self.ctx(wa=True, message="sí"), revised)
        token = current.set(yes)
        try:
            result = action_review.respond(self.bid, ctx.actor, "sí")
        finally:
            current.reset(token)
        self.assertEqual(result["action_result"], "completed")
        self.assertEqual(self.count("expenses"), 1)

    def test_pending_replaced_cannot_consume_other_proposal(self):
        ctx, p = self.propose(self.ctx(wa=True), pending=True)
        old = db.get_pending_action(self.bid, ctx.actor)
        db.set_pending_action(self.bid, ctx.actor, "other", {})
        with self.assertRaises(StateError):
            self.confirm(self.ctx(wa=True), p, pending=old)
        self.assertEqual(self.count("financial_authorizations"), 0)

    def test_old_shown_reference_and_unbound_yes_cannot_approve_current_pending(self):
        ctx, old = self.propose(self.ctx(wa=True), pending=True)
        FinancialChannels(self.ctx(wa=True)).cancel_pending()
        _, new = self.propose(self.ctx(wa=True), self.intent("31.20"), pending=True)
        pending = db.get_pending_action(self.bid, ctx.actor)
        for confirmation in (
            self.ctx(wa=True, message="sí"),
            self.referencing(self.ctx(wa=True, message="sí"), old),
        ):
            token = current.set(confirmation)
            try:
                self.assertEqual(
                    action_review.respond(self.bid, ctx.actor, "sí")["action_result"], "failed"
                )
            finally:
                current.reset(token)
        self.assertEqual(db.get_pending_action(self.bid, ctx.actor)["id"], pending["id"])
        self.assertEqual(self.count("financial_authorizations"), 0)
        self.confirm(self.ctx(wa=True), new, pending=pending)
        self.assertEqual(self.count("expenses"), 1)

    def test_duplicate_distinct_yes_recovers_exact_result_leaves_new_pending(self):
        ctx, p = self.propose(self.ctx(wa=True), pending=True)
        done = self.confirm(
            self.ctx(wa=True), p, pending=db.get_pending_action(self.bid, ctx.actor)
        )
        _, other = self.propose(self.ctx(wa=True), self.intent("31.20"), pending=True)
        pending = db.get_pending_action(self.bid, ctx.actor)
        duplicate = self.referencing(self.ctx(wa=True, message="sí"), p)
        token = current.set(duplicate)
        try:
            self.assertEqual(action_review.respond(self.bid, ctx.actor, "sí"), done)
        finally:
            current.reset(token)
        self.assertEqual(FinancialChannels(duplicate).replay(), done)
        self.assertEqual(db.get_pending_action(self.bid, ctx.actor)["id"], pending["id"])
        self.assertEqual(self.count("expenses"), 1)
        self.assertEqual(self.count("financial_authorizations"), 1)
        with self.assertRaises(ConflictError):
            FinancialChannels(self.referencing(duplicate, other)).replay()

    def test_concurrent_same_confirmation_identity_different_text_conflicts_atomically(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from noesis.purchasing_capture import ExpenseCapture

        _, proposal = self.propose()
        yes = self.ctx(message="sí")
        changed = replace(yes, message="si")
        barrier = Barrier(2)
        authorize = ExpenseCapture.authorize

        def synchronized(capture, *args, **kwargs):
            barrier.wait(timeout=15)
            return authorize(capture, *args, **kwargs)

        def confirm(context):
            try:
                return self.confirm(context, proposal)["action_result"]
            except ConflictError:
                return "conflict"

        with (
            patch.object(ExpenseCapture, "authorize", synchronized),
            ThreadPoolExecutor(max_workers=2) as workers,
        ):
            results = list(workers.map(confirm, [yes, changed]))
        self.assertCountEqual(results, ["completed", "conflict"])
        self.assertEqual(self.count("expenses"), 1)
        self.assertEqual(self.count("financial_authorizations"), 1)

    def test_whatsapp_quote_binds_only_own_business_phone_and_exact_review(self):
        from noesis.financial_channels.whatsapp import bind_reply, review_key

        ctx, p = self.propose(self.ctx(wa=True), pending=True)
        row = whatsapp.queue_text(
            ctx.actor[3:], p["reply"], business_id=self.bid, idempotency_key=review_key(p)
        )
        db.claim_next_whatsapp_message(
            now=db._now(), stale_before="2000-01-01", only_ids=[row["id"]]
        )
        db.mark_whatsapp_sent(row["id"], "wamid.bound", db._now())
        yes = self.ctx(wa=True, message="sí")
        bound = bind_reply(yes, "wamid.bound")
        self.assertEqual(
            bound.confirmation_target, (p["operation_uuid"], p["request_hash"], p["revision"])
        )
        for other in (
            replace(yes, actor="wa:34600999999"),
            replace(yes, business_id=self.bid + 1000),
        ):
            self.assertIsNone(bind_reply(other, "wamid.bound").confirmation_target)
        self.assertIsNone(bind_reply(yes, "wamid.unknown").confirmation_target)
        self.assertIsNone(bind_reply(yes, None).confirmation_target)
        self.assertEqual(self.count("expenses"), 0)

    def test_new_intent_cancels_prepared_before_removing_pending(self):
        ctx, p = self.propose(self.ctx(wa=True), pending=True)
        next_turn = self.ctx(wa=True, message="otra orden")
        FinancialChannels(next_turn).cancel_pending()
        self.assertEqual(
            FinancialChannels(ctx).operations.recover(self.principal, p["operation_uuid"]).state,
            OperationState.CANCELLED,
        )
        self.assertIsNone(db.get_pending_action(self.bid, ctx.actor))
        with self.assertRaises(StateError):
            self.confirm(self.ctx(wa=True), p)
        self.assertEqual(self.count("expenses"), 0)

    def test_durable_identity_not_text_and_changed_message_conflicts(self):
        a, p = self.propose(self.ctx(wa=True, message="gasto 12 €"))
        b, q = self.propose(self.ctx(wa=True, message="gasto 12 €"))
        self.assertNotEqual(a.identity, b.identity)
        self.assertNotEqual(p["operation_uuid"], q["operation_uuid"])
        self.assertEqual(FinancialChannels(a).replay(), p)
        with self.assertRaises(ConflictError):
            FinancialChannels(replace(a, message="gasto 30 €")).replay()

    def test_document_correction_new_review_identity_and_classification_stale(self):
        doc = self.document()
        review_id = str(uuid4())
        ctx = self.ctx(identity=EntryIdentity.reviewed_document(review_id, doc, 1, 1))
        ctx, p = self.propose(ctx, self.intent(document_id=doc))
        with self.assertRaises(StateError):
            FinancialChannels(ctx).execute(p["operation_uuid"])
        repo.record_classification(
            doc, self.bid, detected_kind="contrato", confidence=None, method="human"
        )
        with self.assertRaises(StateError):
            self.confirm(self.ctx(), p)
        revised = self.ctx(identity=EntryIdentity.reviewed_document(review_id, doc, 1, 2))
        _, new = self.propose(revised, self.intent("13", document_id=doc))
        self.confirm(self.ctx(), new)
        self.assertEqual(self.count("economic_events"), 1)
        self.assertEqual(repo.get(doc, self.bid)["expense_id"], db.list_expenses(self.bid)[0]["id"])

    def test_document_ocr_no_auto_authority_and_pdf_batch_denied(self):
        doc = self.document()
        self.assertEqual(self.count("economic_events"), 0)
        repo.record_classification(
            doc, self.bid, detected_kind="ticket", confidence=None, method="pdf_batch"
        )
        with self.assertRaises(StateError):
            self.propose(intent=self.intent(document_id=doc))

    def test_wa_document_first_yes_prepares_exact_second_yes_executes(self):
        doc = self.document()
        phone = "34600111222"
        item = review.new_item(
            fields={"total": "12.10", "supplier": "Ferretería"},
            kind="ticket",
            business=self.business,
            document_id=doc,
        )
        payload = {"items": [item], "index": 0, "document_id": doc}
        whatsapp_documents._save(self.bid, phone, payload)
        ctx = self.ctx(wa=True, message="sí")
        token = current.set(ctx)
        try:
            reply = whatsapp_documents.handle_reply(db.get_business(self.bid), phone, "sí")
        finally:
            current.reset(token)
        self.assertIn("Registrar gasto", reply)
        self.assertEqual(self.count("expenses"), 0)
        self.assertIn("Registrar gasto", FinancialChannels(ctx).replay()["reply"])
        yes = self.referencing(self.ctx(wa=True, message="sí"), FinancialChannels(ctx).replay())
        token = current.set(yes)
        try:
            done = action_review.respond(self.bid, yes.actor, "sí")
        finally:
            current.reset(token)
        self.assertEqual(done["action_result"], "completed")
        self.assertEqual(self.count("economic_events"), 1)

    def test_recurring_auto_issue_never_authority_and_retry_no_duplicate(self):
        schedule = self.schedule(auto_issue=True)
        first = db.process_due_recurring_invoices()
        self.assertEqual(len(first), 1)
        self.assertEqual(db.get_invoice(first[0]["id"], self.bid)["status"], "borrador")
        self.assertEqual(self.count("economic_events"), 0)
        db.process_due_recurring_invoices()
        self.assertEqual(self.count("invoices"), 1)
        self.assertEqual(self.count("financial_operations"), 1)
        from noesis.financial_channels.recurring import occurrence_for_invoice

        identity, rc = occurrence_for_invoice(self.bid, first[0]["id"])
        ctx = self.ctx(identity=identity)
        p = FinancialChannels(ctx).propose(
            {"command": "invoice.issue", "target_id": first[0]["id"], "fields": {}},
            recurring_context=rc,
        )
        self.confirm(self.ctx(), p)
        self.assertEqual(self.count("economic_events"), 1)
        self.assertEqual(identity, EntryIdentity.recurring(schedule["id"], date.today()))

    def test_web_uuid_alias_of_recurring_review_is_bound_and_not_authority(self):
        self.schedule(auto_issue=True)
        invoice = db.process_due_recurring_invoices()[0]
        from noesis.financial_channels.recurring import occurrence_for_invoice

        identity, rc = occurrence_for_invoice(self.bid, invoice["id"])
        web = self.ctx()
        mapped = replace(web, identity=identity, transport_identity=web.identity)
        p = FinancialChannels(mapped).propose(
            {"command": "invoice.issue", "target_id": invoice["id"], "fields": {}},
            recurring_context=rc,
        )
        self.assertEqual(FinancialChannels(web).replay(), p)
        self.assertEqual(self.count("financial_authorizations"), 0)
        with self.assertRaises(ConflictError):
            FinancialChannels(web).propose(self.intent())
        with self.assertRaises(ConflictError):
            self.confirm(web, p)
        self.confirm(self.ctx(), p)
        self.assertEqual(self.count("economic_events"), 1)

    def test_recurring_changed_or_paused_denies_exact_approval(self):
        for changed in ("name", "status"):
            schedule = self.schedule(auto_issue=True)
            generated = db.process_due_recurring_invoices()[0]
            with db.get_conn() as conn:
                op = conn.execute(
                    "SELECT operation_uuid FROM financial_operations WHERE business_id=? AND request_canonical LIKE ?",
                    (self.bid, '%"target_id":' + str(generated["id"]) + "}%"),
                ).fetchone()
            bridge = FinancialChannels(self.ctx())
            p = bridge.response(bridge.operations.recover(self.principal, op["operation_uuid"]))
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE recurring_invoices SET " + changed + "=? WHERE business_id=? AND id=?",
                    ("paused" if changed == "status" else "Cambio", self.bid, schedule["id"]),
                )
            with self.assertRaises(StateError):
                self.confirm(self.ctx(), p)
        self.assertEqual(self.count("economic_events"), 0)

    def test_real_whatsapp_webhook_retry_confirmation_and_response_loss(self):
        phone = "34600111222"
        db.set_whatsapp_status(self.bid, "conectado", phone="600111222")
        request = {
            "from": phone,
            "recipient_phone_id": "recipient",
            "id": "wamid." + uuid4().hex,
            "text": "gasto 12.10 euros",
        }

        def interpret(*args, **kwargs):
            return json.loads(
                run_tool("registrar_gasto", {"concepto": "Material", "importe": "12.10"}, self.bid)
            )

        outgoing = []

        def send(to, text, **kwargs):
            row = whatsapp.queue_text(
                to,
                text,
                business_id=kwargs.get("business_id"),
                idempotency_key=kwargs.get("idempotency_key"),
            )
            meta_id = "wamid.out." + str(row["id"])
            db.claim_next_whatsapp_message(
                now=db._now(), stale_before="2000-01-01", only_ids=[row["id"]]
            )
            db.mark_whatsapp_sent(row["id"], meta_id, db._now())
            outgoing.append(meta_id)
            return True

        with (
            patch.object(whatsapp, "_PHONE_ID", "recipient"),
            patch.object(whatsapp, "send", side_effect=send),
            patch.object(chat, "_handle", side_effect=interpret),
        ):
            whatsapp.handle_inbound(request)
            self.assertTrue(whatsapp.handle_inbound(request)["results"][0]["duplicate"])
            yes = request | {"id": "wamid." + uuid4().hex, "text": "sí", "reply_to": outgoing[0]}
            with (
                patch.object(whatsapp, "send", side_effect=RuntimeError("Meta caído")),
                self.assertRaises(RuntimeError),
            ):
                whatsapp.handle_inbound(yes)
            whatsapp.handle_inbound(yes)
            self.assertTrue(whatsapp.handle_inbound(yes)["results"][0]["duplicate"])
            whatsapp.handle_inbound(yes | {"id": "wamid." + uuid4().hex})
        self.assertEqual(self.count("expenses"), 1)
        self.assertEqual(self.count("financial_operations"), 1)
        self.assertEqual(self.count("financial_authorizations"), 1)

    def test_chat_real_turn_replay_without_model_and_isolated_yes(self):
        actor = f"{self.user['id']}:0"
        ctx = ChannelContext.web(
            self.bid, self.principal, str(uuid4()), chat=True, message="gasto 12.10 euros"
        )

        def interpret(*args, **kwargs):
            return json.loads(
                run_tool("registrar_gasto", {"concepto": "M", "importe": "12.10"}, self.bid)
            )

        with patch.object(chat, "_handle", side_effect=interpret) as model:
            p = chat.handle(self.bid, ctx.message, actor_id=actor, financial_context=ctx)
            again = chat.handle(self.bid, ctx.message, actor_id=actor, financial_context=ctx)
            self.assertEqual(p, again)
            self.assertEqual(model.call_count, 1)
            yes = ChannelContext.web(
                self.bid, self.principal, str(uuid4()), chat=True, message="sí"
            )
            yes = self.referencing(yes, p)
            done = chat.handle(self.bid, "sí", actor_id=actor, financial_context=yes)
            self.assertEqual(
                done, chat.handle(self.bid, "sí", actor_id=actor, financial_context=yes)
            )
        self.assertEqual(self.count("expenses"), 1)

    def test_invoice_and_partial_payment_channels_use_exact_capture(self):
        invoice = self.draft()
        _, p = self.propose(
            intent={"command": "invoice.issue", "target_id": invoice["id"], "fields": {}}
        )
        self.assertIn("Cliente", p["reply"])
        self.assertIn("IVA", p["reply"])
        self.assertIsInstance(p["revision"], str)
        operation = FinancialChannels(self.ctx()).operations.recover(
            self.principal, p["operation_uuid"]
        )
        self.assertEqual(p["revision"], str(operation.request.expected_revision))
        self.confirm(self.ctx(), p)
        _, payment = self.propose(
            intent={
                "command": "customer_payment.record",
                "target_id": invoice["id"],
                "fields": {"amount": "12.10", "method": "transferencia", "mode": "partial"},
            }
        )
        self.assertIn("12.10", payment["reply"])
        self.confirm(self.ctx(), payment)
        self.assertEqual(self.count("economic_events"), 2)
        self.assertEqual(self.count("invoice_payments"), 1)

    def test_supplier_correct_void_expense_void_all_capture(self):
        _, p = self.propose(
            intent={
                "command": "supplier_invoice.confirm",
                "target_id": None,
                "fields": {"supplier_name": "Proveedor", "total": "121"},
            }
        )
        done = self.confirm(self.ctx(), p)
        sid = done["result"]["source_id"]
        _, p = self.propose(
            intent={
                "command": "supplier_invoice.correct",
                "target_id": sid,
                "fields": {"reason": "Total revisado", "total": "130"},
            }
        )
        self.confirm(self.ctx(), p)
        _, p = self.propose(
            intent={
                "command": "supplier_invoice.void",
                "target_id": sid,
                "fields": {"reason": "Retirada"},
            }
        )
        self.confirm(self.ctx(), p)
        _, p = self.propose()
        done = self.confirm(self.ctx(), p)
        _, p = self.propose(
            intent={
                "command": "expense.void",
                "target_id": done["result"]["source_id"],
                "fields": {"reason": "Retirada"},
            }
        )
        self.confirm(self.ctx(), p)
        self.assertEqual(self.count("economic_events"), 5)
        self.assertEqual(db.list_expenses(self.bid), [])
        self.assertEqual(db.list_received_invoices(self.bid), [])

    def test_unauthorized_unknown_type_and_fiscal_cancel_disconnected(self):
        for command in (
            "quote.accepted",
            "job.completed",
            "supplier_payment.made",
            "invoice.fiscal_cancel",
        ):
            with self.assertRaises((ValueError, StateError)):
                self.propose(intent={"command": command, "target_id": None, "fields": {}})
        self.assertEqual(self.count("economic_events"), 0)

    def test_http_double_submit_refresh_conflict_csrf_foreign_and_expired(self):
        import base64
        import time
        from itsdangerous import TimestampSigner
        from starlette.testclient import TestClient
        from noesis.web import server

        http = TestClient(server.app, base_url="https://testserver")
        self.addCleanup(http.close)

        def cookie(seen=None):
            raw = base64.b64encode(
                json.dumps(
                    {"uid": self.user["id"], "sv": 0, "seen": seen or int(time.time())}
                ).encode()
            )
            return TimestampSigner(config.SECRET_KEY).sign(raw).decode()

        cookie_name = "__Host-noesis_session" if config.IS_PRODUCTION else "noesis_session"
        http.cookies.set(cookie_name, cookie())
        path = f"/api/{self.bid}/financial-actions"
        body = {"action_uuid": str(uuid4()), "intent": self.intent()}
        p = http.post(path + "/prepare", json=body)
        self.assertEqual(p.status_code, 200, p.text)
        self.assertEqual(http.post(path + "/prepare", json=body).json(), p.json())
        changed = body | {"intent": self.intent("13")}
        self.assertEqual(http.post(path + "/prepare", json=changed).status_code, 409)
        self.assertEqual(
            http.post(
                path + "/prepare", json=body, headers={"Origin": "https://evil.example"}
            ).status_code,
            403,
        )
        self.assertEqual(
            http.post(
                f"/api/{self.bid + 1000000}/financial-actions/prepare", json=body
            ).status_code,
            403,
        )
        self.assertEqual(
            http.post(
                f"/api/{self.bid}/expenses", json={"amount": "12", "concept": "M"}
            ).status_code,
            409,
        )
        confirmation = {
            "action_uuid": str(uuid4()),
            "operation_uuid": p.json()["operation_uuid"],
            "request_hash": p.json()["request_hash"],
            "revision": p.json()["revision"],
            "decision": "yes",
        }
        done = http.post(path + "/confirm", json=confirmation)
        self.assertEqual(done.status_code, 200, done.text)
        self.assertEqual(http.post(path + "/confirm", json=confirmation).json(), done.json())
        self.assertEqual(http.get(path + "/" + confirmation["operation_uuid"]).json(), done.json())
        invoice = self.draft()
        issue = http.post(
            path + "/prepare",
            json={
                "action_uuid": str(uuid4()),
                "intent": {"command": "invoice.issue", "target_id": invoice["id"], "fields": {}},
            },
        )
        self.assertEqual(issue.status_code, 200, issue.text)
        reviewed = issue.json()
        self.assertIsInstance(reviewed["revision"], str)
        issued = http.post(
            path + "/confirm",
            json={
                "action_uuid": str(uuid4()),
                "operation_uuid": reviewed["operation_uuid"],
                "request_hash": reviewed["request_hash"],
                "revision": reviewed["revision"],
                "decision": "yes",
            },
        )
        self.assertEqual(issued.status_code, 200, issued.text)
        self.assertEqual(issued.json()["action_result"], "completed")
        http.cookies.clear()
        http.cookies.set(
            cookie_name, cookie(int(time.time()) - config.SESSION_IDLE_MINUTES * 60 - 10)
        )
        self.assertEqual(http.post(path + "/confirm", json=confirmation).status_code, 401)
        self.assertEqual(self.count("expenses"), 1)

    def test_bank_csv_upload_only_prepares_rows_then_exact_confirmation(self):
        from dataclasses import replace
        from noesis.bank_capture.service import BankCapture

        content = b"fecha;importe;concepto\n2026-10-02;12,10;Movimiento\n"
        batch = str(uuid4())
        ctx = self.ctx()
        rows = BankCapture(self.bid).review_csv(
            self.principal, content, batch_uuid=batch, account_scope="cuenta-1"
        )
        self.assertEqual(len(rows), 1)
        identity, r = rows[0]
        p = r.parameters
        fields = dict(p["movement"]) | {
            "batch_uuid": batch,
            "row_key": p["row"],
            "account_scope": p["account_scope"],
            "statement_hash": p["statement_hash"],
        }
        _, proposed = self.propose(
            replace(ctx, identity=identity),
            {"command": "bank_transaction.import", "target_id": None, "fields": fields},
        )
        self.assertEqual(self.count("bank_transactions"), 0)
        yes = self.ctx()
        self.confirm(yes, proposed)
        self.assertEqual(self.count("bank_transactions"), 1)
        self.assertEqual(FinancialChannels(yes).replay()["action_result"], "completed")
        self.assertEqual(self.count("bank_transactions"), 1)

    def test_expired_proposal_and_changed_source_require_new_review(self):
        _, p = self.propose()
        with (
            patch(
                "noesis.financial_channels.service._now", return_value="9999-01-01T00:00:00+00:00"
            ),
            self.assertRaises(StateError),
        ):
            self.confirm(self.ctx(), p)
        invoice = self.draft()
        _, p = self.propose(
            intent={"command": "invoice.issue", "target_id": invoice["id"], "fields": {}}
        )
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE invoices SET concept=? WHERE business_id=? AND id=?",
                ("Cambio", self.bid, invoice["id"]),
            )
        with self.assertRaises(StateError):
            self.confirm(self.ctx(), p)
        self.assertEqual(self.count("economic_events"), 0)

    def http_client(self, principal=None):
        import base64
        import time
        from itsdangerous import TimestampSigner
        from starlette.testclient import TestClient
        from noesis.web import server
        principal = principal or self.principal
        http = TestClient(server.app, base_url="https://testserver")
        self.addCleanup(http.close)
        raw = base64.b64encode(json.dumps({"uid": principal.user_id, "sv": principal.session_version,
                                          "seen": int(time.time())}).encode())
        name = "__Host-noesis_session" if config.IS_PRODUCTION else "noesis_session"
        http.cookies.set(name, TimestampSigner(config.SECRET_KEY).sign(raw).decode())
        return http

    def test_committed_recovery_current_session_only_and_immutable_authority(self):
        _, p = self.propose()
        yes = self.ctx()
        done = self.confirm(yes, p)
        _, prepared = self.propose()
        _, approved = self.propose()
        def stop(stage):
            if stage == "authorization_committed":
                raise RuntimeError("antes del efecto")
        with patch("noesis.financial_channels.service.checkpoint", side_effect=stop), self.assertRaises(RuntimeError):
            self.confirm(self.ctx(), approved)
        with db.get_conn() as conn:
            history = {t: [dict(r) for r in conn.execute("SELECT * FROM " + t + " WHERE business_id=?",
                                                       (self.bid,)).fetchall()]
                       for t in ("financial_authorizations", "financial_channel_proposals")}
            conn.execute("UPDATE users SET session_version=1 WHERE id=?", (self.user["id"],))
        renewed = ChannelContext.web(self.bid, Principal(self.user["id"], 1), str(uuid4()))
        bridge = FinancialChannels(renewed)
        with patch("noesis.purchasing_capture.service.purchasing.add_expense", side_effect=AssertionError("writer")):
            self.assertEqual(bridge.response(bridge.operations.recover(renewed.principal, p["operation_uuid"])), done)
            http = self.http_client(renewed.principal)
            path = f"/api/{self.bid}/financial-actions/"
            self.assertEqual(http.get(path + p["operation_uuid"]).json(), done)
            for pending in (prepared, approved):
                with self.assertRaises(AccessDenied):
                    bridge.response(bridge.operations.recover(renewed.principal, pending["operation_uuid"]))
                self.assertEqual(http.get(path + pending["operation_uuid"]).status_code, 403)
            with self.assertRaises(AccessDenied):
                FinancialChannels(yes).operations.recover(yes.principal, p["operation_uuid"])
            self.assertEqual(self.http_client().get(path + p["operation_uuid"]).status_code, 401)
            colleague = db.create_user(uuid4().hex + "@example.test", "hash fixture", self.bid)
            other = FinancialChannels(ChannelContext.web(self.bid, Principal(colleague["id"], 0), str(uuid4())))
            with self.assertRaises(AccessDenied):
                other.response(bridge.operations.recover(renewed.principal, p["operation_uuid"]))
            with self.assertRaises(AccessDenied):
                FinancialChannels(replace(renewed, business_id=self.bid + 1000000)).response(
                    bridge.operations.recover(renewed.principal, p["operation_uuid"]))
        with db.get_conn() as conn:
            after = {t: [dict(r) for r in conn.execute("SELECT * FROM " + t + " WHERE business_id=?",
                                                     (self.bid,)).fetchall()] for t in history}
        self.assertEqual(history, after)
        self.assertEqual(self.count("expenses"), 1)

    def propose_invoice_channel(self, channel, invoice_id):
        from noesis.financial_channels.tools import propose_tool
        intent = {"command": "invoice.issue", "target_id": invoice_id, "fields": {}}
        if channel == "web":
            response = self.http_client().post(f"/api/{self.bid}/financial-actions/prepare",
                json={"action_uuid": str(uuid4()), "intent": intent})
            if response.status_code != 200:
                raise StateError(response.text)
            return response.json(), None
        ctx = (self.ctx(wa=True, message="emite factura") if channel == "whatsapp" else
               ChannelContext.web(self.bid, self.principal, str(uuid4()), chat=True, message="emite factura"))
        phone = f"6{self.bid:08d}"
        if channel == "whatsapp":
            ctx = replace(ctx, actor="wa:34" + phone)
        proposals = []
        def interpret(*args, **kwargs):
            proposal = propose_tool(self.bid, "enviar_factura", {"factura_id": invoice_id})
            proposals.append(proposal)
            return proposal
        with patch.object(chat, "_handle", side_effect=interpret):
            if channel == "whatsapp":
                db.set_whatsapp_status(self.bid, "conectado", phone=phone)
                with patch.object(whatsapp, "_PHONE_ID", "recipient"), patch.object(whatsapp, "send", return_value=True):
                    whatsapp.handle_inbound({"from": "34" + phone, "recipient_phone_id": "recipient",
                        "id": "wamid." + uuid4().hex, "text": ctx.message})
            else:
                chat.handle(self.bid, ctx.message, actor_id=f"{self.user['id']}:0", financial_context=ctx)
        return proposals[0], ctx

    def test_recurring_resolution_all_channels_converge_and_transport_receipts(self):
        self.schedule()
        iid = db.process_due_recurring_invoices()[0]["id"]
        proposals = []
        for channel in ("web", "chat", "whatsapp"):
            p, ctx = self.propose_invoice_channel(channel, iid)
            proposals.append(p)
            if ctx:
                self.assertIsNotNone(db.get_pending_action(self.bid, ctx.actor))
        self.assertEqual(len({p["operation_uuid"] for p in proposals}), 1)
        self.assertEqual(self.count("financial_operations"), 1)
        with db.get_conn() as conn:
            op = conn.execute("SELECT * FROM financial_operations WHERE business_id=?", (self.bid,)).fetchone()
            receipts = conn.execute("SELECT channel FROM financial_channel_receipts WHERE business_id=?",
                                    (self.bid,)).fetchall()
        self.assertEqual(op["entry_namespace"], "recurring")
        self.assertTrue({"web_api", "chat", "whatsapp"} <= {r["channel"] for r in receipts})
        self.assertEqual(self.count("financial_authorizations"), 0)
        self.assertEqual(self.count("economic_events"), 0)
        # Revisión en WhatsApp no cambia la autoridad; su SÍ exacto sí ejecuta una vez.
        self.confirm(self.ctx(wa=True, message="sí"), proposals[-1])
        self.assertEqual(self.count("economic_events"), 1)

    def test_recurring_invalid_origin_fails_closed_in_every_channel(self):
        for problem in ("paused", "changed", "legacy"):
            schedule = self.schedule()
            iid = db.process_due_recurring_invoices()[0]["id"]
            with db.get_conn() as conn:
                if problem == "legacy":
                    conn.execute("UPDATE recurring_invoice_runs SET financial_template_hash=NULL "
                                 "WHERE business_id=? AND invoice_id=?", (self.bid, iid))
                else:
                    field = "status" if problem == "paused" else "name"
                    conn.execute("UPDATE recurring_invoices SET " + field + "=? WHERE business_id=? AND id=?",
                                 (problem, self.bid, schedule["id"]))
            for channel in ("web", "chat", "whatsapp"):
                with self.subTest(problem=problem, channel=channel), self.assertRaises(StateError):
                    self.propose_invoice_channel(channel, iid)
            # Evita que el siguiente vencimiento recoja esta propuesta aún borrador.
            with db.get_conn() as conn:
                conn.execute("UPDATE recurring_invoices SET status='paused' WHERE business_id=? AND id=?",
                             (self.bid, schedule["id"]))
        self.assertEqual(self.count("financial_operations"), 3)
        self.assertEqual(self.count("financial_authorizations"), 0)
        self.assertEqual(self.count("economic_events"), 0)

    def test_nonrecurring_invoice_keeps_channel_identity(self):
        for channel in ("web", "chat", "whatsapp"):
            with self.subTest(channel=channel):
                p, _ = self.propose_invoice_channel(channel, self.draft()["id"])
                with db.get_conn() as conn:
                    row = conn.execute("SELECT channel,recurring_context FROM financial_channel_proposals "
                                       "WHERE business_id=? AND operation_uuid=?", (self.bid, p["operation_uuid"])).fetchone()
                self.assertEqual(row["channel"], "web_api" if channel == "web" else channel)
                self.assertIsNone(row["recurring_context"])

    def test_old_ordinary_recurring_proposal_cannot_authorize(self):
        from noesis.financial_writers import recurring
        schedule = self.schedule()
        with db.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            invoice = recurring.generate_cycle(conn, schedule["id"], self.bid, date.today().isoformat(),
                legacy=True, draft_only=True).legacy_value()
        # Simula el bridge anterior: run real, pero propuesta ordinaria sin contexto.
        with patch("noesis.financial_channels.recurring.occurrence_for_invoice", return_value=None):
            _, p = self.propose(intent={"command": "invoice.issue", "target_id": invoice["id"], "fields": {}})
        with self.assertRaises(StateError):
            self.confirm(self.ctx(), p)
        self.assertEqual(self.count("financial_authorizations"), 0)
        self.assertEqual(self.count("economic_events"), 0)

    def test_expired_recurring_proposal_rejected_by_all_channels(self):
        self.schedule()
        iid = db.process_due_recurring_invoices()[0]["id"]
        with patch("noesis.financial_channels.service._now", return_value="2099-01-01T00:00:00+00:00"):
            for channel in ("web", "chat", "whatsapp"):
                with self.subTest(channel=channel), self.assertRaises(StateError):
                    self.propose_invoice_channel(channel, iid)
        self.assertEqual(self.count("financial_operations"), 1)
        self.assertEqual(self.count("financial_authorizations"), 0)
        self.assertEqual(self.count("economic_events"), 0)

    def worker(self, mode, ctx=None, p=None, crash=None):
        from noesis.invoice_capture.service import PRODUCER_CONFIG

        ctx = ctx or self.ctx()
        args = {
            "mode": mode,
            "business_id": self.bid,
            "user_id": self.user["id"],
            "namespace": ctx.identity.namespace.value,
            "key": ctx.identity.key,
            "actor": ctx.actor,
            "message": ctx.message,
            "proposal": p,
            "crash": crash,
            "producer": {name: getattr(config, name) for name in PRODUCER_CONFIG},
        }
        env = dict(
            os.environ,
            NOESIS_DATABASE_URL=config.DATABASE_URL,
            DATABASE_URL=config.DATABASE_URL,
            NOESIS_DB_PATH=str(config.DB_PATH),
            NOESIS_FINANCIAL_CORE_ENABLED="true",
        )
        return subprocess.Popen(
            [sys.executable, "-m", "tests.financial_channels_worker", json.dumps(args)],
            cwd=Path(__file__).parents[1],
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def run_workers(self, workers, expected=0):
        try:
            for w in workers:
                self.assertEqual(w.stdout.readline().strip(), "READY")
            for w in workers:
                w.stdin.write("go\n")
                w.stdin.flush()
            result = []
            for w in workers:
                out, err = w.communicate(timeout=60)
                self.assertEqual(w.returncode, expected, err)
                result.append(json.loads(out) if out.strip() else None)
            return result
        finally:
            for w in workers:
                if w.poll() is None:
                    w.kill()
                w.communicate()

    def test_processes_same_confirmation_one_authorization_effect(self):
        _, p = self.propose()
        yes = self.ctx()
        result = self.run_workers([self.worker("confirm", yes, p), self.worker("confirm", yes, p)])
        self.assertEqual(result[0], result[1])
        self.assertEqual(self.count("expenses"), 1)
        self.assertEqual(self.count("financial_authorizations"), 1)

    def test_restart_crash_after_authorization_and_after_commit(self):
        for stage in ("authorization_committed", "mutation", "effect_committed"):
            _, p = self.propose(self.ctx(wa=True, message="gasto 12.10 euros"))
            yes = self.ctx(wa=True, message="sí")
            self.run_workers([self.worker("confirm", yes, p, stage)], 73)
            result = self.run_workers([self.worker("replay", yes, p)])[0]
            self.assertEqual(result["action_result"], "completed")
        self.assertEqual(self.count("expenses"), 3)
        self.assertEqual(self.count("financial_operations"), 3)

    def test_process_crash_preparation_atomic_and_durable_after_commit(self):
        ctx = self.ctx(wa=True, message="gasto 12.10 euros")
        self.run_workers([self.worker("propose", ctx, crash="prepared")], 73)
        self.assertEqual(self.count("financial_operations"), 0)
        self.assertEqual(self.count("financial_channel_proposals"), 0)
        self.run_workers([self.worker("propose", ctx, crash="proposal_committed")], 73)
        response = self.run_workers([self.worker("replay", ctx)])[0]
        self.assertTrue(response["confirmation_required"])
        self.assertEqual(self.count("financial_operations"), 1)
        self.assertEqual(self.count("expenses"), 0)

    def test_rectification_channel_and_bank_match_existing_producers(self):
        invoice = self.draft()
        _, p = self.propose(
            intent={"command": "invoice.issue", "target_id": invoice["id"], "fields": {}}
        )
        self.confirm(self.ctx(), p)
        rectified = db.create_rectifying_invoice(
            invoice["id"], self.bid, concept="Corrección", base="-10", reason="Importe corregido"
        )
        _, p = self.propose(
            intent={"command": "invoice.rectify", "target_id": rectified["id"], "fields": {}}
        )
        self.confirm(self.ctx(), p)
        batch = str(uuid4())
        identity = EntryIdentity.imported(batch, "1")
        _, p = self.propose(
            self.ctx(identity=identity),
            {
                "command": "bank_transaction.import",
                "target_id": None,
                "fields": {
                    "batch_uuid": batch,
                    "row_key": "1",
                    "account_scope": "cuenta-1",
                    "statement_hash": "a" * 64,
                    "booked_on": date.today().isoformat(),
                    "amount": "12.10",
                    "description": "Cobro",
                },
            },
        )
        movement = self.confirm(self.ctx(), p)["result"]["bank_transaction_id"]
        db.suggest_bank_transaction(
            movement, self.bid, invoice["id"], score=100, reason="Correspondencia revisada"
        )
        _, p = self.propose(
            intent={"command": "bank_transaction.match", "target_id": movement, "fields": {}}
        )
        self.confirm(self.ctx(), p)
        self.assertEqual(self.count("invoice_payments"), 1)
        self.assertEqual(self.count("economic_events"), 5)

    def test_schema_channel_evidence_immutable_and_downgrade_preserves(self):
        from noesis import migrations

        ctx, p = self.propose()
        self.confirm(self.ctx(), p)
        for table in ("financial_channel_proposals", "financial_channel_receipts"):
            for sql in (
                "UPDATE " + table + " SET request_hash=request_hash WHERE business_id=?",
                "DELETE FROM " + table + " WHERE business_id=?",
            ):
                with self.assertRaises(Exception):
                    with db.get_conn() as conn:
                        conn.execute(sql, (self.bid,))
        with self.assertRaises(ValueError):
            migrations.downgrade(67)
        self.assertEqual(self.count("financial_channel_receipts"), 2)

    def test_processes_recurring_one_draft_occurrence(self):
        self.schedule(auto_issue=True)
        self.run_workers([self.worker("recurring"), self.worker("recurring")])
        self.assertEqual(self.count("invoices"), 1)
        self.assertEqual(self.count("recurring_invoice_runs"), 1)
        self.assertEqual(self.count("financial_operations"), 1)
        self.assertEqual(self.count("economic_events"), 0)

    def test_worker_next_occurrence_and_human_emission_share_lock_order(self):
        from datetime import timedelta
        from noesis.financial_channels.recurring import occurrence_for_invoice

        schedule = self.schedule(auto_issue=True)
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE recurring_invoices SET next_run_on=? WHERE business_id=? AND id=?",
                ((date.today() - timedelta(days=40)).isoformat(), self.bid, schedule["id"]),
            )
        invoice = db.process_due_recurring_invoices()[0]
        identity, rc = occurrence_for_invoice(self.bid, invoice["id"])
        mapped = self.ctx(identity=identity)
        p = FinancialChannels(mapped).propose(
            {"command": "invoice.issue", "target_id": invoice["id"], "fields": {}},
            recurring_context=rc,
        )
        self.run_workers([self.worker("confirm", self.ctx(), p), self.worker("recurring")])
        self.assertEqual(self.count("invoices"), 2)
        self.assertEqual(self.count("economic_events"), 1)

    def test_recurring_process_crash_before_and_after_draft_commit(self):
        self.schedule(auto_issue=True)
        self.run_workers([self.worker("recurring", crash="recurring_before_prepare")], 73)
        self.assertEqual(self.count("invoices"), 0)
        self.run_workers([self.worker("recurring", crash="recurring_draft_committed")], 73)
        self.assertEqual(self.count("invoices"), 1)
        self.assertEqual(self.count("financial_operations"), 0)
        self.run_workers([self.worker("recurring")])
        self.assertEqual(self.count("financial_operations"), 1)
        self.assertEqual(self.count("economic_events"), 0)

    def test_recurring_changed_after_authorization_before_execute_denied(self):
        schedule = self.schedule(auto_issue=True)
        invoice = db.process_due_recurring_invoices()[0]
        from noesis.financial_channels.recurring import occurrence_for_invoice

        identity, rc = occurrence_for_invoice(self.bid, invoice["id"])
        ctx = self.ctx(identity=identity)
        p = FinancialChannels(ctx).propose(
            {"command": "invoice.issue", "target_id": invoice["id"], "fields": {}},
            recurring_context=rc,
        )
        yes = self.ctx()

        def fail(stage):
            if stage == "authorization_committed":
                raise RuntimeError("crash")

        with (
            patch("noesis.financial_channels.service.checkpoint", side_effect=fail),
            self.assertRaises(RuntimeError),
        ):
            self.confirm(yes, p)
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE recurring_invoices SET status=? WHERE business_id=? AND id=?",
                ("paused", self.bid, schedule["id"]),
            )
        with self.assertRaises(StateError):
            FinancialChannels(yes).replay()
        self.assertEqual(self.count("economic_events"), 0)
