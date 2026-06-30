"""Acceso a la tabla `documents`. SIEMPRE filtrado por business_id (aislamiento).

Solo toca la base de datos (metadatos). El fichero físico lo gestiona storage.py.
Import perezoso de db para no crear ciclos (db -> documents -> db).
"""

from __future__ import annotations

from datetime import datetime


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _conn():
    from .. import db
    return db.get_conn()


KINDS = {"documento", "ticket", "contrato", "proveedor"}


def add(business_id: int, *, filename: str, stored_name: str, mime: str, size: int,
        kind: str = "documento", client_id: int | None = None,
        invoice_id: int | None = None, ocr_text: str | None = None,
        ocr_amount: float | None = None, note: str | None = None) -> dict:
    kind = kind if kind in KINDS else "documento"
    with _conn() as conn:
        row = conn.execute(
            "INSERT INTO documents (business_id, client_id, invoice_id, kind, "
            "filename, stored_name, mime, size, ocr_text, ocr_amount, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (business_id, client_id, invoice_id, kind, filename, stored_name, mime,
             int(size), ocr_text, ocr_amount, note, _now()),
        ).fetchone()
        new_id = row["id"]
    return get(new_id, business_id)


def get(doc_id: int, business_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE id=? AND business_id=?",
            (doc_id, business_id)).fetchone()
        return dict(row) if row else None


def list_for_business(business_id: int, client_id: int | None = None) -> list[dict]:
    q = ("SELECT d.*, c.name AS client_name FROM documents d "
         "LEFT JOIN clients c ON c.id = d.client_id "
         "AND c.business_id=d.business_id WHERE d.business_id=?")
    params: list = [business_id]
    if client_id is not None:
        q += " AND d.client_id=?"
        params.append(client_id)
    q += " ORDER BY d.created_at DESC"
    with _conn() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def delete(doc_id: int, business_id: int) -> dict | None:
    """Borra el metadato y devuelve la fila borrada (para que storage borre el fichero)."""
    doc = get(doc_id, business_id)
    if not doc:
        return None
    with _conn() as conn:
        conn.execute("DELETE FROM documents WHERE id=? AND business_id=?",
                     (doc_id, business_id))
    return doc


# ------------------------------------------------------------------ RGPD ---
def export_for_business(business_id: int) -> list[dict]:
    """Metadatos de todos los documentos (para la exportación RGPD de la cuenta)."""
    return list_for_business(business_id)


def stored_names_for_client(business_id: int, client_id: int) -> list[str]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT stored_name FROM documents WHERE business_id=? AND client_id=?",
            (business_id, client_id)).fetchall()
    return [r["stored_name"] for r in rows]


def purge_for_client(business_id: int, client_id: int) -> None:
    """Borra los metadatos de los documentos de un cliente (derecho al olvido)."""
    with _conn() as conn:
        conn.execute("DELETE FROM documents WHERE business_id=? AND client_id=?",
                     (business_id, client_id))


def purge_for_business(business_id: int) -> None:
    """Borra los metadatos de TODOS los documentos de un negocio (baja de cuenta)."""
    with _conn() as conn:
        conn.execute("DELETE FROM documents WHERE business_id=?", (business_id,))
