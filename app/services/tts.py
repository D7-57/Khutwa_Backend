from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)


# v3.3.3: switched from gpt-4o-mini-tts (quality model, 8-15s per call) to
# tts-1 (speed model, ~1-3s per call). Quality is still good for an interview
# practice tool — the trade-off is worth the 5-10x latency drop. tts-1-hd is
# available if quality ever becomes the bottleneck.
TTS_MODEL = "gpt-4o-mini-tts"
# gpt-4o-mini-tts

def synthesize_question_audio(text: str, language: str = "en") -> bytes:
    """
    Generate speech audio from text.
    Picks voice based on language:
      - Arabic: 'shimmer' (handles Arabic phonemes reasonably)
      - English: 'alloy' (neutral professional tone)

    Returns the full MP3 bytes. For lower latency at the *client*, the
    /audio/prompt-audio endpoint streams these bytes as they arrive
    instead of buffering the whole file — see audio.py.
    """
    voice = "shimmer" if language == "ar" else "alloy"

    response = client.audio.speech.create(
        model=TTS_MODEL,
        voice=voice,
        input=text,
        response_format="mp3",
    )
    return response.read()


def stream_question_audio(text: str, language: str = "en"):
    """
    Streaming variant — yields MP3 byte chunks as they're produced by OpenAI.

    This lets the FastAPI endpoint send bytes to the browser as they arrive,
    which means the user can start hearing the question before the full
    audio has been synthesized. For ~30-word prompts, perceived latency
    drops from ~2-3s (synchronous) to ~600-900ms (streaming, first byte).
    """
    voice = "shimmer" if language == "ar" else "alloy"

    # OpenAI's SDK exposes streaming via the with_streaming_response context.
    # iter_bytes() yields chunks; we propagate them up to the StreamingResponse.
    with client.audio.speech.with_streaming_response.create(
        model=TTS_MODEL,
        voice=voice,
        input=text,
        response_format="mp3",
    ) as response:
        for chunk in response.iter_bytes(chunk_size=4096):
            if chunk:
                yield chunk