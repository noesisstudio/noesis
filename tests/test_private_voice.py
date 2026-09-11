"""Contrato del servicio privado sin modelo, credenciales ni tráfico externos."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from noesis import private_voice
from noesis.adapters import transcription


class PrivateVoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.model = Path(self.temp.name)
        (self.model / "model.bin").touch()
        self.token = "synthetic-test-service-token-not-a-secret"
        self.env = patch.dict(os.environ, {"NOESIS_PRIVATE_WHISPER_TOKEN": self.token, "NOESIS_WHISPER_MODEL": str(self.model), "NOESIS_PRIVATE_WHISPER_URL": "http://localhost:8080"})
        self.env.start()
        self.client = TestClient(private_voice.app)
        self.headers = {"Authorization": "Bearer " + self.token}

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.temp.cleanup()

    def test_unauthorized_audio_is_not_processed(self):
        with patch.object(private_voice, "_worker") as worker:
            self.assertEqual(self.client.post("/transcribe", content=b"audio").status_code, 401)
            worker.assert_not_called()

    def test_missing_model_is_not_ready(self):
        (self.model / "model.bin").unlink()
        self.assertEqual(self.client.get("/health").status_code, 503)

    def test_empty_and_oversized_audio_are_rejected(self):
        self.assertEqual(self.client.post("/transcribe", headers=self.headers, content=b"").status_code, 422)
        with patch.object(private_voice, "MAX_BYTES", 4), patch.object(private_voice, "_worker") as worker:
            self.assertEqual(self.client.post("/transcribe", headers=self.headers, content=b"12345").status_code, 413)
            worker.assert_not_called()

    def test_service_returns_worker_transcription(self):
        with patch.object(private_voice, "_worker", return_value={"text": "gasté 20 euros"}):
            response = self.client.post("/transcribe", headers=self.headers, content=b"synthetic")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["text"], "gasté 20 euros")

    def test_timeout_cleans_temporary_audio_and_has_safe_error(self):
        paths = []
        def fail(command, **kwargs):
            paths.append(Path(command[-1]))
            self.assertTrue(paths[-1].exists())
            raise subprocess.TimeoutExpired(command, 120)
        with patch.object(private_voice.subprocess, "run", side_effect=fail):
            with self.assertRaises(HTTPException) as exc:
                private_voice._worker(b"synthetic")
        self.assertEqual(exc.exception.status_code, 422)
        self.assertFalse(paths[0].exists())

    def test_insecure_public_url_and_weak_token_are_rejected(self):
        for env in ({"NOESIS_PRIVATE_WHISPER_URL": "http://public.example.test"}, {"NOESIS_PRIVATE_WHISPER_TOKEN": "short"}, {"NOESIS_PRIVATE_WHISPER_URL": "https://example.test?token=secret"}):
            with patch.dict(os.environ, env), self.assertRaises(ValueError):
                transcription.PrivateWhisperProvider()

    def test_private_configuration_never_silently_falls_back_to_groq(self):
        with patch.dict(os.environ, {"NOESIS_PRIVATE_WHISPER_TOKEN": ""}), patch.object(transcription, "GroqWhisperProvider") as groq:
            with self.assertRaises(ValueError):
                transcription.get_transcriber()
            groq.assert_not_called()

    def test_misconfigured_private_voice_does_not_break_whatsapp_webhook(self):
        from noesis.web import whatsapp
        with patch.dict(os.environ, {"NOESIS_PRIVATE_WHISPER_TOKEN": "short"}), \
             patch.object(whatsapp, "_download_media") as download:
            self.assertIsNone(whatsapp._audio_to_text("123"))
        download.assert_not_called()

    def test_model_busy_is_rejected(self):
        with patch.object(private_voice._busy, "locked", return_value=True):
            self.assertEqual(self.client.post("/transcribe", headers=self.headers, content=b"audio").status_code, 429)
