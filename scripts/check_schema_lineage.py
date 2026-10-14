"""Gate append-only de catálogo/DDL contra main autorizado, sin importar su código."""

import argparse
import ast
from pathlib import Path
import subprocess

from noesis.schema_lineage import CATALOG, IMPLEMENTED_LATEST

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZED_MAIN = "678bd3fdf2f9891b373b0fe8d46ac37b97f0310d"  # pragma: allowlist secret; approved public main SHA
SOURCE = "src/noesis/migrations.py"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode("utf-8")


def catalog(source):
    module = ast.parse(source)
    entries = next(n.value for n in module.body if isinstance(n, ast.AnnAssign)
                   and isinstance(n.target, ast.Name) and n.target.id == "MIGRATIONS")
    pairs, callbacks = [], []
    for row in entries.elts:
        if not isinstance(row, ast.Tuple) or len(row.elts) != 4:
            raise ValueError("MIGRATION_IDENTITY_MISMATCH")
        version, name, up, down = row.elts
        if (not isinstance(version, ast.Constant) or type(version.value) is not int
                or not isinstance(name, ast.Constant) or type(name.value) is not str
                or not isinstance(up, ast.Name) or not isinstance(down, ast.Name)):
            raise ValueError("MIGRATION_IDENTITY_MISMATCH")
        pairs.append((version.value, name.value))
        callbacks.append((up.id, down.id))
    if (len({v for v, _ in pairs}) != len(pairs) or len({n for _, n in pairs}) != len(pairs)
            or tuple(v for v, _ in pairs) != tuple(range(1, len(pairs) + 1))):
        raise ValueError("MIGRATION_COLLISION_OR_GAP")
    definitions = {n.name: ast.dump(n, include_attributes=False) for n in module.body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return tuple(pairs), tuple(callbacks), definitions


def validate(candidate, baseline, current_main):
    pairs, callbacks, definitions = catalog(candidate)
    old_pairs, old_callbacks, old_definitions = catalog(baseline)
    main_pairs, _, _ = catalog(current_main)
    if main_pairs != old_pairs:
        raise ValueError("MIGRATION_PLAN_STALE")
    if pairs[:len(old_pairs)] != old_pairs or callbacks[:len(old_pairs)] != old_callbacks:
        raise ValueError("HISTORICAL_MIGRATION_CHANGED")
    allowed_infrastructure = {"upgrade_connection", "upgrade", "downgrade", "is_current"}
    for name, definition in old_definitions.items():
        if name not in allowed_infrastructure and definitions.get(name) != definition:
            raise ValueError("HISTORICAL_DDL_CHANGED")
    for pair in old_callbacks:
        for name in pair:
            if definitions.get(name) != old_definitions.get(name):
                raise ValueError("HISTORICAL_DDL_CHANGED")
    if (pairs != CATALOG or len(pairs) != IMPLEMENTED_LATEST or old_pairs[-1] !=
            (74, "captacion_hoja_y_tipo") or pairs[74:] != ((75, "evaluacion_readiness_financiera"),)):
        raise ValueError("MIGRATION_IDENTITY_MISMATCH")
    return pairs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--main-ref", default="origin/main")
    args = parser.parse_args()
    baseline = git("show", f"{AUTHORIZED_MAIN}:{SOURCE}")
    current_main = git("show", f"{args.main_ref}:{SOURCE}")
    pairs = validate((ROOT / SOURCE).read_text(encoding="utf-8"), baseline, current_main)
    names = git("ls-tree", "-r", "--name-only", AUTHORIZED_MAIN, "src/noesis").splitlines()
    for name in names:
        if name.endswith(("/schema.py", "_schema.py")) or name == "src/noesis/crm/esquema.py":
            if (ROOT / name).read_text(encoding="utf-8") != git("show", f"{AUTHORIZED_MAIN}:{name}"):
                raise SystemExit("HISTORICAL_DDL_CHANGED: " + name)
    print(f"PASS: {len(pairs)} identidades únicas; CRM74 intacta; A75 append-only; callbacks/DDL históricos conservados.")


if __name__ == "__main__":
    main()
