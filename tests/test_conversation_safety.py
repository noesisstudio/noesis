"""Regresiones de errores reales: intención, identidad, revisión y repetición."""
import json
import asyncio
from io import BytesIO
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch
from starlette.requests import Request
from starlette.datastructures import UploadFile

from noesis import config, db, nlu, action_review
from noesis.tools import run_tool
from noesis.web import chat


class ConversationSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.stack = ExitStack()
        for key, value in {"DB_PATH": Path(self.temp.name) / "qa.db", "DOCS_PATH": Path(self.temp.name) / "docs", "DATABASE_URL": "", "ASSISTANT_REVIEW_ENABLED": True, "ANTHROPIC_API_KEY": ""}.items():
            self.stack.enter_context(patch.object(config, key, value))
        self.stack.enter_context(patch("noesis.web.chat.ai_adapter.local_available", return_value=False))
        self.stack.enter_context(patch("noesis.web.chat.ai_adapter.external_available", return_value=False))
        db.init_db()
        self.bid = db.create_business("QA", "qa@example.test")["id"]
        self.client = db.add_client("Marta López", business_id=self.bid)

    def tearDown(self):
        self.stack.close()
        self.temp.cleanup()

    def say(self, text, actor="owner"):
        return chat.handle(self.bid, text, actor_id=actor)

    def test_destructive_negative_and_queries_never_create_expenses(self):
        for text in ("Borra el gasto 5", "cambia el gasto 5", "no he gastado 5 euros", "ver gasto 5", "¿cuántos gastos tengo en 2026?"):
            self.say(text)
        self.assertEqual(db.list_expenses(self.bid), [])

    def test_tax_suffix_preserves_identity_and_concept(self):
        reply = self.say("Factura a Marta López por revisión 121 euros IVA incluido")
        self.assertIn("121,00", reply["reply"])
        self.assertIn("Marta López", reply["reply"])
        self.assertEqual(db.list_invoices(self.bid), [])
        self.say("sí")
        invoice = db.list_invoices(self.bid)[0]
        self.assertEqual(invoice["client_id"], self.client["id"])
        self.assertEqual(invoice["concept"], "revisión")
        self.assertEqual(float(invoice["total"]), 121)
        self.assertEqual(len(db.list_clients(self.bid)), 1)

        # La vista previa debe respetar el IRPF cero por defecto de los tickets,
        # aunque el negocio use retención en sus facturas completas.
        with db.get_conn() as conn:
            conn.execute("UPDATE businesses SET default_irpf=15 WHERE id=?", (self.bid,))
        reply = self.say("ticket de venta a Marta López 121 euros por revisión")
        self.assertIn("IRPF 0%", reply["reply"])
        self.say("sí")
        ticket = next(inv for inv in db.list_invoices(self.bid) if inv["invoice_type"] == "F2")
        self.assertEqual(float(ticket["total"]), 121)
        self.assertEqual(float(ticket["irpf_rate"]), 0)

    def test_invalid_tax_is_not_replaced_with_default(self):
        result = self.say("factura a Marta por revisión 100 euros IVA 22%")
        self.assertIn("no está admitido", result["reply"])
        self.assertEqual(db.list_invoices(self.bid), [])

    def test_missing_client_never_creates_las(self):
        result = self.say("Agenda en Badalona mañana a las 10")
        self.assertIn("Me falta", result["reply"])
        self.say("sí")
        self.assertEqual(len(db.list_clients(self.bid)), 1)

    def test_agenda_keeps_description_and_confirmed_client(self):
        result = self.say("agenda a marta lópez mañana para reparar la caldera")
        self.assertIn("reparar la caldera", result["reply"])
        self.say("sí")
        jobs = db.jobs_for_date(nlu.parse_date("mañana")[:10], self.bid)
        self.assertEqual(jobs[0]["description"], "reparar la caldera")
        self.assertEqual(jobs[0]["client_id"], self.client["id"])

    def test_unknown_or_ambiguous_client_never_creates_implicit_record(self):
        self.say("factura a Martta por revisión 100 euros")
        self.say("sí")
        db.add_client("Marta García", business_id=self.bid)
        result = self.say("factura a Marta por revisión 100 euros")
        self.assertIn("varios clientes", result["reply"])
        self.assertEqual(db.list_invoices(self.bid), [])
        self.assertEqual(len(db.list_clients(self.bid)), 2)

    def test_correction_replaces_amount_and_reconfirmation_is_single_use(self):
        self.say("gasté 45 euros en gasolina")
        result = self.say("corregir: gasté 35 euros en gasolina")
        self.assertIn("35,00", result["reply"])
        self.say("sí")
        self.say("sí")
        self.assertEqual(len(db.list_expenses(self.bid)), 1)
        self.assertEqual(float(db.list_expenses(self.bid)[0]["amount"]), 35)

    def test_invalid_correction_invalidates_previous_proposal(self):
        self.say("gasté 45 euros en gasolina")
        self.say("corregir: no sé el importe")
        self.say("sí")
        self.assertEqual(db.list_expenses(self.bid), [])

    def test_no_and_other_actor_cannot_confirm(self):
        self.say("gasté 45 euros en gasolina", "alice")
        self.say("sí", "bob")
        self.say("no", "alice")
        self.say("sí", "alice")
        self.assertEqual(db.list_expenses(self.bid), [])

    def test_changed_customer_invalidates_confirmation(self):
        self.say("factura a Marta por revisión 100 euros")
        with db.get_conn() as conn:
            conn.execute("UPDATE clients SET name=? WHERE id=? AND business_id=?", ("Otra persona", self.client["id"], self.bid))
        self.say("sí")
        self.assertEqual(db.list_invoices(self.bid), [])

    def test_ai_tools_also_propose_and_unsupported_writes_are_blocked(self):
        token = action_review.context.set({"actor": "web:owner"})
        try:
            result = json.loads(run_tool("registrar_gasto", {"concepto": "Material", "importe": 20}, self.bid))
            self.assertTrue(result["confirmation_required"])
            self.assertEqual(db.list_expenses(self.bid), [])
        finally:
            action_review.context.reset(token)

    def test_concurrent_yes_only_executes_once(self):
        self.say("gasté 45 euros en gasolina")
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: self.say("sí"), range(2)))
        self.assertEqual(len(db.list_expenses(self.bid)), 1)

    def test_feature_flag_off_preserves_existing_creation(self):
        with patch.object(config, "ASSISTANT_REVIEW_ENABLED", False):
            self.say("gasté 45 euros en gasolina")
        self.assertEqual(len(db.list_expenses(self.bid)), 1)

    def test_cross_business_pending_cannot_be_confirmed(self):
        self.say("gasté 45 euros en gasolina")
        other = db.create_business("Otra", "other@example.test")["id"]
        chat.handle(other, "sí")
        self.assertEqual(db.list_expenses(other), [])
        self.assertEqual(db.list_expenses(self.bid), [])

    def test_doubtful_voice_tax_and_multiple_orders_do_not_write(self):
        for text in ("Factura a Marta López por revisión, 121 euros, y va incluido.", "gasto 5 euros y gasto 10 euros"):
            self.say(text)
            self.say("sí")
        self.assertEqual(db.list_expenses(self.bid), [])
        self.assertEqual(db.list_invoices(self.bid), [])

    def test_expired_proposal_does_not_execute(self):
        self.say("gasté 45 euros en gasolina")
        with db.get_conn() as conn:
            conn.execute("UPDATE whatsapp_pending_actions SET expires_at='2000-01-01' WHERE business_id=?", (self.bid,))
        self.say("sí")
        self.assertEqual(db.list_expenses(self.bid), [])

    def test_ai_cannot_replace_first_proposal_with_second_write(self):
        state = {"actor": "web:owner"}
        token = action_review.context.set(state)
        try:
            first = json.loads(run_tool("registrar_gasto", {"concepto": "Material", "importe": 20}, self.bid))
            second = json.loads(run_tool("registrar_gasto", {"concepto": "Otro", "importe": 90}, self.bid))
            self.assertEqual(first, second)
            self.assertEqual(state["proposal"], first)
        finally:
            action_review.context.reset(token)
        self.say("sí")
        self.assertEqual(float(db.list_expenses(self.bid)[0]["amount"]), 20)

    def test_unknown_ai_write_cannot_bypass_review(self):
        token = action_review.context.set({"actor": "web:owner"})
        try:
            result = json.loads(run_tool("crear_proyecto", {"nombre": "Obra", "presupuesto": 500}, self.bid))
            self.assertIn("requiere revisión", result["reply"])
        finally:
            action_review.context.reset(token)

    def test_expense_project_assignment_is_not_guessed(self):
        token = action_review.context.set({"actor": "web:owner"})
        try:
            result = json.loads(run_tool("registrar_gasto", {"concepto": "Material", "importe": 20, "proyecto_id": 1}, self.bid))
            self.assertIn("No he asignado", result["reply"])
        finally:
            action_review.context.reset(token)
        self.say("sí")
        self.assertEqual(db.list_expenses(self.bid), [])

    def test_payment_partial_is_not_full_payment_or_new_invoice(self):
        result = self.say("Marta ha pagado 20 euros de la factura 1")
        self.assertIn("parcial", result["reply"])
        self.say("sí")
        self.assertEqual(db.list_invoices(self.bid), [])

    def test_changed_invoice_cannot_be_issued_from_stale_review(self):
        invoice = db.add_invoice(self.client["id"], "Trabajo", 100, business_id=self.bid)
        self.say(f"emitir factura {invoice['id']}")
        with db.get_conn() as conn:
            conn.execute("UPDATE invoices SET concept='Modificado' WHERE id=? AND business_id=?", (invoice["id"], self.bid))
        result = self.say("sí")
        self.assertIn("han cambiado", result["reply"])
        self.assertEqual(db.get_invoice(invoice["id"], self.bid)["status"], "borrador")

    def test_audio_and_text_share_actor_but_whatsapp_is_separate(self):
        chat.handle(self.bid, "gasté 45 euros en gasolina", channel="audio", actor_id="alice")
        chat.handle(self.bid, "sí", channel="whatsapp", actor_phone="34600000000")
        self.assertEqual(db.list_expenses(self.bid), [])
        self.say("sí", "alice")
        self.assertEqual(len(db.list_expenses(self.bid)), 1)

    def test_revoked_subscription_blocks_confirmation(self):
        self.say("gasté 45 euros en gasolina")
        with patch.object(db, "subscription_allows_access", return_value=False):
            result = self.say("sí")
        self.assertIn("modo consulta", result["reply"])
        self.assertEqual(db.list_expenses(self.bid), [])

    def test_http_audio_goes_through_groq_and_its_errors_stay_generic(self):
        import os
        import urllib.error

        from noesis.adapters import transcription
        from noesis.web.routers.assistant import api_chat_audio

        request = Request({"type": "http", "session": {"uid": 7, "sv": 1}})
        response = MagicMock()
        response.read.return_value = json.dumps({"text": "gasté 35 euros en gasolina"}).encode()
        response.__enter__.return_value = response
        opener = MagicMock()
        opener.open.return_value = response
        with (
            patch.dict(os.environ, {"NOESIS_PRIVATE_WHISPER_URL": ""}),
            patch.object(config, "GROQ_API_KEY", "clave"),
            patch("urllib.request.build_opener", return_value=opener),
        ):
            result = asyncio.run(api_chat_audio(self.bid, request, UploadFile(filename="nota-de-voz.webm", file=BytesIO(b"webm-voz"))))
            self.assertEqual(result["transcription"], "gasté 35 euros en gasolina")
            self.assertIn("No he guardado", result["reply"])
            self.assertIn(b'filename="audio.webm"', opener.open.call_args.args[0].data)
            self.assertEqual(db.list_expenses(self.bid), [])

            opener.open.side_effect = urllib.error.HTTPError(transcription.GroqWhisperProvider.ENDPOINT, 429, "error", {}, None)
            failed = asyncio.run(api_chat_audio(self.bid, request, UploadFile(filename="nota-de-voz.webm", file=BytesIO(b"webm-voz"))))
        self.assertEqual(failed.status_code, 422)
        self.assertEqual(db.list_expenses(self.bid), [])

    def test_http_audio_preview_then_text_confirm_and_error_clears_proposal(self):
        from noesis.web.routers.assistant import api_chat_audio
        request = Request({"type": "http", "session": {"uid": 7, "sv": 1}})
        with patch("noesis.adapters.transcription.get_transcriber") as provider:
            provider.return_value.transcribe.return_value = "gasté 35 euros en gasolina"
            result = asyncio.run(api_chat_audio(self.bid, request, UploadFile(filename="voice.wav", file=BytesIO(b"synthetic"))))
            self.assertIn("transcription", result)
            self.assertIn("No he guardado", result["reply"])
            self.assertEqual(db.list_expenses(self.bid), [])
            self.say("sí", "7:1")
            self.assertEqual(len(db.list_expenses(self.bid)), 1)
            self.say("gasté 50 euros en gasolina", "7:1")
            provider.return_value.transcribe.side_effect = ValueError("audio ilegible")
            result = asyncio.run(api_chat_audio(self.bid, request, UploadFile(filename="voice.wav", file=BytesIO(b"bad"))))
            self.assertEqual(result.status_code, 422)
            self.say("sí", "7:1")
            self.assertEqual(len(db.list_expenses(self.bid)), 1)

    def test_whatsapp_confirmation_uses_exact_proposal_and_deduplicates(self):
        from noesis.web import whatsapp
        phone = "34600000000"
        db.set_whatsapp_status(self.bid, "conectado", phone="600000000")
        with patch.object(whatsapp, "send"):
            whatsapp.handle_inbound({"from": phone, "id": "qa-msg-1", "text": "gasté 45 euros en gasolina"})
            self.assertEqual(db.list_expenses(self.bid), [])
            whatsapp.handle_inbound({"from": phone, "id": "qa-msg-2", "text": "corregir: gasté 35 euros en gasolina"})
            whatsapp.handle_inbound({"from": phone, "id": "qa-msg-3", "text": "sí"})
            whatsapp.handle_inbound({"from": phone, "id": "qa-msg-3", "text": "sí"})
            whatsapp.handle_inbound({"from": phone, "id": "qa-msg-4", "text": "sí"})
        self.assertEqual(len(db.list_expenses(self.bid)), 1)
        self.assertEqual(float(db.list_expenses(self.bid)[0]["amount"]), 35)
