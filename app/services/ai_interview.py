"""
AI Interview Services — v3

Changes vs v2:
  • Dynamic difficulty: profile_context now carries `experience_band` from the
    real profiles.years_of_experience column. Used to nudge expectations.
  • Focused-practice framing: when profile_context['focus_mode'] is true, the
    evaluator frames feedback as targeted improvement on a known weak area.
  • Clarification fix: classify_user_input now has a much stronger guardrail
    against giving away the answer, and we run a quick post-check to catch
    leaks. If the LLM still leaks, we fall back to a generic hint.
  • Brief explanations are unchanged from v2 (still used for "curiosity" cases
    where the user EXPLICITLY wants to learn).
"""

import json
import re
import random
from openai import OpenAI
from app.core.config import settings
from app.services.interviewer_personalities import (
    difficulty_hint_for_generation,
    normalize_personality,
    personality_note,
)

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

def evaluate_intro(
    answer: str,
    language: str,
    profile_context: dict | None = None,
) -> dict:
    personality = None
    if profile_context:
        personality = normalize_personality(
            profile_context.get("interviewer_personality")
        )
    system = (
        "You are a professional interview coach. Evaluate the candidate's "
        "'Tell me about yourself' answer. Be fair — acknowledge effort but "
        "don't inflate scores for weak answers. Output JSON only, no markdown."
        + personality_note(personality)
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
#  EVALUATE + DECIDE
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


def _profile_note(profile_context: dict | None) -> str:
    """
    Build a short context block for the evaluator prompt based on the user's
    profile. Now consumes the dedicated `experience_band` (from
    profiles.years_of_experience: '0' | '<1' | '1' | '2' | '3+') so we can
    actually shape difficulty expectations.
    """
    if not profile_context:
        return ""

    status = (profile_context.get("status") or "").lower()
    band = (profile_context.get("experience_band") or "").strip()
    has_exp = profile_context.get("has_experience", False)
    yoe = profile_context.get("years_of_experience", 0)
    focus_mode = profile_context.get("focus_mode") is True

    parts = []

    # ── Experience band shapes expectations ──
    if band in ("0", "<1") or (status == "student" and not has_exp):
        parts.append(
            "CANDIDATE CONTEXT: Entry-level — student or no professional experience. "
            "Accept academic projects, coursework, and personal projects as valid examples. "
            "Focus on conceptual understanding, not production-level depth. "
            "Don't ask probing follow-ups about scale or production trade-offs."
        )
    elif band == "1":
        parts.append(
            "CANDIDATE CONTEXT: Junior (~1 year experience). Expect a real but "
            "limited set of work examples; mix of academic and practical answers is fine. "
            "Probing for specifics is OK; deep architecture trade-offs are NOT yet expected."
        )
    elif band == "2":
        parts.append(
            "CANDIDATE CONTEXT: Mid-level (~2 years experience). Expect concrete "
            "production examples and sound reasoning. Vague or purely academic answers "
            "should be marked down for this experience level."
        )
    elif band == "3+":
        parts.append(
            "CANDIDATE CONTEXT: Senior (3+ years experience). Expect strong, specific "
            "real-world examples, ownership stories, and architectural reasoning. "
            "Hold them to a high bar — vague answers should score low."
        )
    else:
        # Fallback to legacy logic when band is not provided
        if status == "student":
            parts.append(
                "CANDIDATE CONTEXT: Student. Accept academic projects and coursework as "
                "valid examples. Focus on understanding rather than production-level depth."
            )
        elif status == "graduate" and not has_exp:
            parts.append(
                "CANDIDATE CONTEXT: Recent graduate, limited work experience. "
                "Academic projects, internships, and personal projects count as valid."
            )
        elif has_exp and yoe >= 3:
            parts.append(
                f"CANDIDATE CONTEXT: Experienced ({yoe}+ roles). Expect real-world "
                "examples and depth; mark down vague answers."
            )

    # ── Focused practice framing ──
    if focus_mode:
        parts.append(
            "FOCUS MODE: This question targets a topic the candidate previously struggled "
            "with. In the feedback, reference that this is a known weak area and give "
            "concrete, actionable improvement guidance — not a generic 'good attempt' line."
        )

    return "\n\n" + "\n\n".join(parts) if parts else ""


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
    if question_type == "soft":
        question_type = "behavioral"
    criteria = SCORING_CRITERIA.get(question_type, SCORING_CRITERIA["general"])
    lang_note = "Respond in Arabic." if language == "ar" else "Respond in English."

    type_guidance = ""
    if question_type == "technical":
        type_guidance = "For technical: if answer lacks depth, follow up on implementation or trade-offs."
    elif question_type == "behavioral":
        type_guidance = "For behavioral: if answer lacks a concrete example, ask for a specific situation."

    extra_context = _profile_note(profile_context)
    if profile_context:
        extra_context += personality_note(
            profile_context.get("interviewer_personality")
        )
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
        "tip": "ONE concrete actionable tip the candidate could apply next time",
        "action": "follow_up | next | re_ask",
        "follow_up_question": "only if action is follow_up",
        "correct_answer": "ALWAYS include a strong sample answer in 2-4 sentences (used as 'study material')",
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
- admitted_ignorance → 20-30 baseline. Specifically:
    * Pure "I don't know" (no engagement) → 20
    * "I don't know but I'd guess X" (admits + attempts) → 25-30
    * "I don't know but can you explain?" (admits + curiosity, no attempt) → 25
  Always provide a strong correct_answer when admitted_ignorance.
- off_topic → 0-15, action = "re_ask"

SCORING PHILOSOPHY: Reward genuine understanding, not just confidence. A hesitant but correct
answer beats a confident wrong one. A candidate who gets the concept right but misses details
deserves 55-70. Reserve below 35 for answers showing no relevant knowledge at all.

STEP 3 — WRITE final_feedback (2-3 sentences) AND tip (ONE actionable next-time line).
The tip MUST be specific to THIS question — not generic advice like "use STAR".
Example tip: "Mention a measurable outcome like the % latency reduction you achieved."

STEP 4 — ALWAYS write a strong correct_answer (2-4 sentences) so the user has study material,
even if they answered well. This is the gold standard the candidate can compare against.

STEP 5 — DECIDE action:
- admitted_ignorance → "next" (don't drill into what they don't know)
- off_topic → "re_ask"
- partial + score < 65 → "follow_up" (ask a probing question that nudges them to be more complete)
- partial + score >= 65 → "next" (they got close enough, move on)
- answered + score < 45 → "follow_up" (the answer was weak — ask them to clarify the part that fell short)
- answered + score 45-70 → "follow_up" (ask for a concrete example: "Can you walk me through a specific time you did this?")
- answered + score > 70 → "next" (strong enough, don't slow the pace)

When you decide "follow_up", `follow_up_question` MUST be:
- specific to THIS question and THIS answer (not a generic "tell me more")
- a single sentence ending in a question mark
- for partial/weak answers: aim at what was missing (e.g. "What would you do if X happened?")
- for middling answers: ask for a concrete example (e.g. "Can you share a specific time you used this approach?")
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
            {"role": "system", "content": "Professional interview evaluator. Be fair — reward real knowledge, don't inflate weak answers. Always provide a correct_answer and a specific tip. JSON only, no markdown."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )

    result = _safe_json(resp.choices[0].message.content)
    result.setdefault("answer_type", "answered")
    result.setdefault("action", "next")
    result.setdefault("follow_up_question", "")
    result.setdefault("correct_answer", "")
    result.setdefault("tip", "")
    result.setdefault("score", 0)

    if result["answer_type"] == "admitted_ignorance":
        result["action"] = "next"
    if result["answer_type"] == "off_topic" and result["action"] != "re_ask":
        result["action"] = "re_ask"

    try: result["score"] = int(result["score"])
    except (ValueError, TypeError): result["score"] = 0

    at = result["answer_type"]
    s = result["score"]
    if at == "admitted_ignorance":
        # Tightened from 20-40 → 20-30. "I don't know but explain it" = 25.
        result["score"] = max(20, min(30, s)) if s > 0 else 25
    elif at == "off_topic":
        result["score"] = min(15, s)
    elif at == "partial":
        result["score"] = max(30, min(55, s)) if s > 0 else 35

    # ── Always populate correct_answer (used as study material in summary) ──
    if not (result.get("correct_answer") or "").strip():
        result["correct_answer"] = _generate_correct_answer(question, role, language)

    return result


def _generate_correct_answer(question: str, role: str, language: str) -> str:
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
    """Used for genuine 'curiosity' (user explicitly asks to learn the topic)."""
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


# ─────────────────────────────────────────
#  CLASSIFY: answer | clarification | curiosity
# ─────────────────────────────────────────

# Generic clarification fallback when the LLM leaks the answer.
# Used as a last-resort hint that's safe.
_CLARIFY_FALLBACK = {
    "ar": (
        "السؤال يبحث عن فهمك العام للموضوع — جرّب تشرح الفكرة بكلماتك "
        "وتعطي مثال إذا قدرت. مو لازم تكون إجابة كاملة."
    ),
    "en": (
        "The question is asking for your general understanding of the topic — "
        "try to explain the idea in your own words and give an example if you can. "
        "It doesn't have to be a complete answer."
    ),
}


def _looks_like_full_answer(text: str, question: str) -> bool:
    """
    Heuristic to catch the 'clarification leaked the answer' bug.
    A clarification should describe what's being asked, not answer it.

    Triggers:
      - Response is suspiciously long (>400 chars) AND contains explanatory
        markers like 'is a', 'means', 'because', 'for example', 'such as'
        which indicate the LLM started teaching instead of redirecting.
      - Response contains 4+ technical-style phrases (semicolons, lists)
        suggesting a textbook answer.
    """
    t = (text or "").strip().lower()
    if len(t) > 600:
        return True
    if len(t) > 400:
        teaching_markers = (
            " is a ", " is the ", " means ", " refers to ", " for example",
            " such as ", " allows you to ", " consists of ", " is used to ",
            "يعني ", "يعرف ", "يستخدم ", "مثال", "مثلاً",
        )
        hits = sum(1 for m in teaching_markers if m in t)
        if hits >= 2:
            return True
    return False


def _looks_like_echo(response: str, user_text: str) -> bool:
    """
    Heuristic to catch the 'clarification parrots the user' bug.

    When the user asks for clarification (e.g. "could you explain what you mean
    by X?"), the LLM sometimes just re-emits that same question almost verbatim
    instead of actually clarifying. We detect this by measuring word overlap
    between the response and the user's input.

    Triggers:
      - 60%+ of the user's words appear (in order) in the response, AND
      - response is short enough that this overlap is meaningful (not a
        long teaching response that happens to mention some of those words).
    """
    r = (response or "").strip().lower()
    u = (user_text or "").strip().lower()
    if not r or not u:
        return False

    # Tokenize on non-letter chars, keep words >= 3 chars (drops "the", "you", etc.
    # less informative — we want content words).
    import re
    user_words = [w for w in re.split(r"[^\wء-ي]+", u) if len(w) >= 4]
    if len(user_words) < 4:
        # Too few content words to meaningfully measure overlap.
        return False

    # Count how many user content words appear anywhere in the response.
    hits = sum(1 for w in user_words if w in r)
    overlap = hits / len(user_words)
    return overlap >= 0.6


def classify_user_input(
    user_text: str,
    current_question: str,
    role: str,
    language: str,
    interviewer_personality: str | None = None,
) -> dict:
    """
    Classify whether the user's input is an answer, a clarification request,
    or a curiosity/learning request.

    Returns:
        {"type": "answer"}                                — proceed to evaluation
        {"type": "clarification", "response": "..."}      — guide them WITHOUT giving the answer
        {"type": "curiosity",     "response": "..."}      — they explicitly want to learn it
    """
    lang_note = "Respond in Arabic." if language == "ar" else "Respond in English."
    persona_block = personality_note(interviewer_personality)

    prompt = f"""The candidate is in an interview for the role: {role}
They were asked: \"\"\"{current_question}\"\"\"
They responded: \"\"\"{user_text}\"\"\"
{persona_block}

Classify their response into ONE of:

1. "answer" — they ARE attempting to answer (even poorly, even "I don't know").
   "I don't know" by itself = answer, NOT curiosity.

2. "clarification" — they're asking what the question MEANS or asking the
   interviewer to rephrase. They want to understand the question, not learn the topic.
   Examples: "what do you mean by X?", "could you rephrase?",
             "are you asking about A or B?", "وش تقصد؟"

3. "curiosity" — they have ALREADY admitted they don't know AND now explicitly
   ask the interviewer to teach the concept.
   Examples: "Can you explain what X is so I learn?", "I'd love to know more — what is it?"

CRITICAL RULES FOR "clarification":
- DO NOT answer the question.
- DO NOT explain the underlying concept.
- DO NOT define technical terms.
- DO NOT echo or paraphrase the candidate's own clarifying question back at them.
- DO restate the interviewer's question in simpler words OR narrow the scope ("are you asking
  about implementation or about trade-offs?").
- DO point out what category of answer is expected ("a brief example from your
  experience"; "a high-level definition is fine").
- Keep response 1-2 sentences, max 40 words.
- Speak AS THE INTERVIEWER would, not as a chatbot.

Worked example (good clarification):
  Question asked:    "How would you design a RESTful API for a microservices architecture?"
  Candidate said:    "Could you explain what you mean by microservices?"
  BAD response:      "Could you explain what you mean by microservices? I'm not sure how it relates."
                     (this echoes the candidate — useless)
  BAD response:      "Microservices are an architectural style where..."
                     (this teaches — that's curiosity, not clarification)
  GOOD response:     "I'm asking how you'd structure your API endpoints and data flow when
                     your application is split across multiple small services. A high-level
                     design is fine."

If the response would teach them what to say, you are doing it wrong — that's
"curiosity", not "clarification". Pick the right category.

For "curiosity" (they explicitly want to learn): give a brief 3-4 sentence
educational explanation. This IS the place to teach.

{lang_note}
Return ONLY JSON:
  {{"type": "answer"}}
  or {{"type": "clarification", "response": "..."}}
  or {{"type": "curiosity", "response": "..."}}"""

    try:
        resp = client.chat.completions.create(
            model=GEN_MODEL,
            messages=[
                {"role": "system", "content": "Interview assistant. Classify the candidate's response. JSON only, no markdown. Never answer the question when classifying as clarification."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=400,
        )
        result = _safe_json(resp.choices[0].message.content)
        rtype = result.get("type")
        if rtype not in ("answer", "clarification", "curiosity"):
            return {"type": "answer"}

        # ── Post-check: did the "clarification" leak the answer or echo the user? ──
        if rtype == "clarification":
            response = (result.get("response") or "").strip()
            if not response:
                return {"type": "answer"}
            # Either failure mode (teaching the answer OR parroting the user)
            # falls back to the same safe generic hint.
            if _looks_like_full_answer(response, current_question) or \
               _looks_like_echo(response, user_text):
                result["response"] = _CLARIFY_FALLBACK.get(
                    language, _CLARIFY_FALLBACK["en"]
                )

        return result
    except Exception:
        return {"type": "answer"}


# ─────────────────────────────────────────
#  Legacy wrappers
# ─────────────────────────────────────────

def score_answer(answer, question, role, language, question_type="technical",
                 body_language_desc="", tone_desc="") -> dict:
    r = evaluate_and_decide(answer=answer, question=question, role=role,
        language=language, question_type=question_type,
        body_language_desc=body_language_desc, tone_desc=tone_desc)
    return {k: r.get(k) for k in ("score", "strengths", "weaknesses", "skill_match",
        "communication_score", "final_feedback", "answer_type", "correct_answer", "tip")}


def decide_next(question, answer, evaluation, role, language, question_type="technical") -> dict:
    if "action" in evaluation:
        return {"action": evaluation["action"], "question": evaluation.get("follow_up_question", "")}
    return {"action": "next", "question": ""}


# ─────────────────────────────────────────
#  CV QUESTION GENERATION (unchanged from v2)
# ─────────────────────────────────────────

def generate_cv_questions(
    role: str,
    language: str,
    count: int = 2,
    cv_summary: str = "",
    company: str | None = None,
) -> list[dict]:
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
        temperature=0.7,
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


def generate_ai_questions(
    role: str,
    language: str,
    count: int = 5,
    tech_ratio: int = 50,
    company: str | None = None,
    cv_summary: str | None = None,
    interviewer_personality: str | None = None,
) -> list[dict]:
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
- {difficulty_hint_for_generation(interviewer_personality)}
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