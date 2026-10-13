"""Inventario semántico de todo schema de usuario, independiente de migrations."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from psycopg import sql

from .postgres_backup_identity import read_identity


def canonical(value) -> str:
    def encode(item):
        if isinstance(item, Decimal):
            return {"decimal": str(item)}
        if isinstance(item, (datetime, date, time)):
            return {type(item).__name__: item.isoformat()}
        if isinstance(item, timedelta):
            return {"timedelta": [item.days, item.seconds, item.microseconds]}
        if isinstance(item, (bytes, memoryview, bytearray)):
            return {"bytes": base64.b64encode(bytes(item)).decode("ascii")}
        return {type(item).__name__: str(item)}
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=encode, ensure_ascii=True)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def constraint_semantics(text: str):
    """pg_dump aplana AND/OR asociativos; conservar todo lo demás, literales incluidos.

    No eliminar paréntesis aritméticos ni cambiar AND por OR. No ejecutar SQL.
    """
    tokens = re.findall(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|[()]|[^\s()'\"]+", text)
    stack = [[]]
    for token in tokens:
        if token == "(":
            child = []
            stack[-1].append(child)
            stack.append(child)
        elif token == ")":
            stack.pop()
        else:
            stack[-1].append(token)

    def normalize(group):
        group = [normalize(item) if isinstance(item, list) else item for item in group]
        while len(group) == 1 and isinstance(group[0], list):
            group = group[0]
        operators = {item for item in group if isinstance(item, str) and item in {"AND", "OR"}}
        if len(operators) == 1:
            operator = next(iter(operators))
            result = []
            for item in group:
                if (isinstance(item, list) and operator in item
                        and not any(isinstance(part, str) and part in {"AND", "OR"} - {operator}
                                    for part in item)):
                    result.extend(item)
                else:
                    result.append(item)
            group = result
        return group
    return normalize(stack[0])


USER_SCHEMA = "n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'"

QUERIES = {
    "collations": "SELECT n.nspname,c.collname,to_jsonb(c)-'oid'-'collowner'-'collnamespace' "
                  "FROM pg_collation c JOIN pg_namespace n ON n.oid=c.collnamespace WHERE " + USER_SCHEMA,
    "schemas": "SELECT n.nspname FROM pg_namespace n WHERE " + USER_SCHEMA,
    "relations": "SELECT n.nspname,c.relname,c.relkind,c.relpersistence,c.relreplident,"
                 "c.relrowsecurity,c.relforcerowsecurity,c.reloptions,"
                 "CASE WHEN c.relkind='p' THEN pg_get_partkeydef(c.oid) END,"
                 "pg_get_expr(c.relpartbound,c.oid) "
                 "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                 "LEFT JOIN pg_tablespace t ON t.oid=c.reltablespace WHERE " + USER_SCHEMA,
    "columns": "SELECT n.nspname,c.relname,a.attnum,a.attname,format_type(a.atttypid,a.atttypmod),"
               "a.attnotnull,a.attidentity,a.attgenerated,a.attcollation::regcollation::text,"
               "pg_get_expr(d.adbin,d.adrelid) FROM pg_attribute a "
               "JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
               "LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum "
               "WHERE a.attnum>0 AND NOT a.attisdropped AND " + USER_SCHEMA,
    "indexes": "SELECT n.nspname,c.relname,pg_get_indexdef(c.oid),i.indisvalid,i.indisready "
               "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
               "JOIN pg_index i ON i.indexrelid=c.oid WHERE " + USER_SCHEMA,
    "constraints": "SELECT n.nspname,co.conname,co.conrelid::regclass::text,co.contype,"
                   "co.condeferrable,co.condeferred,co.convalidated,pg_get_constraintdef(co.oid) "
                   "FROM pg_constraint co JOIN pg_namespace n ON n.oid=co.connamespace WHERE " + USER_SCHEMA,
    "functions": "SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p.oid),"
                 "pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                 "WHERE p.prokind IN ('f','p','w') AND " + USER_SCHEMA,
    "triggers": "SELECT n.nspname,c.relname,t.tgname,t.tgenabled,pg_get_triggerdef(t.oid) "
                "FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE NOT t.tgisinternal AND " + USER_SCHEMA,
    "views": "SELECT n.nspname,c.relname,pg_get_viewdef(c.oid,false),c.relispopulated "
             "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
             "WHERE c.relkind IN ('v','m') AND " + USER_SCHEMA,
    "types": "SELECT n.nspname,t.typname,t.typtype,t.typcategory,"
             "format_type(t.typbasetype,t.typtypmod),t.typnotnull,t.typdefault,"
             "(SELECT json_agg(e.enumlabel ORDER BY e.enumsortorder) FROM pg_enum e WHERE e.enumtypid=t.oid),"
             "(SELECT json_build_array(format_type(r.rngsubtype,NULL),r.rngcanonical::regproc::text,"
             "r.rngsubdiff::regproc::text) FROM pg_range r WHERE r.rngtypid=t.oid) "
             "FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE " + USER_SCHEMA,
    "policies": "SELECT n.nspname,c.relname,p.polname,p.polcmd,p.polpermissive,"
                "pg_get_expr(p.polqual,p.polrelid),pg_get_expr(p.polwithcheck,p.polrelid) "
                "FROM pg_policy p JOIN pg_class c ON c.oid=p.polrelid "
                "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE " + USER_SCHEMA,
    "sequence_definitions": "SELECT n.nspname,c.relname,format_type(s.seqtypid,NULL),"
                            "s.seqstart,s.seqincrement,s.seqmax,s.seqmin,s.seqcache,s.seqcycle "
                            "FROM pg_sequence s JOIN pg_class c ON c.oid=s.seqrelid "
                            "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE " + USER_SCHEMA,
}


def sequences(conn) -> dict[str, str]:
    rows = conn.execute("SELECT n.nspname,c.relname FROM pg_class c "
                        "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='S' AND "
                        + USER_SCHEMA + " ORDER BY 1,2").fetchall()
    return {canonical([schema, name]): digest(conn.execute(
        sql.SQL("SELECT last_value,is_called FROM {}").format(sql.Identifier(schema, name))
    ).fetchone()) for schema, name in rows}


def inventory(conn) -> dict:
    # Deparse idéntico independientemente del search_path de la aplicación.
    conn.execute("SET LOCAL search_path=pg_catalog")
    conn.execute("SET LOCAL timezone='UTC'")
    conn.execute("SET LOCAL extra_float_digits=3")
    conn.execute("SET LOCAL row_security=off")
    objects = {}
    for kind, query in QUERIES.items():
        rows = conn.execute(query).fetchall()
        if kind == "constraints":
            rows = [(*row[:-1], constraint_semantics(row[-1])) for row in rows]
        hashes = sorted(digest(row) for row in rows)
        objects[kind] = {"count": len(hashes), "sha256": digest(hashes)}
    counts, data_hashes = {}, {}
    tables = conn.execute("SELECT n.nspname,c.relname FROM pg_class c "
                          "JOIN pg_namespace n ON n.oid=c.relnamespace "
                          "WHERE c.relkind IN ('r','p','m') AND " + USER_SCHEMA + " ORDER BY 1,2").fetchall()
    for schema, table in tables:
        key = canonical([schema, table])
        # ONLY evita contar otra vez filas de particiones/herencia. Vista materializada tiene datos propios.
        cursor = conn.cursor(name="inventory_" + hashlib.sha256(key.encode()).hexdigest()[:20])
        cursor.execute(sql.SQL("SELECT * FROM ONLY {}").format(sql.Identifier(schema, table)))
        hashes = sorted(digest(row) for row in cursor)
        cursor.close()
        counts[key], data_hashes[key] = len(hashes), digest(hashes)
    identity = read_identity(conn)
    extensions = [list(row) for row in conn.execute(
        "SELECT extname,extversion FROM pg_extension ORDER BY extname").fetchall()]
    return {**identity, "table_count": len(tables), "table_counts": counts,
            "table_data_hashes": data_hashes, "objects": objects,
            "sequence_states": sequences(conn), "required_extensions": extensions}
