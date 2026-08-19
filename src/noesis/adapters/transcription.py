"""Transcripción de voz a texto (audio -> factura/agenda por nota de voz).

Auto-alojado con faster-whisper: coste por uso = 0 € (clave para el margen). El
modelo se descarga una vez y se cachea (en el volumen persistente si se indica
NOESIS_WHISPER_DIR). El cerebro que entiende la frase ya es local y gratis (nlu.py),
así que una nota de voz no gasta tokens de IA.

Patrón adaptador: si algún día se prefiere una API externa, se cambia aquí sin tocar
el resto. Carga perezosa: si faster-whisper no está instalado, no rompe la app.
"""

from __future__ import annotations

import os
import tempfile
from typing import Protocol


class Transcriber(Protocol):
    def transcribe(self, audio: bytes, filename: str = "audio") -> str:
        ...


class LocalWhisperProvider:
    """Transcripción local con faster-whisper (sin coste por uso)."""

    def __init__(self):
        self._model = None
        self._size = os.getenv("NOESIS_WHISPER_MODEL", "base")  # tiny|base|small
        self._dir = os.getenv("NOESIS_WHISPER_DIR") or None     # caché en volumen

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel  # import perezoso
            # int8 en CPU: rápido y poca RAM, suficiente para notas de voz cortas.
            self._model = WhisperModel(self._size, device="cpu", compute_type="int8",
                                       download_root=self._dir)
        return self._model

    def transcribe(self, audio: bytes, filename: str = "audio") -> str:
        from .. import config

        model = self._load()
        suffix = os.path.splitext(filename)[1] or ".ogg"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(audio)
            path = f.name
        try:
            segments, _info = model.transcribe(
                path,
                language=config.WHISPER_LANGUAGE or None,
                beam_size=1,
            )
            return " ".join(s.text.strip() for s in segments).strip()
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass


class GroqWhisperProvider:
    """Transcripción vía la API de Groq (Whisper). Coste ~0,002 €/min.

    Multipart a mano con la stdlib para no añadir dependencias. La clave se lee
    en cada llamada para que los tests puedan activarla/desactivarla.
    """

    ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"

    def transcribe(self, audio: bytes, filename: str = "audio.ogg") -> str:
        import json as _json
        import urllib.request
        import uuid

        from .. import config

        boundary = uuid.uuid4().hex
        name = os.path.basename(filename) or "audio.ogg"
        parts = []
        fields = [
            ("model", config.GROQ_WHISPER_MODEL),
            ("response_format", "json"),
        ]
        if config.WHISPER_LANGUAGE:
            fields.append(("language", config.WHISPER_LANGUAGE))
        for field, value in fields:
            parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{field}"\r\n\r\n'
                f"{value}\r\n".encode()
            )
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n".encode()
        )
        body = b"".join(parts) + audio + f"\r\n--{boundary}--\r\n".encode()
        request = urllib.request.Request(
            self.ENDPOINT,
            data=body,
            headers={
                "Authorization": f"Bearer {config.GROQ_API_KEY}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
        )
        response = urllib.request.urlopen(request, timeout=60).read()
        return str(_json.loads(response).get("text") or "").strip()


def _local_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def available() -> bool:
    """True si hay alguna vía de transcripción (API de Groq o whisper local)."""
    from .. import config

    return bool(config.GROQ_API_KEY) or _local_available()


_local_provider: Transcriber | None = None


def get_transcriber() -> Transcriber | None:
    """Groq si hay clave; si no, whisper local si está instalado; si no, None."""
    from .. import config

    if config.GROQ_API_KEY:
        return GroqWhisperProvider()
    global _local_provider
    if _local_provider is None and _local_available():
        _local_provider = LocalWhisperProvider()
    return _local_provider
