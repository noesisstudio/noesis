"""El nombre dictado por voz: dónde acaba el cliente y empieza la frase.

Caso real del founder, 23-09-2026, por WhatsApp. Dictó «hazme una factura a
Reformas Martínez. Concepto ventanas 850 euros» y recibió «No encuentro un cliente
inequívoco llamado "Reformas Martínez. Concierto Ventanas"». Contestó «sí» y no
pasó nada. Él lo leyó como un problema de acentos; no lo era —los acentos ya se
pliegan— sino dos fallos encadenados:

1. El nombre del cliente se tragaba la frase entera, punto incluido. Buscaba, y
   podía llegar a crear, una ficha llamada «Reformas Martínez. Concierto
   Ventanas», que además sale como nombre fiscal en una factura emitida.
2. Con la revisión encendida, un cliente sin ficha era el final del camino: el
   «sí» lo contestaba la revisión con «no hay ninguna propuesta pendiente».

Las reglas que fijan las pruebas de aquí:

    Un nombre no lleva dentro una frase entera; el punto que separa frases corta.
    El punto de «S.L.» o de una inicial, no.
    Un cliente sin ficha se ofrece crear y se sigue; nunca se crea a escondidas.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noesis import config, db, nlu
from noesis.web import chat

# Frase dictada -> (cliente, concepto, base). El corpus de la voz real: cada
# frase de aquí la escribió alguien de verdad y salió mal.
CORPUS_DICTADO = {
    "hazme una factura a Reformas Martínez. Concepto ventanas 850 euros":
        ("Reformas Martínez", "ventanas", 850.0),
    # «Concierto» es como el dictado escribió «concepto». No se adivina: lo que
    # va detrás del punto es el concepto, se llame como se llame.
    "factura a Reformas Martínez. Concierto Ventanas 850 euros":
        ("Reformas Martínez", "Concierto Ventanas", 850.0),
    "hazme una factura a Reformas Martínez. Ventanas. 850 euros":
        ("Reformas Martínez", "Ventanas", 850.0),
    # Segunda captura del founder, sin punto: la palabra «concepto» es la marca.
    "haz una factura a reformas martinez concepto ventana por 750 euros mas iva":
        ("reformas martinez", "ventana", 750.0),
    "haz una factura a reformas martinez concepto ventana 750 euros":
        ("reformas martinez", "ventana", 750.0),
    # Tercera captura: «concepto» AL FINAL, detrás del importe. La regla que puso
    # el founder con sus palabras: donde diga «concepto», lo que va después es el
    # concepto; si no lo dice, «Servicio».
    "haz una factura a reformas martinez por 750 euros mas iva concepto ventana":
        ("reformas martinez", "ventana", 750.0),
    "haz una factura a reformas martinez 750 euros concepto ventana":
        ("reformas martinez", "ventana", 750.0),
    "factura a reformas martinez por 750 concepto cambio de ventana":
        ("reformas martinez", "cambio de ventana", 750.0),
    # El concepto no se parte por su propio «de»: era «grifo» a secas.
    "factura a Juan concepto cambio de grifo 120 euros":
        ("Juan", "cambio de grifo", 120.0),
    "factura a Juan concepto: reparar el termo 120 euros":
        ("Juan", "reparar el termo", 120.0),
    "factura a Marta en concepto de reforma del baño 300 euros":
        ("Marta", "reforma del baño", 300.0),
    # Lo que ya funcionaba tiene que seguir igual.
    "factura a Reformas Martínez por ventanas 850 euros":
        ("Reformas Martínez", "ventanas", 850.0),
    "factura a Juan por pintura 95 euros": ("Juan", "pintura", 95.0),
    "haz una factura a reformas martinez por 750 euros mas iva":
        ("reformas martinez", "Servicio", 750.0),
}


class PartirNombreTests(unittest.TestCase):
    def test_the_sentence_after_the_dot_is_not_part_of_the_name(self):
        self.assertEqual(nlu._partir_nombre("Reformas Martínez. Concepto ventanas"),
                         ("Reformas Martínez", "ventanas"))
        self.assertEqual(nlu._partir_nombre("Reformas Martínez. Concierto Ventanas"),
                         ("Reformas Martínez", "Concierto Ventanas"))

    def test_the_dot_of_a_company_or_an_initial_stays_inside_the_name(self):
        # Cortar aquí sería el error contrario: partir el nombre de la empresa.
        for nombre in ("Reformas Martínez S.L.", "Talleres J. Pino",
                       "Construcciones M. A. Ribó", "Suministros Hidra S.A."):
            with self.subTest(nombre=nombre):
                self.assertEqual(nlu._partir_nombre(nombre), (nombre, ""))

    def test_a_plain_name_is_left_alone(self):
        self.assertEqual(nlu._partir_nombre("Reformas Martínez"),
                         ("Reformas Martínez", ""))
        self.assertEqual(nlu._partir_nombre(""), ("", ""))


class DictadoTests(unittest.TestCase):
    def test_every_dictated_phrase_splits_client_from_concept(self):
        for frase, (cliente, concepto, base) in CORPUS_DICTADO.items():
            with self.subTest(frase=frase):
                herramienta, datos = nlu.parse(frase)
                self.assertEqual(herramienta, "crear_factura")
                self.assertEqual(datos["cliente"], cliente)
                self.assertEqual(datos["concepto"], concepto)
                self.assertEqual(datos["base"], base)

    def test_the_word_concepto_never_ends_up_inside_the_client(self):
        # Lo que se veía en WhatsApp: «No encuentro un cliente inequívoco llamado
        # "reformas martinez concepto ventana"».
        for frase in CORPUS_DICTADO:
            with self.subTest(frase=frase):
                self.assertNotIn("concepto", nlu.parse(frase)[1]["cliente"].lower())

    def test_the_concept_does_not_keep_the_connector_of_the_amount(self):
        # «ventana por 750 euros» dejaba el concepto en «ventana por».
        for frase, (_, concepto, _) in CORPUS_DICTADO.items():
            with self.subTest(frase=frase):
                self.assertFalse(concepto.lower().endswith((" por", " de", " a")))
                self.assertEqual(nlu.parse(frase)[1]["concepto"], concepto)

    def test_the_alta_does_not_swallow_the_sentence_either(self):
        # El mensaje de error sugería «crear cliente Reformas Martínez. Concierto
        # Ventanas»: seguir ese consejo dejaba una ficha con ese nombre.
        self.assertEqual(nlu.parse("crear cliente Reformas Martínez. Concierto Ventanas"),
                         ("crear_cliente", {"nombre": "Reformas Martínez"}))


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

    def tearDown(self):
        self.settings.stop()
        self.temp.cleanup()

    def wa(self, frase, phone="34600111222"):
        return chat.handle(self.bid, frase, channel="whatsapp",
                           actor_phone=phone)["reply"]


class AcentosTests(_Base):
    def test_an_accent_never_hides_a_client_that_exists(self):
        # Lo que el founder creía que fallaba. Ya funcionaba y tiene que seguir.
        db.add_client("Reformas Martinez", business_id=self.bid)
        for referencia in ("Reformas Martínez", "reformas martinez",
                           "REFORMAS MARTÍNEZ", "Reformas  Martínez"):
            with self.subTest(referencia=referencia):
                hallado = db.resolve_client_reference(referencia, self.bid)
                self.assertEqual(hallado and hallado["name"], "Reformas Martinez")

    def test_the_dictated_invoice_finds_the_client_that_exists(self):
        db.add_client("Reformas Martinez", business_id=self.bid)
        self.wa("hazme una factura a Reformas Martínez. Concepto ventanas 850 euros")
        factura = db.list_invoices(self.bid)[0]
        self.assertEqual(factura["client_name"], "Reformas Martinez")
        self.assertEqual(factura["concept"], "ventanas")


# La MISMA factura dicha de quince maneras. Todas significan lo mismo: cliente
# «Reformas Martinez», concepto «ventana», base 750. El founder lo dijo así:
# «yo lo quiero poder hacer de cualquier manera». El 23-09 fallaban nueve.
CORPUS_QUINCE_MANERAS = (
    "haz una factura a reformas martinez concepto ventana por 750 euros mas iva",
    "haz una factura a reformas martinez por ventana 750 euros",
    "haz una factura a reformas martinez de 750 euros por ventana",
    "hazme una factura para reformas martinez, ventana, 750 euros",
    "factura reformas martinez ventana 750",
    "factura a reformas martinez 750 euros ventana",
    "ponme una factura de 750 a reformas martinez por ventana",
    "necesito facturar 750 euros a reformas martinez por la ventana",
    "facturar a reformas martinez la ventana 750 euros",
    "una factura para reformas martinez de ventana por 750",
    "hazme la factura de reformas martinez: ventana, 750 euros",
    "factura a reformas martinez el cambio de ventana 750 euros",
    "quiero una factura a reformas martinez, concepto ventana, importe 750",
    "factura 750 euros reformas martinez ventana",
    "hazme una factura a reformas martinez por la instalacion de la ventana de 750 euros",
)

# Frases que hablan de facturas sin pedir ninguna. Que el cerebro sea tolerante
# no puede significar que se invente facturas: esto es el contrapeso.
CORPUS_NO_CREA_NADA = (
    "¿la factura de Juan está pagada?",
    "qué facturas tengo pendientes",
    "envía la factura a Marta",
    "cuánto llevo facturado",
    "necesito la factura de Juan",
    "quiero la factura del mes pasado",
    "pásame la factura nº 12",
    "crea una factura recurrente para Ana",
    "factura 12",
    "factura numero 12",
    "pásame factura 7 en PDF",
)


class CualquierManeraTests(_Base):
    """Decirlo de otra forma no puede costar un error.

    Quien sabe dónde acaba el nombre de un cliente no es una regla, es la
    cartera: por eso la prueba da de alta la ficha antes. Es el caso real —se
    factura a quien ya tienes— y el que fallaba.
    """

    def test_the_same_invoice_said_fifteen_ways(self):
        for numero, frase in enumerate(CORPUS_QUINCE_MANERAS):
            with self.subTest(frase=frase):
                if numero:
                    self.tearDown()
                    self.setUp()
                db.add_client("Reformas Martinez", business_id=self.bid)
                self.wa(frase)
                facturas = db.list_invoices(self.bid)
                self.assertEqual(len(facturas), 1, frase)
                factura = facturas[0]
                self.assertEqual(factura["client_name"], "Reformas Martinez")
                self.assertEqual(factura["base"], 750.0)
                self.assertIn("ventana", factura["concept"].lower())

    def test_talking_about_invoices_still_creates_none(self):
        db.add_client("Reformas Martinez", business_id=self.bid)
        for frase in CORPUS_NO_CREA_NADA:
            with self.subTest(frase=frase):
                self.wa(frase)
                self.assertEqual(db.list_invoices(self.bid), [], frase)

    def test_the_ledger_is_what_cuts_the_name(self):
        # Sin ficha no se corta por su cuenta: se pregunta. Cortar a ciegas
        # inventaría un cliente llamado «Reformas Martinez la».
        db.add_client("Reformas Martinez", business_id=self.bid)
        argumentos = {"cliente": "reformas martinez la ventana", "concepto": "Servicio"}
        chat._split_client_with_the_ledger(self.bid, argumentos)
        self.assertEqual(argumentos["cliente"], "Reformas Martinez")
        self.assertEqual(argumentos["concepto"], "la ventana")

    def test_with_two_similar_records_it_does_not_cut_by_guessing(self):
        db.add_client("Reformas Martinez Hermanos", business_id=self.bid)
        db.add_client("Reformas Martinez e Hijos", business_id=self.bid)
        argumentos = {"cliente": "reformas martinez la ventana", "concepto": "Servicio"}
        chat._split_client_with_the_ledger(self.bid, argumentos)
        self.assertEqual(argumentos["cliente"], "reformas martinez la ventana")


class ConceptoTests(unittest.TestCase):
    """La regla, con las palabras del founder: donde diga «concepto», lo de
    después es el concepto; si no dice nada, «Servicio»."""

    def test_the_word_concepto_wins_wherever_it_is_said(self):
        for frase in (
            "haz una factura a reformas martinez concepto ventana por 750 euros",
            "haz una factura a reformas martinez por 750 euros concepto ventana",
            "haz una factura a reformas martinez 750 euros concepto ventana",
            "factura a reformas martinez, concepto ventana, 750 euros",
        ):
            with self.subTest(frase=frase):
                self.assertEqual(nlu.parse(frase)[1]["concepto"], "ventana")

    def test_without_the_word_it_stays_as_servicio(self):
        datos = nlu.parse("haz una factura a reformas martinez por 750 euros")[1]
        self.assertEqual(datos["concepto"], "Servicio")

    def test_removing_the_tax_words_does_not_glue_the_others(self):
        # «750 euros mas iva concepto ventana» dejaba «eurosconcepto ventana».
        datos = nlu.parse(
            "haz una factura a reformas martinez por 750 euros mas iva concepto ventana")[1]
        self.assertEqual(datos["concepto"], "ventana")
        self.assertEqual(datos["base"], 750.0)


class ConfirmacionTests(unittest.TestCase):
    """«Si, genera el pdf» es un sí. Un cambio de importe, no."""

    def test_a_yes_with_a_harmless_tail_is_still_a_yes(self):
        for frase in ("si", "sí", "si, genera el pdf", "sí, mándame el pdf",
                      "si genera el pdf", "vale", "confirmo", "de acuerdo",
                      "sí gracias", "si, por favor", "si, adjuntame el documento"):
            with self.subTest(frase=frase):
                self.assertTrue(nlu.es_confirmacion(frase))

    def test_anything_that_changes_the_operation_is_not_a_yes(self):
        for frase in ("no", "no, gracias", "si, pero cambia el importe",
                      "sí, mejor 500 euros", "si, pero el cliente es otro",
                      "si el cliente es Marta", "corregir: factura a Juan 100",
                      "hazme una factura"):
            with self.subTest(frase=frase):
                self.assertFalse(nlu.es_confirmacion(frase))


class ClienteSinFichaTests(_Base):
    REVISION = True

    def test_the_conversation_from_the_screenshot_now_finishes(self):
        pregunta = self.wa(
            "hazme una factura a Reformas Martínez. Concepto ventanas 850 euros")
        # El nombre de la pregunta ya es el bueno, no la frase entera.
        self.assertIn("Reformas Martínez", pregunta)
        self.assertNotIn("Concepto", pregunta)
        self.assertEqual(db.list_clients(self.bid), [])
        # Y el «sí» hace algo, que es lo que no pasaba.
        respuesta = self.wa("sí")
        self.assertIn("creada", respuesta)
        self.assertEqual([c["name"] for c in db.list_clients(self.bid)],
                         ["Reformas Martínez"])
        factura = db.list_invoices(self.bid)[0]
        self.assertEqual(factura["client_name"], "Reformas Martínez")
        self.assertEqual(factura["concept"], "ventanas")
        self.assertEqual(factura["status"], "borrador")

    def test_a_misspelled_name_is_corrected_in_the_same_breath(self):
        self.wa("hazme una factura a Refromas Lopez 200 euros")
        self.wa("Reformas López")
        self.assertEqual([c["name"] for c in db.list_clients(self.bid)],
                         ["Reformas López"])
        self.assertEqual(db.list_invoices(self.bid)[0]["client_name"],
                         "Reformas López")

    def test_no_record_is_born_without_a_yes(self):
        self.wa("hazme una factura a Reformas Martínez 850 euros")
        self.assertEqual(db.list_clients(self.bid), [])
        self.assertEqual(db.list_invoices(self.bid), [])

    def test_another_person_does_not_confirm_my_order(self):
        self.wa("hazme una factura a Reformas Martínez 850 euros", phone="34600111222")
        self.wa("sí", phone="34699888777")
        self.assertEqual(db.list_clients(self.bid), [])

    def test_a_client_that_already_has_a_record_is_not_asked_about(self):
        db.add_client("Reformas Martinez", business_id=self.bid)
        respuesta = self.wa("hazme una factura a Reformas Martínez 850 euros")
        self.assertNotIn("No tengo ficha", respuesta)

    def test_several_matching_records_still_ask_which_one(self):
        # Ante dos fichas que encajan, crear una tercera sería lo contrario de lo
        # que hace falta: se sigue pidiendo el nombre completo.
        db.add_client("Reformas Martinez Hermanos", business_id=self.bid)
        db.add_client("Reformas Martinez e Hijos", business_id=self.bid)
        respuesta = self.wa("hazme una factura a Reformas Martinez 850 euros")
        self.assertNotIn("No tengo ficha", respuesta)
        self.assertEqual(len(db.list_clients(self.bid)), 2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
