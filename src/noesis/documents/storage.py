"""Almacenamiento físico de los documentos en disco, aislado por negocio.

Estructura:  {DOCS_PATH}/{business_id}/{stored_name}

Reglas de seguridad:
  - El nombre en disco SIEMPRE es un uuid generado por nosotros (nunca el nombre que
    manda el usuario), así no hay forma de salirse de la carpeta (path traversal).
  - Cada negocio tiene su subcarpeta: el aislamiento existe también a nivel de disco.
  - Allowlist de tipos: solo PDF e imágenes (los "papeles" reales de un autónomo).
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from .. import config

# Tipos permitidos: extensión -> mime. Lo que no esté aquí se rechaza.
ALLOWED: dict[str, str] = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


def _business_dir(business_id: int) -> Path:
    d = Path(config.DOCS_PATH) / str(int(business_id))
    d.mkdir(parents=True, exist_ok=True)
    return d


def ext_of(filename: str) -> str:
    """Extensión en minúsculas (con punto), o cadena vacía."""
    return Path(filename or "").suffix.lower()


def is_allowed(filename: str) -> bool:
    return ext_of(filename) in ALLOWED


def mime_for(filename: str) -> str:
    return ALLOWED.get(ext_of(filename), "application/octet-stream")


def save(business_id: int, filename: str, data: bytes) -> str:
    """Guarda los bytes en disco y devuelve el `stored_name` (uuid+ext)."""
    ext = ext_of(filename)
    stored = f"{uuid.uuid4().hex}{ext}"
    path = _business_dir(business_id) / stored
    path.write_bytes(data)
    return stored


def path_for(business_id: int, stored_name: str) -> Path:
    """Ruta absoluta de un fichero. Valida que `stored_name` no escape la carpeta."""
    base = _business_dir(business_id).resolve()
    target = (base / stored_name).resolve()
    if base not in target.parents:
        raise ValueError("Nombre de archivo no válido.")
    return target


def read(business_id: int, stored_name: str) -> bytes | None:
    try:
        path = path_for(business_id, stored_name)
    except ValueError:
        return None
    return path.read_bytes() if path.exists() else None


def delete(business_id: int, stored_name: str) -> None:
    try:
        path = path_for(business_id, stored_name)
    except ValueError:
        return
    path.unlink(missing_ok=True)


def delete_business_dir(business_id: int) -> None:
    """Borra TODA la carpeta de archivos de un negocio (baja RGPD de la cuenta)."""
    d = Path(config.DOCS_PATH) / str(int(business_id))
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
