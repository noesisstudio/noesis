"""Una nota de voz que falla dice por qué, y el motivo es el verdadero.

Antes cualquier error del transcriptor acababa en «el servicio está mal
configurado… queda avisado en Ajustes»: una nota larga, un trozo dudoso o Groq
saturado mandaban al autónomo a tocar Ajustes, que estaba bien.
"""
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from noesis import config, db
from noesis.adapters import transcription
from noesis.web import auth, whatsapp

TEST_PASSWORD = "password-segura-123"  # pragma: allowlist secret


def _groq_falla(code):
    opener = MagicMock()
    opener.open.side_effect = urllib.error.HTTPError(
        transcription.GroqWhisperProvider.ENDPOINT, code, "error", {}, None)
    return opener


class MotivoDelFalloTests(unittest.TestCase):
    def _transcribir(self, opener, **extra):
        with (
            patch.dict(os.environ, {"NOESIS_PRIVATE_WHISPER_URL": ""}),
            patch.object(config, "GROQ_API_KEY", "clave"),
            patch.multiple(config, **extra) if extra else patch.dict({}),
            patch.object(whatsapp, "_download_media", return_value=b"OggS-voz"),
            patch("urllib.request.build_opener", return_value=opener),
        ):
            return whatsapp._audio_to_text("123")

    def test_groq_saturado_pide_reenviar_no_revisar_ajustes(self):
        self.assertEqual(self._transcribir(_groq_falla(429)),
                         (None, whatsapp._VOZ_OCUPADA))

    def test_nota_demasiado_grande_pide_dividirla(self):
        self.assertEqual(self._transcribir(_groq_falla(413)),
                         (None, whatsapp._VOZ_LARGA))
        # Y si pesa más de lo que admitimos, ni se manda.
        sin_llamar = MagicMock()
        self.assertEqual(
            self._transcribir(sin_llamar, MAX_AUDIO_BYTES=4),
            (None, whatsapp._VOZ_LARGA))
        sin_llamar.open.assert_not_called()

    def test_clave_rechazada_si_es_mal_configurada(self):
        self.assertEqual(self._transcribir(_groq_falla(401)),
                         (None, whatsapp._VOZ_MAL_CONFIGURADA))

    def test_trozo_dudoso_del_modelo_local_pide_repetir(self):
        transcriptor = MagicMock()
        transcriptor.transcribe.side_effect = transcription.NotaNoValida(
            "dudosa", "Hay un fragmento de voz dudoso.")
        with patch.object(transcription, "get_transcriber",
                          return_value=transcriptor), \
             patch.object(whatsapp, "_download_media", return_value=b"OggS"):
            self.assertEqual(whatsapp._audio_to_text("123"),
                             (None, whatsapp._VOZ_NO_ENTENDIDA))

    def test_cada_motivo_tiene_su_propia_explicacion(self):
        textos = list(whatsapp._VOZ_EXPLICACION.values())
        self.assertEqual(len(textos), len(set(textos)))
        for texto in textos:
            # Siempre queda una salida: escribirlo.
            self.assertIn("texto", texto)
        self.assertIn("más cortas", whatsapp._VOZ_EXPLICACION[whatsapp._VOZ_LARGA])
        self.assertIn("unos segundos",
                      whatsapp._VOZ_EXPLICACION[whatsapp._VOZ_OCUPADA])
        for motivo in whatsapp._VOZ_POR_MOTIVO.values():
            self.assertIn(motivo, whatsapp._VOZ_EXPLICACION)

    def test_nota_no_valida_sigue_siendo_value_error(self):
        """Quien ya capturaba `ValueError` no cambia de comportamiento."""
        self.assertTrue(issubclass(transcription.NotaNoValida, ValueError))


class VozDelChatWebTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.originales = (config.DB_PATH, config.BACKUP_DIR, config.DOCS_PATH,
                           config.DATABASE_URL)
        config.DATABASE_URL = ""
        config.DB_PATH = Path(self.tempdir.name) / "test.db"
        config.BACKUP_DIR = Path(self.tempdir.name) / "backups"
        config.DOCS_PATH = Path(self.tempdir.name) / "uploads"
        db.init_db()

    def tearDown(self):
        (config.DB_PATH, config.BACKUP_DIR, config.DOCS_PATH,
         config.DATABASE_URL) = self.originales
        self.tempdir.cleanup()

    def _subir(self, transcriptor):
        from starlette.testclient import TestClient

        from noesis.web import server

        self.usuarios = getattr(self, "usuarios", 0) + 1
        email = f"vozweb-{self.usuarios}@example.com"
        business = db.create_business("Voz web", f"negocio-{email}")
        db.update_language(business["id"], "ca")
        db.create_user(email, auth.hash_password(TEST_PASSWORD), business["id"])
        with (
            patch.object(server, "start_scheduler", lambda: None),
            patch.object(transcription, "get_transcriber",
                         return_value=transcriptor),
            TestClient(server.app) as client,
        ):
            entrada = client.post(
                "/login",
                data={"email": email, "password": TEST_PASSWORD},
                follow_redirects=False)
            self.assertEqual(entrada.status_code, 303)
            return client.post(
                f"/api/{business['id']}/chat/audio",
                files={"audio": ("nota.webm", b"webm-voz", "audio/webm")})

    def test_el_idioma_del_negocio_llega_al_transcriptor(self):
        transcriptor = MagicMock()
        transcriptor.transcribe.return_value = "què tinc avui"
        respuesta = self._subir(transcriptor)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(transcriptor.transcribe.call_args.kwargs["language"], "ca")

    def test_nota_larga_y_servicio_saturado_dicen_que_hacer(self):
        for motivo, estado, pista in (("larga", 422, "más cortas"),
                                      ("ocupado", 422, "unos segundos"),
                                      ("dudosa", 422, "más despacio")):
            with self.subTest(motivo=motivo):
                transcriptor = MagicMock()
                transcriptor.transcribe.side_effect = transcription.NotaNoValida(
                    motivo, "x")
                respuesta = self._subir(transcriptor)
                self.assertEqual(respuesta.status_code, estado)
                self.assertIn(pista, respuesta.json()["error"])


if __name__ == "__main__":
    unittest.main()
