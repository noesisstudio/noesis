"""Lecturas y proveedor con la conexión del propietario; sin commit propio."""

from .. import db


def get_invoice(conn, invoice_id, business_id) -> dict | None:
    where = "i.id=? AND i.business_id=?"
    params = [invoice_id, business_id]
    row = conn.execute(
        "SELECT i.*, c.name AS client_name, COALESCE((SELECT SUM(p.amount) FROM invoice_payments p WHERE p.business_id=i.business_id AND p.invoice_id=i.id), 0) AS paid_amount FROM invoices i LEFT JOIN clients c ON c.id = i.client_id AND c.business_id=i.business_id WHERE "
        + where,
        params,
    ).fetchone()
    if not row:
        return None
    lines = conn.execute(
        "SELECT * FROM invoice_lines WHERE invoice_id=? AND business_id=? ORDER BY position, id",
        (invoice_id, business_id),
    ).fetchall()
    result = db._invoice_payment_state(row)
    result["lines"] = [dict(line) for line in lines]
    return result


def get_invoice_cancellation_record(conn, invoice_id: int, business_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM invoice_cancellation_records WHERE invoice_id=? AND business_id=?",
        (invoice_id, business_id),
    ).fetchone()
    return dict(row) if row else None


def get_client(conn, client_id, business_id) -> dict | None:
    sql = "SELECT * FROM clients WHERE id=? AND business_id=?"
    params = [client_id, business_id]
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def get_business(conn, business_id) -> dict | None:
    row = conn.execute("SELECT * FROM businesses WHERE id=?", (business_id,)).fetchone()
    return dict(row) if row else None


def get_project(conn, project_id, business_id):
    return conn.execute(
        "SELECT id FROM projects WHERE id=? AND business_id=?", (project_id, business_id)
    ).fetchone()


def get_received_invoice(conn, received_id, business_id) -> dict | None:
    row = conn.execute(
        "SELECT r.*, s.name AS supplier_name FROM received_invoices r LEFT JOIN suppliers s ON s.id=r.supplier_id AND s.business_id=r.business_id WHERE r.id=? AND r.business_id=?",
        (received_id, business_id),
    ).fetchone()
    return dict(row) if row else None


def get_bank_transaction(conn, transaction_id: int, business_id: int) -> dict | None:
    row = conn.execute(
        "SELECT bt.*, i.number AS invoice_number, i.total AS invoice_total, c.name AS client_name FROM bank_transactions bt LEFT JOIN invoices i ON i.id=bt.suggested_invoice_id AND i.business_id=bt.business_id LEFT JOIN clients c ON c.id=i.client_id AND c.business_id=i.business_id WHERE bt.id=? AND bt.business_id=?",
        (transaction_id, business_id),
    ).fetchone()
    return dict(row) if row else None


def find_supplier(conn, business_id, *, nif=None, name=None) -> dict | None:
    """Busca proveedor por NIF (prioritario) o por nombre, para no duplicar.

    El nombre se compara plegado: quien dicta «materiales sol» se refiere al
    «Materiales Sol» que ya tiene ficha. Comparar exacto creaba un proveedor
    nuevo por cada forma de escribirlo.
    """
    nif = db._clean_nif(nif)
    if nif:
        row = conn.execute(
            "SELECT * FROM suppliers WHERE business_id=? AND nif=?", (business_id, nif)
        ).fetchone()
        if row:
            return dict(row)
    row = db._find_supplier_row_by_name(conn, business_id, (name or "").strip())
    if row:
        return dict(row)
    return None


def add_supplier(
    conn, name, nif=None, email=None, phone=None, note=None, *, business_id: int
) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("El nombre del proveedor es obligatorio.")
    db._valid_party_name(name, "proveedor")
    if len(name) > 200:
        raise ValueError("El nombre del proveedor es demasiado largo (máx. 200).")
    nif = db._clean_nif(nif)
    existing = db._find_supplier_row_by_name(conn, business_id, name)
    if existing:
        raise ValueError("Ya existe un proveedor con ese nombre.")
    row = conn.execute(
        "INSERT INTO suppliers (business_id, name, nif, email, phone, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id",
        (
            business_id,
            name,
            nif,
            (email or "").strip() or None,
            (phone or "").strip() or None,
            (note or "").strip() or None,
            db._now(),
        ),
    ).fetchone()
    return dict(
        conn.execute(
            "SELECT * FROM suppliers WHERE id=? AND business_id=?", (row["id"], business_id)
        ).fetchone()
    )
