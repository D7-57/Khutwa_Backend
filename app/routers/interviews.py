import random
import math
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_
from io import BytesIO
from fastapi.responses import StreamingResponse

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.question import Question
from app.models.profile import Profile
from app.models.cv import CVDocument
from app.models.interview import InterviewSession, SessionQuestion
from app.services.ai_interview import (
    evaluate_intro,
    score_answer,
    decide_next,
    generate_ai_questions,
)
from app.services.stt import transcribe_audio
from app.services.tts import synthesize_question_audio
from app.services.interview_summary import build_interview_summary

router = APIRouter(prefix="/interviews", tags=["interviews"])

INTRO_TEXT = {
    "ar": "السلام عليكم! قبل ما نبدأ، عرّفني بنفسك: تخصصك، اهتمامك، وخبراتك أو مشاريع اشتغلت عليها.",
    "en": "Hi! Before we start, tell me about yourself: your major, interests, and any projects or experience.",
}
OUTRO_TEXT = {
    "ar": "يعطيك العافية، شكراً على وقتك. بنتواصل معك قريباً بإذن الله.",
    "en": "Thanks for your time. We'll be in touch soon.",
}


# ─────────────────────────────────────────
#  START
# ─────────────────────────────────────────


class StartInterviewRequest(BaseModel):
    role_name: str
    num_questions: int = 5
    followup_max: int = 1
    question_source: str = "bank"  # bank | ai | mix
    tech_ratio: int = 50  # 0-100 (% technical vs soft)
    company: str | None = None
    use_cv: bool = False


@router.post("/start")
def start_interview(
    body: StartInterviewRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    language = _get_language(db, uid)

    # ── collect questions based on source ──
    chosen_questions = []  # list of (question_text, question_type, question_id_or_None)

    if body.question_source in ("bank", "mix"):
        chosen_questions.extend(
            _select_bank_questions(db, body, language, uid)
        )

    if body.question_source in ("ai", "mix"):
        # for "mix", fill remaining slots with AI
        remaining = body.num_questions - len(chosen_questions)
        if remaining > 0:
            cv_summary = _get_cv_summary(db, uid) if body.use_cv else None
            ai_qs = generate_ai_questions(
                role=body.role_name,
                language=language,
                count=remaining,
                tech_ratio=body.tech_ratio,
                company=body.company,
                cv_summary=cv_summary,
            )
            for aq in ai_qs:
                # store AI questions in the bank for future use
                q = Question(
                    role_name=body.role_name,
                    question_text=aq["question_text"],
                    question_type=aq.get("question_type", "general"),
                    difficulty=aq.get("difficulty", 3),
                    source="ai_generated",
                    company=body.company,
                    language=language,
                )
                db.add(q)
                db.flush()
                chosen_questions.append((q.question_text, q.question_type, q.id))

    if not chosen_questions:
        raise HTTPException(400, detail="No questions available for this role and configuration.")

    # trim to requested count
    chosen_questions = chosen_questions[:body.num_questions]

    # ── create session ──
    session = InterviewSession(
        user_id=uid,
        role_name=body.role_name,
        language=language,
        question_source=body.question_source,
        company=body.company,
        tech_ratio=body.tech_ratio,
        use_cv=body.use_cv,
        phase="intro",
        current_index=0,
        followup_count=0,
        intro_evaluation_json={"followup_max": body.followup_max},
    )
    db.add(session)
    db.flush()

    # ── create session questions ──
    first_sq_id = None
    for i, (q_text, q_type, q_id) in enumerate(chosen_questions):
        sq = SessionQuestion(
            session_id=session.id,
            question_id=q_id,
            question_type=q_type,
        )
        db.add(sq)
        db.flush()
        if i == 0:
            first_sq_id = sq.id

    session.current_sq_id = first_sq_id
    db.commit()
    db.refresh(session)

    return {
        "session_id": str(session.id),
        "phase": "intro",
        "prompt_type": "intro",
        "prompt_text": INTRO_TEXT.get(language, INTRO_TEXT["en"]),
        "config": {
            "question_source": body.question_source,
            "tech_ratio": body.tech_ratio,
            "company": body.company,
            "use_cv": body.use_cv,
            "num_questions": len(chosen_questions),
        },
    }


# ─────────────────────────────────────────
#  TURN
# ─────────────────────────────────────────


@router.post("/{session_id}/turn")
async def turn(
    session_id: str,
    answer_text: str | None = Form(default=None),
    audio: UploadFile | None = File(default=None),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    s = db.get(InterviewSession, UUID(session_id))
    if not s or str(s.user_id) != user_id:
        raise HTTPException(404, detail="Session not found")

    language = s.language or "en"

    # ── transcribe audio if provided ──
    transcript = None
    if audio is not None:
        audio_bytes = await audio.read()
        transcript = transcribe_audio(
            audio_bytes,
            filename=audio.filename or "answer.webm",
            language=language,
        )
        answer = transcript
    else:
        answer = (answer_text or "").strip()

    if not answer:
        raise HTTPException(400, detail="Provide answer_text or audio")

    followup_max = _get_followup_max(s)

    # ── INTRO PHASE ──
    if s.phase == "intro":
        return _handle_intro(s, answer, transcript, language, db)

    # ── FINISHED ──
    if s.phase in ("outro", "finished"):
        s.phase = "finished"
        db.commit()
        return {
            "phase": "finished",
            "prompt_type": "outro",
            "prompt_text": OUTRO_TEXT.get(language, OUTRO_TEXT["en"]),
            "transcript": transcript,
        }

    # ── BANK PHASE ──
    return _handle_bank(s, answer, transcript, language, followup_max, db)


# ─────────────────────────────────────────
#  QUESTION AUDIO
# ─────────────────────────────────────────


@router.get(
    "/{session_id}/question-audio/{question_id}",
    responses={200: {"content": {"audio/mpeg": {}}}},
)
def question_audio(
    session_id: str,
    question_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    s = db.get(InterviewSession, UUID(session_id))
    if not s or str(s.user_id) != user_id:
        raise HTTPException(404, detail="Session not found")

    q = db.get(Question, UUID(question_id))
    if not q:
        raise HTTPException(404, detail="Question not found")

    audio_bytes = synthesize_question_audio(q.question_text, language=s.language)
    return StreamingResponse(BytesIO(audio_bytes), media_type="audio/mpeg")


# ─────────────────────────────────────────
#  SUMMARY
# ─────────────────────────────────────────


@router.get("/{session_id}/summary")
def get_interview_summary(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    s = db.get(InterviewSession, UUID(session_id))
    if not s or str(s.user_id) != user_id:
        raise HTTPException(404, detail="Session not found")

    return build_interview_summary(db, s.id)


# ─────────────────────────────────────────
#  LIST USER SESSIONS
# ─────────────────────────────────────────


@router.get("")
def list_my_interviews(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    sessions = (
        db.query(InterviewSession)
        .filter(InterviewSession.user_id == uid)
        .order_by(InterviewSession.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "session_id": str(s.id),
            "role_name": s.role_name,
            "phase": s.phase,
            "total_score": s.total_score,
            "question_source": s.question_source,
            "company": s.company,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sessions
    ]


# ═══════════════════════════════════════════
#  PRIVATE HELPERS
# ═══════════════════════════════════════════


def _get_language(db: Session, user_id: UUID) -> str:
    p = db.get(Profile, user_id)
    return p.language if p and p.language in ("ar", "en") else "en"


def _get_followup_max(s: InterviewSession) -> int:
    if isinstance(s.intro_evaluation_json, dict):
        return int(s.intro_evaluation_json.get("followup_max", 1))
    return 1


def _get_cv_summary(db: Session, user_id: UUID) -> str | None:
    """Get a brief CV summary for AI question generation."""
    doc = (
        db.query(CVDocument)
        .filter(CVDocument.user_id == user_id)
        .order_by(CVDocument.created_at.desc())
        .first()
    )
    if not doc or not doc.extracted_data:
        return None

    data = doc.extracted_data
    parts = []
    summary = data.get("summary", "")
    if summary:
        parts.append(summary[:300])

    skills = data.get("skills", {})
    if isinstance(skills, dict):
        all_skills = skills.get("technical", []) + skills.get("tools", [])
    elif isinstance(skills, list):
        all_skills = skills
    else:
        all_skills = []
    if all_skills:
        parts.append(f"Skills: {', '.join(all_skills[:15])}")

    return "\n".join(parts) if parts else None


def _select_bank_questions(
    db: Session,
    body: StartInterviewRequest,
    language: str,
    user_id: UUID,
) -> list[tuple[str, str, UUID]]:
    """Select questions from the bank with type ratio, company priority, and dedup.

    Avoids questions the user has already seen in past sessions.
    Falls back to repeats only if unseen pool is exhausted.
    """

    # ── 1. get question IDs user has already been asked ──
    seen_subq = (
        db.query(SessionQuestion.question_id)
        .join(InterviewSession, InterviewSession.id == SessionQuestion.session_id)
        .filter(InterviewSession.user_id == user_id)
    )
    seen_ids: set[UUID] = {row[0] for row in seen_subq.all()}

    # ── 2. fetch all APPROVED bank questions for this role ──
    base_q = db.query(Question).filter(
        Question.role_name == body.role_name,
        Question.status == "approved",
    )

    lang_qs = base_q.filter(Question.language == language).all()
    if not lang_qs:
        lang_qs = base_q.all()

    if not lang_qs:
        return []

    # ── 3. split into unseen and seen ──
    unseen = [q for q in lang_qs if q.id not in seen_ids]
    seen_fallback = [q for q in lang_qs if q.id in seen_ids]

    # use unseen first; if not enough, allow repeats
    pool = unseen if unseen else seen_fallback

    # ── 4. company filter: prioritize company-specific ──
    company_qs = []
    general_qs = []
    for q in pool:
        if body.company and q.company and q.company.lower() == body.company.lower():
            company_qs.append(q)
        else:
            general_qs.append(q)

    # ── 5. split by type ──
    tech_qs = [q for q in general_qs if q.question_type == "technical"]
    soft_qs = [q for q in general_qs if q.question_type in ("soft", "behavioral", "general")]

    num_tech = round(body.num_questions * body.tech_ratio / 100)
    num_soft = body.num_questions - num_tech

    # ── 6. build selection: company first, then typed, then fill ──
    selected: list[tuple[str, str, UUID]] = []
    selected_ids: set[UUID] = set()

    def _add(q: Question):
        if q.id not in selected_ids:
            selected.append((q.question_text, q.question_type, q.id))
            selected_ids.add(q.id)

    random.shuffle(company_qs)
    for q in company_qs[:2]:
        _add(q)

    remaining_tech = max(0, num_tech - sum(1 for _, t, _ in selected if t == "technical"))
    remaining_soft = max(0, num_soft - sum(1 for _, t, _ in selected if t != "technical"))

    random.shuffle(tech_qs)
    random.shuffle(soft_qs)

    for q in tech_qs[:remaining_tech]:
        _add(q)
    for q in soft_qs[:remaining_soft]:
        _add(q)

    # fill remaining from any leftover
    leftover = tech_qs[remaining_tech:] + soft_qs[remaining_soft:]
    random.shuffle(leftover)
    for q in leftover:
        if len(selected) >= body.num_questions:
            break
        _add(q)

    # ── 7. if unseen wasn't enough, supplement with seen ──
    if len(selected) < body.num_questions and unseen and seen_fallback:
        random.shuffle(seen_fallback)
        for q in seen_fallback:
            if len(selected) >= body.num_questions:
                break
            _add(q)

    return selected


def _get_current_sq(s: InterviewSession, db: Session) -> SessionQuestion | None:
    """Get the current session question, repairing the pointer if needed."""
    if s.current_sq_id:
        sq = db.get(SessionQuestion, s.current_sq_id)
        if sq and sq.session_id == s.id and sq.user_answer is None:
            return sq

    # pointer missing or stale — find next unanswered
    sq = (
        db.query(SessionQuestion)
        .filter(
            SessionQuestion.session_id == s.id,
            SessionQuestion.user_answer.is_(None),
        )
        .order_by(SessionQuestion.id)
        .first()
    )
    if sq:
        s.current_sq_id = sq.id
    return sq


def _advance_pointer(s: InterviewSession, db: Session) -> SessionQuestion | None:
    """Move pointer to next unanswered question."""
    sq = (
        db.query(SessionQuestion)
        .filter(
            SessionQuestion.session_id == s.id,
            SessionQuestion.user_answer.is_(None),
        )
        .order_by(SessionQuestion.id)
        .first()
    )
    s.current_sq_id = sq.id if sq else None
    return sq


def _update_total_score(s: InterviewSession, db: Session):
    """Recalculate the running average score."""
    answered = (
        db.query(SessionQuestion)
        .filter(
            SessionQuestion.session_id == s.id,
            SessionQuestion.user_answer.isnot(None),
        )
        .all()
    )
    if answered:
        s.total_score = int(sum(x.score or 0 for x in answered) / len(answered))


def _handle_intro(
    s: InterviewSession,
    answer: str,
    transcript: str | None,
    language: str,
    db: Session,
) -> dict:
    intro_eval = evaluate_intro(answer=answer, language=language)
    s.intro_score = int(intro_eval.get("score", 0))
    s.intro_feedback = intro_eval.get("feedback", "")
    s.intro_evaluation_json = {**(s.intro_evaluation_json or {}), "intro": intro_eval}

    s.phase = "bank"
    s.current_index = 0
    s.followup_count = 0
    db.flush()

    sq = _get_current_sq(s, db)
    if not sq:
        s.phase = "outro"
        db.commit()
        return {
            "phase": "outro",
            "prompt_type": "outro",
            "prompt_text": OUTRO_TEXT.get(language, OUTRO_TEXT["en"]),
            "transcript": transcript,
            "intro_evaluation": intro_eval,
        }

    q = db.get(Question, sq.question_id)
    db.commit()
    return {
        "phase": "bank",
        "prompt_type": "bank_question",
        "question_id": str(q.id),
        "question_type": sq.question_type or q.question_type,
        "prompt_text": q.question_text,
        "transcript": transcript,
        "intro_evaluation": intro_eval,
    }


def _handle_bank(
    s: InterviewSession,
    answer: str,
    transcript: str | None,
    language: str,
    followup_max: int,
    db: Session,
) -> dict:
    sq = _get_current_sq(s, db)
    if not sq:
        s.phase = "outro"
        db.commit()
        return {
            "phase": "outro",
            "prompt_type": "outro",
            "prompt_text": OUTRO_TEXT.get(language, OUTRO_TEXT["en"]),
            "transcript": transcript,
            "total_score": s.total_score,
        }

    q = db.get(Question, sq.question_id)
    if not q:
        raise HTTPException(404, detail="Question not found")

    q_type = sq.question_type or q.question_type or "technical"

    # evaluate
    evaluation = score_answer(
        answer=answer,
        question=q.question_text,
        role=s.role_name,
        language=language,
        question_type=q_type,
    )

    decision = decide_next(
        question=q.question_text,
        answer=answer,
        evaluation=evaluation,
        role=s.role_name,
        language=language,
        question_type=q_type,
    )

    # store attempt
    if not sq.evaluation_json:
        sq.evaluation_json = {"attempts": []}
    sq.evaluation_json["attempts"].append({
        "answer": answer,
        "evaluation": evaluation,
        "decision": decision,
    })

    action = decision.get("action", "next")
    followup_question = (decision.get("question") or "").strip()

    # follow-up path
    if action in ("follow_up", "clarify") and s.followup_count < followup_max and followup_question:
        s.followup_count += 1
        db.commit()
        return {
            "phase": "bank",
            "action": "follow_up",
            "prompt_type": "follow_up",
            "prompt_text": followup_question,
            "question_id": str(q.id),
            "question_type": q_type,
            "evaluation": evaluation,
            "transcript": transcript,
            "followup_count": s.followup_count,
            "followup_max": followup_max,
        }

    # finalize this question
    s.followup_count = 0
    final_eval = evaluation

    sq.user_answer = answer
    sq.score = int(final_eval.get("score", 0))
    sq.ai_feedback = final_eval.get("final_feedback", "")
    db.flush()

    _update_total_score(s, db)

    # advance to next
    next_sq = _advance_pointer(s, db)

    if not next_sq:
        s.phase = "outro"
        db.commit()
        return {
            "phase": "outro",
            "action": "end",
            "prompt_type": "outro",
            "prompt_text": OUTRO_TEXT.get(language, OUTRO_TEXT["en"]),
            "evaluation": final_eval,
            "transcript": transcript,
            "total_score": s.total_score,
        }

    next_q = db.get(Question, next_sq.question_id)
    db.commit()
    return {
        "phase": "bank",
        "action": "next",
        "prompt_type": "bank_question",
        "question_id": str(next_q.id),
        "question_type": next_sq.question_type or next_q.question_type,
        "prompt_text": next_q.question_text,
        "evaluation": final_eval,
        "transcript": transcript,
        "total_score": s.total_score,
    }