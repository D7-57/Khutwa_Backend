import json
from fastapi import HTTPException

from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def evaluate_cv_with_llm(*, raw_text: str, extracted_data: dict, role_name: str, role_description: str | None, language: str) -> dict:
    """
    Returns evaluation_json with both role_fit and ats sections.
    Must be valid JSON dict.
    """
    schema = {
        "role_fit": {
            "score": 0,
            "matched_skills": [],
            "missing_skills": [],
            "strengths": [],
            "gaps": [],
            "bullet_rewrites": [{"original": "", "improved": ""}],
            "suggested_keywords": [],
        },
        "ats": {
            "score": 0,
            "issues": [{"severity": "low|medium|high", "issue": "", "fix": ""}],
            "checklist": {
                "has_contact_info": True,
                "has_section_headings": True,
                "has_dates": True,
                "has_bullets": True,
                "likely_tables_or_columns": False
            },
        },
        "overall_recommendations": [],
    }

    sys = (
        "You are a strict CV evaluator. Output ONLY valid JSON. "
        "No markdown, no explanations. Scores are integers 0-100. "
        "If unknown, use empty strings/lists and best-effort scoring."
    )

    role_info = f"Role: {role_name}\nRole description: {role_description or ''}".strip()

    user = f"""
Language: {language}

{role_info}

Task:
1) Evaluate CV quality and fit for the role (score 0-100).
2) Evaluate ATS compliance (score 0-100).
3) Provide concrete improvements and bullet rewrites.

Return JSON matching this shape (keys must exist even if empty):
{json.dumps(schema, ensure_ascii=False)}

Use BOTH:
- extracted_data JSON
- raw_text excerpt

EXTRACTED_DATA:
{json.dumps(extracted_data or {}, ensure_ascii=False)}

RAW_TEXT (excerpt):
{(raw_text or '')[:12000]}
""".strip()

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": user},
        ],
    )

    content = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("not dict")
        return data
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to parse evaluation JSON from model")