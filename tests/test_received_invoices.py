"""Regresión de proveedores, facturas recibidas y pipeline documental (mig. 17)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noesis import config, db, migrations
from noesis.adapters import extraction
from noesis.documents import repo as docrepo, service as docservice
from tests.fixtures import TINY_JPEG


class ReceivedInvoicesTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        self.original_docs_path = config.DOCS_PATH
        self.original_database_url = config.DATABASE_URL
        config.DATABASE_URL = ""
        config.DB_PATH = Path(self.tempdir.name) / "test.db"
        config.DOCS_PATH = Path(self.tempdir.name) / "uploads"
        db.init_db()
        self.business = db.create_business("Reformas Norte", "norte@example.com")
        self.other = db.create_business("Limpiezas Sur", "sur@example.com")
        db.update_fiscal(self.business["id"], nif="B11111111",
                         address="Calle Uno 1")

    def tearDown(self):
        config.DB_PATH = self.original_db_path
        config.DOCS_PATH = self.original_docs_path
        config.DATABASE_URL = self.original_database_url
        self.tempdir.cleanup()

    def test_universal_classifier_falls_back_locally_and_waits_for_confirmation(self):
        with patch.object(config, "ANTHROPIC_API_KEY", ""):
            doc = docservice.upload(
                self.business["id"], "ticket-ferreteria.jpg",
                TINY_JPEG, run_ocr=False, auto_classify=True,
            )
        self.assertEqual(doc["classification"]["kind"], "ticket")
        stored = docrepo.get(doc["id"], self.business["id"])
        self.assertEqual(stored["kind"], "ticket")
        self.assertEqual(stored["doc_status"], "pendiente_revisar")
        self.assertIsNone(docrepo.get(doc["id"], self.other["id"]))
        attempt = docrepo.latest_classification(doc["id"], self.business["id"])
        self.assertEqual(attempt["method"], "heuristica")
        self.assertIsNone(attempt["confirmed_kind"])

        docrepo.confirm_classification(doc["id"], self.business["id"], "ticket")
        self.assertEqual(
            docrepo.latest_classification(doc["id"], self.business["id"])["confirmed_kind"],
            "ticket",
        )

    def test_uncertain_document_is_not_forced_into_an_accounting_category(self):
        with patch.object(config, "ANTHROPIC_API_KEY", ""):
            doc = docservice.upload(
                self.business["id"], "papel.jpg", TINY_JPEG,
                run_ocr=False, auto_classify=True,
            )
        self.assertEqual(doc["classification"]["kind"], "documento")
        self.assertEqual(docrepo.get(doc["id"], self.business["id"])["kind"], "documento")

    def test_identical_documents_are_deduplicated_only_inside_the_business(self):
        first = docservice.upload(
            self.business["id"], "ticket-uno.jpg", TINY_JPEG, run_ocr=False
        )

        with self.assertRaises(docservice.DuplicateDocument) as duplicate:
            docservice.upload(
                self.business["id"], "ticket-copia.jpg", TINY_JPEG, run_ocr=False
            )

        self.assertEqual(duplicate.exception.existing_id, first["id"])
        self.assertEqual(len(first["content_sha256"]), 64)
        self.assertEqual(len(docrepo.list_for_business(self.business["id"])), 1)
        stored = list((config.DOCS_PATH / str(self.business["id"])).iterdir())
        self.assertEqual(len(stored), 1)

        other = docservice.upload(
            self.other["id"], "mismo-ticket.jpg", TINY_JPEG, run_ocr=False
        )
        self.assertEqual(other["content_sha256"], first["content_sha256"])

    def test_legacy_document_gets_its_hash_when_the_same_file_returns(self):
        first = docservice.upload(
            self.business["id"], "historico.jpg", TINY_JPEG, run_ocr=False
        )
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE documents SET content_sha256=NULL "
                "WHERE id=? AND business_id=?",
                (first["id"], self.business["id"]),
            )

        with self.assertRaises(docservice.DuplicateDocument):
            docservice.upload(
                self.business["id"], "historico-repetido.jpg", TINY_JPEG,
                run_ocr=False,
            )

        recovered = docrepo.get(first["id"], self.business["id"])
        self.assertEqual(len(recovered["content_sha256"]), 64)

    def test_document_search_is_human_and_isolated_by_business(self):
        client = db.add_client(
            "Marta Instalaciones", business_id=self.business["id"]
        )
        expected = docrepo.add(
            self.business["id"],
            filename="Factura-Caldera-2026.pdf",
            stored_name="search-one.pdf",
            mime="application/pdf",
            size=20,
            kind="factura_recibida",
            client_id=client["id"],
            note="Revisión anual del quemador",
            ocr_text="Proveedor Fuego Norte número F-204",
        )
        docrepo.add(
            self.other["id"],
            filename="Factura-Caldera-2026.pdf",
            stored_name="search-other.pdf",
            mime="application/pdf",
            size=20,
            kind="factura_recibida",
            note="Revisión anual del quemador",
        )

        for query in (
            "caldera",
            "MARTA",
            "quemador",
            "f-204",
            "factura recibida",
        ):
            with self.subTest(query=query):
                found = docrepo.list_for_business(
                    self.business["id"], search=query
                )
                self.assertEqual([row["id"] for row in found], [expected["id"]])

        self.assertEqual(
            docrepo.list_for_business(self.business["id"], search="sin resultado"),
            [],
        )

    def _upload_doc(self, business_id, filename="factura-luz.pdf"):
        return docservice.upload(business_id, filename, b"%PDF-1.4 demo",
                                 run_ocr=False)

    # ----------------------------------------------------------- Proveedores
    def test_supplier_crud_is_isolated_by_business(self):
        supplier = db.add_supplier("Endesa", nif="a81948077",
                                   business_id=self.business["id"])
        self.assertEqual(supplier["nif"], "A81948077")
        self.assertEqual(len(db.list_suppliers(self.business["id"])), 1)
        self.assertEqual(db.list_suppliers(self.other["id"]), [])
        self.assertIsNone(db.get_supplier(supplier["id"], self.other["id"]))
        with self.assertRaises(ValueError):
            db.add_supplier("Endesa", business_id=self.business["id"])
        # El mismo nombre en otro negocio no choca (aislamiento).
        db.add_supplier("Endesa", business_id=self.other["id"])

    def test_find_supplier_prefers_nif_over_name(self):
        by_nif = db.add_supplier("Iberdrola Clientes", nif="A95758389",
                                 business_id=self.business["id"])
        db.add_supplier("Iberdrola", business_id=self.business["id"])
        found = db.find_supplier(self.business["id"], nif="a95758389",
                                 name="Iberdrola")
        self.assertEqual(found["id"], by_nif["id"])

    # ---------------------------------------------------- Facturas recibidas
    def test_received_invoice_links_document_once(self):
        doc = self._upload_doc(self.business["id"])
        supplier = db.add_supplier("Endesa", business_id=self.business["id"])
        received = db.add_received_invoice(
            121.0, supplier_id=supplier["id"], base=100.0, vat_rate=21,
            vat_amount=21.0, number="F-2026-001", issued_on="2026-06-30",
            document_id=doc["id"], business_id=self.business["id"])
        self.assertEqual(received["status"], "pendiente")
        linked = docrepo.get(doc["id"], self.business["id"])
        self.assertEqual(linked["received_invoice_id"], received["id"])
        self.assertEqual(linked["doc_status"], "revisado")
        with self.assertRaises(ValueError):
            db.add_received_invoice(50.0, document_id=doc["id"],
                                    business_id=self.business["id"])

    def test_received_invoice_rejects_cross_business_data(self):
        doc_other = self._upload_doc(self.other["id"])
        supplier_other = db.add_supplier("Ajeno SL",
                                         business_id=self.other["id"])
        with self.assertRaises(ValueError):
            db.add_received_invoice(10.0, supplier_id=supplier_other["id"],
                                    business_id=self.business["id"])
        with self.assertRaises(ValueError):
            db.add_received_invoice(10.0, document_id=doc_other["id"],
                                    business_id=self.business["id"])
        db.add_received_invoice(10.0, business_id=self.business["id"])
        self.assertEqual(db.list_received_invoices(self.other["id"]), [])

    def test_received_invoice_validation(self):
        with self.assertRaises(ValueError):
            db.add_received_invoice(0, business_id=self.business["id"])
        with self.assertRaises(ValueError):
            db.add_received_invoice(100, vat_rate=15,
                                    business_id=self.business["id"])
        with self.assertRaises(ValueError):
            db.add_received_invoice(100, issued_on="30/06/2026",
                                    business_id=self.business["id"])

    def test_received_invoice_can_be_corrected_without_crossing_tenants(self):
        supplier = db.add_supplier("Proveedor Uno", business_id=self.business["id"])
        received = db.add_received_invoice(
            121, supplier_id=supplier["id"], number="ERR-1",
            business_id=self.business["id"],
        )
        corrected = db.update_received_invoice(
            received["id"], business_id=self.business["id"],
            number="F-2026-44", base=100, vat_rate=21, vat_amount=21,
            irpf_amount=0, total=121, issued_on="2026-09-01",
        )
        self.assertEqual(corrected["number"], "F-2026-44")
        self.assertEqual(corrected["base"], 100)
        with self.assertRaises(ValueError):
            db.update_received_invoice(
                received["id"], business_id=self.other["id"], total=10
            )

    def test_received_invoice_edit_button_reaches_the_authenticated_api(self):
        from starlette.testclient import TestClient

        from noesis.web import auth, server

        received = db.add_received_invoice(
            50, number="ANTES", business_id=self.business["id"]
        )
        password = "Prueba-segura-123!"  # pragma: allowlist secret
        db.create_user(
            "edicion@example.com", auth.hash_password(password),
            self.business["id"],
        )
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                logged = client.post("/login", data={
                    "email": "edicion@example.com", "password": password,
                }, follow_redirects=False)
                self.assertEqual(logged.status_code, 303)
                page = client.get(f"/b/{self.business['id']}/costes")
                self.assertIn("editReceived", page.text)
                response = client.patch(
                    f"/api/{self.business['id']}/received-invoices/{received['id']}",
                    json={"number": "DESPUES", "total": 60},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["number"], "DESPUES")
                foreign = client.patch(
                    f"/api/{self.other['id']}/received-invoices/{received['id']}",
                    json={"number": "AJENA", "total": 70},
                )
                self.assertIn(foreign.status_code, {403, 404})

    def test_status_cycle_and_delete_release_document(self):
        doc = self._upload_doc(self.business["id"])
        received = db.add_received_invoice(
            60.5, document_id=doc["id"], business_id=self.business["id"])
        paid = db.set_received_invoice_status(
            received["id"], "pagada", business_id=self.business["id"])
        self.assertEqual(paid["status"], "pagada")
        with self.assertRaises(ValueError):
            db.set_received_invoice_status(received["id"], "archivada",
                                           business_id=self.business["id"])
        db.delete_received_invoice(received["id"], self.business["id"])
        self.assertIsNone(
            docrepo.get(doc["id"],
                        self.business["id"])["received_invoice_id"])

    # ------------------------------------------------------ Pipeline y drafts
    def test_draft_without_ai_marks_document_pending(self):
        doc = self._upload_doc(self.business["id"])
        with patch.object(config, "ANTHROPIC_API_KEY", ""):
            draft = docservice.invoice_draft(self.business["id"], doc["id"])
        self.assertIsNone(draft)
        updated = docrepo.get(doc["id"], self.business["id"])
        self.assertEqual(updated["doc_status"], "pendiente_revisar")
        self.assertIsNotNone(updated["reviewed_at"])

    def test_draft_detects_direction_and_known_supplier(self):
        doc = self._upload_doc(self.business["id"])
        supplier = db.add_supplier("Endesa", nif="A81948077",
                                   business_id=self.business["id"])
        fake = {"number": "F-9", "issued_on": "2026-06-01", "due_on": None,
                "supplier": "Endesa", "supplier_nif": "A81948077",
                "customer": "Reformas Norte", "customer_nif": "B11111111",
                "base": 100.0, "vat_rate": 21, "vat_amount": 21.0,
                "irpf_amount": None, "total": 121.0, "confidence": 90}
        with patch.object(extraction, "extract_invoice", return_value=dict(fake)):
            draft = docservice.invoice_draft(self.business["id"], doc["id"])
        self.assertEqual(draft["direction"], "recibida")
        self.assertEqual(draft["supplier_id"], supplier["id"])
        updated = docrepo.get(doc["id"], self.business["id"])
        self.assertEqual(updated["kind"], "factura_recibida")
        self.assertEqual(updated["doc_status"], "pendiente_revisar")
        self.assertEqual(updated["confidence"], 90)

    def test_confirm_creates_supplier_and_links(self):
        doc = self._upload_doc(self.business["id"])
        received = docservice.confirm_received_invoice(
            self.business["id"], doc["id"], total=121.0,
            supplier_name="Materiales Pérez", supplier_nif="B22222222",
            base=100.0, vat_rate=21, vat_amount=21.0, number="MP-77")
        supplier = db.find_supplier(self.business["id"], nif="B22222222")
        self.assertIsNotNone(supplier)
        self.assertEqual(received["supplier_id"], supplier["id"])
        listed = db.list_received_invoices(self.business["id"])
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["supplier_name"], "Materiales Pérez")

    def test_detect_direction_is_conservative(self):
        draft = {"supplier": "Otra Empresa", "supplier_nif": "C1",
                 "customer": "Cliente Cualquiera", "customer_nif": "C2"}
        self.assertEqual(
            extraction.detect_direction(draft, business_nif="B11111111",
                                        business_name="Reformas Norte"),
            "desconocida")
        self.assertEqual(
            extraction.detect_direction(
                {"supplier": "Reformas Norte", "supplier_nif": "B11111111",
                 "customer": "Pepe", "customer_nif": None},
                business_nif="B11111111", business_name="Reformas Norte"),
            "emitida")

    def test_validated_invoice_discards_dubious_values(self):
        raw = {"number": "F-1", "total": "no-numero", "vat_rate": 15,
               "issued_on": "2026-13-40", "confidence": 400,
               "supplier": "  Endesa  "}
        result = extraction._validated_invoice(raw)
        self.assertEqual(result["supplier"], "Endesa")
        self.assertIsNone(result["total"])
        self.assertIsNone(result["vat_rate"])
        self.assertIsNone(result["issued_on"])
        self.assertIsNone(result["confidence"])

    def test_validated_invoice_warns_on_arithmetic_dates_and_spanish_nif(self):
        result = extraction._validated_invoice({
            "number": "F-2", "supplier": "Proveedor",
            "supplier_nif": "12345678A", "base": 100, "vat_rate": 21,
            "vat_amount": 10, "irpf_amount": 0, "total": 150,
            "issued_on": "2026-09-10", "due_on": "2026-09-01",
            "confidence": 98,
        })
        self.assertTrue(result["requires_review"])
        self.assertEqual(result["confidence"], 50)
        self.assertEqual(len(result["validation_issues"]), 4)

        coherent = extraction._validated_invoice({
            "number": "F-3", "supplier": "Proveedor",
            "supplier_nif": "12345678Z", "base": 100, "vat_rate": 21,
            "vat_amount": 21, "irpf_amount": 0, "total": 121,
            "confidence": 96,
        })
        self.assertFalse(coherent["requires_review"])
        self.assertEqual(coherent["confidence"], 96)

        foreign = extraction._validated_invoice({
            "number": "DE-1", "supplier": "Proveedor UE",
            "supplier_nif": "DE123456789", "total": 20, "confidence": 90,
        })
        self.assertFalse(foreign["requires_review"])

    def test_gestoria_package_includes_received_invoices(self):
        import io
        import zipfile

        from noesis.web import gestoria

        document = docservice.upload(
            self.business["id"], "factura-f9.pdf", b"%PDF-1.4 original",
            kind="factura", run_ocr=False,
        )
        db.add_received_invoice(
            121.0, number="F-9", issued_on="2026-06-15",
            document_id=document["id"], business_id=self.business["id"],
        )
        label = "2026-06"
        package = gestoria.build_package(self.business["id"], label)
        self.assertIsNotNone(package)
        payload, _meta = package
        with zipfile.ZipFile(io.BytesIO(payload)) as bundle:
            names = bundle.namelist()
            csv_name = "03-facturas-recibidas/facturas-recibidas.csv"
            self.assertIn(csv_name, names)
            self.assertTrue(any(
                name.startswith("03-facturas-recibidas/originales/")
                for name in names
            ))
            content = bundle.read(csv_name).decode("utf-8-sig")
        self.assertIn("F-9", content)
        self.assertIn("121.0", content)

    # ------------------------------------------------------------ Migración
    def test_migration_17_roundtrip(self):
        self.assertEqual(migrations.current_version(),
                         migrations.LATEST_VERSION)
        self.assertEqual(migrations.downgrade(16), 16)
        self.assertEqual(migrations.upgrade(), migrations.LATEST_VERSION)
        db.add_supplier("Post-roundtrip SL", business_id=self.business["id"])


if __name__ == "__main__":
    unittest.main()
