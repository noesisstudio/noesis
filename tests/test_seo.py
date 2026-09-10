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
        for privado in ("/b/", "/api/", "/admin", "/p/", "/g/", "/t/"):
            self.assertIn(f"Disallow: {privado}", texto)
        reglas = set(texto.splitlines())
        self.assertIn("Disallow: /gestoria$", reglas)
        self.assertIn("Disallow: /gestoria/", reglas)
        self.assertNotIn("Disallow: /gestoria", reglas)
        self.assertNotIn("Disallow: /login", texto)
        self.assertNotIn("Disallow: /acceso", texto)
        self.assertIn("Allow: /gestoria/login$", reglas)
        # Las directivas son prefijos salvo que terminen en $. La página comercial
        # plural no puede volver a quedar atrapada por la zona profesional privada.
        def bloquea(rule: str, path: str) -> bool:
            patron = rule.removeprefix("Disallow: ")
            return (
                path == patron[:-1]
                if patron.endswith("$")
                else path.startswith(patron)
            )

        self.assertFalse(any(
            bloquea(rule, "/gestorias")
            for rule in reglas
            if rule.startswith("Disallow: ")
        ))
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
        """Bynoesis no debe decir que todo cambió hoy si no puede demostrarlo."""
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
        self.assertEqual(organizacion["name"], "Bynoesis")
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

    def test_llms_txt_summarises_the_public_offer_for_ai_assistants(self):
        """Los asistentes de IA leen /llms.txt para saber qué es la empresa.

        Con precios copiados a mano acabaría contradiciendo a /precios; con
        «noindex, nofollow» se pediría justo lo contrario de seguir sus enlaces.
        """
        from noesis.adapters import billing
        from noesis.web.deps import TEMPLATES

        scheduler, client = self._client()
        with scheduler, client as http, patch.dict(
            TEMPLATES.env.globals, {"public_signup_available": False}
        ):
            respuesta = http.get("/llms.txt")

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(
            respuesta.headers["content-type"].startswith("text/markdown")
        )
        self.assertNotIn("x-robots-tag", respuesta.headers)
        texto = respuesta.text
        self.assertTrue(texto.startswith("# Bynoesis\n\n> "))
        for clave, plan in billing.PLANS.items():
            self.assertIn(f"{plan['name']}: {plan['price']} € al mes + IVA", texto)
            self.assertIn(
                f"{billing.PLAN_ANNUAL_PRICES[clave]} € al año + IVA", texto
            )
        base = config.BASE_URL.rstrip("/")
        for ruta in ("/autonomos", "/gestorias", "/precios", "/preguntas"):
            self.assertIn(f"]({base}{ruta})", texto)
        # Con el alta cerrada no puede invitar a una prueba que no existe.
        self.assertIn(f"{base}/solicitar-acceso", texto)
        self.assertNotIn("Prueba de", texto)
        self.assertIn(config.PUBLIC_CONTACT_EMAIL, texto)

    def test_every_faq_answer_is_marked_up_exactly_as_it_is_shown(self):
        """El JSON-LD de /preguntas y el texto visible salen de la misma fuente.

        Sin voz activa, ni la página ni lo que leen los buscadores pueden
        prometer que Bynoesis entiende notas de voz.
        """
        import json
        import re

        from noesis.web.deps import TEMPLATES

        scheduler, client = self._client()
        with scheduler, client as http, patch.dict(
            TEMPLATES.env.globals, {"voice_available": False, "ocr_available": False}
        ):
            html = http.get("/preguntas").text

        bloque = re.search(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.S
        )
        self.assertIsNotNone(bloque, "/preguntas no lleva datos estructurados")
        grafo = json.loads(bloque.group(1))["@graph"]
        faq = next(item for item in grafo if item["@type"] == "FAQPage")
        self.assertEqual(len(faq["mainEntity"]), 16)
        for pregunta in faq["mainEntity"]:
            with self.subTest(pregunta=pregunta["name"]):
                self.assertIn(f"<summary>{pregunta['name']}</summary>", html)
                self.assertIn(f"<p>{pregunta['acceptedAnswer']['text']}</p>", html)
        voz = next(p for p in faq["mainEntity"] if "notas de voz" in p["name"])
        self.assertIn(
            "se habilita durante la puesta en marcha", voz["acceptedAnswer"]["text"]
        )

    def test_public_pages_use_a_single_brand_name(self):
        """Buscadores y asistentes agrupan lo que se dice de una empresa por su
        nombre: dos nombres para el mismo producto reparten esa identidad."""
        import re

        from noesis.web.routers import pages

        scheduler, client = self._client()
        with scheduler, client as http:
            for ruta in (*pages._INDEXABLES, "/llms.txt"):
                with self.subTest(ruta=ruta):
                    self.assertIsNone(re.search(r"\bNoesis\b", http.get(ruta).text))


if __name__ == "__main__":
    unittest.main()
