"""Servicio privado opcional: audio efímero, proceso acotado y sin base de datos."""
from __future__ import annotations

import asyncio
import hmac
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
_busy = asyncio.Lock()
MAX_BYTES = 12 * 1024 * 1024


def _authorize(request):
    key = os.getenv("NOESIS_PRIVATE_WHISPER_TOKEN", "")
    if len(key) < 32 or not hmac.compare_digest(request.headers.get("authorization", ""), "Bearer " + key):
        raise HTTPException(401, "Acceso no autorizado")


@app.get("/health")
def health():
    model = Path(os.getenv("NOESIS_WHISPER_MODEL", "/models/small"))
    ready = (model / "model.bin").is_file() and len(os.getenv("NOESIS_PRIVATE_WHISPER_TOKEN", "")) >= 32
    if not ready:
        raise HTTPException(503, "Modelo o clave privada pendientes")
    return {"status": "ready", "provider": "private_whisper"}


def _worker(audio: bytes):
    with tempfile.TemporaryDirectory(prefix="noesis-voice-") as directory:
        path = Path(directory) / "audio.bin"
        path.write_bytes(audio)
        try:
            result = subprocess.run([sys.executable, "-m", "noesis.private_voice", "--worker", str(path)], capture_output=True, timeout=120, check=True)
            payload = json.loads(result.stdout)
        except (subprocess.SubprocessError, ValueError):
            raise HTTPException(422, "No he entendido la nota con suficiente claridad. Repite o escribe el mensaje.") from None
        return payload


@app.post("/transcribe")
async def transcribe(request: Request):
    _authorize(request)
    health()
    if _busy.locked():
        raise HTTPException(429, "Transcriptor ocupado; vuelve a intentarlo")
    async with _busy:
        data = bytearray()
        try:
            async with asyncio.timeout(30):
                async for chunk in request.stream():
                    data.extend(chunk)
                    if len(data) > MAX_BYTES:
                        raise HTTPException(413, "Audio demasiado grande")
        except TimeoutError:
            raise HTTPException(408, "Tiempo de subida agotado") from None
        if not data:
            raise HTTPException(422, "Audio vacío")
        return await run_in_threadpool(_worker, bytes(data))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        from .adapters.transcription import LocalWhisperProvider
        text = LocalWhisperProvider().transcribe(Path(sys.argv[2]).read_bytes())
        if not text:
            raise ValueError("No se ha detectado voz")
        print(json.dumps({"text": text}, ensure_ascii=True))
    else:
        import uvicorn
        uvicorn.run(app, host="::", port=int(os.getenv("PORT", "8080")), workers=1, access_log=False)
