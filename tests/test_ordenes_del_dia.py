"""Las órdenes de cada día dichas como se hablan: gastos, agenda y cobros.

Barrido del 23-09-2026, pedido por el founder: «hay muchos errores y no funciona
del todo bien». Se midió antes de tocar nada, con la misma factura de siempre
aparte: de 21 frases naturales repartidas por las cuatro zonas, fallaban 10.

Lo que se encontró, por orden de daño:

- **Cobros, 0 de 4.** El patrón solo aceptaba «pagado» y «cobrado» en masculino,
  y una factura es femenina. «La factura 1 está cobrada» no se entendía y, peor,
  se contestaba «dime cliente, concepto e importe»: se ofrecía crear una factura
  nueva a quien acababa de decir que ya le habían pagado una.
- **Gastos.** La lista de verbos era corta: «pon un gasto…», «anota…» y «mete…»
  no entraban, y la frase acababa en la agenda o en el parte del día. Y el
  concepto se quedaba con la preposición pegada («gasolina de»).
- **Agenda.** «Apúntame mañana a las 10 con Jordi Mas» pedía el cliente teniéndolo
  delante: la primera coincidencia se tragaba el «con» desde el «a» de «a las».
  Y la descripción del trabajo se quedaba con el nombre y la fecha dentro.

Cuando una frase real falle en producción, se añade aquí con lo que se esperaba.
"""
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from noesis import config, db, nlu
from noesis.web import chat

# Frase real -> (concepto, importe) del gasto que tiene que quedar registrado.
CORPUS_GASTOS = {
    "gasté 35 euros en gasolina": ("gasolina", 35.0),
    "he gastado 35 en gasolina": ("gasolina", 35.0),
    "apunta 20 euros de material": ("material", 20.0),
    "me he gastado 47,50 en la ferretería": ("la ferretería", 47.5),
    "gasto de 60 euros en herramientas": ("herramientas", 60.0),
    "pon un gasto de gasolina de 35 euros": ("gasolina", 35.0),
    "anota 15 euros de parking": ("parking", 15.0),
    "mete un gasto de 80 euros en herramientas": ("herramientas", 80.0),
    "compré material por 120 euros": ("material", 120.0),
}

# Frase real -> (cliente, descripción) del trabajo agendado.
CORPUS_AGENDA = {
    "agenda a Jordi Mas mañana a las 10": ("Jordi Mas", "Trabajo"),
    "apúntame mañana a las 10 con Jordi Mas": ("Jordi Mas", "Trabajo"),
    "añade un trabajo para Jordi Mas mañana a las 10": ("Jordi Mas", "Trabajo"),
    "cita con Jordi Mas mañana a las 10": ("Jordi Mas", "Trabajo"),
    "agenda a Jordi Mas mañana para cambiar el termo":
        ("Jordi Mas", "cambiar el termo"),
}

# Todas dicen lo mismo: esa factura ya está cobrada.
CORPUS_COBROS = (
    "Jordi Mas me ha pagado la factura 1",
    "la factura 1 está cobrada",
    "marca la factura 1 como pagada",
    "cobrada la factura 1",
    "he cobrado la factura 1",
    "pon la factura 1 como pagada",
)


class _Base(unittest.TestCase):
    REVISION = False

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = patch.multiple(
            config, DATABASE_URL="", DB_PATH=Path(self.temp.name) / "t.db",
            BACKUP_DIR=Path(self.temp.name) / "b",
            DOCS_PATH=Path(self.temp.name) / "d", ANTHROPIC_API_KEY="",
            ASSISTANT_REVIEW_ENABLED=self.REVISION)
        self.settings.start()
        db.init_db()
        self.bid = db.create_business("Reformas Prueba", "a@example.com")["id"]
        db.update_fiscal(self.bid, nif="12345678Z", address="Calle Prueba 1")

    def tearDown(self):
        self.settings.stop()
        self.temp.cleanup()

    def wa(self, frase):
        return chat.handle(self.bid, frase, channel="whatsapp",
                           actor_phone="34600111222")["reply"]


class GastosTests(_Base):
    def test_every_way_of_saying_an_expense(self):
        for numero, (frase, esperado) in enumerate(CORPUS_GASTOS.items()):
            concepto, importe = esperado
            with self.subTest(frase=frase):
                if numero:
                    self.tearDown()
                    self.setUp()
                self.wa(frase)
                gastos = db.list_expenses(self.bid)
                self.assertEqual(len(gastos), 1, frase)
                self.assertAlmostEqual(float(gastos[0]["amount"]), importe, 2)
                self.assertEqual(gastos[0]["concept"], concepto)

    def test_an_invoice_is_never_taken_for_an_expense(self):
        # El contrapeso: los verbos nuevos («pon», «apunta») también abren
        # facturas y citas, así que no pueden tragárselo todo.
        db.add_client("Jordi Mas", business_id=self.bid)
        self.wa("hazme una factura a Jordi Mas por reforma 500 euros")
        self.assertEqual(db.list_expenses(self.bid), [])
        self.assertEqual(len(db.list_invoices(self.bid)), 1)


class AgendaTests(_Base):
    def _trabajos(self):
        encontrados = []
        for dias in range(0, 9):
            dia = (date.today() + timedelta(days=dias)).isoformat()
            encontrados += db.jobs_for_date(dia, self.bid)
        return encontrados

    def test_every_way_of_booking_a_job(self):
        for numero, (frase, esperado) in enumerate(CORPUS_AGENDA.items()):
            cliente, descripcion = esperado
            with self.subTest(frase=frase):
                if numero:
                    self.tearDown()
                    self.setUp()
                db.add_client("Jordi Mas", business_id=self.bid)
                self.wa(frase)
                trabajos = self._trabajos()
                self.assertEqual(len(trabajos), 1, frase)
                ficha = db.get_client(trabajos[0]["client_id"], self.bid)
                self.assertEqual(ficha["name"], cliente)
                self.assertEqual(trabajos[0]["description"], descripcion)

    def test_the_date_is_not_the_description_of_the_job(self):
        # «para Jordi Mas mañana a las 10» dejaba la cita llamada así entera.
        _, datos = nlu.parse("añade un trabajo para Jordi Mas mañana a las 10")
        self.assertEqual(datos["descripcion"], "Trabajo")
        self.assertNotIn("mañana", datos["descripcion"])

    def test_the_task_keeps_its_own_words(self):
        # Y el contrapeso: cortar por la fecha no puede comerse el trabajo.
        _, datos = nlu.parse("agenda a Marta López el jueves para reparar la caldera")
        self.assertEqual(datos["descripcion"], "reparar la caldera")


class CobrosTests(_Base):
    REVISION = True  # como en producción: el dinero se confirma

    def _factura_emitida(self):
        cliente = db.add_client("Jordi Mas", nif="87654321X",
                                address="Calle Jordi 1", business_id=self.bid)
        factura = db.add_invoice(cliente["id"], "Obra", 100, business_id=self.bid)
        return db.issue_invoice(factura["id"], self.bid)

    def test_every_way_of_saying_it_is_paid(self):
        for numero, frase in enumerate(CORPUS_COBROS):
            with self.subTest(frase=frase):
                if numero:
                    self.tearDown()
                    self.setUp()
                self._factura_emitida()
                self.wa(frase)
                self.wa("sí")
                self.assertEqual(db.list_invoices(self.bid)[0]["status"],
                                 "cobrada", frase)

    def test_saying_it_is_paid_never_offers_to_create_another_invoice(self):
        # El fallo que más confundía: se contestaba «dime cliente, concepto e
        # importe» a quien acababa de decir que ya le habían pagado.
        self._factura_emitida()
        respuesta = self.wa("marca la factura 1 como pagada")
        self.assertNotIn("concepto e importe", respuesta)
        self.assertEqual(len(db.list_invoices(self.bid)), 1)

    def test_a_partial_payment_still_goes_to_review(self):
        # Un cobro a medias necesita importe y se revisa en Facturas: tolerar
        # más formas de decirlo no puede saltarse esa regla.
        self._factura_emitida()
        respuesta = self.wa("cobro parcial de la factura 1 de 50 euros")
        self.assertIn("parcial", respuesta.lower())
        self.assertEqual(db.list_invoices(self.bid)[0]["status"], "enviada")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
