import json
from collections import defaultdict
from openai import OpenAI
from fastapi import HTTPException

from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def _safe_json(raw: str):
    raw = (raw or "").strip()
    try:
        return json.loads(raw)
    except Exception:
        start = raw.find("[")
        end = raw.rfind("]")
        if start != -1 and end != -1:
            return json.loads(raw[start:end + 1])

        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            return json.loads(raw[start:end + 1])

        raise ValueError("No valid JSON found")


def generate_questions_from_cv(
    *,
    raw_text: str,
    extracted_data: dict,
    role_name: str | None,
    max_questions: int,
    language: str,
) -> list[dict]:
    max_questions = max(5, min(max_questions, 20))

    prompt = f"""
Return ONLY valid JSON array.

You are generating a skill-validation MCQ quiz based on a candidate CV.
The goal is to check whether the candidate truly understands the skills claimed in the CV.

Rules:
- Generate up to {max_questions} MCQs
- Focus on skills explicitly mentioned in the CV
- Prioritize the most important and believable skills
- Mix easy, medium, and hard
- 4 options per question
- Exactly one correct answer
- Questions must be practical and role-relevant
- Avoid trivia
- If role is given, slightly bias questions toward that role
- Output format:
[
  {{
    "question": "...",
    "options": ["A", "B", "C", "D"],
    "correct_index": 0,
    "skill": "Python",
    "difficulty": "easy|medium|hard",
    "category": "technical|soft"
  }}
]

Language: {language}
Role: {role_name or "Not specified"}

Extracted CV data:
{json.dumps(extracted_data or {}, ensure_ascii=False)}

Raw CV text excerpt:
{(raw_text or "")[:10000]}
""".strip()

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.3,
        messages=[
            {"role": "system", "content": "You are a strict quiz generator. Output JSON only."},
            {"role": "user", "content": prompt},
        ],
    )

    try:
        data = _safe_json(resp.choices[0].message.content)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to parse quiz JSON")

    if not isinstance(data, list):
        raise HTTPException(status_code=500, detail="Quiz output is not a list")

    cleaned = []
    for item in data[:max_questions]:
        if not isinstance(item, dict):
            continue

        question = str(item.get("question", "")).strip()
        options = item.get("options", [])
        correct_index = item.get("correct_index", None)
        skill = str(item.get("skill", "General")).strip() or "General"
        difficulty = str(item.get("difficulty", "medium")).strip().lower()
        category = str(item.get("category", "technical")).strip().lower()

        if not question:
            continue
        if not isinstance(options, list) or len(options) != 4:
            continue
        if not isinstance(correct_index, int) or correct_index < 0 or correct_index > 3:
            continue
        if difficulty not in {"easy", "medium", "hard"}:
            difficulty = "medium"
        if category not in {"technical", "soft"}:
            category = "technical"

        cleaned.append({
            "question": question,
            "options": [str(x) for x in options],
            "correct_index": correct_index,
            "skill": skill,
            "difficulty": difficulty,
            "category": category,
        })

    if not cleaned:
        raise HTTPException(status_code=500, detail="No valid quiz questions generated")

    return cleaned


def score_quiz_submission(*, questions: list[dict], answers: list[dict]) -> dict:
    answer_map = {a["question_index"]: a["selected_index"] for a in answers if "question_index" in a and "selected_index" in a}

    total = 0
    correct = 0
    per_skill = defaultdict(lambda: {"sum": 0, "count": 0, "category": "technical"})
    wrong_answers = []

    for idx, q in enumerate(questions):
        if idx not in answer_map:
            continue

        selected = answer_map[idx]
        correct_index = q.get("correct_index")
        skill = q.get("skill", "General")
        category = q.get("category", "technical")

        total += 1
        per_skill[skill]["count"] += 1
        per_skill[skill]["category"] = category

        if selected == correct_index:
            correct += 1
            per_skill[skill]["sum"] += 100
        else:
            per_skill[skill]["sum"] += 0
            wrong_answers.append({
                "question": q.get("question"),
                "skill": skill,
                "selected_index": selected,
                "correct_index": correct_index,
                "selected_option": q["options"][selected] if isinstance(selected, int) and 0 <= selected < 4 else None,
                "correct_option": q["options"][correct_index] if isinstance(correct_index, int) and 0 <= correct_index < 4 else None,
            })

    overall = round((correct / total) * 100) if total else 0

    skills = [
        {
            "skill": skill,
            "score": round(data["sum"] / max(data["count"], 1)),
            "category": data["category"],
        }
        for skill, data in per_skill.items()
    ]

    return {
        "overall_score": overall,
        "answered_count": total,
        "correct_count": correct,
        "skills": skills,
        "wrong_answers": wrong_answers,
    }


def generate_quiz_feedback(*, result: dict, role_name: str | None) -> str:
    if not result.get("wrong_answers"):
        return "Excellent work. You showed strong understanding of the skills reflected in your CV."

    prompt = f"""
You are a career coach.

The candidate completed a CV-based MCQ quiz.
Role context: {role_name or "General"}

Result:
{json.dumps(result, ensure_ascii=False)}

Write short practical feedback:
- mention weak skill areas
- suggest what to review
- keep it encouraging
- maximum 120 words
""".strip()

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.4,
        messages=[
            {"role": "system", "content": "You are a concise career coach."},
            {"role": "user", "content": prompt},
        ],
    )

    return (resp.choices[0].message.content or "").strip()