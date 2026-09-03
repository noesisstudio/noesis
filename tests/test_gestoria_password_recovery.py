"""Recuperación segura y aislada del acceso profesional de gestoría."""

from __future__ import annotations

import re
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from starlette.testclient import TestClient

from noesis import config, db
from noesis.web import auth, mfa, server


OLD_PASSWORD = "Clave-profesional-2026"  # pragma: allowlist secret
NEW_PASSWORD = "Nueva-clave-profesional-2026"  # pragma: allowlist secret


class GestoriaPasswordRecoveryTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_db_path = config.DB_PATH
        self.old_docs_path = config.DOCS_PATH
        self.old_database_url = config.DATABASE_URL
        self.old_base_url = config.BASE_URL
        config.DATABASE_URL = ""
        config.DB_PATH = Path(self.tempdir.name) / "test.db"
        config.DOCS_PATH = Path(self.tempdir.name) / "uploads"
        config.BASE_URL = "https://bynoesis.example"
        db.init_db()
        self.account = db.create_gestoria_account(
            "equipo@gestoria.example",
            auth.hash_password(OLD_PASSWORD),
            "Gestoría Ejemplo",
        )

    def tearDown(self):
        config.DB_PATH = self.old_db_path
        config.DOCS_PATH = self.old_docs_path
        config.DATABASE_URL = self.old_database_url
        config.BASE_URL = self.old_base_url
        self.tempdir.cleanup()

    @staticmethod
    def _token_from_last_email() -> str:
        messages = db.list_email_messages(limit=10)
        match = re.search(
            r"/gestoria/restablecer\?token=([^\s]+)",
            messages[0]["text_body"],
        )
        if not match:
            raise AssertionError("El correo no contiene el enlace de recuperación.")
        return match.group(1)

    def test_request_is_nonenumerating_and_queues_only_for_active_account(self):
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                unknown = client.post(
                    "/gestoria/recuperar",
                    data={"email": "nadie@gestoria.example"},
                    follow_redirects=False,
                )
                known = client.post(
                    "/gestoria/recuperar",
                    data={"email": self.account["email"]},
                    follow_redirects=False,
                )
                unknown_page = client.get(unknown.headers["location"])
                known_page = client.get(known.headers["location"])

        self.assertEqual(unknown.headers["location"], known.headers["location"])
        self.assertIn("Si ese correo tiene una cuenta", unknown_page.text)
        self.assertIn("Si ese correo tiene una cuenta", known_page.text)
        messages = db.list_email_messages(limit=10)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["to_email"], self.account["email"])
        self.assertIsNone(messages[0]["business_id"])
        self.assertNotIn(self._token_from_last_email(), known_page.text)

    def test_reset_is_single_use_invalidates_sessions_and_keeps_mfa(self):
        counter = int(time.time()) // 30
        recovery = mfa.generate_recovery_codes(1)[0]
        db.enable_gestoria_mfa(
            self.account["id"], [mfa.recovery_hash(recovery)], counter - 1
        )
        code = mfa.code_for_counter(
            mfa.secret_for(db.get_gestoria_account(self.account["id"])), counter
        )
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as old_session, TestClient(server.app) as recovery_client:
                login = old_session.post(
                    "/gestoria/login",
                    data={
                        "email": self.account["email"],
                        "password": OLD_PASSWORD,
                    },
                    follow_redirects=False,
                )
                self.assertEqual(login.headers["location"], "/gestoria/mfa")
                second_factor = old_session.post(
                    "/gestoria/mfa",
                    data={"code": code},
                    follow_redirects=False,
                )
                self.assertEqual(second_factor.headers["location"], "/gestoria")
                server_account = db.get_gestoria_account(self.account["id"])
                self.assertEqual(old_session.get("/gestoria").status_code, 200)
                recovery_client.post(
                    "/gestoria/recuperar",
                    data={"email": self.account["email"]},
                    follow_redirects=False,
                )
                token = self._token_from_last_email()
                reset = recovery_client.post(
                    "/gestoria/restablecer",
                    data={"token": token, "password": NEW_PASSWORD},
                    follow_redirects=False,
                )
                replay = recovery_client.post(
                    "/gestoria/restablecer",
                    data={"token": token, "password": NEW_PASSWORD},
                    follow_redirects=False,
                )
                old_access = old_session.get(
                    "/gestoria", follow_redirects=False
                )

        self.assertEqual(reset.headers["location"], "/gestoria/login?error=reset_ok")
        self.assertEqual(replay.headers["location"], "/gestoria/restablecer?error=token")
        self.assertEqual(old_access.headers["location"], "/gestoria/login")
        updated = db.get_gestoria_account(self.account["id"])
        self.assertTrue(updated["mfa_enabled"])
        self.assertEqual(updated["mfa_recovery_hashes"], server_account["mfa_recovery_hashes"])
        self.assertFalse(auth.verify_password(OLD_PASSWORD, updated["password_hash"]))
        self.assertTrue(auth.verify_password(NEW_PASSWORD, updated["password_hash"]))
        self.assertGreater(updated["session_version"], server_account["session_version"])

    def test_expired_token_cannot_change_password(self):
        token = "token-expirado-de-prueba"
        db.create_gestoria_password_reset(
            self.account["id"], auth.hash_token(token), ttl_minutes=60
        )
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE gestoria_password_resets SET expires_at=?",
                ("2000-01-01T00:00:00",),
            )
        result = db.reset_gestoria_password(
            auth.hash_token(token), auth.hash_password(NEW_PASSWORD)
        )
        self.assertIsNone(result)
        account = db.get_gestoria_account(self.account["id"])
        self.assertTrue(auth.verify_password(OLD_PASSWORD, account["password_hash"]))


if __name__ == "__main__":
    unittest.main()
