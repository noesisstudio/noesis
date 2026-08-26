from __future__ import annotations

import json
import unittest

from noesis import production_check


def _headers(*, indexable: bool = False) -> dict[str, str]:
    headers = {
        "strict-transport-security": "max-age=31536000; includeSubDomains",
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "x-permitted-cross-domain-policies": "none",
        "cross-origin-opener-policy": "same-origin",
        "cross-origin-resource-policy": "same-origin",
        "referrer-policy": "strict-origin-when-cross-origin",
        "content-security-policy": (
            "default-src 'self'; object-src 'none'; frame-ancestors 'none'; "
            "base-uri 'self'"
        ),
    }
    if not indexable:
        headers["x-robots-tag"] = "noindex, nofollow"
    return headers


class ProductionCheckTestCase(unittest.TestCase):
    base_url = "https://bynoesis.com"

    def _fetcher(self, *, schema: int = 50, legal_placeholder: bool = False):
        public_paths = ("/", *production_check.LEGAL_PATHS)
        sitemap = (
            '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            + "".join(
                f"<url><loc>{self.base_url}{path}</loc></url>" for path in public_paths
            )
            + "</urlset>"
        )

        def fetch(url: str) -> production_check.Response:
            path = url.removeprefix(self.base_url)
            if path == "/health":
                body = json.dumps({"status": "ok", "release": "release-test-2026"})
                return production_check.Response(200, url, _headers(), body.encode())
            if path == "/ready":
                body = json.dumps(
                    {"status": "ready", "release": "release-test-2026", "schema": schema}
                )
                return production_check.Response(200, url, _headers(), body.encode())
            if path == "/sitemap.xml":
                return production_check.Response(200, url, _headers(), sitemap.encode())
            if path in public_paths:
                marker = "[Razón social]" if legal_placeholder and path == "/privacidad" else ""
                html = (
                    "<html><head><link rel='canonical' href='"
                    f"{url}'></head><body><h1>Página</h1>{marker}</body></html>"
                )
                return production_check.Response(200, url, _headers(indexable=True), html.encode())
            return production_check.Response(404, url, _headers(), b"")

        return fetch

    def test_accepts_a_complete_public_release(self):
        report = production_check.audit_production(
            self.base_url,
            expected_schema=50,
            expected_release="release-test-2026-full-commit-reference",
            fetcher=self._fetcher(),
        )

        self.assertEqual(report["release"], "release-test-2026")
        self.assertEqual(report["public_pages"], 5)

    def test_rejects_a_stale_release(self):
        with self.assertRaises(production_check.ProductionCheckError) as raised:
            production_check.audit_production(
                self.base_url,
                expected_schema=50,
                expected_release="different-release",
                fetcher=self._fetcher(),
            )

        self.assertIn("no el esperado", str(raised.exception))

    def test_rejects_a_half_applied_schema(self):
        with self.assertRaises(production_check.ProductionCheckError) as raised:
            production_check.audit_production(
                self.base_url,
                expected_schema=50,
                fetcher=self._fetcher(schema=49),
            )

        self.assertIn("esquema 49", str(raised.exception))

    def test_rejects_legal_placeholders(self):
        with self.assertRaises(production_check.ProductionCheckError) as raised:
            production_check.audit_production(
                self.base_url,
                expected_schema=50,
                fetcher=self._fetcher(legal_placeholder=True),
            )

        self.assertIn("marcador legal", str(raised.exception))

    def test_rejects_missing_security_headers(self):
        fetcher = self._fetcher()

        def without_hsts(url: str) -> production_check.Response:
            response = fetcher(url)
            if url.endswith("/health"):
                headers = dict(response.headers)
                headers.pop("strict-transport-security")
                return production_check.Response(
                    response.status, response.url, headers, response.body
                )
            return response

        with self.assertRaises(production_check.ProductionCheckError) as raised:
            production_check.audit_production(
                self.base_url,
                expected_schema=50,
                fetcher=without_hsts,
            )

        self.assertIn("strict-transport-security", str(raised.exception))
