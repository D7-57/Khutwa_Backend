import json
from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

def score_answer(answer: str, question: str, role: str) -> dict:
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

    raw = resp.choices[0].message.content.strip()
    try:
        return json.loads(raw)
    except Exception:
        # fallback extract JSON block
        start = raw.find("{")
        end = raw.rfind("}")
        return json.loads(raw[start:end+1])

def next_action(question: str, answer: str, evaluation: dict, role: str) -> dict:
    prompt = f"""
You are an adaptive AI interviewer.
Return ONLY JSON:

{{
  "action": "follow_up" | "clarify" | "next" | "end",
  "question": ""
}}

RULES:
- score < 50 → follow_up
- communication_score < 50 → clarify
- score > 75 → next
- if this was the last question → end
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
    raw = resp.choices[0].message.content.strip()
    try:
        return json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        return json.loads(raw[start:end+1])
