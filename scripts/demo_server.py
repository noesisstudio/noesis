"""Arranca Noesis con el negocio de demostración cargado, en una base aparte.

Uso:  python scripts/demo_server.py   (o el lanzador «noesis-demo» del editor)

Usa una base propia (``noesis-demo.db``, ignorada por git) para no tocar tu base
de desarrollo. Si está vacía, la siembra con ``demo.seed_rich``. Login:
demo@noesis.app / demo1234.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# La ruta de la BD debe fijarse ANTES de importar config.
os.environ.setdefault("NOESIS_DB_PATH", str(ROOT / "noesis-demo.db"))
os.environ.setdefault("NOESIS_DOCS_PATH", str(ROOT / "uploads-demo"))
os.environ.setdefault("NOESIS_SECRET", "demo-secret-solo-local")

sys.path.insert(0, str(ROOT / "src"))

from noesis import db, demo  # noqa: E402


def main() -> None:
    db.init_db()
    if not db.list_businesses():
        info = demo.seed_rich(reset=False)
        print(f"Demo sembrado. Login: {info['email']} / {info['password']}")
    else:
        print("Ya había datos; arrancando sin re-sembrar. "
              "Borra noesis-demo.db para empezar de cero.")

    import uvicorn

    port = int(os.environ.get("PORT", "8014"))
    uvicorn.run("noesis.web.server:app", host="127.0.0.1", port=port, reload=False)


if __name__ == "__main__":
    main()
