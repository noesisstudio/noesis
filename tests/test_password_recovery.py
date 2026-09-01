"""Continuidad segura del acceso del titular de un negocio."""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from starlette.testclient import TestClient

from noesis import config, db
from noesis.web import auth, server


OLD_PASSWORD = "Clave-segura-del-titular-2026"  # pragma: allowlist secret
NEW_PASSWORD = "Nueva-clave-segura-del-titular-2026"  # pragma: allowlist secret


class PasswordRecoveryTestCase(unittest.TestCase):
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
        self.business, self.user = db.create_account(
            "Negocio seguro", "titular@example.com",
            auth.hash_password(OLD_PASSWORD), "servicios",
        )

    def tearDown(self):
        config.DB_PATH = self.old_db_path
        config.DOCS_PATH = self.old_docs_path
        config.DATABASE_URL = self.old_database_url
        config.BASE_URL = self.old_base_url
        self.tempdir.cleanup()

    @staticmethod
    def _tokens_from_email() -> list[str]:
        tokens: list[str] = []
        for message in db.list_email_messages(limit=10):
            match = re.search(r"/restablecer\?token=([^\s]+)", message["text_body"])
            if match:
                tokens.append(match.group(1))
        return tokens

    def test_new_link_invalidates_previous_and_response_does_not_enumerate(self):
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                unknown = client.post(
                    "/recuperar", data={"email": "nadie@example.com"},
                    follow_redirects=False,
                )
                first = client.post(
                    "/recuperar", data={"email": self.user["email"]},
                    follow_redirects=False,
                )
                first_token = self._tokens_from_email()[0]
                second = client.post(
                    "/recuperar", data={"email": self.user["email"]},
                    follow_redirects=False,
                )
                newest_token = self._tokens_from_email()[0]

                old_link = client.post(
                    "/restablecer",
                    data={"token": first_token, "password": NEW_PASSWORD},
                    follow_redirects=False,
                )
                valid_link = client.post(
                    "/restablecer",
                    data={"token": newest_token, "password": NEW_PASSWORD},
                    follow_redirects=False,
                )

        self.assertEqual(unknown.headers["location"], first.headers["location"])
        self.assertEqual(first.headers["location"], second.headers["location"])
        self.assertNotEqual(first_token, newest_token)
        self.assertEqual(old_link.headers["location"], "/restablecer?error=token")
        self.assertEqual(valid_link.headers["location"], "/login?error=reset_ok")
        updated = db.get_user(self.user["id"])
        self.assertTrue(auth.verify_password(NEW_PASSWORD, updated["password_hash"]))

    def test_atomic_reset_revokes_an_existing_session_and_is_single_use(self):
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as old_session, TestClient(server.app) as recovery:
                old_session.post("/login", data={
                    "email": self.user["email"], "password": OLD_PASSWORD,
                })
                self.assertEqual(
                    old_session.get(f"/b/{self.business['id']}/resumen").status_code,
                    200,
                )
                recovery.post("/recuperar", data={"email": self.user["email"]})
                token = self._tokens_from_email()[0]
                reset = recovery.post(
                    "/restablecer",
                    data={"token": token, "password": NEW_PASSWORD},
                    follow_redirects=False,
                )
                replay = recovery.post(
                    "/restablecer",
                    data={"token": token, "password": NEW_PASSWORD},
                    follow_redirects=False,
                )
                old_access = old_session.get(
                    f"/b/{self.business['id']}/resumen", follow_redirects=False
                )

        self.assertEqual(reset.headers["location"], "/login?error=reset_ok")
        self.assertEqual(replay.headers["location"], "/restablecer?error=token")
        self.assertEqual(old_access.headers["location"], "/login")
        events = [
            item["event_type"] for item in db.list_security_events()
            if item["subject_business_id"] == self.business["id"]
        ]
        self.assertIn("account.password_reset_requested", events)
        self.assertIn("account.password_reset_completed", events)


if __name__ == "__main__":
    unittest.main()
