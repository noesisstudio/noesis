"""Esquema de la migración 74: tipo de contacto, datos de la hoja y conexión.

`migrations.py` solo la registra; lo que crea está aquí, junto al código que lo
usa. Es aditiva: el código anterior no lee ninguna de estas columnas.
"""
from __future__ import annotations


def upgrade(conn) -> None:
    """Captación: a quién perseguimos (tipo), dónde está y de qué hoja viene.

    La lista de gestorías vive en una hoja de Google que ya se usa para trabajar.
    En vez de copiarla una vez y dejar dos listas que se separan, la ficha recuerda
    de qué hoja y de qué fila salió (`hoja_id`, `hoja_clave`): así una segunda
    lectura actualiza los datos de contacto sin tocar lo que es del CRM (estado,
    historial, nota, baja).

    `tipo` se separa de `origen` porque no son lo mismo: una gestoría encontrada
    en su web y un fontanero encontrado en su web comparten origen, pero no
    embudo, ni guion, ni objetivo.

    `sales_feeds` guarda solo la huella del enlace por el que la hoja lee el estado
    del CRM: quien tenga acceso a la base no puede reconstruir el enlace.
    """
    from ..migrations import _column_names, _types

    t = _types(conn.dialect)
    columnas = _column_names(conn, "sales_prospects")
    for nombre, definicion in (
            ("tipo", "TEXT NOT NULL DEFAULT 'autonomo'"),
            ("provincia", "TEXT"),
            ("direccion", "TEXT"),
            ("web", "TEXT"),
            ("hoja_id", t["ref"]),
            ("hoja_clave", "TEXT"),
            ("hoja_estado", "TEXT"),
            ("correo_verificacion", "TEXT"),
            ("hoja_vista_el", "TEXT")):
        if nombre not in columnas:
            conn.execute(
                f"ALTER TABLE sales_prospects ADD COLUMN {nombre} {definicion}")
    # Quien ya estaba en la lista como gestoría, gremio o almacén lo estaba por el
    # origen: era la única forma de decirlo. Se traduce una vez para no perderlo.
    for tipo in ("gestoria", "gremio", "almacen"):
        conn.execute(
            "UPDATE sales_prospects SET tipo=? WHERE origen=? AND tipo='autonomo'",
            (tipo, tipo))
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sales_prospects_tipo "
        "ON sales_prospects(tipo, estado)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sales_prospects_hoja "
        "ON sales_prospects(hoja_id, hoja_clave)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sales_sheets ("
        f"id {t['id']}, "
        "nombre TEXT NOT NULL, "
        "url TEXT NOT NULL, "
        "tipo TEXT NOT NULL DEFAULT 'gestoria', "
        "origen TEXT NOT NULL DEFAULT 'web', "
        f"activa {t['boolean']} NOT NULL DEFAULT TRUE, "
        f"ultima_lectura {t['timestamp']}, "
        "ultimo_estado TEXT, "
        "ultimo_error TEXT, "
        "filas INTEGER NOT NULL DEFAULT 0, "
        "nuevas INTEGER NOT NULL DEFAULT 0, "
        "actualizadas INTEGER NOT NULL DEFAULT 0, "
        f"created_at {t['timestamp']} NOT NULL, "
        f"updated_at {t['timestamp']})"
    )
    # Quien pidió que se le borrase no puede volver a entrar en la siguiente
    # lectura de la hoja. Se guarda una huella de su correo o teléfono, no el
    # dato: sirve para reconocerlo si vuelve, no para saber quién era.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sales_suppressions ("
        "huella TEXT PRIMARY KEY, "
        f"created_at {t['timestamp']} NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sales_feeds ("
        "clave TEXT PRIMARY KEY, "
        "token_hash TEXT NOT NULL, "
        f"created_at {t['timestamp']} NOT NULL, "
        f"leido_el {t['timestamp']})"
    )


def downgrade(conn) -> None:
    if conn.execute("SELECT huella FROM sales_suppressions LIMIT 1").fetchone():
        # Sin esta tabla, el código anterior no sabría a quién no readmitir.
        raise ValueError("Hay contactos borrados a petición suya: la migración "
                         "74 no se revierte mientras exista esa lista.")
    conn.execute("DROP TABLE IF EXISTS sales_suppressions")
    conn.execute("DROP TABLE IF EXISTS sales_feeds")
    conn.execute("DROP TABLE IF EXISTS sales_sheets")
    conn.execute("DROP INDEX IF EXISTS idx_sales_prospects_hoja")
    conn.execute("DROP INDEX IF EXISTS idx_sales_prospects_tipo")
    # Las columnas son aditivas y el código anterior no las lee. En SQLite se
    # conservan (volver a subir no las duplica); en Postgres se retiran.
    if conn.dialect != "sqlite":
        for nombre in ("hoja_vista_el", "correo_verificacion", "hoja_estado",
                       "hoja_clave", "hoja_id", "web", "direccion", "provincia",
                       "tipo"):
            conn.execute(
                f"ALTER TABLE sales_prospects DROP COLUMN IF EXISTS {nombre}")
