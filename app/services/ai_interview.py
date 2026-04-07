import json
import re
from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def _safe_json(raw: str) -> dict:
    raw = (raw or "").strip()
    try:
        return json.loads(raw)
    except Exception:
        # try extracting from markdown fences
        match = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        # try bare braces
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            return json.loads(raw[start:end + 1])
        return {}


# ─────────────────────────────────────────
#  INTRO EVALUATION
# ─────────────────────────────────────────

def evaluate_intro(answer: str, language: str) -> dict:
    system = (
        "You are a strict interview evaluator. Evaluate the candidate's "
        "'Tell me about yourself' answer. Output JSON only, no markdown."
    )

    schema = {
        "score": "0-100",
        "mentioned_major": "true/false",
        "mentioned_interest": "true/false",
        "mentioned_experience": "true/false",
        "missing": [],
        "feedback": "",
    }

    lang_note = "Respond in Arabic." if language == "ar" else "Respond in English."

    prompt = f"""Evaluate this self-introduction answer.

{lang_note}

Return ONLY JSON matching: {json.dumps(schema)}

Candidate's answer: \"\"\"{answer}\"\"\""""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return _safe_json(resp.choices[0].message.content)


# ─────────────────────────────────────────
#  SCORE ANSWER (question-type aware)
# ─────────────────────────────────────────

SCORING_CRITERIA = {
    "technical": (
        "Focus on: technical accuracy, depth of knowledge, correct terminology, "
        "practical examples. Weight: 60% correctness, 25% depth, 15% communication."
    ),
    "soft": (
        "Focus on: self-awareness, real examples (STAR method), honesty, "
        "emotional intelligence. Weight: 40% substance, 35% structure, 25% delivery."
    ),
    "behavioral": (
        "Focus on: specific examples using STAR method (Situation, Task, Action, Result), "
        "relevance to workplace scenarios, lessons learned. "
        "Weight: 40% concrete examples, 30% relevance, 30% reflection."
    ),
    "general": (
        "Focus on: clarity, relevance to the role, self-awareness, "
        "and professional presentation. Weight: equal across all."
    ),
}


def score_answer(
    answer: str,
    question: str,
    role: str,
    language: str,
    question_type: str = "technical",
    body_language_desc: str = "",
    tone_desc: str = "",
) -> dict:
    criteria = SCORING_CRITERIA.get(question_type, SCORING_CRITERIA["general"])

    lang_note = "Respond in Arabic." if language == "ar" else "Respond in English."

    schema = {
        "score": "0-100",
        "strengths": [],
        "weaknesses": [],
        "skill_match": "0-100",
        "communication_score": "0-100",
        "body_language_score": "0-100 (only if data provided, else null)",
        "final_feedback": "",
    }

    # build optional context sections
    extra_context = ""
    if body_language_desc:
        extra_context += f"\n\nBODY LANGUAGE (from computer vision):\n{body_language_desc}"
        extra_context += "\nIncorporate body language into communication_score and body_language_score."
    if tone_desc:
        extra_context += f"\n\nVOCAL TONE ANALYSIS:\n{tone_desc}"
        extra_context += "\nIncorporate tone metrics into communication_score."

    prompt = f"""Evaluate this interview answer.

Question type: {question_type}
Scoring criteria: {criteria}
Role: {role}
{lang_note}
{extra_context}

Return ONLY JSON matching: {json.dumps(schema)}

Question: \"\"\"{question}\"\"\"
Answer: \"\"\"{answer}\"\"\""""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Strict interview evaluator. Output JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return _safe_json(resp.choices[0].message.content)


# ─────────────────────────────────────────
#  DECIDE NEXT ACTION
# ─────────────────────────────────────────

def decide_next(
    question: str,
    answer: str,
    evaluation: dict,
    role: str,
    language: str,
    question_type: str = "technical",
) -> dict:
    lang_note = "Respond in Arabic." if language == "ar" else "Respond in English."

    type_guidance = ""
    if question_type == "technical":
        type_guidance = "For technical questions: if the answer lacks depth, ask for a specific implementation detail or trade-off."
    elif question_type in ("soft", "behavioral"):
        type_guidance = "For soft/behavioral questions: if the answer lacks a concrete example, ask 'Can you give me a specific situation where...'"

    prompt = f"""You are an adaptive AI interviewer.
{lang_note}

Return ONLY JSON:
{{"action": "follow_up" | "clarify" | "next", "question": ""}}

RULES:
- score < 50 → follow_up (ask a targeted follow-up)
- communication_score < 40 → clarify (ask them to rephrase more clearly)
- score > 70 → next (move on)
- 50-70 → use your judgment based on weaknesses
{type_guidance}

Question type: {question_type}
Original question: {question}
Candidate's answer: {answer}
Evaluation: {json.dumps(evaluation)}
Role: {role}"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Adaptive interviewer. Output JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    return _safe_json(resp.choices[0].message.content)


# ─────────────────────────────────────────
#  AI QUESTION GENERATION
# ─────────────────────────────────────────

def generate_ai_questions(
    role: str,
    language: str,
    count: int = 5,
    tech_ratio: int = 50,
    company: str | None = None,
    cv_summary: str | None = None,
) -> list[dict]:
    """
    Generate interview questions using AI.
    Returns list of {"question_text", "question_type", "difficulty"}.
    """
    num_tech = round(count * tech_ratio / 100)
    num_soft = count - num_tech

    lang_note = "Generate questions in Arabic." if language == "ar" else "Generate questions in English."

    company_note = f"\nTarget company: {company}. Include 1-2 questions specific to this company's domain." if company else ""
    cv_note = f"\nCandidate's CV summary: {cv_summary}\nInclude 1-2 questions that probe claims from their CV." if cv_summary else ""

    prompt = f"""Generate {count} interview questions for the role: {role}

Breakdown: {num_tech} technical questions, {num_soft} soft/behavioral questions.
{lang_note}{company_note}{cv_note}

Return ONLY a JSON array:
[
  {{"question_text": "...", "question_type": "technical|soft|behavioral|general", "difficulty": 1-5}}
]

Rules:
- Technical: test real knowledge, not definitions
- Soft/behavioral: use "Tell me about a time..." or scenario-based format
- Vary difficulty (mix of 2, 3, 4)
- Make questions specific to the role, not generic"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Interview question designer. Output JSON array only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
    )

    raw = resp.choices[0].message.content or "[]"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\[.*]", raw, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
        else:
            data = []

    if not isinstance(data, list):
        data = []

    # validate and normalize
    questions = []
    for item in data[:count]:
        if not isinstance(item, dict) or not item.get("question_text"):
            continue
        questions.append({
            "question_text": item["question_text"],
            "question_type": item.get("question_type", "general"),
            "difficulty": min(5, max(1, int(item.get("difficulty", 3)))),
        })

    return questions