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
        model = self._load()
        suffix = os.path.splitext(filename)[1] or ".ogg"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(audio)
            path = f.name
        try:
            segments, _info = model.transcribe(path, language="es", beam_size=1)
            return " ".join(s.text.strip() for s in segments).strip()
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass


def available() -> bool:
    """True si faster-whisper está instalado y se puede transcribir en local."""
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


_provider: Transcriber | None = None


def get_transcriber() -> Transcriber | None:
    """Devuelve el transcriptor activo, o None si no está disponible."""
    global _provider
    if _provider is None and available():
        _provider = LocalWhisperProvider()
    return _provider
