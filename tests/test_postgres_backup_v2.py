"""Contratos y fallos seguros sin servidor ni datos reales."""
import gzip
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from psycopg.conninfo import make_conninfo

from noesis.web import backups, postgres_native_backup as native
from noesis.web import postgres_backup_tools as tools
from noesis.web.postgres_backup_inventory import constraint_semantics, digest


class NativeBackupContracts(unittest.TestCase):
    def test_A_dump_major_enforced(self):
        for major in (16, 17, 19):
            with self.subTest(major=major), patch.dict(os.environ, {"NOESIS_POSTGRES_BIN": "/fixture"}), patch.object(tools, "run", return_value=f"pg_dump (PostgreSQL) {major}.1"):
                with self.assertRaisesRegex(tools.BackupError, "MAJOR_18"):
                    tools.Toolchain.discover()

    def test_B_restore_major_enforced(self):
        with patch.dict(os.environ, {"NOESIS_POSTGRES_BIN": "/fixture"}), patch.object(tools, "run", side_effect=["pg_dump (PostgreSQL) 18.6", "pg_restore (PostgreSQL) 17.9"]):
            with self.assertRaisesRegex(tools.BackupError, "MAJOR_18"):
                tools.Toolchain.discover()

    def test_server_newer_than_dump_fails(self):
        with self.assertRaisesRegex(tools.BackupError, "OLDER_THAN_SERVER"):
            tools.Toolchain(Path("/bin"), "18.6", "18.6").check_server(19)

    def test_V_stderr_and_secrets_are_not_exposed(self):
        result = subprocess.CompletedProcess(["pg_dump"], 1, b"", b"password=synthetic-not-a-secret SQL customer")
        with patch.object(tools.subprocess, "run", return_value=result) as process:
            with self.assertRaisesRegex(tools.BackupError, "^NATIVE_TOOL_FAILED$"):
                tools.run(["pg_dump", "--version"])
        self.assertFalse(process.call_args.kwargs["shell"])
        self.assertEqual(process.call_args.kwargs["timeout"], 900)
        self.assertTrue(process.call_args.kwargs["capture_output"])

    def test_timeout_has_no_argv_or_stderr(self):
        with patch.object(tools.subprocess, "run", side_effect=subprocess.TimeoutExpired("secret", 1, stderr=b"secret")):
            with self.assertRaisesRegex(tools.BackupError, "^NATIVE_TOOL_UNAVAILABLE_OR_TIMEOUT$"):
                tools.run(["pg_dump"])

    def test_environment_does_not_inherit_credentials(self):
        with patch.dict(os.environ, {"PGPASSWORD": "fixture", "DATABASE_URL": "fixture", "AWS_SECRET_ACCESS_KEY": "fixture"}):  # pragma: allowlist secret - sólo fixture
            env = tools.safe_environment()
        self.assertFalse(set(env) & {"PGPASSWORD", "DATABASE_URL", "AWS_SECRET_ACCESS_KEY"})

    @unittest.skipUnless(os.name == "posix", "Permisos POSIX verificados en matriz PostgreSQL")
    def test_private_password_file_lifetime(self):
        with tools.libpq_environment(make_conninfo(host="/tmp/fixture", dbname="fixture", user="fixture", password="fixture")) as env:  # pragma: allowlist secret - contraseña ficticia de test
            path = Path(env["PGPASSFILE"])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
            self.assertNotIn("PGPASSWORD", env)
            self.assertNotIn("password", " ".join(env))
        self.assertFalse(path.exists())

    def test_connection_options_not_silently_dropped(self):
        with self.assertRaisesRegex(tools.BackupError, "UNSUPPORTED_CONNECTION_OPTION"):
            with tools.libpq_environment("service=fixture"):
                self.fail("No debe aceptar servicios libpq ambientales")

    def test_X_arbitrary_destination_rejected(self):
        for target in (True, "arbitrary-target", Mock(), {"is_test": True}):
            with self.assertRaisesRegex(tools.BackupError, "DISPOSABLE_TARGET_REQUIRED"):
                native.restore(Path("fixture.pgdump"), target, Mock())

    def test_unsealed_target_cannot_be_created(self):
        with self.assertRaisesRegex(tools.BackupError, "DISPOSABLE_TARGET_REQUIRED"):
            tools._DisposableTarget(object(), "fixture", "fixture", Path("/tmp"), None)

    def test_outbound_interface_blocks_restore(self):
        with patch.object(tools.socket, "if_nameindex", return_value=[(1, "lo"), (2, "eth0")]):
            self.assertFalse(tools.outbound_blocked())

    def test_U_legacy_newer_header_rejected_before_any_sql(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "v1.dump.gz"
            with gzip.open(path, "wt") as stream:
                json.dump({"format": backups.POSTGRES_DUMP_FORMAT, "schema_version": 79,
                           "tables": ["future_unknown"]}, stream)
                stream.write("\n")
            connection = Mock()
            with patch.object(backups.migrations, "upgrade_connection") as upgrade:
                with self.assertRaisesRegex(tools.BackupError, "LEGACY_BACKUP_REQUIRES_NEWER_SCHEMA_CATALOG"):
                    backups._restore_postgres_dump(connection, path)
            upgrade.assert_not_called()
            connection.execute.assert_not_called()
            with patch.object(backups, "disposable_target") as target:
                with self.assertRaisesRegex(tools.BackupError, "LEGACY_BACKUP_REQUIRES_NEWER_SCHEMA_CATALOG"):
                    backups._verify_postgres_backup(path, {})
            target.assert_not_called()

    def test_O_missing_set_before_target_created(self):
        with patch.object(native, "disposable_target") as target:
            with self.assertRaisesRegex(tools.BackupError, "BACKUP_SET_INCOMPLETE"):
                native.verify(Path("missing.pgdump"), Mock())
        target.assert_not_called()

    def test_native_pair_is_explicit(self):
        path = Path("a.pgdump")
        self.assertEqual(backups._documents_pair(path), Path("a.docs.zip"))
        self.assertEqual(native.pair(path, ".manifest.json"), Path("a.manifest.json"))

    def test_unknown_suffix_not_interpreted(self):
        with self.assertRaises(tools.BackupError):
            native.pair(Path("a.sql"), ".manifest.json")

    def test_failed_native_verification_no_rotation_or_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "a.pgdump"
            for suffix in (".pgdump", ".docs.zip", ".manifest.json"):
                native.pair(path, suffix).write_bytes(b"partial")
            with (patch.object(backups.config, "DATABASE_URL", "unused"),
                  patch.object(backups, "_create_postgres_backup", return_value=(path, {})),
                  patch.object(backups, "_verify_postgres_backup", side_effect=tools.BackupError("NATIVE_TOOL_FAILED")),
                  patch.object(backups, "_record_result") as record,
                  patch.object(backups, "_rotate") as rotate,
                  patch.object(backups, "_upload_backup_set") as upload):
                backups.run_backup()
            record.assert_called_once_with(path, "error", "postgres", "NATIVE_TOOL_FAILED")
            rotate.assert_not_called()
            upload.assert_not_called()
            self.assertFalse(path.exists())

    def test_sqlite_monetary_encoding_legacy_not_changed(self):
        self.assertEqual(backups._encode_value(1.5), 1.5)

    def test_check_canonicalization_only_associative_booleans(self):
        a = constraint_semantics("CHECK ((x>0 AND y>0) AND z>0)")
        b = constraint_semantics("CHECK (x>0 AND y>0 AND z>0)")
        self.assertEqual(a, b)
        for change in ("CHECK ((x>0 OR y>0) AND z>0)", "CHECK (x>1 AND y>0 AND z>0)",
                       "CHECK (x>0 AND y>0 OR z>0)"):
            self.assertNotEqual(a, constraint_semantics(change))
        self.assertNotEqual(constraint_semantics("CHECK ((x+y)*z>0)"),
                            constraint_semantics("CHECK (x+y*z>0)"))
        self.assertNotEqual(constraint_semantics("CHECK (label='AND')"),
                            constraint_semantics("CHECK (label='OR')"))

    def test_raw_money_hash_preserves_decimal_precision(self):
        from decimal import Decimal
        self.assertNotEqual(digest([Decimal("10000000000000.0001")]),
                            digest([Decimal("10000000000000.0002")]))

    def test_download_native_complete_set_and_legacy_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.pgdump"
            for suffix in (".pgdump", ".docs.zip", ".manifest.json"):
                native.pair(path, suffix).write_bytes(b"fixture")
            with patch.object(native, "load_set"):
                bundle, temporary = backups.download_file(path)
            try:
                import zipfile
                with zipfile.ZipFile(bundle) as archive:
                    self.assertEqual(set(archive.namelist()),
                                     {"fixture.pgdump", "fixture.docs.zip", "fixture.manifest.json"})
                self.assertTrue(temporary)
            finally:
                bundle.unlink()
            legacy = Path(directory) / "fixture.db"
            self.assertEqual(backups.download_file(legacy), (legacy, False))


if __name__ == "__main__":
    unittest.main()
