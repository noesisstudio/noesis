"""Que la factura salga desde el correo del autónomo, no desde el nuestro.

Hasta ahora las facturas salían desde la dirección de Bynoesis: el cliente recibía
su factura de un remitente que no conocía y, si contestaba, la respuesta no le
llegaba a nadie. El founder lo pidió así el 25-09-2026: «yo soy un cliente, me
conecto y pongo mi correo; que haya alguna manera de vincularlo».

La forma de hacerlo es que cada autónomo autorice a Bynoesis a enviar **en su
nombre**, y eso significa guardar una llave de su cuenta. De ahí las tres reglas
que fijan las pruebas de aquí, por orden de gravedad:

    Esa llave no toca el disco en claro. Nunca.
    Si el autónomo retira el permiso, se le dice; no se reintenta a ciegas.
    Y mientras no haya conexión, las facturas siguen saliendo por Bynoesis: esto
    añade una vía, no sustituye la que ya funcionaba.
"""
import base64
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote

from noesis import config, db, secret_box
from noesis.adapters import google_mail
from noesis.web import auth, scheduler

SECRETO = "secreto-de-pruebas-con-longitud-mas-que-suficiente"  # pragma: allowlist secret - credencial ficticia del fixture


class _Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = patch.multiple(
            config, DATABASE_URL="", DB_PATH=Path(self.temp.name) / "t.db",
            BACKUP_DIR=Path(self.temp.name) / "b",
            DOCS_PATH=Path(self.temp.name) / "d", SECRET_KEY=SECRETO,
            GOOGLE_CLIENT_ID="id-de-pruebas",
            GOOGLE_CLIENT_SECRET="secreto-de-pruebas",  # pragma: allowlist secret - credencial ficticia del fixture
            GOOGLE_REDIRECT_URI="https://bynoesis.com/integraciones/google/callback")
        self.settings.start()
        db.init_db()
        self.bid = db.create_business("Reformas Prueba", "a@example.com")["id"]

    def tearDown(self):
        self.settings.stop()
        self.temp.cleanup()

    def conectar(self, correo="autonomo@gmail.com"):
        return db.save_oauth_credentials(
            self.bid, "google", account_email=correo,
            refresh_token="refresh-de-google", access_token="access-de-google",
            expires_at=(datetime.now() + timedelta(hours=1)).isoformat(
                timespec="seconds"),
            scope=google_mail.SCOPE)

    def fila_cruda(self):
        with db.get_conn() as conn:
            return dict(conn.execute(
                "SELECT * FROM oauth_credentials WHERE business_id=?",
                (self.bid,)).fetchone())


class CajaFuerteTests(_Base):
    """Lo primero es que la llave no se pueda leer teniendo la base de datos."""

    def test_a_secret_comes_back_exactly_as_it_went_in(self):
        self.assertEqual(secret_box.leer(secret_box.guardar("1//abc-refresh")),
                         "1//abc-refresh")

    def test_what_is_written_does_not_contain_the_secret(self):
        guardado = secret_box.guardar("1//abc-refresh")
        self.assertNotIn("1//abc-refresh", guardado)
        self.assertTrue(guardado.startswith("v1:"))

    def test_another_server_secret_cannot_read_it(self):
        guardado = secret_box.guardar("1//abc-refresh")
        with patch.object(config, "SECRET_KEY", "otro-secreto-igual-de-largo-pero-distinto"):
            # Devuelve None, no revienta: significa «hay que volver a conectar».
            self.assertIsNone(secret_box.leer(guardado))

    def test_it_refuses_to_encrypt_with_the_secret_that_is_in_the_repository(self):
        with patch.object(config, "SECRET_KEY", "dev-secret-cambiar-en-produccion"):
            self.assertFalse(secret_box.disponible())
            with self.assertRaises(ValueError):
                secret_box.guardar("1//abc-refresh")

    def test_something_stored_in_another_format_is_ignored_not_crashed_on(self):
        self.assertIsNone(secret_box.leer("texto-plano-de-antes"))
        self.assertIsNone(secret_box.leer(""))
        self.assertIsNone(secret_box.leer(None))


class CuentaGuardadaTests(_Base):
    def test_the_tokens_are_encrypted_on_disk(self):
        self.conectar()
        cruda = self.fila_cruda()
        self.assertNotIn("refresh-de-google", str(cruda.values()))
        self.assertNotIn("access-de-google", str(cruda.values()))
        # Y aun así se leen bien por el camino normal.
        cuenta = db.get_oauth_credentials(self.bid, "google")
        self.assertEqual(cuenta["refresh_token"], "refresh-de-google")
        self.assertEqual(cuenta["account_email"], "autonomo@gmail.com")

    def test_refreshing_the_access_token_keeps_the_lasting_permission(self):
        """Google solo entrega el `refresh_token` la primera vez.

        Si al renovar se pisara con nada, la conexión moriría en una hora sin que
        nadie supiera por qué.
        """
        self.conectar()
        db.save_oauth_credentials(self.bid, "google", access_token="access-nuevo",
                                  expires_at="2099-01-01T00:00:00")
        cuenta = db.get_oauth_credentials(self.bid, "google")
        self.assertEqual(cuenta["refresh_token"], "refresh-de-google")
        self.assertEqual(cuenta["access_token"], "access-nuevo")
        self.assertEqual(cuenta["account_email"], "autonomo@gmail.com")

    def test_reconnecting_replaces_instead_of_piling_up(self):
        self.conectar()
        self.conectar("otra@gmail.com")
        with db.get_conn() as conn:
            cuantas = conn.execute(
                "SELECT COUNT(*) c FROM oauth_credentials WHERE business_id=?",
                (self.bid,)).fetchone()["c"]
        self.assertEqual(cuantas, 1)
        self.assertEqual(db.get_oauth_credentials(self.bid, "google")["account_email"],
                         "otra@gmail.com")

    def test_a_revoked_account_keeps_the_reason_and_can_be_reconnected(self):
        self.conectar()
        db.mark_oauth_credentials(self.bid, "google", status="revoked",
                                  error="Se retiró el acceso.")
        cuenta = db.get_oauth_credentials(self.bid, "google")
        self.assertEqual(cuenta["status"], "revoked")
        self.assertIn("retiró", cuenta["last_error"])
        # Volver a conectar la revive y borra el aviso viejo.
        self.conectar()
        cuenta = db.get_oauth_credentials(self.bid, "google")
        self.assertEqual(cuenta["status"], "active")
        self.assertFalse(cuenta["last_error"])

    def test_disconnecting_leaves_nothing_behind(self):
        self.conectar()
        self.assertTrue(db.delete_oauth_credentials(self.bid, "google"))
        self.assertIsNone(db.get_oauth_credentials(self.bid, "google"))
        self.assertFalse(db.delete_oauth_credentials(self.bid, "google"))

    def test_closing_the_account_takes_the_permission_with_it(self):
        """Es una llave de la cuenta de Google del autónomo, no un dato nuestro:
        darse de baja tiene que llevársela, no dejarla huérfana en la tabla."""
        self.conectar()
        db.delete_business_cascade(self.bid)
        with db.get_conn() as conn:
            quedan = conn.execute(
                "SELECT COUNT(*) c FROM oauth_credentials WHERE business_id=?",
                (self.bid,)).fetchone()["c"]
        self.assertEqual(quedan, 0)

    def test_a_secret_written_with_another_key_reads_as_not_connected(self):
        self.conectar()
        with patch.object(config, "SECRET_KEY", "otro-secreto-igual-de-largo-pero-distinto"):
            self.assertIsNone(db.get_oauth_credentials(self.bid, "google")["refresh_token"])
            self.assertFalse(google_mail.disponible(self.bid))


class PermisoTests(_Base):
    """Lo que se le pide a Google, y lo que se le dice al autónomo si falta algo."""

    def test_only_permission_to_send_is_asked_for(self):
        url = google_mail.url_de_autorizacion(self.bid, "estado-123")
        self.assertIn("gmail.send", url)
        # Leer el correo sería un permiso «restringido»: auditoría y meses.
        self.assertNotIn("gmail.readonly", url)
        self.assertNotIn("mail.google.com", url)

    def test_the_permission_asked_for_is_a_lasting_one(self):
        url = google_mail.url_de_autorizacion(self.bid, "estado-123")
        self.assertIn("access_type=offline", url)
        self.assertIn("prompt=consent", url)
        self.assertIn("state=estado-123", url)

    def test_without_server_credentials_it_says_what_is_missing(self):
        with patch.multiple(config, GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET=""):
            self.assertFalse(google_mail.configurado())
            with self.assertRaises(ValueError) as caso:
                google_mail.url_de_autorizacion(self.bid, "x")
        self.assertIn("GOOGLE_CLIENT_ID", str(caso.exception))

    def test_a_permission_that_would_expire_in_an_hour_is_rejected_at_the_door(self):
        with patch.object(google_mail, "_peticion",
                          return_value={"access_token": "a", "expires_in": 3600}):
            with self.assertRaises(RuntimeError) as caso:
                google_mail.canjear_codigo("codigo")
        self.assertIn("vuelve a conectarla", str(caso.exception).lower())

    def test_available_only_when_there_is_a_live_connection(self):
        self.assertFalse(google_mail.disponible(self.bid))
        self.conectar()
        self.assertTrue(google_mail.disponible(self.bid))
        db.mark_oauth_credentials(self.bid, "google", status="revoked")
        self.assertFalse(google_mail.disponible(self.bid))


class EnvioTests(_Base):
    def _enviar(self, respuestas):
        llamadas = []

        def falso(url, **kwargs):
            llamadas.append((url, kwargs))
            return respuestas.pop(0) if respuestas else {"id": "msg-1"}

        with patch.object(google_mail, "_peticion", side_effect=falso):
            enviado = google_mail.enviar(
                self.bid, "cliente@ejemplo.com", "Factura 2026/0001",
                "Te adjunto la factura.",
                adjuntos=[("factura.pdf", b"%PDF-1.4 fingido", "application", "pdf")])
        return enviado, llamadas

    def test_the_invoice_goes_out_from_the_freelancers_address_with_the_pdf(self):
        self.conectar()
        enviado, llamadas = self._enviar([{"id": "msg-1"}])
        self.assertTrue(enviado)
        crudo = json.loads(llamadas[-1][1]["cuerpo"])["raw"]
        mensaje = base64.urlsafe_b64decode(crudo).decode(errors="replace")
        self.assertIn("From: autonomo@gmail.com", mensaje)
        self.assertIn("To: cliente@ejemplo.com", mensaje)
        self.assertIn("factura.pdf", mensaje)

    def test_a_valid_token_is_reused_instead_of_asking_google_again(self):
        self.conectar()
        _, llamadas = self._enviar([{"id": "msg-1"}])
        self.assertEqual([url for url, _ in llamadas], [google_mail.ENVIAR])

    def test_an_expired_token_is_renewed_without_bothering_anyone(self):
        db.save_oauth_credentials(
            self.bid, "google", account_email="autonomo@gmail.com",
            refresh_token="refresh-de-google", access_token="caducado",
            expires_at=(datetime.now() - timedelta(minutes=1)).isoformat(
                timespec="seconds"))
        _, llamadas = self._enviar([{"access_token": "nuevo", "expires_in": 3600},
                                    {"id": "msg-1"}])
        self.assertEqual([url for url, _ in llamadas],
                         [google_mail.TOKEN, google_mail.ENVIAR])
        # Y el nuevo queda guardado, cifrado, para no renovar en cada correo.
        self.assertEqual(db.get_oauth_credentials(self.bid, "google")["access_token"],
                         "nuevo")

    def test_when_the_freelancer_withdraws_the_access_it_is_written_down(self):
        self.conectar()
        with patch.object(google_mail, "_peticion",
                          side_effect=google_mail.CuentaRevocada("retirado")):
            with self.assertRaises(google_mail.CuentaRevocada):
                google_mail.enviar(self.bid, "c@ejemplo.com", "Asunto", "Cuerpo")
        cuenta = db.get_oauth_credentials(self.bid, "google")
        self.assertEqual(cuenta["status"], "revoked")
        # Y deja de ofrecerse como vía: el siguiente correo sale por Bynoesis.
        self.assertFalse(google_mail.disponible(self.bid))

    def test_sending_without_any_connection_is_a_revoked_account_not_a_crash(self):
        with self.assertRaises(google_mail.CuentaRevocada):
            google_mail.enviar(self.bid, "c@ejemplo.com", "Asunto", "Cuerpo")


class RutasTests(_Base):
    """El vaivén con Google, visto desde el navegador del autónomo."""

    def setUp(self):
        super().setUp()
        self.negocio, self.usuario = db.create_account(
            "Reformas Web", "web@ejemplo.com",
            auth.hash_password("clave-larga-de-pruebas"), "reformas")

    def _http(self):
        from starlette.testclient import TestClient

        from noesis.web import server

        return TestClient(server.app)

    def _dentro(self, http):
        http.post("/login", data={"email": "web@ejemplo.com",
                                  "password": "clave-larga-de-pruebas"},  # pragma: allowlist secret
                  follow_redirects=False)

    def _empezar(self, http):
        """Arranca la conexión y devuelve el `state` que Google tendrá que traer."""
        ida = http.get(f"/b/{self.negocio['id']}/integraciones/google/conectar",
                       follow_redirects=False)
        return ida, ida.headers["location"].split("state=")[1].split("&")[0]

    def test_a_stranger_cannot_start_a_connection_for_someone_elses_business(self):
        with self._http() as http:
            respuesta = http.get(
                f"/b/{self.negocio['id']}/integraciones/google/conectar",
                follow_redirects=False)
        self.assertEqual(respuesta.headers["location"], "/login")

    def test_connecting_sends_the_freelancer_to_google_and_remembers_the_state(self):
        with self._http() as http:
            self._dentro(http)
            ida, estado = self._empezar(http)
        self.assertIn("accounts.google.com", ida.headers["location"])
        self.assertTrue(estado)

    def test_a_return_that_does_not_match_saves_nothing(self):
        """Sin esto, un tercero podría provocar la vuelta contra otra cuenta."""
        with self._http() as http:
            self._dentro(http)
            self._empezar(http)
            respuesta = http.get(
                "/integraciones/google/callback?code=x&state=inventado",
                follow_redirects=False)
        self.assertIn("ajustes", respuesta.headers["location"])
        self.assertIsNone(db.get_oauth_credentials(self.negocio["id"], "google"))

    def test_saying_no_in_googles_screen_is_explained_not_swallowed(self):
        with self._http() as http:
            self._dentro(http)
            _, estado = self._empezar(http)
            respuesta = http.get(
                f"/integraciones/google/callback?error=access_denied&state={estado}",
                follow_redirects=False)
        self.assertIn("Bynoesis", unquote(respuesta.headers["location"]))
        self.assertIsNone(db.get_oauth_credentials(self.negocio["id"], "google"))

    def test_the_whole_round_trip_leaves_the_account_connected(self):
        with self._http() as http:
            self._dentro(http)
            _, estado = self._empezar(http)
            with patch.object(google_mail, "canjear_codigo", return_value={
                "access_token": "access", "refresh_token": "refresh",
                "expires_in": 3600,
            }), patch.object(google_mail, "correo_de_la_cuenta",
                             return_value="autonomo@gmail.com"):
                respuesta = http.get(
                    f"/integraciones/google/callback?code=codigo&state={estado}",
                    follow_redirects=False)
        self.assertIn("autonomo@gmail.com", unquote(respuesta.headers["location"]))
        cuenta = db.get_oauth_credentials(self.negocio["id"], "google")
        self.assertEqual(cuenta["account_email"], "autonomo@gmail.com")
        self.assertEqual(cuenta["status"], "active")

    def test_disconnecting_needs_to_be_your_own_business(self):
        db.save_oauth_credentials(self.negocio["id"], "google",
                                  account_email="a@gmail.com",
                                  refresh_token="r")
        with self._http() as http:
            http.post(f"/b/{self.negocio['id']}/integraciones/google/desconectar",
                      follow_redirects=False)
        self.assertIsNotNone(db.get_oauth_credentials(self.negocio["id"], "google"))
        with self._http() as http:
            self._dentro(http)
            http.post(f"/b/{self.negocio['id']}/integraciones/google/desconectar",
                      follow_redirects=False)
        self.assertIsNone(db.get_oauth_credentials(self.negocio["id"], "google"))


class ColaDeCorreoTests(_Base):
    """Por dónde sale de verdad cada factura, ya en la cola durable."""

    def setUp(self):
        super().setUp()
        db.update_fiscal(self.bid, nif="12345678Z", address="Calle Prueba 1")
        self.cliente = db.add_client("Juan", nif="87654321X",
                                     address="Calle Juan 1",
                                     email="juan@ejemplo.com",
                                     business_id=self.bid)
        borrador = db.add_invoice(self.cliente["id"], "Obra", 100,
                                  business_id=self.bid)
        self.factura = db.issue_invoice(borrador["id"], self.bid)

    def encolar(self):
        db.enqueue_email_message(
            business_id=self.bid, to_email="juan@ejemplo.com",
            subject=f"Factura {self.factura['number']}",
            text_body="Te adjunto la factura.", html_body=None,
            idempotency_key=f"entrega-{self.factura['id']}",
            entity_type="invoice", entity_id=self.factura["id"])

    def test_with_gmail_connected_it_goes_out_from_the_freelancer(self):
        self.conectar()
        self.encolar()
        with patch.object(google_mail, "enviar", return_value=True) as propio, \
                patch("noesis.adapters.email.send_email") as bynoesis:
            scheduler.process_email_outbox()
        self.assertTrue(propio.called)
        self.assertFalse(bynoesis.called)
        adjuntos = propio.call_args.kwargs["adjuntos"]
        self.assertEqual(len(adjuntos), 1)
        self.assertTrue(adjuntos[0][0].endswith(".pdf"))
        self.assertTrue(adjuntos[0][1].startswith(b"%PDF"))

    def test_without_gmail_it_still_goes_out_from_bynoesis_as_always(self):
        """El contrapeso: esto añade una vía, no sustituye la que funcionaba."""
        self.encolar()
        with (
            patch.multiple(config, BREVO_API_KEY="xkeysib-pruebas"),  # pragma: allowlist secret - credencial ficticia del fixture
            patch("noesis.adapters.email.send_email", return_value=True) as bynoesis,
            patch.object(google_mail, "enviar") as propio,
        ):
            scheduler.process_email_outbox()
        self.assertTrue(bynoesis.called)
        self.assertFalse(propio.called)

    def test_with_no_way_out_at_all_the_email_waits_instead_of_disappearing(self):
        self.encolar()
        with patch.multiple(config, BREVO_API_KEY="", SMTP_HOST="", SMTP_USER="",
                            SMTP_PASS=""):
            scheduler.process_email_outbox()
        with db.get_conn() as conn:
            fila = dict(conn.execute(
                "SELECT status, last_error FROM email_outbox").fetchone())
        self.assertNotEqual(fila["status"], "sent")
        self.assertIn("SMTP", fila["last_error"])

    def test_a_connection_withdrawn_mid_queue_falls_back_to_bynoesis(self):
        """Retirar el permiso no puede dejar la factura atascada para siempre."""
        self.conectar()
        self.encolar()
        with (
            patch.multiple(config, BREVO_API_KEY="xkeysib-pruebas"),  # pragma: allowlist secret - credencial ficticia del fixture
            patch.object(google_mail, "_peticion",
                         side_effect=google_mail.CuentaRevocada("retirado")),
        ):
            scheduler.process_email_outbox()
        # La conexión queda marcada como muerta, sola, en vez de reintentarse a
        # ciegas contra un permiso que el autónomo ha retirado a propósito.
        self.assertEqual(
            db.get_oauth_credentials(self.bid, "google")["status"], "revoked")
        self.assertFalse(google_mail.disponible(self.bid))
        # Y en el siguiente intento la factura sale por Bynoesis, que es lo que
        # importa: el cliente la recibe igual.
        with db.get_conn() as conn:
            conn.execute("UPDATE email_outbox SET next_attempt_at=?",
                         ("2000-01-01T00:00:00",))
        with (
            patch.multiple(config, BREVO_API_KEY="xkeysib-pruebas"),  # pragma: allowlist secret - credencial ficticia del fixture
            patch("noesis.adapters.email.send_email", return_value=True) as bynoesis,
        ):
            scheduler.process_email_outbox()
        self.assertTrue(bynoesis.called)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
