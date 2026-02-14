from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm", language: str | None = None) -> str:
    kwargs = {}
    if language in ("ar", "en"):
        kwargs["language"] = language

    resp = client.audio.transcriptions.create(
        model="whisper-1",
        file=(filename, audio_bytes),
        **kwargs,
    )
    return resp.text

