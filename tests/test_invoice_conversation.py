"""Regresiones de conversaciones reales: identidad, recibos y PDFs por WhatsApp."""
import json
import unittest
from io import BytesIO
from unittest.mock import patch

from pypdf import PdfReader

from noesis import agent, db, tools
from noesis.web import chat, whatsapp
from tests import test_backend as fixtures


class InvoiceConversationTestCase(unittest.TestCase):
    setUp = fixtures.BackendTestCase.setUp
    tearDown = fixtures.BackendTestCase.tearDown
    make_business = fixtures.BackendTestCase.make_business

    def test_create_ticket_and_pdf_uses_new_draft_not_existing_demo(self):
        biz, client = self.make_business('Creación compuesta')
        db.set_whatsapp_status(biz['id'], 'conectado', phone='600111222')
        old = self.invoice(biz, client, issued=True)
        with patch.object(whatsapp, 'send'), \
             patch.object(whatsapp, '_upload_owner_draft_pdf', return_value='12345'), \
             patch.object(whatsapp, '_post_to_meta', return_value='wamid-created') as post:
            whatsapp.handle_inbound({'from': '34600111222', 'id': 'compound-new',
                'text': 'Creame un tiquet para jana 200€ concepto aire acondicionado y enviam pdf'})
        draft = db.list_invoices(biz['id'])[0]
        self.assertNotEqual(draft['id'], old['id'])
        self.assertEqual(draft['status'], 'borrador')
        self.assertEqual(draft['client_name'].lower(), 'jana')
        self.assertEqual(draft['concept'], 'aire acondicionado')
        self.assertEqual(draft['total'], 200)
        self.assertIn(str(draft['id']), post.call_args.args[0]['document']['filename'])

    def test_screenshot_over_limit_creation_and_crealo_keep_fiscal_reason(self):
        biz, client = self.make_business('Rechazo con contexto')
        db.set_whatsapp_status(biz['id'], 'conectado', phone='600111222')
        self.invoice(biz, client, issued=True)
        with patch.object(whatsapp, 'send') as send, patch.object(whatsapp, '_post_to_meta') as post:
            for number, text in enumerate((
                'Creame un tiquet para jana 520€ concepto aire acondicionado y enviam pdf', 'Crealo'
            )):
                whatsapp.handle_inbound({'from': '34600111222', 'id': f'limit-{number}', 'text': text})
                self.assertIn('400', send.call_args.args[1])
                self.assertNotIn('No encuentro', send.call_args.args[1])
        post.assert_not_called()
        self.assertEqual(len(db.list_invoices(biz['id'])), 1)

    def test_pdf_clarification_f2_jana_preserves_download_intent(self):
        biz, client = self.make_business('Selección F2')
        db.set_whatsapp_status(biz['id'], 'conectado', phone='600111222')
        self.invoice(biz, client, issued=True)
        jana = db.add_client('Jana', business_id=biz['id'])
        wanted = self.invoice(biz, jana, issued=True)
        with patch.object(whatsapp, 'send'), patch.object(whatsapp, '_post_to_meta', return_value='wamid-jana') as post:
            whatsapp.handle_inbound({'from': '34600111222', 'id': 'f2-ask', 'text': 'Pasame factura f2 en pdf'})
            post.assert_not_called()
            whatsapp.handle_inbound({'from': '34600111222', 'id': 'f2-select', 'text': 'F2 jana'})
        self.assertIn(f'/invoices/{wanted["id"]}/pdf', post.call_args.args[0]['document']['link'])

    def invoice(self, business, client, amount=100, issued=False):
        inv = db.add_invoice(client['id'], 'Reparación real', amount,
                             business_id=business['id'], invoice_type='F2')
        return db.issue_invoice(inv['id'], business['id']) if issued else inv

    def test_unknown_customer_and_number_never_fall_back_to_demo(self):
        biz, client = self.make_business('Identidad PDF')
        self.invoice(biz, client, issued=True)
        for message in ('Enviam pdf del tiquet de jana', 'pásame PDF ticket Jana',
                        'pásame factura 999999 en PDF', 'pásame factura ABC-404 en PDF'):
            with self.subTest(message=message):
                found, error = whatsapp._invoice_for_owner_pdf(biz['id'], message)
                self.assertIsNone(found)
                self.assertTrue(error)

    def test_multiple_invoices_require_selection_but_latest_includes_draft(self):
        biz, client = self.make_business('Selección')
        issued = self.invoice(biz, client, issued=True)
        draft = self.invoice(biz, client, 75)
        for message in ('Pásamelo en PDF', f'PDF de factura de {client["name"]}'):
            found, error = whatsapp._invoice_for_owner_pdf(biz['id'], message)
            self.assertIsNone(found)
            self.assertIn('varios', error)
        found, _ = whatsapp._invoice_for_owner_pdf(biz['id'], 'pásame la última factura en PDF')
        self.assertEqual(found['id'], draft['id'])
        found, _ = whatsapp._invoice_for_owner_pdf(biz['id'], 'pásame la última factura emitida en PDF')
        self.assertEqual(found['id'], issued['id'])

    def test_focus_is_scoped_to_phone_business_and_expires(self):
        biz, client = self.make_business('Contexto')
        first = self.invoice(biz, client, issued=True)
        self.invoice(biz, client, 75)
        whatsapp._remember_invoice(biz['id'], '34600111222', first['id'])
        found, _ = whatsapp._invoice_for_owner_pdf(biz['id'], 'imprímela', '34600111222')
        self.assertEqual(found['id'], first['id'])
        self.assertIsNone(whatsapp._invoice_for_owner_pdf(biz['id'], 'imprímela', '34600999888')[0])
        other, _ = self.make_business('Otro negocio')
        self.assertIsNone(whatsapp._invoice_for_owner_pdf(other['id'], f'factura {first["id"]}')[0])
        db.set_pending_action(biz['id'], 'invoice-focus:34600111222', 'invoice_focus',
                              {'invoice_id': first['id']}, ttl_minutes=-1)
        self.assertIsNone(whatsapp._invoice_for_owner_pdf(biz['id'], 'imprímela', '34600111222')[0])

    def test_draft_pdf_contains_real_customer_amount_and_watermark(self):
        biz, _ = self.make_business('PDF borrador real')
        jana = db.add_client('Jana Real', business_id=biz['id'])
        draft = self.invoice(biz, jana, 125)
        captured = []
        def upload(data, filename):
            captured.append(PdfReader(BytesIO(data)).pages[0].extract_text())
            self.assertTrue(filename.startswith('borrador-ticket-'))
            return '123456789'
        with patch.object(whatsapp, '_upload_owner_draft_pdf', side_effect=upload), \
             patch.object(whatsapp, '_post_to_meta', return_value='wamid-real') as post:
            result = whatsapp._send_owner_invoice_pdf(biz, '34600111222', 'pásame el PDF del ticket de Jana Real')
        self.assertTrue(result['sent'])
        self.assertEqual(result['invoice_id'], draft['id'])
        self.assertIn('Jana Real', captured[0])
        self.assertIn('151,25', captured[0])
        self.assertIn('BORRADOR - PENDIENTE DE EMISION', captured[0])
        self.assertEqual(post.call_args.args[0]['document']['id'], '123456789')
        self.assertEqual(db.get_invoice(draft['id'], biz['id'])['status'], 'borrador')

    def test_model_cannot_invent_creation_or_overwrite_tool_receipt(self):
        biz, client = self.make_business('Respuesta verificada')
        with patch.object(chat, '_handle', return_value={
            'source': 'ia', 'reply': 'Tíquet F2 preparat per Jana. Guardat al sistema.'
        }):
            result = chat.handle(biz['id'], 'la segona opcio del tiquet')
        self.assertIn('No tengo una ejecución verificada', result['reply'])
        self.assertEqual(db.list_invoices(biz['id']), [])
        def model(*args, **kwargs):
            tools.run_tool('crear_factura', {'cliente': client['name'], 'concepto': 'Grifo',
                                           'base': 100, 'tipo_factura': 'F2'}, biz['id'])
            return {'source': 'ia', 'reply': 'Factura emitida por 999 euros para otra persona.'}
        with patch.object(chat, '_handle', side_effect=model):
            result = chat.handle(biz['id'], 'prepara lo que hemos hablado')
        self.assertIn('borrador', result['reply'])
        self.assertNotIn('999', result['reply'])
        self.assertIn('121,00', result['reply'])
        self.assertEqual(result['invoice_ids'], [db.list_invoices(biz['id'])[0]['id']])

    def test_failed_simplified_creation_cannot_be_reported_as_saved(self):
        biz, client = self.make_business('Ticket rechazado')
        def model(*args, **kwargs):
            tools.run_tool('crear_factura', {'cliente': client['name'], 'concepto': 'Reforma',
                                           'base': 1250, 'tipo_factura': 'F2'}, biz['id'])
            return {'source': 'ia', 'reply': 'Ticket creado y listo.'}
        with patch.object(chat, '_handle', side_effect=model):
            result = chat.handle(biz['id'], 'reforma para Jana')
        self.assertIn('400', result['reply'])
        self.assertEqual(result['invoice_ids'], [])
        self.assertEqual(db.list_invoices(biz['id']), [])

    def test_local_creation_and_confirmation_keep_verified_focus_for_print(self):
        biz, client = self.make_business('Conversación completa')
        db.set_whatsapp_status(biz['id'], 'conectado', phone='600111222')
        self.invoice(biz, client, issued=True)
        with patch.object(whatsapp, 'send'), \
             patch.object(whatsapp, '_post_to_meta', return_value='wamid-print') as post:
            whatsapp.handle_inbound({'from': '34600111222', 'id': 'focus1',
                                     'text': 'ticket de venta a Jana por grifo 125 euros'})
            created = db.list_invoices(biz['id'])[0]
            whatsapp.handle_inbound({'from': '34600111222', 'id': 'focus2', 'text': 'emítela'})
            self.assertEqual(db.get_invoice(created['id'], biz['id'])['status'], 'borrador')
            whatsapp.handle_inbound({'from': '34600111222', 'id': 'focus3', 'text': 'sí'})
            result = whatsapp.handle_inbound({'from': '34600111222', 'id': 'focus4', 'text': 'imprímela'})
        self.assertTrue(result['results'][0]['sent'])
        self.assertIn(f'/invoices/{created["id"]}/pdf', post.call_args.args[0]['document']['link'])

    def test_print_quoted_old_message_does_not_use_newer_focus(self):
        biz, client = self.make_business('Respuesta citada')
        db.set_whatsapp_status(biz['id'], 'conectado', phone='600111222')
        inv = self.invoice(biz, client, issued=True)
        whatsapp._remember_invoice(biz['id'], '34600111222', inv['id'])
        with patch.object(whatsapp, 'send'), patch.object(whatsapp, '_post_to_meta') as post:
            result = whatsapp.handle_inbound({'from': '34600111222', 'id': 'quote1',
                                             'reply_to': 'old-message', 'text': 'imprímela'})
        post.assert_not_called()
        self.assertFalse(result['results'][0]['sent'])

    def test_cached_agent_refreshes_turns_resolved_by_local_rules(self):
        biz, _ = self.make_business('Historial')
        class Cached:
            business_id = biz['id']
            messages = [{'role': 'assistant', 'content': 'historial viejo'}]
        db.add_assistant_message(biz['id'], 'user', 'crea ticket')
        db.add_assistant_message(biz['id'], 'assistant', 'Borrador #42 preparado')
        db.add_assistant_message(biz['id'], 'user', 'lo anterior')
        cached = Cached()
        agent._refresh_conversation(cached)
        self.assertIn('Borrador #42', json.dumps(cached.messages))
        self.assertNotIn('historial viejo', json.dumps(cached.messages))
        self.assertNotIn('lo anterior', json.dumps(cached.messages))

    def test_verified_old_quote_selects_its_invoice_instead_of_current_focus(self):
        biz, client = self.make_business('Cita verificada')
        db.set_whatsapp_status(biz['id'], 'conectado', phone='600111222')
        old = self.invoice(biz, client, 75, issued=True)
        new = self.invoice(biz, client, 100, issued=True)
        whatsapp._remember_invoice_message(biz['id'], '34600111222', old['id'], 'wamid-old')
        whatsapp._remember_invoice(biz['id'], '34600111222', new['id'])
        with patch.object(whatsapp, 'send'), patch.object(whatsapp, '_post_to_meta', return_value='wamid-new') as post:
            result = whatsapp.handle_inbound({'from': '34600111222', 'id': 'verified-quote',
                                             'reply_to': 'wamid-old', 'text': 'imprímela'})
        self.assertTrue(result['results'][0]['sent'])
        self.assertIn(f'/invoices/{old["id"]}/pdf', post.call_args.args[0]['document']['link'])

    def test_simplified_invoice_without_customer_nif_still_requires_issuer_identity(self):
        biz, _ = self.make_business('NIF emisor')
        customer = db.add_client('Particular sin NIF', business_id=biz['id'])
        draft = self.invoice(biz, customer, 100)
        with db.get_conn() as conn:
            conn.execute('UPDATE businesses SET nif=NULL WHERE id=?', (biz['id'],))
        with self.assertRaisesRegex(ValueError, 'NIF del negocio'):
            db.issue_invoice(draft['id'], biz['id'])
        db.update_fiscal(biz['id'], nif=fixtures.ISSUER_NIF)
        issued = db.issue_invoice(draft['id'], biz['id'])
        self.assertEqual(issued['status'], 'enviada')
        self.assertFalse(issued.get('recipient_nif'))

    def test_upload_uses_actual_pdf_bytes_and_requires_meta_id(self):
        from unittest.mock import MagicMock
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"id":"123456"}'
        data = b'%PDF-1.4 actual-test-content'
        with patch.object(whatsapp, '_TOKEN', 'test-token'), patch.object(whatsapp, '_PHONE_ID', '12345'), \
             patch.object(whatsapp.urllib.request, 'urlopen', return_value=response) as request:
            media_id = whatsapp._upload_owner_draft_pdf(data, 'borrador-12.pdf')
            self.assertEqual(media_id, '123456')
            self.assertIn(data, request.call_args.args[0].data)
            self.assertTrue(request.call_args.args[0].full_url.endswith('/12345/media'))
            response.read.return_value = b'{}'
            with self.assertRaisesRegex(ValueError, 'no confirmó'):
                whatsapp._upload_owner_draft_pdf(data, 'borrador-12.pdf')

    def test_pdf_language_and_negative_commands(self):
        for phrase in ('imprímela', 'imprimeix-la', 'pásame factura 29 en PDF',
                       'Enviam pdf del tiquet de jana', 'No pots enviar el PDF per aqui?'):
            self.assertTrue(whatsapp._is_owner_pdf_request(phrase), phrase)
        for phrase in ('no me envíes el PDF de la factura', 'no mandes factura PDF', 'no imprimas'):
            self.assertFalse(whatsapp._is_owner_pdf_request(phrase), phrase)
