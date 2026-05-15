from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)


# v3.3.4: switched from whisper-1 to gpt-4o-mini-transcribe.
# - Cost: $0.003/min vs whisper's $0.006/min (50% cheaper)
# - Quality: better word error rate than whisper-1, designed for low-latency
#   streaming apps. Production-stable as of 2026.
# - Drop-in: identical response shape, just a model swap.
# - Trade-off: no word-level timestamps (we don't use them anyway).
STT_MODEL = "gpt-4o-mini-transcribe"
# whisper-1

def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm", language: str | None = None) -> str:
    kwargs = {}
    if language in ("ar", "en"):
        kwargs["language"] = language

    resp = client.audio.transcriptions.create(
        model=STT_MODEL,
        file=(filename, audio_bytes),
        **kwargs,
    )
    return resp.text