"""Pruebas del recuento de visitas.

El objetivo del recuento es saber qué páginas sirven, no seguir a personas. Estas
pruebas fijan justo eso: que cuenta lo público y que no puede guardar nada que
identifique a nadie.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noesis import config, db


class PageViewsTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.original = {
            name: getattr(config, name)
            for name in ("DB_PATH", "DOCS_PATH", "BACKUP_DIR", "DATABASE_URL")
        }
        root = Path(self.temporary.name)
        config.DATABASE_URL = ""
        config.DB_PATH = root / "page-views.db"
        config.DOCS_PATH = root / "uploads"
        config.BACKUP_DIR = root / "backups"
        db.init_db()

    def tearDown(self):
        for name, value in self.original.items():
            setattr(config, name, value)
        self.temporary.cleanup()

    def _client(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        return patch.object(server, "start_scheduler", lambda: None), TestClient(
            server.app
        )

    def test_repeated_views_add_up_instead_of_piling_rows(self):
        for _ in range(3):
            db.record_page_view("/precios")
        resumen = db.page_views_summary(30)
        self.assertEqual(resumen["total"], 3)
        self.assertEqual(len(resumen["by_path"]), 1)

    def test_only_the_referring_domain_is_kept_never_the_full_url(self):
        """Una URL de búsqueda lleva lo que la persona escribió: no se guarda."""
        scheduler, client = self._client()
        with scheduler, client as http:
            http.get("/precios", headers={
                "Referer": "https://www.google.com/search?q=algo+personal",
            })

        procedencias = db.page_views_summary(30)["by_referrer"]
        self.assertEqual(procedencias[0]["referrer_host"], "www.google.com")
        # El término buscado no puede aparecer en ninguna parte.
        with db.get_conn() as conn:
            filas = conn.execute("SELECT * FROM page_views").fetchall()
        self.assertNotIn("algo+personal", str([dict(f) for f in filas]))

    def test_private_areas_and_assets_are_not_counted(self):
        scheduler, client = self._client()
        with scheduler, client as http:
            http.get("/static/app.css")
            http.get("/robots.txt")
            http.get("/health")
            http.get("/api/1/algo")
            http.get("/admin")

        # Ninguna de esas rutas describe interés por la web pública, y la del panel
        # de un cliente ni siquiera debe quedar registrada.
        self.assertEqual(db.page_views_summary(30)["total"], 0)

    def test_a_public_page_is_counted(self):
        scheduler, client = self._client()
        with scheduler, client as http:
            http.get("/precios")

        resumen = db.page_views_summary(30)
        self.assertEqual(resumen["total"], 1)
        self.assertEqual(resumen["by_path"][0]["path"], "/precios")

    def test_counting_never_breaks_a_page(self):
        """Medir es información, no funcionalidad: si falla, la web sigue."""
        scheduler, client = self._client()
        with scheduler, client as http, patch.object(
            db, "record_page_view", side_effect=RuntimeError("base caída")
        ):
            respuesta = http.get("/precios")

        self.assertEqual(respuesta.status_code, 200)


if __name__ == "__main__":
    unittest.main()
