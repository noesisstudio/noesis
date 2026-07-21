from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from noesis import config, db, migrations
from noesis.web import auth, backups


class VerifiedBackupTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.original = {
            "DB_PATH": config.DB_PATH,
            "BACKUP_DIR": config.BACKUP_DIR,
            "DOCS_PATH": config.DOCS_PATH,
            "DATABASE_URL": config.DATABASE_URL,
            "BACKUP_S3_ENDPOINT": config.BACKUP_S3_ENDPOINT,
            "BACKUP_S3_BUCKET": config.BACKUP_S3_BUCKET,
            "BACKUP_S3_ACCESS_KEY": config.BACKUP_S3_ACCESS_KEY,
            "BACKUP_S3_SECRET_KEY": config.BACKUP_S3_SECRET_KEY,
        }
        root = Path(self.temporary.name)
        config.DATABASE_URL = ""
        config.DB_PATH = root / "noesis.db"
        config.BACKUP_DIR = root / "backups"
        config.DOCS_PATH = root / "uploads"
        config.BACKUP_S3_ENDPOINT = ""
        config.BACKUP_S3_BUCKET = ""
        config.BACKUP_S3_ACCESS_KEY = ""
        config.BACKUP_S3_SECRET_KEY = ""
        db.init_db()

    def tearDown(self):
        for name, value in self.original.items():
            setattr(config, name, value)
        self.temporary.cleanup()

    def _business_with_data(self, name: str = "Backup Seguro"):
        business = db.create_business(name, "backup@example.com")
        client = db.add_client("Cliente recuperable", business_id=business["id"])
        worker = db.create_worker(business["id"], "Trabajador recuperable")
        db.clock_worker(business["id"], worker["id"], "entrada", "web")
        return business, client

    def test_sqlite_backup_roundtrip_is_verified_and_recorded(self):
        business, _client = self._business_with_data()

        path = backups.run_backup()

        self.assertIsNotNone(path)
        self.assertTrue(path.is_file())
        self.assertEqual(path.suffix, ".db")
        result = db.latest_backup_run()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["filename"], path.name)
        self.assertGreater(result["size_bytes"], 0)
        self.assertEqual(backups.latest_verified_backup(), path)
        with db.get_conn() as conn:
            event = conn.execute(
                "SELECT event_data FROM product_events "
                "WHERE business_id=? AND event_name='backup_verificado' "
                "ORDER BY id DESC LIMIT 1",
                (business["id"],),
            ).fetchone()
        self.assertEqual(json.loads(event["event_data"])["status"], "ok")

        # La propia verificación ya restauró en un archivo desechable. Además
        # comprobamos que el artefacto conserva las filas clave del origen.
        import sqlite3

        with closing(sqlite3.connect(path)) as restored:
            version = restored.execute(
                "SELECT MAX(version) FROM schema_migrations"
            ).fetchone()[0]
            clients = restored.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
            clockins = restored.execute(
                "SELECT COUNT(*) FROM worker_clockins"
            ).fetchone()[0]
        self.assertEqual(version, migrations.LATEST_VERSION)
        self.assertEqual(clients, 1)
        self.assertEqual(clockins, 1)

    def test_failed_verification_preserves_last_good_copy(self):
        self._business_with_data()
        good = backups.run_backup()

        with (
            patch.object(
                backups,
                "_verify_sqlite_backup",
                side_effect=RuntimeError("restauración inválida"),
            ),
            patch.object(backups, "_rotate") as rotate,
        ):
            failed = backups.run_backup()

        self.assertTrue(good.exists())
        self.assertTrue(failed.exists())
        rotate.assert_not_called()
        self.assertEqual(db.latest_backup_run()["status"], "error")
        self.assertEqual(backups.latest_verified_backup(), good)

    def test_backup_includes_and_verifies_uploaded_documents(self):
        from noesis.documents import service

        business, _client = self._business_with_data("Backup documentos")
        service.upload(
            business["id"], "factura.pdf", b"%PDF-documento",
            run_ocr=False,
        )

        database_path = backups.run_backup()
        documents = sorted(Path(config.BACKUP_DIR).glob("*.docs.zip"))

        self.assertIsNotNone(database_path)
        self.assertEqual(len(documents), 1)
        backups._verify_documents_backup(documents[0])

    def test_postgres_path_dumps_and_verifies_without_real_service(self):
        destination = Path(config.BACKUP_DIR) / "noesis-mocked.dump.gz"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"mock")
        config.DATABASE_URL = "postgresql://unused"
        counts = {table: 0 for table in backups.KEY_TABLES}

        with (
            patch.object(
                backups,
                "_create_postgres_backup",
                return_value=(destination, counts),
            ) as create,
            patch.object(backups, "_verify_postgres_backup") as verify,
            patch.object(backups, "_record_result") as record,
            patch.object(backups, "_rotate") as rotate,
            patch.object(backups, "_upload_offsite") as upload,
        ):
            result = backups.run_backup()

        self.assertEqual(result, destination)
        create.assert_called_once_with()
        verify.assert_called_once_with(destination, counts)
        record.assert_called_once_with(destination, "ok", "postgres")
        rotate.assert_called_once_with()
        self.assertEqual(upload.call_count, 2)
        upload.assert_any_call(destination)
        uploaded_documents = upload.call_args_list[1].args[0]
        self.assertTrue(uploaded_documents.name.endswith(".docs.zip"))

    def test_only_admin_can_download_latest_verified_backup(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        business, _client = self._business_with_data("Admin Backup")
        admin = db.create_user(
            "admin-backup@example.com",
            auth.hash_password("password-segura-123"),
            business["id"],
        )
        with db.get_conn() as conn:
            conn.execute("UPDATE users SET is_admin=1 WHERE id=?", (admin["id"],))
        normal_business = db.create_business("Usuario normal", "normal@example.com")
        normal = db.create_user(
            "normal-backup@example.com",
            auth.hash_password("password-segura-123"),
            normal_business["id"],
        )
        path = backups.run_backup()

        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                client.post(
                    "/login",
                    data={
                        "email": normal["email"],
                        "password": "password-segura-123",
                    },
                )
                self.assertEqual(
                    client.get("/admin/backups/latest").status_code, 403
                )

            with TestClient(server.app) as client:
                client.post(
                    "/login",
                    data={
                        "email": admin["email"],
                        "password": "password-segura-123",
                    },
                )
                panel = client.get("/admin")
                downloaded = client.get("/admin/backups/latest")

        self.assertEqual(panel.status_code, 200)
        self.assertIn("Verificación OK", panel.text)
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.content, path.read_bytes())
        event_types = [
            event["event_type"] for event in db.list_security_events(10)
        ]
        self.assertIn("admin.panel_viewed", event_types)
        self.assertIn("admin.backup_downloaded", event_types)


if __name__ == "__main__":
    unittest.main()
