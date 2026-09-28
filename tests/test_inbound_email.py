"""Regresiones del catch-all documental y la identidad de clientes."""

from __future__ import annotations

import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import patch

from noesis import config, db, migrations
from noesis.documents import inbound_email, malware, repo as docrepo, service
from tests.fixtures import TINY_JPEG


class InboundEmailTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original = {
            "DB_PATH": config.DB_PATH,
            "DOCS_PATH": config.DOCS_PATH,
            "DATABASE_URL": config.DATABASE_URL,
            "INBOUND_EMAIL_DOMAIN": config.INBOUND_EMAIL_DOMAIN,
            "INBOUND_EMAIL_PREFIX": config.INBOUND_EMAIL_PREFIX,
            "CLAMAV_REQUIRED": config.CLAMAV_REQUIRED,
        }
        config.DATABASE_URL = ""
        config.DB_PATH = Path(self.tempdir.name) / "test.db"
        config.DOCS_PATH = Path(self.tempdir.name) / "uploads"
        config.INBOUND_EMAIL_DOMAIN = "bynoesis.test"
        config.INBOUND_EMAIL_PREFIX = "docs"
        config.CLAMAV_REQUIRED = False
        db.init_db()
        self.business = db.create_business("Taller Norte", "norte@example.com")
        self.other = db.create_business("Taller Sur", "sur@example.com")

    def tearDown(self):
        for key, value in self.original.items():
            setattr(config, key, value)
        self.tempdir.cleanup()

    @staticmethod
    def _message(to_address: str, *, second_to: str | None = None) -> bytes:
        message = EmailMessage()
        message["From"] = "proveedor@example.net"
        message["To"] = to_address
        if second_to:
            message["Cc"] = second_to
        message["Subject"] = "Ticket de material"
        message.set_content("Documento para revisar.")
        message.add_attachment(
            TINY_JPEG,
            maintype="image",
            subtype="jpeg",
            filename="ticket-ferreteria.jpg",
        )
        return message.as_bytes()

    @staticmethod
    def _gmail_forwarding(to_address: str, *, signed: bool | None = True,
                          link: str = "https://mail-settings.google.com/mail/vf-%5BANGjdJ9x%5D-Qm4") -> bytes:
        message = EmailMessage()
        message["From"] = "Gmail Team <forwarding-noreply@google.com>"
        message["To"] = to_address
        message["Subject"] = "(#123456789) Gmail Forwarding Confirmation"
        if signed is not None:
            message["Authentication-Results"] = (
                f"mx.hostinger.com; dkim={'pass' if signed else 'fail'} "
                "header.d=google.com; spf=pass"
            )
        message.set_content(
            "carlos.fontaneria@gmail.com has requested to automatically forward "
            f"mail to your email address {to_address}.\n"
            "Confirmation code: 123456789\n\n"
            "To allow carlos.fontaneria@gmail.com to automatically forward mail "
            "to your address, please click the link below to confirm the request:\n\n"
            f"{link}\n"
        )
        return message.as_bytes()

    def test_gmail_forwarding_confirmation_reaches_the_owner(self):
        """Sin esto el autónomo nunca ve el código y el reenvío no se activa."""
        route = inbound_email.ensure_route(self.business["id"])
        with patch("noesis.adapters.email.queue_email", return_value=True) as notify:
            result = inbound_email.process_raw_message(
                self._gmail_forwarding(route["address"])
            )
        self.assertEqual(result["status"], "gmail_forwarding")
        self.assertTrue(result["permanent"])
        self.assertEqual(result["documents"], [])
        notify.assert_called_once()
        to, _subject, body = notify.call_args.args[:3]
        self.assertEqual(to, "norte@example.com")
        self.assertIn("https://mail-settings.google.com/mail/vf-%5BANGjdJ9x%5D-Qm4", body)
        self.assertIn("123456789", body)
        self.assertIn("carlos.fontaneria@gmail.com", body)
        self.assertEqual(notify.call_args.kwargs["business_id"], self.business["id"])

    def test_forged_forwarding_request_is_not_relayed(self):
        """Cualquiera puede escribir el From: si la firma de Google falla, no se reenvía."""
        route = inbound_email.ensure_route(self.business["id"])
        with patch("noesis.adapters.email.queue_email") as notify:
            result = inbound_email.process_raw_message(
                self._gmail_forwarding(route["address"], signed=False)
            )
        notify.assert_not_called()
        self.assertEqual(result["code"], "no_attachments")

    def test_a_mailbox_that_says_nothing_about_dkim_still_relays_the_google_link(self):
        route = inbound_email.ensure_route(self.business["id"])
        with patch("noesis.adapters.email.queue_email", return_value=True) as notify:
            result = inbound_email.process_raw_message(
                self._gmail_forwarding(route["address"], signed=None)
            )
        self.assertEqual(result["status"], "gmail_forwarding")
        notify.assert_called_once()

    def test_only_the_top_authentication_line_is_trusted(self):
        """Una línea «pass» escrita más abajo por el remitente no tapa un fallo."""
        route = inbound_email.ensure_route(self.business["id"])
        raw = self._gmail_forwarding(route["address"], signed=False)
        raw = raw.replace(
            b"Authentication-Results:",
            b"Authentication-Results: mx.hostinger.com; dkim=fail header.d=google.com\n"
            b"Authentication-Results:", 1).replace(b"dkim=fail header.d=google.com; spf",
                                                   b"dkim=pass header.d=google.com; spf", 1)
        message = inbound_email.BytesParser(policy=inbound_email.policy.default).parsebytes(raw)
        self.assertIsNone(inbound_email.gmail_forwarding_request(message))

    def test_a_gmail_auto_forward_is_routed_by_x_forwarded_to(self):
        """Al reenviar, Gmail deja en el To la dirección del autónomo, no la nuestra."""
        route = inbound_email.ensure_route(self.business["id"])
        raw = self._message("carlos.fontaneria@gmail.com").replace(
            b"To: carlos.fontaneria@gmail.com",
            b"To: carlos.fontaneria@gmail.com\nX-Forwarded-To: "
            + route["address"].encode(), 1)
        result = inbound_email.process_raw_message(raw)
        self.assertEqual(result["business_id"], self.business["id"])
        self.assertEqual(len(result["documents"]), 1)

    def test_logos_and_signature_icons_do_not_become_documents(self):
        route = inbound_email.ensure_route(self.business["id"])
        message = EmailMessage()
        message["From"] = "facturas@proveedor.example"
        message["To"] = route["address"]
        message["Subject"] = "Tu factura"
        message.set_content("Adjuntamos la factura.")
        message.add_alternative("<p>Adjuntamos la factura.</p><img src='cid:logo'>",
                                subtype="html")
        html_part = message.get_payload()[1]
        html_part.add_related(b"\x89PNG" + b"0" * 2000, maintype="image",
                              subtype="png", cid="<logo>", filename="logo.png")
        for index in range(9):
            message.add_attachment(b"\x89PNG" + b"1" * 800, maintype="image",
                                   subtype="png", filename=f"icono{index}.png",
                                   disposition="inline")
        message.add_attachment(b"%PDF-1.4\n" + b"0" * 40_000,
                               maintype="application", subtype="pdf",
                               filename="factura.pdf")
        parsed = inbound_email.BytesParser(
            policy=inbound_email.policy.default).parsebytes(message.as_bytes())
        names = [name for name, _payload in inbound_email._attachments(parsed)]
        # Los diez adornos no cuentan (y no hacen rechazar el correo por «demasiados»).
        self.assertEqual(names, ["factura.pdf"])

    def test_inspect_explains_a_forward_without_touching_the_database(self):
        route = inbound_email.ensure_route(self.business["id"])
        lost = inbound_email.inspect_raw_message(self._message("carlos@gmail.com"))
        self.assertEqual(lost["route_tokens"], [])
        self.assertIn("no conserva el destinatario", lost["verdict"])
        kept = inbound_email.inspect_raw_message(self._message(route["address"]))
        self.assertEqual(len(kept["route_tokens"]), 1)
        self.assertTrue(kept["route_tokens"][0].endswith("…"))
        self.assertIn("Correcto", kept["verdict"])
        confirmation = inbound_email.inspect_raw_message(
            self._gmail_forwarding(route["address"]))
        self.assertTrue(confirmation["gmail_forwarding"])
        self.assertEqual(confirmation["google_signature"], "pass")

    def test_only_google_confirmation_links_are_relayed(self):
        route = inbound_email.ensure_route(self.business["id"])
        raw = self._gmail_forwarding(
            route["address"], link="https://mail.google.com.evil.example/mail/vf-x"
        )
        message = inbound_email.BytesParser(
            policy=inbound_email.policy.default
        ).parsebytes(raw)
        request = inbound_email.gmail_forwarding_request(message)
        # El código de Google sigue siendo útil; el enlace ajeno nunca se envía.
        self.assertIsNone(request["link"])
        self.assertEqual(request["code"], "123456789")

    def test_catch_all_routes_one_message_to_one_business_and_deduplicates(self):
        route = inbound_email.ensure_route(self.business["id"])
        raw = self._message(route["address"])
        with patch("noesis.documents.service.ocr.extract", return_value=None):
            result = inbound_email.process_raw_message(raw)
            duplicate = inbound_email.process_raw_message(raw)

        self.assertEqual(result["status"], "processed")
        self.assertEqual(result["business_id"], self.business["id"])
        self.assertEqual(duplicate["status"], "duplicate")
        own = docrepo.list_for_business(self.business["id"])
        self.assertEqual(len(own), 1)
        self.assertEqual(own[0]["doc_status"], "pendiente_revisar")
        self.assertEqual(docrepo.list_for_business(self.other["id"]), [])

    def test_two_route_tokens_fail_closed_without_storing_anything(self):
        first = inbound_email.ensure_route(self.business["id"])
        second = inbound_email.ensure_route(self.other["id"])
        result = inbound_email.process_raw_message(
            self._message(first["address"], second_to=second["address"])
        )
        self.assertEqual(result["code"], "route_ambiguous")
        self.assertEqual(docrepo.list_for_business(self.business["id"]), [])
        self.assertEqual(docrepo.list_for_business(self.other["id"]), [])

    def test_required_scanner_outage_leaves_the_message_for_retry(self):
        route = inbound_email.ensure_route(self.business["id"])
        config.CLAMAV_REQUIRED = True
        raw = self._message(route["address"])
        with patch(
            "noesis.documents.malware.scan",
            side_effect=malware.ScannerUnavailable("caída simulada"),
        ):
            with self.assertRaises(inbound_email.InboundEmailError):
                inbound_email.process_raw_message(raw)
        self.assertEqual(docrepo.list_for_business(self.business["id"]), [])

        config.CLAMAV_REQUIRED = False
        with patch("noesis.documents.service.ocr.extract", return_value=None):
            retried = inbound_email.process_raw_message(raw)
        self.assertEqual(retried["status"], "processed")
        self.assertEqual(len(docrepo.list_for_business(self.business["id"])), 1)

    def test_unknown_customer_is_only_created_after_owner_confirmation(self):
        document = docrepo.add(
            self.business["id"],
            filename="factura-emitida.pdf",
            stored_name="issued.pdf",
            mime="application/pdf",
            size=10,
            kind="factura_emitida",
            doc_status="pendiente_revisar",
        )
        with patch.object(service, "file_bytes", return_value=(b"pdf", "application/pdf", "x.pdf")), patch(
            "noesis.adapters.extraction.extract_invoice",
            return_value={
                "supplier": "Taller Norte",
                "supplier_nif": "B11111111",
                "customer": "Comunidad Mar",
                "customer_nif": "H22222222",
                "number": "F-18",
                "total": 121,
                "confidence": 95,
            },
        ):
            draft = service.invoice_draft(self.business["id"], document["id"])

        self.assertEqual(draft["direction"], "emitida")
        self.assertEqual(draft["client_resolution"]["status"], "pending")
        candidate = db.get_document_client_candidate(
            document["id"], self.business["id"]
        )
        self.assertEqual(candidate["status"], "pending")
        self.assertIsNone(db.resolve_client_identity(
            self.business["id"], name="Comunidad Mar", nif="H22222222"
        ))

        client = service.confirm_client_candidate(
            self.business["id"], document["id"],
            name="Comunidad del Mar", nif="H22222229",
        )
        self.assertEqual(client["name"], "Comunidad del Mar")
        self.assertEqual(client["nif"], "H22222229")
        self.assertEqual(
            docrepo.get(document["id"], self.business["id"])["client_id"],
            client["id"],
        )

    def test_confirmed_client_keeps_the_contact_data_read_on_the_invoice(self):
        document = docrepo.add(
            self.business["id"],
            filename="factura-emitida.pdf",
            stored_name="issued-contact.pdf",
            mime="application/pdf",
            size=10,
            kind="factura_emitida",
            doc_status="pendiente_revisar",
        )
        with patch.object(
            service, "file_bytes",
            return_value=(b"pdf", "application/pdf", "x.pdf"),
        ), patch(
            "noesis.adapters.extraction.extract_invoice",
            return_value={
                "supplier": "Taller Norte",
                "supplier_nif": "B11111111",
                "customer": "Comunidad del Pino",
                "customer_nif": "H44444444",
                "customer_address": "Calle Larga 4 08001 Barcelona",
                "customer_email": "admin@pino.example",
                "customer_phone": "+34931234567",
                "number": "F-19",
                "total": 121,
                "confidence": 95,
            },
        ):
            draft = service.invoice_draft(self.business["id"], document["id"])

        # La lectura propone, no da de alta: la ficha nace al confirmar.
        self.assertEqual(draft["customer_address"],
                         "Calle Larga 4 08001 Barcelona")
        self.assertEqual(db.list_clients(self.business["id"]), [])

        client = service.confirm_client_candidate(
            self.business["id"], document["id"],
            address=draft["customer_address"], email=draft["customer_email"],
            phone=draft["customer_phone"],
        )
        self.assertEqual(client["address"], "Calle Larga 4 08001 Barcelona")
        self.assertEqual(client["email"], "admin@pino.example")
        self.assertEqual(client["phone"], "+34931234567")

    def test_existing_client_keeps_its_own_contact_data(self):
        existing = db.add_client(
            "Hotel Antiguo", nif="B55555555", address="Plaza Vieja 1",
            email="reservas@antiguo.example", phone="+34911111111",
            business_id=self.business["id"],
        )
        document = docrepo.add(
            self.business["id"], filename="factura.pdf",
            stored_name="issued-existing.pdf", mime="application/pdf", size=10,
            kind="factura_emitida",
        )
        db.propose_document_client(
            self.business["id"], document["id"],
            name="Hotel Antiguo", nif="B55555555",
        )
        client = service.confirm_client_candidate(
            self.business["id"], document["id"],
            address="Otra Calle 9", email="otro@antiguo.example",
            phone="+34999999999",
        )
        self.assertEqual(client["id"], existing["id"])
        self.assertEqual(client["address"], "Plaza Vieja 1")
        self.assertEqual(client["email"], "reservas@antiguo.example")
        self.assertEqual(client["phone"], "+34911111111")
        self.assertEqual(len(db.list_clients(self.business["id"])), 1)

    def test_known_nif_is_linked_without_creating_a_duplicate(self):
        client = db.add_client(
            "Hotel Antiguo", nif="B33333333", business_id=self.business["id"]
        )
        document = docrepo.add(
            self.business["id"], filename="factura.pdf", stored_name="f.pdf",
            mime="application/pdf", size=10, kind="factura_emitida",
        )
        candidate = db.propose_document_client(
            self.business["id"], document["id"],
            name="Hotel con otro texto", nif="B33333333",
        )
        self.assertEqual(candidate["status"], "confirmed")
        self.assertEqual(candidate["matched_client_id"], client["id"])
        self.assertEqual(len(db.list_clients(self.business["id"])), 1)

    def test_explicit_client_creation_reuses_an_existing_nif(self):
        client = db.add_client(
            "Comunidad Original", nif="H44444444", business_id=self.business["id"]
        )
        reused = db.get_or_create_client(
            "Nombre escrito de otro modo",
            self.business["id"],
            nif="H-44444444",
        )
        self.assertEqual(reused["id"], client["id"])
        self.assertEqual(len(db.list_clients(self.business["id"])), 1)

    def test_schema_is_current(self):
        self.assertEqual(migrations.current_version(), migrations.LATEST_VERSION)


if __name__ == "__main__":
    unittest.main()
