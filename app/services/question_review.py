"""
AI service for community question validation and translation — v2.

NEW IN V2:
  Returns a `quality_score` (0..100) so the router can decide:
    >= 70  → status='approved' (high quality, on-topic, well-formed)
    40-69  → status='pending'  (let the community vote decide)
    < 40   → status='rejected' (off-topic, gibberish, spam)

The previous version only filtered for safety (offensive / not-a-question /
illegal), which let through every "off-track" question that was technically
a legitimate sentence — e.g. a marketing question submitted under
'software_engineer'. The quality scorer addresses that.
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
    Validate a community-submitted question, score its quality, and translate it.

    Returns:
        {
            "approved":         True | False,        # convenience: quality_score >= 40
            "quality_score":    0..100,              # used by router for tier decision
            "rejection_reason": "..." | None,
            "text_en":          "...",
            "text_ar":          "...",
        }
    """
    target_language = "Arabic" if source_language == "en" else "English"
    source_label = "English" if source_language == "en" else "Arabic"

    prompt = f"""You are reviewing a community-submitted interview question.
Target role: {role_name or 'general'}
Source language: {source_label}

Question:
\"\"\"{question_text}\"\"\"

Do THREE things:

1. SAFETY CHECK
   Reject (quality_score = 0) if it is:
     - Offensive, discriminatory, contains slurs/hate speech
     - Asking for illegal activity
     - Pure spam, gibberish, or not a question at all

2. QUALITY SCORE (0..100). Judge the question itself, not the answer.
   Consider:
     - On-topic for the role? (off-topic for the role is a big penalty)
     - Well-formed (clear, unambiguous, real interview-style)?
     - Tests something useful — knowledge, skill, judgment, or behavior?
     - Not a duplicate of a 101 textbook definition (those score lower)
     - Trick / scenario / opinion questions are FINE — they can score high

   Rough anchors:
     90-100 = sharp, role-specific, would impress an interviewer
     70-89  = solid, usable in a real interview
     50-69  = passable but generic, awkward wording, or borderline relevance
     30-49  = poorly worded, too vague, or weakly related to the role
     10-29  = barely an interview question (off-track, rambling, irrelevant)
     0-9    = safety reject or pure noise

   Be CALIBRATED, not lenient. The whole point is to filter off-track items.

3. TRANSLATE the question into {target_language}.
   - Preserve tone and meaning
   - Keep technical terms in English even in the Arabic translation
   - Adapt culture-specific phrasing naturally

If quality_score < 40, set rejection_reason to a SHORT human-readable
note in {source_label} so the submitter understands what was wrong.
Otherwise leave rejection_reason null.

Return ONLY JSON (no markdown):
{{
  "quality_score": 0-100,
  "rejection_reason": "..." or null,
  "translated_text": "..."
}}"""

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You score and translate interview questions. "
                        "JSON only, no markdown. Be calibrated — the score "
                        "should genuinely separate off-topic submissions from "
                        "good ones."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

        raw = (resp.choices[0].message.content or "").strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            data = json.loads(match.group(0)) if match else {}

        # ── Parse + clamp quality score ──
        try:
            quality_score = int(data.get("quality_score", 50))
        except (ValueError, TypeError):
            quality_score = 50
        quality_score = max(0, min(100, quality_score))

        approved = quality_score >= 40  # backward-compat boolean
        rejection_reason = data.get("rejection_reason") if not approved else None

        translated = (data.get("translated_text") or "").strip()

        if source_language == "en":
            return {
                "approved": approved,
                "quality_score": quality_score,
                "rejection_reason": rejection_reason,
                "text_en": question_text.strip(),
                "text_ar": translated or question_text.strip(),
            }
        else:
            return {
                "approved": approved,
                "quality_score": quality_score,
                "rejection_reason": rejection_reason,
                "text_en": translated or question_text.strip(),
                "text_ar": question_text.strip(),
            }

    except Exception:
        # If AI fails, neither approve nor reject — let community decide.
        return {
            "approved": True,
            "quality_score": 50,
            "rejection_reason": None,
            "text_en": question_text.strip(),
            "text_ar": question_text.strip(),
        }
