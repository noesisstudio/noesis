"""Contratos del sitio público: promesas, privacidad, rutas y medición."""
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from noesis import config, db
from noesis.web import server
from noesis.web.deps import TEMPLATES
from noesis.web.public_marketing import marketing_context
from noesis.web.routers import pages


class PublicMarketingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [
            patch.object(config, "DB_PATH", Path(self.temp.name) / "site.db"),
            patch.object(config, "DATABASE_URL", ""),
            patch.object(config, "SEED_DEMO", False),
            patch.object(config, "RESET_DB", False),
            patch.object(server, "start_scheduler", lambda: None),
            patch.object(config, "PUBLIC_WHATSAPP_DEMO_PHONE", ""),
        ]
        for item in self.patches:
            item.start()
        pages._public_event_times.clear()
        self.http = TestClient(server.app)
        self.http.__enter__()

    def tearDown(self):
        self.http.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def post_event(self, data, **kwargs):
        return self.http.post("/public/event", json=data, headers={
            "origin": "http://testserver", "sec-fetch-site": "same-origin",
        }, **kwargs)

    def test_public_routes_metadata_and_schema_are_consistent(self):
        titles = set()
        for path in ("/", "/autonomos", "/gestorias", "/contacto", "/preguntas"):
            with self.subTest(path=path):
                response = self.http.get(path)
                self.assertEqual(response.status_code, 200)
                text = response.text
                self.assertEqual(len(re.findall(r"<h1[ >]", text)), 1)
                title = re.search(r"<title>(.*?)</title>", text, re.S)[1]
                self.assertNotIn(title, titles)
                titles.add(title)
                self.assertIn(f'href="{config.BASE_URL}{path}"', text)
                self.assertIn('name="description"', text)
                self.assertIn('name="twitter:card"', text)
                self.assertIn('property="og:title"', text)
                for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S):
                    graph = json.loads(raw)
                    for item in graph.get("@graph", []):
                        self.assertNotIn(item["@type"], {"Review", "AggregateRating", "LocalBusiness"})
                        if item["@type"] == "FAQPage":
                            for question in item["mainEntity"]:
                                self.assertIn(question["name"], text)
                ids = re.findall(r'\bid="([^"]+)"', text)
                self.assertEqual(len(ids), len(set(ids)), "IDs duplicados")

    def test_media_unavailable_never_claims_audio_or_automatic_ocr(self):
        with patch.dict(TEMPLATES.env.globals, {"voice_available": False, "ocr_available": False}):
            text = self.http.get("/").text
        self.assertNotIn('class="voice-message"', text)
        self.assertNotIn("He leído 52,40", text)
        self.assertIn("Dime el importe por escrito", text)
        self.assertIn("Los audios", text)
        self.assertIn("Borrador preparado.", text)
        self.assertNotIn("Factura creada.", text)

    def test_media_enabled_shows_reviewable_examples(self):
        with patch.dict(TEMPLATES.env.globals, {"voice_available": True, "ocr_available": True}):
            text = self.http.get("/").text
        self.assertIn('class="voice-message"', text)
        self.assertIn("Confirma la lectura", text)
        self.assertIn("822,80", text)

    def test_whatsapp_cta_requires_explicit_valid_public_number(self):
        for value in ("", "+34123456789", "javascript:alert(1)", "123?secret"):
            with patch.object(config, "PUBLIC_WHATSAPP_DEMO_PHONE", value):
                context = marketing_context("inicio")
                self.assertFalse(context["public_whatsapp_demo"])
                self.assertTrue(context["marketing_cta_href"].startswith("/"))
        with patch.object(config, "PUBLIC_WHATSAPP_DEMO_PHONE", "34123456789"):
            context = marketing_context("inicio")
            self.assertTrue(context["public_whatsapp_demo"])
            self.assertTrue(context["marketing_cta_href"].startswith("https://wa.me/34123456789?"))

    def test_all_ctas_respect_closed_signup(self):
        with patch.dict(TEMPLATES.env.globals, {"public_signup_available": False}):
            for path in ("/", "/autonomos", "/gestorias", "/precios"):
                page = self.http.get(path).text
                self.assertNotIn("/onboarding?intent=", page, path)
                self.assertIn("/solicitar-acceso", page, path)

    def test_calendar_is_inert_until_permission_and_csp_is_scoped(self):
        contact = self.http.get("/contacto")
        self.assertNotIn("<iframe", contact.text)
        self.assertNotRegex(contact.text, r'<script[^>]+src="https://')
        self.assertIn("Permitir y ver calendario", contact.text)
        self.assertIn("agenda-una-llamada-con-nosotros", contact.text)
        self.assertIn("frame-src https://cal.com;", contact.headers["content-security-policy"])
        for path in ("/", "/autonomos", "/gestorias", "/privacidad"):
            page = self.http.get(path)
            self.assertIn("frame-src 'none';", page.headers["content-security-policy"])
            self.assertNotIn('src="/static/public-calendar.js', page.text)

    def test_interactions_are_separate_from_visits(self):
        db.record_page_view("/autonomos")
        response = self.post_event({"event": "hero_demo_started", "page": "/"})
        self.assertEqual(response.status_code, 204)
        self.assertNotIn("set-cookie", response.headers)
        self.assertEqual(db.page_views_summary()["total"], 1)
        self.assertEqual(db.public_interactions_summary(), [
            {"event": "hero_demo_started", "page": "/", "total": 1},
        ])

    def test_public_gestorias_is_counted_but_private_gestoria_is_not(self):
        from starlette.requests import Request

        with patch.object(db, "record_page_view") as record:
            for path in ("/gestorias", "/gestoria", "/gestoria/clientes/7"):
                request = Request({"type": "http", "method": "GET", "path": path,
                                   "headers": [], "scheme": "http",
                                   "server": ("testserver", 80), "query_string": b""})
                server._count_public_view(request, 200)
            record.assert_called_once_with("/gestorias", "")

    def test_public_links_and_fragment_targets_exist(self):
        from html import unescape
        from urllib.parse import urlsplit

        cache = {}
        for source in ("/", "/autonomos", "/gestorias", "/contacto"):
            page = self.http.get(source).text
            self.assertNotIn('id="testimonials-title"', page)
            for raw in re.findall(r'href="([^"]+)"', page):
                target = urlsplit(unescape(raw))
                if target.scheme or target.netloc or not raw.startswith(("/", "#")):
                    continue
                path = target.path or source
                if path.startswith("/static/"):
                    continue
                if path not in cache:
                    response = self.http.get(path)
                    self.assertLess(response.status_code, 400, path)
                    cache[path] = response.text
                if target.fragment:
                    self.assertIn(f'id="{target.fragment}"', cache[path], raw)

    def test_rejects_personal_data_unbounded_payloads_and_foreign_origins(self):
        for data in ({"event": "hero_demo_started", "page": "/", "email": "someone@example.com"},
                     {"event": "unknown", "page": "/"}, {"event": "final_cta", "page": "/b/5"},
                     {"event": "final_cta", "page": "/?email=private"},
                     {"event": [], "page": "/"}, []):
            self.assertEqual(self.post_event(data).status_code, 400)
        self.assertEqual(self.post_event({"event": "x" * 300, "page": "/"}).status_code, 413)
        response = self.http.post("/public/event", json={"event": "final_cta", "page": "/"},
                                  headers={"origin": "https://outside.example"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(db.public_interactions_summary(), [])

    def test_event_failure_does_not_break_conversion(self):
        with patch.object(db, "record_page_view", side_effect=RuntimeError("offline")):
            self.assertEqual(self.post_event({"event": "final_cta", "page": "/"}).status_code, 204)
        self.assertEqual(self.http.get("/contacto").status_code, 200)

    def test_bounded_event_rate(self):
        import time
        pages._public_event_times.extend([time.monotonic()] * 300)
        self.assertEqual(self.post_event({"event": "final_cta", "page": "/"}).status_code, 429)
