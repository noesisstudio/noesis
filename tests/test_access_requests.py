"""Pruebas del alta controlada: solicitud publica y aprobacion del fundador."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noesis import config, db
from noesis.web import auth


class AccessRequestTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.original = {
            name: getattr(config, name)
            for name in ("DB_PATH", "DOCS_PATH", "BACKUP_DIR", "DATABASE_URL",
                         "ADMIN_EMAIL", "ADMIN_EMAILS", "IS_PRODUCTION")
        }
        root = Path(self.temporary.name)
        config.DATABASE_URL = ""
        config.DB_PATH = root / "access-requests.db"
        config.DOCS_PATH = root / "uploads"
        config.BACKUP_DIR = root / "backups"
        config.ADMIN_EMAIL = "fundador@bynoesis.com"
        config.ADMIN_EMAILS = (config.ADMIN_EMAIL,)
        config.IS_PRODUCTION = False
        db.init_db()

    def tearDown(self):
        for name, value in self.original.items():
            setattr(config, name, value)
        self.temporary.cleanup()

    def _client(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        return patch.object(server, "start_scheduler", lambda: None), TestClient(
            server.app
        )

    # ------------------------------------------------------------ formulario --
    def test_valid_request_is_stored_with_its_commercial_context(self):
        scheduler, client = self._client()
        with scheduler, client as http, patch(
            "noesis.adapters.email.queue_email", return_value=True
        ) as notify:
            response = http.post("/solicitar-acceso", data={
                "name": "Marta Vidal", "email": "Marta@Ejemplo.com",
                "business_name": "Fontanería Vidal", "sector": "Fontanería",
                "phone": "600123456", "message": "Facturo tarde",
                "plan": "pro", "acepto": "1",
            }, follow_redirects=False)

        self.assertEqual(response.status_code, 303)
        self.assertIn("enviado=1", response.headers["location"])
        stored = db.list_access_requests()
        self.assertEqual(len(stored), 1)
        # El correo se normaliza para que no entren duplicados por mayúsculas.
        self.assertEqual(stored[0]["email"], "marta@ejemplo.com")
        self.assertEqual(stored[0]["plan_interest"], "pro")
        self.assertEqual(stored[0]["status"], "nueva")
        # Salen dos correos: el aviso al buzón de solicitudes y la confirmación
        # al solicitante. El aviso no va al correo del administrador: quien
        # atiende las solicitudes no tiene por qué ser quien administra.
        destinatarios = [llamada.args[0] for llamada in notify.call_args_list]
        self.assertIn(config.ACCESS_REQUESTS_EMAIL, destinatarios)
        self.assertIn("marta@ejemplo.com", destinatarios)

    def test_request_without_consent_or_valid_email_is_rejected(self):
        scheduler, client = self._client()
        with scheduler, client as http:
            no_consent = http.post("/solicitar-acceso", data={
                "name": "Sin permiso", "email": "a@b.com", "sector": "Obra",
            }, follow_redirects=False)
            bad_email = http.post("/solicitar-acceso", data={
                "name": "Correo raro", "email": "no-es-un-correo",
                "sector": "Obra", "acepto": "1",
            }, follow_redirects=False)

        self.assertIn("error=consent", no_consent.headers["location"])
        self.assertIn("error=email", bad_email.headers["location"])
        self.assertEqual(db.list_access_requests(), [])

    def test_gestoria_request_is_identified_without_opening_client_access(self):
        scheduler, client = self._client()
        with scheduler, client as http, patch(
            "noesis.adapters.email.queue_email", return_value=True
        ):
            page = http.get("/solicitar-acceso?perfil=gestoria")
            response = http.post("/solicitar-acceso", data={
                "perfil": "gestoria", "name": "Núria Serra",
                "email": "nuria@gestoria.example",
                "business_name": "Serra Assessors", "phone": "600000000",
                "message": "Llevamos unas 30 empresas", "acepto": "1",
            }, follow_redirects=False)

        self.assertIn("Tu cartera, preparada para asesorar", page.text)
        self.assertEqual(response.status_code, 303)
        self.assertIn("perfil=gestoria", response.headers["location"])
        stored = db.list_access_requests()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["business_name"], "Serra Assessors")
        self.assertEqual(stored[0]["sector"], "Gestoría y asesoría")
        self.assertIsNone(db.get_gestoria_account_by_email(
            "nuria@gestoria.example"
        ))

    def test_honeypot_looks_successful_but_stores_nothing(self):
        """Al robot se le responde como a una persona: no aprende del rechazo."""
        scheduler, client = self._client()
        with scheduler, client as http:
            response = http.post("/solicitar-acceso", data={
                "name": "Robot", "email": "robot@spam.com", "sector": "x",
                "acepto": "1", "nsx_check": "http://spam.example",
            }, follow_redirects=False)

        self.assertIn("enviado=1", response.headers["location"])
        self.assertEqual(db.list_access_requests(), [])

    def test_repeating_the_same_email_is_thanked_not_treated_as_an_error(self):
        """Quien insiste suele ser una persona impaciente, no un ataque."""
        scheduler, client = self._client()
        payload = {
            "name": "Insistente", "email": "insistente@ejemplo.com",
            "sector": "Reformas", "acepto": "1",
        }
        with scheduler, client as http, patch(
            "noesis.adapters.email.queue_email", return_value=True
        ), patch.object(auth, "is_rate_limited", return_value=False):
            for _ in range(3):
                http.post("/solicitar-acceso", data=payload, follow_redirects=False)
            extra = http.post(
                "/solicitar-acceso", data=payload, follow_redirects=False
            )
            pagina = http.get("/solicitar-acceso?enviado=1&repetida=1")

        destino = extra.headers["location"]
        self.assertIn("enviado=1", destino)
        self.assertIn("repetida=1", destino)
        self.assertNotIn("error=", destino)
        # No se duplica la solicitud, pero se le dice que ya la tenemos.
        self.assertEqual(len(db.list_access_requests()), 3)
        self.assertIn("ya teníamos tu solicitud", pagina.text)

    def test_a_flood_from_one_address_is_still_cut(self):
        scheduler, client = self._client()
        with scheduler, client as http, patch(
            "noesis.adapters.email.queue_email", return_value=True
        ), patch.object(auth, "is_rate_limited", return_value=True):
            respuesta = http.post("/solicitar-acceso", data={
                "name": "Bombardeo", "email": "otro@ejemplo.com",
                "sector": "Obra", "acepto": "1",
            }, follow_redirects=False)

        self.assertIn("error=throttle", respuesta.headers["location"])
        self.assertEqual(db.list_access_requests(), [])

    # -------------------------------------------------------------- borrado --
    def test_admin_deletes_discarded_test_requests_and_their_notifications(self):
        def notify(req):
            db.enqueue_email_message(
                business_id=None, to_email=config.ADMIN_EMAIL,
                subject=f"Nueva solicitud de acceso: {req['name']}",
                text_body=f"Nombre: {req['name']}\nCorreo: {req['email']}\nTeléfono: —",
            )
        junk = [db.create_access_request("Prova", "prova@gmail.com", phone="654832459"),
                db.create_access_request("asf", "a_f@gmail.com")]
        keep = db.create_access_request("Cliente real", "real@ejemplo.com")
        similar = db.create_access_request("Parecido", "axf@gmail.com")
        for req in (*junk, keep, similar):
            notify(req)
        for req in (*junk, similar):
            db.update_access_request(req["id"], status="descartada")
        # Una descartada que no se borra por id, para verificar el borrado masivo.
        db.update_access_request(similar["id"], status="contactada")
        admin_business, _ = db.create_account(
            "Bynoesis", config.ADMIN_EMAIL, auth.hash_password("clave-larga-admin"), "software",
        )
        intruder_business, _ = db.create_account(
            "Ajeno", "ajeno@ejemplo.com", auth.hash_password("clave-larga-ajena"), "software",
        )

        scheduler, client = self._client()
        with scheduler, client as http:
            http.post("/login", data={"email": "ajeno@ejemplo.com",
                                      "password": "clave-larga-ajena"},  # pragma: allowlist secret
                      follow_redirects=False)
            http.post("/admin/solicitudes/eliminar-descartadas", follow_redirects=False)
            self.assertEqual(len(db.list_access_requests()), 4)
            http.post("/logout", follow_redirects=False)
            http.cookies.clear()
            http.post("/login", data={"email": config.ADMIN_EMAIL,
                                      "password": "clave-larga-admin"},  # pragma: allowlist secret
                      follow_redirects=False)
            self.assertIn("Eliminar todas las descartadas", http.get("/admin").text)
            response = http.post("/admin/solicitudes/eliminar-descartadas", follow_redirects=False)
            self.assertEqual(response.status_code, 303)
            http.post(f"/admin/solicitudes/{keep['id']}/eliminar", follow_redirects=False)

        self.assertEqual({r["email"] for r in db.list_access_requests()}, {"axf@gmail.com"})
        with db.get_conn() as conn:
            rows = conn.execute("SELECT text_body FROM email_outbox").fetchall()
        bodies = [row["text_body"] for row in rows]
        self.assertEqual(len(bodies), 1)
        self.assertIn("axf@gmail.com", bodies[0])

    # -------------------------------------------------------------- aprobación --
    def test_approval_creates_account_without_a_password_anyone_knows(self):
        request = db.create_access_request(
            "Luis Soler", "luis@ejemplo.com",
            business_name="Electricidad Soler", sector="Electricidad",
        )
        admin_business, admin_user = db.create_account(
            "Bynoesis", config.ADMIN_EMAIL, auth.hash_password("clave-larga-admin"),
            "software",
        )

        scheduler, client = self._client()
        with scheduler, client as http, patch(
            "noesis.adapters.email.queue_email", return_value=True
        ) as invitation:
            http.post("/login", data={
                "email": config.ADMIN_EMAIL,
                "password": "clave-larga-admin",  # pragma: allowlist secret
            }, follow_redirects=False)
            response = http.post(
                f"/admin/solicitudes/{request['id']}/alta", follow_redirects=False
            )

        self.assertEqual(response.status_code, 303)
        updated = db.get_access_request(request["id"])
        self.assertEqual(updated["status"], "alta")
        self.assertIsNotNone(updated["business_id"])

        created = db.get_user_by_email("luis@ejemplo.com")
        self.assertIsNotNone(created)
        self.assertNotEqual(created["business_id"], admin_business["id"])
        self.assertNotEqual(created["id"], admin_user["id"])

        # La invitación lleva el enlace para que elija contraseña él mismo.
        body = invitation.call_args.args[2]
        self.assertIn("/restablecer?token=", body)

    def test_approval_is_refused_when_the_email_already_has_an_account(self):
        db.create_account(
            "Ya existe", "repetido@ejemplo.com",
            auth.hash_password("clave-larga-cliente"), "obra",
        )
        request = db.create_access_request("Repetido", "repetido@ejemplo.com")
        db.create_account(
            "Bynoesis", config.ADMIN_EMAIL, auth.hash_password("clave-larga-admin"),
            "software",
        )

        scheduler, client = self._client()
        with scheduler, client as http:
            http.post("/login", data={
                "email": config.ADMIN_EMAIL,
                "password": "clave-larga-admin",  # pragma: allowlist secret
            }, follow_redirects=False)
            http.post(
                f"/admin/solicitudes/{request['id']}/alta", follow_redirects=False
            )

        self.assertEqual(db.get_access_request(request["id"])["status"], "nueva")

    def test_requests_are_only_visible_to_the_founder(self):
        db.create_access_request("Privada", "privada@ejemplo.com")
        db.create_account(
            "Cliente normal", "cliente@ejemplo.com",
            auth.hash_password("clave-larga-cliente"), "obra",
        )

        scheduler, client = self._client()
        with scheduler, client as http:
            http.post("/login", data={
                "email": "cliente@ejemplo.com",
                "password": "clave-larga-cliente",  # pragma: allowlist secret
            }, follow_redirects=False)
            panel = http.get("/admin", follow_redirects=False)
            approve = http.post(
                "/admin/solicitudes/1/alta", follow_redirects=False
            )

        self.assertEqual(panel.headers["location"], "/login")
        self.assertEqual(approve.headers["location"], "/login")
        self.assertEqual(db.get_access_request(1)["status"], "nueva")


if __name__ == "__main__":
    unittest.main()


class AdminEmailsTestCase(unittest.TestCase):
    """El panel admite varios responsables sin compartir una misma cuenta."""

    def setUp(self):
        self.original = (config.ADMIN_EMAILS, config.ADMIN_EMAIL)
        config.ADMIN_EMAIL = ""

    def tearDown(self):
        config.ADMIN_EMAILS, config.ADMIN_EMAIL = self.original

    def test_the_single_address_setting_still_grants_access(self):
        """`ADMIN_EMAIL` y `ADMIN_EMAILS` no pueden divergir en silencio.

        La segunda se deriva de la primera, así que quien cambie solo una espera
        que surta efecto. Si no lo hiciera, un permiso quedaría concedido o negado
        sin que nada lo avisara: en un control de acceso eso no se puede permitir.
        """
        config.ADMIN_EMAILS = ()
        config.ADMIN_EMAIL = "xavier@bynoesis.com"
        self.assertTrue(config.is_admin_email("xavier@bynoesis.com"))
        self.assertFalse(config.is_admin_email("otro@ejemplo.com"))

    def test_several_addresses_are_accepted_and_normalised(self):
        config.ADMIN_EMAILS = ("xavier@bynoesis.com", "miquel@bynoesis.com")
        self.assertTrue(config.is_admin_email("xavier@bynoesis.com"))
        # Mayúsculas y espacios no deben dejar fuera a un responsable.
        self.assertTrue(config.is_admin_email("  Miquel@Bynoesis.com  "))

    def test_anyone_else_is_refused(self):
        config.ADMIN_EMAILS = ("xavier@bynoesis.com",)
        self.assertFalse(config.is_admin_email("cliente@ejemplo.com"))
        self.assertFalse(config.is_admin_email(""))
        self.assertFalse(config.is_admin_email(None))

    def test_without_configuration_nobody_is_admin(self):
        config.ADMIN_EMAILS = ()
        self.assertFalse(config.is_admin_email("cualquiera@ejemplo.com"))
