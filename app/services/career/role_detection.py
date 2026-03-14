import json
from uuid import UUID

from openai import OpenAI

from app.core.config import settings
from app.schemas.career.roles import RoleDetectResponse, RoleSuggestion

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def detect_roles(
    *,
    roles: list,  # list of Role ORM objects (leaf roles only)
    answers: dict | None = None,
    message: str | None = None,
    context: dict | None = None,
) -> RoleDetectResponse:
    """
    Given questionnaire answers or a free-text message, use OpenAI to
    suggest the top 3-5 matching roles from the available catalog.
    """

    # build role catalog string for the prompt
    role_catalog = []
    for r in roles:
        role_catalog.append({
            "id": str(r.id),
            "name": r.name,
            "description": r.description or "",
        })

    # build user input section
    user_input_parts = []
    if answers:
        user_input_parts.append(f"Questionnaire answers:\n{json.dumps(answers, ensure_ascii=False, indent=2)}")
    if message:
        user_input_parts.append(f"User message: {message}")
    if context:
        user_input_parts.append(f"Additional context:\n{json.dumps(context, ensure_ascii=False, indent=2)}")

    user_input = "\n\n".join(user_input_parts)

    system_prompt = """You are a career counselor AI for Khutwa, a job readiness platform for Saudi graduates and job seekers.

Your task: Given the user's input (questionnaire answers or free-text description), suggest the top 3-5 best matching career roles from the available catalog.

RULES:
- ONLY suggest roles that exist in the provided catalog (use exact IDs).
- For each suggestion, provide a confidence score (0.0-1.0) and a brief reason in the same language the user used.
- If the input is too vague, set follow_up to a clarifying question.
- Be practical and consider the Saudi job market context.

Respond ONLY in valid JSON with this exact shape:
{
  "suggestions": [
    {"role_id": "uuid", "role_name": "name", "confidence": 0.85, "reason": "brief reason"}
  ],
  "follow_up": null or "clarifying question"
}"""

    user_prompt = f"""Available roles catalog:
{json.dumps(role_catalog, ensure_ascii=False, indent=2)}

User input:
{user_input}"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
    )

    content = resp.choices[0].message.content or "{}"

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # try to extract JSON from markdown fences
        import re
        match = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
        else:
            return RoleDetectResponse(
                suggestions=[],
                follow_up="I couldn't process the response. Could you describe your interests in more detail?",
            )

    # validate role IDs exist in our catalog
    valid_ids = {str(r.id) for r in roles}
    role_name_map = {str(r.id): r.name for r in roles}

    suggestions = []
    for s in data.get("suggestions", []):
        rid = s.get("role_id", "")
        if rid in valid_ids:
            suggestions.append(
                RoleSuggestion(
                    role_id=UUID(rid),
                    role_name=role_name_map[rid],
                    confidence=min(1.0, max(0.0, float(s.get("confidence", 0.5)))),
                    reason=s.get("reason", ""),
                )
            )

    # sort by confidence descending, cap at 5
    suggestions.sort(key=lambda x: x.confidence, reverse=True)
    suggestions = suggestions[:5]

    return RoleDetectResponse(
        suggestions=suggestions,
        follow_up=data.get("follow_up"),
    )