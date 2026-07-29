"""Pruebas de lo que ven los buscadores y de la página de dirección inexistente."""

from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

from noesis import config


class SeoTestCase(unittest.TestCase):
    def _client(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        return patch.object(server, "start_scheduler", lambda: None), TestClient(
            server.app
        )

    def test_robots_keeps_private_areas_out_of_search_engines(self):
        scheduler, client = self._client()
        with scheduler, client as http:
            respuesta = http.get("/robots.txt")

        self.assertEqual(respuesta.status_code, 200)
        texto = respuesta.text
        # Paneles, portales por token y formularios de sesión no deben indexarse:
        # unos no aportan nada en una búsqueda y otros llevan datos de clientes.
        for privado in ("/b/", "/api/", "/admin", "/p/", "/g/", "/t/", "/login"):
            self.assertIn(f"Disallow: {privado}", texto)
        self.assertIn("Sitemap:", texto)

    def test_sitemap_is_valid_and_only_lists_public_pages(self):
        scheduler, client = self._client()
        with scheduler, client as http:
            respuesta = http.get("/sitemap.xml")

        self.assertEqual(respuesta.status_code, 200)
        raiz = ET.fromstring(respuesta.content)
        rutas = [
            url[0].text.replace(config.BASE_URL, "") for url in raiz
        ]
        self.assertIn("/", rutas)
        self.assertIn("/precios", rutas)
        self.assertIn("/solicitar-acceso", rutas)
        # Ninguna zona privada puede colarse en el mapa.
        for privado in ("/admin", "/login", "/onboarding"):
            self.assertNotIn(privado, rutas)

    def test_a_wrong_address_shows_a_page_not_a_raw_error(self):
        scheduler, client = self._client()
        with scheduler, client as http:
            respuesta = http.get("/una-direccion-que-no-existe")

        self.assertEqual(respuesta.status_code, 404)
        self.assertIn("Esta página no existe", respuesta.text)
        # Con el diseño del sitio, no el JSON crudo del servidor.
        self.assertIn("public-header", respuesta.text)
        self.assertNotIn('{"detail"', respuesta.text)

    def test_the_api_still_answers_json_when_something_is_missing(self):
        """Quien consume la API espera datos, no una página HTML."""
        scheduler, client = self._client()
        with scheduler, client as http:
            respuesta = http.get("/api/no-existe")

        self.assertEqual(respuesta.headers["content-type"], "application/json")

    def test_the_classic_favicon_path_answers(self):
        scheduler, client = self._client()
        with scheduler, client as http:
            respuesta = http.get("/favicon.ico")

        self.assertEqual(respuesta.status_code, 200)


if __name__ == "__main__":
    unittest.main()
