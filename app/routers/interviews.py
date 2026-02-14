import random
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import and_
from io import BytesIO
from fastapi.responses import StreamingResponse

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.question import Question
from app.models.profile import Profile
from app.models.interview import InterviewSession, SessionQuestion
from app.services.ai_interview import evaluate_intro, score_answer, decide_next
from app.services.stt import transcribe_audio
from app.services.tts import synthesize_question_audio

router = APIRouter(prefix="/interviews", tags=["interviews"])

INTRO_AR = "السلام عليكم! قبل ما نبدأ، عرّفني بنفسك: تخصصك، اهتمامك، وخبراتك أو مشاريع اشتغلت عليها."
INTRO_EN = "Hi! Before we start, tell me about yourself: your major, interests, and any projects or experience."

OUTRO_AR = "يعطيك العافية، شكراً على وقتك. بنتواصل معك قريباً بإذن الله."
OUTRO_EN = "Thanks for your time. We’ll be in touch soon."


def _get_language(db: Session, user_id: UUID) -> str:
    p = db.get(Profile, user_id)
    if p and p.language in ("ar", "en"):
        return p.language
    return "en"


@router.post("/start")
def start_interview(
    role_name: str,
    num_questions: int = 5,
    followup_max: int = 1,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    language = _get_language(db, uid)

    qs = db.query(Question).filter(Question.role_name == role_name).all()
    if not qs:
        raise HTTPException(400, detail="No questions for this role")

    chosen = random.sample(qs, k=min(num_questions, len(qs)))

    session = InterviewSession(
        user_id=uid,
        role_name=role_name,
        language=language,
        phase="intro",
        current_index=0,
        followup_count=0,
        intro_evaluation_json={"followup_max": int(followup_max)},
    )
    db.add(session)
    db.flush()  # session.id exists now

    # ✅ CREATE session_questions AND set current_sq_id
    first_sq_id = None
    for i, q in enumerate(chosen):
        sq = SessionQuestion(session_id=session.id, question_id=q.id)
        db.add(sq)
        db.flush()  # sq.id exists now
        if i == 0:
            first_sq_id = sq.id

    session.current_sq_id = first_sq_id

    db.commit()
    db.refresh(session)  # ✅ ensures values reflect DB
    intro_text = INTRO_AR if language == "ar" else INTRO_EN
    return {
        "session_id": str(session.id),
        "phase": session.phase,
        "prompt_type": "intro",
        "prompt_text": intro_text,
    }

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

    audio_bytes = synthesize_question_audio(q.question_text)
    return StreamingResponse(BytesIO(audio_bytes), media_type="audio/mpeg")


@router.post("/{session_id}/turn")
async def turn(
    session_id: str,
    # Either provide answer_text OR audio file
    answer_text: str | None = Form(default=None),
    audio: UploadFile | None = File(default=None),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    s = db.get(InterviewSession, UUID(session_id))
    if not s or str(s.user_id) != user_id:
        raise HTTPException(404, detail="Session not found")

    language = s.language or "en"

    # Transcribe if audio provided
    transcript = None
    if audio is not None:
        audio_bytes = await audio.read()
        transcript = transcribe_audio(audio_bytes, filename=audio.filename or "answer.webm", language=language)
        answer = transcript
    else:
        answer = (answer_text or "").strip()

    if not answer:
        raise HTTPException(400, detail="Provide answer_text or audio")

    followup_max = 1
    if isinstance(s.intro_evaluation_json, dict):
        followup_max = int(s.intro_evaluation_json.get("followup_max", 1))

    # -------------------
    # INTRO PHASE
    # -------------------
    if s.phase == "intro":
        intro_eval = evaluate_intro(answer=answer, language=language)
        s.intro_score = int(intro_eval.get("score", 0))
        s.intro_feedback = intro_eval.get("feedback", "")
        s.intro_evaluation_json = {**(s.intro_evaluation_json or {}), "intro": intro_eval}

        # Move to bank phase
        s.phase = "bank"
        s.current_index = 0
        s.followup_count = 0
        db.commit()

        # return first bank question (unanswered #0)
        sq = (
            db.query(SessionQuestion)
            .filter(and_(SessionQuestion.session_id == s.id, SessionQuestion.user_answer.is_(None)))
            .first()
        )
        if not sq:
            # No questions at all -> outro
            s.phase = "outro"
            db.commit()
            outro = OUTRO_AR if language == "ar" else OUTRO_EN
            return {"phase": "outro", "prompt_type": "outro", "prompt_text": outro, "transcript": transcript, "intro_evaluation": intro_eval}

        q = db.get(Question, sq.question_id)
        return {
            "phase": "bank",
            "prompt_type": "bank_question",
            "question_id": str(q.id),
            "prompt_text": q.question_text,
            "transcript": transcript,
            "intro_evaluation": intro_eval,
        }

    # -------------------
    # OUTRO / FINISHED
    # -------------------
    if s.phase in ("outro", "finished"):
        outro = OUTRO_AR if language == "ar" else OUTRO_EN
        s.phase = "finished"
        db.commit()
        return {"phase": "finished", "prompt_type": "outro", "prompt_text": outro, "transcript": transcript}

    # -------------------
    # BANK PHASE
    # -------------------
    # current unanswered question
    # -------------------
    # BANK PHASE (pointer-driven, no repeats)
    # -------------------

    # 0) Repair pointer if it is missing (safety net)
    if not s.current_sq_id:
        fallback = (
            db.query(SessionQuestion)
            .filter(
                SessionQuestion.session_id == s.id,
                SessionQuestion.user_answer.is_(None),
            )
            .order_by(SessionQuestion.id)
            .first()
        )
        if not fallback:
            s.phase = "outro"
            db.commit()
            outro = OUTRO_AR if language == "ar" else OUTRO_EN
            return {"phase": "outro", "prompt_type": "outro", "prompt_text": outro, "transcript": transcript}

        s.current_sq_id = fallback.id
        db.commit()

    # 1) Load current question row using pointer
    sq = db.get(SessionQuestion, s.current_sq_id)
    if not sq or sq.session_id != s.id:
        # pointer is invalid -> repair again
        fallback = (
            db.query(SessionQuestion)
            .filter(
                SessionQuestion.session_id == s.id,
                SessionQuestion.user_answer.is_(None),
            )
            .order_by(SessionQuestion.id)
            .first()
        )
        if not fallback:
            s.phase = "outro"
            s.current_sq_id = None
            db.commit()
            outro = OUTRO_AR if language == "ar" else OUTRO_EN
            return {"phase": "outro", "prompt_type": "outro", "prompt_text": outro, "transcript": transcript}

        s.current_sq_id = fallback.id
        db.commit()
        sq = fallback

    # If current is already answered (can happen if pointer wasn't advanced earlier), advance now.
    if sq.user_answer is not None:
        next_unanswered = (
            db.query(SessionQuestion)
            .filter(
                SessionQuestion.session_id == s.id,
                SessionQuestion.user_answer.is_(None),
            )
            .order_by(SessionQuestion.id)
            .first()
        )
        if not next_unanswered:
            s.phase = "outro"
            s.current_sq_id = None
            db.commit()
            outro = OUTRO_AR if language == "ar" else OUTRO_EN
            return {"phase": "outro", "prompt_type": "outro", "prompt_text": outro, "transcript": transcript}

        s.current_sq_id = next_unanswered.id
        db.commit()
        sq = next_unanswered

    # 2) Load the question text
    q = db.get(Question, sq.question_id)
    if not q:
        raise HTTPException(404, detail="Question not found")

    # 3) Evaluate this attempt
    evaluation = score_answer(
        answer=answer,
        question=q.question_text,
        role=s.role_name,
        language=language,
    )

    decision = decide_next(
        question=q.question_text,
        answer=answer,
        evaluation=evaluation,
        role=s.role_name,
        language=language,
    )

    action = decision.get("action", "next")
    followup_question = (decision.get("question") or "").strip()

    # 4) Store attempts (do not finalize yet)
    if not sq.evaluation_json:
        sq.evaluation_json = {"attempts": []}

    sq.evaluation_json["attempts"].append({
        "answer": answer,
        "evaluation": evaluation,
        "decision": decision,
    })

    # Determine followup_max
    followup_max = 1
    if isinstance(s.intro_evaluation_json, dict):
        followup_max = int(s.intro_evaluation_json.get("followup_max", 1))

    # 5) Follow-up path (stay on SAME sq, don't finalize)
    if action in ("follow_up", "clarify") and s.followup_count < followup_max and followup_question:
        s.followup_count += 1
        db.commit()
        return {
            "phase": "bank",
            "action": "follow_up",
            "prompt_type": "follow_up",
            "prompt_text": followup_question,
            "question_id": str(q.id),
            "evaluation": evaluation,
            "transcript": transcript,
            "followup_count": s.followup_count,
            "followup_max": followup_max,
        }

    # 6) Finalize the current question (either next, or followup limit reached, or no followup question)
    s.followup_count = 0
    final_eval = sq.evaluation_json["attempts"][-1]["evaluation"]

    sq.user_answer = answer
    sq.score = int(final_eval.get("score", 0))
    sq.ai_feedback = final_eval.get("final_feedback", "")

    db.flush()  # ✅ IMPORTANT: make UPDATE visible to subsequent queries in this request

    # Update session total score (avg of answered)
    answered_rows = (
        db.query(SessionQuestion)
        .filter(
            SessionQuestion.session_id == s.id,
            SessionQuestion.user_answer.isnot(None),
        )
        .all()
    )
    if answered_rows:
        s.total_score = int(sum(x.score or 0 for x in answered_rows) / len(answered_rows))

    # 7) Advance pointer to next unanswered
    next_sq = (
        db.query(SessionQuestion)
        .filter(
            SessionQuestion.session_id == s.id,
            SessionQuestion.user_answer.is_(None),
        )
        .order_by(SessionQuestion.id)
        .first()
    )

    if not next_sq:
        s.phase = "outro"
        s.current_sq_id = None
        db.commit()
        outro = OUTRO_AR if language == "ar" else OUTRO_EN
        return {
            "phase": "outro",
            "action": "end",
            "prompt_type": "outro",
            "prompt_text": outro,
            "evaluation": final_eval,
            "transcript": transcript,
            "total_score": s.total_score,
        }

    s.current_sq_id = next_sq.id
    db.commit()

    next_q = db.get(Question, next_sq.question_id)
    return {
        "phase": "bank",
        "action": "next",
        "prompt_type": "bank_question",
        "question_id": str(next_q.id),
        "prompt_text": next_q.question_text,
        "evaluation": final_eval,
        "transcript": transcript,
        "total_score": s.total_score,
    }
