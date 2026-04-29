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
        "You are a professional interview coach. Evaluate the candidate's "
        "'Tell me about yourself' answer. Be fair — acknowledge effort but "
        "don't inflate scores for weak answers. Output JSON only, no markdown."
    )
    schema = {
        "score": "0-100",
        "mentioned_major": True,
        "mentioned_interest": True,
        "mentioned_experience": True,
        "missing": [],
        "feedback": "",
    }
    lang_note = "Respond in Arabic." if language == "ar" else "Respond in English."
    prompt = f"""Evaluate this self-introduction answer.

The candidate can share their background in many ways. Consider ALL of these as valid content:
- Major / field of study / specialization
- Career interests, passions, goals
- Work experience, internships, freelance work
- Personal projects, side projects, open source contributions
- Skills, tools, technologies they use
- Certifications, courses, bootcamps
- General background story (where they're from, what led them here)
- Career transition story
- What motivates or drives them

Scoring guidance:
- Rich, detailed self-intro covering multiple aspects → 75-90
- Decent intro covering 2-3 aspects → 55-70
- Brief but on-topic (shares something genuine about themselves) → 40-55
- Vague or barely relevant → 20-40
- Off-topic or empty → 0-20

The "mentioned_major", "mentioned_interest", "mentioned_experience" fields should be true/false booleans
(not strings). Set them to true if the candidate mentioned ANYTHING in those broad categories.
For example: talking about a personal project counts as "experience". Mentioning what excites them
counts as "interest". Any mention of their field counts as "major".

{lang_note}

Return ONLY JSON matching this structure: {json.dumps(schema)}

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
        "Focus on: technical accuracy, understanding of core concepts, correct terminology, "
        "practical examples. Partial knowledge of the right concepts is better than silence, "
        "but a wrong answer is still wrong — don't inflate it. "
        "Weight: 50% correctness, 25% depth, 25% communication."
    ),
    "behavioral": (
        "Focus on: specific examples (STAR method is ideal but not required), "
        "self-awareness, relevance to workplace scenarios, and lessons learned. "
        "Accept genuine reflection even without perfect structure, but vague answers "
        "like 'I'm a team player' without evidence should score low. "
        "Weight: 35% concrete examples, 35% relevance, 30% reflection."
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
    profile_context: dict | None = None,
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

    # ── Profile-aware context ──
    profile_note = ""
    if profile_context:
        status = profile_context.get("status", "")
        yoe = profile_context.get("years_of_experience", 0)
        has_exp = profile_context.get("has_experience", False)

        if status == "student":
            profile_note = (
                "\n\nCANDIDATE CONTEXT: This is a student with no/limited work experience. "
                "Adjust expectations: accept academic projects and coursework as valid examples. "
                "Don't penalize for lack of industry experience. Focus on understanding of concepts "
                "rather than production-level depth."
            )
        elif status == "graduate" and not has_exp:
            profile_note = (
                "\n\nCANDIDATE CONTEXT: Recent graduate with limited work experience. "
                "Academic projects, internships, and personal projects count as valid experience. "
                "Focus on conceptual understanding and learning ability."
            )
        elif has_exp and yoe >= 3:
            profile_note = (
                f"\n\nCANDIDATE CONTEXT: Experienced professional ({yoe}+ roles). "
                "Expect concrete real-world examples and deeper technical depth. "
                "Vague or purely academic answers should be scored lower for this experience level."
            )
        elif has_exp:
            profile_note = (
                f"\n\nCANDIDATE CONTEXT: Has some work experience ({yoe} role(s)). "
                "Expect a mix of academic and practical knowledge."
            )

    extra_context = ""
    if profile_note:
        extra_context += profile_note
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
This is a practice interview for learning — be honest but constructive.

STEP 1 — CLASSIFY the answer:
- "answered": gave a substantive answer (even if imperfect — partial knowledge counts)
- "partial": expressed uncertainty but attempted ("I think...", "I'm not sure but...")
- "admitted_ignorance": honestly said they don't know ("I haven't used that", "I'm not familiar")
- "off_topic": irrelevant or joke answer

STEP 2 — SCORE based on type:
- answered → score fairly: mostly correct with minor gaps = 60-75, solid = 75-90, exceptional = 90+.
  But if the answer is factually WRONG or shows misunderstanding, score 25-45 even if confident.
- partial → 30-55 credit based on how close their guess was
- admitted_ignorance → 20-40 for honesty, provide correct answer in correct_answer
- off_topic → 0-15, action = "re_ask"

SCORING PHILOSOPHY: Reward genuine understanding, not just confidence. A hesitant but correct
answer beats a confident wrong one. A candidate who gets the concept right but misses details
deserves 55-70. Reserve below 35 for answers showing no relevant knowledge at all.

STEP 3 — DECIDE action:
- admitted_ignorance → "next" (don't drill into what they don't know)
- off_topic → "re_ask"
- partial → "next" (credit them, move on)
- answered + score < 45 → "follow_up"
- answered + score >= 65 → "next"
- answered + 45-65 → judgment call, prefer "next" for pace
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
            {"role": "system", "content": "Professional interview evaluator. Be fair — reward real knowledge, don't inflate weak answers. Evaluate AND decide next action. JSON only, no markdown."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
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
        result["score"] = max(20, min(40, s)) if s > 0 else 25
    elif at == "off_topic":
        result["score"] = min(15, s)
    elif at == "partial":
        result["score"] = max(30, min(55, s)) if s > 0 else 35

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


def generate_brief_explanation(question: str, role: str, language: str) -> str:
    """
    Generate a brief educational explanation when the user doesn't know the answer.
    This teaches them the concept so they learn, not just get scored.
    """
    lang_note = "Respond in Arabic." if language == "ar" else "Respond in English."
    try:
        resp = client.chat.completions.create(
            model=GEN_MODEL,
            messages=[
                {"role": "system", "content": (
                    "You are a friendly teacher helping someone prepare for interviews. "
                    "Explain the concept briefly so they understand it for next time. "
                    "Keep it practical — what it is, why it matters, and a simple example. "
                    "3-5 sentences max. Plain text only, no markdown."
                )},
                {"role": "user", "content": (
                    f"Role: {role}\n{lang_note}\n\n"
                    f"The candidate was asked this interview question and didn't know the answer:\n"
                    f"\"{question}\"\n\n"
                    f"Give a brief, friendly explanation of the concept so they can learn it."
                )},
            ],
            temperature=0.4,
            max_tokens=400,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return ""


def classify_user_input(
    user_text: str,
    current_question: str,
    role: str,
    language: str,
) -> dict:
    """
    Classify whether the user's input is an answer, a clarification request,
    or a curiosity/learning request.

    Returns:
        {"type": "answer"} — normal answer, proceed to evaluation
        {"type": "clarification", "response": "..."} — user asked what the question means
        {"type": "curiosity", "response": "..."} — user wants to learn about the topic
    """
    lang_note = "Respond in Arabic." if language == "ar" else "Respond in English."

    prompt = f"""The candidate is in an interview for the role: {role}
They were asked: \"\"\"{current_question}\"\"\"
They responded: \"\"\"{user_text}\"\"\"

Classify their response:
1. "answer" — they are attempting to answer the question (even poorly, even "I don't know")
2. "clarification" — they are asking what the question means, asking for context,
   or requesting the interviewer to rephrase/explain the question
3. "curiosity" — they already said they don't know BUT are now asking to learn about the topic.
   e.g. "Can you explain what that is?", "I'd love to know more about this",
   "What does that mean?", "Why is it important?", "وش يعني هالشي؟", "ممكن توضح؟"

IMPORTANT: "I don't know" by itself is an ANSWER (type "answer"), not curiosity.
Curiosity is when they explicitly ask the interviewer to teach/explain the concept.

If it's a clarification, provide a helpful response that:
- Explains what the question is looking for (without giving away the answer)
- Gives them a hint about what direction to take
- Keeps it to 2-3 sentences

If it's curiosity, provide a brief educational explanation:
- What the concept is, why it matters, a simple example
- 3-4 sentences max, practical and friendly

{lang_note}
Return ONLY JSON:
  {{"type": "answer"}}
  or {{"type": "clarification", "response": "..."}}
  or {{"type": "curiosity", "response": "..."}}"""

    try:
        resp = client.chat.completions.create(
            model=GEN_MODEL,
            messages=[
                {"role": "system", "content": "Interview assistant. Classify the candidate's response. JSON only, no markdown."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=400,
        )
        result = _safe_json(resp.choices[0].message.content)
        if result.get("type") in ("answer", "clarification", "curiosity"):
            return result
        return {"type": "answer"}
    except Exception:
        return {"type": "answer"}


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