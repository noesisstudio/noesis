"""Identidad global del schema: registry exacto y objetos, nunca autoridad financiera.

Las inspecciones reciben conexión/TX prestadas. Sólo el migrador propietario
adquiere el lock exclusivo; un consumidor usa SHARE antes de tomar snapshot.
"""

from dataclasses import dataclass
from enum import Enum
from importlib.resources import files
import hashlib
import json
import time


class LineageId(str, Enum):
    CANONICAL_PRE74 = "CANONICAL_PRE74"
    CANONICAL_CRM74 = "CANONICAL_CRM74"
    CANONICAL_FINANCIAL_75_80_PREFIX = "CANONICAL_CRM74_FINANCIAL75_80"
    LEGACY_FINANCIAL_74_79 = "LEGACY_FINANCIAL74_79"
    UNKNOWN_OR_CORRUPT = "UNKNOWN_OR_CORRUPT"


class SchemaLineageError(ValueError):
    """Diagnóstico cerrado, sin SQL, credenciales ni valores de negocio."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


_CATALOG = json.loads(files("noesis.core").joinpath("schema_lineage_catalog.json")
                      .read_text(encoding="utf-8"))
CATALOG = tuple((row["version"], row["name"]) for row in _CATALOG["migrations"])
IMPLEMENTED_LATEST = 75
LEGACY_NAMES = (
    "evaluacion_readiness_financiera", "resoluciones_antecedentes_financieros",
    "cobertura_cancelacion_fiscal_live", "activacion_handoff_generaciones",
    "privacy_export_retention_closure", "providers_preflight_dispatch_evidence",
)
LEGACY_CATALOG = CATALOG[:73] + tuple((74 + i, name) for i, name in enumerate(LEGACY_NAMES))
if (_CATALOG["implemented_latest"] != IMPLEMENTED_LATEST or len(CATALOG) != IMPLEMENTED_LATEST
        or tuple(v for v, _ in CATALOG) != tuple(range(1, IMPLEMENTED_LATEST + 1))
        or len({name for _, name in CATALOG}) != IMPLEMENTED_LATEST):
    raise SchemaLineageError("MIGRATION_IDENTITY_MISMATCH")


def _pairs(identities):
    if type(identities) not in (list, tuple):
        raise SchemaLineageError("SCHEMA_METADATA_INCOMPLETE")
    result = []
    for row in identities:
        if (type(row) not in (tuple, list) or len(row) != 2 or type(row[0]) is not int
                or row[0] <= 0 or type(row[1]) is not str or not 1 <= len(row[1]) <= 128):
            raise SchemaLineageError("SCHEMA_METADATA_INCOMPLETE")
        result.append(tuple(row))
    if len({v for v, _ in result}) != len(result):
        raise SchemaLineageError("SCHEMA_METADATA_INCOMPLETE")
    return tuple(result)


def fingerprint(identities):
    pairs = sorted(_pairs(identities))
    body = {"format": "noesis.schema-lineage.v1",
            "migrations": [{"version": version, "name": name} for version, name in pairs]}
    return hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Observation:
    lineage_id: LineageId
    schema_version: int | None
    migration_identity: tuple
    lineage_fingerprint: str | None
    integrity: str
    errors: tuple[str, ...] = ()
    object_profile_id: str | None = None
    object_profile_hash: str | None = None

    def require_canonical(self, allowed):
        if self.lineage_id == LineageId.LEGACY_FINANCIAL_74_79:
            raise SchemaLineageError("LEGACY_FINANCIAL_LINEAGE_DETECTED")
        if self.errors:
            raise SchemaLineageError(self.errors[0])
        if self.integrity != "VERIFIED" or self.schema_version not in allowed:
            raise SchemaLineageError("SCHEMA_LINEAGE_MISMATCH")
        return self

    def binding(self):
        self.require_canonical((75,))
        return dict(binding_version=1, catalog_id="canonical-v1", lineage_id=self.lineage_id.value,
                    schema_version=self.schema_version, lineage_fingerprint=self.lineage_fingerprint,
                    object_profile_id=self.object_profile_id, object_profile_hash=self.object_profile_hash)


def classify_registry(identities):
    """Clasifica también legacy corrupta; no confundir reconocimiento con ownership."""
    sentinel = any(type(row) in (tuple, list) and len(row) == 2
                   and type(row[0]) is int and row[0] == 74 and row[1] == LEGACY_NAMES[0]
                   for row in identities) if type(identities) in (tuple, list) else False
    lineage = LineageId.LEGACY_FINANCIAL_74_79 if sentinel else LineageId.UNKNOWN_OR_CORRUPT
    try:
        pairs = _pairs(identities)
        pairs = tuple(sorted(pairs))
        n = len(pairs)
        expected = LEGACY_CATALOG if sentinel else CATALOG
        if any(v > len(expected) for v, _ in pairs):
            raise SchemaLineageError("FUTURE_SCHEMA_UNSUPPORTED")
        if tuple(v for v, _ in pairs) != tuple(range(1, n + 1)):
            raise SchemaLineageError("MIGRATION_GAP")
        if n > len(expected):
            raise SchemaLineageError("FUTURE_SCHEMA_UNSUPPORTED")
        if pairs != expected[:n]:
            raise SchemaLineageError("MIGRATION_IDENTITY_MISMATCH")
        if not sentinel:
            lineage = (LineageId.CANONICAL_PRE74 if n < 74 else LineageId.CANONICAL_CRM74
                       if n == 74 else LineageId.CANONICAL_FINANCIAL_75_80_PREFIX)
        return Observation(lineage, n, pairs, fingerprint(pairs), "REGISTRY_ONLY")
    except SchemaLineageError as exc:
        return Observation(lineage, None, (), None, "CORRUPT", (exc.code,))


def connection(value):
    return getattr(value, "borrowed_connection", value)


def begin_schema_access(value):
    """Primer lock de la TX; nunca reinicia una TX ni degrada aislamiento."""
    conn = connection(value)
    if conn.dialect == "sqlite":
        if not conn.raw.in_transaction:
            raise SchemaLineageError("SCHEMA_TX_PROTOCOL_REQUIRED")
        return
    conn._schema_reset_if_idle()
    if conn._schema_lock_mode in ("share", "exclusive"):
        return
    if conn._schema_statement_count or conn._schema_untracked_tx:
        raise SchemaLineageError("SCHEMA_TX_PROTOCOL_REQUIRED")
    try:
        conn.execute("SET LOCAL lock_timeout='30s'")
        conn.execute("LOCK TABLE schema_migrations IN SHARE MODE")
    except Exception as exc:
        code = "MIGRATION_LOCK_TIMEOUT" if getattr(exc, "sqlstate", "") == "55P03" else "SCHEMA_METADATA_INCOMPLETE"
        raise SchemaLineageError(code) from None
    conn._schema_lock_mode = "share"


MIGRATION_LOCK_KEY = 2533761095082033151
MIGRATION_LOCK_TIMEOUT = 30.0


def lock_migrator(conn):
    """Advisory xact exclusivo → registry exclusivo, antes de decidir DDL."""
    if conn.dialect == "sqlite":
        conn.execute("PRAGMA busy_timeout=30000")
        if not conn.raw.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        conn._schema_lock_mode = "exclusive"
        return
    conn._schema_reset_if_idle()
    if conn._schema_lock_mode == "exclusive":
        return
    if conn._schema_prelock_savepoint:
        raise SchemaLineageError("SCHEMA_TX_PROTOCOL_REQUIRED")
    if conn._schema_lock_mode == "share":
        raise SchemaLineageError("SCHEMA_TX_PROTOCOL_REQUIRED")
    if conn._schema_statement_count or conn._schema_untracked_tx:
        isolation = conn.execute("SHOW transaction_isolation").fetchone()[0]
        if isolation != "read committed":
            raise SchemaLineageError("SCHEMA_TX_PROTOCOL_REQUIRED")
    else:
        conn.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
    conn.execute("SET LOCAL lock_timeout='30s'")
    conn.execute("SET LOCAL statement_timeout='30s'")
    deadline = time.monotonic() + MIGRATION_LOCK_TIMEOUT
    while not conn.execute("SELECT pg_try_advisory_xact_lock(?) AS acquired", (MIGRATION_LOCK_KEY,)).fetchone()["acquired"]:
        if time.monotonic() >= deadline:
            raise SchemaLineageError("MIGRATION_LOCK_TIMEOUT")
        time.sleep(min(0.25, max(0, deadline - time.monotonic())))
    # Primera lectura de catálogo después del advisory; no decisiones pre-lock.
    exists = conn.execute("SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() AND table_name='schema_migrations'").fetchone()
    if exists:
        try:
            conn.execute("LOCK TABLE schema_migrations IN ACCESS EXCLUSIVE MODE")
        except Exception:
            raise SchemaLineageError("MIGRATION_LOCK_TIMEOUT") from None
    conn._schema_lock_mode = "exclusive"


def inspect(value, *, namespace=None, bootstrap=False, objects=True):
    """Sólo SELECT/PRAGMA: el propietario debe aportar snapshot/protocolo exterior."""
    from .schema_objects import inspect_registry, validate_objects
    conn = connection(value)
    return inspect_registry(conn, namespace=namespace, bootstrap=bootstrap,
                            validate=validate_objects if objects else None)


def require_compatible(value, allowed):
    begin_schema_access(value)
    return inspect(value).require_canonical(tuple(allowed))


def require_runtime(value):
    return require_compatible(value, (IMPLEMENTED_LATEST,))


def registry_sql_predicate(version="75"):
    """Guard compilado del prefijo instalado; no admite futuras filas diseñadas."""
    matching = " OR ".join(f"(version={v} AND name='{name}')" for v, name in CATALOG)
    return f"({version}=75 AND (SELECT COUNT(*) FROM schema_migrations)=75 AND NOT EXISTS(SELECT 1 FROM schema_migrations WHERE NOT ({matching})))"
