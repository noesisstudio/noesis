"""Regresiones del perímetro de seguridad y de invariantes fiscales."""

from __future__ import annotations

import tempfile
import unittest
import urllib.error
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from unittest.mock import patch

from hypothesis import given, settings, strategies as st
from starlette.testclient import TestClient

from noesis import config, db
from noesis.documents import service as docservice
from noesis.web import auth, server, whatsapp
from tests.fixtures import TINY_JPEG


class SecurityHardeningTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        self.original_docs_path = config.DOCS_PATH
        self.original_database_url = config.DATABASE_URL
        config.DATABASE_URL = ""
        config.DB_PATH = Path(self.tempdir.name) / "security.db"
        config.DOCS_PATH = Path(self.tempdir.name) / "uploads"
        db.init_db()

    def tearDown(self):
        config.DB_PATH = self.original_db_path
        config.DOCS_PATH = self.original_docs_path
        config.DATABASE_URL = self.original_database_url
        self.tempdir.cleanup()

    def test_upload_rejects_disguised_or_active_content_before_storage(self):
        business = db.create_business("Seguridad", "security@example.com")
        invalid = (
            ("falso.pdf", TINY_JPEG),
            ("falso.jpg", b"%PDF-1.7\n%%EOF"),
            ("activo.pdf", b"%PDF-1.7\n/JavaScript /JS\n%%EOF"),
        )
        for filename, payload in invalid:
            with self.subTest(filename=filename), self.assertRaises(docservice.UploadError):
                docservice.upload(
                    business["id"], filename, payload, run_ocr=False
                )
        stored = config.DOCS_PATH / str(business["id"])
        self.assertFalse(stored.exists())

    def test_upload_accepts_a_real_small_image(self):
        business = db.create_business("Imagen", "image@example.com")
        document = docservice.upload(
            business["id"], "foto.jpg", TINY_JPEG, run_ocr=False
        )
        self.assertEqual(document["mime"], "image/jpeg")

    def test_rate_limit_is_persistent_and_does_not_store_the_identity(self):
        raw_key = "login-account:persona@example.com"
        for _ in range(8):
            auth.record_failed_attempt(raw_key)
        self.assertTrue(auth.is_rate_limited(raw_key))
        with db.get_conn() as conn:
            rows = conn.execute("SELECT key_hash FROM auth_attempts").fetchall()
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(raw_key not in row["key_hash"] for row in rows))
        auth.clear_attempts(raw_key)
        self.assertFalse(auth.is_rate_limited(raw_key))

    def test_request_ids_headers_and_logout_cleanup(self):
        with patch.object(config, "LOG_REQUESTS", False), TestClient(server.app) as client:
            response = client.get("/", headers={"X-Request-ID": "incident-12345"})
            self.assertEqual(response.headers["x-request-id"], "incident-12345")
            self.assertEqual(response.headers["x-content-type-options"], "nosniff")
            self.assertEqual(response.headers["x-frame-options"], "DENY")
            self.assertEqual(response.headers["cross-origin-opener-policy"], "same-origin")
            logout = client.post("/logout")
            self.assertEqual(logout.history[0].headers["clear-site-data"],
                             '"cache", "cookies", "storage"')

    def test_declared_oversized_request_is_rejected_before_parsing(self):
        with patch.object(config, "MAX_REQUEST_BYTES", 10), TestClient(server.app) as client:
            response = client.post(
                "/login",
                content=b"x",
                headers={"Content-Length": "100"},
            )
        self.assertEqual(response.status_code, 413)

    def test_private_portals_do_not_cache_or_leak_the_token_as_referrer(self):
        with patch.object(config, "LOG_REQUESTS", False), TestClient(server.app) as client:
            response = client.get("/p/token-inexistente")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")

    def test_whatsapp_media_only_allows_meta_hosts_and_safe_redirects(self):
        self.assertTrue(
            whatsapp._trusted_meta_media_url("https://lookaside.fbsbx.com/media")
        )
        for url in (
            "http://lookaside.fbsbx.com/media",
            "https://facebook.com.evil.example/media",
            "https://token@fbcdn.net/media",
            "https://127.0.0.1/internal",
        ):
            with self.subTest(url=url):
                self.assertFalse(whatsapp._trusted_meta_media_url(url))
        with self.assertRaises(urllib.error.URLError):
            whatsapp._TrustedMetaRedirect().redirect_request(
                None, None, 302, "Found", {}, "https://evil.example/internal"
            )


class FiscalInvariantTestCase(unittest.TestCase):
    @settings(max_examples=80, deadline=None)
    @given(
        cents=st.integers(min_value=1, max_value=100_000_000),
        vat=st.sampled_from([0, 4, 10, 21]),
        irpf=st.sampled_from([0, 7, 15]),
    )
    def test_invoice_total_is_always_base_plus_vat_minus_irpf(
        self, cents: int, vat: int, irpf: int
    ):
        base = Decimal(cents) / Decimal(100)
        lines = db._normalize_invoice_lines([{
            "description": "Servicio",
            "quantity": 1,
            "unit_price": str(base),
            "discount_rate": 0,
            "vat_rate": vat,
        }])
        totals = db._invoice_totals(lines, irpf)
        expected = (
            Decimal(str(totals["base"]))
            + Decimal(str(totals["vat_amount"]))
            - Decimal(str(totals["irpf_amount"]))
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.assertEqual(Decimal(str(totals["total"])), expected)


if __name__ == "__main__":
    unittest.main()
