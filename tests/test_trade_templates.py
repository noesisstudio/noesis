"""Plantillas por oficio y contrato de las plantillas de Meta.

Dos cosas que se rompen en silencio si nadie las fija. La primera: cargar la
plantilla de un oficio dos veces no puede duplicar el catálogo del autónomo ni
perder el IVA de cada partida. La segunda: un parámetro de plantilla de WhatsApp
con un salto de línea hace que Meta rechace el mensaje entero, y eso no se ve
hasta que el envío falla en producción.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noesis import config, db, trades, whatsapp_templates
from noesis.web import auth, whatsapp

TEST_PASSWORD = "password-segura-123"  # pragma: allowlist secret


class TradeTemplatesTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.original = {
            name: getattr(config, name)
            for name in ("DB_PATH", "DOCS_PATH", "BACKUP_DIR", "DATABASE_URL")
        }
        root = Path(self.temporary.name)
        config.DATABASE_URL = ""
        config.DB_PATH = root / "oficios.db"
        config.DOCS_PATH = root / "uploads"
        config.BACKUP_DIR = root / "backups"
        db.init_db()
        self.business = db.create_business(
            "Fontanería Ruiz", "jefe@example.com", sector="Fontanero autónomo"
        )
        db.create_user(
            "jefe@example.com", auth.hash_password(TEST_PASSWORD),
            self.business["id"],
        )

    def tearDown(self):
        for name, value in self.original.items():
            setattr(config, name, value)
        self.temporary.cleanup()

    # ------------------------------------------------- plantillas por oficio --
    def test_el_oficio_se_adivina_por_como_lo_escribe_el_autonomo(self):
        """El sector es texto libre: hay que reconocer sus palabras, no las nuestras."""
        self.assertEqual(trades.suggest_trade("Fontanero autónomo"), "fontaneria")
        self.assertEqual(trades.suggest_trade("REFORMAS INTEGRALES"), "reformas")
        self.assertEqual(trades.suggest_trade("lampistería"), "fontaneria")
        self.assertIsNone(trades.suggest_trade(""))
        self.assertIsNone(trades.suggest_trade("consultoría de marca"))

    def test_cada_partida_llega_con_su_iva_y_dice_si_es_material(self):
        overview = {t["key"]: t for t in trades.catalog_overview(self.business["id"])}
        reformas = overview["reformas"]
        self.assertTrue(reformas["has_reduced_rate"])
        # El material de obra tributa al 21% aunque la mano de obra vaya al 10%.
        material = next(
            item for item in reformas["items"] if item["name"] == "Material de obra"
        )
        self.assertEqual(material["kind"], "producto")
        self.assertEqual(material["vat_rate"], 21)
        mano = next(
            item for item in reformas["items"]
            if item["name"] == "Mano de obra reforma"
        )
        self.assertEqual(mano["vat_rate"], trades.REDUCED_RATE)
        self.assertEqual(
            sum(entry["items"] for entry in reformas["vat_summary"]),
            reformas["count"],
        )

    def test_cargar_dos_veces_no_duplica_el_catalogo(self):
        first = trades.load_catalog(self.business["id"], "fontaneria")
        self.assertGreater(first["created"], 0)
        self.assertEqual(first["skipped"], 0)

        overview = {t["key"]: t for t in trades.catalog_overview(self.business["id"])}
        self.assertEqual(overview["fontaneria"]["pending"], 0)
        self.assertEqual(
            overview["fontaneria"]["already"], overview["fontaneria"]["count"]
        )

        second = trades.load_catalog(self.business["id"], "fontaneria")
        self.assertEqual(second["created"], 0)
        self.assertEqual(
            len(db.list_products(self.business["id"])), first["created"]
        )

    def test_el_catalogo_de_un_negocio_no_marca_el_de_otro(self):
        otro = db.create_business("Reformas Sur", "otro@example.com")
        trades.load_catalog(self.business["id"], "fontaneria")
        ajeno = {t["key"]: t for t in trades.catalog_overview(otro["id"])}
        self.assertEqual(ajeno["fontaneria"]["already"], 0)

    def test_la_pagina_de_oficios_muestra_las_plantillas_y_las_carga(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as http:
                http.post("/login", data={
                    "email": "jefe@example.com",
                    "password": TEST_PASSWORD,  # pragma: allowlist secret
                })
                page = http.get(f"/b/{self.business['id']}/oficios")
                self.assertEqual(page.status_code, 200)
                self.assertIn("Plantillas por oficio", page.text)

                data = http.get(
                    f"/api/{self.business['id']}/oficios/plantillas"
                ).json()
                self.assertEqual(data["sugerido"], "fontaneria")
                self.assertEqual(len(data["oficios"]), len(trades.TRADE_CATALOGS))

                loaded = http.post(
                    f"/api/{self.business['id']}/oficios/fontaneria/cargar",
                    json={},
                ).json()
                self.assertGreater(loaded["created"], 0)

        nombres = {p["name"] for p in db.list_products(self.business["id"])}
        self.assertIn("Mano de obra fontanería", nombres)

    # ------------------------------------------------------ plantillas de Meta --
    def test_ninguna_plantilla_declarada_seria_rechazada_por_meta(self):
        """Cuerpo solo con variables o huecos descolocados: rechazo seguro."""
        for spec in whatsapp_templates.SPECS:
            with self.subTest(plantilla=spec.name):
                self.assertEqual(spec.problems(), [])
                self.assertEqual(spec.category, "utility")

    def test_los_saltos_de_linea_nunca_viajan_dentro_de_un_hueco(self):
        """Meta rechaza el mensaje entero si un parámetro trae un salto de línea."""
        self.assertEqual(
            whatsapp.template_param("Obras\ny Reformas\tSur"),
            "Obras y Reformas Sur",
        )
        self.assertEqual(whatsapp.template_param("Juan" + " " * 6 + "Pérez"),
                         "Juan Pérez")
        self.assertEqual(whatsapp.template_param(None), "")
        self.assertEqual(len(whatsapp.template_param("x" * 2000)), 1024)

    def test_al_encolar_una_plantilla_los_valores_ya_van_saneados(self):
        message = whatsapp.queue_template(
            "34600111222",
            "noesis_factura_lista",
            ["Ana\nGarcía", "Fontanería Ruiz", "F-2026-1", "121,00 €", "https://x/y"],
            business_id=self.business["id"],
        )
        self.assertIn("Ana García", message["template_params"])
        self.assertNotIn("\\n", message["template_params"])
