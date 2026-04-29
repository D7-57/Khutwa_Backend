from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import or_
from uuid import UUID

from app.models.interview import InterviewSession, SessionQuestion
from app.models.question import Question


def build_interview_summary(db: Session, session_id: UUID) -> dict:
    s = db.get(InterviewSession, session_id)
    if not s:
        return {"error": "Session not found"}

    # Get all session questions — LEFT JOIN with Question (question_id may be null for CV Qs)
    sqs = (
        db.query(SessionQuestion)
        .filter(SessionQuestion.session_id == s.id)
        .order_by(SessionQuestion.id)
        .all()
    )

    questions = []
    answered_scores = []

    language = s.language or "en"

    for sq in sqs:
        # Resolve question text: from SessionQuestion.question_text (CV) or Question table (bank)
        if sq.question_text:
            q_text = sq.question_text
            q_source = "cv_generated"
        elif sq.question_id:
            q = db.get(Question, sq.question_id)
            q_text = q.get_text(language) if q else ""
            q_source = "bank"
        else:
            q_text = ""
            q_source = "unknown"

        # Get all attempts
        all_attempts = sq.evaluation_json.get("attempts", []) if sq.evaluation_json else []
        last_attempt = all_attempts[-1] if all_attempts else {}

        # Find the first real answer attempt (not a follow-up)
        first_attempt = {}
        for att in all_attempts:
            if not att.get("is_followup") and att.get("evaluation"):
                first_attempt = att
                break
        if not first_attempt:
            first_attempt = last_attempt

        # Use first attempt's evaluation for the main display
        eval_data = first_attempt.get("evaluation", {})

        item = {
            "session_question_id": str(sq.id),
            "question_id": str(sq.question_id) if sq.question_id else None,
            "question_text": q_text,
            "question_type": sq.question_type or "general",
            "question_source": q_source,
            "user_answer": sq.user_answer,
            "score": sq.score,
            "ai_feedback": sq.ai_feedback,
            "attempt_count": len(all_attempts),
        }

        # Include evaluation details from first real attempt
        if eval_data.get("answer_type"):
            item["answer_type"] = eval_data["answer_type"]
        if eval_data.get("correct_answer"):
            item["correct_answer"] = eval_data["correct_answer"]
        if eval_data.get("strengths"):
            item["strengths"] = eval_data["strengths"]
        if eval_data.get("weaknesses"):
            item["weaknesses"] = eval_data["weaknesses"]
        if eval_data.get("skill_match"):
            item["skill_match"] = eval_data["skill_match"]
        if eval_data.get("communication_score"):
            item["communication_score"] = eval_data["communication_score"]
        if eval_data.get("final_feedback"):
            item["final_feedback"] = eval_data["final_feedback"]

        # Tone + body data (from last attempt — most recent recording)
        if last_attempt.get("tone"):
            item["tone"] = last_attempt["tone"]
        if last_attempt.get("body_language"):
            item["body_language"] = last_attempt["body_language"]
        if last_attempt.get("explanation"):
            item["explanation"] = last_attempt["explanation"]

        # ── Follow-up Q&A: collect all follow-up attempts for display ──
        followups = []
        for att in all_attempts:
            if att.get("is_followup"):
                followups.append({
                    "question": att.get("followup_question", ""),
                    "answer": att.get("answer", ""),
                    "score": att.get("evaluation", {}).get("score"),
                    "feedback": att.get("evaluation", {}).get("final_feedback", ""),
                })
            elif att.get("action") == "follow_up" and att.get("follow_up_question"):
                # This attempt triggered a follow-up — note the follow-up question
                if not followups or followups[-1].get("question") != att["follow_up_question"]:
                    followups.append({"question": att["follow_up_question"], "answer": "", "score": None, "feedback": ""})
        if followups:
            item["followups"] = followups

        questions.append(item)
        if sq.user_answer is not None and sq.score is not None:
            answered_scores.append(int(sq.score))

    bank_avg = int(sum(answered_scores) / len(answered_scores)) if answered_scores else None

    if s.intro_score is not None and bank_avg is not None:
        overall = int(0.2 * s.intro_score + 0.8 * bank_avg)
    else:
        overall = bank_avg

    config = s.intro_evaluation_json or {}

    result = {
        "session_id": str(s.id),
        "role_name": s.role_name,
        "language": s.language,
        "phase": s.phase,
        "mode": config.get("mode", "text"),
        "question_source": s.question_source,
        "company": s.company,
        "intro_score": s.intro_score,
        "intro_feedback": s.intro_feedback,
        "bank_average": bank_avg,
        "overall_score": overall,
        "questions": questions,
    }

    if config.get("intro_tone"):
        result["intro_tone"] = config["intro_tone"]
    if config.get("intro_body_language"):
        result["intro_body_language"] = config["intro_body_language"]

    return result