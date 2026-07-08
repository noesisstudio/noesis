from __future__ import annotations

import sys
import traceback

from starlette.testclient import TestClient

from noesis import config, db, demo
from noesis.web import server


HOT_API_PATHS = [
    "/api/{bid}/summary",
    "/api/{bid}/plan",
    "/api/{bid}/pending",
    "/api/{bid}/analysis",
    "/api/{bid}/received-invoices",
    "/api/{bid}/leads",
    "/api/{bid}/products",
    "/api/{bid}/suppliers",
    "/api/{bid}/gestoria/requests",
    "/api/{bid}/pnl",
    "/api/{bid}/agenda",
    "/api/{bid}/income/by-client",
    "/api/{bid}/costs/breakdown",
    "/api/{bid}/taxes",
    "/api/{bid}/invoices",
]


HOT_PAGE_PATHS = [
    "/b/{bid}/resumen",
    "/b/{bid}/costes",
    "/b/{bid}/analisis",
    "/b/{bid}/documentos",
    "/b/{bid}/crm",
    "/b/{bid}/agenda",
]


def _ensure_postgres() -> None:
    if not config.DATABASE_URL:
        raise RuntimeError(
            "Este smoke test exige DATABASE_URL para ejecutarse contra Postgres."
        )


def _seed_if_empty() -> dict:
    businesses = db.list_businesses()
    if not businesses:
        demo.seed_rich(reset=False, force=True)
        businesses = db.list_businesses()
    if not businesses:
        raise RuntimeError("No se pudo sembrar ningun negocio de prueba.")
    return businesses[0]


def _login(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={"email": demo.DEMO_EMAIL, "password": demo.DEMO_PASSWORD},
        follow_redirects=False,
    )
    if response.status_code != 303:
        raise RuntimeError(
            f"Login demo fallido: HTTP {response.status_code} {response.text[:200]}"
        )


def _check_gets(client: TestClient, business_id: int) -> list[str]:
    failures: list[str] = []
    for template in [*HOT_PAGE_PATHS, *HOT_API_PATHS]:
        path = template.format(bid=business_id)
        try:
            response = client.get(path)
        except Exception as exc:  # noqa: BLE001 - queremos que CI muestre el tipo real.
            detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            failures.append(f"{path}: excepcion {detail}")
            continue
        if response.status_code >= 500:
            failures.append(
                f"{path}: HTTP {response.status_code} {response.text[:500]}"
            )
    return failures


def main() -> int:
    try:
        _ensure_postgres()
        db.init_db()
        business = _seed_if_empty()
        with TestClient(server.app) as client:
            _login(client)
            failures = _check_gets(client, int(business["id"]))
    except Exception as exc:  # noqa: BLE001 - script de CI: reporta y falla.
        traceback.print_exception(type(exc), exc, exc.__traceback__)
        return 1

    if failures:
        print("Rutas calientes con fallo contra Postgres:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    checked = len(HOT_PAGE_PATHS) + len(HOT_API_PATHS)
    print(f"Smoke Postgres OK: {checked} rutas calientes sin 5xx.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
