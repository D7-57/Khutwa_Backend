"""
Interview summary builder — v3.

Changes vs v2:
  • Always carries `correct_answer`, `final_feedback`, and `tip` per question.
  • `tip` is the new per-question actionable advice from the evaluator (kept
    separate from `final_feedback` so the UI can render them differently).
  • If a question is a 'skipped' (filled in by /finalize), we annotate it
    so the feedback page can render it as 'Skipped' instead of treating
    score=0 as a failure.
  • Practice mode + finished_early are surfaced for the feedback header.
  • Bank questions carry their vote info (upvotes, downvotes, my_vote) so
    the feedback page can render the thumbs up/down row inline.
"""

from __future__ import annotations
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.interview import InterviewSession, SessionQuestion
from app.models.question import Question
from app.models.question_vote import QuestionVote


def build_interview_summary(
    db: Session,
    session_id: UUID,
    user_id: UUID | None = None,
) -> dict:
    s = db.get(InterviewSession, session_id)
    if not s:
        return {"error": "Session not found"}

    sqs = (
        db.query(SessionQuestion)
        .filter(SessionQuestion.session_id == s.id)
        .order_by(SessionQuestion.id)
        .all()
    )

    # Bulk-load this user's votes on the bank questions in this session, so we
    # don't make N round-trips during summary rendering.
    bank_qids = [sq.question_id for sq in sqs if sq.question_id]
    my_votes: dict = {}
    if user_id and bank_qids:
        votes = (
            db.query(QuestionVote)
            .filter(
                QuestionVote.user_id == user_id,
                QuestionVote.question_id.in_(bank_qids),
            )
            .all()
        )
        my_votes = {v.question_id: v.vote for v in votes}

    questions = []
    answered_scores = []

    language = s.language or "en"

    for sq in sqs:
        q_obj = None
        # v3.3.2: source now lives on the SessionQuestion row. Old rows
        # (before the column was added) won't have it — fall back to the
        # text-vs-id heuristic for those, which still works for the
        # CV/bank case but mis-attributes AI to CV. That's acceptable for
        # backward compat.
        if sq.source:
            q_source = sq.source
            if sq.question_text:
                q_text = sq.question_text
            elif sq.question_id:
                q_obj = db.get(Question, sq.question_id)
                q_text = q_obj.get_text(language) if q_obj else ""
            else:
                q_text = ""
        elif sq.question_text:
            q_text = sq.question_text
            q_source = "cv_generated"
        elif sq.question_id:
            q_obj = db.get(Question, sq.question_id)
            q_text = q_obj.get_text(language) if q_obj else ""
            q_source = "bank"
        else:
            q_text = ""
            q_source = "unknown"

        all_attempts = sq.evaluation_json.get("attempts", []) if sq.evaluation_json else []
        last_attempt = all_attempts[-1] if all_attempts else {}

        first_attempt = {}
        for att in all_attempts:
            if not att.get("is_followup") and att.get("evaluation"):
                first_attempt = att
                break
        if not first_attempt:
            first_attempt = last_attempt

        # Narrative feedback should reflect how the candidate left this slot —
        # usually the latest graded attempt — not only the weak first swing.
        eval_data = {}
        for att in reversed(all_attempts):
            ev = att.get("evaluation")
            if isinstance(ev, dict) and ev:
                eval_data = ev
                break
        if not eval_data:
            eval_data = first_attempt.get("evaluation", {}) if first_attempt else {}
        is_skipped = bool(
            (sq.evaluation_json or {}).get("skipped")
            or first_attempt.get("skipped")
        )

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
            "skipped": is_skipped,
        }

        # NEW: vote info for bank questions, so the feedback page can render
        # the thumbs row without a second round-trip per question.
        if q_obj is not None and q_source == "bank":
            item["upvotes"] = int(q_obj.upvotes or 0)
            item["downvotes"] = int(q_obj.downvotes or 0)
            item["my_vote"] = int(my_votes.get(q_obj.id, 0))
            # If the user submitted this question themselves, don't show the
            # vote row at all — the backend would 403 the call anyway.
            item["is_own_submission"] = (
                q_obj.submitted_by is not None
                and user_id is not None
                and q_obj.submitted_by == user_id
            )

        # Always populate these — they're the core of the summary audit.
        item["answer_type"] = eval_data.get("answer_type") or (
            "skipped" if is_skipped else "answered"
        )
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
        # NEW: per-question actionable tip
        if eval_data.get("tip"):
            item["tip"] = eval_data["tip"]

        if last_attempt.get("tone"):
            item["tone"] = last_attempt["tone"]
        if last_attempt.get("body_language"):
            item["body_language"] = last_attempt["body_language"]
        if last_attempt.get("explanation"):
            item["explanation"] = last_attempt["explanation"]

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
                if not followups or followups[-1].get("question") != att["follow_up_question"]:
                    followups.append({
                        "question": att["follow_up_question"],
                        "answer": "", "score": None, "feedback": "",
                    })
        if followups:
            item["followups"] = followups

        questions.append(item)
        # Don't include skipped questions in the answered-scores average so a
        # finished-early session doesn't punish the user for the gaps.
        if (
            sq.user_answer is not None
            and sq.score is not None
            and not is_skipped
        ):
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
        "practice_mode": s.practice_mode,
        "finished_early": s.finished_early,
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