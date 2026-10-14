"""Serving y ownership separados; ninguna reparación/migración desde startup."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noesis import config, db, migrations
from noesis.schema_lineage import SchemaLineageError
from noesis.web import server


class LineageStartupTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="noesis-startup-lineage-")
        self.addCleanup(directory.cleanup)
        settings = patch.multiple(config, DATABASE_URL="", DB_PATH=Path(directory.name) / "fixture.db",
                                 IS_PRODUCTION=False, RESET_DB=False, SEED_DEMO=False,
                                 INBOUND_EMAIL_ENABLED=False, ADMIN_REQUIRE_GOOGLE_OAUTH=False,
                                 CLAMAV_REQUIRED=False)
        settings.start()
        self.addCleanup(settings.stop)

    def test_canonical75_serves_without_init_db_or_upgrade(self):
        migrations.upgrade()
        with patch.object(db, "init_db", side_effect=AssertionError("DDL desde startup")), patch.object(server, "start_scheduler") as scheduler:
            server._startup()
            scheduler.assert_called_once()

    def test_canonical74_cannot_serve_or_auto_migrate(self):
        migrations.upgrade(74)
        with patch.object(db, "init_db", side_effect=AssertionError("DDL")), patch.object(server, "start_scheduler") as scheduler:
            with self.assertRaises(SchemaLineageError):
                server._startup()
            scheduler.assert_not_called()
        self.assertEqual(migrations.current_version(), 74)

    def test_legacy_wrong_or_missing_objects_block_workers(self):
        migrations.upgrade()
        with db.get_conn() as conn:
            conn.execute("DROP TRIGGER financial_readiness_evaluations_insert")
        with patch.object(server, "start_scheduler") as scheduler:
            with self.assertRaises(SchemaLineageError):
                server._startup()
            scheduler.assert_not_called()

    def test_ready_cannot_accept_numeric75_after_name_or_object_drift(self):
        from noesis.web.routers.webhooks import readiness
        migrations.upgrade()
        self.assertEqual(readiness()["status"], "ready")
        with db.get_conn() as conn:
            conn.execute("UPDATE schema_migrations SET name='wrong' WHERE version=74")
        self.assertEqual(readiness().status_code, 503)
        with db.get_conn() as conn:
            conn.execute("UPDATE schema_migrations SET name='captacion_hoja_y_tipo' WHERE version=74")
            conn.execute("DROP TRIGGER financial_readiness_evaluations_insert")
        self.assertEqual(readiness().status_code, 503)

    def test_sqlite_backup_verification_rejects_numeric75_wrong_lineage(self):
        from noesis.web import backups
        migrations.upgrade()
        with db.get_conn() as conn:
            conn.execute("UPDATE schema_migrations SET name='wrong' WHERE version=74")
        with self.assertRaises(SchemaLineageError):
            backups._verify_sqlite_backup(config.DB_PATH, {})


if __name__ == "__main__":
    unittest.main()
