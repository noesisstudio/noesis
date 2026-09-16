"""Órdenes de agenda en lenguaje natural, con y sin cliente.

«Añade un trabajo para mañana a las 12» era una orden corriente que el cerebro
local no entendía: solo reconocía agenda/apunta/cita/reserva y siempre con cliente,
así que la frase caía en el respaldo de IA y, sin IA, en un mensaje de disculpa.
"""

import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from noesis import config, db, nlu
from noesis.web import chat

TOMORROW = date.today() + timedelta(days=1)


class AgendaParsingTests(unittest.TestCase):
    def test_add_a_job_with_date_but_no_client_keeps_the_date(self):
        tool, args = nlu.parse("añade un trabajo para mañana a las 12")
        self.assertEqual(tool, nlu.NEED_JOB_CLIENT)
        self.assertEqual(
            args["fecha_hora"],
            datetime(TOMORROW.year, TOMORROW.month, TOMORROW.day, 12, 0).isoformat(timespec="minutes"),
        )

    def test_other_ways_of_asking_for_the_same_thing(self):
        for order in (
            "agrega un trabajo mañana a las 12",
            "pon una cita para mañana a las 12",
            "créame una visita mañana a las 12",
            "programa un aviso mañana a las 12",
        ):
            with self.subTest(order=order):
                self.assertEqual(nlu.parse(order)[0], nlu.NEED_JOB_CLIENT)

    def test_client_and_date_still_create_the_job_directly(self):
        tool, args = nlu.parse("agenda a Marta López mañana a las 10 para reparar la caldera")
        self.assertEqual(tool, "agendar_trabajo")
        self.assertEqual(args["cliente"], "Marta López")
        self.assertEqual(args["descripcion"], "reparar la caldera")

    def test_client_written_after_the_date_is_understood(self):
        tool, args = nlu.parse("añade una visita el jueves por la tarde para Ana Ruiz")
        self.assertEqual(tool, "agendar_trabajo")
        self.assertEqual(args["cliente"], "Ana Ruiz")

    def test_a_job_without_date_asks_only_for_the_day(self):
        self.assertEqual(nlu.parse("apunta un trabajo para Ana Ruiz")[0], nlu.NEED_DATE)

    def test_other_orders_are_not_swallowed_by_the_agenda(self):
        for order, expected in (
            ("crear cliente Ana Ruiz", "crear_cliente"),
            ("hazme una factura a Juan de 100 euros", "crear_factura"),
            ("gasté 45 euros en gasolina", "registrar_gasto"),
            ("qué trabajos tengo hoy", "ver_agenda"),
        ):
            with self.subTest(order=order):
                self.assertEqual(nlu.parse(order)[0], expected)


class AgendaConversationTests(unittest.TestCase):
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
        self.business = db.create_business("Reformas Norte SL", "norte@example.com")
        self.bid = self.business["id"]
        self.client = db.add_client("Marta López", business_id=self.bid)

    def tearDown(self):
        for name, value in self.saved.items():
            setattr(config, name, value)
        self.tempdir.cleanup()

    def say(self, message):
        return chat.handle(self.bid, message, actor_id="7:1")["reply"]

    def jobs(self):
        return db.jobs_for_date(TOMORROW.isoformat(), self.bid)

    def test_the_missing_client_is_asked_and_a_name_finishes_the_job(self):
        reply = self.say("añade un trabajo para mañana a las 12")
        self.assertIn("Me falta el cliente", reply)
        self.assertIn("mañana a las 12:00", reply)
        self.assertEqual(self.jobs(), [])

        self.say("Marta López")
        jobs = self.jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["client_id"], self.client["id"])
        self.assertTrue(str(jobs[0]["scheduled_for"]).endswith("12:00"))

        # La pendiente se consumió: repetir el nombre no crea un segundo trabajo.
        self.say("Marta López")
        self.assertEqual(len(self.jobs()), 1)

    def test_a_yes_never_completes_a_job_by_itself(self):
        self.say("añade un trabajo para mañana a las 12")
        self.say("sí")
        self.assertEqual(self.jobs(), [])
        self.assertEqual(len(db.list_clients(self.bid)), 1)

    def test_the_description_survives_the_question(self):
        reply = self.say("añade un trabajo para mañana a las 9 para cambiar el termo")
        self.assertIn("cambiar el termo", reply)
        self.say("con Marta López")
        jobs = db.jobs_for_date(TOMORROW.isoformat(), self.bid)
        self.assertEqual(jobs[0]["description"], "cambiar el termo")

    def test_an_unrelated_order_does_not_become_a_client_name(self):
        self.say("añade un trabajo para mañana a las 12")
        with patch.object(chat, "_coach_reply", return_value="consejo"):
            self.say("cuánto llevo facturado este mes")
        self.assertEqual(self.jobs(), [])


if __name__ == "__main__":
    unittest.main()
