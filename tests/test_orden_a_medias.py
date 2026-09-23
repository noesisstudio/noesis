"""Órdenes a medias: se guarda lo entendido y se declara lo que falta.

Este archivo es el **corpus de frases reales que fallaron**. Cada frase de aquí la
escribió alguien de verdad y recibió un «no he creado nada» o un «no se
identificó el cliente» cuando el dato estaba dicho o se iba a dar después. La
regla que fijan todas juntas:

    Una orden reconocida nunca tira lo que se entendió porque falte otra parte.

Cuando una frase nueva falle en producción, se añade aquí con lo que se esperaba.
Así el mismo error no puede volver sin que salte una prueba. Es lo que no hubo la
primera vez: la agenda tuvo este mismo fallo el 16-09 y se arregló solo para la
agenda.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noesis import config, db, nlu
from noesis.web import chat

# Frase real -> lo que tiene que quedar guardado en el borrador.
# `cliente` es el nombre de ficha enlazada; `apuntado`, un nombre dicho sin ficha.
CORPUS_FACTURA_A_MEDIAS = {
    "hazme una factura para este cliente": {"cliente": "Jordi Mas"},
    "añade una factura, ya luego te paso los datos": {},
    "hazme una factura, invéntatela y luego pongo los datos": {},
    "factura para Jordi Mas, los datos te los paso luego": {"cliente": "Jordi Mas"},
    "hazme una factura a Jordi Mas por reforma": {"cliente": "Jordi Mas",
                                                  "concepto": "reforma"},
    "hazme una factura por reforma del baño": {"concepto": "reforma del baño"},
    "crea una factura para él": {"cliente": "Jordi Mas"},
    "hazme una factura": {},
    "factura a Pere Soler": {"apuntado": "Pere Soler"},
}

# Frases que mencionan una factura pero no piden crearla. Crear aquí un borrador
# sería peor que el fallo original.
CORPUS_NO_CREA = (
    "¿la factura de Juan está pagada?",
    "qué facturas tengo pendientes",
    "envía la factura a Marta",
    "cuánto llevo facturado",
    # Con determinante definido se habla de una factura que ya existe: «necesito»
    # y «quiero» no piden crearla. Crear un borrador aquí sería inventársela.
    "necesito la factura de Juan",
    "quiero la factura del mes pasado",
    "pásame la factura nº 12",
    # Una recurrente se configura en Facturas; un borrador suelto haría creer que
    # ya se repite sola.
    "crea una factura recurrente para Ana",
)

# Órdenes completas: siguen su camino de siempre, sin pasar por el borrador a medias.
CORPUS_COMPLETAS = (
    "factura a Juan por pintura 95 euros",
    "hazme una factura a Juan de 100 euros",
    "prepárame una factura a Marta de 250 euros",
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
        db.update_fiscal(self.bid, nif="12345678Z", address="Calle Prueba 1")

    def tearDown(self):
        self.settings.stop()
        self.temp.cleanup()

    def di(self, frase, actor="u1"):
        return chat.handle(self.bid, frase, channel="web", actor_id=actor)


class CorpusTests(_Base):
    def test_every_real_phrase_creates_a_draft_and_keeps_what_was_said(self):
        # Cada frase parte de una base limpia. La primera la deja `setUp` y la
        # última la recoge `tearDown`: nunca hay dos entornos montados a la vez.
        # Anidarlos dejaba `config` parcheado apuntando a un directorio ya borrado
        # y reventaba las pruebas que corrieran después en el mismo proceso.
        for numero, (frase, esperado) in enumerate(CORPUS_FACTURA_A_MEDIAS.items()):
            with self.subTest(frase=frase):
                if numero:
                    self.tearDown()
                    self.setUp()
                self.di("crea el cliente Jordi Mas")
                antes = len(db.list_invoices(self.bid))
                respuesta = self.di(frase)["reply"]
                self.assertNotIn("No he creado nada", respuesta)
                self.assertNotIn("no se identific", respuesta.lower())
                facturas = db.list_invoices(self.bid)
                self.assertEqual(len(facturas), antes + 1, respuesta)
                factura = db.get_invoice(max(f["id"] for f in facturas), self.bid)
                cliente = (db.get_client(factura["client_id"], self.bid)
                           if factura.get("client_id") else None)
                if "cliente" in esperado:
                    self.assertEqual(cliente and cliente["name"], esperado["cliente"])
                if "apuntado" in esperado:
                    self.assertIsNone(cliente)
                    self.assertEqual(factura["recipient_name"], esperado["apuntado"])
                if "concepto" in esperado:
                    self.assertEqual(factura["concept"], esperado["concepto"])
                self.assertEqual(factura["status"], "borrador")

    def test_questions_about_invoices_never_create_one(self):
        for frase in CORPUS_NO_CREA:
            with self.subTest(frase=frase):
                antes = len(db.list_invoices(self.bid))
                self.di(frase)
                self.assertEqual(len(db.list_invoices(self.bid)), antes)

    def test_complete_orders_keep_their_usual_route(self):
        for frase in CORPUS_COMPLETAS:
            with self.subTest(frase=frase):
                self.assertEqual(nlu.parse(frase)[0], "crear_factura")


class CompletarTests(_Base):
    def test_this_client_is_the_one_just_mentioned(self):
        self.di("crea el cliente Ana Ruiz")
        self.di("crea el cliente Jordi Mas")
        self.di("hazme una factura para este cliente")
        factura = db.latest_partial_invoice(self.bid)
        self.assertEqual(db.get_client(factura["client_id"], self.bid)["name"],
                         "Jordi Mas")

    def test_a_longer_name_wins_over_a_shorter_one_in_the_same_message(self):
        db.get_or_create_client("Jordi", business_id=self.bid)
        self.di("crea el cliente Jordi Mas")
        self.di("hazme una factura para este cliente")
        factura = db.latest_partial_invoice(self.bid)
        self.assertEqual(db.get_client(factura["client_id"], self.bid)["name"],
                         "Jordi Mas")

    def test_loose_answers_fill_the_draft_until_it_is_a_real_invoice(self):
        self.di("crea el cliente Jordi Mas")
        self.di("hazme una factura para este cliente")
        self.di("el concepto es reforma del baño")
        respuesta = self.di("300 euros")["reply"]
        self.assertIn("completo", respuesta)
        factura = db.get_invoice(db.list_invoices(self.bid)[0]["id"], self.bid)
        self.assertEqual(db.invoice_pending_fields(factura), [])
        self.assertEqual(factura["concept"], "reforma del baño")
        self.assertAlmostEqual(factura["total"], 363.0)
        # Reconstruida con `update_invoice_draft`: tiene su línea como cualquier otra.
        with db.get_conn() as conn:
            lineas = conn.execute("SELECT COUNT(*) AS n FROM invoice_lines "
                                  "WHERE invoice_id=?", (factura["id"],)).fetchone()["n"]
        self.assertEqual(lineas, 1)

    def test_a_name_without_record_links_itself_when_the_client_is_created(self):
        self.di("factura para Pere Soler, los datos te los paso luego")
        respuesta = self.di("crea el cliente Pere Soler")["reply"]
        self.assertIn("enlazado al borrador", respuesta)
        factura = db.list_invoices(self.bid)[0]
        self.assertEqual(db.get_client(factura["client_id"], self.bid)["name"],
                         "Pere Soler")

    def test_no_implicit_client_record_is_created(self):
        # Un alta implícita duplica clientes por errores de voz: el nombre se
        # guarda en el borrador, pero la ficha solo nace con «crea el cliente».
        self.di("factura para Pere Soler, los datos te los paso luego")
        self.assertEqual(db.list_clients(self.bid), [])

    def test_with_several_clients_and_nobody_named_it_does_not_guess(self):
        # «este cliente» sin que se haya nombrado a nadie no puede resolverse. Antes
        # se cogía el cliente más reciente: una factura a nombre de otra persona.
        db.get_or_create_client("Ana Ruiz", business_id=self.bid)
        db.get_or_create_client("Jordi Mas", business_id=self.bid)
        self.di("hazme una factura para este cliente")
        factura = db.latest_partial_invoice(self.bid)
        self.assertIsNone(factura["client_id"])
        self.assertIn("cliente", db.invoice_pending_fields(factura))

    def test_with_a_single_client_that_one_is_the_one(self):
        db.get_or_create_client("Ana Ruiz", business_id=self.bid)
        self.di("hazme una factura para este cliente")
        factura = db.latest_partial_invoice(self.bid)
        self.assertEqual(db.get_client(factura["client_id"], self.bid)["name"],
                         "Ana Ruiz")

    def test_an_unrelated_sentence_is_not_taken_as_data(self):
        self.di("hazme una factura para este cliente")
        antes = db.latest_partial_invoice(self.bid)
        self.di("el cliente es muy pesado con los plazos")
        despues = db.get_invoice(antes["id"], self.bid)
        self.assertEqual(db.invoice_pending_fields(despues),
                         db.invoice_pending_fields(antes))

    def test_another_person_does_not_complete_my_draft(self):
        self.di("hazme una factura", actor="u1")
        self.di("300 euros", actor="u2")
        self.assertIn("importe", db.invoice_pending_fields(
            db.latest_partial_invoice(self.bid)))


class EmitirTests(_Base):
    def test_a_draft_with_gaps_cannot_be_issued_and_says_what_is_missing(self):
        factura = db.create_partial_invoice(self.bid, concept="Reforma")
        with self.assertRaisesRegex(ValueError, "a medias.*cliente.*importe"):
            db.issue_invoice(factura["id"], self.bid)
        self.assertEqual(db.get_invoice(factura["id"], self.bid)["status"], "borrador")

    def test_completing_from_the_web_form_leaves_it_issuable(self):
        # El fallo que tuvo este diseño al escribirlo: el formulario de la web
        # guarda con `update_invoice_draft`, que no quitaba la marca de «a medias».
        # La factura quedaba completa y bloqueada para siempre.
        factura = db.create_partial_invoice(self.bid, client_name="Ana")
        cliente = db.add_client("Ana", nif="12345678Z", address="Calle Ana 1",
                                business_id=self.bid)
        db.update_invoice_draft(
            factura["id"], self.bid, client_id=cliente["id"],
            lines=[{"description": "Termo", "quantity": 1, "unit_price": 120,
                    "discount_rate": 0, "vat_rate": 21}])
        self.assertEqual(db.invoice_pending_fields(
            db.get_invoice(factura["id"], self.bid)), [])
        emitida = db.issue_invoice(factura["id"], self.bid)
        self.assertNotEqual(emitida["status"], "borrador")

    def test_the_invoice_list_carries_what_the_page_needs(self):
        db.create_partial_invoice(self.bid, client_name="Pere Soler")
        fila = db.list_invoices(self.bid)[0]
        self.assertIn("pending_fields", fila)
        self.assertEqual(fila["recipient_name"], "Pere Soler")
        # `client_name` ya viene del nombre apuntado (COALESCE), así que lo único
        # que distingue «sin ficha» en la página es que no haya `client_id`.
        self.assertEqual(fila["client_name"], "Pere Soler")
        self.assertIsNone(fila["client_id"])

    def test_editing_from_the_web_replaces_the_name_written_by_hand(self):
        # El nombre apuntado manda sobre el del cliente en el listado. Si al asignar
        # ficha se quedara, una factura de Ana seguiría saliendo a nombre de Pere.
        factura = db.create_partial_invoice(self.bid, client_name="Pere Soler")
        ana = db.add_client("Ana", nif="12345678Z", address="Calle Ana 1",
                            business_id=self.bid)
        db.update_invoice_draft(
            factura["id"], self.bid, client_id=ana["id"],
            lines=[{"description": "Termo", "quantity": 1, "unit_price": 120,
                    "discount_rate": 0, "vat_rate": 21}])
        fila = db.list_invoices(self.bid)[0]
        self.assertIsNone(fila["recipient_name"])
        self.assertEqual(fila["client_name"], "Ana")

    def test_three_fields_at_once_is_a_normal_invoice(self):
        cliente = db.get_or_create_client("Ana", business_id=self.bid)
        factura = db.create_partial_invoice(self.bid, client_id=cliente["id"],
                                            concept="Termo", base=120)
        self.assertEqual(db.invoice_pending_fields(factura), [])

    def test_an_issued_invoice_cannot_be_completed(self):
        # Emitir exige NIF y domicilio del cliente: se dan para poder emitirla.
        cliente = db.add_client("Ana", nif="12345678Z", address="Calle Ana 1",
                                business_id=self.bid)
        factura = db.add_invoice(cliente["id"], "Termo", 120, business_id=self.bid)
        db.issue_invoice(factura["id"], self.bid)
        with self.assertRaisesRegex(ValueError, "emitida"):
            db.complete_invoice_fields(factura["id"], self.bid, base=999)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
