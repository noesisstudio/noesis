"""Reglas locales: los apellidos no son órdenes y «a nombre de» apunta al cliente."""
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from noesis import config, db, nlu
from noesis.web import chat


class LocalNameRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.stack = ExitStack()
        for key, value in {"DB_PATH": Path(self.temp.name) / "qa.db", "DOCS_PATH": Path(self.temp.name) / "docs",
                           "DATABASE_URL": "", "ASSISTANT_REVIEW_ENABLED": True, "ANTHROPIC_API_KEY": ""}.items():
            self.stack.enter_context(patch.object(config, key, value))
        self.stack.enter_context(patch("noesis.web.chat.ai_adapter.local_available", return_value=False))
        self.stack.enter_context(patch("noesis.web.chat.ai_adapter.external_available", return_value=False))
        db.init_db()
        self.bid = db.create_business("QA", "qa@example.test")["id"]

    def tearDown(self):
        self.stack.close()
        self.temp.cleanup()

    def say(self, text):
        return chat.handle(self.bid, text, actor_id="owner")

    def test_surname_is_not_a_delete_order(self):
        self.assertIsNone(nlu.safety_refusal("crea cliente Carla Borràs"))
        self.assertEqual(nlu.parse("crea cliente Carla Borràs"), ("crear_cliente", {"nombre": "Carla Borràs"}))
        self.assertTrue(self.say("crea cliente Carla Borràs").get("confirmation_required"))
        self.say("sí")
        self.assertEqual([c["name"] for c in db.list_clients(self.bid)], ["Carla Borràs"])

    def test_delete_verbs_are_still_blocked(self):
        for text in ("Borra el gasto 5", "bórralo", "elimina la factura 3", "cancela la cita de mañana", "esborra el client"):
            with self.subTest(text=text):
                self.assertIsNotNone(nlu.safety_refusal(text))

    def test_invoice_in_the_name_of_client(self):
        _tool, args = nlu.parse("hazme una factura a nombre de Carla de 100 euros")
        self.assertEqual(args["cliente"], "Carla")


if __name__ == "__main__":
    unittest.main()
