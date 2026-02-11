from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
from app.core.security import get_current_user_id
from app.services.stt import transcribe_audio

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
