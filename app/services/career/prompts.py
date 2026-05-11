import json
from app.schemas.career.questionnaire import QuestionnaireAnswers


QUESTION_LABELS = {
    # Energy source → human-readable for prompt
    "writing_communicating":  "Writing & communicating",
    "analyzing_data":         "Analyzing data & numbers",
    "building_coding":        "Building & coding",
    "designing_visuals":      "Designing visuals",
    "helping_advising":       "Helping & advising people",
    "managing_organizing":    "Managing & organizing",
    "researching_learning":   "Researching & learning",
    # Work style
    "structured_analytical":  "Structured / analytical",
    "creative_openended":     "Creative / open-ended",
    "people_coordination":    "People & coordination",
    "builder_maker":          "Builder / maker",
    # Output preference
    "shipped_built_something":  "Shipped or built something",
    "helped_someone":           "Helped someone solve a problem",
    "made_something_beautiful": "Made something look/feel better",
    "found_an_insight":         "Found an insight in data",
    "hit_a_target_closed_deal": "Hit a target or closed a deal",
    # Priority
    "high_salary":         "High starting salary",
    "fast_learning":       "Fast learning curve",
    "creative_freedom":    "Creative freedom",
    "job_stability":       "Job stability",
    "clear_career_ladder": "Clear career ladder",
}


SYSTEM_PROMPT = """\
You are a career counselor AI for Khutwa (خطوة), a job-readiness \
platform built for Saudi graduates and early-career job seekers.

CONTEXT:
- Users are fresh graduates or career changers in Saudi Arabia.
- The platform currently supports three domains:
    • Information Technology / Computing (Software Engineering, Data & AI,
      Cybersecurity, Networking & Cloud, Information Systems & Business)
    • Engineering (Industrial, Petroleum, Chemical, Mechanical, Civil)
    • Business (Business Administration, Accounting, Finance,
      Economics, Management Information Systems)
- Respond in the language indicated by preferred_language (ar or en), \
with a warm and encouraging tone.

TASK:
Given the structured questionnaire answers (and optionally a free-text \
message or CV context), suggest the top 3–5 best-matching roles from the \
provided catalog.

RULES:
1. ONLY suggest roles present in the catalog — use their exact UUIDs. \
   Do NOT invent roles or suggest anything outside the catalog.
2. Confidence scoring guide:
   - 0.85–1.0 : strong signal from ≥3 answers pointing to this role
   - 0.65–0.84: moderate signal, reasonable fit
   - 0.40–0.64: possible fit, worth exploring
   - Below 0.40: do not include
3. reason must be 1–2 sentences, specific to the user's answers.
   BAD:  "This role suits you."
   GOOD: "Your preference for data analysis and structured problem-solving \
maps directly to this role, and it aligns with your priority of a fast \
learning curve."
4. Multi-select answers carry MORE weight — if a user picked 2-3 energy \
   sources, roles that match multiple picks should score higher.
5. follow_up rules:
   - null  → answers are clear enough
   - string → ask ONE specific clarifying question
   - Trigger follow_up when: background_and_enjoyed is missing or vague, \
     or top 2 suggestions have confidence gap < 0.10 (genuinely ambiguous).
6. If considered_roles mentions a role NOT in the catalog, note it in \
   follow_up: "You mentioned X — we don't have that role yet, but [Y] is \
   the closest match."

OUTPUT — valid JSON only, no markdown fences:
{
  "suggestions": [
    {
      "role_id": "uuid",
      "role_name": "exact name from catalog",
      "confidence": 0.87,
      "reason": "specific reason tied to their answers"
    }
  ],
  "follow_up": null
}"""


def build_user_prompt(
    role_catalog: list[dict],
    answers: QuestionnaireAnswers | None = None,
    message: str | None = None,
    context: dict | None = None,
) -> str:
    """Build the user-facing prompt from questionnaire answers, message, and context."""
    parts = [
        f"ROLE CATALOG ({len(role_catalog)} roles):\n"
        + json.dumps(role_catalog, ensure_ascii=False)
    ]

    if answers:
        # Convert enum keys → readable labels for the model
        readable: dict[str, str | list[str]] = {
            "Q1 – Energy sources (multi-select)": [
                QUESTION_LABELS.get(e, e) for e in answers.energy_sources
            ],
            "Q2 – Work style": QUESTION_LABELS.get(
                answers.work_style, answers.work_style
            ),
            "Q3 – Output preferences (multi-select)": [
                QUESTION_LABELS.get(o, o) for o in answers.output_preferences
            ],
            "Q4 – Top priority": QUESTION_LABELS.get(
                answers.top_priority, answers.top_priority
            ),
        }

        if answers.background_and_enjoyed:
            readable["Q5 – Background"] = answers.background_and_enjoyed

        if answers.considered_roles:
            readable["Q6 – Roles considered"] = answers.considered_roles

        readable["preferred_language"] = answers.preferred_language

        parts.append(
            "QUESTIONNAIRE ANSWERS:\n"
            + json.dumps(readable, ensure_ascii=False, indent=2)
        )

    if message:
        parts.append(f"FREE-TEXT FROM USER:\n{message}")

    if context:
        ctx = dict(context)  # avoid mutating the caller's dict
        # Pull the field selection out and show it prominently so the model
        # knows the user has already chosen a domain.
        selected_field = ctx.pop("field", None)
        if selected_field:
            parts.append(
                f"USER'S SELECTED FIELD: {selected_field}\n"
                f"Prioritise roles from the {selected_field} domain. "
                f"Do not suggest roles from other fields unless there is no "
                f"reasonable match in {selected_field}."
            )
        if ctx:
            parts.append(
                "CV / ADDITIONAL CONTEXT:\n"
                + json.dumps(ctx, ensure_ascii=False, indent=2)
            )

    return "\n\n".join(parts)