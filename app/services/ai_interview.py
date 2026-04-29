"""
AI Interview Services — v2

Changes:
  1. score_answer + decide_next → evaluate_and_decide (1 LLM call)
  2. answer_type classification
  3. gpt-4o for eval, gpt-4o-mini for generation
  4. generate_ai_questions → generate_cv_questions (only for CV-based Qs)
  5. AI questions no longer saved to Question table
  6. Intro variants with personalization
"""

import json
import re
import random
from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

EVAL_MODEL = "gpt-4o"
GEN_MODEL  = "gpt-4o-mini"


def _safe_json(raw: str) -> dict:
    raw = (raw or "").strip()
    try:
        return json.loads(raw)
    except Exception:
        match = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
        if match:
            try: return json.loads(match.group(1))
            except Exception: pass
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            try: return json.loads(raw[start:end + 1])
            except Exception: pass
        return {}


def _safe_json_array(raw: str) -> list:
    raw = (raw or "").strip()
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except Exception:
        match = re.search(r"\[.*]", raw, re.DOTALL)
        if match:
            try: return json.loads(match.group(0))
            except Exception: pass
        return []


# ─────────────────────────────────────────
#  INTRO
# ─────────────────────────────────────────

INTRO_VARIANTS = {
    "ar": [
        "السلام عليكم! قبل ما نبدأ، عرّفني بنفسك: تخصصك، اهتمامك، وخبراتك أو مشاريع اشتغلت عليها.",
        "أهلاً وسهلاً! عرّفني على نفسك — وش تخصصك وإيش الأشياء اللي اشتغلت عليها أو تهتم فيها؟",
        "مرحباً! خلّنا نبدأ بمقدمة بسيطة عنك — تخصصك، شغفك، وأي خبرة عملية أو مشاريع.",
        "يا هلا! قبل الأسئلة، حب أعرفك أكثر. كلمني عن نفسك وخلفيتك ووش اللي يحمسك.",
    ],
    "en": [
        "Hi! Before we start, tell me about yourself: your major, interests, and any projects or experience.",
        "Welcome! Let's begin with a quick introduction — what's your background and what have you been working on?",
        "Hey there! Tell me a bit about yourself — your field, what interests you, and any hands-on experience.",
        "Great to have you! Before the questions, I'd love to hear about your background and what drives you.",
    ],
}

OUTRO_TEXT = {
    "ar": "يعطيك العافية، شكراً على وقتك. بنتواصل معك قريباً بإذن الله.",
    "en": "Thanks for your time. We'll be in touch soon.",
}


def pick_intro(language: str, name: str | None = None) -> str:
    lang = language if language in INTRO_VARIANTS else "en"
    text = random.choice(INTRO_VARIANTS[lang])
    if name:
        if lang == "ar":
            text = text.replace("!", f" {name}!", 1)
        else:
            text = text.replace("!", f", {name}!", 1)
    return text


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
        model=GEN_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return _safe_json(resp.choices[0].message.content)


# ─────────────────────────────────────────
#  MERGED: EVALUATE + DECIDE (single LLM call)
# ─────────────────────────────────────────

SCORING_CRITERIA = {
    "technical": (
        "Focus on: technical accuracy, depth of knowledge, correct terminology, "
        "practical examples. Weight: 60% correctness, 25% depth, 15% communication."
    ),
    "behavioral": (
        "Focus on: specific examples using STAR method (Situation, Task, Action, Result), "
        "self-awareness, emotional intelligence, relevance to workplace scenarios, lessons learned. "
        "Weight: 40% concrete examples, 30% relevance, 30% reflection."
    ),
    "general": (
        "Focus on: clarity, relevance to the role, self-awareness, "
        "and professional presentation. Weight: equal across all."
    ),
}


def evaluate_and_decide(
    answer: str,
    question: str,
    role: str,
    language: str,
    question_type: str = "technical",
    body_language_desc: str = "",
    tone_desc: str = "",
) -> dict:
    # Map legacy "soft" to "behavioral"
    if question_type == "soft":
        question_type = "behavioral"
    criteria = SCORING_CRITERIA.get(question_type, SCORING_CRITERIA["general"])
    lang_note = "Respond in Arabic." if language == "ar" else "Respond in English."

    type_guidance = ""
    if question_type == "technical":
        type_guidance = "For technical: if answer lacks depth, follow up on implementation or trade-offs."
    elif question_type == "behavioral":
        type_guidance = "For behavioral: if answer lacks a concrete example, ask for a specific situation."

    extra_context = ""
    if body_language_desc:
        extra_context += f"\n\nBODY LANGUAGE:\n{body_language_desc}"
    if tone_desc:
        extra_context += f"\n\nVOCAL TONE:\n{tone_desc}"

    schema = {
        "answer_type": "answered | partial | admitted_ignorance | off_topic",
        "score": "0-100",
        "strengths": ["..."],
        "weaknesses": ["..."],
        "skill_match": "0-100",
        "communication_score": "0-100",
        "final_feedback": "concise feedback",
        "action": "follow_up | next | re_ask",
        "follow_up_question": "only if action is follow_up",
        "correct_answer": "only if admitted_ignorance or partial",
    }

    prompt = f"""You are an expert interviewer evaluating a candidate's response.

STEP 1 — CLASSIFY the answer:
- "answered": gave a substantive answer
- "partial": expressed uncertainty but attempted ("I think...", "I'm not sure but...")
- "admitted_ignorance": honestly said they don't know ("I haven't used that", "I'm not familiar")
- "off_topic": irrelevant or joke answer

STEP 2 — SCORE based on type:
- answered → score normally
- partial → 25-50 credit, confirm/correct their guess in correct_answer
- admitted_ignorance → 20-35 for honesty, provide correct answer in correct_answer
- off_topic → 0-10, action = "re_ask"

STEP 3 — DECIDE action:
- admitted_ignorance → "next" (don't drill into what they don't know)
- off_topic → "re_ask"
- partial → "next" (credit them, move on)
- answered + score < 50 → "follow_up"
- answered + score >= 70 → "next"
- answered + 50-70 → judgment call, prefer "next" for pace
{type_guidance}

Question type: {question_type}
Criteria: {criteria}
Role: {role}
{lang_note}
{extra_context}

Return ONLY JSON:
{json.dumps(schema, indent=2)}

Question: \"\"\"{question}\"\"\"
Answer: \"\"\"{answer}\"\"\""""

    resp = client.chat.completions.create(
        model=EVAL_MODEL,
        messages=[
            {"role": "system", "content": "Strict but fair interview evaluator. Evaluate AND decide next action. JSON only, no markdown."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    result = _safe_json(resp.choices[0].message.content)
    result.setdefault("answer_type", "answered")
    result.setdefault("action", "next")
    result.setdefault("follow_up_question", "")
    result.setdefault("correct_answer", "")
    result.setdefault("score", 0)

    # Force action based on answer_type
    if result["answer_type"] == "admitted_ignorance":
        result["action"] = "next"
    if result["answer_type"] == "off_topic" and result["action"] != "re_ask":
        result["action"] = "re_ask"

    # Parse and clamp score
    try: result["score"] = int(result["score"])
    except (ValueError, TypeError): result["score"] = 0

    # Enforce score ranges per answer_type — LLM sometimes ignores these
    at = result["answer_type"]
    s = result["score"]
    if at == "admitted_ignorance":
        result["score"] = max(20, min(35, s)) if s > 0 else 25
    elif at == "off_topic":
        result["score"] = min(10, s)
    elif at == "partial":
        result["score"] = max(25, min(50, s)) if s > 0 else 30

    # Fallback: if admitted_ignorance/partial but no correct_answer, generate one
    if at in ("admitted_ignorance", "partial") and not (result.get("correct_answer") or "").strip():
        result["correct_answer"] = _generate_correct_answer(question, role, language)

    return result


def _generate_correct_answer(question: str, role: str, language: str) -> str:
    """Quick fallback to generate a correct answer when the eval LLM didn't provide one."""
    lang_note = "Answer in Arabic." if language == "ar" else "Answer in English."
    try:
        resp = client.chat.completions.create(
            model=GEN_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert interviewer. Give a concise, correct answer to this interview question. Plain text only, no markdown."},
                {"role": "user", "content": f"Role: {role}\n{lang_note}\n\nQuestion: {question}\n\nProvide a strong sample answer in 2-4 sentences."},
            ],
            temperature=0.3,
            max_tokens=300,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return ""


# Legacy wrappers
def score_answer(answer, question, role, language, question_type="technical",
                 body_language_desc="", tone_desc="") -> dict:
    r = evaluate_and_decide(answer=answer, question=question, role=role,
        language=language, question_type=question_type,
        body_language_desc=body_language_desc, tone_desc=tone_desc)
    return {k: r.get(k) for k in ("score", "strengths", "weaknesses", "skill_match",
        "communication_score", "final_feedback", "answer_type", "correct_answer")}

def decide_next(question, answer, evaluation, role, language, question_type="technical") -> dict:
    if "action" in evaluation:
        return {"action": evaluation["action"], "question": evaluation.get("follow_up_question", "")}
    return {"action": "next", "question": ""}


# ─────────────────────────────────────────
#  CV QUESTION GENERATION
# ─────────────────────────────────────────

def generate_cv_questions(
    role: str,
    language: str,
    count: int = 2,
    cv_summary: str = "",
    company: str | None = None,
) -> list[dict]:
    """
    Generate interview questions that probe the candidate's CV.
    Varies across projects, skills, certifications, and experience.
    Each question is prefixed with a CV reference.

    Returns list of {"question_text", "question_type", "difficulty", "source"}.
    NOT saved to the Question table.
    """
    if language == "ar":
        lang_note = "Generate questions in Arabic."
        prefix_instruction = (
            'Every question MUST start with a phrase referencing the CV, such as: '
            '"ذكرت في سيرتك الذاتية..." أو "لاحظت في سيرتك أنك..." أو "كتبت في سيرتك أنك عملت على..." '
            'Use varied openings — do not start every question the same way.'
        )
    else:
        lang_note = "Generate questions in English."
        prefix_instruction = (
            'Every question MUST start with a phrase referencing the CV, such as: '
            '"You mentioned in your CV that...", "I noticed on your resume that...", '
            '"Your CV shows that you worked on...", "According to your resume..." '
            'Use varied openings — do not start every question the same way.'
        )

    company_note = f"\nTarget company: {company}." if company else ""

    # Pick which CV areas to focus on based on count
    if count == 1:
        focus = "Pick ONE area from: a specific project, a technical skill, a certification, or a work experience entry. Choose randomly."
    elif count == 2:
        focus = "Pick TWO DIFFERENT areas: e.g. one about a project and one about a skill. Do NOT ask about the same project/skill twice."
    else:
        focus = f"Pick {count} DIFFERENT areas spread across: projects, technical skills, certifications, and work experience. Each question must target a DIFFERENT item from the CV."

    prompt = f"""Generate {count} interview questions that probe this candidate's CV for the role: {role}

IMPORTANT RULES:
1. {prefix_instruction}
2. {focus}
3. Each question must test whether the candidate truly did what they claim.
4. Vary question styles:
   - For projects: "Walk me through how you built X" / "What was the hardest part of X?"
   - For skills: "You listed Y — can you explain a real scenario where you used it?"
   - For certifications: "You have Z certification — how has it applied to your work?"
   - For experience: "You worked at W as a [role] — what was your main contribution?"
5. Do NOT generate generic questions. Each must reference something specific from the CV.
6. Do NOT ask about the same project or skill more than once even across different sessions.

{lang_note}{company_note}

Candidate's CV summary:
\"\"\"{cv_summary}\"\"\"

Return ONLY a JSON array:
[{{"question_text": "...", "question_type": "technical|behavioral", "difficulty": 2-4, "cv_area": "project|skill|certification|experience"}}]"""

    resp = client.chat.completions.create(
        model=GEN_MODEL,
        messages=[
            {"role": "system", "content": "Interview question designer specializing in CV-based probing. You create unique, varied questions each time. Output JSON array only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,  # higher for variety across sessions
    )

    data = _safe_json_array(resp.choices[0].message.content or "[]")
    questions = []
    for item in data[:count]:
        if not isinstance(item, dict) or not item.get("question_text"):
            continue
        questions.append({
            "question_text": item["question_text"],
            "question_type": item.get("question_type", "technical"),
            "difficulty": min(5, max(1, int(item.get("difficulty", 3)))),
            "source": "cv_generated",
        })
    return questions


# ─────────────────────────────────────────
#  GENERIC AI QUESTION GENERATION (kept for backward compat)
# ─────────────────────────────────────────

def generate_ai_questions(
    role: str,
    language: str,
    count: int = 5,
    tech_ratio: int = 50,
    company: str | None = None,
    cv_summary: str | None = None,
) -> list[dict]:
    """Generate interview questions. If cv_summary is provided, delegates to generate_cv_questions."""
    if cv_summary:
        return generate_cv_questions(role=role, language=language, count=count,
                                     cv_summary=cv_summary, company=company)

    num_tech = round(count * tech_ratio / 100)
    num_soft = count - num_tech
    lang_note = "Generate questions in Arabic." if language == "ar" else "Generate questions in English."
    company_note = f"\nTarget company: {company}." if company else ""

    prompt = f"""Generate {count} interview questions for the role: {role}

Breakdown: {num_tech} technical, {num_soft} soft/behavioral.
{lang_note}{company_note}

Return ONLY a JSON array:
[{{"question_text": "...", "question_type": "technical|soft|behavioral", "difficulty": 1-5}}]

Rules:
- Technical: test real knowledge, not definitions
- Soft/behavioral: "Tell me about a time..." or scenario format
- Vary difficulty (mix of 2, 3, 4)
- Specific to the role"""

    resp = client.chat.completions.create(
        model=GEN_MODEL,
        messages=[
            {"role": "system", "content": "Interview question designer. JSON array only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
    )

    data = _safe_json_array(resp.choices[0].message.content or "[]")
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
