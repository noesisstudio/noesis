"""Corregir una propuesta hablando, sin repetir la orden entera.

Con la revisión encendida —lo de producción— la conversación de cada día es
«propongo → confirmas o corriges». Corregir solo funcionaba escribiendo
«corregir:» y repitiendo la orden completa. Medido el 24-09-2026: de nueve formas
naturales de corregir funcionaba **una**, la de «corregir:». Las demás soltaban el
parte del día o el resumen de impuestos y, peor, **descartaban la propuesta**, así
que había que reescribirlo todo.

Las dos reglas que fijan las pruebas de aquí:

    Una corrección cambia SOLO lo que se nombra; lo demás se conserva.
    Una orden nueva sigue sustituyendo la propuesta, y el sí y el no siguen
    valiendo lo que valían.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noesis import config, db
from noesis.web import chat


class _Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = patch.multiple(
            config, DATABASE_URL="", DB_PATH=Path(self.temp.name) / "t.db",
            BACKUP_DIR=Path(self.temp.name) / "b",
            DOCS_PATH=Path(self.temp.name) / "d", ANTHROPIC_API_KEY="",
            ASSISTANT_REVIEW_ENABLED=True)
        self.settings.start()
        db.init_db()
        self.bid = db.create_business("Reformas Prueba", "a@example.com")["id"]
        db.update_fiscal(self.bid, nif="12345678Z", address="Calle Prueba 1")
        db.add_client("Juan", nif="87654321X", address="Calle Juan 1",
                      business_id=self.bid)
        db.add_client("Pedro", nif="11111111H", address="Calle Pedro 2",
                      business_id=self.bid)

    def tearDown(self):
        self.settings.stop()
        self.temp.cleanup()

    def wa(self, frase):
        return chat.handle(self.bid, frase, channel="whatsapp",
                           actor_phone="34600111222")["reply"]

    def propuesta(self):
        return self.wa("hazme una factura a Juan por obra 100 euros")


class ImporteTests(_Base):
    def test_every_way_of_correcting_the_amount(self):
        for frase in ("no, eran 120", "no, son 120 euros", "120 euros",
                      "mejor 120 euros", "cámbialo a 120", "que sean 120 euros"):
            with self.subTest(frase=frase):
                self.tearDown()
                self.setUp()
                self.propuesta()
                revisada = self.wa(frase)
                self.assertIn("120,00", revisada)
                # Y lo que no se nombra no se toca.
                self.assertIn("Juan", revisada)
                self.assertIn("obra", revisada)

    def test_the_correction_does_not_write_anything_by_itself(self):
        # Corregir vuelve a proponer: sigue haciendo falta un «sí».
        self.propuesta()
        self.wa("no, eran 120")
        self.assertEqual(db.list_invoices(self.bid), [])
        self.wa("sí")
        self.assertEqual(db.list_invoices(self.bid)[0]["base"], 120.0)


class OtrosCamposTests(_Base):
    def test_correcting_the_client_keeps_the_amount_and_concept(self):
        self.propuesta()
        revisada = self.wa("es para Pedro")
        self.assertIn("Pedro", revisada)
        self.assertIn("100,00", revisada)
        self.assertIn("obra", revisada)

    def test_correcting_the_concept_keeps_the_client_and_amount(self):
        self.propuesta()
        revisada = self.wa("el concepto es ventana")
        self.assertIn("ventana", revisada)
        self.assertIn("Juan", revisada)
        self.assertIn("100,00", revisada)

    def test_saying_the_amount_already_had_vat(self):
        # «Con IVA incluido» sobre 100 € deja la base en 82,64.
        self.propuesta()
        revisada = self.wa("con IVA incluido")
        self.assertIn("82,64", revisada)

    def test_correcting_the_tax_rates(self):
        self.propuesta()
        self.assertIn("IVA 10.0%", self.wa("ponle 10% de IVA"))
        self.assertIn("IRPF 15.0%", self.wa("y 15% de IRPF"))

    def test_an_expense_can_be_corrected_too(self):
        self.wa("gasté 35 euros en gasolina")
        revisada = self.wa("no, eran 47,50")
        self.assertIn("47,50", revisada)
        self.assertIn("gasolina", revisada)


class ContrapesoTests(_Base):
    """Entender más correcciones no puede romper lo que ya valía."""

    def test_a_new_complete_order_still_replaces_the_proposal(self):
        self.propuesta()
        nueva = self.wa("hazme una factura a Pedro por reforma 500 euros")
        self.assertIn("Pedro", nueva)
        self.assertIn("500,00", nueva)
        self.assertIn("reforma", nueva)
        self.assertEqual(db.list_invoices(self.bid), [])

    def test_yes_and_no_still_mean_what_they_meant(self):
        self.propuesta()
        self.wa("sí")
        self.assertEqual(len(db.list_invoices(self.bid)), 1)
        self.propuesta()
        self.assertIn("Descartado", self.wa("no"))
        self.assertEqual(len(db.list_invoices(self.bid)), 1)

    def test_writing_the_whole_order_after_corregir_still_works(self):
        self.propuesta()
        revisada = self.wa("corregir: factura a Juan por obra 120 euros")
        self.assertIn("120,00", revisada)

    def test_a_question_is_answered_without_inventing_a_correction(self):
        self.propuesta()
        respuesta = self.wa("cuánto me deben")
        self.assertNotIn("Preparar factura", respuesta)
        self.assertEqual(db.list_invoices(self.bid), [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
