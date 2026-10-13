"""Herramientas nativas y destinos que este proceso posee; nunca una DSN de restore."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import socket
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import tuple_row


class BackupError(RuntimeError):
    """Sólo códigos estables: stderr, SQL y credenciales no salen del proceso."""


def run(argv: list[str], *, env: dict | None = None, timeout: int = 900) -> str:
    try:
        # Binarios locales verificados; nunca shell ni DSN en argv.
        result = subprocess.run(  # nosec B603
            argv, env=env, shell=False, capture_output=True, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise BackupError("NATIVE_TOOL_UNAVAILABLE_OR_TIMEOUT") from None
    if result.returncode:
        # No persistir stderr: puede contener SQL, parámetros, rutas o usuarios.
        raise BackupError("NATIVE_TOOL_FAILED")
    return result.stdout.decode("utf-8", errors="strict")


def safe_environment() -> dict[str, str]:
    # Ni PG*, DATABASE_URL, tokens o claves del proceso padre llegan al hijo.
    return {key: os.environ[key] for key in (
        "PATH", "LD_LIBRARY_PATH", "SYSTEMROOT", "WINDIR", "LANG", "TZ",
    ) if key in os.environ} | {"LC_ALL": "C", "PGCONNECT_TIMEOUT": "15"}


@contextmanager
def libpq_environment(dsn: str):
    values = conninfo_to_dict(dsn)
    allowed = {
        "host": "PGHOST", "hostaddr": "PGHOSTADDR", "port": "PGPORT",
        "dbname": "PGDATABASE", "user": "PGUSER", "sslmode": "PGSSLMODE",
        "sslrootcert": "PGSSLROOTCERT", "sslcert": "PGSSLCERT",
        "sslkey": "PGSSLKEY", "sslcrl": "PGSSLCRL",
        "channel_binding": "PGCHANNELBINDING", "target_session_attrs": "PGTARGETSESSIONATTRS",
        "connect_timeout": "PGCONNECT_TIMEOUT", "application_name": "PGAPPNAME",
    }
    if set(values) - set(allowed) - {"password"}:
        raise BackupError("LIBPQ_UNSUPPORTED_CONNECTION_OPTION")
    env = safe_environment()
    env.update({allowed[key]: value for key, value in values.items() if key in allowed})
    with tempfile.TemporaryDirectory(prefix="noesis-libpq-") as temporary:
        if os.name != "posix":
            raise BackupError("PRIVATE_PGPASS_REQUIRES_POSIX_PERMISSIONS")
        folder = Path(temporary)
        folder.chmod(0o700)
        password_file = folder / "pgpass"
        contents = ""
        if "password" in values:
            # Una entrada sólo para este endpoint. libpq usa localhost para socket UNIX.
            fields = [values.get("host", "localhost"), values.get("port", "5432"),
                      values.get("dbname", ""), values.get("user", ""), values["password"]]
            if (any("\n" in item or "\r" in item for item in fields)
                    or any("," in item or "*" in item for item in fields[:-1])):
                raise BackupError("LIBPQ_UNSUPPORTED_PASSWORD_FILE_FIELD")
            if fields[0].startswith("/"):
                fields[0] = "localhost"
            contents = ":".join(item.replace("\\", "\\\\").replace(":", "\\:")
                                for item in fields) + "\n"
        descriptor = os.open(password_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(contents)
        # También vacío: nunca caer en ~/.pgpass del usuario del worker.
        env["PGPASSFILE"] = str(password_file)
        yield env


@dataclass(frozen=True)
class Toolchain:
    directory: Path
    dump_version: str
    restore_version: str
    major: int = 18

    def binary(self, name: str) -> str:
        return str(self.directory / name)

    @classmethod
    def discover(cls):
        configured = os.environ.get("NOESIS_POSTGRES_BIN")
        found = shutil.which("pg_dump") if not configured else None
        if not configured and not found:
            raise BackupError("POSTGRES_TOOLCHAIN_REQUIRED")
        directory = Path(configured) if configured else Path(found).resolve().parent
        versions = []
        for name in ("pg_dump", "pg_restore", "initdb", "pg_ctl", "postgres"):
            version = run([str(directory / name), "--version"], env=safe_environment(), timeout=15).strip()
            match = re.fullmatch(r"\S+ \(PostgreSQL\) (\d+)\.[^\r\n]+", version)
            if not match or int(match[1]) != 18:
                raise BackupError("POSTGRES_TOOLCHAIN_MAJOR_18_REQUIRED")
            versions.append(version)
        return cls(directory.resolve(), versions[0], versions[1])

    def check_server(self, major: int):
        if major > self.major:
            raise BackupError("PG_DUMP_OLDER_THAN_SERVER")


def outbound_blocked() -> bool:
    """Prueba del namespace actual, no una afirmación de configuración."""
    if os.name != "posix" or {name for _, name in socket.if_nameindex()} - {"lo"}:
        return False
    # Un namespace sin interfaz externa carece de ruta hacia proveedores.
    return Path("/proc/net/route").is_file()


_OWNED = object()


class _DisposableTarget:
    __slots__ = ("_seal", "dsn", "identity", "directory", "toolchain", "active", "used")

    def __init__(self, seal, dsn, identity, directory, toolchain):
        if seal is not _OWNED:
            raise BackupError("DISPOSABLE_TARGET_REQUIRED")
        for key, value in (("_seal", seal), ("dsn", dsn), ("identity", identity),
                           ("directory", directory), ("toolchain", toolchain), ("active", True), ("used", False)):
            object.__setattr__(self, key, value)

    def __setattr__(self, name, value):
        raise AttributeError("Destino desechable inmutable")

    def consume(self):
        object.__setattr__(self, "used", True)

    def close(self):
        object.__setattr__(self, "active", False)

    def connection(self):
        if self._seal is not _OWNED or not self.active or not outbound_blocked():
            raise BackupError("DISPOSABLE_TARGET_REQUIRED")
        return psycopg.connect(self.dsn)

    def assert_empty(self, source_fingerprint: str):
        if self.used:
            raise BackupError("RESTORE_DESTINATION_NOT_EMPTY")
        with self.connection() as conn:
            if database_identity(conn) != self.identity or self.identity == source_fingerprint:
                raise BackupError("RESTORE_IDENTITY_MISMATCH")
            if conn.execute("SHOW listen_addresses").fetchone()[0] != "":
                raise BackupError("RESTORE_NETWORK_LISTENER_FORBIDDEN")
            if conn.execute("SHOW data_directory").fetchone()[0] != str(self.directory / "data"):
                raise BackupError("RESTORE_CLUSTER_NOT_OWNED")
            objects = conn.execute(
                "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'"
            ).fetchone()[0]
            functions = conn.execute(
                "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'"
            ).fetchone()[0]
            schemas = conn.execute(
                "SELECT count(*) FROM pg_namespace WHERE nspname !~ '^pg_' "
                "AND nspname NOT IN ('information_schema','public')"
            ).fetchone()[0]
            types = conn.execute(
                "SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace "
                "WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'"
            ).fetchone()[0]
            if objects or functions or schemas or types:
                raise BackupError("RESTORE_DESTINATION_NOT_EMPTY")


def database_identity(conn) -> str:
    # Identidad de instancia + OID/nombre, sin host, usuario ni password.
    with conn.cursor(row_factory=tuple_row) as cursor:
        row = cursor.execute(
            "SELECT system_identifier::text, (SELECT oid FROM pg_database WHERE datname=current_database()), "
            "current_database() FROM pg_control_system()"
        ).fetchone()
    return hashlib.sha256(repr(row).encode()).hexdigest()


def database_settings(conn) -> dict:
    with conn.cursor(row_factory=tuple_row) as cursor:
        row = cursor.execute(
            "SELECT pg_encoding_to_char(encoding),datlocprovider,datcollate,datctype,"
            "coalesce(to_jsonb(d)->>'datlocale',to_jsonb(d)->>'daticulocale'),datcollversion,"
            "to_jsonb(d)->>'daticurules' "
            "FROM pg_database d WHERE datname=current_database()"
        ).fetchone()
    return dict(zip(("encoding", "provider", "lc_collate", "lc_ctype", "locale", "collation_version", "icu_rules"), row))


def create_database_statement(name: str, settings: dict | None):
    statement = psycopg.sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(psycopg.sql.Identifier(name))
    if settings is None:
        return statement
    if set(settings) != {"encoding", "provider", "lc_collate", "lc_ctype", "locale", "collation_version", "icu_rules"}:
        raise BackupError("UNSUPPORTED_DATABASE_SETTINGS")
    providers = {"c": "libc", "i": "icu", "b": "builtin"}
    if settings["provider"] not in providers:
        raise BackupError("UNSUPPORTED_LOCALE_PROVIDER")
    for parameter, value in (("ENCODING", settings["encoding"]), ("LOCALE_PROVIDER", providers[settings["provider"]]),
                             ("LC_COLLATE", settings["lc_collate"]), ("LC_CTYPE", settings["lc_ctype"])):
        statement += psycopg.sql.SQL(" {} {}").format(psycopg.sql.SQL(parameter), psycopg.sql.Literal(value))
    if settings["provider"] in {"i", "b"}:
        parameter = "ICU_LOCALE" if settings["provider"] == "i" else "BUILTIN_LOCALE"
        statement += psycopg.sql.SQL(" {} {}").format(psycopg.sql.SQL(parameter), psycopg.sql.Literal(settings["locale"]))
    if settings["provider"] == "i" and settings["icu_rules"] is not None:
        statement += psycopg.sql.SQL(" ICU_RULES {}").format(psycopg.sql.Literal(settings["icu_rules"]))
    return statement


@contextmanager
def disposable_target(tools: Toolchain | None = None, *, settings: dict | None = None):
    """Crea una instancia nueva sin TCP en un namespace sin outbound. POSIX/no root."""
    if not outbound_blocked() or os.geteuid() == 0:
        raise BackupError("ISOLATED_NONROOT_RESTORE_WORKER_REQUIRED")
    tools = tools or Toolchain.discover()
    with tempfile.TemporaryDirectory(prefix="nv2-") as temporary:
        directory = Path(temporary)
        directory.chmod(0o700)
        socket_directory = directory / "socket"
        socket_directory.mkdir(mode=0o700)
        data = directory / "data"
        role = "restore_" + uuid.uuid4().hex
        run([tools.binary("initdb"), "-D", str(data), "--username=" + role,
             "--auth-local=trust", "--auth-host=reject", "--no-locale", "--encoding=UTF8"],
            env=safe_environment())
        with (data / "postgresql.conf").open("a") as output:
            output.write(f"\nlisten_addresses=''\nunix_socket_directories='{socket_directory}'\n"
                         "unix_socket_permissions=0700\nlog_statement='none'\n"
                         "log_min_error_statement='panic'\nlog_parameter_max_length_on_error=0\n")
        target = None
        try:
            # PostgreSQL tampoco persiste SQL/DETAIL de un archive fallido.
            run([tools.binary("pg_ctl"), "-D", str(data), "-l", os.devnull,
                 "-w", "start"], env=safe_environment(), timeout=60)
            dsn = make_conninfo(host=str(socket_directory), dbname="postgres", user=role)
            with psycopg.connect(dsn, autocommit=True) as conn:
                name = "restore_" + uuid.uuid4().hex
                conn.execute(create_database_statement(name, settings))
            dsn = make_conninfo(host=str(socket_directory), dbname=name, user=role)
            with psycopg.connect(dsn) as conn:
                if settings is not None and database_settings(conn) != settings:
                    raise BackupError("DATABASE_ENCODING_LOCALE_VERSION_MISMATCH")
                identity = database_identity(conn)
            target = _DisposableTarget(_OWNED, dsn, identity, directory, tools)
            yield target
        finally:
            if target:
                target.close()
            # Sólo el cluster nuevo creado aquí: ni DROP ni --clean sobre endpoints externos.
            if (data / "postmaster.pid").exists():
                run([tools.binary("pg_ctl"), "-D", str(data), "-m", "immediate", "-w", "stop"],
                    env=safe_environment(), timeout=60)
