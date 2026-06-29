"""Esquema de la tabla `documents`. Se aplica desde db.init_db (idempotente)."""

from __future__ import annotations

import sqlite3

# Cada documento pertenece a UN negocio (aislamiento) y, opcionalmente, va ligado a
# un cliente o a una factura. El fichero físico se guarda en disco (ver storage.py);
# aquí solo se guardan los metadatos y el texto extraído por OCR.
SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id  INTEGER NOT NULL,
    client_id    INTEGER,                              -- opcional: papel de un cliente
    invoice_id   INTEGER,                              -- opcional: papel de una factura
    kind         TEXT NOT NULL DEFAULT 'documento',    -- documento|ticket|contrato|proveedor
    filename     TEXT NOT NULL,                        -- nombre original (mostrar)
    stored_name  TEXT NOT NULL,                        -- nombre en disco (uuid, no adivinable)
    mime         TEXT,
    size         INTEGER NOT NULL DEFAULT 0,
    ocr_text     TEXT,                                 -- texto leído de la imagen (opcional)
    ocr_amount   REAL,                                 -- importe detectado (opcional)
    note         TEXT,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_business ON documents(business_id);
CREATE INDEX IF NOT EXISTS idx_documents_client   ON documents(business_id, client_id);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Crea la tabla de documentos si no existe. Llamado desde db.init_db()."""
    conn.executescript(SCHEMA)
