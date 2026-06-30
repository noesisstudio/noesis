"""Copias locales de SQLite.

Cada copia se hace con la API de backup de SQLite (consistente aunque la app esté
escribiendo) en una carpeta `backups/` junto a la base de datos —que en producción
vive en el volumen persistente—. Se conservan las últimas N y se borran las viejas.

Es una red de seguridad básica pero real: si el archivo principal se corrompe,
hay una copia reciente. Para catástrofe total del volumen conviene, más adelante,
subir estas copias fuera (S3/Backblaze); el punto de enganche es `run_backup`.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from .. import config

log = logging.getLogger("noesis.backups")
KEEP = 14  # copias diarias conservadas (~2 semanas)


def _backup_dir() -> Path:
    d = Path(config.BACKUP_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def run_backup() -> Path | None:
    if config.DATABASE_URL:
        # Postgres usa las copias gestionadas del proveedor. No se intenta volcar una
        # base remota desde el proceso web.
        return None
    src = Path(config.DB_PATH)
    if not src.exists():
        return None
    dest = _backup_dir() / f"noesis-{datetime.now():%Y%m%d-%H%M%S}.db"
    try:
        with sqlite3.connect(str(src)) as source, sqlite3.connect(str(dest)) as target:
            source.backup(target)
        _rotate()
        log.info("Copia de seguridad creada: %s", dest.name)
        return dest
    except Exception as e:  # noqa: BLE001
        log.error("Fallo creando copia de seguridad: %s", e)
        return None


def _rotate() -> None:
    copies = sorted(_backup_dir().glob("noesis-*.db"))
    for old in copies[:-KEEP]:
        try:
            old.unlink()
        except OSError:
            pass
