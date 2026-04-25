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
        q_text = (
            (q.question_text_ar if s.language == "ar" else q.question_text_en)
            or q.question_text_en
            or q.question_text_ar
            or ""
        )
        item = {
            "session_question_id": str(sq.id),
            "question_id": str(q.id),
            "question_text": q_text,
            "user_answer": sq.user_answer,
            "score": sq.score,
            "ai_feedback": sq.ai_feedback,
        }
        questions.append(item)
        if sq.user_answer is not None and sq.score is not None:
            answered_scores.append(int(sq.score))

    bank_avg = int(sum(answered_scores) / len(answered_scores)) if answered_scores else None

    # Decide what "overall" means for you:
    # Option A) overall = bank_avg
    overall = bank_avg

    # Option B) include intro as 20% weight (example)
    # if s.intro_score is not None and bank_avg is not None:
    #     overall = int(0.2 * s.intro_score + 0.8 * bank_avg)

    return {
        "session_id": str(s.id),
        "role_name": s.role_name,
        "language": s.language,
        "phase": s.phase,
        "intro_score": s.intro_score,
        "intro_feedback": s.intro_feedback,
        "bank_average": bank_avg,
        "overall_score": overall,
        "questions": questions,
    }
