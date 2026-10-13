"""La demo con datos inventados.

1. Que no pueda escribirse nunca encima de contactos de verdad.
2. Que lo que genera se abra solo: sin pedir nada a la app ni a otra web que no
   sean las tipografías, y avisando arriba de que los datos no existen.
3. Que sea la página de verdad, no una copia que envejece aparte.
"""
import json
import random
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noesis import config, db
from noesis.crm import demo, hoja

from .base import ConBase


class DatosInventadosTests(ConBase):
    def test_the_invented_sheet_has_the_real_columns_and_no_real_domain(self):
        leido = hoja.parse_hoja(demo.hoja_inventada(random.Random(7)))
        self.assertEqual(leido["ignoradas"], [])
        self.assertEqual(len(leido["filas"]),
                         sum(zona[2] for zona in demo._ZONAS.values()))
        self.assertTrue(all(f["email"].endswith(".example") for f in leido["filas"]))
        # Teléfonos que no pueden ser de nadie: prefijo, ceros y un contador.
        self.assertTrue(all(re.fullmatch(r"\+349\d{1,2}00\d{4,5}", f["telefono"])
                            for f in leido["filas"]))

    def test_the_same_seed_gives_the_same_list(self):
        self.assertEqual(demo.hoja_inventada(random.Random(7)),
                         demo.hoja_inventada(random.Random(7)))

    def test_it_never_mixes_with_contacts_that_are_already_there(self):
        db.add_prospect(nombre="Gestoria de verdad", email="info@real.cat")
        with self.assertRaises(RuntimeError):
            demo.sembrar()
        self.assertEqual(len(db.list_prospects()), 1)

    def test_it_refuses_a_postgres_database(self):
        with patch.object(config, "DATABASE_URL", "postgresql://x/y"), \
                self.assertRaises(RuntimeError):
            demo.sembrar()

    def test_sowing_leaves_a_normal_day_not_eighty_overdue_calls(self):
        from noesis import sales

        cuantos = demo.sembrar()
        resumen = sales.resumen(db.list_prospects())
        self.assertEqual(cuantos["autonomos"], len(demo._AUTONOMOS))
        self.assertLessEqual(len(resumen["hoy"]), 20)
        self.assertGreater(len(resumen["hoy"]), 0)


class ArchivosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.salida = Path(cls.temp.name) / "demo"
        cls.antes = (config.DB_PATH, config.DATABASE_URL, config.ADMIN_EMAIL)
        cls.resultado = demo.construir(cls.salida)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_the_configuration_is_left_as_it_was(self):
        self.assertEqual(
            (config.DB_PATH, config.DATABASE_URL, config.ADMIN_EMAIL), self.antes)

    def test_it_writes_one_page_per_view_and_the_cards(self):
        self.assertEqual(sorted(p.name for p in self.salida.iterdir()),
                         ["autonomos.html", "fichas.json", "gestorias.html",
                          "index.html"])
        fichas = json.loads((self.salida / "fichas.json").read_text("utf-8"))
        self.assertEqual(len(fichas), self.resultado["fichas"])
        self.assertTrue(all('id="ficha"' in html for html in fichas.values()))

    def test_every_page_opens_on_its_own(self):
        for nombre in demo.VISTAS:
            html = (self.salida / nombre).read_text("utf-8")
            # Nada que pedir a la app: ni estilos, ni script, ni imágenes. (Sin
            # `assertIn` sobre la página: un fallo imprimiría medio megabyte.)
            self.assertFalse('src="/' in html, nombre)
            self.assertFalse('href="/static' in html, nombre)
            self.assertTrue("window.crmDemo" in html, nombre)
            self.assertTrue("Demo con datos inventados" in html, nombre)
            # Las vistas se enlazan entre sí como archivos.
            self.assertTrue('href="gestorias.html"' in html, nombre)
            # Fuera de las tipografías, no se carga ni se enlaza ninguna otra web.
            externos = set(re.findall(r'(?:href|src)="https?://([^/"]+)', html))
            self.assertEqual(externos, {"fonts.googleapis.com"}, nombre)

    def test_the_first_page_has_no_document_shell_and_the_others_do(self):
        # La primera la envuelve quien la publica; las demás se sirven tal cual.
        portada = (self.salida / "index.html").read_text("utf-8")
        self.assertTrue(portada.startswith("<title>"))
        self.assertFalse("<body" in portada)
        otra = (self.salida / "gestorias.html").read_text("utf-8")
        self.assertTrue(otra.startswith("<!doctype html>"))
        self.assertTrue('<meta charset="utf-8">' in otra)

    def test_it_is_the_real_page(self):
        html = (self.salida / "gestorias.html").read_text("utf-8")
        for trozo in ("Cómo va la captación", "Tablero", "Siguiente tanda",
                      "Hoja de Google", "=IMPORTDATA(", "data-crm-pestanas"):
            self.assertTrue(trozo in html, trozo)
        # El menú del resto del panel interno y la sesión no viajan con la demo.
        self.assertFalse('<details class="admin-nav-disclosure"' in html)
        self.assertFalse('action="/logout"' in html)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
