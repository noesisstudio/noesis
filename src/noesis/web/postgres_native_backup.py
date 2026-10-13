"""Backup nativo autocontenido. Integridad técnica no concede autoridad G ni E."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from .postgres_backup_inventory import digest, inventory, sequences
from .postgres_backup_identity import IDENTITY_FIELDS, privacy_status, validate_manifest_identity
from .postgres_backup_tools import (
    BackupError, Toolchain, _DisposableTarget, database_identity, database_settings,
    disposable_target, libpq_environment, run, safe_environment,
)

FORMAT = "noesis-postgres-native-v2"
PRIVACY_REQUIRED = "POST_RESTORE_PRIVACY_RECONCILIATION_REQUIRED"


def pair(path: Path, suffix: str) -> Path:
    if path.suffix != ".pgdump":
        raise BackupError("NATIVE_ARCHIVE_SUFFIX_REQUIRED")
    return path.with_suffix(suffix)


def file_hash(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def toc(path: Path, tools: Toolchain) -> dict:
    text = run([tools.binary("pg_restore"), "--list", str(path)], env=safe_environment())
    lines = []
    classes = {}
    kinds = ("MATERIALIZED VIEW DATA", "MATERIALIZED VIEW", "SEQUENCE OWNED BY",
             "SEQUENCE SET", "TABLE DATA", "FK CONSTRAINT", "CHECK CONSTRAINT",
             "DEFAULT", "SCHEMA", "TABLE", "SEQUENCE", "INDEX", "CONSTRAINT",
             "FUNCTION", "PROCEDURE", "TRIGGER", "TYPE", "DOMAIN", "VIEW", "EXTENSION", "COLLATION")
    for line in text.splitlines():
        if not line or line.startswith(";"):
            continue
        # IDs de catálogo no son portables. El resto del TOC no se publica sin hashear.
        normalized = re.sub(r"^\d+; \d+ \d+ ", "", line).strip()
        lines.append(normalized)
        for kind in kinds:
            if normalized.startswith(kind + " "):
                classes[kind] = classes.get(kind, 0) + 1
                break
    if not lines:
        raise BackupError("EMPTY_ARCHIVE_TOC")
    return {"archive_toc_hash": digest(sorted(lines)), "archive_object_classes": classes}


def create(dsn: str, destination: Path, documents_creator, documents_verifier,
           *, code_sha: str | None = None) -> dict:
    """READ ONLY + snapshot exportado compartido con pg_dump; manifest se publica al final."""
    tools = Toolchain.discover()
    archive_part = pair(destination, ".pgdump.part")
    manifest_path = pair(destination, ".manifest.json")
    docs_path = pair(destination, ".docs.zip")
    manifest_part = pair(destination, ".manifest.json.part")
    owned = (destination, archive_part, docs_path, manifest_path, manifest_part)
    if any(path.exists() or path.is_symlink() for path in owned):
        raise BackupError("BACKUP_DESTINATION_ALREADY_EXISTS")
    if os.name != "posix":
        raise BackupError("NATIVE_BACKUP_REQUIRES_PRIVATE_POSIX_STORAGE")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        # No ampliar ni cambiar permisos de un directorio compartido del operador.
        if destination.parent.stat().st_mode & 0o077:
            raise BackupError("PRIVATE_BACKUP_DIRECTORY_REQUIRED")
        with psycopg.connect(dsn) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            server_number = int(conn.execute("SHOW server_version_num").fetchone()[0])
            tools.check_server(server_number // 10000)
            snapshot = conn.execute("SELECT pg_export_snapshot()").fetchone()[0]
            metadata = inventory(conn)
            metadata.update({"source_database_fingerprint": database_identity(conn),
                             "database_settings": database_settings(conn),
                             "source_server_version": conn.execute("SHOW server_version").fetchone()[0],
                             "source_server_major": server_number // 10000})
            with libpq_environment(dsn) as env:
                run([tools.binary("pg_dump"), "--format=custom", "--no-owner", "--no-privileges",
                     "--no-tablespaces", "--snapshot=" + snapshot, "--file=" + str(archive_part)], env=env)
            if sequences(conn) != metadata["sequence_states"]:
                raise BackupError("SOURCE_SEQUENCES_CHANGED_DURING_BACKUP")
            # Segundo inventario detecta DDL/filas no congelables que hayan cambiado.
            if inventory(conn) != {key: metadata[key] for key in inventory_keys()}:
                raise BackupError("SOURCE_INVENTORY_CHANGED_DURING_BACKUP")
        archive_part.chmod(0o600)
        archive_part.replace(destination)
        documents_creator(destination)
        docs_path.chmod(0o600)
        documents_verifier(docs_path)
        manifest = {"format_version": FORMAT, "manifest_contract_version": 2,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "pg_dump_version": tools.dump_version, "pg_dump_major": tools.major,
                    "application_code_sha": code_sha if code_sha and re.fullmatch(r"[0-9a-f]{40}", code_sha) else None,
                    "archive_sha256": file_hash(destination), "archive_size": destination.stat().st_size,
                    "documents_sha256": file_hash(docs_path), "documents_size": docs_path.stat().st_size,
                    **metadata, **toc(destination, tools)}
        with manifest_part.open("x", encoding="utf-8") as output:
            json.dump(manifest, output, sort_keys=True, separators=(",", ":"))
            output.flush()
            os.fsync(output.fileno())
        manifest_part.chmod(0o600)
        manifest_part.replace(manifest_path)
        return manifest
    except Exception as exc:
        for path in owned:
            path.unlink(missing_ok=True)
        if isinstance(exc, BackupError):
            raise
        raise BackupError("NATIVE_BACKUP_FAILED") from None


def inventory_keys(contract_version: int = 2) -> tuple[str, ...]:
    base = ("schema_version", "table_count", "table_counts", "table_data_hashes", "objects",
            "sequence_states", "required_extensions")
    return base + IDENTITY_FIELDS if contract_version == 2 else base


def _closed_json(text):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise BackupError("DUPLICATE_MANIFEST_FIELD")
            value[key] = item
        return value
    return json.loads(text, object_pairs_hook=pairs)


def load_set(path: Path, documents_verifier) -> dict:
    """Hashes y contrato cerrado antes de iniciar un servidor o restaurar DDL."""
    manifest_path, docs_path = pair(path, ".manifest.json"), pair(path, ".docs.zip")
    if any(not item.is_file() or item.is_symlink() for item in (path, manifest_path, docs_path)):
        raise BackupError("BACKUP_SET_INCOMPLETE")
    try:
        if manifest_path.stat().st_size > 16 * 1024 * 1024:
            raise BackupError("MANIFEST_TOO_LARGE")
        manifest = _closed_json(manifest_path.read_text(encoding="utf-8"))
        contract_version = manifest.get("manifest_contract_version", 1)
        if type(contract_version) is not int or contract_version not in (1, 2):
            raise BackupError("UNSUPPORTED_MANIFEST_CONTRACT")
        fields = set(inventory_keys(contract_version)) | {
            "format_version", "created_at", "pg_dump_version", "pg_dump_major", "application_code_sha",
            "archive_sha256", "archive_size", "documents_sha256", "documents_size",
            "source_database_fingerprint", "source_server_version", "source_server_major", "database_settings",
            "archive_toc_hash", "archive_object_classes",
        }
        if contract_version == 2:
            fields.add("manifest_contract_version")
        elif "manifest_contract_version" in manifest:
            raise BackupError("UNSUPPORTED_MANIFEST_CONTRACT")
        if set(manifest) != fields or manifest["format_version"] != FORMAT:
            raise BackupError("UNSUPPORTED_MANIFEST_CONTRACT")
        if contract_version == 2:
            validate_manifest_identity(manifest)
        for field in ("archive_sha256", "documents_sha256", "source_database_fingerprint", "archive_toc_hash"):
            if not re.fullmatch(r"[0-9a-f]{64}", manifest[field]):
                raise BackupError("INVALID_MANIFEST_HASH")
        if (type(manifest["schema_version"]) is not int or manifest["schema_version"] < 0
                or manifest["pg_dump_major"] != 18 or not isinstance(manifest["table_counts"], dict)
                or len(manifest["table_counts"]) != manifest["table_count"]
                or set(manifest["table_counts"]) != set(manifest["table_data_hashes"])
                or any(type(total) is not int or total < 0 for total in manifest["table_counts"].values())):
            raise BackupError("INVALID_MANIFEST_INVENTORY")
        for artifact, prefix in ((path, "archive"), (docs_path, "documents")):
            if (artifact.stat().st_size != manifest[prefix + "_size"]
                    or file_hash(artifact) != manifest[prefix + "_sha256"]):
                raise BackupError("BACKUP_SET_HASH_MISMATCH")
        documents_verifier(docs_path)
        return manifest
    except BackupError:
        raise
    except Exception:
        raise BackupError("INVALID_BACKUP_SET") from None


def check_extensions(conn, extensions):
    available = set(conn.execute("SELECT name,version FROM pg_available_extension_versions").fetchall())
    if any(tuple(extension) not in available for extension in extensions):
        raise BackupError("REQUIRED_EXTENSION_UNAVAILABLE")


def restore(path: Path, target: _DisposableTarget, documents_verifier) -> dict:
    """Destino sellado creado aquí; ningún parámetro DSN/is_test ni migrations."""
    if not isinstance(target, _DisposableTarget):
        raise BackupError("DISPOSABLE_TARGET_REQUIRED")
    manifest = load_set(path, documents_verifier)
    tools = Toolchain.discover()
    tools.check_server(manifest["source_server_major"])
    if toc(path, tools) != {key: manifest[key] for key in ("archive_toc_hash", "archive_object_classes")}:
        raise BackupError("ARCHIVE_OBJECT_INVENTORY_MISMATCH")
    target.assert_empty(manifest["source_database_fingerprint"])
    with target.connection() as conn:
        if database_settings(conn) != manifest["database_settings"]:
            raise BackupError("DATABASE_ENCODING_LOCALE_VERSION_MISMATCH")
        check_extensions(conn, manifest["required_extensions"])
    target.consume()  # También queda consumido si falla o se interrumpe pg_restore.
    try:
        with libpq_environment(target.dsn) as env:
            run([tools.binary("pg_restore"), "--exit-on-error", "--single-transaction",
                 "--no-owner", "--no-privileges", "--no-tablespaces", "--dbname=" +
                 # Nombre aleatorio local; credenciales/endpoint nunca van en argv.
                 psycopg.conninfo.conninfo_to_dict(target.dsn)["dbname"], str(path)], env=env)
        with target.connection() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            actual = inventory(conn)
            keys = inventory_keys(manifest.get("manifest_contract_version", 1))
            if {key: actual[key] for key in keys} != {key: manifest[key] for key in keys}:
                categories = [key for key in keys if actual[key] != manifest[key]]
                if "objects" in categories:
                    categories.extend(kind for kind in actual["objects"]
                                      if actual["objects"][kind] != manifest["objects"].get(kind))
                raise BackupError("RESTORED_INVENTORY_MISMATCH:" + ",".join(categories))
            conn.execute("SELECT 1").fetchone()
        return {"technical_integrity": "PASS", "schema_version": manifest["schema_version"],
                "table_count": manifest["table_count"], "pg_restore_version": tools.restore_version,
                "privacy_status": privacy_status(actual),
                "schema_lineage_id": actual["schema_lineage_id"],
                "schema_lineage_fingerprint": actual["schema_lineage_fingerprint"],
                "migration_identities": actual["migration_identities"],
                "manifest_contract_version": manifest.get("manifest_contract_version", 1),
                "g_real_evidence": False, "serving_authorized": False}
    except BackupError:
        raise
    except Exception:
        raise BackupError("NATIVE_RESTORE_FAILED") from None


def verify(path: Path, documents_verifier) -> dict:
    manifest = load_set(path, documents_verifier)
    with disposable_target(settings=manifest["database_settings"]) as target:
        return restore(path, target, documents_verifier)
