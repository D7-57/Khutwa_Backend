import json
import re
from uuid import UUID

from openai import OpenAI

from app.core.config import settings
from app.schemas.career.roles import RoleDetectResponse, RoleSuggestion
from app.schemas.career.questionnaire import QuestionnaireAnswers
from app.services.career.prompts import SYSTEM_PROMPT, build_user_prompt

client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Threshold below which we drop a suggestion
MIN_CONFIDENCE = 0.40
MAX_SUGGESTIONS = 5


def detect_roles(
    *,
    roles: list,
    answers: QuestionnaireAnswers | None = None,
    message: str | None = None,
    context: dict | None = None,
) -> RoleDetectResponse:
    """
    Suggest the top 3–5 matching roles given questionnaire answers,
    a free-text message, and/or CV context.

    At least one of answers, message, or context must be provided.
    """

    # Build catalog — only leaf roles, trim descriptions to save tokens
    role_catalog = [
        {
            "id": str(r.id),
            "name": r.name,
            "description": (r.description or "")[:120],
        }
        for r in roles
    ]

    user_prompt = build_user_prompt(
        role_catalog=role_catalog,
        answers=answers,
        message=message,
        context=context,
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
            timeout=20,
        )
    except Exception as e:
        # Surface API errors clearly
        raise RuntimeError(f"OpenAI API call failed: {e}") from e

    content = resp.choices[0].message.content or "{}"

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Fallback: try to extract JSON from markdown fences
        match = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
        else:
            return RoleDetectResponse(
                suggestions=[],
                follow_up="I couldn't process the response. Could you describe your interests in more detail?",
            )

    # ── Validate & filter ─────────────────────────────────────────────────
    valid_ids = {str(r.id) for r in roles}
    role_name_map = {str(r.id): r.name for r in roles}

    suggestions = []
    for s in data.get("suggestions", []):
        rid = s.get("role_id", "")
        confidence = min(1.0, max(0.0, float(s.get("confidence", 0))))

        if rid not in valid_ids:
            continue  # hallucinated role ID — drop
        if confidence < MIN_CONFIDENCE:
            continue  # below threshold — drop

        suggestions.append(
            RoleSuggestion(
                role_id=UUID(rid),
                role_name=role_name_map[rid],
                confidence=confidence,
                reason=s.get("reason", "").strip(),
            )
        )

    suggestions.sort(key=lambda x: x.confidence, reverse=True)
    suggestions = suggestions[:MAX_SUGGESTIONS]

    # ── Detect genuinely ambiguous results ─────────────────────────────────
    follow_up = data.get("follow_up")
    if not follow_up and len(suggestions) >= 2:
        gap = suggestions[0].confidence - suggestions[1].confidence
        if gap < 0.10:
            follow_up = (
                "You seem like a strong fit for both "
                + suggestions[0].role_name
                + " and "
                + suggestions[1].role_name
                + ". Would you like me to compare what a typical day looks like in each?"
            )

    return RoleDetectResponse(
        suggestions=suggestions,
        follow_up=follow_up,
    )
