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
    "/api/{bid}/projects",
    "/api/{bid}/integrations",
]


HOT_PAGE_PATHS = [
    "/b/{bid}/resumen",
    "/b/{bid}/costes",
    "/b/{bid}/analisis",
    "/b/{bid}/documentos",
    "/b/{bid}/crm",
    "/b/{bid}/agenda",
    "/b/{bid}/proyectos",
    "/b/{bid}/ajustes",
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


def _operational_paths(business_id: int) -> list[str]:
    """Siembra y visita detalles que una lista estática no puede representar."""
    paths: list[str] = []
    projects = db.list_projects(business_id)
    if not projects:
        clients = db.list_clients(business_id)
        if not clients:
            raise RuntimeError("La demo Postgres no creó clientes para el humo.")
        project = db.add_project(
            "Proyecto humo Postgres",
            1000,
            client_id=clients[0]["id"],
            location="Barcelona",
            business_id=business_id,
        )
        projects = [project]
    project_id = int(projects[0]["id"])
    paths.append(f"/api/{business_id}/projects/{project_id}")
    project = db.get_project(project_id, business_id)
    if not project:
        raise RuntimeError("No se pudo leer el proyecto sembrado para el humo.")
    jobs = project.get("jobs") or []
    if not jobs:
        client_id = project.get("client_id")
        if not client_id:
            raise RuntimeError("El proyecto de humo no tiene cliente.")
        jobs = [db.add_job(
            client_id,
            "Trabajo de campo para humo Postgres",
            project_id=project_id,
            business_id=business_id,
        )]
    paths.append(f"/api/{business_id}/jobs/{int(jobs[0]['id'])}/field")
    return paths


def _check_gets(client: TestClient, business_id: int) -> list[str]:
    failures: list[str] = []
    paths = [
        template.format(bid=business_id)
        for template in [*HOT_PAGE_PATHS, *HOT_API_PATHS]
    ]
    paths.extend(_operational_paths(business_id))
    for path in paths:
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

    checked = len(HOT_PAGE_PATHS) + len(HOT_API_PATHS) + 2
    print(f"Smoke Postgres OK: {checked} rutas calientes sin 5xx.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
