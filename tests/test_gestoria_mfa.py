"""MFA profesional: activación, reto, anti-replay y recuperación de emergencia."""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from starlette.testclient import TestClient

from noesis import config, db, migrations
from noesis.web import auth, mfa, server


PASSWORD = "Clave-profesional-2026"


class GestoriaMfaTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_db_path = config.DB_PATH
        self.old_docs_path = config.DOCS_PATH
        self.old_database_url = config.DATABASE_URL
        config.DATABASE_URL = ""
        config.DB_PATH = Path(self.tempdir.name) / "test.db"
        config.DOCS_PATH = Path(self.tempdir.name) / "uploads"
        db.init_db()

    def tearDown(self):
        config.DB_PATH = self.old_db_path
        config.DOCS_PATH = self.old_docs_path
        config.DATABASE_URL = self.old_database_url
        self.tempdir.cleanup()

    def account(self, email: str = "segura@gestoria.example") -> dict:
        return db.create_gestoria_account(
            email, auth.hash_password(PASSWORD), "Gestoría Segura"
        )

    def test_migration_46_to_47_preserves_the_professional_account(self):
        migrations.downgrade(46)
        account = self.account("migracion@gestoria.example")
        migrations.upgrade(47)

        upgraded = db.get_gestoria_account(account["id"])
        self.assertFalse(upgraded["mfa_enabled"])
        self.assertEqual(upgraded["mfa_recovery_hashes"], "[]")
        self.assertEqual(upgraded["mfa_last_counter"], -1)

    def test_totp_is_standard_and_recovery_codes_have_offline_entropy(self):
        account = self.account()
        secret = mfa.secret_for(account)
        counter = int(time.time()) // 30
        code = mfa.code_for_counter(secret, counter)

        self.assertEqual(mfa.matching_counter(account, code), counter)
        self.assertIn("otpauth://totp/Noesis%3A", mfa.provisioning_uri(account))
        codes = mfa.generate_recovery_codes()
        self.assertEqual(len(codes), 8)
        self.assertEqual(len(set(codes)), 8)
        self.assertTrue(all(len(mfa.normalize_recovery_code(value)) == 16
                            for value in codes))

    def test_password_never_bypasses_mfa_and_each_factor_is_single_use(self):
        account = self.account()
        counter = int(time.time()) // 30
        totp = mfa.code_for_counter(mfa.secret_for(account), counter)
        recovery = mfa.generate_recovery_codes(1)[0]
        db.enable_gestoria_mfa(
            account["id"], [mfa.recovery_hash(recovery)], counter - 1
        )

        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                login = client.post("/gestoria/login", data={
                    "email": account["email"], "password": PASSWORD,
                }, follow_redirects=False)
                self.assertEqual(login.headers["location"], "/gestoria/mfa")
                self.assertEqual(
                    client.get("/gestoria", follow_redirects=False).headers["location"],
                    "/gestoria/login",
                )

                # Volvemos a iniciar el reto porque intentar la cartera limpia la
                # sesión pendiente, pero nunca concede acceso.
                client.post("/gestoria/login", data={
                    "email": account["email"], "password": PASSWORD,
                })
                accepted = client.post(
                    "/gestoria/mfa", data={"code": totp}, follow_redirects=False
                )
                self.assertEqual(accepted.headers["location"], "/gestoria")

                client.post("/gestoria/logout")
                client.post("/gestoria/login", data={
                    "email": account["email"], "password": PASSWORD,
                })
                replay = client.post(
                    "/gestoria/mfa", data={"code": totp}, follow_redirects=False
                )
                self.assertIn("error=1", replay.headers["location"])
                recovered = client.post(
                    "/gestoria/mfa", data={"code": recovery},
                    follow_redirects=False,
                )
                self.assertEqual(recovered.headers["location"], "/gestoria")

        self.assertEqual(
            db.gestoria_recovery_codes_remaining(
                db.get_gestoria_account(account["id"])
            ),
            0,
        )

    def test_account_can_enable_mfa_and_codes_are_only_shown_once(self):
        account = self.account("activar@gestoria.example")
        counter = int(time.time()) // 30
        code = mfa.code_for_counter(mfa.secret_for(account), counter)

        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                client.post("/gestoria/login", data={
                    "email": account["email"], "password": PASSWORD,
                })
                setup = client.get("/gestoria/seguridad")
                self.assertEqual(setup.status_code, 200)
                self.assertIn("Activar segundo factor", setup.text)
                rejected = client.post(
                    "/gestoria/seguridad/activar",
                    data={"password": "incorrecta", "code": code},
                    follow_redirects=False,
                )
                self.assertIn("error=verify", rejected.headers["location"])
                self.assertFalse(
                    db.get_gestoria_account(account["id"])["mfa_enabled"]
                )
                enabled = client.post(
                    "/gestoria/seguridad/activar",
                    data={"password": PASSWORD, "code": code},
                    follow_redirects=False,
                )
                self.assertEqual(enabled.status_code, 200)
                first_view = enabled
                second_view = client.get("/gestoria/seguridad")

        updated = db.get_gestoria_account(account["id"])
        self.assertTrue(updated["mfa_enabled"])
        self.assertEqual(db.gestoria_recovery_codes_remaining(updated), 8)
        self.assertIn("Tus códigos de recuperación", first_view.text)
        self.assertNotIn("Tus códigos de recuperación", second_view.text)


if __name__ == "__main__":
    unittest.main()
