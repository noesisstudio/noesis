"""Pruebas de las páginas dedicadas a un oficio.

Existen para captar búsquedas largas —«programa para fontaneros»— y para que quien
llega se reconozca. Las dos cosas dependen de que cada página diga algo distinto de
verdad, así que eso es lo que se comprueba aquí.
"""

from __future__ import annotations

import itertools
import re
import unittest
from unittest.mock import patch

from noesis.web import oficios


class OficiosTestCase(unittest.TestCase):
    def _client(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        return patch.object(server, "start_scheduler", lambda: None), TestClient(
            server.app
        )

    def _cuerpo(self, html: str) -> set[str]:
        """Palabras del contenido, sin etiquetas."""
        principal = re.search(r"<main.*?</main>", html, re.S)
        limpio = re.sub(r"<[^>]+>", " ", principal.group(0))
        return set(re.findall(r"[a-záéíóúñü]{4,}", limpio.lower()))

    def test_each_trade_page_speaks_for_itself(self):
        scheduler, client = self._client()
        with scheduler, client as http:
            for slug, oficio in oficios.listado():
                with self.subTest(oficio=slug):
                    respuesta = http.get(f"/para-{slug}")
                    self.assertEqual(respuesta.status_code, 200)
                    html = respuesta.text
                    # Título y descripción propios: si los compartieran, un buscador
                    # elegiría una sola y descartaría el resto.
                    self.assertIn(oficio["titulo"], html)
                    self.assertIn(oficio["descripcion"], html)
                    self.assertIn(oficio["h1"], html)
                    self.assertEqual(html.count("<h1"), 1)

    def test_the_pages_are_not_the_same_text_with_a_word_swapped(self):
        """Copiar una página y cambiar el oficio es lo que Google llama página puente.

        Se penaliza, así que hacerlo sería peor que no tenerlas. Este límite existe
        para que quien añada un oficio nuevo tenga que escribirlo de verdad.
        """
        scheduler, client = self._client()
        with scheduler, client as http:
            cuerpos = {
                slug: self._cuerpo(http.get(f"/para-{slug}").text)
                for slug, _ in oficios.listado()
            }

        for a, b in itertools.combinations(cuerpos, 2):
            comun = len(cuerpos[a] & cuerpos[b]) / len(cuerpos[a] | cuerpos[b])
            with self.subTest(pareja=f"{a}/{b}"):
                # Lo que comparten es el menú, el pie y las palabras corrientes del
                # castellano; el contenido propio debe pesar bastante más.
                self.assertLess(comun, 0.55, f"{a} y {b} se parecen demasiado")

    def test_an_invented_trade_is_not_a_page(self):
        """Si respondiera a cualquier palabra, se indexarían direcciones inventadas."""
        scheduler, client = self._client()
        with scheduler, client as http:
            respuesta = http.get("/para-astronautas")

        self.assertEqual(respuesta.status_code, 404)

    def test_the_home_page_links_to_every_trade(self):
        """Un buscador llega a estas páginas por enlaces, no por adivinación."""
        scheduler, client = self._client()
        with scheduler, client as http:
            portada = http.get("/").text

        for slug, _ in oficios.listado():
            self.assertIn(f'href="/para-{slug}"', portada)

    def test_every_trade_is_offered_to_search_engines(self):
        scheduler, client = self._client()
        with scheduler, client as http:
            mapa = http.get("/sitemap.xml").text

        for slug, _ in oficios.listado():
            self.assertIn(f"/para-{slug}", mapa)


if __name__ == "__main__":
    unittest.main()
