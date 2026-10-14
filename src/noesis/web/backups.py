"""Copias verificadas de SQLite y Postgres.

SQLite conserva su copia consistente ``.db``. PostgreSQL usa un set nativo V2,
independiente del catálogo de migraciones. V1 sigue siendo legible cuando su
catálogo es reconstruible. Cada copia se verifica antes de rotar o subirla.
"""

from __future__ import annotations

import base64
import argparse
import gzip
import hashlib
import hmac
import http.client
import json
import logging
import os
import sqlite3
import time as monotonic_time
import tempfile
import zipfile
from contextlib import closing
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote, urlsplit

from .. import config, db, migrations
from . import postgres_native_backup as native
from .postgres_backup_tools import BackupError, _DisposableTarget, database_identity, disposable_target

try:
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
except ImportError:  # SQLite local no necesita cargar el driver.
    psycopg = None
    sql = None
    dict_row = None


log = logging.getLogger("noesis.backups")
KEEP = 14  # copias diarias conservadas (~2 semanas)
KEY_TABLES = (
    "businesses",
    "invoices",
    "worker_clockins",
    "invoice_records",
    "clients",
)
POSTGRES_DUMP_FORMAT = "noesis-postgres-logical-v1"


def _backup_dir() -> Path:
    directory = Path(config.BACKUP_DIR)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Normalizada en el origen: en macOS /var es un enlace a /private/var, así
    # que comparar una ruta normalizada con otra que no lo está daba falsos
    # negativos al localizar la última copia verificada.
    return directory.resolve()


def _destination(suffix: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return _backup_dir() / f"noesis-{stamp}{suffix}"


def _sqlite_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        for table in KEY_TABLES
    }


def _create_sqlite_backup() -> tuple[Path, dict[str, int]] | None:
    source_path = Path(config.DB_PATH)
    if not source_path.exists():
        return None
    destination = _destination(".db")
    with (
        closing(sqlite3.connect(str(source_path))) as source,
        closing(sqlite3.connect(str(destination))) as target,
    ):
        # La transacción de lectura fija la misma instantánea para recuentos y copia.
        source.execute("BEGIN")
        origin_counts = _sqlite_counts(source)
        source.backup(target)
    return destination, origin_counts


def _verify_sqlite_backup(path: Path, origin_counts: dict[str, int]) -> None:
    """Restaura la copia en otro archivo y valida esquema, integridad y recuentos."""
    with tempfile.TemporaryDirectory(prefix="noesis-backup-verify-") as temporary:
        restored_path = Path(temporary) / "restored.db"
        with (
            closing(sqlite3.connect(str(path))) as source,
            closing(sqlite3.connect(str(restored_path))) as target,
        ):
            source.backup(target)
        with closing(sqlite3.connect(str(restored_path))) as restored:
            integrity = restored.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError(f"PRAGMA integrity_check: {integrity}")
            from ..schema_lineage import require_runtime
            restored.row_factory = sqlite3.Row
            restored.execute("BEGIN")
            version = require_runtime(db.Connection(restored, "sqlite")).schema_version
            if int(version) != migrations.LATEST_VERSION:
                raise RuntimeError(
                    f"Esquema restaurado {version}/{migrations.LATEST_VERSION}"
                )
            restored_counts = _sqlite_counts(restored)
    if restored_counts != origin_counts:
        raise RuntimeError(
            f"Los recuentos restaurados no cuadran: "
            f"{restored_counts} != {origin_counts}"
        )


def _encode_value(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return {"__noesis_type__": "decimal", "value": str(value)}
    if isinstance(value, datetime):
        return {"__noesis_type__": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__noesis_type__": "date", "value": value.isoformat()}
    if isinstance(value, time):
        return {"__noesis_type__": "time", "value": value.isoformat()}
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {
            "__noesis_type__": "bytes",
            "value": base64.b64encode(bytes(value)).decode("ascii"),
        }
    if isinstance(value, (dict, list)):
        return {"__noesis_type__": "json", "value": value}
    return {"__noesis_type__": "string", "value": str(value)}


def _decode_value(value):
    if not isinstance(value, dict) or "__noesis_type__" not in value:
        return value
    kind = value["__noesis_type__"]
    raw = value.get("value")
    if kind == "decimal":
        return Decimal(raw)
    if kind == "datetime":
        return datetime.fromisoformat(raw)
    if kind == "date":
        return date.fromisoformat(raw)
    if kind == "time":
        return time.fromisoformat(raw)
    if kind == "bytes":
        return base64.b64decode(raw)
    return raw


def _postgres_table_order(conn) -> list[str]:
    tables = [
        row["table_name"]
        for row in conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema=current_schema() AND table_type='BASE TABLE' "
            "ORDER BY table_name"
        ).fetchall()
    ]
    dependencies = {table: set() for table in tables}
    rows = conn.execute(
        "SELECT tc.table_name AS child, ccu.table_name AS parent "
        "FROM information_schema.table_constraints tc "
        "JOIN information_schema.constraint_column_usage ccu "
        "ON ccu.constraint_catalog=tc.constraint_catalog "
        "AND ccu.constraint_schema=tc.constraint_schema "
        "AND ccu.constraint_name=tc.constraint_name "
        "WHERE tc.constraint_type='FOREIGN KEY' "
        "AND tc.table_schema=current_schema() "
        "AND ccu.table_schema=current_schema()"
    ).fetchall()
    for row in rows:
        if row["child"] in dependencies and row["parent"] != row["child"]:
            dependencies[row["child"]].add(row["parent"])

    ordered: list[str] = []
    pending = set(tables)
    while pending:
        ready = sorted(
            table for table in pending if not (dependencies[table] & pending)
        )
        if not ready:  # Una FK circular no debe impedir conservar los datos.
            ready = [sorted(pending)[0]]
        for table in ready:
            ordered.append(table)
            pending.remove(table)
    return ordered


def _postgres_primary_key(conn, table: str) -> list[str]:
    rows = conn.execute(
        "SELECT kcu.column_name FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu "
        "ON kcu.constraint_catalog=tc.constraint_catalog "
        "AND kcu.constraint_schema=tc.constraint_schema "
        "AND kcu.constraint_name=tc.constraint_name "
        "WHERE tc.constraint_type='PRIMARY KEY' "
        "AND tc.table_schema=current_schema() AND tc.table_name=%s "
        "ORDER BY kcu.ordinal_position",
        (table,),
    ).fetchall()
    return [row["column_name"] for row in rows]


def _create_postgres_backup() -> tuple[Path, dict[str, int]]:
    destination = _destination(".pgdump")
    manifest = native.create(
        config.DATABASE_URL, destination, _create_documents_backup, _verify_documents_backup,
        code_sha=os.environ.get("RAILWAY_GIT_COMMIT_SHA") or os.environ.get("GITHUB_SHA"),
    )
    return destination, manifest["table_counts"]


def _create_postgres_backup_v1() -> tuple[Path, dict[str, int]]:
    if psycopg is None:
        raise RuntimeError("psycopg no está instalado.")
    destination = _destination(".dump.gz")
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        from ..schema_lineage import require_runtime
        wrapped = db.Connection(conn, "postgres")
        wrapped.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        identity = require_runtime(wrapped)
        tables = _postgres_table_order(conn)
        counts = {
            table: int(
                conn.execute(
                    sql.SQL("SELECT COUNT(*) AS total FROM {}").format(
                        sql.Identifier(table)
                    )
                ).fetchone()["total"]
            )
            for table in tables
        }
        version = identity.schema_version
        header = {
            "format": POSTGRES_DUMP_FORMAT,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": version,
            "tables": tables,
            "counts": counts,
        }
        with gzip.open(destination, "wt", encoding="utf-8", newline="\n") as output:
            output.write(json.dumps(header, ensure_ascii=False) + "\n")
            for table in tables:
                primary_key = _postgres_primary_key(conn, table)
                statement = sql.SQL("SELECT * FROM {}").format(
                    sql.Identifier(table)
                )
                if primary_key:
                    statement += sql.SQL(" ORDER BY {}").format(
                        sql.SQL(", ").join(map(sql.Identifier, primary_key))
                    )
                cursor = conn.execute(statement)
                columns = [column.name for column in cursor.description]
                output.write(
                    json.dumps(
                        {"type": "table", "name": table, "columns": columns},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                for row in cursor:
                    output.write(
                        json.dumps(
                            {
                                "type": "row",
                                "values": [
                                    _encode_value(row[column]) for column in columns
                                ],
                            },
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        + "\n"
                    )
    return destination, counts


def _insert_postgres_rows(raw, table: str, columns: list[str], rows: list[list]) -> None:
    if not rows:
        return
    statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )
    with raw.cursor() as cursor:
        cursor.executemany(statement, rows)


def _set_postgres_user_triggers(raw, tables: list[str], *, enabled: bool) -> None:
    """Suspende solo triggers de negocio durante una restauración íntegra.

    Las claves foráneas y demás restricciones internas permanecen activas. Esto
    permite reconstruir, por ejemplo, las líneas congeladas de una factura emitida
    sin desproteger el esquema una vez finalizada la restauración.
    """
    action = sql.SQL("ENABLE" if enabled else "DISABLE")
    for table in tables:
        raw.execute(
            sql.SQL("ALTER TABLE {} {} TRIGGER USER").format(
                sql.Identifier(table), action
            )
        )


def _reset_postgres_sequences(raw) -> None:
    """Alinea identidades para que una restauración pueda seguir escribiendo."""
    schema = raw.execute(
        "SELECT current_schema() AS schema_name"
    ).fetchone()["schema_name"]
    identity_columns = raw.execute(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema=current_schema() "
        "AND (is_identity='YES' OR column_default LIKE 'nextval(%') "
        "ORDER BY table_name, ordinal_position"
    ).fetchall()
    for column in identity_columns:
        table = column["table_name"]
        name = column["column_name"]
        relation = sql.Identifier(schema, table).as_string(raw)
        sequence = raw.execute(
            "SELECT pg_get_serial_sequence(%s, %s) AS sequence_name",
            (relation, name),
        ).fetchone()["sequence_name"]
        if not sequence:
            continue
        maximum = raw.execute(
            sql.SQL("SELECT MAX({}) AS maximum FROM {}").format(
                sql.Identifier(name), sql.Identifier(table)
            )
        ).fetchone()["maximum"]
        if maximum is None:
            raw.execute("SELECT setval(%s::regclass, 1, false)", (sequence,))
        else:
            raw.execute(
                "SELECT setval(%s::regclass, %s, true)", (sequence, maximum)
            )


def _legacy_preflight(path: Path) -> dict:
    from .postgres_backup_identity import describe
    # Antes de cualquier DDL, siquiera de migraciones. No reconstruir el futuro.
    with gzip.open(path, "rt", encoding="utf-8") as source:
        header = json.loads(source.readline())
    if header.get("format") != POSTGRES_DUMP_FORMAT:
        raise BackupError("UNSUPPORTED_LEGACY_BACKUP_FORMAT")
    if type(header.get("schema_version")) is not int or header["schema_version"] < 1:
        raise BackupError("INVALID_LEGACY_BACKUP_INVENTORY")
    if header["schema_version"] > migrations.LATEST_VERSION:
        raise BackupError("LEGACY_BACKUP_REQUIRES_NEWER_SCHEMA_CATALOG")
    if int(header.get("schema_version", 0)) != migrations.LATEST_VERSION:
        raise BackupError("LEGACY_BACKUP_REQUIRES_MATCHING_SCHEMA_CATALOG")
    # El catálogo legacy sólo puede reconstruir tablas/columnas conocidas. La
    # inspección offline precede al DDL PostgreSQL y evita un restore parcial.
    with closing(sqlite3.connect(":memory:")) as catalog:
        catalog.row_factory = sqlite3.Row
        migrations.upgrade_connection(db.Connection(catalog, "sqlite"))
        known = {row[0]: {column[1] for column in catalog.execute(
            'PRAGMA table_info("' + row[0].replace('"', '""') + '")')}
            for row in catalog.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if set(header.get("tables", [])) != set(header.get("counts", {})) or not header.get("tables"):
        raise BackupError("INVALID_LEGACY_BACKUP_INVENTORY")
    if set(header["tables"]) - set(known):
        raise BackupError("LEGACY_BACKUP_REQUIRES_NEWER_SCHEMA_CATALOG")
    if set(header["tables"]) != set(known) - {"sqlite_sequence"}:
        raise BackupError("LEGACY_BACKUP_INCOMPLETE_SCHEMA_CATALOG")
    with gzip.open(path, "rt", encoding="utf-8") as source:
        source.readline()
        declared = []
        registry = []
        current_table, current_columns = None, None
        for line in source:
            record = json.loads(line)
            if record.get("type") == "table":
                name, columns = record.get("name"), record.get("columns")
                if name not in known or set(columns or []) != known[name]:
                    raise BackupError("LEGACY_BACKUP_REQUIRES_NEWER_SCHEMA_CATALOG")
                declared.append(name)
                current_table, current_columns = name, columns
            elif record.get("type") == "row" and current_table == "schema_migrations":
                values = record.get("values")
                if (type(values) is not list or len(values) != len(current_columns)
                        or set(current_columns) != {"version", "name", "applied_at"}):
                    raise BackupError("SCHEMA_METADATA_INCOMPLETE")
                row = dict(zip(current_columns, values))
                if row["applied_at"] is None:
                    raise BackupError("SCHEMA_METADATA_INCOMPLETE")
                registry.append([row["version"], row["name"]])
            elif record.get("type") != "row":
                raise BackupError("INVALID_LEGACY_BACKUP_INVENTORY")
        if declared != header["tables"] or len(declared) != len(set(declared)):
            raise BackupError("INVALID_LEGACY_BACKUP_INVENTORY")
        # V1 no fija el orden de filas; la identidad se ordena por versión numérica.
        if any(type(row[0]) is not int for row in registry):
            raise BackupError("SCHEMA_METADATA_INCOMPLETE")
        identity = describe(sorted(registry, key=lambda row: row[0]), require_current=True)
        if identity["schema_version"] != header["schema_version"]:
            raise BackupError("MANIFEST_LINEAGE_IDENTITY_MISMATCH")
    return header


def _restore_postgres_dump(raw, path: Path, *, target=None) -> tuple[dict, list[str]]:
    _legacy_preflight(path)
    if not isinstance(target, _DisposableTarget):
        raise BackupError("DISPOSABLE_TARGET_REQUIRED")
    target.assert_empty("0" * 64)
    if database_identity(raw) != target.identity:
        raise BackupError("RESTORE_IDENTITY_MISMATCH")
    target.consume()
    wrapped = db.Connection(raw, "postgres")
    migrations.upgrade_connection(wrapped)
    tables: list[str] = []
    current_table = ""
    columns: list[str] = []
    pending_rows: list[list] = []

    def flush() -> None:
        nonlocal pending_rows
        _insert_postgres_rows(raw, current_table, columns, pending_rows)
        pending_rows = []

    with gzip.open(path, "rt", encoding="utf-8") as source:
        header = json.loads(source.readline())
        if header.get("format") != POSTGRES_DUMP_FORMAT:
            raise RuntimeError("El formato del backup Postgres no es compatible.")
        expected_tables = [str(table) for table in header.get("tables", [])]
        if not expected_tables:
            raise RuntimeError("El backup Postgres no declara sus tablas.")
        _set_postgres_user_triggers(raw, expected_tables, enabled=False)
        for line in source:
            record = json.loads(line)
            if record["type"] == "table":
                flush()
                current_table = record["name"]
                columns = record["columns"]
                tables.append(current_table)
                if current_table == "schema_migrations":
                    raw.execute("DELETE FROM schema_migrations")
            elif record["type"] == "row":
                pending_rows.append(
                    [_decode_value(value) for value in record["values"]]
                )
                if len(pending_rows) >= 500:
                    flush()
        flush()
    _reset_postgres_sequences(raw)
    _set_postgres_user_triggers(raw, expected_tables, enabled=True)
    return header, tables


def _verify_postgres_backup(path: Path, origin_counts: dict[str, int]) -> dict | None:
    """V2 nativo o V1 acotado; ambos en instancia nueva, nunca en el origen."""
    if path.suffix == ".pgdump":
        manifest = native.load_set(path, _verify_documents_backup)
        if manifest["table_counts"] != origin_counts:
            raise BackupError("BACKUP_COUNTS_MISMATCH")
        return native.verify(path, _verify_documents_backup)
    if psycopg is None:
        raise RuntimeError("psycopg no está instalado.")
    _legacy_preflight(path)
    with disposable_target() as target:
        with psycopg.connect(target.dsn, row_factory=dict_row) as raw:
            header, tables = _restore_postgres_dump(raw, path, target=target)
            if int(header.get("schema_version", 0)) != migrations.LATEST_VERSION:
                raise RuntimeError(
                    f"El backup declara el esquema "
                    f"{header.get('schema_version')}/{migrations.LATEST_VERSION}"
                )
            wrapped = db.Connection(raw, "postgres")
            from ..schema_lineage import inspect
            version = inspect(wrapped).require_canonical((migrations.LATEST_VERSION,)).schema_version
            if version != migrations.LATEST_VERSION:
                raise RuntimeError(
                    f"Esquema restaurado {version}/{migrations.LATEST_VERSION}"
                )
            missing = [table for table in KEY_TABLES if table not in tables]
            if missing:
                raise RuntimeError(
                    f"Faltan tablas clave en el backup: {', '.join(missing)}"
                )
            expected_tables = header.get("tables", [])
            if tables != expected_tables:
                raise RuntimeError("La lista de tablas restaurada no está completa.")
            restored_counts = {
                table: int(
                    raw.execute(
                        sql.SQL("SELECT COUNT(*) AS total FROM {}").format(
                            sql.Identifier(table)
                        )
                    ).fetchone()["total"]
                )
                for table in expected_tables
            }
            if restored_counts != origin_counts:
                raise RuntimeError(
                    f"Los recuentos restaurados no cuadran: "
                    f"{restored_counts} != {origin_counts}"
                )


def _record_result(
    path: Path | None,
    status: str,
    storage: str,
    error: str | None = None,
) -> None:
    try:
        db.record_backup_result(
            path.name if path else None,
            path.stat().st_size if path and path.exists() else 0,
            status,
            storage,
            error,
        )
    except Exception as exc:  # noqa: BLE001
        log.error("No se pudo registrar el resultado del backup: %s", type(exc).__name__)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _documents_pair(database_path: Path) -> Path:
    for suffix in (".dump.gz", ".sql.gz", ".db", ".pgdump"):
        if database_path.name.endswith(suffix):
            return database_path.with_name(database_path.name[:-len(suffix)] + ".docs.zip")
    raise RuntimeError("Formato de copia no reconocido para asociar documentos.")


def _create_documents_backup(database_path: Path | None = None) -> Path:
    """Copia los documentos del volumen con rutas relativas y hashes verificables."""
    root = Path(config.DOCS_PATH)
    destination = _documents_pair(database_path) if database_path else _destination(".docs.zip")
    manifest: dict[str, str] = {}
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
    ) as archive:
        if root.exists():
            resolved_root = root.resolve()
            for path in sorted(root.rglob("*")):
                if path.is_symlink() or not path.is_file():
                    continue
                resolved = path.resolve()
                if resolved_root not in resolved.parents:
                    continue
                relative = path.relative_to(root).as_posix()
                archive.write(path, relative)
                manifest[relative] = _file_sha256(path)
        archive.writestr(
            ".noesis-manifest.json",
            json.dumps(manifest, sort_keys=True, separators=(",", ":")),
        )
    return destination


def _verify_documents_backup(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("El ZIP de documentos está corrupto.")
        try:
            manifest = json.loads(
                archive.read(".noesis-manifest.json").decode("utf-8")
            )
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("El backup de documentos no tiene manifiesto válido.") from exc
        expected = set(manifest)
        actual = {
            name for name in archive.namelist()
            if name != ".noesis-manifest.json"
        }
        if actual != expected:
            raise RuntimeError("El backup de documentos está incompleto.")
        for name, expected_hash in manifest.items():
            digest = hashlib.sha256(archive.read(name)).hexdigest()
            if not hmac.compare_digest(digest, expected_hash):
                raise RuntimeError(f"El documento {name} no supera la verificación.")


def _aws_signing_key(secret: str, day: str, region: str) -> bytes:
    date_key = hmac.new(
        ("AWS4" + secret).encode(), day.encode(), hashlib.sha256
    ).digest()
    region_key = hmac.new(date_key, region.encode(), hashlib.sha256).digest()
    service_key = hmac.new(region_key, b"s3", hashlib.sha256).digest()
    return hmac.new(service_key, b"aws4_request", hashlib.sha256).digest()


def _upload_offsite(path: Path) -> bool | None:
    """Sube por S3 Signature V4 solo cuando están todas las credenciales."""
    credentials = (
        config.BACKUP_S3_ENDPOINT,
        config.BACKUP_S3_BUCKET,
        config.BACKUP_S3_ACCESS_KEY,
        config.BACKUP_S3_SECRET_KEY,
    )
    if not any(credentials):
        return None
    legal_context = (
        config.BACKUP_S3_REGION,
        config.BACKUP_S3_PROVIDER_NAME,
        config.BACKUP_S3_DATA_REGION,
    )
    if not all(credentials) or not all(legal_context):
        log.error("Configuración S3 de backups incompleta; no se sube la copia.")
        return False

    parsed = urlsplit(config.BACKUP_S3_ENDPOINT.rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        log.error("NOESIS_BACKUP_S3_ENDPOINT no es una URL HTTP válida.")
        return False
    if config.IS_PRODUCTION and parsed.scheme != "https":
        log.error("Los backups externos deben usar HTTPS en producción.")
        return False
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        log.error("El endpoint S3 no admite credenciales, query ni fragmento.")
        return False
    if config.IS_PRODUCTION and not config.BACKUP_S3_SSE:
        log.error("La copia externa requiere cifrado solicitado en producción.")
        return False
    prefix = config.BACKUP_S3_PREFIX.strip("/")
    object_key = "/".join(part for part in (prefix, path.name) if part)
    base_path = parsed.path.rstrip("/")
    canonical_uri = (
        f"{base_path}/{quote(config.BACKUP_S3_BUCKET, safe='')}/"
        f"{quote(object_key, safe='/')}"
    )
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    day = now.strftime("%Y%m%d")
    region = config.BACKUP_S3_REGION
    payload_hash = _file_sha256(path)
    # S3 exige checksum para subir a un bucket con retención Object Lock.
    # MD5 se usa solo como checksum de transporte; la firma sigue siendo SHA-256.
    checksum = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(chunk)
    content_md5 = base64.b64encode(checksum.digest()).decode("ascii")
    host = parsed.netloc
    canonical_headers = (
        f"content-md5:{content_md5}\n"
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "content-md5;host;x-amz-content-sha256;x-amz-date"
    if config.BACKUP_S3_SSE:
        canonical_headers += (
            f"x-amz-server-side-encryption:{config.BACKUP_S3_SSE}\n"
        )
        signed_headers += ";x-amz-server-side-encryption"
    canonical_request = (
        f"PUT\n{canonical_uri}\n\n{canonical_headers}\n"
        f"{signed_headers}\n{payload_hash}"
    )
    scope = f"{day}/{region}/s3/aws4_request"
    string_to_sign = (
        "AWS4-HMAC-SHA256\n"
        f"{amz_date}\n{scope}\n"
        f"{hashlib.sha256(canonical_request.encode()).hexdigest()}"
    )
    signature = hmac.new(
        _aws_signing_key(config.BACKUP_S3_SECRET_KEY, day, region),
        string_to_sign.encode(),
        hashlib.sha256,
    ).hexdigest()
    authorization = (
        "AWS4-HMAC-SHA256 "
        f"Credential={config.BACKUP_S3_ACCESS_KEY}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    connection_class = (
        http.client.HTTPSConnection
        if parsed.scheme == "https"
        else http.client.HTTPConnection
    )
    connection = connection_class(
        parsed.hostname,
        parsed.port,
        timeout=config.BACKUP_S3_TIMEOUT_SECONDS,
    )
    try:
        connection.putrequest("PUT", canonical_uri, skip_host=True)
        connection.putheader("Host", host)
        connection.putheader("Content-Length", str(path.stat().st_size))
        connection.putheader("Content-Type", "application/octet-stream")
        connection.putheader("Content-MD5", content_md5)
        connection.putheader("x-amz-content-sha256", payload_hash)
        connection.putheader("x-amz-date", amz_date)
        if config.BACKUP_S3_SSE:
            connection.putheader(
                "x-amz-server-side-encryption", config.BACKUP_S3_SSE
            )
        connection.putheader("Authorization", authorization)
        connection.endheaders()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                connection.send(chunk)
        response = connection.getresponse()
        response.read()
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f"S3 respondió HTTP {response.status}")
        log.info("Backup subido fuera del servidor: %s", path.name)
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("Fallo subiendo el backup fuera del servidor: %s", type(exc).__name__)
        return False
    finally:
        connection.close()


def offsite_destination_id() -> str:
    """Huella del destino, sin publicar endpoint, bucket ni credenciales."""
    values = (
        config.BACKUP_S3_ENDPOINT, config.BACKUP_S3_BUCKET,
        config.BACKUP_S3_PREFIX, config.BACKUP_S3_REGION,
        config.BACKUP_S3_PROVIDER_NAME, config.BACKUP_S3_DATA_REGION,
        config.BACKUP_S3_SSE,
    )
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()


def _upload_backup_set(database_path: Path, documents_path: Path) -> None:
    if not any((config.BACKUP_S3_ENDPOINT, config.BACKUP_S3_BUCKET,
                config.BACKUP_S3_ACCESS_KEY, config.BACKUP_S3_SECRET_KEY)):
        return
    metadata = {"destination_id": offsite_destination_id()}
    # Si se interrumpe el proceso no queda un éxito anterior como último intento.
    db.record_security_event("backup.offsite_started", area="backups", metadata=metadata)
    try:
        database_ok = _upload_offsite(database_path) is True
        documents_ok = _upload_offsite(documents_path) is True
        manifest_ok = (database_path.suffix != ".pgdump" or
                       _upload_offsite(native.pair(database_path, ".manifest.json")) is True)
    except Exception as exc:  # noqa: BLE001 - la copia local sigue siendo válida
        log.error("Subida externa interrumpida: %s", type(exc).__name__)
        database_ok = documents_ok = manifest_ok = False
    passed = database_ok and documents_ok and manifest_ok
    db.record_security_event(
        "backup.offsite_passed" if passed else "backup.offsite_failed",
        severity="info" if passed else "critical", area="backups",
        metadata={**metadata, "database_ok": database_ok, "archive_ok": documents_ok,
                  "manifest_ok": manifest_ok},
    )


def run_backup() -> Path | None:
    """Crea, restaura y valida una copia antes de rotar o subirla fuera."""
    storage = "postgres" if config.DATABASE_URL else "sqlite"
    destination: Path | None = None
    documents_backup: Path | None = None
    try:
        if config.DATABASE_URL:
            destination, origin_counts = _create_postgres_backup()
            _verify_postgres_backup(destination, origin_counts)
        else:
            created = _create_sqlite_backup()
            if created is None:
                return None
            destination, origin_counts = created
            _verify_sqlite_backup(destination, origin_counts)
        documents_backup = (_documents_pair(destination) if destination.suffix == ".pgdump"
                            else _create_documents_backup(destination))
        _verify_documents_backup(documents_backup)
    except Exception as exc:  # noqa: BLE001
        error = str(exc) if isinstance(exc, BackupError) or storage == "sqlite" else "POSTGRES_BACKUP_FAILED"
        log.error("Fallo creando o verificando el backup %s: %s", storage, error)
        if destination is not None and destination.suffix == ".pgdump":
            for suffix in (".pgdump", ".docs.zip", ".manifest.json"):
                native.pair(destination, suffix).unlink(missing_ok=True)
        _record_result(destination, "error", storage, error)
        # No se rota: una verificación fallida jamás elimina la última copia buena.
        return destination

    _record_result(destination, "ok", storage)
    _rotate()
    if documents_backup is not None:
        _upload_backup_set(destination, documents_backup)
    log.info(
        "Copia de seguridad verificada: %s (%d bytes)",
        destination.name,
        destination.stat().st_size,
    )
    return destination


def _rotate() -> None:
    paths = [path for path in _backup_dir().glob("noesis-*") if path.is_file()]
    # V2 rota el set completo. No contar archives incompletos como copias buenas.
    native_sets = []
    for archive in paths:
        if archive.suffix == ".pgdump":
            try:
                native.load_set(archive, _verify_documents_backup)
            except BackupError:
                continue
            native_sets.append(archive)
    for old in sorted(native_sets, key=lambda path: path.name)[:-KEEP]:
        for suffix in (".pgdump", ".docs.zip", ".manifest.json"):
            native.pair(old, suffix).unlink(missing_ok=True)
    native_docs = {native.pair(path, ".docs.zip") for path in paths if path.suffix == ".pgdump"}
    paths = [path for path in paths if path not in native_docs]
    groups = (
        [
            path for path in paths
            if path.name.endswith((".db", ".dump.gz", ".sql.gz"))
        ],
        [path for path in paths if path.name.endswith(".docs.zip")],
    )
    for copies in groups:
        for old in sorted(copies, key=lambda path: path.name)[:-KEEP]:
            try:
                old.unlink()
            except OSError:
                log.warning("No se pudo eliminar la copia antigua %s", old.name)


def latest_verified_backup() -> Path | None:
    record = db.latest_backup_run(status="ok")
    if not record or not record.get("filename"):
        return None
    directory = _backup_dir().resolve()
    candidate = (directory / record["filename"]).resolve()
    if candidate.parent != directory or not candidate.is_file():
        return None
    if candidate.suffix == ".pgdump":
        try:
            native.load_set(candidate, _verify_documents_backup)
        except BackupError:
            return None
    return candidate


def download_file(path: Path) -> tuple[Path, bool]:
    """V2 se descarga completo. El llamador elimina sólo el ZIP temporal devuelto."""
    if path.suffix != ".pgdump":
        return path, False
    native.load_set(path, _verify_documents_backup)
    descriptor, name = tempfile.mkstemp(prefix="noesis-backup-set-", suffix=".zip")
    os.close(descriptor)
    bundle = Path(name)
    try:
        with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_STORED) as archive:
            for suffix in (".pgdump", ".docs.zip", ".manifest.json"):
                part = native.pair(path, suffix)
                archive.write(part, part.name)
        return bundle, True
    except Exception:
        bundle.unlink(missing_ok=True)
        raise BackupError("BACKUP_DOWNLOAD_SET_FAILED") from None


def verify_latest_backup_set() -> dict:
    """Repite una restauracion aislada del ultimo juego de copias disponible.

    Es independiente de la verificacion hecha al crear la copia. No toca el
    esquema real: SQLite usa un temporal y PostgreSQL un esquema desechable.
    """
    started = monotonic_time.monotonic()
    database_path = latest_verified_backup()
    documents_path = _documents_pair(database_path) if database_path else None
    storage = "postgres" if config.DATABASE_URL else "sqlite"
    native_result = None
    try:
        if database_path is None:
            raise RuntimeError("No hay una copia de base de datos verificada.")
        if storage == "postgres":
            if database_path.suffix == ".pgdump":
                expected = native.load_set(database_path, _verify_documents_backup)["table_counts"]
            else:
                with gzip.open(database_path, "rt", encoding="utf-8") as source:
                    header = json.loads(source.readline())
                expected = {str(table): int(total) for table, total in (header.get("counts") or {}).items()}
            if not expected:
                raise RuntimeError("La copia PostgreSQL no declara sus recuentos.")
            native_result = _verify_postgres_backup(database_path, expected)
        else:
            with closing(sqlite3.connect(database_path)) as source:
                expected = _sqlite_counts(source)
            _verify_sqlite_backup(database_path, expected)
        if documents_path is None or not documents_path.is_file():
            raise RuntimeError(
                "No hay un ZIP asociado a esta base. Crea un nuevo juego de copias; "
                "los juegos históricos requieren identificar su pareja manualmente."
            )
        _verify_documents_backup(documents_path)
    except Exception as exc:  # noqa: BLE001 - debe dejar evidencia y devolver estado
        duration = round(monotonic_time.monotonic() - started, 3)
        db.record_security_event(
            "backup.restore_drill_failed",
            severity="critical",
            area="backups",
            metadata={
                "storage": storage,
                "duration_seconds": duration,
                "error_type": type(exc).__name__,
            },
        )
        return {
            "ok": False,
            "storage": storage,
            "duration_seconds": duration,
            "error": (str(exc)[:300] if isinstance(exc, BackupError) or storage == "sqlite"
                      else "POSTGRES_RESTORE_CHECK_FAILED"),
        }
    duration = round(monotonic_time.monotonic() - started, 3)
    db.record_security_event(
        "backup.restore_drill_technical_passed" if native_result else "backup.restore_drill_passed",
        severity="info",
        area="backups",
        metadata={"storage": storage, "duration_seconds": duration},
    )
    return {
        "ok": True,
        "storage": storage,
        "duration_seconds": duration,
        "error": None,
        **(native_result or {}),
    }


def restore_check_main() -> int:
    """Entrada CLI para el simulacro; devuelve codigo no cero si falla."""
    parser = argparse.ArgumentParser(description="Verificación técnica de copias aisladas")
    parser.add_argument("--native-archive", type=Path)
    args = parser.parse_args()
    if args.native_archive:
        # Herramienta de recovery, no arranque de app73 sobre DB79 ni reconciliación E.
        try:
            result = native.verify(args.native_archive, _verify_documents_backup)
        except Exception as exc:  # noqa: BLE001 - nunca publicar SQL/DSN del driver
            print(json.dumps({"technical_integrity": "FAIL",
                              "error": str(exc) if isinstance(exc, BackupError) else "NATIVE_RESTORE_FAILED"}))
            return 2
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    db.init_db(auto_migrate=not bool(config.DATABASE_URL))
    result = verify_latest_backup_set()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


def admin_backup_status() -> dict:
    latest = db.latest_backup_run()
    verified = latest_verified_backup()
    if not latest:
        return {
            "created_at": None,
            "size_bytes": 0,
            "size_human": "—",
            "status": None,
            "error": None,
            "download_available": False,
        }
    size = int(latest.get("size_bytes") or 0)
    if size >= 1024 * 1024:
        size_human = f"{size / (1024 * 1024):.1f} MB"
    elif size >= 1024:
        size_human = f"{size / 1024:.1f} KB"
    else:
        size_human = f"{size} B"
    return {
        **latest,
        "size_human": size_human,
        "download_available": verified is not None,
        "download_filename": verified.name if verified else None,
    }
