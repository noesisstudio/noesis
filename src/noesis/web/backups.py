"""Copias verificadas de SQLite y Postgres.

SQLite conserva su copia consistente ``.db``. Postgres se vuelca mediante psycopg
a un formato lógico comprimido y portable dentro de Noesis. Cada copia se restaura
en una base o esquema desechable antes de rotarla o enviarla fuera del servidor.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import hmac
import http.client
import json
import logging
import sqlite3
import tempfile
import uuid
import zipfile
from contextlib import closing
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote, urlsplit

from .. import config, db, migrations

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
    directory.mkdir(parents=True, exist_ok=True)
    return directory


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
            version = restored.execute(
                "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
            ).fetchone()[0]
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
    if psycopg is None:
        raise RuntimeError("psycopg no está instalado.")
    destination = _destination(".dump.gz")
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
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
        version = int(
            conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS version "
                "FROM schema_migrations"
            ).fetchone()["version"]
        )
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


def _restore_postgres_dump(raw, path: Path) -> tuple[dict, list[str]]:
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
    return header, tables


def _verify_postgres_backup(path: Path, origin_counts: dict[str, int]) -> None:
    """Restaura en un esquema desechable de la misma instancia y luego lo elimina."""
    if psycopg is None:
        raise RuntimeError("psycopg no está instalado.")
    schema = f"noesis_backup_verify_{uuid.uuid4().hex}"
    with psycopg.connect(config.DATABASE_URL, autocommit=True) as control:
        control.execute(
            sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema))
        )
    try:
        with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as raw:
            raw.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
            )
            header, tables = _restore_postgres_dump(raw, path)
            if int(header.get("schema_version", 0)) != migrations.LATEST_VERSION:
                raise RuntimeError(
                    f"El backup declara el esquema "
                    f"{header.get('schema_version')}/{migrations.LATEST_VERSION}"
                )
            wrapped = db.Connection(raw, "postgres")
            version = migrations.current_version_connection(wrapped)
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
    finally:
        with psycopg.connect(config.DATABASE_URL, autocommit=True) as control:
            control.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(schema)
                )
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
        log.error("No se pudo registrar el resultado del backup: %s", exc)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _create_documents_backup() -> Path:
    """Copia los documentos del volumen con rutas relativas y hashes verificables."""
    root = Path(config.DOCS_PATH)
    destination = _destination(".docs.zip")
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
    values = (
        config.BACKUP_S3_ENDPOINT,
        config.BACKUP_S3_BUCKET,
        config.BACKUP_S3_ACCESS_KEY,
        config.BACKUP_S3_SECRET_KEY,
    )
    if not any(values):
        return None
    if not all(values):
        log.error("Configuración S3 de backups incompleta; no se sube la copia.")
        return False

    parsed = urlsplit(config.BACKUP_S3_ENDPOINT.rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        log.error("NOESIS_BACKUP_S3_ENDPOINT no es una URL HTTP válida.")
        return False
    if config.IS_PRODUCTION and parsed.scheme != "https":
        log.error("Los backups externos deben usar HTTPS en producción.")
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
    region = config.BACKUP_S3_REGION or "us-east-1"
    payload_hash = _file_sha256(path)
    host = parsed.netloc
    canonical_headers = (
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
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
        connection.putrequest("PUT", canonical_uri)
        connection.putheader("Host", host)
        connection.putheader("Content-Length", str(path.stat().st_size))
        connection.putheader("Content-Type", "application/octet-stream")
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
        log.error("Fallo subiendo el backup fuera del servidor: %s", exc)
        return False
    finally:
        connection.close()


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
        documents_backup = _create_documents_backup()
        _verify_documents_backup(documents_backup)
    except Exception as exc:  # noqa: BLE001
        log.error("Fallo creando o verificando el backup %s: %s", storage, exc)
        _record_result(destination, "error", storage, str(exc))
        # No se rota: una verificación fallida jamás elimina la última copia buena.
        return destination

    _record_result(destination, "ok", storage)
    _rotate()
    _upload_offsite(destination)
    if documents_backup is not None:
        _upload_offsite(documents_backup)
    log.info(
        "Copia de seguridad verificada: %s (%d bytes)",
        destination.name,
        destination.stat().st_size,
    )
    return destination


def _rotate() -> None:
    paths = [path for path in _backup_dir().glob("noesis-*") if path.is_file()]
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
    return candidate


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
