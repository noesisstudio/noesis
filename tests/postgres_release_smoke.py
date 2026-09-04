"""Puerta destructiva exclusiva de la base PostgreSQL descartable del CI.

Nunca ejecutar contra Railway. El guardián solo admite localhost/noesis_ci.
El rollback descarta las tablas nuevas a propósito, no datos de clientes reales.
"""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from urllib.parse import urlsplit

from starlette.testclient import TestClient

from noesis import config, db, migrations
from noesis.web import auth, server


PASSWORD = "noesis-release-test-password"  # pragma: allowlist secret


def _guard() -> None:
    url = urlsplit(config.DATABASE_URL)
    if url.hostname not in {"localhost", "127.0.0.1", "::1"} or url.path != "/noesis_ci":
        raise RuntimeError("Solo se admite PostgreSQL local descartable: noesis_ci.")
    if config.IS_PRODUCTION:
        raise RuntimeError("El rollback de pruebas no admite modo producción.")
    assert not config.VALUE_LEDGER_ENABLED
    assert not config.VALUE_LEDGER_ADMIN_ENABLED
    assert migrations.current_version() == 55


def _snapshot() -> dict:
    # SQL fijo: no admite nombres procedentes de usuarios ni de argumentos.
    with db.get_conn() as conn:
        return {
            "invoices": [dict(r) for r in conn.execute("SELECT * FROM invoices ORDER BY id").fetchall()],
            "clients": [dict(r) for r in conn.execute("SELECT * FROM clients ORDER BY id").fetchall()],
            "users": [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY id").fetchall()],
            "clockins": [dict(r) for r in conn.execute("SELECT * FROM worker_clockins ORDER BY id").fetchall()],
        }


def _rollback() -> None:
    original = _snapshot()
    assert migrations.downgrade(54) == 54
    assert _snapshot() == original
    assert migrations.downgrade(53) == 53
    assert _snapshot() == original
    assert migrations.upgrade(54) == 54
    assert _snapshot() == original
    assert migrations.upgrade(55) == 55
    assert _snapshot() == original
    # La guardia fiscal debe seguir funcionando tras todo el ciclo.
    emitted = next(i for i in original["invoices"] if i["status"] in {"enviada", "parcial", "cobrada"})
    try:
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE invoices SET concept='No debe cambiar' WHERE id=? AND business_id=?",
                (emitted["id"], emitted["business_id"]),
            )
    except db.IntegrityError:
        pass
    else:
        raise AssertionError("Se perdió la inmutabilidad fiscal durante el rollback.")
    print("PostgreSQL 55->54->53->54->55: datos e inmutabilidad conservados.")


def _privacy() -> None:
    business = db.create_business("Privacidad CI", "privacy-release@example.com")
    bid = business["id"]
    user = db.create_user("privacy-release@example.com", auth.hash_password(PASSWORD), bid)
    other = db.create_business("Otra cuenta CI", "other-release@example.com")
    db.update_fiscal(bid, nif="A12345678", address="Calle Prueba 1")  # pragma: allowlist secret
    customer = db.add_client(
        "Cliente CI", nif="B12345678", address="Calle Prueba 2", business_id=bid,  # pragma: allowlist secret
    )
    invoice = db.add_invoice(customer["id"], "Servicio de prueba", 100, business_id=bid)
    db.issue_invoice(invoice["id"], bid)
    with patch.object(server, "start_scheduler", lambda: None), TestClient(server.app) as http:
        response = http.post("/login", data={"email": user["email"], "password": PASSWORD})
        assert response.status_code == 200
        for _ in range(2):
            response = http.post(
                f"/b/{bid}/account/delete",
                data={"confirm": "BORRAR", "password": PASSWORD},
                follow_redirects=False,
            )
            assert response.status_code == 303, response.text
            assert "ok=baja-solicitada" in response.headers["location"]
        assert "Solicitud #" in http.get(f"/b/{bid}/ajustes").text
        assert http.get("/admin").status_code == 403
    requests = db.list_privacy_requests(business_id=bid)
    assert len(requests) == 1
    request = requests[0]
    assert request["retention_required"]
    assert not db.list_privacy_requests(business_id=other["id"])
    try:
        db.create_privacy_request(other["id"], requester_user_id=user["id"])
    except ValueError:
        pass
    else:
        raise AssertionError("Se permitió crear una solicitud para otra empresa.")

    def submit(_index):
        return db.create_privacy_request(bid, requester_user_id=user["id"])["id"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert set(pool.map(submit, range(8))) == {request["id"]}
    exported = db.export_business_data(bid)["privacy_requests"]
    assert len(exported) == 1 and "resolution_note" not in exported[0]
    notices = [
        r for r in db.list_email_messages(bid, limit=20)
        if str(r.get("idempotency_key") or "").startswith("privacy-request-")
    ]
    assert len(notices) == 1
    with db.get_conn() as conn:
        conn.execute("UPDATE users SET is_admin=TRUE WHERE id=?", (user["id"],))
    with patch.object(server, "start_scheduler", lambda: None), TestClient(server.app) as http:
        http.post("/login", data={"email": user["email"], "password": PASSWORD})
        assert "Privacidad y bajas" in http.get("/admin").text
        response = http.post(
            f"/admin/privacidad/{request['id']}/estado",
            data={"status": "legal_hold", "resolution_note": "Conservación fiscal de prueba."},
            follow_redirects=False,
        )
        assert response.status_code == 303
    assert db.list_privacy_requests(business_id=bid)[0]["status"] == "legal_hold"
    assert db.get_business(bid) and db.get_invoice(invoice["id"], bid)
    # La baja directa sigue disponible cuando no hay documentos protegidos.
    assert db.delete_business_cascade(other["id"])
    assert db.get_business(other["id"]) is None
    assert db.security_event_integrity()["ok"]
    print("Privacidad PostgreSQL: flujo HTTP, permisos, aislamiento, exportación y avisos OK.")


if __name__ == "__main__":
    _guard()
    _rollback()
    _privacy()
