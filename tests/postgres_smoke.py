from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import sys
import traceback

from starlette.testclient import TestClient

from noesis import config, db, demo
from noesis.documents import repo as document_repo
from noesis.web import backups, server


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
    "/api/{bid}/invoice-series",
    "/api/{bid}/recurring-invoices",
    "/api/{bid}/projects",
    "/api/{bid}/documents?q=factura",
]


HOT_PAGE_PATHS = [
    "/b/{bid}/resumen",
    "/b/{bid}/costes",
    "/b/{bid}/analisis",
    "/b/{bid}/documentos",
    "/b/{bid}/crm",
    "/b/{bid}/agenda",
    "/b/{bid}/cobros",
    "/b/{bid}/facturas",
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

    clients = db.list_clients(business_id)
    fiscal_client = next(
        (item for item in clients if item.get("nif") and item.get("address")),
        None,
    )
    if not fiscal_client:
        fiscal_client = db.add_client(
            "Cliente fiscal humo", nif="B12345678",
            address="Calle Cliente 1", business_id=business_id,
        )
    business = db.get_business(business_id)
    if not business.get("nif") or not business.get("address"):
        db.update_fiscal(
            business_id, nif="A12345678", address="Calle Negocio 1"
        )
    professional = db.add_invoice(
        fiscal_client["id"], "Factura profesional Postgres", None,
        business_id=business_id,
        lines=[
            {"description": "Servicio", "quantity": 2,
             "unit_price": 30, "vat_rate": 21},
            {"description": "Material", "quantity": 1,
             "unit_price": 20, "discount_rate": 5, "vat_rate": 10},
        ],
    )
    professional = db.update_invoice_draft(
        professional["id"], business_id, client_id=fiscal_client["id"],
        lines=professional["lines"], irpf_rate=0,
        notes="Validación de factura profesional en PostgreSQL.",
    )
    professional = db.issue_invoice(professional["id"], business_id)
    if len(professional.get("lines") or []) != 2:
        raise RuntimeError("Postgres no conservó las líneas de factura.")
    try:
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE invoice_lines SET unit_price=1 "
                "WHERE invoice_id=? AND business_id=?",
                (professional["id"], business_id),
            )
    except db.IntegrityError:
        pass
    else:
        raise RuntimeError("Postgres permitió alterar una factura emitida.")
    paths.extend([
        f"/api/{business_id}/invoices/{professional['id']}",
        f"/api/{business_id}/invoices/{professional['id']}/history",
        f"/api/{business_id}/invoices/{professional['id']}/pdf",
    ])
    db.add_recurring_invoice(
        business_id, fiscal_client["id"], name="Programación humo Postgres",
        cadence="monthly",
        next_run_on=(datetime.now().date() + timedelta(days=30)).isoformat(),
        lines=[{"description": "Mantenimiento", "quantity": 1,
                "unit_price": 50, "vat_rate": 21}],
    )

    token = db.get_or_create_calendar_token(business_id)
    if db.get_business_by_calendar_token(token)["id"] != business_id:
        raise RuntimeError("El calendario privado no respeta el negocio.")
    paths.append(f"/cal/{token}.ics")

    pending = db.pending_payments(business_id)
    if not pending:
        invoice = db.add_invoice(
            clients[0]["id"], "Factura para conciliación Postgres", 100,
            business_id=business_id,
        )
        pending = [db.issue_invoice(invoice["id"], business_id)]
        pending[0]["remaining_amount"] = pending[0]["total"]
    invoice = pending[0]
    fingerprint = hashlib.sha256(
        f"postgres-smoke:{business_id}:{invoice['id']}".encode()
    ).hexdigest()
    movement = db.add_bank_transaction(
        business_id, import_hash=fingerprint,
        booked_on=datetime.now().date().isoformat(),
        amount=invoice["remaining_amount"],
        description=f"Cobro factura {invoice.get('number') or invoice['id']}",
    )
    if movement:
        db.suggest_bank_transaction(
            movement["id"], business_id, invoice["id"],
            score=120, reason="Humo Postgres.",
        )
        confirmed = db.confirm_bank_transaction(movement["id"], business_id)
        if confirmed.get("status") != "confirmed":
            raise RuntimeError("La conciliación no confirmó el movimiento.")

    now = datetime.now()
    queued = db.enqueue_email_message(
        business_id=business_id, to_email="smoke@example.com",
        subject="Humo Postgres", text_body="Mensaje de prueba interno.",
        idempotency_key=f"postgres-smoke:{business_id}", max_attempts=1,
        now=now.isoformat(timespec="seconds"),
    )
    claimed = db.claim_next_email_message(
        now=now.isoformat(timespec="seconds"),
        stale_before=(now - timedelta(minutes=5)).isoformat(timespec="seconds"),
    )
    if not claimed or claimed["id"] != queued["id"]:
        raise RuntimeError("La outbox de correo no pudo reclamar el mensaje.")
    db.mark_email_retry(
        claimed["id"], error="Humo controlado",
        next_attempt_at=(now + timedelta(minutes=1)).isoformat(timespec="seconds"),
        updated_at=now.isoformat(timespec="seconds"),
    )
    if db.get_email_message(claimed["id"])["status"] != "failed":
        raise RuntimeError("La outbox de correo no agotó el intento de humo.")
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


def _check_security_audit(business_id: int) -> None:
    """Comprueba en Postgres la cadena y el trigger, no solo su DDL."""
    event = db.record_security_event(
        "security.postgres_smoke",
        area="security",
        subject_business_id=business_id,
        metadata={"storage": "postgres"},
    )
    if not db.security_event_integrity()["ok"]:
        raise RuntimeError("La cadena de auditoria no supera la verificacion.")
    try:
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE security_events SET severity='critical' WHERE id=?",
                (event["id"],),
            )
    except db.IntegrityError:
        return
    raise RuntimeError("Postgres permitio modificar la bitacora append-only.")


def _check_document_deduplication(business_id: int) -> None:
    """Comprueba que PostgreSQL aplica la huella única dentro del negocio."""
    digest = hashlib.sha256(
        f"postgres-document-smoke:{business_id}:{datetime.now().isoformat()}".encode()
    ).hexdigest()
    document_repo.add(
        business_id,
        filename="huella-postgres.pdf",
        stored_name="smoke/huella-postgres.pdf",
        mime="application/pdf",
        size=24,
        content_sha256=digest,
    )
    try:
        document_repo.add(
            business_id,
            filename="huella-postgres-copia.pdf",
            stored_name="smoke/huella-postgres-copia.pdf",
            mime="application/pdf",
            size=24,
            content_sha256=digest,
        )
    except db.IntegrityError:
        return
    raise RuntimeError("Postgres permitio duplicar una huella documental del negocio.")


def _check_backup_roundtrip() -> None:
    """Una copia con facturas emitidas debe restaurarse en un esquema aislado."""
    backup_path = backups.run_backup()
    latest = db.latest_backup_run()
    if backup_path is None or not latest or latest.get("status") != "ok":
        detail = (latest or {}).get("error") or "sin artefacto verificado"
        raise RuntimeError(f"El backup PostgreSQL no quedó verificado: {detail}")
    drill = backups.verify_latest_backup_set()
    if not drill.get("ok"):
        raise RuntimeError(
            f"El simulacro de restauración PostgreSQL falló: {drill.get('error')}"
        )


def main() -> int:
    try:
        _ensure_postgres()
        db.init_db()
        business = _seed_if_empty()
        _check_security_audit(int(business["id"]))
        _check_document_deduplication(int(business["id"]))
        with TestClient(server.app) as client:
            _login(client)
            failures = _check_gets(client, int(business["id"]))
        _check_backup_roundtrip()
    except Exception as exc:  # noqa: BLE001 - script de CI: reporta y falla.
        traceback.print_exception(type(exc), exc, exc.__traceback__)
        return 1

    if failures:
        print("Rutas calientes con fallo contra Postgres:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    checked = len(HOT_PAGE_PATHS) + len(HOT_API_PATHS) + 6
    print(f"Smoke Postgres OK: {checked} rutas calientes sin 5xx.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
