from __future__ import annotations
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.interview import InterviewSession, SessionQuestion
from app.models.question import Question


def build_interview_summary(db: Session, session_id: UUID) -> dict:
    s = db.get(InterviewSession, session_id)
    if not s:
        return {"error": "Session not found"}

    rows = (
        db.query(SessionQuestion, Question)
        .join(Question, Question.id == SessionQuestion.question_id)
        .filter(SessionQuestion.session_id == s.id)
        .order_by(SessionQuestion.id)
        .all()
    )

    questions = []
    answered_scores = []

    for sq, q in rows:
        # extract tone + body from the last attempt if available
        last_attempt = {}
        if sq.evaluation_json and sq.evaluation_json.get("attempts"):
            last_attempt = sq.evaluation_json["attempts"][-1]

        item = {
            "session_question_id": str(sq.id),
            "question_id": str(q.id),
            "question_text": q.question_text,
            "question_type": sq.question_type or q.question_type,
            "user_answer": sq.user_answer,
            "score": sq.score,
            "ai_feedback": sq.ai_feedback,
            "attempt_count": len(sq.evaluation_json.get("attempts", [])) if sq.evaluation_json else 0,
        }

        # include tone + body data if present
        if last_attempt.get("tone"):
            item["tone"] = last_attempt["tone"]
        if last_attempt.get("body_language"):
            item["body_language"] = last_attempt["body_language"]

        questions.append(item)
        if sq.user_answer is not None and sq.score is not None:
            answered_scores.append(int(sq.score))

    bank_avg = int(sum(answered_scores) / len(answered_scores)) if answered_scores else None

    # include intro as 20% weight if available
    if s.intro_score is not None and bank_avg is not None:
        overall = int(0.2 * s.intro_score + 0.8 * bank_avg)
    else:
        overall = bank_avg

    # extract session config
    config = s.intro_evaluation_json or {}
    mode = config.get("mode", "text")

    result = {
        "session_id": str(s.id),
        "role_name": s.role_name,
        "language": s.language,
        "phase": s.phase,
        "mode": mode,
        "question_source": s.question_source,
        "company": s.company,
        "intro_score": s.intro_score,
        "intro_feedback": s.intro_feedback,
        "bank_average": bank_avg,
        "overall_score": overall,
        "questions": questions,
    }

    # include intro-level tone/body if captured
    if config.get("intro_tone"):
        result["intro_tone"] = config["intro_tone"]
    if config.get("intro_body_language"):
        result["intro_body_language"] = config["intro_body_language"]

    return result
