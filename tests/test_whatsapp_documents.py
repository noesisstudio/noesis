"""Recorridos completos de fotos y PDF por WhatsApp, con base de datos real.

Meta y la IA están simulados; la lectura local, la separación de PDF, la revisión,
las correcciones y los registros contables son los del producto.
"""

import itertools
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fpdf import FPDF
from PIL import Image

from noesis import config, db
from noesis.adapters import extraction
from noesis.documents import repo as docrepo
from noesis.documents import service as docservice
from noesis.web import whatsapp, whatsapp_documents

PHONE = "34600111222"
OWN_NIF = "B12345674"  # pragma: allowlist secret
SUPPLIER_NIF = "A81948077"  # pragma: allowlist secret


def jpeg(color):
    buffer = BytesIO()
    Image.new("RGB", (40, 40), color).save(buffer, "JPEG")
    return buffer.getvalue()


def pdf(*pages):
    document = FPDF()
    for text in pages:
        document.add_page()
        document.set_font("helvetica", size=11)
        document.multi_cell(0, 7, text)
    return bytes(document.output())


def ai_reading(*documents, statement=None):
    return {"documents": list(documents), "statement": statement, "source": "ia"}


class WhatsappDocumentsTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        names = ("DB_PATH", "BACKUP_DIR", "DOCS_PATH", "DATABASE_URL", "ANTHROPIC_API_KEY")
        self.saved = {name: getattr(config, name) for name in names}
        config.DATABASE_URL = ""
        config.ANTHROPIC_API_KEY = ""
        config.DB_PATH = Path(self.tempdir.name) / "test.db"
        config.BACKUP_DIR = Path(self.tempdir.name) / "backups"
        config.DOCS_PATH = Path(self.tempdir.name) / "uploads"
        db.init_db()
        business = db.create_business("Reformas Norte SL", "norte@example.com")
        db.update_fiscal(business["id"], nif=OWN_NIF, address="Calle Principal 1")
        db.set_whatsapp_status(business["id"], "conectado", phone="600111222")
        self.business = db.get_business(business["id"])
        self.bid = self.business["id"]
        self.replies = []
        self.chat_messages = []
        self.media = b""
        self.ids = itertools.count(1)
        self.patches = [
            patch.object(whatsapp, "send", side_effect=lambda phone, text, **kw: self.replies.append(text)),
            patch.object(whatsapp, "_download_media", side_effect=lambda *args, **kwargs: self.media),
            patch.object(whatsapp.chat, "handle", side_effect=self._chat),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        for name, value in self.saved.items():
            setattr(config, name, value)
        self.tempdir.cleanup()

    def _chat(self, business_id, text, **kwargs):
        self.chat_messages.append(text)
        return {"reply": "respuesta del asistente"}

    def _id(self):
        return f"wamid-doc-{next(self.ids)}"

    def send_photo(self, data, caption=""):
        self.media = data
        return whatsapp.handle_inbound({
            "from": PHONE, "id": self._id(), "image_id": "img", "image_mime": "image/jpeg",
            "caption": caption,
        })["results"][0]

    def send_pdf(self, data, filename="factura.pdf"):
        self.media = data
        return whatsapp.handle_inbound({
            "from": PHONE, "id": self._id(), "media_document_id": "doc",
            "media_document_mime": "application/pdf", "media_document_filename": filename,
        })["results"][0]

    def say(self, text):
        whatsapp.handle_inbound({"from": PHONE, "id": self._id(), "text": text})
        return self.replies[-1]

    def pending(self):
        return db.get_pending_action(self.bid, whatsapp_documents.review_key(PHONE))

    def test_unreadable_photo_asks_for_the_data_and_links_the_expense_to_it(self):
        result = self.send_photo(jpeg((10, 20, 30)))
        self.assertTrue(result["pending"])
        self.assertIn("Guardado en tus papeles", self.replies[-1])
        self.assertIn("Escríbeme el total", self.replies[-1])

        reply = self.say("45,20 gasolinera Repsol")
        self.assertIn("Cambiado", reply)
        self.assertIn("Total *45,20 €*", reply)

        reply = self.say("sí")
        self.assertIn("Apuntado ✅", reply)
        expenses = db.list_expenses(self.bid)
        self.assertEqual(len(expenses), 1)
        self.assertEqual(expenses[0]["amount"], 45.2)
        self.assertEqual(docrepo.get(result["document_id"], self.bid)["expense_id"], expenses[0]["id"])
        self.assertIsNone(self.pending())

        # Un segundo SÍ ya no pertenece a la revisión y no duplica el gasto.
        self.say("sí")
        self.assertEqual(len(db.list_expenses(self.bid)), 1)

        # Reenviar la misma foto no la vuelve a apuntar.
        again = self.send_photo(jpeg((10, 20, 30)))
        self.assertTrue(again["already_stored"])
        self.assertIn("ya está registrado como gasto", self.replies[-1])
        self.assertEqual(len(db.list_expenses(self.bid)), 1)

    def test_invoice_that_does_not_add_up_is_fixed_in_the_chat_before_saving(self):
        reading = ai_reading({
            "kind": "factura_recibida", "number": "P-44", "supplier": "Ferretería Sol",
            "supplier_nif": SUPPLIER_NIF, "base": 100.0, "vat_rate": 21, "vat_amount": 21.0,
            "total": 150.0,
        })
        with (patch.object(whatsapp_documents, "_ai_allowed", return_value=True),
              patch.object(extraction, "read_document", return_value=reading)):
            result = self.send_pdf(b"%PDF-1.4 factura p-44")
        self.assertTrue(result["pending"])
        self.assertIn("⚠️", self.replies[-1])
        self.assertIn("no coincide", self.replies[-1])

        self.assertIn("Todavía no lo guardo", self.say("sí"))
        self.assertEqual(db.list_received_invoices(self.bid), [])

        self.assertIn("Cambiado: total", self.say("el total es 121"))
        self.assertIn("Hecho ✅", self.say("sí"))
        received = db.list_received_invoices(self.bid)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["total"], 121.0)
        self.assertEqual(received[0]["number"], "P-44")
        self.assertEqual(docrepo.get(result["document_id"], self.bid)["received_invoice_id"], received[0]["id"])

    def test_pdf_with_two_invoices_is_split_and_both_are_saved(self):
        pages = [
            f"FERRETERIA SOL S.L.\nCIF A81948077\nFactura F-{n}\nFecha 0{n}/09/2026\n"
            f"Base imponible {n}00,00\nIVA 21% {n * 21},00\nTOTAL FACTURA {n * 121},00"
            for n in (1, 2)
        ]
        reading = ai_reading(*[
            {"kind": "factura_recibida", "pages": [n, n], "number": f"F-{n}",
             "supplier": "Ferretería Sol", "supplier_nif": SUPPLIER_NIF,
             "base": n * 100.0, "vat_rate": 21, "vat_amount": n * 21.0, "total": n * 121.0}
            for n in (1, 2)
        ])
        with (patch.object(whatsapp_documents, "_ai_allowed", return_value=True),
              patch.object(extraction, "read_document", return_value=reading)):
            result = self.send_pdf(pdf(*pages), filename="dos-facturas.pdf")
        self.assertEqual(result["items"], 2)
        self.assertIn("He encontrado 2 facturas", self.replies[-1])
        self.assertIn("separado", self.replies[-1])
        self.assertTrue(docrepo.is_batch_source(result["document_id"], self.bid))

        reply = self.say("todas")
        self.assertIn("He guardado 2", reply)
        received = db.list_received_invoices(self.bid)
        self.assertEqual(sorted(row["total"] for row in received), [121.0, 242.0])
        linked = [doc for doc in docrepo.list_for_business(self.bid) if doc.get("received_invoice_id")]
        self.assertEqual(len(linked), 2)
        self.assertNotIn(result["document_id"], [doc["id"] for doc in linked])
        self.assertIsNone(self.pending())

    def test_statement_skips_invoices_already_registered(self):
        docservice.record_received_invoice(
            self.bid, total=121.0, supplier_name="Ferreteria Sol S.L.",
            supplier_nif=SUPPLIER_NIF, number="F-2026/0101",
        )
        statement = (
            "Ferreteria Sol S.L.  CIF A81948077\nEXTRACTO DE FACTURAS PENDIENTES\n"
            "Cliente: Reformas Norte SL\n"
            "F-2026/0101  02/07/2026   02/08/2026    121,00\n"
            "F-2026/0120  15/07/2026   15/08/2026    60,50\n"
            "F-2026/0153  12/09/2026   12/10/2026    66,55\n"
        )
        result = self.send_pdf(pdf(statement), filename="extracto.pdf")
        self.assertEqual(result["classification"], "extracto")
        self.assertEqual(result["items"], 2)
        self.assertIn("1 ya consta", self.replies[-1])
        self.assertIn("(1 de 2)", self.replies[-1])

        reply = self.say("no")
        self.assertIn("Descartada", reply)
        self.assertIn("(2 de 2)", reply)
        reply = self.say("sí")
        self.assertIn("Hecho ✅", reply)
        self.assertIn("Listo", reply)
        totals = sorted(row["total"] for row in db.list_received_invoices(self.bid))
        self.assertEqual(totals, [66.55, 121.0])
        self.assertIsNone(self.pending())

    def test_other_orders_pass_through_while_the_review_waits(self):
        self.send_photo(jpeg((200, 10, 10)))
        self.assertEqual(self.say("¿qué tengo hoy en la agenda?"), "respuesta del asistente")
        self.assertIsNotNone(self.pending())
        self.assertIn("Todavía no lo guardo", self.say("sí"))

    def test_newer_confirmation_elsewhere_is_not_taken_by_the_review(self):
        self.send_photo(jpeg((10, 200, 10)))
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE whatsapp_pending_actions SET created_at='2000-01-01T00:00:00' "
                "WHERE business_id=? AND phone=?", (self.bid, whatsapp_documents.review_key(PHONE)),
            )
        db.set_pending_action(self.bid, PHONE, "reclamar", {"invoice_id": 1})
        self.assertIsNone(whatsapp_documents.handle_reply(self.business, PHONE, "sí"))

    def test_received_invoice_already_registered_is_not_saved_twice(self):
        docservice.record_received_invoice(
            self.bid, total=121.0, supplier_name="Ferretería Sol", supplier_nif=SUPPLIER_NIF,
            number="P-44",
        )
        reading = ai_reading({
            "kind": "factura_recibida", "number": "P44", "supplier": "Ferretería Sol",
            "supplier_nif": SUPPLIER_NIF, "base": 100.0, "vat_rate": 21, "vat_amount": 21.0,
            "total": 121.0,
        })
        with (patch.object(whatsapp_documents, "_ai_allowed", return_value=True),
              patch.object(extraction, "read_document", return_value=reading)):
            result = self.send_pdf(b"%PDF-1.4 duplicada")
        self.assertIn("ya constaba", self.say("sí"))
        self.assertEqual(len(db.list_received_invoices(self.bid)), 1)
        self.assertEqual(docrepo.get(result["document_id"], self.bid)["doc_status"], "duplicado")

    def test_own_invoice_is_archived_without_issuing_it_again(self):
        reading = ai_reading({
            "kind": "factura_emitida", "number": "2026-15", "supplier": "Reformas Norte SL",
            "supplier_nif": OWN_NIF, "customer": "Ferretería Sol", "customer_nif": SUPPLIER_NIF,
            "base": 200.0, "vat_rate": 21, "vat_amount": 42.0, "total": 242.0,
        })
        with (patch.object(whatsapp_documents, "_ai_allowed", return_value=True),
              patch.object(extraction, "read_document", return_value=reading)):
            result = self.send_pdf(b"%PDF-1.4 emitida")
        self.assertIn("emitida por ti", self.replies[-1])
        self.assertIn("Archivada", self.say("sí"))
        document = docrepo.get(result["document_id"], self.bid)
        self.assertEqual((document["kind"], document["doc_status"]), ("factura_emitida", "revisado"))
        self.assertEqual(db.list_invoices(self.bid), [])
        self.assertEqual(db.list_received_invoices(self.bid), [])

    def test_caption_with_labelled_data_is_used_but_a_project_name_is_not(self):
        self.send_photo(jpeg((5, 5, 250)), caption="total 12,50 proveedor Bar Pepe")
        self.assertIn("Total *12,50 €*", self.replies[-1])
        self.assertIn("Apuntado ✅", self.say("sí"))
        self.assertEqual(db.list_expenses(self.bid)[0]["amount"], 12.5)

    def test_correction_starting_with_no_is_applied_not_discarded(self):
        reading = ai_reading({"kind": "ticket", "supplier": "Bar Pepe", "total": 30.0})
        with (patch.object(whatsapp_documents, "_ai_allowed", return_value=True),
              patch.object(extraction, "read_document", return_value=reading)):
            self.send_photo(jpeg((90, 90, 90)))
        self.assertIn("Cambiado: total", self.say("no, son 13,40"))
        self.assertIn("Apuntado ✅ Gasto de 13,40 €", self.say("vale"))


if __name__ == "__main__":
    unittest.main()
