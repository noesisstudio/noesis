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


class TicketYEnvioTests(_Base):
    """Tickets y órdenes sobre una factura que ya existe."""

    def test_a_ticket_without_a_concept_is_not_worth_zero_euros(self):
        # «Hazme un ticket de 40 euros» creaba un ticket de 0,00 € con concepto
        # «4»: el patrón partía el «40» en «4» y «0». Dato corrupto, no
        # malentendido.
        _, datos = nlu.parse("hazme un ticket de 40 euros")
        self.assertEqual(datos["base"], 40.0)
        self.assertEqual(datos["concepto"], "Venta")
        self.assertEqual(datos["tipo_factura"], "F2")

    def test_the_ticket_keeps_its_concept_and_client(self):
        for frase, concepto in (
            ("ticket de venta por cambiar el grifo 40 euros", "cambiar el grifo"),
            ("hazme un ticket a Juan por reparación 40 euros", "reparación"),
        ):
            with self.subTest(frase=frase):
                _, datos = nlu.parse(frase)
                self.assertEqual(datos["base"], 40.0)
                self.assertEqual(datos["concepto"], concepto)

    def test_sending_an_invoice_is_not_the_same_as_issuing_it(self):
        # Emitir le pone número definitivo y la cuenta para Hacienda: no se
        # adivina. Antes esto contestaba «dime cliente, concepto e importe».
        respuesta = self.wa("envía la factura 3")
        self.assertIn("emitir factura 3", respuesta)
        self.assertNotIn("concepto e importe", respuesta)
        self.assertEqual(db.list_invoices(self.bid), [])

    def test_naming_an_invoice_never_offers_to_create_another(self):
        # El patrón de fondo que provocaba duplicados: cualquier frase que
        # nombre una factura por su número habla de una que ya existe.
        for frase in ("pásame la factura 3", "pásame factura 3 en PDF",
                      "qué pasa con la factura 3"):
            with self.subTest(frase=frase):
                respuesta = self.wa(frase)
                self.assertNotIn("concepto e importe", respuesta)
                self.assertEqual(db.list_invoices(self.bid), [])


class ConsultasTests(unittest.TestCase):
    def test_asking_what_is_on_the_agenda(self):
        # «Qué trabajos tengo mañana» no encajaba por la tilde de «qué»: se
        # comparaba contra el texto con acentos en vez de contra el normalizado.
        for frase in ("qué trabajos tengo mañana", "qué tengo hoy",
                      "agenda de mañana", "que citas tengo hoy"):
            with self.subTest(frase=frase):
                self.assertEqual(nlu.parse(frase)[0], "ver_agenda")

    def test_asking_what_is_pending_is_not_a_payment(self):
        # Contestaba con la explicación del cobro parcial a una pregunta.
        for frase in ("qué facturas tengo pendientes de cobro", "cuánto me deben",
                      "quién me debe dinero"):
            with self.subTest(frase=frase):
                self.assertEqual(nlu.parse(frase)[0], "ver_cobros_pendientes")


class CatalanTests(unittest.TestCase):
    """El producto se vende en Lleida y se habla catalán a diario.

    Barrido del 23-09: de ocho consultas en catalán funcionaba **una**, y «demà»
    no se reconocía como fecha, así que ninguna orden de agenda en catalán
    encontraba día. Las órdenes de factura sí funcionaban; las preguntas, no.
    """

    def test_the_questions_work_in_catalan(self):
        for frase, herramienta in (
            ("quant em deuen", "ver_cobros_pendientes"),
            ("qui em deu diners", "ver_cobros_pendientes"),
            ("factures pendents de cobrament", "ver_cobros_pendientes"),
            ("què tinc avui", "ver_agenda"),
            ("quins treballs tinc demà", "ver_agenda"),
            ("com vaig d'impostos", "ver_impuestos"),
            ("quant he facturat aquest mes", "resumen_negocio"),
            ("ensenyam els meus clients", "listar_clientes"),
        ):
            with self.subTest(frase=frase):
                self.assertEqual(nlu.parse(frase)[0], herramienta)

    def test_the_spanish_questions_still_work(self):
        # El contrapeso obligatorio: añadir un idioma no puede romper el otro.
        for frase, herramienta in (
            ("cuánto me deben", "ver_cobros_pendientes"),
            ("qué tengo hoy", "ver_agenda"),
            ("qué trabajos tengo mañana", "ver_agenda"),
            ("cómo voy de impuestos", "ver_impuestos"),
            ("cuánto he facturado este mes", "resumen_negocio"),
            ("enséñame mis clientes", "listar_clientes"),
        ):
            with self.subTest(frase=frase):
                self.assertEqual(nlu.parse(frase)[0], herramienta)

    def test_catalan_dates_and_weekdays(self):
        # «Demà» no era una fecha: la agenda en catalán no funcionaba nunca.
        for frase in ("agenda a Jordi Mas demà a les 10",
                      "agenda a Jordi Mas dijous a les 9"):
            with self.subTest(frase=frase):
                herramienta, datos = nlu.parse(frase)
                self.assertEqual(herramienta, "agendar_trabajo")
                self.assertEqual(datos["cliente"], "Jordi Mas")
                self.assertIn("T", datos["fecha_hora"])

    def test_catalan_orders_that_write(self):
        self.assertEqual(nlu.parse("he gastat 35 euros en gasolina"),
                         ("registrar_gasto", {"concepto": "gasolina",
                                              "importe": 35.0}))
        self.assertEqual(nlu.parse("crea el client Jordi Mas"),
                         ("crear_cliente", {"nombre": "Jordi Mas"}))
        self.assertEqual(nlu.parse("la factura 1 ja està cobrada"),
                         ("registrar_pago", {"factura_id": 1}))

    def test_the_role_is_read_by_its_root_not_by_the_exact_word(self):
        # «client» iba a proveedores porque se comparaba con la palabra exacta.
        for frase, herramienta in (
            ("crea el client Jordi Mas", "crear_cliente"),
            ("crea el cliente Jordi Mas", "crear_cliente"),
            ("crea el proveidor Materials Sol", "crear_proveedor"),
            ("nuevo proveedor Materiales Sol", "crear_proveedor"),
            ("da de alta a Jordi como client", "crear_cliente"),
        ):
            with self.subTest(frase=frase):
                self.assertEqual(nlu.parse(frase)[0], herramienta)


class VozTests(unittest.TestCase):
    """Una nota de voz no llega escrita como un mensaje tecleado.

    Al dictar, el importe viene en letra («trescientos euros») y la hora también
    («a las diez»). Antes el importe no se veía —la orden entera se caía— y la
    hora caía en un respaldo que agendaba a las 9:00 **sin avisar**, que es peor
    que no entenderla: te apunta la cita a otra hora y no te enteras.
    """

    def test_amounts_said_out_loud(self):
        for dicho, esperado in (
            ("gasté treinta y cinco euros en gasolina", 35.0),
            ("apunta veinte euros de material", 20.0),
            ("gasté cuarenta y siete euros con cincuenta en la ferretería", 47.5),
        ):
            with self.subTest(dicho=dicho):
                self.assertEqual(nlu.parse(dicho)[1]["importe"], esperado)
        for dicho, esperado in (
            ("hazme una factura a Jordi Mas por reforma trescientos euros", 300.0),
            ("hazme una factura a Jordi Mas por reforma setecientos cincuenta euros",
             750.0),
            ("hazme una factura a Jordi Mas por obra mil doscientos euros", 1200.0),
            ("hazme una factura a Jordi Mas por obra cien euros", 100.0),
        ):
            with self.subTest(dicho=dicho):
                self.assertEqual(nlu.parse(dicho)[1]["base"], esperado)

    def test_a_name_that_sounds_like_a_number_is_left_alone(self):
        # El contrapeso: solo se traducen las cifras pegadas a «euros», o un
        # cliente llamado «Tres Torres» se convertiría en «3 Torres».
        self.assertEqual(nlu._cifras_dictadas("factura a Tres Torres por obra 300 euros"),
                         "factura a Tres Torres por obra 300 euros")
        self.assertEqual(nlu._cifras_dictadas("crea el cliente Ochoa"),
                         "crea el cliente Ochoa")

    def test_times_said_out_loud(self):
        for dicho, esperado in (
            ("agenda a Jordi Mas mañana a las diez", "T10:00"),
            ("cita con Jordi Mas mañana a las nueve y media", "T09:30"),
            ("agenda a Jordi Mas mañana a las once menos cuarto", "T10:45"),
            ("agenda a Jordi Mas mañana a las doce y cuarto", "T12:15"),
            # «de la tarde» son las 17:00, no las 5 de la madrugada.
            ("agenda a Jordi Mas mañana a las cinco de la tarde", "T17:00"),
            ("agenda a Jordi Mas mañana a las 8 de la tarde", "T20:00"),
            # Y lo que ya funcionaba sigue igual.
            ("agenda a Jordi Mas mañana a las 10", "T10:00"),
            ("agenda a Jordi Mas mañana por la tarde", "T16:00"),
            ("agenda a Jordi Mas mañana", "T09:00"),
        ):
            with self.subTest(dicho=dicho):
                self.assertTrue(nlu.parse(dicho)[1]["fecha_hora"].endswith(esperado),
                                nlu.parse(dicho)[1]["fecha_hora"])

    def test_tomorrow_is_a_day_not_an_hour(self):
        # La raíz del fallo: «mañana» (el día) y «por la mañana» (la hora) valían
        # lo mismo, así que cualquier hora dicha en letra se perdía y quedaban
        # las 9:00.
        self.assertEqual(nlu._parse_time("manana a las diez"), (10, 0))
        self.assertEqual(nlu._parse_time("por la manana"), (9, 0))


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
