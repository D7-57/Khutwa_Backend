import json
from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)


SECTION_PROMPTS = {
    "summary": {
        "system": (
            "You are an expert CV writer. Rewrite the given professional summary "
            "to be more impactful, concise, and ATS-friendly. "
            "Keep it to 2-4 sentences. Use strong action-oriented language. "
            "Do NOT invent skills or experiences not implied by the original."
        ),
        "instruction": "Improve this professional summary:",
    },
    "experience_bullet": {
        "system": (
            "You are an expert CV writer. Rewrite the given experience bullet point "
            "to follow the XYZ formula: Accomplished [X] as measured by [Y], by doing [Z]. "
            "Use strong action verbs. Be specific and quantify impact where possible. "
            "Keep it to 1-2 lines. Do NOT invent metrics not implied by the original."
        ),
        "instruction": "Improve this experience bullet point:",
    },
    "project_description": {
        "system": (
            "You are an expert CV writer. Rewrite the given project description "
            "to highlight technical impact, technologies used, and outcomes. "
            "Keep it concise (1-3 sentences). Use active voice."
        ),
        "instruction": "Improve this project description:",
    },
}


def enhance_section(
    *,
    section: str,
    content: str,
    context: dict | None = None,
    language: str = "en",
) -> dict:
    """
    Use AI to improve a specific CV section text.
    Returns {"original", "improved", "changes_summary"}.
    """
    prompts = SECTION_PROMPTS.get(section)
    if not prompts:
        # generic fallback
        prompts = {
            "system": (
                "You are an expert CV writer. Improve the given text to be more "
                "professional, concise, and ATS-friendly. Do NOT invent information."
            ),
            "instruction": "Improve this text:",
        }

    # build context string if available
    context_str = ""
    if context:
        role_name = context.get("role_name", "")
        if role_name:
            context_str += f"\nTarget role: {role_name}"
        # could add more context here (skills, etc.)

    lang_note = "Respond in Arabic." if language == "ar" else "Respond in English."

    user_prompt = f"""{prompts['instruction']}

\"\"\"{content}\"\"\"
{context_str}

{lang_note}

Respond ONLY with valid JSON:
{{"improved": "the improved text", "changes_summary": "brief 1-sentence explanation of changes"}}"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.3,
        messages=[
            {"role": "system", "content": prompts["system"]},
            {"role": "user", "content": user_prompt},
        ],
    )

    raw = resp.choices[0].message.content or "{}"

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        import re
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
        else:
            data = {"improved": content, "changes_summary": "Could not process."}

    return {
        "original": content,
        "improved": data.get("improved", content),
        "changes_summary": data.get("changes_summary", ""),
    }