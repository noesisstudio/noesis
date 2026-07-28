"""Pruebas del centro CISO, auditoria inmutable, antivirus y restauracion."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noesis import config, db, migrations, security_center
from noesis.documents import malware, service
from noesis.web import backups
from tests.fixtures import TINY_JPEG


class SecurityOperationsTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.original = {
            name: getattr(config, name)
            for name in (
                "DB_PATH", "DOCS_PATH", "BACKUP_DIR", "DATABASE_URL",
                "CLAMAV_HOST", "CLAMAV_PORT", "CLAMAV_TIMEOUT_SECONDS",
                "CLAMAV_REQUIRED", "BACKUP_S3_ENDPOINT", "BACKUP_S3_BUCKET",
                "BACKUP_S3_ACCESS_KEY", "BACKUP_S3_SECRET_KEY",
            )
        }
        root = Path(self.temporary.name)
        config.DATABASE_URL = ""
        config.DB_PATH = root / "security-operations.db"
        config.DOCS_PATH = root / "uploads"
        config.BACKUP_DIR = root / "backups"
        config.CLAMAV_HOST = ""
        config.CLAMAV_REQUIRED = False
        config.BACKUP_S3_ENDPOINT = ""
        config.BACKUP_S3_BUCKET = ""
        config.BACKUP_S3_ACCESS_KEY = ""
        config.BACKUP_S3_SECRET_KEY = ""
        db.init_db()

    def tearDown(self):
        for name, value in self.original.items():
            setattr(config, name, value)
        self.temporary.cleanup()

    def test_security_log_is_chained_sanitized_and_append_only(self):
        first = db.record_security_event(
            "admin.panel_viewed",
            area="admin",
            actor_user_id=7,
            request_id="request-12345678",
            metadata={
                "storage": "sqlite",
                "email": "must-not-be-stored@example.com",
                "token_value": "must-not-be-stored",
            },
        )
        second = db.record_security_event(
            "backup.restore_drill_passed", area="backups"
        )

        self.assertEqual(first["metadata"], {"storage": "sqlite"})
        self.assertEqual(second["previous_hash"], first["event_hash"])
        self.assertTrue(db.security_event_integrity()["ok"])
        with db.get_conn() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "UPDATE security_events SET severity='critical' WHERE id=?",
                    (first["id"],),
                )
        with db.get_conn() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM security_events WHERE id=?", (first["id"],))

    def test_migration_35_roundtrip_reinstalls_security_guards(self):
        # Se compara contra la última versión, no contra un número fijo: así el
        # test sigue cubriendo el ciclo cuando se añaden migraciones nuevas.
        self.assertEqual(migrations.current_version(), migrations.LATEST_VERSION)
        # La 34 es la anterior a que existiera la bitácora de seguridad.
        self.assertEqual(migrations.downgrade(34), 34)
        with db.get_conn() as conn:
            table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='security_events'"
            ).fetchone()
        self.assertIsNone(table)
        self.assertEqual(migrations.upgrade(), migrations.LATEST_VERSION)
        db.record_security_event("security.migration_verified")

    def test_clamav_protocol_clean_and_malware(self):
        class FakeSocket:
            def __init__(self, response: bytes):
                self.response = response
                self.sent = bytearray()

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def settimeout(self, _timeout):
                pass

            def sendall(self, payload):
                self.sent.extend(payload)

            def recv(self, _size):
                response, self.response = self.response, b""
                return response

        config.CLAMAV_HOST = "clamav.internal"
        clean_socket = FakeSocket(b"stream: OK\0")
        with patch.object(malware.socket, "create_connection", return_value=clean_socket):
            self.assertEqual(malware.scan(TINY_JPEG).status, "clean")
        self.assertTrue(clean_socket.sent.startswith(b"zINSTREAM\0"))

        infected = FakeSocket(b"stream: Eicar-Test-Signature FOUND\0")
        with patch.object(malware.socket, "create_connection", return_value=infected):
            result = malware.scan(TINY_JPEG)
        self.assertEqual(result.status, "malware")
        self.assertEqual(result.signature, "Eicar-Test-Signature")

    def test_required_scanner_fails_closed_before_storage(self):
        business = db.create_business("Documentos seguros", "owner@example.com")
        config.CLAMAV_HOST = "clamav.internal"
        config.CLAMAV_REQUIRED = True
        with (
            patch.object(
                malware, "scan", side_effect=malware.ScannerUnavailable("caido")
            ),
            self.assertRaises(service.UploadError),
        ):
            service.upload(business["id"], "foto.jpg", TINY_JPEG, run_ocr=False)
        self.assertFalse((config.DOCS_PATH / str(business["id"])).exists())
        event = db.list_security_events(1)[0]
        self.assertEqual(event["event_type"], "document.scan_unavailable")

    def test_independent_restore_drill_records_evidence(self):
        db.create_business("Copia", "backup@example.com")
        self.assertIsNotNone(backups.run_backup())

        result = backups.verify_latest_backup_set()

        self.assertTrue(result["ok"])
        self.assertEqual(
            db.list_security_events(1)[0]["event_type"],
            "backup.restore_drill_passed",
        )

    def test_ciso_report_is_read_only_and_actionable(self):
        db.record_security_event("admin.panel_viewed", area="admin")
        before = len(db.list_security_events())

        report = security_center.build_security_report()

        self.assertIn(report["status"], {"verde", "ambar", "rojo"})
        self.assertGreaterEqual(report["score"], 0)
        self.assertLessEqual(report["score"], 10)
        self.assertTrue(any(item["control"] == "Bitacora de seguridad"
                            for item in report["findings"]))
        self.assertEqual(len(db.list_security_events()), before)

    def test_auth_pressure_is_aggregated_without_identifiers(self):
        db.record_auth_attempt(
            "hash-no-reversible", "2099-01-01T10:00:00",
            keep_since="2099-01-01T09:00:00",
        )
        summary = db.auth_attempt_summary()
        self.assertEqual(summary["attempts"], 1)
        self.assertEqual(summary["pseudonymous_keys"], 1)
        self.assertNotIn("hash-no-reversible", str(summary))


if __name__ == "__main__":
    unittest.main()
