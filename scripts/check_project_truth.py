"""Valida que el estado compartido no se separe del producto real.

El JSON es la fuente legible por máquinas. En pull requests, cualquier cambio de
código debe actualizar también esa foto y el registro de QA; los cambios de
arquitectura deben dejar además una decisión o actualizar el mapa de código.
"""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "docs" / "project-state.json"


def _fail(message: str) -> None:
    raise SystemExit(f"ERROR · verdad del proyecto: {message}")


def _changed_files(base_ref: str) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        line.strip().replace("\\", "/")
        for line in result.stdout.splitlines()
        if line.strip()
    }


def validate(base_ref: str = "") -> None:
    from noesis import migrations
    from noesis.adapters.billing import PLAN_PRICES

    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"no se puede leer {STATE_PATH.relative_to(ROOT)} ({exc}).")

    if state.get("schema_version") != migrations.LATEST_VERSION:
        _fail(
            "project-state.json declara migración "
            f"{state.get('schema_version')}, pero el código llega a "
            f"{migrations.LATEST_VERSION}."
        )
    if state.get("pricing_eur_ex_vat") != PLAN_PRICES:
        _fail(
            "los precios de project-state.json no coinciden con el catálogo de "
            f"código ({PLAN_PRICES})."
        )
    try:
        state_day = date.fromisoformat(str(state["state_date"]))
    except (KeyError, ValueError):
        _fail("state_date falta o no usa YYYY-MM-DD.")
    if state_day > date.today():
        _fail("state_date no puede estar en el futuro.")

    if not base_ref:
        return
    changed = _changed_files(base_ref)
    product_changes = {path for path in changed if path.startswith("src/noesis/")}
    if product_changes and "docs/project-state.json" not in changed:
        _fail(
            "este PR cambia el producto pero no docs/project-state.json. Actualiza "
            "la foto compartida aunque el cambio parezca pequeño."
        )
    if product_changes and "docs/Registro-QA.md" not in changed:
        _fail(
            "este PR cambia el producto pero no docs/Registro-QA.md. Registra qué "
            "se probó y qué no se pudo probar."
        )

    architecture_prefixes = (
        "src/noesis/db.py",
        "src/noesis/migrations.py",
        "src/noesis/agent.py",
        "src/noesis/internal_brain.py",
        "src/noesis/adapters/",
        "src/noesis/web/routers/",
        "src/noesis/web/deps.py",
    )
    architecture_changed = any(
        path == prefix or path.startswith(prefix)
        for path in changed
        for prefix in architecture_prefixes
    )
    architecture_docs = {
        "docs/Mapa-codigo.md",
        "docs/Arquitectura.md",
        "docs/Decisiones.md",
    }
    if architecture_changed and not changed.intersection(architecture_docs):
        _fail(
            "el PR cambia arquitectura pero no actualiza Mapa-codigo, Arquitectura "
            "ni Decisiones."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref", default="")
    args = parser.parse_args(argv)
    validate(args.base_ref.strip())
    print("OK · estado, esquema y precios están sincronizados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
