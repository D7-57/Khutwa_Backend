import json
from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def _safe_json(raw: str) -> dict:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        return json.loads(raw[start:end + 1])


def evaluate_intro(answer: str, language: str) -> dict:
    # language: "ar" or "en"
    if language == "ar":
        prompt = f"""
قيّم إجابة المتقدم على سؤال التعريف بالنفس. أعد JSON فقط:

{{
  "score": 0-100,
  "mentioned_major": true/false,
  "mentioned_interest": true/false,
  "mentioned_experience": true/false,
  "missing": [],
  "feedback": ""
}}

إجابة المتقدم: {answer}
"""
    else:
        prompt = f"""
Evaluate the candidate's 'Tell me about yourself' answer. Return JSON only:

{{
  "score": 0-100,
  "mentioned_major": true/false,
  "mentioned_interest": true/false,
  "mentioned_experience": true/false,
  "missing": [],
  "feedback": ""
}}

Answer: {answer}
"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a strict interview evaluator. Output JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return _safe_json(resp.choices[0].message.content)


def score_answer(answer: str, question: str, role: str, language: str) -> dict:
    if language == "ar":
        prompt = f"""
قيّم إجابة مقابلة وظيفية. أعد JSON فقط:

{{
  "score": 0-100,
  "strengths": [],
  "weaknesses": [],
  "skill_match": 0-100,
  "communication_score": 0-100,
  "final_feedback": ""
}}

السؤال: {question}
الإجابة: {answer}
الدور: {role}
"""
    else:
        prompt = f"""
Evaluate the following interview answer. Return ONLY JSON:

{{
  "score": 0-100,
  "strengths": [],
  "weaknesses": [],
  "skill_match": 0-100,
  "communication_score": 0-100,
  "final_feedback": ""
}}

Question: {question}
Answer: {answer}
Role: {role}
"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Strict interview evaluator. Output JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return _safe_json(resp.choices[0].message.content)


def decide_next(question: str, answer: str, evaluation: dict, role: str, language: str) -> dict:
    if language == "ar":
        prompt = f"""
أنت مُحاور ذكي. أعد JSON فقط:

{{
  "action": "follow_up" | "clarify" | "next",
  "question": ""
}}

قواعد:
- score < 50 → follow_up
- communication_score < 50 → clarify
- score > 75 → next
- إذا ذكرت الضعف "detail" اطلب مثال

السؤال: {question}
الإجابة: {answer}
التقييم: {evaluation}
الدور: {role}
"""
    else:
        prompt = f"""
You are an adaptive AI interviewer.
Return ONLY JSON:

{{
  "action": "follow_up" | "clarify" | "next",
  "question": ""
}}

RULES:
- score < 50 → follow_up
- communication_score < 50 → clarify
- score > 75 → next
- weaknesses that mention "detail" → ask for an example

QUESTION: {question}
ANSWER: {answer}
EVALUATION: {evaluation}
ROLE: {role}
"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Adaptive interviewer. Output JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return _safe_json(resp.choices[0].message.content)
