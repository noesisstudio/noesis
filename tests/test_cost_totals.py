"""Las facturas de proveedor cuentan como gasto en el mes, no solo en el trimestre.

Antes, Costes podía decir «0 € de gasto» con facturas recibidas confirmadas,
mientras Impuestos ya las sumaba: dos pantallas contando distinto lo mismo.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from noesis import config, db


class MonthlyCostsTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        self.original_database_url = config.DATABASE_URL
        config.DATABASE_URL = ""
        config.DB_PATH = Path(self.tempdir.name) / "test.db"
        db.init_db()
        self.business = db.create_business("Reformas Norte", "norte@example.com")
        self.other = db.create_business("Limpiezas Sur", "sur@example.com")
        self.today = date.today()
        self.month = self.today.strftime("%Y-%m")

    def tearDown(self):
        config.DB_PATH = self.original_db_path
        config.DATABASE_URL = self.original_database_url
        self.tempdir.cleanup()

    def _received(self, business_id, **kwargs):
        supplier = (db.find_supplier(business_id, name="Suministros Pepe")
                    or db.add_supplier("Suministros Pepe",
                                       business_id=business_id))
        return db.add_received_invoice(
            kwargs.pop("total", 121), supplier_id=supplier["id"],
            business_id=business_id, **kwargs)

    def test_a_confirmed_supplier_invoice_shows_up_in_the_month(self):
        vacio = db.month_billing(business_id=self.business["id"])
        self.assertEqual(vacio["expenses"], 0)

        self._received(self.business["id"], base=100, vat_rate=21,
                       vat_amount=21, issued_on=self.today.isoformat())
        mes = db.month_billing(business_id=self.business["id"])
        self.assertEqual(mes["expenses"], 121)
        self.assertEqual(mes["expenses_received"], 121)
        self.assertEqual(mes["expenses_manual"], 0)
        self.assertEqual(mes["received_count"], 1)
        self.assertEqual(mes["expense_base"], 100)
        self.assertEqual(mes["vat_input"], 21)

    def test_manual_expenses_and_supplier_invoices_add_up_without_mixing(self):
        db.add_expense("Gasolina", 60.5, vat_rate=21,
                       business_id=self.business["id"])
        self._received(self.business["id"], base=100, vat_rate=21,
                       vat_amount=21, issued_on=self.today.isoformat())
        mes = db.month_billing(business_id=self.business["id"])
        self.assertEqual(mes["expenses"], 181.5)
        self.assertEqual(mes["expenses_manual"], 60.5)
        self.assertEqual(mes["expenses_received"], 121)
        self.assertEqual(mes["expense_count"], 1)
        self.assertEqual(mes["received_count"], 1)

    def test_a_supplier_invoice_without_base_never_invents_one(self):
        self._received(self.business["id"], total=200,
                       issued_on=self.today.isoformat())
        mes = db.month_billing(business_id=self.business["id"])
        self.assertEqual(mes["expenses"], 200)
        # Sin base declarada, el total es lo único cierto: IVA soportado cero.
        self.assertEqual(mes["expense_base"], 200)
        self.assertEqual(mes["vat_input"], 0)

    def test_another_month_and_another_business_stay_out(self):
        otro_mes = date(self.today.year - 1, 1, 15).isoformat()
        self._received(self.business["id"], base=500, vat_amount=105,
                       total=605, issued_on=otro_mes)
        self._received(self.other["id"], base=100, vat_amount=21, total=121,
                       issued_on=self.today.isoformat())
        mes = db.month_billing(business_id=self.business["id"])
        self.assertEqual(mes["expenses"], 0)
        self.assertEqual(db.month_billing(
            otro_mes[:7], business_id=self.business["id"])["expenses"], 605)

    def test_the_category_chart_counts_supplier_invoices_too(self):
        db.add_expense("Gasolina", 60, category="Combustible",
                       business_id=self.business["id"])
        self._received(self.business["id"], total=121,
                       issued_on=self.today.isoformat())
        self._received(self.business["id"], total=40, category="Combustible",
                       issued_on=self.today.isoformat())
        categorias = {fila["category"]: fila
                      for fila in db.expenses_by_category(self.business["id"])}
        self.assertEqual(categorias["Combustible"]["total"], 100)
        self.assertEqual(categorias["Combustible"]["n"], 2)
        self.assertEqual(categorias["Facturas de proveedor"]["total"], 121)
        self.assertNotIn("Facturas de proveedor",
                         {fila["category"] for fila
                          in db.expenses_by_category(self.other["id"])})

    def test_the_costs_screen_reads_the_same_figure_as_the_tax_quarter(self):
        self._received(self.business["id"], base=100, vat_rate=21,
                       vat_amount=21, issued_on=self.today.isoformat())
        db.add_expense("Material", 50, vat_rate=21,
                       business_id=self.business["id"])
        mes = db.month_billing(business_id=self.business["id"])
        trimestre = db.tax_quarter(
            self.today.year, (self.today.month - 1) // 3 + 1,
            self.business["id"])
        self.assertEqual(mes["expenses"], trimestre["gastos"])

    def test_the_empty_invoices_screen_points_to_the_received_ones(self):
        from starlette.testclient import TestClient

        from noesis.web import auth, server

        password = "Prueba-segura-123!"  # pragma: allowlist secret
        db.create_user("costes@example.com", auth.hash_password(password),
                       self.business["id"])
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                client.post("/login", data={
                    "email": "costes@example.com", "password": password,
                }, follow_redirects=False)
                html = client.get(f"/b/{self.business['id']}/facturas").text
                self.assertIn("Costes &rarr; Facturas recibidas",
                              html.replace("→", "&rarr;"))


if __name__ == "__main__":
    unittest.main()
