"""Regresión PostgreSQL: migrar una factura emitida real de esquema 32 a 35."""

from __future__ import annotations

from datetime import datetime
import sys
import traceback

from noesis import config, db, migrations


ISSUER_NIF = "A12345678"  # pragma: allowlist secret
CLIENT_NIF = "B12345678"  # pragma: allowlist secret


def main() -> int:
    try:
        if not config.DATABASE_URL:
            raise RuntimeError("Este smoke exige DATABASE_URL.")
        if migrations.current_version() != 32:
            raise RuntimeError("El smoke debe empezar exactamente en esquema 32.")

        now = datetime.now().isoformat(timespec="seconds")
        with db.get_conn() as conn:
            business = conn.execute(
                "INSERT INTO businesses (name, owner_email, sector, created_at) "
                "VALUES (?, ?, ?, ?) RETURNING id",
                ("Migración histórica", "migration@example.com", "Servicios", now),
            ).fetchone()
            client = conn.execute(
                "INSERT INTO clients "
                "(business_id, name, nif, address, created_at) "
                "VALUES (?, ?, ?, ?, ?) RETURNING id",
                (
                    business["id"], "Cliente histórico", CLIENT_NIF,
                    "Calle Cliente 1", now,
                ),
            ).fetchone()
            invoice = conn.execute(
                "INSERT INTO invoices "
                "(business_id, number, client_id, concept, base, vat_rate, "
                "vat_amount, irpf_rate, irpf_amount, total, status, issued_at, "
                "issuer_name, issuer_nif, issuer_address, recipient_name, "
                "recipient_nif, recipient_address, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "RETURNING id",
                (
                    business["id"], "2026/0001", client["id"],
                    "Servicio histórico", 100, 21, 21, 0, 0, 121, "emitida", now,
                    "Migración histórica", ISSUER_NIF, "Calle Negocio 1",
                    "Cliente histórico", CLIENT_NIF, "Calle Cliente 1", now,
                ),
            ).fetchone()

        if migrations.upgrade() != migrations.LATEST_VERSION:
            raise RuntimeError("La migración no alcanzó el esquema actual.")

        with db.get_conn() as conn:
            migrated = conn.execute(
                "SELECT series_id FROM invoices WHERE id=? AND business_id=?",
                (invoice["id"], business["id"]),
            ).fetchone()
            lines = conn.execute(
                "SELECT COUNT(*) AS total FROM invoice_lines "
                "WHERE invoice_id=? AND business_id=?",
                (invoice["id"], business["id"]),
            ).fetchone()
        if not migrated or migrated["series_id"] is None or lines["total"] != 1:
            raise RuntimeError("La factura histórica no recibió serie y línea.")

        try:
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE invoices SET concept='Alteración' "
                    "WHERE id=? AND business_id=?",
                    (invoice["id"], business["id"]),
                )
        except db.IntegrityError:
            pass
        else:
            raise RuntimeError("El guardián no se reinstaló tras el backfill.")
    except Exception as exc:  # noqa: BLE001 - CI debe mostrar el fallo exacto.
        traceback.print_exception(type(exc), exc, exc.__traceback__)
        return 1

    print("Migración PostgreSQL 32 -> 35 con factura emitida: OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
