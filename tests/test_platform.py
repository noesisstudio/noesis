"""Regresión de la capa plataforma (migración 18): productos, CRM, solicitudes
de gestoría, idioma, P&G honesto y plan diario ampliado."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from noesis import config, db, migrations
from noesis.web import chat


class PlatformTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        self.original_docs_path = config.DOCS_PATH
        self.original_database_url = config.DATABASE_URL
        config.DATABASE_URL = ""
        config.DB_PATH = Path(self.tempdir.name) / "test.db"
        config.DOCS_PATH = Path(self.tempdir.name) / "uploads"
        db.init_db()
        self.business = db.create_business("Obras Delta", "delta@example.com")
        self.other = db.create_business("Ajeno SL", "ajeno@example.com")
        self.bid = self.business["id"]

    def tearDown(self):
        config.DB_PATH = self.original_db_path
        config.DOCS_PATH = self.original_docs_path
        config.DATABASE_URL = self.original_database_url
        self.tempdir.cleanup()

    # -------------------------------------------------------------- Productos
    def test_product_margin_only_with_cost(self):
        with_cost = db.add_product("Hora de obra", price=45, cost=20,
                                   business_id=self.bid)
        self.assertEqual(with_cost["margin"], 25.0)
        self.assertEqual(with_cost["margin_pct"], 55.6)
        without = db.add_product("Visita", price=30, business_id=self.bid)
        self.assertIsNone(without["margin"])
        self.assertIsNone(without["margin_pct"])

    def test_product_validation_and_isolation(self):
        db.add_product("Hora", price=40, business_id=self.bid)
        with self.assertRaises(ValueError):
            db.add_product("Hora", price=40, business_id=self.bid)
        with self.assertRaises(ValueError):
            db.add_product("Mal IVA", price=10, vat_rate=15,
                           business_id=self.bid)
        with self.assertRaises(ValueError):
            db.add_product("Negativo", price=-5, business_id=self.bid)
        self.assertEqual(db.list_products(self.other["id"]), [])

    def test_product_low_stock_and_deactivate(self):
        p = db.add_product("Tornillos", kind="producto", price=3, stock=2,
                           stock_alert=5, business_id=self.bid)
        self.assertTrue(p["low_stock"])
        db.update_product(p["id"], business_id=self.bid, active=False)
        self.assertEqual(db.list_products(self.bid), [])
        self.assertEqual(
            len(db.list_products(self.bid, include_inactive=True)), 1)
        with self.assertRaises(ValueError):
            db.update_product(p["id"], business_id=self.bid, price="no")
        with self.assertRaises(ValueError):
            db.update_product(p["id"], business_id=self.other["id"], price=4)

    # ------------------------------------------------------------------- CRM
    def test_lead_lifecycle_and_convert(self):
        lead = db.add_lead("María — reforma baño", phone="600111222",
                           source="WhatsApp", value_estimate=1500,
                           next_action_on="2026-07-01", business_id=self.bid)
        self.assertEqual(lead["status"], "nuevo")
        db.update_lead(lead["id"], business_id=self.bid,
                       status="presupuesto_enviado")
        due = db.leads_due_today(self.bid)
        self.assertEqual([l["id"] for l in due], [lead["id"]])
        result = db.convert_lead_to_client(lead["id"], business_id=self.bid)
        self.assertEqual(result["lead"]["status"], "ganado")
        self.assertEqual(result["lead"]["client_id"], result["client"]["id"])
        # Convertido: ya no cuenta como seguimiento pendiente.
        self.assertEqual(db.leads_due_today(self.bid), [])
        with self.assertRaises(ValueError):
            db.convert_lead_to_client(lead["id"], business_id=self.bid)

    def test_lead_validation_and_isolation(self):
        with self.assertRaises(ValueError):
            db.add_lead("", business_id=self.bid)
        with self.assertRaises(ValueError):
            db.add_lead("X", next_action_on="1/7/2026", business_id=self.bid)
        lead = db.add_lead("Solo mío", business_id=self.bid)
        self.assertIsNone(db.get_lead(lead["id"], self.other["id"]))
        with self.assertRaises(ValueError):
            db.update_lead(lead["id"], business_id=self.bid, status="volando")

    # ------------------------------------------------- Solicitudes gestoría
    def test_gestoria_request_flow(self):
        req = db.add_gestoria_request("Falta la factura de la furgoneta.",
                                      business_id=self.bid)
        self.assertEqual(req["status"], "abierta")
        with self.assertRaises(ValueError):
            db.add_gestoria_request("", business_id=self.bid)
        replied = db.reply_gestoria_request(
            req["id"], "Subida, la tienes en Documentos.",
            business_id=self.bid)
        self.assertEqual(replied["status"], "respondida")
        self.assertEqual(
            db.list_gestoria_requests(self.bid, status="abierta"), [])
        with self.assertRaises(ValueError):
            db.reply_gestoria_request(req["id"], "Fuga",
                                      business_id=self.other["id"])

    # ---------------------------------------------------------------- Idioma
    def test_language_persists_and_validates(self):
        db.update_language(self.bid, "ca")
        self.assertEqual(db.get_business(self.bid)["language"], "ca")
        with self.assertRaises(ValueError):
            db.update_language(self.bid, "klingon")

    # ------------------------------------------------------------------- P&G
    def test_pnl_never_invents_numbers(self):
        empty = db.profit_and_loss(self.bid)
        self.assertIsNone(empty["revenue"])
        self.assertIsNone(empty["gross_result"])
        self.assertIsNone(empty["ebitda_estimate"])
        self.assertTrue(any("factura" in m for m in empty["missing"]))
        # Con solo gastos sigue sin inventar resultado.
        db.add_expense("Gasolina", 50, vat_rate=21, business_id=self.bid)
        partial = db.profit_and_loss(self.bid)
        self.assertIsNotNone(partial["costs"])
        self.assertIsNone(partial["gross_result"])

    # ------------------------------------------------------------ Plan diario
    def test_daily_plan_includes_new_signals(self):
        from noesis.documents import service as docservice
        db.add_lead("Frío SA", next_action_on="2026-01-01",
                    business_id=self.bid)
        db.add_gestoria_request("Necesito el modelo 130.",
                                business_id=self.bid)
        doc = docservice.upload(self.bid, "papel.pdf", b"%PDF-1.4 x",
                                run_ocr=False)
        from noesis.documents import repo as docrepo
        docrepo.set_review(doc["id"], self.bid,
                           doc_status="pendiente_revisar")
        db.add_received_invoice(99.0, business_id=self.bid)
        topics = {item["topic"] for item in
                  chat._daily_plan(chat._business_state(self.bid))}
        self.assertLessEqual({"crm", "gestoria", "documentos", "pagos"},
                             topics)

    # ------------------------------------------------------- Asistente por página
    def test_page_briefing_uses_real_data(self):
        text = chat.page_briefing(self.bid, "documentos")
        self.assertIn("No tienes documentos pendientes", text)
        self.assertIsNone(chat.page_briefing(self.bid, "pagina-inventada"))
        reply = chat.handle(self.bid, "¿qué significa esta página?",
                            page="crm")
        self.assertEqual(reply["source"], "local")
        self.assertIn("CRM".lower(), reply["reply"].lower())

    # -------------------------------------------------------- RGPD y migración
    def test_export_and_cascade_cover_new_tables(self):
        db.add_product("Hora", price=40, business_id=self.bid)
        db.add_lead("Lead", business_id=self.bid)
        db.add_gestoria_request("Hola", business_id=self.bid)
        db.add_supplier("Prov", business_id=self.bid)
        db.add_received_invoice(10, business_id=self.bid)
        data = db.export_business_data(self.bid)
        for key in ("products", "leads", "gestoria_requests", "suppliers",
                    "received_invoices"):
            self.assertEqual(len(data[key]), 1, key)
        self.assertTrue(db.delete_business_cascade(self.bid))
        self.assertIsNone(db.get_business(self.bid))

    def test_migration_18_roundtrip(self):
        self.assertEqual(migrations.current_version(),
                         migrations.LATEST_VERSION)
        self.assertEqual(migrations.downgrade(17), 17)
        self.assertEqual(migrations.upgrade(), migrations.LATEST_VERSION)
        db.add_product("Post", price=1, business_id=self.other["id"])


if __name__ == "__main__":
    unittest.main()
