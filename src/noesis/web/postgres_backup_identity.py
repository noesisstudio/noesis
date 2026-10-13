"""Identidad del registry para backups; no validator runtime ni autoridad financiera."""

import hashlib
import json

from .postgres_backup_tools import BackupError

CANONICAL_PRE74 = "CANONICAL_PRE74"
CANONICAL_CRM74 = "CANONICAL_CRM74"
LEGACY_FINANCIAL = "LEGACY_FINANCIAL74_79"
LEGACY_NAMES = (
    "evaluacion_readiness_financiera",
    "resoluciones_antecedentes_financieros",
    "cobertura_cancelacion_fiscal_live",
    "activacion_handoff_generaciones",
    "privacy_export_retention_closure",
    "providers_preflight_dispatch_evidence",
)
IDENTITY_FIELDS = ("migration_identities", "schema_lineage_fingerprint", "schema_lineage_id")


def expected_identities() -> list[list]:
    from noesis.migrations import MIGRATIONS
    return [[version, name] for version, name, *_ in MIGRATIONS]


def fingerprint(identities: list[list]) -> str:
    body = {"format": "noesis.schema-lineage.v1",
            "migrations": [{"version": version, "name": name} for version, name in identities]}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def describe(identities, *, require_current: bool = False) -> dict:
    """Prefijo completo/ordenado, nunca MAX-only. Sólo registry, no compatibilidad DDL."""
    if (type(identities) is not list or not identities
            or any(type(row) is not list or len(row) != 2
                   or type(row[0]) is not int or row[0] <= 0
                   or type(row[1]) is not str or not 1 <= len(row[1]) <= 128 for row in identities)):
        raise BackupError("SCHEMA_METADATA_INCOMPLETE")
    versions = [row[0] for row in identities]
    if len(set(versions)) != len(versions):
        raise BackupError("DUPLICATE_MIGRATION_VERSION")
    if versions != list(range(1, len(versions) + 1)):
        raise BackupError("MIGRATION_GAP_OR_ORDER_MISMATCH")
    expected = expected_identities()
    current = len(expected)
    legacy = expected[:73] + [[74 + index, name] for index, name in enumerate(LEGACY_NAMES)]
    n = len(identities)
    if n >= 74 and identities[73] == legacy[73]:
        if n > 79 or identities != legacy[:n]:
            raise BackupError("MIGRATION_IDENTITY_MISMATCH")
        lineage = LEGACY_FINANCIAL
    else:
        if n > current:
            raise BackupError("FUTURE_SCHEMA_UNSUPPORTED")
        if identities != expected[:n]:
            raise BackupError("MIGRATION_IDENTITY_MISMATCH")
        lineage = (CANONICAL_PRE74 if n < 74 else CANONICAL_CRM74 if n == 74
                   else "CANONICAL_CRM74_FINANCIAL75_80")
    if require_current and (lineage != CANONICAL_CRM74 or identities != expected):
        raise BackupError("CURRENT_CANONICAL_CRM74_REQUIRED")
    return {"schema_version": n, "migration_identities": identities,
            "schema_lineage_fingerprint": fingerprint(identities), "schema_lineage_id": lineage}


def read_identity(conn) -> dict:
    rows = conn.execute("SELECT version,name,applied_at FROM public.schema_migrations ORDER BY version").fetchall()
    if any(row[2] is None for row in rows):
        raise BackupError("SCHEMA_METADATA_INCOMPLETE")
    return describe([[row[0], row[1]] for row in rows])


def validate_manifest_identity(manifest: dict) -> dict:
    identity = describe(manifest["migration_identities"])
    if any(manifest[key] != identity[key] for key in ("schema_version", *IDENTITY_FIELDS)):
        raise BackupError("MANIFEST_LINEAGE_IDENTITY_MISMATCH")
    return identity


def privacy_status(identity: dict) -> str:
    """Evidencia técnica de instalación por nombre; nunca serving ni aprobación legal."""
    names = {name for _, name in identity["migration_identities"]}
    if "privacy_export_retention_closure" in names:
        return "POST_RESTORE_PRIVACY_RECONCILIATION_REQUIRED"
    return "NO_E_INSTALLED"
