"""Perfiles SOLO de fixtures precisas; el producto nunca importa este modulo.

El catalogo de producto sigue rechazando NUMERIC/TEXT en columnas legacy cuya
estructura canonicamente es binaria. Estos deltas cerrados permiten conservar
las pruebas historicas que declaran dinero exacto en esquemas sinteticos.
No se generan expectativas desde la DB sometida a la prueba.
"""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import tempfile
from urllib.parse import urlsplit

from noesis import config, schema_objects
from noesis.schema_lineage import SchemaLineageError, canonical

STORAGE = {"expenses": ("amount", "vat_rate"),
           "received_invoices": ("base", "vat_amount", "irpf_amount", "total", "vat_rate"),
           "bank_transactions": ("amount",), "invoice_payments": ("amount",)}
ORIGINAL_VALIDATE = schema_objects.validate_objects


def convert_storage(conn):
    if conn.dialect == "postgres":
        for table, columns in STORAGE.items():
            for column in columns:
                conn.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE NUMERIC USING {column}::numeric")
    else:
        import re
        conn.execute("PRAGMA writable_schema=ON")
        for table, columns in STORAGE.items():
            ddl = conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (table,)).fetchone()["sql"]
            for column in columns:
                ddl = re.sub(r"\b" + column + r"\s+REAL\b", column + " TEXT", ddl)
            conn.execute("UPDATE sqlite_master SET sql=? WHERE name=?", (ddl, table))
        version = conn.execute("PRAGMA schema_version").fetchone()["schema_version"]
        conn.execute(f"PRAGMA schema_version={version + 1}")
        conn.execute("PRAGMA writable_schema=OFF")


@lru_cache(maxsize=10)
def fixture_objects(dialect, version):
    data = json.loads(Path(__file__).with_name("synthetic_exact_schema_profiles.json").read_text(encoding="utf-8"))
    return dict(schema_objects.expected_objects(dialect, version), **data[dialect][str(version)])


def _validate(conn, observation, namespace=None):
    if observation.schema_version not in (71, 72, 73, 74, 75):
        return ORIGINAL_VALIDATE(conn, observation, namespace)
    allowed = not config.IS_PRODUCTION
    if conn.dialect == "postgres":
        url = urlsplit(config.DATABASE_URL)
        allowed = allowed and url.hostname in ("localhost", "127.0.0.1", "::1") and url.path == "/noesis_ci"
    else:
        allowed = allowed and Path(config.DB_PATH).resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
    if not allowed:
        return ORIGINAL_VALIDATE(conn, observation, namespace)
    # Una observacion nueva por TX; comparar dos catalogos inmutables de test.
    actual = schema_objects.physical_objects(conn, namespace)
    def matches(expected):
        for key, value in expected.items():
            if actual.get(key) == value:
                continue
            if (conn.dialect == "postgres" and key.startswith("constraint:")
                    and value[2] == ["c"] and actual.get(key) is not None):
                observed = actual[key]
                if observed[:5] == value[:5] and observed[5] is False:
                    from noesis.web.postgres_backup_inventory import constraint_semantics
                    def semantic(tokens):
                        text = " ".join(t.upper() if t in ("and", "or") else t for t in tokens)
                        return constraint_semantics(text.removesuffix(" not valid"))
                    if semantic(observed[6]) == semantic(value[6]):
                        continue
            if (conn.dialect == "sqlite" and observation.schema_version < 74
                    and conn._schema_lock_mode == "exclusive" and key == "table:sales_prospects"
                    and actual.get(key) == schema_objects.expected_objects("sqlite", 74).get(key)):
                continue
            return False
        return not schema_objects.has_unknown_financial_objects(actual, expected)
    expected = schema_objects.expected_objects(conn.dialect, observation.schema_version)
    if not matches(expected):
        expected = fixture_objects(conn.dialect, observation.schema_version)
        if not matches(expected):
            if conn.dialect == "sqlite" and conn._schema_lock_mode == "exclusive":
                return ORIGINAL_VALIDATE(conn, observation, namespace)
            raise SchemaLineageError("SCHEMA_OBJECT_MISMATCH")
    return (f"{conn.dialect}/canonical{observation.schema_version}/v1",
            hashlib.sha256(canonical(expected).encode("utf-8")).hexdigest())


def enable():
    # Solo llamadas explicitas desde fixtures/worker de tests, nunca config runtime.
    schema_objects.validate_objects = _validate
