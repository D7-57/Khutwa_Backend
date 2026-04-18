"""
AI service for community question validation and translation.

- Validates questions (rejects offensive, nonsensical, non-questions)
- Translates between Arabic and English
- Light touch: accepts weird/unique questions, only rejects truly bad ones
"""

import json
from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

MODEL = "gpt-4o-mini"


def validate_and_translate(
    question_text: str,
    source_language: str,  # "ar" or "en"
    role_name: str = "",
) -> dict:
    """
    Validate a community-submitted question and translate it.

    Returns:
        {
            "approved": True/False,
            "rejection_reason": "..." or None,
            "text_en": "...",
            "text_ar": "...",
        }
    """
    target_language = "Arabic" if source_language == "en" else "English"
    source_label = "English" if source_language == "en" else "Arabic"

    prompt = f"""You are reviewing a community-submitted interview question for the role: {role_name or 'general'}.

The question was written in {source_label}:
\"\"\"{question_text}\"\"\"

Do TWO things:

1. VALIDATE: Is this an acceptable interview question?
   - APPROVE if it's a legitimate question, even if unusual, niche, creative, or oddly worded
   - APPROVE trick questions, scenario questions, opinion questions — these are all valid interview formats
   - Only REJECT if it is:
     * Offensive, discriminatory, or contains slurs/hate speech
     * Not a question at all (just random text, spam, or gibberish)
     * Asking for illegal activity
   - Be LENIENT. When in doubt, approve. Unique questions are valuable.

2. TRANSLATE: Translate the question into {target_language}.
   - Keep the same tone and meaning
   - If it references culture-specific concepts, adapt naturally
   - For technical terms, keep them in English even in Arabic translation

Return ONLY JSON (no markdown):
{{
  "approved": true/false,
  "rejection_reason": "brief reason in {source_label}" or null,
  "translated_text": "the question in {target_language}"
}}"""

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You validate and translate interview questions. JSON only, no markdown. Be lenient — approve anything that's a legitimate question."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

        raw = (resp.choices[0].message.content or "").strip()
        # Parse JSON
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            data = json.loads(match.group(0)) if match else {}

        approved = data.get("approved", True)  # default to approve
        rejection_reason = data.get("rejection_reason") if not approved else None
        translated = (data.get("translated_text") or "").strip()

        if source_language == "en":
            return {
                "approved": approved,
                "rejection_reason": rejection_reason,
                "text_en": question_text.strip(),
                "text_ar": translated or question_text.strip(),
            }
        else:
            return {
                "approved": approved,
                "rejection_reason": rejection_reason,
                "text_en": translated or question_text.strip(),
                "text_ar": question_text.strip(),
            }

    except Exception:
        # If AI fails, approve and use original text for both
        return {
            "approved": True,
            "rejection_reason": None,
            "text_en": question_text.strip(),
            "text_ar": question_text.strip(),
        }
