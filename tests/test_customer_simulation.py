"""Simulación barata de un cliente: solo reglas locales y datos sintéticos."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noesis import config, db, nlu
from noesis.web import chat


class CustomerSimulationTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original = (config.DB_PATH, config.DOCS_PATH, config.DATABASE_URL)
        config.DATABASE_URL = ""
        config.DB_PATH = Path(self.tempdir.name) / "journey.db"
        config.DOCS_PATH = Path(self.tempdir.name) / "uploads"
        db.init_db()
        self.business = db.create_business("Instalaciones Prueba", "owner@example.com")
        db.update_fiscal(
            self.business["id"], nif="12345678Z", address="Calle Prueba 1"
        )

    def tearDown(self):
        config.DB_PATH, config.DOCS_PATH, config.DATABASE_URL = self.original
        self.tempdir.cleanup()

    def test_common_message_corpus_has_a_deterministic_route(self):
        corpus = {
            "crear cliente Ana Ruiz": "crear_cliente",
            "añade cliente Talleres Norte": "crear_cliente",
            "nuevo proveedor Materiales Sol": "crear_proveedor",
            "factura a Juan 95": "crear_factura",
            "factúrame a María 300": "crear_factura",
            "factura a Juan 1.250,50 euros": "crear_factura",
            "hazme una factura de 500 a Talleres López": "crear_factura",
            "factura a Juan por pintura 95 euros": "crear_factura",
            "hazme una factura a Juan de 100 euros": "crear_factura",
            "presupuesto a Ana por un baño 2.400 euros": "crear_presupuesto",
            "ticket de venta por desplazamiento 36,30 euros": "crear_factura",
            "gasté 45 euros en gasolina": "registrar_gasto",
            "compré 30 de tornillos": "registrar_gasto",
            "agenda a Marta mañana por la mañana": "agendar_trabajo",
            "qué trabajos tengo hoy": "ver_agenda",
            "quién me debe": "ver_cobros_pendientes",
            "cuánto llevo facturado": "resumen_negocio",
            "cómo va mi IVA": "ver_impuestos",
            "qué documentos tengo pendientes": "ver_documentos_pendientes",
            "cómo van mis proyectos": "ver_proyectos",
            "qué puedes hacer sin preguntarme": "ver_control_noesis",
            "crear usuario Paco": nlu.NEED_USER_INVITE,
            # Antes era NEED_INVOICE: pedía los tres datos y no creaba nada. Ahora
            # crea el borrador a medias (decisión del 22-09-2026).
            "hazme una factura": nlu.PARTIAL_INVOICE,
        }
        for message, expected in corpus.items():
            with self.subTest(message=message):
                parsed = nlu.parse(message)
                self.assertIsNotNone(parsed)
                self.assertEqual(parsed[0], expected)

    def test_end_to_end_local_office_journey_does_not_use_paid_ai(self):
        bid = self.business["id"]
        with (
            patch.object(config, "ANTHROPIC_API_KEY", ""),
            patch("noesis.web.chat.ai_adapter.local_available", return_value=False),
            patch("noesis.web.chat.ai_adapter.external_available", return_value=False),
        ):
            messages = (
                "crear cliente Ana Ruiz",
                "nuevo proveedor Materiales Sol",
                "factura a Ana Ruiz por reparar el termo 1.200,50 euros",
                "presupuesto a Ana Ruiz por revisar instalación 250 euros",
                "agenda a Ana Ruiz mañana por la mañana",
                "gasté 45 euros en gasolina",
                "cuánto llevo facturado",
                "cómo va mi IVA",
                "qué clientes tengo",
                "quién me debe",
            )
            replies = [chat.handle(bid, message) for message in messages]

        self.assertTrue(all(reply["source"] == "local" for reply in replies))
        self.assertEqual(len(db.list_invoices(bid)), 1)
        self.assertEqual(len(db.list_quotes(bid)), 1)
        self.assertEqual(len(db.list_expenses(bid)), 1)
        self.assertGreaterEqual(len(db.list_clients(bid)), 1)
        self.assertEqual(len(db.list_suppliers(bid)), 1)

        db.add_client("Sergio López", business_id=bid)
        db.add_client("Sergio Martínez", business_id=bid)
        before = len(db.list_invoices(bid))
        ambiguous = chat.handle(bid, "factura a Sergio 100 euros")
        self.assertIn("varios clientes", ambiguous["reply"])
        self.assertEqual(len(db.list_invoices(bid)), before)


if __name__ == "__main__":
    unittest.main()
