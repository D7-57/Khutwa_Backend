from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.security import get_current_user_id
from app.services.stt import transcribe_audio
from app.services.tts import stream_question_audio

router = APIRouter(prefix="/audio", tags=["audio"])


@router.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    _user_id: str = Depends(get_current_user_id),
):
    if not audio.content_type or "audio" not in audio.content_type:
        raise HTTPException(status_code=400, detail="Upload an audio file")

    audio_bytes = await audio.read()
    text = transcribe_audio(audio_bytes, filename=audio.filename or "audio.webm")
    return {"transcript": text}


@router.get(
    "/prompt-audio",
    responses={200: {"content": {"audio/mpeg": {}}}},
)
def prompt_audio(
    text: str,
    language: str = "en",
    _user_id: str = Depends(get_current_user_id),
):
    """
    Streams TTS audio for the given text.

    v3.3.3 changes:
      - tts-1 model (was gpt-4o-mini-tts) — ~5-10x faster.
      - Streaming response — bytes leave the server as they arrive from
        OpenAI, so the browser starts decoding before the full MP3 finishes
        generating. Cuts perceived latency to ~600-900ms.
      - language parameter — previously the voice was always 'alloy'.
    """
    return StreamingResponse(
        stream_question_audio(text, language=language),
        media_type="audio/mpeg",
    )