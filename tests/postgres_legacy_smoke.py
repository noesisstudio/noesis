"""Comprueba el código base sobre esquema nuevo antes de bajar la base efímera."""

import json
from pathlib import Path
from urllib.parse import urlsplit

from noesis import config, db, migrations


if __name__ == "__main__":
    url = urlsplit(config.DATABASE_URL)
    if url.hostname not in {"localhost", "127.0.0.1", "::1"} or url.path != "/noesis_ci":
        raise RuntimeError("Solo se admite la base PostgreSQL descartable del CI.")
    assert not config.IS_PRODUCTION
    assert migrations.LATEST_VERSION == 53, "Debe importar el código base, no el candidato."
    expected_schema = json.loads(
        (Path(__file__).resolve().parents[1] / "docs/project-state.json").read_text(encoding="utf-8")
    )["schema_version"]
    assert migrations.current_version() == expected_schema
    business = db.create_business("Código anterior CI", "legacy-ci@example.com")
    bid = business["id"]
    db.update_fiscal(bid, nif="A12345678", address="Calle Prueba 1")  # pragma: allowlist secret
    client = db.add_client(
        "Cliente anterior", nif="B12345678", address="Calle Prueba 2", business_id=bid,  # pragma: allowlist secret
    )
    invoice = db.add_invoice(client["id"], "Factura con código anterior", 100, business_id=bid)
    invoice = db.issue_invoice(invoice["id"], bid)
    assert invoice["status"] == "enviada"
    payment = db.add_invoice_payment(invoice["id"], 50, business_id=bid)
    assert payment["amount"] == 50
    assert db.invoice_paid_amount(invoice["id"], bid) == 50
    assert db.export_business_data(bid)["business"]["id"] == bid
    assert migrations.current_version() == expected_schema
    print(f"Código base esquema 53 sobre BD {expected_schema}: cliente, factura, emisión, cobro y exportación OK.")
