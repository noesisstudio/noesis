"""Perfiles físicos revisados, sin datos, owners, OID ni timestamps de aplicación."""

from dataclasses import replace
from importlib.resources import files
from functools import lru_cache
import hashlib
import json
import re
from pathlib import Path
import tempfile

from .schema_lineage import (
    LineageId, SchemaLineageError, Observation, canonical, classify_registry,
)

# Cuerpo DELETE antiguo66 exacto, reproducido por la regresion69 conservada.
# Solo owner68 reconoce esta variante cerrada antes de la reparacion69.
OLD_CASH_DELETE = "CREATE OR REPLACE FUNCTION cash_payment_delete() RETURNS trigger LANGUAGE plpgsql AS $function$ BEGIN IF EXISTS(SELECT 1 FROM payment_economic_coverage c WHERE c.business_id=OLD.business_id AND c.payment_id=OLD.id) THEN RAISE EXCEPTION 'Cobertura de cobro/banco incoherente' USING ERRCODE='23514'; END IF; RETURN NEW; END $function$"

PROFILE_VERSIONS = tuple(range(1, 76))


def quote_ident(name):
    return '"' + name.replace('"', '""') + '"'


def normalized_sql(text, namespace=""):
    if text is None:
        return None
    return list(_sql_tokens(text, namespace))


@lru_cache(maxsize=4096)
def _sql_tokens(text, namespace=""):
    # Cache inmutable de lexer puro; nunca observaciones ni registry de DB.
    if namespace:
        # Normalizar cualificadores de identificadores sin tocar literales SQL.
        parts = re.split(r"('(?:''|[^'])*')", text)
        text = "".join(part if i % 2 else part.replace(quote_ident(namespace) + ".", "").replace(namespace + ".", "")
                       for i, part in enumerate(parts))
    tokens = re.findall(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|[^\s'\"]+", text)
    return tuple(t if t.startswith("'") else t[1:-1].replace('""', '"') if t.startswith('"') else t.lower() for t in tokens)


def physical_objects(conn, namespace=None):
    """Descriptores estructurales completos; nunca consulta filas de negocio."""
    result = {}
    if conn.dialect == "sqlite":
        rows = conn.execute_exact("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
        for row in rows:
            if row["sql"] is not None:
                result[row["type"] + ":" + row["name"]] = normalized_sql(row["sql"])
        return result
    namespace = namespace or conn.execute_exact("SELECT current_schema() AS namespace").fetchone()["namespace"]
    queries = {
        "relation": "SELECT c.relname,c.relkind,c.relpersistence,c.relrowsecurity,c.relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=? AND c.relkind IN ('r','p','v','m','f') ORDER BY c.relname",
        "column": "SELECT c.relname,a.attname,row_number() OVER (PARTITION BY c.oid ORDER BY a.attnum),format_type(a.atttypid,a.atttypmod),a.attnotnull,a.attidentity,a.attgenerated,pg_get_expr(d.adbin,d.adrelid) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE n.nspname=? AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum",
        "constraint": "SELECT c.relname,co.conname,co.contype,co.condeferrable,co.condeferred,co.convalidated,pg_get_constraintdef(co.oid) FROM pg_constraint co JOIN pg_class c ON c.oid=co.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=? ORDER BY c.relname,co.conname",
        "index": "SELECT c.relname,i.indisvalid,i.indisready,pg_get_indexdef(c.oid) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_index i ON i.indexrelid=c.oid WHERE n.nspname=? ORDER BY c.relname",
        "trigger": "SELECT c.relname,t.tgname,t.tgenabled,pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=? AND NOT t.tgisinternal ORDER BY c.relname,t.tgname",
        "function": "SELECT p.proname,pg_get_function_identity_arguments(p.oid),pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=? AND p.prokind IN ('f','p','w') AND NOT EXISTS(SELECT 1 FROM pg_depend d WHERE d.classid='pg_proc'::regclass AND d.objid=p.oid AND d.deptype='e') ORDER BY p.proname,2",
        "sequence": "SELECT c.relname,format_type(s.seqtypid,NULL),s.seqstart,s.seqincrement,s.seqmax,s.seqmin,s.seqcache,s.seqcycle FROM pg_sequence s JOIN pg_class c ON c.oid=s.seqrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=? ORDER BY c.relname",
    }
    # Identidades de objetos ordenadas; deparser puede cualificar el namespace.
    for kind, query in queries.items():
        for row in conn.execute_exact(query, (namespace,)).fetchall():
            values = list(row.values())
            key_fields = 2 if kind in ("column", "constraint", "trigger", "function") else 1
            key = kind + ":" + ":".join(str(v) for v in values[:key_fields])
            result[key] = [normalized_sql(v, namespace) if type(v) is str else v for v in values]
    return result


@lru_cache(maxsize=1)
def _profiles():
    return json.loads(files("noesis.core").joinpath("schema_object_profiles.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=150)
def expected_objects(dialect, version):
    profiles = _profiles()["profiles"][dialect]
    result = {}
    for stage in range(version + 1):
        delta = profiles[str(stage)]
        for key in delta["remove"]:
            result.pop(key)
        result.update(delta["set"])
    return result


def has_unknown_financial_objects(actual, expected):
    extra = set(actual) - set(expected)
    if not extra:
        return False
    prefixes = ("financial_", "economic_", "accounting_", "journal_", "tax_", "open_item",
                "invoice_economic_", "payment_economic_", "bank_economic_",
                "supplier_invoice_economic_", "expense_economic_",
                "fiscal_cancellation_", "invoice_fiscal_")
    owned_tables = {key.split(":", 1)[1].casefold() for key in expected
                    if key.startswith(("table:", "relation:"))}
    for key in extra:
        parts = key.split(":")
        if any(part.casefold().startswith(prefixes) for part in parts):
            return True
        if parts[0] in ("column", "constraint", "trigger") and len(parts) > 2 and parts[1].casefold() in owned_tables:
            return True
        if parts[0] in ("index", "trigger"):
            value = actual[key]
            tokens = value[-1] if value and isinstance(value[-1], list) else value
            for position, token in enumerate(tokens[:-1]):
                if token == "on":
                    owner = tokens[position + 1]
                    if owner == "only" and position + 2 < len(tokens):
                        owner = tokens[position + 2]
                    if owner.split("(", 1)[0].casefold() in owned_tables:
                        return True
    return False


def validate_objects(conn, observation, namespace=None):
    n = observation.schema_version
    actual = physical_objects(conn, namespace)
    if n == 0:
        metadata = expected_objects(conn.dialect, 0)
        present = any(key in actual for key in ("table:schema_migrations", "relation:schema_migrations"))
        if present and any(actual.get(key) != value for key, value in metadata.items()):
            raise SchemaLineageError("SCHEMA_METADATA_INCOMPLETE")
        extras = set(actual) - set(metadata) if present else set(actual)
        if extras:
            retained = {"table:document_profiles", "index:idx_document_profiles_business_id",
                        "index:idx_document_profiles_business_version"}
            allowed = (conn.dialect == "sqlite" and conn._schema_lock_mode == "exclusive"
                       and "table:schema_migrations" in actual and extras == retained)
            if allowed:
                baseline = expected_objects("sqlite", 70)
                allowed = all(actual[key] == baseline[key] for key in retained)
                allowed = allowed and not conn.execute_exact("SELECT 1 FROM document_profiles LIMIT 1").fetchone()
            if not allowed:
                raise SchemaLineageError("SCHEMA_METADATA_INCOMPLETE")
        return "bootstrap0", hashlib.sha256(canonical({}).encode()).hexdigest()
    expected = expected_objects(conn.dialect, n)
    variant = False
    key = "function:cash_payment_delete:"
    historical = [["cash_payment_delete"], [], normalized_sql(OLD_CASH_DELETE)]
    if (conn.dialect == "postgres" and n == 68 and conn._schema_lock_mode == "exclusive"
            and actual.get(key) == historical):
        expected = dict(expected, **{key: historical})
        variant = True
    def matches(key, value):
        if actual.get(key) == value:
            return True
        return (conn.dialect == "sqlite" and n < 74 and conn._schema_lock_mode == "exclusive"
                and key == "table:sales_prospects"
                and actual.get(key) == expected_objects("sqlite", 74).get(key))
    if any(not matches(key, value) for key, value in expected.items()):
        from . import config
        synthetic_owner = (conn.dialect == "sqlite" and conn._schema_lock_mode == "exclusive"
                           and not config.IS_PRODUCTION and not config.DATABASE_URL
                           and Path(config.DB_PATH).resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()))
        if synthetic_owner:
            databases = conn.execute_exact("PRAGMA database_list").fetchall()
            main_file = next((row["file"] for row in databases if row["name"] == "main"), "")
            synthetic_owner = bool(main_file) and Path(main_file).resolve() == Path(config.DB_PATH).resolve()
        if synthetic_owner:
            for delta in _profiles().get("synthetic_sqlite_owner_variants", {}).get(str(n), ()):
                technical = dict(expected)
                for key in delta["remove"]:
                    technical.pop(key)
                technical.update(delta["set"])
                if actual == technical:
                    profile_hash = hashlib.sha256(canonical(technical).encode("utf-8")).hexdigest()
                    return f"sqlite/synthetic-owner/{n}/v1", profile_hash
        raise SchemaLineageError("SCHEMA_OBJECT_MISMATCH")
    # Un objeto adicional no puede fingir la instalación de una etapa futura.
    if has_unknown_financial_objects(actual, expected):
        raise SchemaLineageError("SCHEMA_OBJECT_MISMATCH")
    profile_id = f"{conn.dialect}/canonical{n}/v1" + ("/historical-delete" if variant else "")
    return profile_id, hashlib.sha256(canonical(expected).encode("utf-8")).hexdigest()


def inspect_registry(conn, *, namespace=None, bootstrap=False, validate=None):
    """Prefijo completo y shape de metadata; nunca crea ni repara objetos."""
    if conn.dialect == "sqlite":
        exists = conn.execute_exact("SELECT 1 AS present FROM sqlite_master WHERE type='table' AND name='schema_migrations'").fetchone()
        columns = conn.execute_exact("PRAGMA table_info(schema_migrations)").fetchall() if exists else []
        good = ([(r["name"], r["type"].upper()) for r in columns] ==
                [("version", "INTEGER"), ("name", "TEXT"), ("applied_at", "TEXT")]
                and [r["pk"] for r in columns] == [1, 0, 0]
                and columns[1]["notnull"] == 1 and columns[2]["notnull"] == 1) if exists else False
        table = "schema_migrations"
    else:
        namespace = namespace or conn.execute_exact("SELECT current_schema() AS namespace").fetchone()["namespace"]
        exists = conn.execute_exact("SELECT 1 AS present FROM information_schema.tables WHERE table_schema=? AND table_name='schema_migrations'", (namespace,)).fetchone()
        columns = conn.execute_exact("SELECT column_name,data_type,is_nullable FROM information_schema.columns WHERE table_schema=? AND table_name='schema_migrations' ORDER BY ordinal_position", (namespace,)).fetchall() if exists else []
        good = ([(r["column_name"], r["data_type"], r["is_nullable"]) for r in columns] ==
                [("version", "integer", "NO"), ("name", "text", "NO"), ("applied_at", "timestamp without time zone", "NO")]) if exists else False
        if exists:
            pk = conn.execute_exact("SELECT pg_get_constraintdef(co.oid) AS definition FROM pg_constraint co JOIN pg_class c ON c.oid=co.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=? AND c.relname='schema_migrations' AND co.contype='p'", (namespace,)).fetchall()
            good = good and len(pk) == 1 and pk[0]["definition"] == "PRIMARY KEY (version)"
        table = quote_ident(namespace) + ".schema_migrations"
    if not exists:
        observation = classify_registry([])
        if not bootstrap:
            return replace(observation, lineage_id=LineageId.UNKNOWN_OR_CORRUPT,
                           integrity="CORRUPT", errors=("SCHEMA_METADATA_INCOMPLETE",))
    elif not good:
        return Observation(LineageId.UNKNOWN_OR_CORRUPT, None, (), None, "CORRUPT", ("SCHEMA_METADATA_INCOMPLETE",))
    else:
        rows = conn.execute_exact(f"SELECT version,name,applied_at FROM {table} ORDER BY version").fetchall()
        observation = classify_registry([[row["version"], row["name"]] for row in rows])
        if any(row["applied_at"] is None for row in rows) or (not rows and not bootstrap):
            return replace(observation, integrity="CORRUPT", errors=("SCHEMA_METADATA_INCOMPLETE",))
    if observation.errors or observation.lineage_id == LineageId.LEGACY_FINANCIAL_74_79:
        return observation
    if validate:
        try:
            profile_id, profile_hash = validate(conn, observation, namespace)
            integrity = "TECHNICAL_ONLY" if profile_id.startswith("sqlite/synthetic-owner/") else "VERIFIED"
            return replace(observation, integrity=integrity, object_profile_id=profile_id,
                           object_profile_hash=profile_hash)
        except SchemaLineageError as exc:
            return replace(observation, integrity="CORRUPT", errors=(exc.code,))
    return observation
