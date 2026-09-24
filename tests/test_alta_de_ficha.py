"""Altas de clientes y proveedores: un fallo no puede cerrar la conversación.

Dar de alta una ficha es lo que más veces sale mal, porque se dicta hablando: sin
el nombre, con el teléfono pegado detrás, con el nombre escrito de otra manera o
con algo que no es un nombre. Antes, cualquiera de esas cosas terminaba la
conversación —listando fichas, soltando el parte del día o con un error crudo— y
había que reescribir la orden entera. La regla que fijan todas las pruebas de aquí:

    Un alta que no se puede completar pregunta lo que falta y sigue viva.
    Lo que se guarda es una ficha de verdad, nunca una frase entera ni un número.

Cuando una frase real falle en producción, se añade aquí con lo que se esperaba.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noesis import config, db, nlu
from noesis.web import chat

# Frase real -> ficha que tiene que quedar guardada.
CORPUS_ALTA = {
    "crea el cliente Jordi Mas": ("cliente", "Jordi Mas", None),
    "crear cliente Ana Ruiz": ("cliente", "Ana Ruiz", None),
    "da de alta a Talleres Pino como proveedor": ("proveedor", "Talleres Pino", None),
    "nuevo proveedor Materiales Sol": ("proveedor", "Materiales Sol", None),
    # El teléfono dictado detrás del nombre va a su columna, no al nombre.
    "crea el cliente Marta Vila, telefono 611 22 33 44":
        ("cliente", "Marta Vila", "611223344"),
    "crea el cliente Pere Soler con telefono 600123456":
        ("cliente", "Pere Soler", "600123456"),
}

# Frases que piden un alta pero no traen un nombre utilizable: se pregunta y no se
# crea nada. Crear aquí una ficha es peor que preguntar.
CORPUS_PREGUNTA = (
    "crea el cliente",
    "crear cliente ",
    "nuevo proveedor",
    "añade un cliente",
    "crea el cliente 600123456",
)


class _Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = patch.multiple(
            config, DATABASE_URL="", DB_PATH=Path(self.temp.name) / "t.db",
            BACKUP_DIR=Path(self.temp.name) / "b",
            DOCS_PATH=Path(self.temp.name) / "d", ANTHROPIC_API_KEY="")
        self.settings.start()
        db.init_db()
        self.bid = db.create_business("Reformas Prueba", "a@example.com")["id"]

    def tearDown(self):
        self.settings.stop()
        self.temp.cleanup()

    def di(self, frase, actor="u1"):
        return chat.handle(self.bid, frase, channel="web", actor_id=actor)["reply"]


class CorpusTests(_Base):
    def test_every_phrase_creates_the_record_it_names(self):
        # Cada frase parte de una base limpia: la primera la deja `setUp` y la
        # última la recoge `tearDown`. Anidar entornos deja `config` parcheado
        # apuntando a un directorio borrado y tumba las pruebas siguientes.
        for numero, (frase, esperado) in enumerate(CORPUS_ALTA.items()):
            tipo, nombre, telefono = esperado
            with self.subTest(frase=frase):
                if numero:
                    self.tearDown()
                    self.setUp()
                respuesta = self.di(frase)
                self.assertIn("guardado", respuesta)
                fichas = (db.list_clients(self.bid) if tipo == "cliente"
                          else db.list_suppliers(self.bid))
                self.assertEqual([f["name"] for f in fichas], [nombre], respuesta)
                if tipo == "cliente":
                    self.assertEqual(fichas[0]["phone"], telefono)

    def test_an_alta_without_a_usable_name_asks_instead_of_guessing(self):
        for frase in CORPUS_PREGUNTA:
            with self.subTest(frase=frase):
                respuesta = self.di(frase)
                self.assertIn("¿Cómo se llama?", respuesta)
                self.assertEqual(db.list_clients(self.bid), [])
                self.assertEqual(db.list_suppliers(self.bid), [])


class CompletarTests(_Base):
    def test_the_name_alone_finishes_the_alta(self):
        self.di("crea el cliente")
        self.assertIn("guardado", self.di("Jordi Mas"))
        self.assertEqual([c["name"] for c in db.list_clients(self.bid)], ["Jordi Mas"])

    def test_the_supplier_is_remembered_not_the_client(self):
        self.di("nuevo proveedor")
        self.di("Materiales Sol")
        self.assertEqual([s["name"] for s in db.list_suppliers(self.bid)],
                         ["Materiales Sol"])
        self.assertEqual(db.list_clients(self.bid), [])

    def test_a_question_during_the_alta_is_not_taken_as_a_name(self):
        # El fallo que tuvo este diseño al escribirlo: «qué facturas tengo
        # pendientes» creaba un cliente con ese nombre.
        self.di("crea el cliente")
        self.di("qué facturas tengo pendientes")
        self.assertEqual(db.list_clients(self.bid), [])
        # Y el alta sigue viva: el nombre de verdad la termina.
        self.di("Pere Soler")
        self.assertEqual([c["name"] for c in db.list_clients(self.bid)], ["Pere Soler"])

    def test_another_person_does_not_finish_my_alta(self):
        self.di("crea el cliente", actor="u1")
        self.di("Anna Puig", actor="u2")
        self.assertEqual(db.list_clients(self.bid), [])

    def test_a_failed_alta_stays_open_for_the_next_name(self):
        respuesta = self.di("nuevo proveedor " + "B" * 400)
        self.assertIn("demasiado largo", respuesta)
        self.assertEqual(db.list_suppliers(self.bid), [])
        self.assertIn("guardado", self.di("Materiales Sol"))
        self.assertEqual([s["name"] for s in db.list_suppliers(self.bid)],
                         ["Materiales Sol"])


class FichasSanasTests(_Base):
    def test_a_name_too_long_is_refused_the_same_for_both(self):
        # Clientes no tenía límite: entraban nombres de 400 caracteres que luego
        # salían así en listas, PDF y facturas.
        with self.assertRaisesRegex(ValueError, "demasiado largo"):
            db.add_client("A" * 201, business_id=self.bid)
        with self.assertRaisesRegex(ValueError, "demasiado largo"):
            db.add_supplier("B" * 201, business_id=self.bid)

    def test_the_two_reasons_are_told_apart(self):
        # Llevan a cosas distintas: uno se arregla diciendo el nombre y el otro
        # acortándolo. Un mismo mensaje para los dos no dice qué hacer.
        with self.assertRaisesRegex(ValueError, "obligatorio"):
            db.add_client("   ", business_id=self.bid)
        with self.assertRaisesRegex(ValueError, "obligatorio"):
            db.add_supplier("", business_id=self.bid)

    def test_a_typo_reuses_the_client_instead_of_duplicating_it(self):
        """«Por un tilde o una letra me pone un cliente nuevo», dijo el founder.

        Al dictar y al teclear eso pasa constantemente, y cada vez partía en dos
        el historial del mismo cliente.
        """
        db.add_client("Reformas Martinez", business_id=self.bid)
        for dicho in ("Reformas Martines", "Reformas Martínez", "reformas martinz",
                      "Reformas Martinezz", "REFORMAS MARTINES"):
            with self.subTest(dicho=dicho):
                hallado = db.resolve_client_reference(dicho, self.bid)
                self.assertEqual(hallado and hallado["name"], "Reformas Martinez")

    def test_a_name_the_dictation_cut_short_finds_the_client(self):
        """Caso real del founder, 24-09: «si el audio coge reforma me hace un
        cliente nuevo».

        Al dictar, la transcripción se come el apellido o una letra final:
        «Reformas Martinez» llega como «reforma». Comparar solo el nombre entero
        lo descartaba por diferencia de longitud, así que nacía una ficha nueva y
        el historial del cliente quedaba partido en dos.
        """
        db.add_client("Reformas Martinez", business_id=self.bid)
        for dicho in ("reforma", "reformas", "Reformas", "martinez",
                      "Reformas Martines"):
            with self.subTest(dicho=dicho):
                hallado = db.resolve_client_reference(dicho, self.bid)
                self.assertEqual(hallado and hallado["name"], "Reformas Martinez")

    def test_a_dictated_invoice_with_a_cut_name_creates_no_second_record(self):
        db.add_client("Reformas Martinez", business_id=self.bid)
        self.di("hazme una factura a reforma 300 euros")
        self.assertEqual([c["name"] for c in db.list_clients(self.bid)],
                         ["Reformas Martinez"])

    def test_a_different_person_is_still_a_different_person(self):
        # El contrapeso: tolerar erratas no puede acabar facturando a otro.
        for nombre in ("Reformas Martinez", "Ana"):
            db.add_client(nombre, business_id=self.bid)
        for distinto in ("Construcciones Vila", "Pedro Sanchez", "Ema",
                         "Reformas Garcia"):
            with self.subTest(distinto=distinto):
                self.assertIsNone(db.resolve_client_reference(distinto, self.bid))

    def test_a_short_name_is_not_corrected_by_one_letter(self):
        # En nombres cortos una letra sí cambia de persona: «Ana» y «Ann».
        db.add_client("Ana", business_id=self.bid)
        self.assertIsNone(db.resolve_client_reference("Ann", self.bid))

    def test_with_two_similar_records_it_asks_instead_of_choosing(self):
        db.add_client("Reformas Martinez", business_id=self.bid)
        db.add_client("Reformas Martinex", business_id=self.bid)
        with self.assertRaisesRegex(ValueError, "se parece a varios"):
            db.resolve_client_reference("Reformas Martines", self.bid)

    def test_the_same_supplier_written_differently_is_not_duplicated(self):
        self.di("nuevo proveedor Materiales Sol")
        self.di("nuevo proveedor materiales sol")
        self.di("nuevo proveedor MATERIALES SOL")
        self.assertEqual([s["name"] for s in db.list_suppliers(self.bid)],
                         ["Materiales Sol"])

    def test_find_supplier_matches_ignoring_case_and_accents(self):
        db.add_supplier("Construccions Ribó", business_id=self.bid)
        self.assertIsNotNone(db.find_supplier(self.bid, name="construccions ribo"))

    def test_add_supplier_refuses_a_duplicate_written_differently(self):
        db.add_supplier("Materiales Sol", business_id=self.bid)
        with self.assertRaisesRegex(ValueError, "Ya existe"):
            db.add_supplier("materiales sol", business_id=self.bid)

    def test_a_known_client_keeps_the_phone_it_already_had(self):
        db.add_client("Jordi Mas", phone="600111222", business_id=self.bid)
        self.di("crea el cliente Jordi Mas, telefono 611 22 33 44")
        self.assertEqual(db.list_clients(self.bid)[0]["phone"], "600111222")

    def test_a_known_client_without_phone_gets_the_one_just_said(self):
        db.add_client("Jordi Mas", business_id=self.bid)
        self.di("crea el cliente Jordi Mas, telefono 611 22 33 44")
        self.assertEqual(db.list_clients(self.bid)[0]["phone"], "611223344")


class WebFormTests(_Base):
    """La web tiene que contestar el motivo, no romperse."""

    def _http(self):
        from starlette.testclient import TestClient
        from noesis.web.server import app
        return TestClient(app)

    def test_a_bad_client_name_is_a_400_with_its_reason_not_a_500(self):
        from noesis.web.routers import clients as ruta
        respuesta = _llamar(ruta.api_create_client, self.bid,
                            {"name": "A" * 400})
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("demasiado largo", respuesta.body.decode())
        self.assertEqual(db.list_clients(self.bid), [])

    def test_the_invoice_form_says_it_too(self):
        from noesis.web.routers import invoicing as ruta
        respuesta = _llamar(ruta.api_create_invoice, self.bid,
                            {"client_name": "A" * 400, "concept": "Obra",
                             "base": 100})
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("demasiado largo", respuesta.body.decode())


def _llamar(vista, business_id, cuerpo):
    """Ejecuta una vista asíncrona con un cuerpo JSON, sin levantar el servidor."""
    import asyncio
    import json as _json

    class _Peticion:
        async def json(self):
            return cuerpo

        async def body(self):
            return _json.dumps(cuerpo).encode()

        headers = {"content-type": "application/json"}

    return asyncio.run(vista(business_id, _Peticion()))


class ParserTests(unittest.TestCase):
    def test_the_name_is_separated_from_the_contact_data(self):
        self.assertEqual(nlu.parse_party_name("Jordi Mas, teléfono 600 12 34 56"),
                         ("Jordi Mas", "600123456"))
        self.assertEqual(nlu.parse_party_name("Ana con teléfono 611222333"),
                         ("Ana", "611222333"))
        self.assertEqual(nlu.parse_party_name("Talleres Pino"),
                         ("Talleres Pino", None))

    def test_the_company_form_is_part_of_the_name(self):
        # «S.L.» va en el nombre fiscal, que es el que sale en la factura.
        # Cortarlo por su coma daba de alta a otra empresa.
        self.assertEqual(nlu.parse_party_name("Reformas Martínez, S.L."),
                         ("Reformas Martínez, S.L.", None))
        self.assertEqual(nlu.parse_party_name("Reformas Martínez, S.L., telefono 600123456"),
                         ("Reformas Martínez, S.L.", "600123456"))

    def test_something_that_cannot_be_a_name_is_refused(self):
        self.assertEqual(nlu.parse_party_name("600123456"), (None, None))
        self.assertEqual(nlu.parse_party_name("   "), (None, None))
        self.assertEqual(nlu.parse_party_name("---"), (None, None))

    def test_an_alta_without_a_name_is_its_own_intent(self):
        self.assertEqual(nlu.parse("crea el cliente"),
                         (nlu.NEED_PARTY_NAME, {"tipo": "cliente"}))
        self.assertEqual(nlu.parse("nuevo proveedor"),
                         (nlu.NEED_PARTY_NAME, {"tipo": "proveedor"}))
        # Y no se confunde con listar, que es lo que hacía antes.
        self.assertEqual(nlu.parse("clientes"), ("listar_clientes", {}))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
