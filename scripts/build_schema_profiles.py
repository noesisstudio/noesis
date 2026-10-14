"""Construcción deliberada de perfiles en fixtures vacíos; no acepta DSN del usuario.

No se ejecuta en startup ni CI para reparar expectativas. El resultado versionado
se revisa junto a callbacks/contrato y CI sólo lo verifica, nunca lo regenera.
"""

import argparse
from pathlib import Path
import json
import sqlite3

from noesis import db, migrations
from noesis.schema_objects import physical_objects


def collect(conn):
    migrations._ensure_version_table(conn)
    previous = physical_objects(conn)
    result = {"0": {"set": previous, "remove": []}}
    for version, name, apply, _ in migrations.MIGRATIONS:
        apply(conn)
        conn.execute("INSERT INTO schema_migrations VALUES (?,?,?)",
                     (version, name, "2026-10-13T00:00:00+00:00"))
        current = physical_objects(conn)
        result[str(version)] = {"set": {key: value for key, value in current.items()
                                        if previous.get(key) != value},
                                "remove": sorted(set(previous) - set(current))}
        previous = current
    return result


def collect_synthetic_owner_variants():
    """Recorridos legacy cerrados; describen fixtures, jamás un perfil runtime."""
    variants = {}
    targets = (1, 10, 16, 18, 25, 46, 53, 54, 55, 57, 58, 62, 63, 64, 65, 66, 67, 68, 69)
    for target in targets:
        with sqlite3.connect(":memory:") as raw:
            raw.row_factory = sqlite3.Row
            raw.execute("PRAGMA foreign_keys=ON")
            raw.execute("BEGIN IMMEDIATE")
            conn = db.Connection(raw, "sqlite")
            deltas = collect(conn)
            expected, compiled = {}, {}
            for stage in range(76):
                for key in deltas[str(stage)]["remove"]:
                    expected.pop(key)
                expected.update(deltas[str(stage)]["set"])
                compiled[stage] = dict(expected)
            def record(stage):
                actual = physical_objects(conn)
                expected = compiled[stage]
                delta = {"set": {key: value for key, value in actual.items() if expected.get(key) != value},
                         "remove": sorted(set(expected) - set(actual))}
                if delta["set"] or delta["remove"]:
                    entries = variants.setdefault(str(stage), [])
                    if delta not in entries:
                        entries.append(delta)
            for version, _name, _apply, revert in reversed(migrations.MIGRATIONS):
                if version > target:
                    revert(conn)
                    conn.execute("DELETE FROM schema_migrations WHERE version=?", (version,))
                    record(version - 1)
            for version, name, apply, _revert in migrations.MIGRATIONS:
                if version > target:
                    apply(conn)
                    conn.execute("INSERT INTO schema_migrations VALUES (?,?,?)",
                                 (version, name, "2026-10-13T00:00:00+00:00"))
                    record(version)
    return variants


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--postgres", action="store_true")
    parser.add_argument("--synthetic-owner-variants", action="store_true")
    args = parser.parse_args()
    destination = Path(__file__).resolve().parents[1] / "src/noesis/core/schema_object_profiles.json"
    profiles = json.loads(destination.read_text(encoding="utf-8")) if destination.exists() else {
        "format": "noesis.schema-objects.v1", "profiles": {"sqlite": {}, "postgres": {}}}
    if args.synthetic_owner_variants:
        if args.postgres:
            raise SystemExit("Variantes técnicas exclusivamente SQLite sintética")
        profiles["synthetic_sqlite_owner_variants"] = collect_synthetic_owner_variants()
        destination.write_text(json.dumps(profiles, ensure_ascii=False, sort_keys=True, indent=2)
                               + "\n", encoding="utf-8")
        print("Variantes técnicas SQLite sintéticas generadas; sin permiso de serving")
        return
    if args.postgres:
        from noesis.web.postgres_backup_tools import disposable_target, outbound_blocked
        if not outbound_blocked():
            raise SystemExit("Sólo fixture propio no root en namespace sin outbound.")
        with disposable_target() as target:
            with target.connection() as raw:
                from psycopg.rows import dict_row
                raw.row_factory = dict_row
                profiles["profiles"]["postgres"] = collect(db.Connection(raw, "postgres"))
    else:
        with sqlite3.connect(":memory:") as raw:
            raw.row_factory = sqlite3.Row
            raw.execute("PRAGMA foreign_keys=ON")
            raw.execute("BEGIN IMMEDIATE")
            profiles["profiles"]["sqlite"] = collect(db.Connection(raw, "sqlite"))
    destination.write_text(json.dumps(profiles, ensure_ascii=False, sort_keys=True, indent=2)
                           + "\n", encoding="utf-8")
    print("Perfiles sintéticos generados: " + ("PostgreSQL18" if args.postgres else "SQLite"))


if __name__ == "__main__":
    main()
