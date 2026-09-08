"""Transcripción de voz a texto (audio -> factura/agenda por nota de voz).

Auto-alojado con faster-whisper: sin tarifa externa por minuto; consume CPU/RAM. El
modelo se descarga una vez y se cachea (en el volumen persistente si se indica
NOESIS_WHISPER_DIR). El cerebro que entiende la frase ya es local y gratis (nlu.py),
así que una nota de voz no gasta tokens de IA.

Patrón adaptador: si algún día se prefiere una API externa, se cambia aquí sin tocar
el resto. Carga perezosa: si faster-whisper no está instalado, no rompe la app.
"""

from __future__ import annotations

import os
import tempfile
import threading
from urllib.parse import urlsplit
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
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel  # import perezoso
            # int8 en CPU: rápido y poca RAM, suficiente para notas de voz cortas.
            self._model = WhisperModel(self._size, device="cpu", compute_type="int8",
                                       cpu_threads=2, num_workers=1, download_root=self._dir)
        return self._model

    def transcribe(self, audio: bytes, filename: str = "audio") -> str:
        if not self._lock.acquire(blocking=False):
            raise ValueError("El transcriptor está ocupado. Inténtalo en unos segundos.")
        try:
            return self._transcribe(audio, filename)
        finally:
            self._lock.release()

    def _transcribe(self, audio: bytes, filename: str = "audio") -> str:
        from .. import config

        if not audio or len(audio) > config.MAX_AUDIO_BYTES:
            raise ValueError("Audio vacío o demasiado grande.")
        model = self._load()
        suffix = os.path.splitext(filename)[1] or ".ogg"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(audio)
            path = f.name
        try:
            # Decodificación por bloques: rechaza duración excesiva antes de que
            # Whisper materialice todo el audio en memoria.
            import av
            maximum = int(os.getenv("NOESIS_WHISPER_MAX_SECONDS", "120"))
            duration = 0.0
            with av.open(path) as container:
                for frame in container.decode(audio=0):
                    duration += frame.samples / frame.sample_rate
                    if duration > maximum:
                        raise ValueError("La nota supera la duración máxima. Divídela en notas más cortas.")
            segments, _info = model.transcribe(
                path,
                language=config.WHISPER_LANGUAGE or None,
                beam_size=5,
                vad_filter=True,
                condition_on_previous_text=False,
            )
            parts = []
            for segment in segments:
                if getattr(segment, "no_speech_prob", 0) > 0.6 or getattr(segment, "avg_logprob", 0) < -1:
                    raise ValueError("Hay un fragmento de voz dudoso. Repite la nota o escribe la orden.")
                parts.append(segment.text.strip())
            text = " ".join(parts).strip()
            if len(text) > config.MAX_CHAT_CHARS:
                raise ValueError("La transcripción es demasiado larga.")
            return text
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


class PrivateWhisperProvider:
    """Solo habla con el destino privado configurado; nunca deriva a terceros."""

    def __init__(self):
        self.url = os.getenv("NOESIS_PRIVATE_WHISPER_URL", "").rstrip("/")
        self.token = os.getenv("NOESIS_PRIVATE_WHISPER_TOKEN", "")
        parsed = urlsplit(self.url)
        private_host = parsed.hostname in {"localhost", "127.0.0.1", "::1"} or (parsed.hostname or "").endswith(".railway.internal")
        if len(self.token) < 32 or parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname or (parsed.scheme != "https" and not (parsed.scheme == "http" and private_host)):
            raise ValueError("Configura Whisper por HTTPS o red privada Railway y una clave de servicio.")

    def transcribe(self, audio: bytes, filename: str = "audio") -> str:
        import json
        import urllib.request
        from .. import config

        if not audio or len(audio) > config.MAX_AUDIO_BYTES:
            raise ValueError("Audio vacío o demasiado grande.")
        request = urllib.request.Request(self.url + "/transcribe", data=audio, headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/octet-stream"})
        # Nunca seguir redirecciones con una nota de voz y credenciales.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        with urllib.request.build_opener(NoRedirect).open(request, timeout=150) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError("Respuesta de transcripción demasiado grande.")
        text = json.loads(raw).get("text")
        if not isinstance(text, str) or not text.strip() or len(text) > config.MAX_CHAT_CHARS:
            raise ValueError("No he entendido la nota con suficiente claridad.")
        return text.strip()


def _local_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def available() -> bool:
    """True si hay alguna vía de transcripción (API de Groq o whisper local)."""
    from .. import config

    if os.getenv("NOESIS_PRIVATE_WHISPER_URL"):
        try:
            PrivateWhisperProvider()
            return True
        except ValueError:
            return False
    return bool(config.GROQ_API_KEY) or _local_available()


_local_provider: Transcriber | None = None


def get_transcriber() -> Transcriber | None:
    """Privado si está configurado; en otro caso Groq o el modelo local."""
    from .. import config

    if os.getenv("NOESIS_PRIVATE_WHISPER_URL"):
        return PrivateWhisperProvider()
    if config.GROQ_API_KEY:
        return GroqWhisperProvider()
    global _local_provider
    if _local_provider is None and _local_available():
        _local_provider = LocalWhisperProvider()
    return _local_provider
