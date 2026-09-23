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

    def test_confirmation_rejects_changed_draft_inside_issue_transaction(self):
        from noesis.conversation_plan import expected_invoice
        biz, client = self.make_business('Confirmación de versión')
        draft = self.invoice(biz, client)
        fingerprint = whatsapp._invoice_fingerprint(draft, biz['id'])
        with db.get_conn() as conn:
            conn.execute('UPDATE invoices SET concept=? WHERE id=? AND business_id=?',
                         ('Otro concepto', draft['id'], biz['id']))
        token = expected_invoice.set((biz['id'], draft['id'], fingerprint))
        try:
            with self.assertRaisesRegex(ValueError, 'cambió'):
                db.issue_invoice(draft['id'], biz['id'])
        finally:
            expected_invoice.reset(token)
        self.assertEqual(db.get_invoice(draft['id'], biz['id'])['status'], 'borrador')

    def test_issue_from_unknown_quote_never_uses_current_invoice(self):
        biz, client = self.make_business('Cita no autorizada')
        db.set_whatsapp_status(biz['id'], 'conectado', phone='600111222')
        draft = self.invoice(biz, client)
        whatsapp._remember_invoice(biz['id'], '34600111222', draft['id'])
        with patch.object(whatsapp, 'send') as send:
            whatsapp.handle_inbound({'from': '34600111222', 'id': 'unknown-issue',
                'reply_to': 'unknown-old-message', 'text': 'Emitir y enviame el pdf'})
        self.assertIn('mensaje anterior', send.call_args.args[1])
        self.assertIsNone(db.get_pending_action(biz['id'], '34600111222'))

    def test_vat_inclusive_total_is_preserved_through_issue_and_pdf(self):
        biz, client = self.make_business('Precio final')
        for rate in (0, 4, 10, 21):
            for gross in (99.99, 100, 121, 200, 400):
                with self.subTest(rate=rate, gross=gross):
                    result = json.loads(tools.run_tool('crear_factura', {
                        'cliente': client['name'], 'concepto': 'Revisión', 'base': gross,
                        'iva': rate, 'tipo_factura': 'F2', 'importe_incluye_iva': True,
                    }, biz['id']))
                    invoice = result['factura']
                    self.assertEqual(invoice['total'], gross)
                    self.assertEqual(db.issue_invoice(invoice['id'], biz['id'])['total'], gross)
                    lines = db.get_invoice_lines(invoice['id'], biz['id'])
                    self.assertAlmostEqual(lines[0]['base'] + lines[0]['vat_amount'], gross)
                    if rate == 21 and gross == 100:
                        from noesis.web.invoice_pdf import build_invoice_pdf
                        contents = PdfReader(BytesIO(build_invoice_pdf(invoice['id'], biz['id']))).pages[0].extract_text()
                        self.assertIn('100,00', contents)
                        self.assertIn('17,36', contents)

    def test_issue_and_send_me_pdf_requires_confirmation_and_keeps_recipient(self):
        biz, client = self.make_business('Emisión con plan')
        db.set_whatsapp_status(biz['id'], 'conectado', phone='600111222')
        draft = self.invoice(biz, client)
        whatsapp._remember_invoice(biz['id'], '34600111222', draft['id'])
        with patch.object(whatsapp, 'send') as send, patch.object(whatsapp, '_post_to_meta', return_value='wamid-plan') as post:
            whatsapp.handle_inbound({'from': '34600111222', 'id': 'plan-issue', 'text': 'Emitir y enviame el pdf'})
            self.assertIn('Confirmas', send.call_args.args[1])
            self.assertEqual(db.get_invoice(draft['id'], biz['id'])['status'], 'borrador')
            post.assert_not_called()
            whatsapp.handle_inbound({'from': '34600111222', 'id': 'plan-yes', 'text': 'sí'})
            self.assertEqual(post.call_args.args[0]['to'], '34600111222')
            self.assertIn(f'/invoices/{draft["id"]}/pdf', post.call_args.args[0]['document']['link'])

    def test_intent_plan_never_issues_on_negation_or_ambiguous_delivery(self):
        from noesis.conversation_plan import invoice_plan
        self.assertFalse(invoice_plan('no emitir y enviame pdf').issue)
        self.assertTrue(invoice_plan('emitir y enviar pdf').ambiguous_recipient)
        self.assertFalse(invoice_plan('emitir y enviar pdf al cliente').owner_pdf)

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

    def test_screenshot_ticket_over_limit_offers_full_invoice_for_last_client(self):
        biz, client = self.make_business('Ticket grande')
        db.set_whatsapp_status(biz['id'], 'conectado', phone='600111222')
        self.invoice(biz, client, issued=True)
        clients_before = len(db.list_clients(biz['id']))
        with patch.object(whatsapp, 'send') as send, patch.object(whatsapp, '_post_to_meta') as post:
            whatsapp.handle_inbound({'from': '34600111222', 'id': 'big-1',
                'text': 'creame un ticket para el ultimo cliente que he hecho de 3000 euros totales'})
            reply = send.call_args.args[1]
            self.assertIn('400', reply)
            self.assertIn('factura completa', reply)
            self.assertIn(client['name'], reply)
            whatsapp.handle_inbound({'from': '34600111222', 'id': 'big-2',
                'text': 'vale, pero quiero que me crees este ticket'})
            self.assertIn('no me lo puedo saltar', send.call_args.args[1])
            self.assertEqual(len(db.list_invoices(biz['id'])), 1)
            whatsapp.handle_inbound({'from': '34600111222', 'id': 'big-3', 'text': 'sí'})
            self.assertIn('Factura #', send.call_args.args[1])
        post.assert_not_called()
        self.assertEqual(len(db.list_clients(biz['id'])), clients_before)
        draft = db.list_invoices(biz['id'])[0]
        self.assertEqual((draft['invoice_type'], draft['status'], draft['total'], draft['client_id']),
                         ('F1', 'borrador', 3000, client['id']))

    def test_last_three_tickets_are_listed_and_sent_as_pdf(self):
        biz, client = self.make_business('Últimos tickets')
        db.set_whatsapp_status(biz['id'], 'conectado', phone='600111222')
        tickets = [self.invoice(biz, client, 50 + n, issued=True) for n in range(4)]
        with patch.object(whatsapp, 'send') as send, \
             patch.object(whatsapp, '_post_to_meta', return_value='wamid-last') as post:
            whatsapp.handle_inbound({'from': '34600111222', 'id': 'last-3',
                'text': 'mustrame los 3 ultimos tickets y mandamelos en pdf'})
        self.assertIn('últimos 3 tickets', send.call_args_list[0].args[1])
        links = [call.args[0]['document']['link'] for call in post.call_args_list]
        self.assertEqual(len(links), 3)
        for ticket in tickets[1:]:
            self.assertTrue(any(f'/invoices/{ticket["id"]}/pdf' in link for link in links))
        self.assertIsNone(whatsapp._recent_documents_request('pásame la última factura en PDF'))

    def test_web_markdown_bold_becomes_whatsapp_bold(self):
        self.assertEqual(whatsapp.whatsapp_markup('facturado **0,00 €** y **“ver documentos”**'),
                         'facturado *0,00 €* y *“ver documentos”*')

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

    def test_a_new_invoice_arrives_with_its_pdf_without_being_asked(self):
        """Decisión del founder (23-09): quiere verla antes de emitirla.

        Antes el PDF solo salía si la orden decía «y mándamelo en PDF», así que
        la factura se preparaba a ciegas.
        """
        biz, _ = self.make_business('PDF sin pedirlo')
        db.set_whatsapp_status(biz['id'], 'conectado', phone='600111222')
        db.add_client('Reformas Martinez', business_id=biz['id'])
        with patch.object(whatsapp, 'send'), \
             patch.object(whatsapp, '_upload_owner_draft_pdf', return_value='9911'), \
             patch.object(whatsapp, '_post_to_meta', return_value='wamid-auto') as post:
            whatsapp.handle_inbound({
                'from': '34600111222', 'id': 'pdf-auto-1',
                'text': 'haz una factura a reformas martinez concepto ventana por 750 euros'})
        borrador = db.list_invoices(biz['id'])[0]
        self.assertEqual(borrador['concept'], 'ventana')
        documento = post.call_args.args[0]
        self.assertEqual(documento['type'], 'document')
        self.assertEqual(documento['document']['id'], '9911')
        self.assertIn(str(borrador['id']), documento['document']['filename'])
        self.assertIn('BORRADOR', documento['document']['caption'])

    def test_the_pdf_also_arrives_when_the_invoice_is_born_from_a_yes(self):
        # Con la revisión encendida —lo de producción— la factura nace al
        # confirmar, y ese camino no adjuntaba el PDF ni pidiéndolo.
        from noesis import config

        biz, _ = self.make_business('PDF tras confirmar')
        db.set_whatsapp_status(biz['id'], 'conectado', phone='600111222')
        db.add_client('Reformas Martinez', business_id=biz['id'])
        with patch.object(config, 'ASSISTANT_REVIEW_ENABLED', True), \
             patch.object(whatsapp, 'send'), \
             patch.object(whatsapp, '_upload_owner_draft_pdf', return_value='9912'), \
             patch.object(whatsapp, '_post_to_meta', return_value='wamid-si') as post:
            whatsapp.handle_inbound({
                'from': '34600111222', 'id': 'pdf-review-1',
                'text': 'haz una factura a reformas martinez concepto ventana por 750 euros'})
            self.assertEqual(db.list_invoices(biz['id']), [])  # solo propuesta
            whatsapp.handle_inbound({'from': '34600111222', 'id': 'pdf-review-2',
                                     'text': 'sí'})
        borrador = db.list_invoices(biz['id'])[0]
        self.assertEqual(borrador['concept'], 'ventana')
        self.assertEqual(post.call_args.args[0]['document']['id'], '9912')

    def test_a_half_finished_draft_is_not_sent_as_a_pdf(self):
        # Un borrador a medias no es una factura todavía: un PDF con «Pendiente
        # de concepto» y 0 € confunde más de lo que ayuda.
        biz, _ = self.make_business('Sin PDF a medias')
        db.set_whatsapp_status(biz['id'], 'conectado', phone='600111222')
        with patch.object(whatsapp, 'send'), \
             patch.object(whatsapp, '_post_to_meta', return_value='wamid-no') as post:
            whatsapp.handle_inbound({'from': '34600111222', 'id': 'pdf-medias-1',
                                     'text': 'hazme una factura'})
        self.assertTrue(db.list_invoices(biz['id']))
        post.assert_not_called()

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
        with patch.object(whatsapp, '_TOKEN', 'test-token'), patch.object(whatsapp, '_PHONE_ID', '12345 \n'), \
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
