from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def synthesize_question_audio(text: str, language: str = "en") -> bytes:
    # pick voice based on language
    voice = "ash" if language == "ar" else "alloy"

    response = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=voice,
        input=text,
    )
    return response.read()
