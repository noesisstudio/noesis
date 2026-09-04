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


KINDS = {"documento", "ticket", "contrato", "proveedor", "albaran",
         "factura_emitida", "factura_recibida", "presupuesto"}
# Ciclo de revisión: pendiente_revisar -> revisado -> enviado_gestoria ->
# validado; además rechazado y duplicado. Los históricos nacen 'revisado'.
DOC_STATUSES = {"pendiente_revisar", "revisado", "enviado_gestoria",
                "validado", "rechazado", "duplicado"}


def add(business_id: int, *, filename: str, stored_name: str, mime: str, size: int,
        kind: str = "documento", client_id: int | None = None,
        invoice_id: int | None = None, project_id: int | None = None,
        ocr_text: str | None = None,
        ocr_amount: float | None = None, note: str | None = None,
        doc_status: str = "revisado", confidence: float | None = None,
        content_sha256: str | None = None) -> dict:
    kind = kind if kind in KINDS else "documento"
    doc_status = doc_status if doc_status in DOC_STATUSES else "revisado"
    with _conn() as conn:
        row = conn.execute(
            "INSERT INTO documents (business_id, client_id, invoice_id, project_id, kind, "
            "filename, stored_name, mime, size, ocr_text, ocr_amount, note, "
            "doc_status, confidence, content_sha256, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (business_id, client_id, invoice_id, project_id, kind, filename, stored_name, mime,
             int(size), ocr_text, ocr_amount, note, doc_status, confidence,
             content_sha256, _now()),
        ).fetchone()
        new_id = row["id"]
    return get(new_id, business_id)


def find_by_content_hash(business_id: int, content_sha256: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE business_id=? AND content_sha256=? "
            "ORDER BY id LIMIT 1",
            (business_id, content_sha256),
        ).fetchone()
    return dict(row) if row else None


def legacy_hash_candidates(business_id: int, size: int) -> list[dict]:
    """Históricos sin huella que pueden coincidir; el contenido decide después."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM documents WHERE business_id=? AND size=? "
            "AND content_sha256 IS NULL ORDER BY id",
            (business_id, int(size)),
        ).fetchall()
    return [dict(row) for row in rows]


def set_content_hash(doc_id: int, business_id: int, content_sha256: str) -> dict | None:
    with _conn() as conn:
        conn.execute(
            "UPDATE documents SET content_sha256=? "
            "WHERE id=? AND business_id=? AND content_sha256 IS NULL",
            (content_sha256, doc_id, business_id),
        )
    return get(doc_id, business_id)


def set_review(doc_id: int, business_id: int, *, kind: str | None = None,
               doc_status: str | None = None, confidence: float | None = None,
               review_note: str | None = None) -> dict | None:
    """Actualiza la revisión de un documento (tipo, estado, nota). Trazable:
    siempre sella reviewed_at. Devuelve el documento actualizado o None."""
    updates: list[str] = ["reviewed_at=?"]
    params: list = [_now()]
    if kind is not None:
        if kind not in KINDS:
            raise ValueError("Tipo de documento desconocido.")
        updates.append("kind=?")
        params.append(kind)
    if doc_status is not None:
        if doc_status not in DOC_STATUSES:
            raise ValueError("Estado de documento desconocido.")
        updates.append("doc_status=?")
        params.append(doc_status)
    if confidence is not None:
        updates.append("confidence=?")
        params.append(float(confidence))
    if review_note is not None:
        updates.append("review_note=?")
        params.append(review_note.strip()[:500] or None)
    params.extend([doc_id, business_id])
    with _conn() as conn:
        conn.execute(
            f"UPDATE documents SET {', '.join(updates)} "
            "WHERE id=? AND business_id=?", params)
    return get(doc_id, business_id)


def set_context(doc_id: int, business_id: int, *,
                client_id: int | None = None,
                project_id: int | None = None) -> dict | None:
    """Asocia cliente/proyecto sin permitir referencias de otro negocio."""
    from .. import db

    document = get(doc_id, business_id)
    if not document:
        return None
    project = None
    if project_id not in (None, ""):
        project = db.get_project(int(project_id), business_id)
        if not project:
            raise ValueError("El proyecto no pertenece a este negocio.")
        project_id = int(project_id)
        project_client_id = project.get("client_id")
        if client_id in (None, "") and project_client_id:
            client_id = int(project_client_id)
        elif client_id not in (None, "") and project_client_id not in (None, int(client_id)):
            raise ValueError("El cliente no coincide con el proyecto.")
    else:
        project_id = None
    if client_id not in (None, ""):
        client_id = int(client_id)
        if not db.get_client(client_id, business_id):
            raise ValueError("El cliente no pertenece a este negocio.")
    else:
        client_id = None
    with _conn() as conn:
        conn.execute(
            "UPDATE documents SET client_id=?, project_id=? "
            "WHERE id=? AND business_id=?",
            (client_id, project_id, doc_id, business_id),
        )
    return get(doc_id, business_id)


def record_classification(
    doc_id: int,
    business_id: int,
    *,
    detected_kind: str,
    confidence: float | None,
    method: str,
    reason: str | None = None,
) -> dict | None:
    """Registra una propuesta sin borrar intentos anteriores."""
    if detected_kind not in KINDS or not get(doc_id, business_id):
        return None
    with _conn() as conn:
        row = conn.execute(
            "INSERT INTO document_classifications "
            "(business_id, document_id, detected_kind, confidence, method, "
            "reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (business_id, doc_id, detected_kind, confidence,
             (method or "heuristica")[:30], (reason or "")[:500] or None, _now()),
        ).fetchone()
        saved = conn.execute(
            "SELECT * FROM document_classifications WHERE id=? AND business_id=?",
            (row["id"], business_id),
        ).fetchone()
    return dict(saved)


def confirm_classification(
    doc_id: int, business_id: int, confirmed_kind: str
) -> dict | None:
    """Confirma la última propuesta y conserva la corrección como aprendizaje."""
    if confirmed_kind not in KINDS:
        raise ValueError("Tipo de documento desconocido.")
    with _conn() as conn:
        row = conn.execute(
            "SELECT id FROM document_classifications WHERE business_id=? "
            "AND document_id=? ORDER BY id DESC LIMIT 1",
            (business_id, doc_id),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE document_classifications SET confirmed_kind=?, confirmed_at=? "
            "WHERE id=? AND business_id=?",
            (confirmed_kind, _now(), row["id"], business_id),
        )
        saved = conn.execute(
            "SELECT * FROM document_classifications WHERE id=? AND business_id=?",
            (row["id"], business_id),
        ).fetchone()
    result = dict(saved)
    from .. import value_ledger
    value_ledger.observe_useful_action(
        business_id,
        "document_classification_confirmed",
        entity_type="document",
        entity_id=doc_id,
        idempotency_key=f"document_classification:{row['id']}",
        metadata={
            "detected_kind": result.get("detected_kind"),
            "confirmed_kind": confirmed_kind,
            "corrected": result.get("detected_kind") != confirmed_kind,
        },
    )
    return result


def latest_classification(doc_id: int, business_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM document_classifications WHERE business_id=? "
            "AND document_id=? ORDER BY id DESC LIMIT 1",
            (business_id, doc_id),
        ).fetchone()
    return dict(row) if row else None


def list_pending_review(business_id: int) -> list[dict]:
    with _conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM documents WHERE business_id=? "
            "AND doc_status='pendiente_revisar' ORDER BY created_at DESC",
            (business_id,)).fetchall()]


def get(doc_id: int, business_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE id=? AND business_id=?",
            (doc_id, business_id)).fetchone()
        return dict(row) if row else None


def list_for_business(
    business_id: int,
    client_id: int | None = None,
    *,
    search: str | None = None,
) -> list[dict]:
    q = ("SELECT d.*, c.name AS client_name, p.name AS project_name, "
         "dc.proposed_name AS proposed_client_name, "
         "dc.proposed_nif AS proposed_client_nif, "
         "dc.status AS proposed_client_status "
         "FROM documents d "
         "LEFT JOIN clients c ON c.id = d.client_id "
         "AND c.business_id=d.business_id "
         "LEFT JOIN projects p ON p.id=d.project_id "
         "AND p.business_id=d.business_id "
         "LEFT JOIN document_client_candidates dc ON dc.document_id=d.id "
         "AND dc.business_id=d.business_id WHERE d.business_id=?")
    params: list = [business_id]
    if client_id is not None:
        q += " AND d.client_id=?"
        params.append(client_id)
    term = (search or "").strip().lower()[:120]
    if term:
        like = f"%{term}%"
        kind_like = f"%{term.replace(' ', '_')}%"
        q += (
            " AND (LOWER(COALESCE(d.filename, '')) LIKE ? "
            "OR LOWER(COALESCE(d.note, '')) LIKE ? "
            "OR LOWER(COALESCE(d.ocr_text, '')) LIKE ? "
            "OR LOWER(COALESCE(c.name, '')) LIKE ? "
            "OR LOWER(COALESCE(p.name, '')) LIKE ? "
            "OR LOWER(COALESCE(d.kind, '')) LIKE ?)"
        )
        params.extend([like, like, like, like, like, kind_like])
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
