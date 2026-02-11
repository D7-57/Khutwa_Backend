from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    # Whisper STT
    resp = client.audio.transcriptions.create(
        model="whisper-1",
        file=(filename, audio_bytes),
    )
    return resp.text
