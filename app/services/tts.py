from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def synthesize_question_audio(text: str, language: str = "en") -> bytes:
    """
    Generate speech audio from text.
    Picks voice based on language:
      - Arabic: 'ash' (works well with Arabic text)
      - English: 'alloy' (neutral professional tone)
    """
    voice = "ash" if language == "ar" else "alloy"

    response = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=voice,
        input=text,
    )
    return response.read()