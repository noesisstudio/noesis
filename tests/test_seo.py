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
        # los que llevan datos ni siquiera deben rastrearse. Los accesos públicos sí
        # se dejan rastrear para que Google pueda leer su cabecera HTTP noindex.
        for privado in (
            "/b/", "/api/", "/admin", "/p/", "/g/", "/t/", "/gestoria",
        ):
            self.assertIn(f"Disallow: {privado}", texto)
        self.assertNotIn("Disallow: /login", texto)
        self.assertNotIn("Disallow: /acceso", texto)
        self.assertIn("Allow: /gestoria/login", texto)
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
        self.assertIn("/autonomos", rutas)
        self.assertIn("/gestorias", rutas)
        self.assertIn("/precios", rutas)
        self.assertIn("/solicitar-acceso", rutas)
        # Ninguna zona privada puede colarse en el mapa.
        for privado in ("/admin", "/login", "/onboarding"):
            self.assertNotIn(privado, rutas)

    def test_sitemap_does_not_claim_fake_freshness_or_ignored_priority(self):
        """Noesis no debe decir que todo cambió hoy si no puede demostrarlo."""
        scheduler, client = self._client()
        with scheduler, client as http:
            texto = http.get("/sitemap.xml").text

        self.assertNotIn("<lastmod>", texto)
        self.assertNotIn("<priority>", texto)

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

    def test_public_login_opens_a_clear_role_selector(self):
        scheduler, client = self._client()
        with scheduler, client as http:
            home = http.get("/")
            selector = http.get("/acceso")
            app = http.get("/app", follow_redirects=False)

        self.assertIn('href="/acceso">Iniciar sesión', home.text)
        self.assertEqual(selector.status_code, 200)
        self.assertIn("Autónomo o empresa", selector.text)
        self.assertIn("Gestoría", selector.text)
        self.assertIn('href="/login"', selector.text)
        self.assertIn('href="/gestoria/login"', selector.text)
        self.assertIn("cliente", selector.text.lower())
        self.assertEqual(app.headers["location"], "/acceso")

    def test_every_indexable_page_describes_itself_and_keeps_the_site_menu(self):
        """Una página del sitemap puede ser la primera que alguien vea.

        Si no lleva descripción, el buscador se inventa un fragmento del texto; y
        si no lleva el menú, quien aterrice ahí desde Google no tiene forma de
        llegar al resto. Las legales estuvieron mucho tiempo así.
        """
        from noesis.web.routers import pages

        scheduler, client = self._client()
        with scheduler, client as http:
            titulos = set()
            descripciones = set()
            for ruta in pages._INDEXABLES:
                with self.subTest(ruta=ruta):
                    html = http.get(ruta).text
                    self.assertIn('name="description"', html)
                    self.assertIn('name="robots" content="index, follow', html)
                    self.assertIn('rel="canonical"', html)
                    self.assertIn('class="public-nav"', html)
                    self.assertIn('property="og:url"', html)
                    self.assertIn('name="twitter:description"', html)
                    self.assertEqual(html.count("<h1"), 1)
                    titulo = html.split("<title>", 1)[1].split("</title>", 1)[0]
                    descripcion = html.split(
                        '<meta name="description" content="', 1
                    )[1].split('">', 1)[0]
                    self.assertNotIn(titulo, titulos)
                    self.assertNotIn(descripcion, descripciones)
                    titulos.add(titulo)
                    descripciones.add(descripcion)

    def test_the_home_page_has_a_single_main_heading(self):
        """La maqueta del producto reproduce pantallas con título propio.

        Como son el retrato de una app dentro de la página, no pueden competir con
        el encabezado real: un buscador no sabría de qué trata la portada y un
        lector de pantalla anunciaría diecinueve títulos principales.
        """
        scheduler, client = self._client()
        with scheduler, client as http:
            html = http.get("/").text

        self.assertEqual(html.count("<h1"), 1)

    def test_search_engines_get_a_company_card_they_can_read(self):
        import json
        import re

        scheduler, client = self._client()
        with scheduler, client as http:
            home = http.get("/").text
            prices = http.get("/precios").text

        bloque = re.search(
            r'<script type="application/ld\+json">(.*?)</script>', home, re.S
        )
        self.assertIsNotNone(bloque, "falta la ficha de empresa para buscadores")
        datos = json.loads(bloque.group(1))  # inválido = ignorado por Google
        tipos = {item["@type"] for item in datos["@graph"]}
        self.assertEqual(tipos, {"Organization", "WebSite"})
        organizacion = next(
            item for item in datos["@graph"] if item["@type"] == "Organization"
        )
        self.assertEqual(organizacion["name"], "Noesis")
        self.assertNotIn('application/ld+json', prices)

    def test_non_public_routes_send_an_explicit_noindex_header(self):
        scheduler, client = self._client()
        with scheduler, client as http:
            for ruta in ("/login", "/acceso", "/gestoria/login", "/no-existe"):
                with self.subTest(ruta=ruta):
                    response = http.get(ruta)
                    self.assertEqual(
                        response.headers.get("x-robots-tag"), "noindex, nofollow"
                    )


if __name__ == "__main__":
    unittest.main()
