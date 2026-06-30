"""Módulo de documentos ("papeles") de Noesis — AISLADO a propósito.

Todo lo relativo a los archivos que sube el autónomo (recibos, contratos, fotos de
tickets, facturas de proveedor) vive aquí, separado del resto, para que si algo
falla sea fácil de localizar:

  - schema.py   -> tabla `documents` (se engancha a db.init_db).
  - storage.py  -> guardar/leer/borrar el fichero físico en disco, por negocio.
  - repo.py     -> acceso a la tabla (CRUD + export/borrado RGPD), aislado por negocio.
  - ocr.py      -> leer el texto/importe de una foto (OCR), opcional y degradable.
  - service.py  -> orquestación de alto nivel (subir, extraer datos, pasar a gasto).

Punto de entrada que usa el servidor web: `service`. El resto del módulo solo se
relaciona con la base de datos a través de `db.get_conn()` (import perezoso) para no
crear ciclos de importación.
"""

from __future__ import annotations

from . import ocr, repo, service, storage  # noqa: F401
from .schema import ensure_schema  # noqa: F401

__all__ = ["ensure_schema", "service", "repo", "storage", "ocr"]
