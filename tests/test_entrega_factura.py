"""Entregar una factura al cliente por correo, dicho hablando.

Petición del founder (24-09-2026): «quiero poder decir envía la factura por
correo». La maquinaria estaba entera —`prepare_invoice_delivery` genera el PDF,
elige canal, encola de forma durable y `process_email_outbox` adjunta el PDF
regenerándolo desde el número de factura— pero **no había forma de pedirlo
hablando**: no era una herramienta del chat, solo se llamaba desde dentro.

Y había una segunda causa, del tipo que más se ha repetido este mes: el redactor
de mensajes se quedaba cualquier frase que llevara la palabra «correo», así que
«envía la factura 3 por correo» contestaba «dime a qué cliente escribimos», con
la factura delante y numerada. Es el punto #3 de la lista del founder: una regla
local interceptando por una coincidencia parcial.

Las reglas que fijan las pruebas de aquí:

    Entregar no es emitir. Una factura en borrador no se entrega: se dice que hay
    que emitirla primero, con las palabras exactas para hacerlo.
    Entregar sale hacia otra persona, así que se propone y se confirma.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noesis import config, db, nlu
from noesis.web import chat, whatsapp


class _Base(unittest.TestCase):
    CON_CORREO = True
    EMITIDA = True

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        # Un servidor CON proveedor de correo y WhatsApp, que es lo que
        # representa el camino bueno. Sin ellos no se encola nada a propósito.
        self.settings = patch.multiple(
            config, DATABASE_URL="", DB_PATH=Path(self.temp.name) / "t.db",
            BACKUP_DIR=Path(self.temp.name) / "b",
            DOCS_PATH=Path(self.temp.name) / "d", ANTHROPIC_API_KEY="",
            ASSISTANT_REVIEW_ENABLED=True,
            BREVO_API_KEY="xkeysib-pruebas")  # pragma: allowlist secret - credencial ficticia del fixture
        self.settings.start()
        self.canal_wa = patch.multiple(whatsapp, _TOKEN="token", _PHONE_ID="123")
        self.canal_wa.start()
        db.init_db()
        self.bid = db.create_business("Reformas Prueba", "a@example.com")["id"]
        db.update_fiscal(self.bid, nif="12345678Z", address="Calle Prueba 1")
        self.cliente = db.add_client(
            "Juan", nif="87654321X", address="Calle Juan 1",
            email="juan@ejemplo.com" if self.CON_CORREO else None,
            phone="600222333", business_id=self.bid)
        factura = db.add_invoice(self.cliente["id"], "Obra", 100,
                                 business_id=self.bid)
        self.factura = (db.issue_invoice(factura["id"], self.bid)
                        if self.EMITIDA else factura)

    def tearDown(self):
        self.canal_wa.stop()
        self.settings.stop()
        self.temp.cleanup()

    def wa(self, frase):
        return chat.handle(self.bid, frase, channel="whatsapp",
                           actor_phone="34600111222")["reply"]

    def en_cola(self):
        with db.get_conn() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT to_email, entity_type, entity_id FROM email_outbox"
            ).fetchall()]


class CerebroTests(unittest.TestCase):
    def test_saying_the_channel_makes_it_a_delivery(self):
        for frase, canal in (
            ("envía la factura 3 por correo", "email"),
            ("manda la factura 3 al cliente por email", "email"),
            ("envíale la factura 3 por correo electrónico", "email"),
            ("envía la factura 3 por whatsapp", "whatsapp"),
        ):
            with self.subTest(frase=frase):
                self.assertEqual(nlu.parse(frase),
                                 ("entregar_factura",
                                  {"factura_id": 3, "canal": canal}))

    def test_without_a_channel_it_still_asks_what_you_mean(self):
        # Emitir y entregar no son lo mismo y sin canal no se adivina.
        self.assertEqual(nlu.parse("envía la factura 3")[0], nlu.NEED_REVIEW)

    def test_issuing_is_never_confused_with_delivering(self):
        for frase in ("emitir factura 3", "emitir y enviar factura 3"):
            with self.subTest(frase=frase):
                self.assertEqual(nlu.parse(frase)[0], "enviar_factura")


class EntregaTests(_Base):
    def test_the_invoice_reaches_the_email_queue_with_its_pdf(self):
        propuesta = self.wa("envía la factura 1 por correo")
        self.assertIn("juan@ejemplo.com", propuesta)
        self.assertIn("al CLIENTE", propuesta)
        self.assertEqual(self.en_cola(), [])  # aún sin confirmar
        self.assertIn("en camino", self.wa("sí"))
        # `entity_type=invoice` es lo que hace que al enviarse se adjunte el PDF,
        # regenerado desde el número de factura. Sin eso el correo prometería un
        # adjunto que no lleva.
        self.assertEqual(self.en_cola(), [{"to_email": "juan@ejemplo.com",
                                           "entity_type": "invoice",
                                           "entity_id": 1}])

    def test_nothing_leaves_without_a_yes(self):
        self.wa("envía la factura 1 por correo")
        self.assertEqual(self.en_cola(), [])

    def test_it_is_written_down_in_the_history_of_the_invoice(self):
        self.wa("envía la factura 1 por correo")
        self.wa("sí")
        eventos = [e["event_type"] for e in db.list_invoice_events(self.bid)]
        self.assertIn("entrega_preparada", eventos)


class BorradorTests(_Base):
    EMITIDA = False

    def test_a_draft_is_not_delivered_and_says_how_to_do_it(self):
        respuesta = self.wa("envía la factura 1 por correo")
        self.assertIn("borrador", respuesta)
        self.assertIn("emitir y enviar factura 1", respuesta)
        self.assertEqual(self.en_cola(), [])


class SinCorreoTests(_Base):
    CON_CORREO = False

    def test_it_says_the_client_has_no_email_instead_of_failing(self):
        respuesta = self.wa("envía la factura 1 por correo")
        self.assertIn("no tiene correo", respuesta)
        self.assertIn("Clientes", respuesta)
        self.assertEqual(self.en_cola(), [])

    def test_whatsapp_works_when_the_phone_is_the_one_on_file(self):
        self.wa("envía la factura 1 por whatsapp")
        self.assertIn("en camino", self.wa("sí"))


class SinProveedorTests(_Base):
    """Nunca decir «en camino» si no hay forma de enviar.

    Con el servidor sin credenciales de correo, la app encolaba el envío igual y
    contestaba «📨 en camino». El autónomo creía que su cliente tenía la factura y
    no había salido nada. Es el peor tipo de fallo: silencioso y de los que hacen
    que no te paguen.
    """

    def setUp(self):
        super().setUp()
        self.sin_correo = patch.multiple(
            config, SMTP_HOST="", SMTP_USER="", SMTP_PASS="", BREVO_API_KEY="")
        self.sin_correo.start()

    def tearDown(self):
        self.sin_correo.stop()
        super().tearDown()

    def test_it_says_what_is_missing_instead_of_promising_delivery(self):
        self.wa("envía la factura 1 por correo")
        respuesta = self.wa("sí")
        self.assertNotIn("en camino", respuesta)
        self.assertIn("no está configurado", respuesta)
        # Y nombra lo que falta, para poder arreglarlo sin adivinar.
        self.assertIn("BREVO_API_KEY", respuesta)
        self.assertEqual(self.en_cola(), [])

    def test_it_offers_the_way_out_that_does_work(self):
        self.wa("envía la factura 1 por correo")
        self.assertIn("descarga el PDF", self.wa("sí"))


class ContrapesoTests(_Base):
    def test_writing_a_normal_email_still_works(self):
        # La salida que se añadió al redactor solo puede afectar a las frases
        # que nombran una factura por su número.
        respuesta = self.wa("escribe un correo a Juan para decirle que llego tarde")
        self.assertIn("Borrador", respuesta)
        self.assertNotIn("Entregar la factura", respuesta)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
