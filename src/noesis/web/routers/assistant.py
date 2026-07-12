"""Rutas del asistente."""

from __future__ import annotations

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from ... import config, db
from .. import chat
from ..deps import _read_json

router = APIRouter()


@router.get("/api/{business_id}/chat/history")
def api_chat_history(business_id: int, limit: int = 60):
    return {"items": db.list_assistant_messages(business_id, limit=limit)}


@router.get("/api/{business_id}/assistant/memories")
def api_assistant_memories(business_id: int):
    """Memoria visible: el usuario puede saber qué conserva Noesis."""
    return {"items": db.list_memories(business_id)}


@router.post("/api/{business_id}/assistant/memories")
async def api_assistant_remember(business_id: int, request: Request):
    try:
        body = await _read_json(request)
        memory = db.remember(
            business_id, body.get("key"), body.get("value"),
            source="user", confidence=100, user_confirmed=True,
        )
    except (ValueError, TypeError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    db.record_product_event(business_id, "assistant_memory_confirmed")
    return memory


@router.delete("/api/{business_id}/assistant/memories/{memory_id}")
def api_assistant_forget(business_id: int, memory_id: int):
    if not db.delete_memory(business_id, memory_id):
        return JSONResponse({"error": "Recuerdo no encontrado."}, status_code=404)
    db.record_product_event(business_id, "assistant_memory_deleted")
    return {"ok": True}

@router.post("/api/{business_id}/chat")
async def api_chat(business_id: int, request: Request):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    message = str(body.get("message") or "").strip()
    if not message or len(message) > config.MAX_CHAT_CHARS:
        return JSONResponse(
            {"error": "El mensaje está vacío o es demasiado largo."}, status_code=400
        )
    page = str(body.get("page") or "").strip() or None
    return await run_in_threadpool(chat.handle, business_id, message, page)


@router.post("/api/{business_id}/chat/audio")
async def api_chat_audio(business_id: int, audio: UploadFile = File(...)):
    # Nota de voz -> texto (Whisper local, sin coste por uso) -> cerebro local.
    from ...adapters import transcription
    tr = transcription.get_transcriber()
    if tr is None:
        return JSONResponse(
            {"error": "Transcripción de voz no disponible en este servidor."},
            status_code=503)
    data = await audio.read(config.MAX_AUDIO_BYTES + 1)
    if len(data) > config.MAX_AUDIO_BYTES:
        return JSONResponse({"error": "El audio es demasiado grande."}, status_code=413)
    try:
        text = await run_in_threadpool(
            tr.transcribe, data, audio.filename or "audio"
        )
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "No he podido entender el audio."}, status_code=422)
    if not text:
        return JSONResponse({"error": "El audio estaba vacío o no se entendió."},
                            status_code=422)
    result = await run_in_threadpool(
        lambda: chat.handle(business_id, text, channel="audio")
    )
    return {"transcription": text, **result}




@router.post("/api/{business_id}/language")
async def api_update_language(business_id: int, request: Request):
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    try:
        db.update_language(business_id, body.get("language"))
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"ok": True, "language": body.get("language")}


@router.post("/api/{business_id}/explanation-level")
async def api_update_explanation_level(business_id: int, request: Request):
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    try:
        db.update_explanation_level(business_id, body.get("level"))
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"ok": True, "level": body.get("level")}
