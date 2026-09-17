"""Descargas en Excel: el archivo es un .xlsx real y los datos van tipados."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from datetime import date
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

from noesis import config, db
from noesis.web import reports, xlsx

SHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


class XlsxWriterTestCase(unittest.TestCase):
    def test_package_has_the_parts_excel_requires_and_parses(self):
        payload = xlsx.build_sheet(["A", "B"], [[1, "uno"]], title="Hoja")
        paquete = zipfile.ZipFile(BytesIO(payload))
        self.assertIsNone(paquete.testzip())
        for parte in ("[Content_Types].xml", "_rels/.rels", "xl/workbook.xml",
                      "xl/_rels/workbook.xml.rels", "xl/styles.xml",
                      "xl/worksheets/sheet1.xml"):
            self.assertIn(parte, paquete.namelist())
            ElementTree.fromstring(paquete.read(parte))

    def test_numbers_dates_and_text_keep_their_type(self):
        payload = xlsx.build_sheet(
            ["Fecha", "Importe", "Concepto", "Vacio"],
            [["2026-09-16", 605.0, "Bajante", ""],
             [date(2026, 1, 1), 12, "Otro", None]],
        )
        hoja = zipfile.ZipFile(BytesIO(payload)).read(
            "xl/worksheets/sheet1.xml").decode("utf-8")
        # 46281 = días entre 1899-12-30 y 2026-09-16.
        self.assertIn('<c r="A2" s="3"><v>46281</v></c>', hoja)
        self.assertIn('<c r="B2" s="2"><v>605.0</v></c>', hoja)
        self.assertIn('<c r="A3" s="3"><v>46023</v></c>', hoja)
        self.assertIn('<c r="D2"/>', hoja)
        self.assertNotIn("inlineStr", hoja.split("<row r=\"2\">")[1][:60])

    def test_user_text_cannot_become_a_formula_or_break_the_xml(self):
        payload = xlsx.build_sheet(
            ["Concepto"],
            [["=1+1"], ["<b>Ferretería</b> & Cía"], ["texto\x07con control"]],
        )
        hoja = zipfile.ZipFile(BytesIO(payload)).read(
            "xl/worksheets/sheet1.xml").decode("utf-8")
        ElementTree.fromstring(hoja)
        # Una celda inlineStr nunca se evalúa: no se emite ningún <f>.
        self.assertNotIn("<f>", hoja)
        self.assertIn("=1+1", hoja)
        self.assertIn("&lt;b&gt;Ferretería&lt;/b&gt; &amp; Cía", hoja)
        self.assertIn("textocon control", hoja)

    def test_sheet_name_is_trimmed_to_what_excel_accepts(self):
        payload = xlsx.build_sheet(["A"], [], title="Informe/2026: [muy largo] " * 3)
        libro = zipfile.ZipFile(BytesIO(payload)).read("xl/workbook.xml").decode()
        nombre = libro.split('name="')[1].split('"')[0]
        self.assertLessEqual(len(nombre), 31)
        for prohibido in ("/", ":", "[", "]", "*", "?", "\\"):
            self.assertNotIn(prohibido, nombre)

    def test_same_data_gives_the_same_file(self):
        primero = xlsx.build_sheet(["A"], [[1]], title="X")
        self.assertEqual(primero, xlsx.build_sheet(["A"], [[1]], title="X"))


class XlsxReportsTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        self.original_database_url = config.DATABASE_URL
        config.DATABASE_URL = ""
        config.DB_PATH = Path(self.tempdir.name) / "test.db"
        db.init_db()
        self.business = db.create_business("Reformas Norte", "norte@example.com")
        self.other = db.create_business("Limpiezas Sur", "sur@example.com")

    def tearDown(self):
        config.DB_PATH = self.original_db_path
        config.DATABASE_URL = self.original_database_url
        self.tempdir.cleanup()

    def _values(self, payload: bytes) -> list[str]:
        hoja = zipfile.ZipFile(BytesIO(payload)).read(
            "xl/worksheets/sheet1.xml").decode("utf-8")
        raiz = ElementTree.fromstring(hoja)
        textos = []
        for celda in raiz.iter(f"{SHEET_NS}c"):
            valor = celda.find(f"{SHEET_NS}v")
            texto = celda.find(f"{SHEET_NS}is/{SHEET_NS}t")
            if valor is not None:
                textos.append(valor.text)
            elif texto is not None:
                textos.append(texto.text)
        return textos

    def test_each_report_only_carries_its_own_business(self):
        cliente = db.add_client("Hotel Mar", business_id=self.business["id"])
        db.add_invoice(cliente["id"], "Reforma baño", 100, vat_rate=21,
                       business_id=self.business["id"])
        db.add_expense("Material", 50, vat_rate=21,
                       business_id=self.business["id"])
        proveedor = db.add_supplier("Suministros Sur",
                                    business_id=self.business["id"])
        db.add_received_invoice(121, supplier_id=proveedor["id"], number="P-1",
                                business_id=self.business["id"])

        ajeno = db.add_client("Cliente Ajeno", business_id=self.other["id"])
        db.add_invoice(ajeno["id"], "Trabajo ajeno", 999, vat_rate=21,
                       business_id=self.other["id"])

        facturas = self._values(reports.invoices_xlsx(self.business["id"]))
        self.assertIn("Reforma baño", facturas)
        self.assertNotIn("Trabajo ajeno", facturas)
        self.assertNotIn("Cliente Ajeno", facturas)

        costes = self._values(reports.costs_xlsx(self.business["id"]))
        self.assertIn("Material", costes)
        recibidas = self._values(
            reports.received_invoices_xlsx(self.business["id"]))
        self.assertIn("Suministros Sur", recibidas)
        self.assertIn("P-1", recibidas)

    def test_empty_business_still_downloads_a_valid_sheet(self):
        payload = reports.invoices_xlsx(self.business["id"])
        paquete = zipfile.ZipFile(BytesIO(payload))
        self.assertIsNone(paquete.testzip())
        self.assertIn("Numero", self._values(payload))

    def test_buttons_and_routes_deliver_an_xlsx_to_the_owner(self):
        from starlette.testclient import TestClient

        from noesis.web import auth, server

        cliente = db.add_client("Hotel Mar", business_id=self.business["id"])
        db.add_invoice(cliente["id"], "Reforma baño", 100, vat_rate=21,
                       business_id=self.business["id"])
        password = "Prueba-segura-123!"  # pragma: allowlist secret
        db.create_user("excel@example.com", auth.hash_password(password),
                       self.business["id"])
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                logged = client.post("/login", data={
                    "email": "excel@example.com", "password": password,
                }, follow_redirects=False)
                self.assertEqual(logged.status_code, 303)
                for pagina, ruta in (("facturas", "invoices"),
                                     ("costes", "costs")):
                    html = client.get(f"/b/{self.business['id']}/{pagina}").text
                    self.assertIn(f"/reports/{ruta}.xlsx", html)
                respuesta = client.get(
                    f"/api/{self.business['id']}/reports/invoices.xlsx")
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(respuesta.headers["content-type"],
                                 xlsx.MEDIA_TYPE)
                self.assertIn("noesis_facturas.xlsx",
                              respuesta.headers["content-disposition"])
                self.assertTrue(respuesta.content.startswith(b"PK"))
                self.assertIn("Reforma baño", self._values(respuesta.content))
                ajeno = client.get(
                    f"/api/{self.other['id']}/reports/invoices.xlsx")
                self.assertIn(ajeno.status_code, {403, 404})


if __name__ == "__main__":
    unittest.main()
