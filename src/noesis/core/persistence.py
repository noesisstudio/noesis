"""Vista exacta de una conexión prestada por db.get_conn().

El servicio posee la transacción; los futuros repositorios reciben esta vista
y business_id explícito. Esta infraestructura no decide permisos ni añade
filtros SQL: cada repositorio debe imponer el aislamiento de su dominio.
SQLite guarda dinero nuevo como TEXT canónico, nunca REAL/NUMERIC con afinidad
binaria; PostgreSQL usa NUMERIC. Las tablas legacy no se migran aquí.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..db import Connection, Cursor


def _check_exact(value) -> None:
    if isinstance(value, float):
        raise TypeError("El Financial Core no admite float; usa Decimal o texto canónico.")
    if isinstance(value, Decimal) and not value.is_finite():
        raise ValueError("El Financial Core no admite decimales no finitos.")
    if isinstance(value, dict):
        for item in value.values():
            _check_exact(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            _check_exact(item)


class _ExactCursor:
    def __init__(self, cursor: Cursor):
        self._cursor = cursor

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def fetchone(self):
        row = self._cursor.fetchone()
        _check_exact(row)
        return row

    def fetchall(self):
        rows = self._cursor.fetchall()
        _check_exact(rows)
        return rows


class FinancialSession:
    """No abre, confirma, revierte ni cierra conexiones; comparte su transacción."""

    def __init__(self, connection: Connection):
        self._connection = connection

    @property
    def dialect(self) -> str:
        return self._connection.dialect

    @property
    def borrowed_connection(self) -> Connection:
        """Frontera explícita con escritores legacy; no normalizar dinero nuevo."""
        return self._connection

    def execute(self, sql: str, params=()) -> _ExactCursor:
        params = tuple(params)
        _check_exact(params)
        return _ExactCursor(self._connection.execute_exact(sql, params))
