"""Una nota de voz que no se entiende debe decir qué se oyó.

Con el mismo mensaje para «no te he oído» y «no he entendido la orden», el
autónomo concluye que el audio no funciona aunque la transcripción sea perfecta.
"""

from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noesis import config, db


class VoiceFallbackReplyTestCase(unittest.TestCase):
    def test_the_reply_quotes_the_transcription_only_for_voice(self):
        from noesis.web import chat

        voz = chat._ai_unavailable_reply("audio", "hazme lo del otro día")
        self.assertIn("He entendido esto de tu nota de voz", voz)
        self.assertIn("hazme lo del otro día", voz)
        self.assertIn("No he sabido interpretar", voz)

        escrito = chat._ai_unavailable_reply("web")
        self.assertNotIn("nota de voz", escrito)
        self.assertIn("No he sabido interpretar", escrito)

    def test_a_long_or_empty_transcription_never_floods_the_reply(self):
        from noesis.web import chat

        largo = chat._ai_unavailable_reply("audio", "pues mira " * 60)
        self.assertLessEqual(len(largo.split("«")[1].split("»")[0]), 160)
        for vacio in ("", "   ", None):
            self.assertNotIn("nota de voz",
                             chat._ai_unavailable_reply("audio", vacio))

    def test_whatsapp_keeps_its_own_examples(self):
        from noesis.web import chat

        self.assertIn("PDF", chat._ai_unavailable_reply("whatsapp", "algo"))


class VoiceWiringTestCase(unittest.TestCase):
    """El aviso no sirve si los dos canales no marcan la entrada como voz."""

    def test_both_channels_mark_a_voice_note_as_voice(self):
        from noesis.web import whatsapp
        from noesis.web.routers import assistant

        self.assertIn("voice=bool(audio_id)", inspect.getsource(whatsapp))
        self.assertIn("voice=True", inspect.getsource(assistant.api_chat_audio))

    def test_handle_accepts_the_flag_and_defaults_to_text(self):
        from noesis.web import chat

        for funcion in (chat.handle, chat._handle):
            parametro = inspect.signature(funcion).parameters["voice"]
            self.assertFalse(parametro.default)


class VoiceBrainTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        self.original_database_url = config.DATABASE_URL
        config.DATABASE_URL = ""
        config.DB_PATH = Path(self.tempdir.name) / "test.db"
        db.init_db()
        self.business = db.create_business("Reformas Norte", "norte@example.com")

    def tearDown(self):
        config.DB_PATH = self.original_db_path
        config.DATABASE_URL = self.original_database_url
        self.tempdir.cleanup()

    def test_a_transcribed_order_with_capital_and_full_stop_still_works(self):
        """Whisper devuelve mayúscula y punto final; eso no puede estorbar."""
        from noesis.web import chat

        with patch.object(config, "ANTHROPIC_API_KEY", ""):
            for frase in ("gasté 45 euros en gasolina",
                          "Gasté 45 euros en gasolina.",
                          "He gastado 45 euros en gasolina."):
                respuesta = chat.handle(self.business["id"], frase,
                                        channel="audio", voice=True)["reply"]
                self.assertIn("45", respuesta)
                self.assertNotIn("No he sabido interpretar", respuesta)


if __name__ == "__main__":
    unittest.main()
