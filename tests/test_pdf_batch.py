"""Lotes PDF: aislamiento, conservación, reintentos y registro individual."""
from io import BytesIO
import json
import unittest
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject

from noesis import db, gestoria_workspace
from noesis.documents import pdf_batch, repo, service
from noesis.web.routers.documents import api_document_draft
from tests import test_backend as fixtures


class PdfBatchTests(unittest.TestCase):
    setUp = fixtures.BackendTestCase.setUp
    tearDown = fixtures.BackendTestCase.tearDown

    def source(self):
        business = db.create_business("Lotes", "lotes@example.com")
        writer = PdfWriter()
        for width in (300, 400, 500):
            writer.add_blank_page(width, 700)
        stream = BytesIO()
        writer.write(stream)
        data = stream.getvalue()
        doc = service.upload(business["id"], "varias-facturas.pdf", data, run_ocr=False)
        return business["id"], doc["id"], data

    def test_split_preserves_original_and_pages_without_accounting(self):
        bid, did, original = self.source()
        result = pdf_batch.split(bid, did, "1-2;3")
        self.assertTrue(result["ok"])
        self.assertEqual(service.file_bytes(bid, did)[0], original)
        self.assertEqual(len(result["documents"]), 2)
        for part, widths in zip(result["documents"], ((300, 400), (500,))):
            doc = repo.get(part["id"], bid)
            self.assertEqual(doc["doc_status"], "pendiente_revisar")
            self.assertIsNone(doc["client_id"])
            self.assertIsNone(doc["ocr_amount"])
            reader = PdfReader(BytesIO(service.file_bytes(bid, doc["id"])[0]))
            self.assertEqual(tuple(float(p.mediabox.width) for p in reader.pages), widths)
        self.assertEqual(db.list_invoices(bid), [])
        self.assertEqual(db.list_received_invoices(bid), [])
        self.assertEqual(db.list_expenses(bid), [])

    def test_repeat_reuses_parts_and_rejects_changed_partition(self):
        bid, did, _ = self.source()
        first = pdf_batch.split(bid, did, "1-2;3")
        second = pdf_batch.split(bid, did, "1 - 2; 3")
        self.assertEqual([d["id"] for d in first["documents"]], [d["id"] for d in second["documents"]])
        self.assertTrue(all(d["reused"] for d in second["documents"]))
        self.assertEqual(pdf_batch.inspect(bid, did)["ranges"], "1-2;3-3")
        with self.assertRaises(ValueError):
            pdf_batch.split(bid, did, "1;2-3")
        self.assertEqual(len(repo.list_for_business(bid)), 3)

    def test_invalid_ranges_have_no_writes(self):
        bid, did, _ = self.source()
        for ranges in ("1;3", "1-2;2-3", "2;3", "1-3", "1;2;3;4", "1-2;3;", None, "x", "1-999;3"):
            with self.subTest(ranges=ranges), self.assertRaises(ValueError):
                pdf_batch.split(bid, did, ranges)
        self.assertFalse(repo.is_batch_source(did, bid))
        self.assertEqual(len(repo.list_for_business(bid)), 1)

    def test_foreign_business_cannot_read_or_split(self):
        bid, did, _ = self.source()
        other = db.create_business("Otro", "otro@example.com")["id"]
        for call in (lambda: pdf_batch.inspect(other, did), lambda: pdf_batch.split(other, did, "1-2;3")):
            with self.assertRaises(ValueError):
                call()
        self.assertFalse(repo.is_batch_source(did, bid))

    def test_partial_failure_can_resume_without_duplicates(self):
        bid, did, _ = self.source()
        real_upload = service.upload
        calls = 0

        def interrupted(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise service.TransientUploadError("Prueba de fallo de almacenamiento")
            return real_upload(*args, **kwargs)

        with patch.object(service, "upload", side_effect=interrupted):
            result = pdf_batch.split(bid, did, "1-2;3")
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["documents"]), 1)
        self.assertTrue(repo.is_batch_source(did, bid))
        resumed = pdf_batch.split(bid, did, "1-2;3")
        self.assertTrue(resumed["ok"])
        self.assertTrue(resumed["documents"][0]["reused"])
        self.assertEqual(len(repo.list_for_business(bid)), 3)

    def test_source_cannot_be_counted_but_children_can(self):
        bid, did, _ = self.source()
        result = pdf_batch.split(bid, did, "1-2;3")
        for call in (
            lambda: db.add_received_invoice(300, document_id=did, business_id=bid),
            lambda: db.add_expense("Lote", 300, document_id=did, business_id=bid),
            lambda: service.confirm_received_invoice(bid, did, total=300, supplier_name="No crear"),
        ):
            with self.assertRaises(ValueError):
                call()
        self.assertEqual(api_document_draft(bid, did).status_code, 409)
        child = result["documents"][0]["id"]
        received = service.confirm_received_invoice(bid, child, total=121, base=100, vat_amount=21, vat_rate=21)
        with self.assertRaises(ValueError):
            db.add_expense("Duplicado", 121, document_id=child, business_id=bid)
        linked = repo.get(child, bid)
        self.assertEqual(linked["received_invoice_id"], received["id"])
        self.assertEqual(linked["doc_status"], "revisado")
        from datetime import date
        today = date.today()
        archive = gestoria_workspace.document_archive(bid, year=today.year, quarter=(today.month-1)//3+1)
        row = next(d for d in archive["documents"] if d["id"] == child)
        self.assertEqual(row["ocr_amount"], 121)
        self.assertEqual(row["record_url"], f"/b/{bid}/costes")
        self.assertTrue(next(d for d in archive["documents"] if d["id"] == did)["is_batch_source"])

    def test_accounted_source_cannot_be_split(self):
        bid, did, _ = self.source()
        db.add_received_invoice(121, document_id=did, business_id=bid)
        with self.assertRaises(ValueError):
            pdf_batch.split(bid, did, "1-2;3")

    def test_forms_are_not_split(self):
        bid, _did, original = self.source()
        writer = PdfWriter(clone_from=BytesIO(original))
        writer.root_object[NameObject("/AcroForm")] = DictionaryObject()
        stream = BytesIO()
        writer.write(stream)
        doc = service.upload(bid, "formulario.pdf", stream.getvalue(), run_ocr=False)
        with self.assertRaises(ValueError):
            pdf_batch.split(bid, doc["id"], "1-2;3")

    def test_failed_extraction_offers_manual_review_and_missing_is_404(self):
        bid, did, _ = self.source()
        with patch.object(service, "invoice_draft", return_value=None):
            result = api_document_draft(bid, did)
        self.assertEqual(result.status_code, 200)
        self.assertTrue(json.loads(result.body)["manual"])
        self.assertEqual(api_document_draft(bid, did+999).status_code, 404)
