"""Comprobación externa, segura y repetible del release publicado.

No usa sesiones ni credenciales. Comprueba únicamente superficies públicas para
detectar despliegues incompletos, regresiones SEO/legales y pérdida de cabeceras de
seguridad antes de que las descubra un cliente.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree


USER_AGENT = "Bynoesis-Production-Check/1.0"
LEGAL_PATHS = ("/privacidad", "/terminos", "/aviso-legal", "/encargado-tratamiento")
LEGAL_PLACEHOLDERS = (
    "[razón social]",
    "[razon social]",
    "[nif/cif]",
    "[dirección]",
    "[direccion]",
)
REQUIRED_HEADERS = {
    "strict-transport-security": "max-age=",
    "x-content-type-options": "nosniff",
    "x-frame-options": "deny",
    "x-permitted-cross-domain-policies": "none",
    "cross-origin-opener-policy": "same-origin",
    "cross-origin-resource-policy": "same-origin",
    "referrer-policy": "strict-origin-when-cross-origin",
}
REQUIRED_CSP = (
    "object-src 'none'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
)


@dataclass(frozen=True)
class Response:
    status: int
    url: str
    headers: dict[str, str]
    body: bytes

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


class ProductionCheckError(RuntimeError):
    """Agrupa todos los fallos del release para corregirlos en una sola pasada."""

    def __init__(self, failures: list[str]):
        super().__init__("; ".join(failures))
        self.failures = failures


Fetcher = Callable[[str], Response]


def fetch(url: str, *, timeout: float = 10.0) -> Response:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as raw:  # noqa: S310 - URL explícita del operador
            return Response(
                status=int(raw.status),
                url=raw.geturl(),
                headers={key.lower(): value for key, value in raw.headers.items()},
                body=raw.read(2_000_000),
            )
    except HTTPError as exc:
        return Response(
            status=int(exc.code),
            url=exc.geturl(),
            headers={key.lower(): value for key, value in exc.headers.items()},
            body=exc.read(2_000_000),
        )
    except (OSError, URLError) as exc:
        raise RuntimeError(f"no se pudo conectar con {url} ({type(exc).__name__})") from exc


def _json(response: Response, path: str, failures: list[str]) -> dict:
    try:
        payload = json.loads(response.text)
    except json.JSONDecodeError:
        failures.append(f"{path} no devuelve JSON válido")
        return {}
    if not isinstance(payload, dict):
        failures.append(f"{path} no devuelve un objeto JSON")
        return {}
    return payload


def _public_urls(sitemap: Response, base_url: str, failures: list[str]) -> list[str]:
    try:
        root = ElementTree.fromstring(sitemap.body)
    except ElementTree.ParseError:
        failures.append("/sitemap.xml no contiene XML válido")
        return []
    base_host = urlsplit(base_url).netloc.lower()
    urls = []
    for element in root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url"):
        location = element.findtext(
            "{http://www.sitemaps.org/schemas/sitemap/0.9}loc", default=""
        ).strip()
        if not location:
            failures.append("el sitemap contiene una URL vacía")
            continue
        if urlsplit(location).netloc.lower() != base_host:
            failures.append(f"el sitemap declara un dominio ajeno: {location}")
            continue
        urls.append(location)
    if not urls:
        failures.append("el sitemap no declara ninguna página pública")
    if len(urls) != len(set(urls)):
        failures.append("el sitemap contiene URLs duplicadas")
    return list(dict.fromkeys(urls))


def audit_production(
    base_url: str,
    *,
    expected_schema: int,
    expected_release: str = "",
    fetcher: Fetcher = fetch,
) -> dict:
    """Audita el release y devuelve evidencia mínima; lanza un error agregado."""
    base_url = base_url.rstrip("/")
    if urlsplit(base_url).scheme != "https":
        raise ProductionCheckError(["la URL de producción debe usar HTTPS"])

    failures: list[str] = []
    health = fetcher(f"{base_url}/health")
    ready = fetcher(f"{base_url}/ready")
    for path, response in (("/health", health), ("/ready", ready)):
        if response.status != 200:
            failures.append(f"{path} responde HTTP {response.status}, no 200")

    health_data = _json(health, "/health", failures)
    ready_data = _json(ready, "/ready", failures)
    if health_data.get("status") != "ok":
        failures.append("/health no declara status=ok")
    if ready_data.get("status") != "ready":
        failures.append("/ready no declara status=ready")
    health_release = str(health_data.get("release", "")).strip()
    ready_release = str(ready_data.get("release", "")).strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]{6,64}", health_release):
        failures.append("/health no identifica un release público válido")
    if health_release != ready_release:
        failures.append("/health y /ready pertenecen a releases distintos")
    release_matches = (
        not expected_release
        or health_release.startswith(expected_release)
        or expected_release.startswith(health_release)
    )
    if not release_matches:
        failures.append(
            f"producción ejecuta {health_release or 'un release desconocido'}, "
            f"no el esperado {expected_release}"
        )
    if ready_data.get("schema") != expected_schema:
        failures.append(
            f"producción usa esquema {ready_data.get('schema')}; se esperaba {expected_schema}"
        )

    for header, expected_fragment in REQUIRED_HEADERS.items():
        actual = health.headers.get(header, "").lower()
        if expected_fragment not in actual:
            failures.append(f"falta la protección HTTP {header}={expected_fragment}")
    csp = health.headers.get("content-security-policy", "").lower()
    for directive in REQUIRED_CSP:
        if directive not in csp:
            failures.append(f"la CSP publicada no contiene {directive}")
    if "noindex" not in health.headers.get("x-robots-tag", "").lower():
        failures.append("/health no está excluido de buscadores")

    sitemap = fetcher(f"{base_url}/sitemap.xml")
    if sitemap.status != 200:
        failures.append(f"/sitemap.xml responde HTTP {sitemap.status}, no 200")
    public_urls = _public_urls(sitemap, base_url, failures)
    pages: dict[str, Response] = {}
    for url in public_urls:
        response = fetcher(url)
        path = urlsplit(url).path or "/"
        pages[path] = response
        if response.status != 200:
            failures.append(f"{path} responde HTTP {response.status}, no 200")
            continue
        text = response.text.lower()
        if "<html" not in text:
            failures.append(f"{path} no devuelve una página HTML")
        if len(re.findall(r"<h1(?:\s|>)", text)) != 1:
            failures.append(f"{path} debe tener exactamente un H1")
        if "noindex" in response.headers.get("x-robots-tag", "").lower():
            failures.append(f"{path} figura en el sitemap pero publica noindex")
        canonical = re.search(
            r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', text
        )
        if not canonical:
            failures.append(f"{path} no publica canonical")
        elif urlsplit(canonical.group(1)).netloc.lower() != urlsplit(base_url).netloc.lower():
            failures.append(f"{path} publica un canonical fuera del dominio")

    for path in LEGAL_PATHS:
        response = pages.get(path)
        if response is None:
            failures.append(f"{path} no aparece en el sitemap")
            continue
        text = response.text.lower()
        for placeholder in LEGAL_PLACEHOLDERS:
            if placeholder in text:
                failures.append(f"{path} conserva el marcador legal {placeholder}")

    if failures:
        raise ProductionCheckError(failures)
    return {
        "status": "ok",
        "base_url": base_url,
        "release": health_release,
        "schema": expected_schema,
        "public_pages": len(public_urls),
        "security_headers": len(REQUIRED_HEADERS) + 1,
    }


def _repository_schema() -> int:
    state_path = Path.cwd() / "docs" / "project-state.json"
    try:
        value = json.loads(state_path.read_text(encoding="utf-8"))["schema_version"]
        return int(value)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ProductionCheckError(
            [
                "no se pudo obtener el esquema esperado de docs/project-state.json; "
                "indícalo con --expected-schema"
            ]
        ) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Comprueba desde fuera que el release público de Bynoesis está completo."
    )
    parser.add_argument("--base-url", default="https://bynoesis.com")
    parser.add_argument(
        "--expected-schema",
        type=int,
        default=0,
        help="Por defecto se lee de docs/project-state.json.",
    )
    parser.add_argument("--expected-release", default="")
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--delay", type=float, default=15.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        expected_schema = args.expected_schema or _repository_schema()
    except ProductionCheckError as exc:
        print(f"ERROR · {exc}")
        return 1
    attempts = max(1, min(args.attempts, 20))
    last_error: ProductionCheckError | None = None
    for attempt in range(1, attempts + 1):
        try:
            report = audit_production(
                args.base_url,
                expected_schema=expected_schema,
                expected_release=args.expected_release.strip(),
            )
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                print(
                    "OK · producción coherente · "
                    f"release {report['release']} · esquema {report['schema']} · "
                    f"{report['public_pages']} páginas públicas"
                )
            return 0
        except (ProductionCheckError, RuntimeError) as exc:
            last_error = (
                exc if isinstance(exc, ProductionCheckError) else ProductionCheckError([str(exc)])
            )
            if attempt < attempts:
                time.sleep(max(0.0, min(args.delay, 60.0)))
    assert last_error is not None
    print("ERROR · el release publicado no supera la puerta externa:")
    for failure in last_error.failures:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
