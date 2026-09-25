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
def api_chat_history(business_id: int, request: Request, limit: int = 60):
    actor = f"web:{request.session.get('uid')}:{request.session.get('sv', 0)}"
    return {"items": db.list_conversation_messages(business_id, limit=limit, actor=actor)}


@router.get("/api/{business_id}/assistant/memories")
def api_assistant_memories(business_id: int):
    """Memoria visible: el usuario puede saber qué conserva Bynoesis."""
    return {"items": db.list_memories(business_id)}


@router.get("/api/{business_id}/assistant/learning")
def api_assistant_learning(business_id: int, days: int = 7):
    from ... import learning
    return {**learning.report(business_id, days), "rules": learning.rules(business_id)}


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


@router.get("/api/{business_id}/assistant/permissions")
def api_assistant_permissions(business_id: int):
    """Centro de control: límites efectivos y no solo preferencias guardadas."""
    return {
        "items": db.automation_catalog(business_id),
        "mode_labels": db.AUTOMATION_MODE_LABELS,
    }


@router.post("/api/{business_id}/assistant/permissions")
async def api_update_assistant_permission(business_id: int, request: Request):
    try:
        body = await _read_json(request)
        permission = db.update_automation_permission(
            business_id, body.get("action_key"), body.get("mode")
        )
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    db.record_product_event(
        business_id,
        "assistant_permission_updated",
        f"{permission['key']}:{permission['mode']}",
    )
    return permission


@router.get("/api/{business_id}/assistant/actions")
def api_assistant_actions(business_id: int, limit: int = 30):
    """Historial auditable de lo que Bynoesis propuso o llegó a ejecutar."""
    return {"items": db.list_assistant_actions(business_id, limit=limit)}

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
    business = db.get_business(business_id) or {}
    if (
        getattr(request.state, "subscription_read_only", False)
        and business.get("is_demo")
    ):
        return await run_in_threadpool(
            chat.handle_read_only, business_id, message, page
        )
    return await run_in_threadpool(chat.handle, business_id, message, page, actor_id=f"{request.session.get('uid')}:{request.session.get('sv', 0)}")


@router.post("/api/{business_id}/chat/audio")
async def api_chat_audio(business_id: int, request: Request, audio: UploadFile = File(...)):
    # Nota de voz -> texto (Whisper privado, Groq o local) -> cerebro local.
    from ...adapters import transcription
    actor_id = f"{request.session.get('uid')}:{request.session.get('sv', 0)}"
    def audio_error(message: str, status: int):
        if config.ASSISTANT_REVIEW_ENABLED:
            db.clear_pending_action(business_id, f"web:{actor_id}")
        return JSONResponse({"error": message}, status_code=status)
    try:
        tr = transcription.get_transcriber()
    except ValueError:
        tr = None
    if tr is None:
        return audio_error("Transcripción de voz no disponible en este servidor.", 503)
    data = await audio.read(config.MAX_AUDIO_BYTES + 1)
    if len(data) > config.MAX_AUDIO_BYTES:
        return audio_error("El audio es demasiado grande.", 413)
    try:
        text = await run_in_threadpool(
            tr.transcribe, data, audio.filename or "audio"
        )
    except Exception:  # noqa: BLE001
        return audio_error("No he podido entender el audio. Se ha descartado la propuesta anterior; escribe de nuevo la orden.", 422)
    if not text:
        return audio_error("El audio estaba vacío o no se entendió.", 422)
    result = await run_in_threadpool(
        lambda: chat.handle(business_id, text, channel="audio",
                            actor_id=actor_id, voice=True)
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
