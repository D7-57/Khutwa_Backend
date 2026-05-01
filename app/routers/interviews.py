"""
Interviews router — v2

Question mix:
  Count | General (bank) | CV (AI) | Tech+Behavioral (bank)
  3     | 1              | 1       | 1   (no CV → 1 general, 2 bank)
  5     | 1              | 2       | 2   (no CV → 1 general, 4 bank)
  7     | 2              | 2       | 3   (no CV → 2 general, 5 bank)
  10    | 3              | 3       | 4   (no CV → 3 general, 7 bank)

CV questions are AI-generated and stored in session_questions.question_text
(NOT in the questions table). question_id is null for these.
"""

import random
import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session
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
    evaluate_and_decide,
    generate_cv_questions,
    classify_user_input,
    generate_brief_explanation,
    pick_intro,
    OUTRO_TEXT,
)
from app.services.stt import transcribe_audio
from app.services.tts import synthesize_question_audio
from app.services.interview_summary import build_interview_summary
from app.services.interview.body_tracker import get_tracker, create_tracker, remove_tracker
from app.services.interview.tone_analyzer import analyze_tone

router = APIRouter(prefix="/interviews", tags=["interviews"])

# ─── Question mix lookup ─────────────────────────────────────────────────
# (general_from_bank, cv_from_ai, tech_behavioral_from_bank)
QUESTION_MIX = {
    3:  (1, 1, 1),
    5:  (1, 2, 2),
    7:  (2, 2, 3),
    10: (3, 3, 4),
}

MAX_REASK = 2  # after this many re-asks, auto-score 0 and move on
MAX_CLARIFY = 2  # max clarification questions per interview question

REASK_TEXT = {
    "ar": "لم أسمع إجابتك. ممكن تعيد الإجابة؟",
    "en": "I didn't catch your answer. Could you try again?",
}
OFF_TOPIC_TEXT = {
    "ar": "يبدو أن إجابتك غير متعلقة بالسؤال. ممكن تحاول تجاوب على السؤال المطروح؟",
    "en": "That doesn't seem related to the question. Could you try answering the question asked?",
}
CLARIFY_EXHAUSTED_TEXT = {
    "ar": "أعتقد إنك فهمت السؤال الحين. حاول تجاوب بأفضل ما عندك.",
    "en": "I think you have enough context now. Please give it your best shot.",
}
REASK_EXHAUSTED_TEXT = {
    "ar": "خلنا ننتقل للسؤال التالي.",
    "en": "Let's move on to the next question.",
}


# ─────────────────────────────────────────
#  START
# ─────────────────────────────────────────

class StartInterviewRequest(BaseModel):
    role_name: str
    num_questions: int = 5
    followup_max: int = 1
    question_source: str = "bank"  # bank | ai | mix (legacy, still accepted)
    tech_ratio: int = 50
    company: str | None = None
    use_cv: bool = False
    mode: str = "text"  # text | audio | video
    is_rapid: bool = False


@router.post("/start")
def start_interview(
    body: StartInterviewRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    language = _get_language(db, uid)
    profile = db.get(Profile, uid)
    user_name = profile.first_name if profile and profile.first_name else None

    # ── Extract profile context for personalization ──
    profile_context = {}
    if profile:
        status = (profile.current_status or "").strip().lower()
        if status:
            profile_context["status"] = status  # student | graduate | employed

        # Compute years of experience from experiences JSON
        experiences = profile.experiences or []
        if isinstance(experiences, list) and experiences:
            profile_context["years_of_experience"] = len(experiences)
            profile_context["has_experience"] = True
        else:
            profile_context["years_of_experience"] = 0
            profile_context["has_experience"] = False

        if profile.major:
            profile_context["major"] = profile.major
        if profile.university:
            profile_context["university"] = profile.university

    # ── Build question mix ──
    all_questions = _build_question_mix(
        db=db,
        body=body,
        language=language,
        user_id=uid,
    )

    if not all_questions:
        raise HTTPException(400, detail="No questions available for this configuration.")

    # ── Create session ──
    is_rapid = body.is_rapid
    session = InterviewSession(
        user_id=uid,
        role_name=body.role_name,
        language=language,
        question_source=body.question_source,
        company=body.company,
        tech_ratio=body.tech_ratio,
        use_cv=body.use_cv,
        is_rapid=is_rapid,
        phase="rapid" if is_rapid else "intro",
        current_index=0,
        followup_count=0,
        intro_evaluation_json={"followup_max": body.followup_max, "mode": body.mode, "profile_context": profile_context},
    )
    db.add(session)
    db.flush()

    if body.mode == "video":
        create_tracker(str(session.id))

    # ── Create session questions ──
    first_sq_id = None
    all_question_data = []

    for i, qdata in enumerate(all_questions):
        sq = SessionQuestion(
            session_id=session.id,
            question_id=qdata.get("question_id"),       # None for CV questions
            question_text=qdata.get("question_text"),     # set for CV questions
            question_type=qdata["question_type"],
        )
        db.add(sq)
        db.flush()
        if i == 0:
            first_sq_id = sq.id

        all_question_data.append({
            "question_id": str(qdata["question_id"]) if qdata.get("question_id") else None,
            "question_type": qdata["question_type"],
            "question_text": qdata["display_text"],
            "source": qdata.get("source", "bank"),
        })

    session.current_sq_id = first_sq_id
    db.commit()
    db.refresh(session)

    # ── Response ──
    if is_rapid:
        return {
            "session_id": str(session.id),
            "phase": "rapid",
            "prompt_type": "rapid",
            "prompt_text": pick_intro(language, user_name),
            "questions": all_question_data,
            "config": _config_dict(body, len(all_questions)),
        }

    return {
        "session_id": str(session.id),
        "phase": "intro",
        "prompt_type": "intro",
        "prompt_text": pick_intro(language, user_name),
        "config": _config_dict(body, len(all_questions)),
    }


def _config_dict(body: StartInterviewRequest, count: int) -> dict:
    return {
        "question_source": body.question_source,
        "tech_ratio": body.tech_ratio,
        "company": body.company,
        "use_cv": body.use_cv,
        "mode": body.mode,
        "is_rapid": body.is_rapid,
        "num_questions": count,
    }


# ─────────────────────────────────────────
#  QUESTION MIX BUILDER
# ─────────────────────────────────────────

def _build_question_mix(
    db: Session,
    body: StartInterviewRequest,
    language: str,
    user_id: UUID,
) -> list[dict]:
    """
    Builds the final ordered list of questions for the session.

    Each item: {
        "question_id": UUID | None,    # None for CV-generated
        "question_text": str | None,    # set for CV-generated (stored in session_questions)
        "display_text": str,            # the text to show/speak
        "question_type": str,
        "source": "bank_general" | "bank_tech" | "cv_generated",
    }
    """
    num = body.num_questions
    mix = QUESTION_MIX.get(num)
    if not mix:
        # Fallback: nearest defined count
        nearest = min(QUESTION_MIX.keys(), key=lambda k: abs(k - num))
        mix = QUESTION_MIX[nearest]

    n_general, n_cv, n_bank = mix

    # If no CV, redistribute CV slots to bank
    if not body.use_cv:
        n_bank += n_cv
        n_cv = 0

    # ── 1. General questions from bank ──
    general_qs = _select_from_bank(
        db, body.role_name, language, user_id,
        question_type="general",
        count=n_general,
        company=body.company,
    )

    # ── 2. CV-based questions (AI-generated, not saved to Question table) ──
    cv_qs = []
    if n_cv > 0:
        cv_summary = _get_cv_summary(db, user_id)
        if cv_summary:
            raw_cv = generate_cv_questions(
                role=body.role_name,
                language=language,
                count=n_cv,
                cv_summary=cv_summary,
                company=body.company,
            )
            for cq in raw_cv:
                cv_qs.append({
                    "question_id": None,
                    "question_text": cq["question_text"],  # stored in SessionQuestion
                    "display_text": cq["question_text"],
                    "question_type": cq.get("question_type", "technical"),
                    "source": "cv_generated",
                })
        # If CV generation failed or no CV data, give those slots to bank
        if len(cv_qs) < n_cv:
            n_bank += (n_cv - len(cv_qs))

    # ── 3. Tech/behavioral from bank (ratio applies here) ──
    num_tech = round(n_bank * body.tech_ratio / 100)
    num_soft = n_bank - num_tech

    # Exclude IDs already selected for general
    exclude_ids = {q["question_id"] for q in general_qs if q["question_id"]}

    tech_qs = _select_from_bank(
        db, body.role_name, language, user_id,
        question_type="technical",
        count=num_tech,
        company=body.company,
        exclude_ids=exclude_ids,
    )

    exclude_ids.update(q["question_id"] for q in tech_qs if q["question_id"])

    soft_qs = _select_from_bank(
        db, body.role_name, language, user_id,
        question_type=None,  # soft, behavioral, or general (non-technical)
        count=num_soft,
        company=body.company,
        exclude_ids=exclude_ids,
        soft_types=True,
    )

    # ── Assemble: general first, then interleave CV + bank ──
    bank_qs = tech_qs + soft_qs
    random.shuffle(bank_qs)
    random.shuffle(cv_qs)

    result = list(general_qs)  # general at the start

    # Interleave CV and bank questions
    ci, bi = 0, 0
    while ci < len(cv_qs) or bi < len(bank_qs):
        if ci < len(cv_qs):
            result.append(cv_qs[ci]); ci += 1
        if bi < len(bank_qs):
            result.append(bank_qs[bi]); bi += 1

    return result[:num]


def _select_from_bank(
    db: Session,
    role_name: str,
    language: str,
    user_id: UUID,
    question_type: str | None = None,
    count: int = 2,
    company: str | None = None,
    exclude_ids: set[UUID] | None = None,
    soft_types: bool = False,
) -> list[dict]:
    """Select questions from the bank. Returns list of question dicts."""
    if count <= 0:
        return []

    # Map legacy "soft" to "behavioral"
    if question_type == "soft":
        question_type = "behavioral"

    # IDs user has already seen
    seen_subq = (
        db.query(SessionQuestion.question_id)
        .join(InterviewSession, InterviewSession.id == SessionQuestion.session_id)
        .filter(InterviewSession.user_id == user_id)
    )
    seen_ids = {row[0] for row in seen_subq.all() if row[0]}
    if exclude_ids:
        seen_ids.update(exclude_ids)

    # Pull from both the specific role AND the "general" pool
    if question_type == "general":
        # General questions live under role_name="general"
        all_qs = db.query(Question).filter(
            Question.role_name == "general",
            Question.status == "approved",
        ).all()
    else:
        # Role-specific questions
        all_qs = db.query(Question).filter(
            Question.role_name == role_name,
            Question.status == "approved",
        ).all()

    if not all_qs:
        return []

    # Type filter
    if question_type:
        pool = [x for x in all_qs if x.question_type == question_type]
    elif soft_types:
        # "soft_types" means non-technical: behavioral or general
        pool = [x for x in all_qs if x.question_type in ("behavioral", "general")]
    else:
        pool = all_qs

    # Prefer unseen
    unseen = [x for x in pool if x.id not in seen_ids]
    if not unseen:
        unseen = pool  # allow repeats if exhausted

    # Company priority
    company_qs = []
    other_qs = []
    for x in unseen:
        if company and x.company and x.company.lower() == company.lower():
            company_qs.append(x)
        else:
            other_qs.append(x)

    random.shuffle(company_qs)
    random.shuffle(other_qs)

    selected = []
    for x in company_qs + other_qs:
        if len(selected) >= count:
            break
        if x.id not in (exclude_ids or set()):
            selected.append(x)

    return [
        {
            "question_id": q.id,
            "question_text": None,  # text comes from Question table via FK
            "display_text": q.get_text(language),
            "question_type": q.question_type,
            "source": f"bank_{q.question_type}",
        }
        for q in selected
    ]


# ─────────────────────────────────────────
#  TURN
# ─────────────────────────────────────────

@router.post("/{session_id}/turn")
async def turn(
    session_id: str,
    answer_text: str | None = Form(default=None),
    audio: UploadFile | None = File(default=None),
    recording_seconds: float = Form(default=0.0),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    s = db.get(InterviewSession, UUID(session_id))
    if not s or str(s.user_id) != user_id:
        raise HTTPException(404, detail="Session not found")

    language = s.language or "en"
    mode = (s.intro_evaluation_json or {}).get("mode", "text")

    # Transcribe audio
    transcript = None
    if audio is not None:
        audio_bytes = await audio.read()
        transcript = transcribe_audio(audio_bytes, filename=audio.filename or "answer.webm", language=language)
        answer = transcript
    else:
        answer = (answer_text or "").strip()

    # Empty → re-ask
    if not answer:
        return {
            "phase": s.phase,
            "action": "re_ask",
            "prompt_type": "re_ask",
            "prompt_text": REASK_TEXT.get(language, REASK_TEXT["en"]),
            "transcript": transcript,
        }

    # Tone + body language
    tone_desc, tone_data = "", None
    if mode in ("audio", "video") and recording_seconds > 1:
        tone_result = analyze_tone(answer, recording_seconds)
        tone_desc = tone_result.describe_for_llm()
        tone_data = tone_result.to_dict()

    body_desc, body_data = "", None
    tracker = get_tracker(session_id) if mode == "video" else None
    if tracker:
        body_summary = tracker.get_summary()
        body_desc = body_summary.describe_for_llm()
        body_data = body_summary.to_dict()
        tracker.reset()

    followup_max = _get_followup_max(s)

    if s.phase == "intro":
        return _handle_intro(s, answer, transcript, language, db,
                             tone_desc=tone_desc, tone_data=tone_data,
                             body_desc=body_desc, body_data=body_data)

    if s.phase in ("outro", "finished"):
        if mode == "video": remove_tracker(session_id)
        s.phase = "finished"
        db.commit()
        return {"phase": "finished", "prompt_type": "outro",
                "prompt_text": OUTRO_TEXT.get(language, OUTRO_TEXT["en"]), "transcript": transcript}

    return _handle_bank(s, answer, transcript, language, followup_max, db,
                        tone_desc=tone_desc, tone_data=tone_data,
                        body_desc=body_desc, body_data=body_data)


# ─────────────────────────────────────────
#  QUESTION AUDIO / VIDEO WS / SUMMARY / LIST
# ─────────────────────────────────────────

@router.get("/{session_id}/question-audio/{question_id}",
            responses={200: {"content": {"audio/mpeg": {}}}})
def question_audio(session_id: str, question_id: str,
                   user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    s = db.get(InterviewSession, UUID(session_id))
    if not s or str(s.user_id) != user_id:
        raise HTTPException(404)
    q = db.get(Question, UUID(question_id))
    if not q: raise HTTPException(404)
    return StreamingResponse(BytesIO(synthesize_question_audio(q.question_text, language=s.language)),
                             media_type="audio/mpeg")


@router.post("/{session_id}/transcribe")
async def transcribe_only(
    session_id: str,
    audio: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Transcribe audio without evaluation. Used for rapid-fire audio mode."""
    s = db.get(InterviewSession, UUID(session_id))
    if not s or str(s.user_id) != user_id:
        raise HTTPException(404, detail="Session not found")

    language = s.language or "en"
    audio_bytes = await audio.read()
    transcript = transcribe_audio(audio_bytes, filename=audio.filename or "answer.webm", language=language)

    return {"transcript": transcript or ""}

@router.websocket("/{session_id}/video")
async def video_ws(websocket: WebSocket, session_id: str):
    await websocket.accept()
    tracker = get_tracker(session_id) or create_tracker(session_id)
    try:
        while True:
            msg = json.loads(await websocket.receive_text())
            if msg.get("reset"): tracker.reset(); continue
            tracker.record_frame(
                eye_contact=float(msg.get("eye_contact", 0)), smile=float(msg.get("smile", 0)),
                frown=float(msg.get("frown", 0)), hands_visible=bool(msg.get("hands_visible", False)),
                face_detected=bool(msg.get("face_detected", False)), gesture=msg.get("gesture", "none"))
    except: pass

@router.get("/{session_id}/summary")
def get_interview_summary(session_id: str, user_id: str = Depends(get_current_user_id),
                          db: Session = Depends(get_db)):
    s = db.get(InterviewSession, UUID(session_id))
    if not s or str(s.user_id) != user_id: raise HTTPException(404)
    return build_interview_summary(db, s.id)

@router.get("")
def list_my_interviews(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    uid = UUID(user_id)
    sessions = db.query(InterviewSession).filter(InterviewSession.user_id == uid)\
        .order_by(InterviewSession.created_at.desc()).limit(50).all()

    results = []
    for s in sessions:
        config = s.intro_evaluation_json or {}
        q_count = db.query(SessionQuestion).filter(SessionQuestion.session_id == s.id).count()
        answered = db.query(SessionQuestion).filter(
            SessionQuestion.session_id == s.id, SessionQuestion.user_answer.isnot(None)
        ).count()

        results.append({
            "session_id": str(s.id),
            "role_name": s.role_name,
            "phase": s.phase,
            "total_score": s.total_score,
            "intro_score": s.intro_score,
            "question_source": s.question_source,
            "company": s.company,
            "mode": config.get("mode", "text"),
            "is_rapid": s.is_rapid,
            "num_questions": q_count,
            "num_answered": answered,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    return results


@router.get("/analytics")
def get_interview_analytics(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """
    Aggregated analytics across all interview sessions:
    - Score trend over time
    - Weak areas by question_type
    - Per-role breakdown
    - Improvement rate
    """
    uid = UUID(user_id)

    sessions = db.query(InterviewSession).filter(
        InterviewSession.user_id == uid,
        InterviewSession.total_score.isnot(None),
    ).order_by(InterviewSession.created_at.asc()).all()

    if not sessions:
        return {
            "total_sessions": 0,
            "score_trend": [],
            "weak_areas": [],
            "role_breakdown": {},
            "avg_score": 0,
            "best_score": 0,
            "recent_avg": 0,
            "improvement": 0,
        }

    # ── Score trend (per session, chronological) ──
    score_trend = []
    for s in sessions:
        score_trend.append({
            "session_id": str(s.id),
            "score": s.total_score,
            "role": s.role_name,
            "date": s.created_at.isoformat() if s.created_at else None,
        })

    # ── Per question_type analytics ──
    all_sqs = (
        db.query(SessionQuestion)
        .join(InterviewSession, InterviewSession.id == SessionQuestion.session_id)
        .filter(
            InterviewSession.user_id == uid,
            SessionQuestion.score.isnot(None),
        ).all()
    )

    type_scores: dict[str, list[int]] = {}
    for sq in all_sqs:
        qt = sq.question_type or "general"
        type_scores.setdefault(qt, []).append(sq.score or 0)

    weak_areas = []
    for qt, scores in sorted(type_scores.items(), key=lambda x: sum(x[1]) / len(x[1]) if x[1] else 0):
        avg = int(sum(scores) / len(scores)) if scores else 0
        weak_areas.append({
            "question_type": qt,
            "avg_score": avg,
            "count": len(scores),
        })

    # ── Per-role breakdown ──
    role_scores: dict[str, list[int]] = {}
    for s in sessions:
        role_scores.setdefault(s.role_name, []).append(s.total_score or 0)

    role_breakdown = {}
    for role, scores in role_scores.items():
        role_breakdown[role] = {
            "sessions": len(scores),
            "avg_score": int(sum(scores) / len(scores)) if scores else 0,
            "best_score": max(scores) if scores else 0,
        }

    # ── Overall stats ──
    all_scores = [s.total_score for s in sessions if s.total_score is not None]
    avg_score = int(sum(all_scores) / len(all_scores)) if all_scores else 0
    best_score = max(all_scores) if all_scores else 0

    # Recent average (last 5 sessions)
    recent = all_scores[-5:] if len(all_scores) >= 5 else all_scores
    recent_avg = int(sum(recent) / len(recent)) if recent else 0

    # Improvement: recent avg vs first 5 sessions avg
    early = all_scores[:5] if len(all_scores) >= 5 else all_scores
    early_avg = int(sum(early) / len(early)) if early else 0
    improvement = recent_avg - early_avg

    return {
        "total_sessions": len(sessions),
        "score_trend": score_trend,
        "weak_areas": weak_areas,
        "role_breakdown": role_breakdown,
        "avg_score": avg_score,
        "best_score": best_score,
        "recent_avg": recent_avg,
        "improvement": improvement,
    }


@router.post("/{session_id}/retake")
def retake_interview(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Reset an existing interview session — clears all scores and answers
    so the user can retry the same questions with a fresh start.
    """
    uid = UUID(user_id)
    s = db.get(InterviewSession, UUID(session_id))
    if not s or str(s.user_id) != user_id:
        raise HTTPException(404, detail="Session not found")

    language = _get_language(db, uid)
    profile = db.get(Profile, uid)

    # ── Reset all session question data ──
    sqs = (
        db.query(SessionQuestion)
        .filter(SessionQuestion.session_id == s.id)
        .order_by(SessionQuestion.id)
        .all()
    )

    first_sq_id = None
    all_question_data = []
    for sq in sqs:
        # Clear answers, scores, feedback, evaluation data
        sq.user_answer = None
        sq.score = None
        sq.ai_feedback = None
        sq.evaluation_json = None

        if first_sq_id is None:
            first_sq_id = sq.id

        q_text = sq.question_text or ""
        if not q_text and sq.question_id:
            from app.models.question import Question
            q = db.get(Question, sq.question_id)
            if q:
                q_text = q.get_text(language)

        all_question_data.append({
            "session_question_id": str(sq.id),
            "question_id": str(sq.question_id) if sq.question_id else None,
            "question_text": q_text,
            "question_type": sq.question_type,
        })

    # ── Reset session-level data ──
    s.phase = "intro"
    s.current_index = 0
    s.current_sq_id = first_sq_id
    s.followup_count = 0
    s.total_score = None
    s.intro_score = None
    s.intro_feedback = None

    # Keep profile_context and mode from old config, clear intro evaluation
    old_config = s.intro_evaluation_json or {}
    s.intro_evaluation_json = {
        "followup_max": old_config.get("followup_max", 1),
        "mode": old_config.get("mode", "text"),
        "profile_context": old_config.get("profile_context", {}),
    }

    config = s.intro_evaluation_json
    mode = config.get("mode", "text")

    if mode == "video":
        create_tracker(str(s.id))

    db.commit()

    user_name = profile.first_name if profile and profile.first_name else None
    intro_text = pick_intro(language, user_name)

    return {
        "session_id": str(s.id),
        "phase": "intro",
        "prompt_text": intro_text,
        "mode": mode,
        "role_name": s.role_name,
        "questions": all_question_data,
    }


# ─────────────────────────────────────────
#  RAPID-FIRE BATCH SUBMIT
# ─────────────────────────────────────────

class RapidAnswer(BaseModel):
    question_index: int
    answer_text: str

class RapidSubmitRequest(BaseModel):
    answers: list[RapidAnswer]


@router.post("/{session_id}/rapid-submit")
def rapid_submit(
    session_id: str,
    body: RapidSubmitRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    s = db.get(InterviewSession, UUID(session_id))
    if not s or str(s.user_id) != user_id:
        raise HTTPException(404, detail="Session not found")
    if not s.is_rapid:
        raise HTTPException(400, detail="Session is not rapid mode")

    language = s.language or "en"
    profile_context = (s.intro_evaluation_json or {}).get("profile_context")
    sqs = (
        db.query(SessionQuestion)
        .filter(SessionQuestion.session_id == s.id)
        .order_by(SessionQuestion.id)
        .all()
    )

    if not sqs:
        raise HTTPException(400, detail="No questions in session")

    # Map answers by index
    answer_map = {a.question_index: a.answer_text for a in body.answers}

    results = []
    scores = []

    for i, sq in enumerate(sqs):
        answer = (answer_map.get(i) or "").strip()
        q_text = _get_sq_question_text(sq, db, language)
        q_type = sq.question_type or "technical"

        if not answer:
            # Unanswered — score 0
            sq.user_answer = ""
            sq.score = 0
            sq.ai_feedback = "No answer provided"
            sq.evaluation_json = {"attempts": [{"answer": "", "evaluation": {"score": 0, "answer_type": "off_topic"}, "action": "next"}]}
            results.append({"index": i, "score": 0, "answer_type": "skipped", "feedback": "No answer provided"})
            scores.append(0)
            continue

        # Score each answer
        result = evaluate_and_decide(
            answer=answer, question=q_text, role=s.role_name,
            language=language, question_type=q_type,
            profile_context=profile_context,
        )

        evaluation = {
            "score": result.get("score", 0),
            "strengths": result.get("strengths", []),
            "weaknesses": result.get("weaknesses", []),
            "skill_match": result.get("skill_match", 0),
            "communication_score": result.get("communication_score", 0),
            "final_feedback": result.get("final_feedback", ""),
            "answer_type": result.get("answer_type", "answered"),
            "correct_answer": result.get("correct_answer", ""),
        }

        sq.user_answer = answer
        sq.score = int(evaluation["score"])
        sq.ai_feedback = evaluation.get("final_feedback", "")
        sq.evaluation_json = {"attempts": [{"answer": answer, "evaluation": evaluation, "action": "next"}]}

        results.append({
            "index": i,
            "score": sq.score,
            "answer_type": evaluation["answer_type"],
            "feedback": evaluation.get("final_feedback", ""),
            "correct_answer": evaluation.get("correct_answer", ""),
        })
        scores.append(sq.score)

    # Update session
    s.total_score = int(sum(scores) / len(scores)) if scores else 0
    s.phase = "finished"
    db.commit()

    return {
        "session_id": str(s.id),
        "total_score": s.total_score,
        "results": results,
    }


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
    doc = db.query(CVDocument).filter(CVDocument.user_id == user_id)\
        .order_by(CVDocument.created_at.desc()).first()
    if not doc or not doc.extracted_data: return None
    data = doc.extracted_data
    parts = []
    if data.get("summary"): parts.append(data["summary"][:300])
    skills = data.get("skills", {})
    if isinstance(skills, dict):
        all_skills = skills.get("technical", []) + skills.get("tools", [])
    elif isinstance(skills, list):
        all_skills = skills
    else:
        all_skills = []
    if all_skills: parts.append(f"Skills: {', '.join(all_skills[:15])}")
    # Include projects for CV question generation
    projects = data.get("projects", [])
    if isinstance(projects, list) and projects:
        random.shuffle(projects)  # randomize so LLM doesn't always pick the first
        proj_text = "; ".join(str(p) for p in projects[:5])
        parts.append(f"Projects: {proj_text[:300]}")
    experience = data.get("experience", [])
    if isinstance(experience, list) and experience:
        random.shuffle(experience)
        exp_text = "; ".join(str(e) for e in experience[:5])
        parts.append(f"Experience: {exp_text[:300]}")
    # Include certifications
    certs = data.get("certifications", []) or data.get("certificates", [])
    if isinstance(certs, list) and certs:
        cert_text = "; ".join(str(c) for c in certs[:5])
        parts.append(f"Certifications: {cert_text[:300]}")
    # Shuffle section order so LLM doesn't always focus on the first section
    random.shuffle(parts)
    return "\n".join(parts) if parts else None


def _get_current_sq(s: InterviewSession, db: Session) -> SessionQuestion | None:
    if s.current_sq_id:
        sq = db.get(SessionQuestion, s.current_sq_id)
        if sq and sq.session_id == s.id and sq.user_answer is None:
            return sq
    sq = db.query(SessionQuestion).filter(
        SessionQuestion.session_id == s.id, SessionQuestion.user_answer.is_(None)
    ).order_by(SessionQuestion.id).first()
    if sq: s.current_sq_id = sq.id
    return sq


def _advance_pointer(s: InterviewSession, db: Session) -> SessionQuestion | None:
    sq = db.query(SessionQuestion).filter(
        SessionQuestion.session_id == s.id, SessionQuestion.user_answer.is_(None)
    ).order_by(SessionQuestion.id).first()
    s.current_sq_id = sq.id if sq else None
    return sq


def _update_total_score(s: InterviewSession, db: Session):
    answered = db.query(SessionQuestion).filter(
        SessionQuestion.session_id == s.id, SessionQuestion.user_answer.isnot(None)
    ).all()
    if answered:
        s.total_score = int(sum(x.score or 0 for x in answered) / len(answered))


def _get_sq_question_text(sq: SessionQuestion, db: Session, language: str = "en") -> str:
    """Get question text — from session_question.question_text (CV) or Question table (bank)."""
    if sq.question_text:
        return sq.question_text
    if sq.question_id:
        q = db.get(Question, sq.question_id)
        if q: return q.get_text(language)
    return ""


def _handle_intro(s, answer, transcript, language, db, tone_desc="", tone_data=None, body_desc="", body_data=None):
    intro_eval = evaluate_intro(answer=answer, language=language)
    s.intro_score = int(intro_eval.get("score", 0))
    s.intro_feedback = intro_eval.get("feedback", "")

    intro_json = {**(s.intro_evaluation_json or {}), "intro": intro_eval}
    if tone_data: intro_json["intro_tone"] = tone_data
    if body_data: intro_json["intro_body_language"] = body_data
    s.intro_evaluation_json = intro_json

    s.phase = "bank"
    s.current_index = 0
    s.followup_count = 0
    db.flush()

    sq = _get_current_sq(s, db)
    if not sq:
        s.phase = "outro"
        db.commit()
        return {"phase": "outro", "prompt_type": "outro",
                "prompt_text": OUTRO_TEXT.get(language, OUTRO_TEXT["en"]),
                "transcript": transcript, "intro_evaluation": intro_eval}

    q_text = _get_sq_question_text(sq, db, language)
    db.commit()
    return {
        "phase": "bank", "prompt_type": "bank_question",
        "question_id": str(sq.question_id) if sq.question_id else None,
        "question_type": sq.question_type,
        "prompt_text": q_text,
        "transcript": transcript, "intro_evaluation": intro_eval,
    }


def _handle_bank(s, answer, transcript, language, followup_max, db,
                 tone_desc="", tone_data=None, body_desc="", body_data=None):
    sq = _get_current_sq(s, db)
    if not sq:
        s.phase = "outro"; db.commit()
        return {"phase": "outro", "prompt_type": "outro",
                "prompt_text": OUTRO_TEXT.get(language, OUTRO_TEXT["en"]),
                "transcript": transcript, "total_score": s.total_score}

    q_text = _get_sq_question_text(sq, db, language)
    q_type = sq.question_type or "technical"

    # ── Determine what question text to evaluate against ──
    # If we're in a follow-up, the user is answering the follow-up question,
    # NOT the original question. We must evaluate against the follow-up text.
    eval_question_text = q_text  # default: the original question
    is_followup_answer = s.followup_count > 0
    if is_followup_answer:
        # Get the follow-up question from the last attempt that triggered it
        attempts = (sq.evaluation_json or {}).get("attempts", [])
        for att in reversed(attempts):
            if att.get("action") == "follow_up" and att.get("follow_up_question"):
                eval_question_text = att["follow_up_question"]
                break

    # ── Clarification detection ──
    classification = classify_user_input(
        user_text=answer,
        current_question=eval_question_text,
        role=s.role_name,
        language=language,
    )

    if classification.get("type") == "clarification":
        if not sq.evaluation_json:
            sq.evaluation_json = {"attempts": [], "clarify_count": 0}
        clarify_count = sq.evaluation_json.get("clarify_count", 0)

        if clarify_count >= MAX_CLARIFY:
            exhaust_msg = CLARIFY_EXHAUSTED_TEXT.get(language, CLARIFY_EXHAUSTED_TEXT["en"])
            exhaust_prompt = exhaust_msg + f"\n\n{eval_question_text}"
            db.commit()
            return {
                "phase": "bank", "action": "clarify_exhausted",
                "prompt_type": "clarification", "prompt_text": exhaust_prompt,
                "question_id": str(sq.question_id) if sq.question_id else None,
                "question_type": q_type, "transcript": transcript,
                "clarify_count": clarify_count, "clarify_max": MAX_CLARIFY,
            }

        clarification_response = classification.get("response", "")
        if clarification_response:
            sq.evaluation_json = {**sq.evaluation_json, "clarify_count": clarify_count + 1}
            db.flush()
            clarify_prompt = clarification_response + f"\n\n{eval_question_text}"
            db.commit()
            return {
                "phase": "bank", "action": "clarify",
                "prompt_type": "clarification", "prompt_text": clarify_prompt,
                "question_id": str(sq.question_id) if sq.question_id else None,
                "question_type": q_type, "transcript": transcript,
                "clarify_count": clarify_count + 1, "clarify_max": MAX_CLARIFY,
            }

    if classification.get("type") == "curiosity":
        curiosity_response = classification.get("response", "")
        if curiosity_response:
            CURIOSITY_BONUS = 5
            if not sq.evaluation_json:
                sq.evaluation_json = {"attempts": []}
            curiosity_eval = {
                "score": 35, "answer_type": "admitted_ignorance",
                "final_feedback": "Great curiosity! Asking to learn shows strong growth mindset.",
                "correct_answer": curiosity_response,
            }
            sq.evaluation_json = {
                **sq.evaluation_json,
                "attempts": sq.evaluation_json.get("attempts", []) + [
                    {"answer": answer, "evaluation": curiosity_eval,
                     "action": "next", "curiosity": True, "explanation": curiosity_response}
                ],
            }
            sq.user_answer = sq.user_answer or answer
            sq.score = 35 + CURIOSITY_BONUS
            sq.ai_feedback = curiosity_eval["final_feedback"]
            s.followup_count = 0
            db.flush()
            _update_total_score(s, db)

            next_sq = _advance_pointer(s, db)
            if not next_sq:
                s.phase = "outro"; db.commit()
                return {"phase": "outro", "action": "end", "prompt_type": "outro",
                        "prompt_text": OUTRO_TEXT.get(language, OUTRO_TEXT["en"]),
                        "evaluation": curiosity_eval, "explanation": curiosity_response,
                        "transcript": transcript, "total_score": s.total_score}
            nq_text = _get_sq_question_text(next_sq, db, language)
            db.commit()
            return {"phase": "bank", "action": "next", "prompt_type": "bank_question",
                    "question_id": str(next_sq.question_id) if next_sq.question_id else None,
                    "question_type": next_sq.question_type, "prompt_text": nq_text,
                    "evaluation": curiosity_eval, "explanation": curiosity_response,
                    "transcript": transcript, "total_score": s.total_score}

    # ── Evaluate against the correct question (original or follow-up) ──
    profile_context = (s.intro_evaluation_json or {}).get("profile_context")
    result = evaluate_and_decide(
        answer=answer, question=eval_question_text, role=s.role_name,
        language=language, question_type=q_type,
        body_language_desc=body_desc, tone_desc=tone_desc,
        profile_context=profile_context,
    )

    evaluation = {
        "score": result.get("score", 0),
        "strengths": result.get("strengths", []),
        "weaknesses": result.get("weaknesses", []),
        "skill_match": result.get("skill_match", 0),
        "communication_score": result.get("communication_score", 0),
        "final_feedback": result.get("final_feedback", ""),
        "answer_type": result.get("answer_type", "answered"),
        "correct_answer": result.get("correct_answer", ""),
    }

    action = result.get("action", "next")
    followup_q = (result.get("follow_up_question") or "").strip()
    answer_type = result.get("answer_type", "answered")

    # ── Store attempt with follow-up metadata ──
    if not sq.evaluation_json: sq.evaluation_json = {"attempts": []}
    attempt = {"answer": answer, "evaluation": evaluation, "action": action}
    if is_followup_answer:
        attempt["is_followup"] = True
        attempt["followup_question"] = eval_question_text
    if followup_q and action == "follow_up":
        attempt["follow_up_question"] = followup_q
    if tone_data: attempt["tone"] = tone_data
    if body_data: attempt["body_language"] = body_data
    sq.evaluation_json = {
        **sq.evaluation_json,
        "attempts": sq.evaluation_json.get("attempts", []) + [attempt],
    }

    # ── Off-topic: re-ask with cap ──
    if answer_type == "off_topic":
        reask_count = len([
            a for a in sq.evaluation_json.get("attempts", [])
            if a.get("evaluation", {}).get("answer_type") == "off_topic"
        ])

        if reask_count >= MAX_REASK:
            s.followup_count = 0
            sq.user_answer = sq.user_answer or answer
            sq.score = 0
            sq.ai_feedback = evaluation.get("final_feedback", "")
            db.flush()
            _update_total_score(s, db)
            next_sq = _advance_pointer(s, db)
            if not next_sq:
                s.phase = "outro"; db.commit()
                return {"phase": "outro", "action": "end", "prompt_type": "outro",
                        "prompt_text": OUTRO_TEXT.get(language, OUTRO_TEXT["en"]),
                        "evaluation": evaluation, "transcript": transcript,
                        "total_score": s.total_score}
            nq_text = _get_sq_question_text(next_sq, db, language)
            db.commit()
            return {"phase": "bank", "action": "next", "prompt_type": "bank_question",
                    "question_id": str(next_sq.question_id) if next_sq.question_id else None,
                    "question_type": next_sq.question_type, "prompt_text": nq_text,
                    "evaluation": evaluation, "skip_reason": "reask_exhausted",
                    "skip_message": REASK_EXHAUSTED_TEXT.get(language, REASK_EXHAUSTED_TEXT["en"]),
                    "transcript": transcript, "total_score": s.total_score}

        reask_prompt = OFF_TOPIC_TEXT.get(language, OFF_TOPIC_TEXT["en"])
        reask_prompt += f"\n\n{eval_question_text}"
        db.commit()
        return {"phase": "bank", "action": "re_ask", "prompt_type": "re_ask",
                "prompt_text": reask_prompt,
                "question_id": str(sq.question_id) if sq.question_id else None,
                "question_type": q_type, "evaluation": evaluation,
                "transcript": transcript, "reask_count": reask_count, "reask_max": MAX_REASK}

    # ── Admitted ignorance / partial ──
    if answer_type in ("admitted_ignorance", "partial"):
        s.followup_count = 0
        sq.user_answer = sq.user_answer or answer
        sq.score = int(evaluation.get("score", 25))
        sq.ai_feedback = evaluation.get("final_feedback", "")
        correct = evaluation.get("correct_answer", "")
        db.flush()
        _update_total_score(s, db)
        next_sq = _advance_pointer(s, db)
        if not next_sq:
            s.phase = "outro"; db.commit()
            return {"phase": "outro", "action": "end", "prompt_type": "outro",
                    "prompt_text": OUTRO_TEXT.get(language, OUTRO_TEXT["en"]),
                    "evaluation": evaluation, "correct_answer": correct,
                    "transcript": transcript, "total_score": s.total_score}
        nq_text = _get_sq_question_text(next_sq, db, language)
        db.commit()
        return {"phase": "bank", "action": "next", "prompt_type": "bank_question",
                "question_id": str(next_sq.question_id) if next_sq.question_id else None,
                "question_type": next_sq.question_type, "prompt_text": nq_text,
                "evaluation": evaluation, "correct_answer": correct,
                "transcript": transcript, "total_score": s.total_score}

    # ── Follow-up: DO NOT set user_answer — keep sq pointer alive ──
    if action in ("follow_up", "clarify") and s.followup_count < followup_max and followup_q:
        s.followup_count += 1
        # Save baseline score from first attempt but do NOT set user_answer
        if sq.score is None:
            sq.score = int(evaluation.get("score", 0))
            sq.ai_feedback = evaluation.get("final_feedback", "")
        db.flush()
        db.commit()
        return {"phase": "bank", "action": "follow_up", "prompt_type": "follow_up",
                "prompt_text": followup_q,
                "question_id": str(sq.question_id) if sq.question_id else None,
                "question_type": q_type, "evaluation": evaluation,
                "transcript": transcript, "followup_count": s.followup_count,
                "followup_max": followup_max}

    # ── Finalize + next ──
    s.followup_count = 0
    if sq.user_answer is None:
        sq.user_answer = answer  # keep original answer from first attempt
    # Combine scores: use the better of original vs follow-up
    new_score = int(evaluation.get("score", 0))
    if sq.score is not None and is_followup_answer:
        sq.score = max(sq.score, (sq.score + new_score) // 2)
    else:
        sq.score = new_score
    sq.ai_feedback = evaluation.get("final_feedback", "")
    db.flush()
    _update_total_score(s, db)

    next_sq = _advance_pointer(s, db)
    if not next_sq:
        s.phase = "outro"; db.commit()
        return {"phase": "outro", "action": "end", "prompt_type": "outro",
                "prompt_text": OUTRO_TEXT.get(language, OUTRO_TEXT["en"]),
                "evaluation": evaluation, "transcript": transcript,
                "total_score": s.total_score}

    nq_text = _get_sq_question_text(next_sq, db, language)
    db.commit()
    return {"phase": "bank", "action": "next", "prompt_type": "bank_question",
            "question_id": str(next_sq.question_id) if next_sq.question_id else None,
            "question_type": next_sq.question_type, "prompt_text": nq_text,
            "evaluation": evaluation, "transcript": transcript,
            "total_score": s.total_score}