"""
Interviews router — v3

WHAT'S NEW vs v2:
  • practice_mode (free | focused)
      'focused' biases question selection toward topics the user has previously
      scored < 55 on for the same role. The evaluator also gets a focus_mode
      flag so its feedback frames "you were weak on this — here's how to fix it"
      instead of generic praise.

  • Dynamic difficulty from profile.years_of_experience
      The string column ("0", "<1", "1", "2", "3+") is read directly and
      passed to the evaluator as `experience_band`. Bank selection ALSO uses
      this band to filter question difficulty:
          band  difficulty range
           0    1..3
          <1    1..3
           1    1..4
           2    2..4
          3+    2..5

  • Finalize-early endpoint (POST /interviews/{id}/finalize)
      Used by the "End & View Scores" button. Marks remaining unanswered
      questions as skipped (score=0), recomputes total_score, sets
      phase='finished' and finished_early=True, finished_at=now().
      Without this, sessions ended via the UI button stayed phase='bank'
      forever and showed 'in progress' in the history list.

  • Resume endpoint (GET /interviews/{id}/resume)
      Returns enough info for the Flutter app to re-enter an in-progress
      session at the right place: current question text, phase, mode,
      total_score, remaining count.

  • Per-question relevance endpoint
      POST /interviews/{session_id}/questions/{question_id}/relevance
      The Flutter client already calls this (see InterviewRepository
      .postQuestionRelevance). Now it actually exists.

  • Summary now always includes correct_answer + tip per question.
"""

import random
import json
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from io import BytesIO
from fastapi.responses import StreamingResponse

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.question import Question
from app.models.profile import Profile
from app.models.cv import CVDocument
from app.models.interview import InterviewSession, SessionQuestion
from app.models.question_vote import QuestionRelevanceFeedback
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

# (general_from_bank, cv_from_ai, tech_behavioral_from_bank)
QUESTION_MIX = {
    3:  (1, 1, 1),
    5:  (1, 2, 2),
    7:  (2, 2, 3),
    10: (3, 3, 4),
}

MAX_REASK = 2
MAX_CLARIFY = 2

# A user is considered to have a "weak" question if they previously scored
# below this threshold on it for the same role.
WEAK_THRESHOLD = 55

# Minimum number of finished sessions before focused practice is unlocked.
# Below this, we don't have enough signal.
MIN_SESSIONS_FOR_FOCUSED = 3

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

# Difficulty bands per experience level — used for dynamic difficulty
# in question selection.
DIFFICULTY_RANGES: dict[str, tuple[int, int]] = {
    "0":  (1, 3),
    "<1": (1, 3),
    "1":  (1, 4),
    "2":  (2, 4),
    "3+": (2, 5),
}


# ─────────────────────────────────────────
#  START
# ─────────────────────────────────────────

class StartInterviewRequest(BaseModel):
    role_name: str
    num_questions: int = 5
    followup_max: int = 1
    question_source: str = "bank"
    tech_ratio: int = 50
    company: str | None = None
    use_cv: bool = False
    mode: str = "text"
    is_rapid: bool = False
    # NEW: 'free' | 'focused'
    practice_mode: str = "free"
    # NEW: 'ar' | 'en' (any of three names accepted from the client, see
    # /start handler for query-string fallbacks).
    language: str | None = None
    interview_language: str | None = None
    lang: str | None = None


@router.post("/start")
def start_interview(
    body: StartInterviewRequest,
    # Query-string aliases — kept for backend-version compatibility with older
    # clients that send language via the URL instead of the body.
    language: str | None = None,
    interview_language: str | None = None,
    lang: str | None = None,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    # Honor an explicit language choice from the client if it parses as ar/en,
    # otherwise fall through to the user's stored profile language.
    requested_language = _resolve_requested_language(
        body.interview_language,
        body.language,
        body.lang,
        interview_language,
        language,
        lang,
    )
    language = requested_language or _get_language(db, uid)
    profile = db.get(Profile, uid)
    user_name = profile.first_name if profile and profile.first_name else None

    practice_mode = (body.practice_mode or "free").lower()
    if practice_mode not in ("free", "focused"):
        practice_mode = "free"

    # Focused practice gating: require enough finished sessions of signal.
    if practice_mode == "focused":
        finished_count = (
            db.query(InterviewSession)
            .filter(
                InterviewSession.user_id == uid,
                # Both 'finished' and 'outro' are terminal in this codebase —
                # natural completion routes through 'outro', finalize-early
                # and rapid-submit go to 'finished'. Count both.
                InterviewSession.phase.in_(["finished", "outro"]),
            )
            .count()
        )
        if finished_count < MIN_SESSIONS_FOR_FOCUSED:
            # Quietly downgrade rather than 400 — the UI should also block
            # this, but we don't want a hard failure if the user slipped through.
            practice_mode = "free"

    # ── Profile context ──
    profile_context: dict = {}
    if profile:
        status = (profile.current_status or "").strip().lower()
        if status:
            profile_context["status"] = status

        # Use the dedicated string band first; fall back to legacy len(experiences).
        band = (profile.years_of_experience or "").strip()
        if band in DIFFICULTY_RANGES:
            profile_context["experience_band"] = band
            profile_context["has_experience"] = band not in ("0", "<1")
            # Numeric proxy for older code paths
            profile_context["years_of_experience"] = (
                0 if band in ("0", "<1") else
                3 if band == "3+" else int(band)
            )
        else:
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

    if practice_mode == "focused":
        profile_context["focus_mode"] = True

    # ── Build question mix ──
    weak_question_ids = _get_weak_question_ids(db, uid, body.role_name)

    all_questions = _build_question_mix(
        db=db,
        body=body,
        language=language,
        user_id=uid,
        weak_question_ids=weak_question_ids if practice_mode == "focused" else set(),
        experience_band=profile_context.get("experience_band"),
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
        practice_mode=practice_mode,
        phase="rapid" if is_rapid else "intro",
        current_index=0,
        followup_count=0,
        intro_evaluation_json={
            "followup_max": body.followup_max,
            "mode": body.mode,
            "profile_context": profile_context,
            "practice_mode": practice_mode,
        },
    )
    db.add(session)
    db.flush()

    if body.mode == "video":
        create_tracker(str(session.id))

    first_sq_id = None
    all_question_data = []

    for i, qdata in enumerate(all_questions):
        sq = SessionQuestion(
            session_id=session.id,
            question_id=qdata.get("question_id"),
            question_text=qdata.get("question_text"),
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
            "config": _config_dict(body, len(all_questions), practice_mode),
            "language": language,
        }

    return {
        "session_id": str(session.id),
        "phase": "intro",
        "prompt_type": "intro",
        "prompt_text": pick_intro(language, user_name),
        "config": _config_dict(body, len(all_questions), practice_mode),
        "language": language,
    }


def _config_dict(body: StartInterviewRequest, count: int, practice_mode: str) -> dict:
    return {
        "question_source": body.question_source,
        "tech_ratio": body.tech_ratio,
        "company": body.company,
        "use_cv": body.use_cv,
        "mode": body.mode,
        "is_rapid": body.is_rapid,
        "num_questions": count,
        "practice_mode": practice_mode,
    }


# ─────────────────────────────────────────
#  WEAK-AREA HELPER
# ─────────────────────────────────────────

def _get_weak_question_ids(
    db: Session, user_id: UUID, role_name: str
) -> set[UUID]:
    """
    Question IDs the user is currently weak on for this role.

    "Currently weak" = the user's MOST RECENT attempt at the question scored
    below WEAK_THRESHOLD. If they later re-encountered the question and did
    well, it falls out of the weak set — focused practice should chase what
    you're *still* bad at, not follow you around forever.

    SessionQuestion has no timestamp of its own, so we use the parent
    InterviewSession.created_at as the recency proxy. (Within one session
    it's also a stable tiebreaker: SessionQuestion.id, which is a uuid v4,
    isn't time-ordered, but two attempts of the same question in one session
    isn't a realistic case.)
    """
    rn = func.row_number().over(
        partition_by=SessionQuestion.question_id,
        order_by=InterviewSession.created_at.desc(),
    ).label("rn")

    inner = (
        db.query(
            SessionQuestion.question_id.label("qid"),
            SessionQuestion.score.label("score"),
            rn,
        )
        .join(InterviewSession, InterviewSession.id == SessionQuestion.session_id)
        .filter(
            InterviewSession.user_id == user_id,
            InterviewSession.role_name == role_name,
            SessionQuestion.question_id.isnot(None),
            SessionQuestion.score.isnot(None),
        )
        .subquery()
    )

    rows = (
        db.query(inner.c.qid)
        .filter(inner.c.rn == 1, inner.c.score < WEAK_THRESHOLD)
        .all()
    )
    return {r[0] for r in rows if r[0]}


# ─────────────────────────────────────────
#  QUESTION MIX BUILDER
# ─────────────────────────────────────────

def _build_question_mix(
    db: Session,
    body: StartInterviewRequest,
    language: str,
    user_id: UUID,
    weak_question_ids: set[UUID] | None = None,
    experience_band: str | None = None,
) -> list[dict]:
    num = body.num_questions
    mix = QUESTION_MIX.get(num)
    if not mix:
        nearest = min(QUESTION_MIX.keys(), key=lambda k: abs(k - num))
        mix = QUESTION_MIX[nearest]

    n_general, n_cv, n_bank = mix

    if not body.use_cv:
        n_bank += n_cv
        n_cv = 0

    # ── 1. General questions from bank ──
    general_qs = _select_from_bank(
        db, body.role_name, language, user_id,
        question_type="general",
        count=n_general,
        company=body.company,
        weak_question_ids=weak_question_ids,
        experience_band=experience_band,
    )

    # ── 2. CV-based questions ──
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
                    "question_text": cq["question_text"],
                    "display_text": cq["question_text"],
                    "question_type": cq.get("question_type", "technical"),
                    "source": "cv_generated",
                })
        if len(cv_qs) < n_cv:
            n_bank += (n_cv - len(cv_qs))

    # ── 3. Tech/behavioral from bank ──
    num_tech = round(n_bank * body.tech_ratio / 100)
    num_soft = n_bank - num_tech

    exclude_ids = {q["question_id"] for q in general_qs if q["question_id"]}

    tech_qs = _select_from_bank(
        db, body.role_name, language, user_id,
        question_type="technical",
        count=num_tech,
        company=body.company,
        exclude_ids=exclude_ids,
        weak_question_ids=weak_question_ids,
        experience_band=experience_band,
    )

    exclude_ids.update(q["question_id"] for q in tech_qs if q["question_id"])

    soft_qs = _select_from_bank(
        db, body.role_name, language, user_id,
        question_type=None,
        count=num_soft,
        company=body.company,
        exclude_ids=exclude_ids,
        soft_types=True,
        weak_question_ids=weak_question_ids,
        experience_band=experience_band,
    )

    bank_qs = tech_qs + soft_qs
    random.shuffle(bank_qs)
    random.shuffle(cv_qs)

    result = list(general_qs)
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
    weak_question_ids: set[UUID] | None = None,
    experience_band: str | None = None,
) -> list[dict]:
    if count <= 0:
        return []

    if question_type == "soft":
        question_type = "behavioral"

    seen_subq = (
        db.query(SessionQuestion.question_id)
        .join(InterviewSession, InterviewSession.id == SessionQuestion.session_id)
        .filter(InterviewSession.user_id == user_id)
    )
    seen_ids = {row[0] for row in seen_subq.all() if row[0]}
    if exclude_ids:
        seen_ids.update(exclude_ids)

    if question_type == "general":
        all_qs = db.query(Question).filter(
            Question.role_name == "general",
            Question.status == "approved",
        ).all()
    else:
        all_qs = db.query(Question).filter(
            Question.role_name == role_name,
            Question.status == "approved",
        ).all()

    if not all_qs:
        return []

    if question_type:
        pool = [x for x in all_qs if x.question_type == question_type]
    elif soft_types:
        pool = [x for x in all_qs if x.question_type in ("behavioral", "general")]
    else:
        pool = all_qs

    # ── DYNAMIC DIFFICULTY ──
    # Filter by difficulty range matching the candidate's experience band.
    # If the strict range gives us nothing, fall back to all difficulties so
    # we don't produce an empty session.
    if experience_band and experience_band in DIFFICULTY_RANGES:
        lo, hi = DIFFICULTY_RANGES[experience_band]
        difficulty_filtered = [
            x for x in pool
            if (x.difficulty or 1) >= lo and (x.difficulty or 1) <= hi
        ]
        if difficulty_filtered:
            pool = difficulty_filtered

    # Prefer unseen
    unseen = [x for x in pool if x.id not in seen_ids]
    fallback_seen = False
    if not unseen:
        unseen = pool  # allow repeats if exhausted
        fallback_seen = True

    # ── FOCUSED PRACTICE: float weak questions to the top ──
    # When focused mode is on, the user has already seen these — but here
    # repetition is the point. Build the candidate set from the ALL pool
    # (including seen) for the weak ones.
    weak_pool: list = []
    normal_pool: list = unseen
    if weak_question_ids:
        weak_pool = [x for x in pool if x.id in weak_question_ids]
        # Don't double-count: remove weak ones from normal_pool
        weak_set = {x.id for x in weak_pool}
        normal_pool = [x for x in unseen if x.id not in weak_set]

    # ── Company priority within each pool ──
    def _split_company(items):
        comp, other = [], []
        for x in items:
            if company and x.company and x.company.lower() == company.lower():
                comp.append(x)
            else:
                other.append(x)
        random.shuffle(comp); random.shuffle(other)
        return comp + other

    weak_pool = _split_company(weak_pool)
    normal_pool = _split_company(normal_pool)

    # Take from weak first, then fill from normal.
    candidate = weak_pool + normal_pool

    selected = []
    excl = exclude_ids or set()
    for x in candidate:
        if len(selected) >= count:
            break
        if x.id in excl:
            continue
        selected.append(x)
        excl.add(x.id)

    return [
        {
            "question_id": q.id,
            "question_text": None,
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

    transcript = None
    if audio is not None:
        audio_bytes = await audio.read()
        transcript = transcribe_audio(audio_bytes, filename=audio.filename or "answer.webm", language=language)
        answer = transcript
    else:
        answer = (answer_text or "").strip()

    if not answer:
        return {
            "phase": s.phase,
            "action": "re_ask",
            "prompt_type": "re_ask",
            "prompt_text": REASK_TEXT.get(language, REASK_TEXT["en"]),
            "transcript": transcript,
        }

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
        if not s.finished_at:
            s.finished_at = datetime.now(timezone.utc)
        db.commit()
        return {"phase": "finished", "prompt_type": "outro",
                "prompt_text": OUTRO_TEXT.get(language, OUTRO_TEXT["en"]), "transcript": transcript}

    response = _handle_bank(s, answer, transcript, language, followup_max, db,
                        tone_desc=tone_desc, tone_data=tone_data,
                        body_desc=body_desc, body_data=body_data)

    if tone_data and isinstance(response, dict):
        response["tone"] = tone_data
    if body_data and isinstance(response, dict):
        response["body_language"] = body_data

    return response


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
            if msg.get("reset"):
                tracker.reset()
                continue
            jpeg_b64 = msg.get("frame", "")
            if not jpeg_b64:
                continue
            live = tracker.process_frame(jpeg_b64)
            try:
                await websocket.send_text(json.dumps(live))
            except Exception:
                break
    except: pass


@router.get("/{session_id}/summary")
def get_interview_summary(session_id: str, user_id: str = Depends(get_current_user_id),
                          db: Session = Depends(get_db)):
    s = db.get(InterviewSession, UUID(session_id))
    if not s or str(s.user_id) != user_id: raise HTTPException(404)
    return build_interview_summary(db, s.id, user_id=UUID(user_id))


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
            "practice_mode": s.practice_mode,
            "finished_early": s.finished_early,
            "num_questions": q_count,
            "num_answered": answered,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "finished_at": s.finished_at.isoformat() if s.finished_at else None,
        })
    return results


@router.get("/analytics")
def get_interview_analytics(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
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
            "focused_unlocked": False,
        }

    score_trend = []
    for s in sessions:
        score_trend.append({
            "session_id": str(s.id),
            "score": s.total_score,
            "role": s.role_name,
            "date": s.created_at.isoformat() if s.created_at else None,
        })

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

    all_scores = [s.total_score for s in sessions if s.total_score is not None]
    avg_score = int(sum(all_scores) / len(all_scores)) if all_scores else 0
    best_score = max(all_scores) if all_scores else 0

    recent = all_scores[-5:] if len(all_scores) >= 5 else all_scores
    recent_avg = int(sum(recent) / len(recent)) if recent else 0

    early = all_scores[:5] if len(all_scores) >= 5 else all_scores
    early_avg = int(sum(early) / len(early)) if early else 0
    improvement = recent_avg - early_avg

    finished_count = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.user_id == uid,
            # Both 'finished' and 'outro' are terminal — see the start endpoint
            # for the same logic.
            InterviewSession.phase.in_(["finished", "outro"]),
        )
        .count()
    )

    return {
        "total_sessions": len(sessions),
        "score_trend": score_trend,
        "weak_areas": weak_areas,
        "role_breakdown": role_breakdown,
        "avg_score": avg_score,
        "best_score": best_score,
        "recent_avg": recent_avg,
        "improvement": improvement,
        # NEW: tells the Flutter setup screen whether to enable Focused mode.
        "focused_unlocked": finished_count >= MIN_SESSIONS_FOR_FOCUSED,
        "finished_count": finished_count,
    }


# ─────────────────────────────────────────
#  RESUME / FINALIZE
# ─────────────────────────────────────────

@router.get("/{session_id}/resume")
def resume_interview(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Returns the state needed to re-enter an in-progress session at the
    correct point. Used by the history screen's 'Resume' action.
    """
    s = db.get(InterviewSession, UUID(session_id))
    if not s or str(s.user_id) != user_id:
        raise HTTPException(404, detail="Session not found")

    if s.phase in ("finished", "outro"):
        raise HTTPException(400, detail="Session is already finished")

    language = s.language or "en"
    mode = (s.intro_evaluation_json or {}).get("mode", "text")

    # Find current question (first unanswered one) and total counts.
    sqs = (
        db.query(SessionQuestion)
        .filter(SessionQuestion.session_id == s.id)
        .order_by(SessionQuestion.id)
        .all()
    )
    total = len(sqs)
    answered = sum(1 for sq in sqs if sq.user_answer is not None)

    current_sq = None
    if s.current_sq_id:
        for sq in sqs:
            if sq.id == s.current_sq_id and sq.user_answer is None:
                current_sq = sq
                break
    if current_sq is None:
        current_sq = next((sq for sq in sqs if sq.user_answer is None), None)

    if current_sq is None:
        # Everything answered but phase != finished — odd state. Just finalize.
        s.phase = "finished"
        if not s.finished_at:
            s.finished_at = datetime.now(timezone.utc)
        _update_total_score(s, db)
        db.commit()
        return {
            "session_id": str(s.id),
            "phase": "finished",
            "mode": mode,
            "role_name": s.role_name,
            "total_questions": total,
            "answered": answered,
            "prompt_text": OUTRO_TEXT.get(language, OUTRO_TEXT["en"]),
        }

    if mode == "video":
        # Reset/re-create tracker for this session.
        if not get_tracker(str(s.id)):
            create_tracker(str(s.id))

    return {
        "session_id": str(s.id),
        "phase": s.phase,
        "mode": mode,
        "role_name": s.role_name,
        "language": language,
        "prompt_text": _get_sq_question_text(current_sq, db, language),
        "current_question_id": str(current_sq.question_id) if current_sq.question_id else None,
        "current_question_type": current_sq.question_type,
        "answered": answered,
        "total_questions": total,
        "company": s.company,
        "question_source": s.question_source,
        "practice_mode": s.practice_mode,
    }


@router.post("/{session_id}/finalize")
def finalize_interview(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Called by the 'End & View Scores' button in the Flutter UI.

    Marks any unanswered questions as skipped (score=0, ai_feedback='skipped'),
    recomputes total_score, and sets phase='finished', finished_early=True,
    finished_at=now(). Idempotent — safe to call on an already-finished session.
    """
    s = db.get(InterviewSession, UUID(session_id))
    if not s or str(s.user_id) != user_id:
        raise HTTPException(404, detail="Session not found")

    mode = (s.intro_evaluation_json or {}).get("mode", "text")
    if mode == "video":
        remove_tracker(str(s.id))

    if s.phase == "finished":
        # Already finished — return current snapshot.
        return _finalize_response(s, db)

    # Mark unanswered SQs as skipped.
    sqs = (
        db.query(SessionQuestion)
        .filter(
            SessionQuestion.session_id == s.id,
            SessionQuestion.user_answer.is_(None),
        )
        .all()
    )
    for sq in sqs:
        sq.user_answer = ""
        sq.score = 0
        sq.ai_feedback = "Skipped"
        sq.evaluation_json = {
            **(sq.evaluation_json or {}),
            "skipped": True,
            "attempts": (sq.evaluation_json or {}).get("attempts", []) + [
                {"answer": "", "evaluation": {
                    "score": 0,
                    "answer_type": "off_topic",
                    "final_feedback": "Skipped — session ended early.",
                    "correct_answer": "",
                }, "action": "next", "skipped": True},
            ],
        }

    s.phase = "finished"
    s.finished_early = True
    s.finished_at = datetime.now(timezone.utc)
    s.followup_count = 0
    db.flush()
    _update_total_score(s, db)
    db.commit()
    db.refresh(s)
    return _finalize_response(s, db)


def _finalize_response(s: InterviewSession, db: Session) -> dict:
    answered = db.query(SessionQuestion).filter(
        SessionQuestion.session_id == s.id,
        SessionQuestion.user_answer.isnot(None),
    ).count()
    total = db.query(SessionQuestion).filter(
        SessionQuestion.session_id == s.id,
    ).count()
    return {
        "session_id": str(s.id),
        "phase": s.phase,
        "total_score": s.total_score,
        "finished_early": s.finished_early,
        "finished_at": s.finished_at.isoformat() if s.finished_at else None,
        "num_answered": answered,
        "num_questions": total,
    }


# ─────────────────────────────────────────
#  RELEVANCE FEEDBACK
# ─────────────────────────────────────────

class RelevanceRequest(BaseModel):
    relevant: bool


@router.post("/{session_id}/questions/{question_id}/relevance")
def post_question_relevance(
    session_id: str,
    question_id: str,
    body: RelevanceRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Lightweight 'was this question relevant?' signal from inside an interview.
    Distinct from community votes — this is a per-session per-user yes/no
    that we can later aggregate into community moderation if we want.
    """
    try:
        sid = UUID(session_id)
        qid = UUID(question_id)
    except ValueError:
        raise HTTPException(400, detail="Invalid id")

    s = db.get(InterviewSession, sid)
    if not s or str(s.user_id) != user_id:
        raise HTTPException(404, detail="Session not found")

    q = db.get(Question, qid)
    if not q:
        raise HTTPException(404, detail="Question not found")

    uid = UUID(user_id)
    existing = (
        db.query(QuestionRelevanceFeedback)
        .filter(
            QuestionRelevanceFeedback.session_id == sid,
            QuestionRelevanceFeedback.question_id == qid,
            QuestionRelevanceFeedback.user_id == uid,
        )
        .one_or_none()
    )
    if existing:
        existing.relevant = body.relevant
    else:
        db.add(QuestionRelevanceFeedback(
            session_id=sid,
            question_id=qid,
            user_id=uid,
            relevant=body.relevant,
        ))
    db.commit()
    return {"ok": True, "relevant": body.relevant}


# ─────────────────────────────────────────
#  RETAKE
# ─────────────────────────────────────────

@router.post("/{session_id}/retake")
def retake_interview(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    s = db.get(InterviewSession, UUID(session_id))
    if not s or str(s.user_id) != user_id:
        raise HTTPException(404, detail="Session not found")

    language = _get_language(db, uid)
    profile = db.get(Profile, uid)

    sqs = (
        db.query(SessionQuestion)
        .filter(SessionQuestion.session_id == s.id)
        .order_by(SessionQuestion.id)
        .all()
    )

    first_sq_id = None
    all_question_data = []
    for sq in sqs:
        sq.user_answer = None
        sq.score = None
        sq.ai_feedback = None
        sq.evaluation_json = None

        if first_sq_id is None:
            first_sq_id = sq.id

        q_text = sq.question_text or ""
        if not q_text and sq.question_id:
            q = db.get(Question, sq.question_id)
            if q:
                q_text = q.get_text(language)

        all_question_data.append({
            "session_question_id": str(sq.id),
            "question_id": str(sq.question_id) if sq.question_id else None,
            "question_text": q_text,
            "question_type": sq.question_type,
        })

    s.phase = "rapid" if s.is_rapid else "intro"
    s.current_index = 0
    s.current_sq_id = first_sq_id
    s.followup_count = 0
    s.total_score = None
    s.intro_score = None
    s.intro_feedback = None
    s.finished_early = False
    s.finished_at = None

    old_config = s.intro_evaluation_json or {}
    s.intro_evaluation_json = {
        "followup_max": old_config.get("followup_max", 1),
        "mode": old_config.get("mode", "text"),
        "profile_context": old_config.get("profile_context", {}),
        "practice_mode": s.practice_mode,
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

    answer_map = {a.question_index: a.answer_text for a in body.answers}

    results = []
    scores = []

    for i, sq in enumerate(sqs):
        answer = (answer_map.get(i) or "").strip()
        q_text = _get_sq_question_text(sq, db, language)
        q_type = sq.question_type or "technical"

        if not answer:
            sq.user_answer = ""
            sq.score = 0
            sq.ai_feedback = "No answer provided"
            sq.evaluation_json = {"attempts": [{"answer": "", "evaluation": {"score": 0, "answer_type": "off_topic"}, "action": "next"}]}
            results.append({"index": i, "score": 0, "answer_type": "skipped", "feedback": "No answer provided"})
            scores.append(0)
            continue

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
            "tip": result.get("tip", ""),
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
            "tip": evaluation.get("tip", ""),
            "correct_answer": evaluation.get("correct_answer", ""),
        })
        scores.append(sq.score)

    s.total_score = int(sum(scores) / len(scores)) if scores else 0
    s.phase = "finished"
    s.finished_at = datetime.now(timezone.utc)
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


def _resolve_requested_language(*values: str | None) -> str | None:
    """
    Pick the first 'ar' or 'en' from the candidates, case/whitespace-insensitive.

    Used in /start to honor an explicit choice from the client (sent via any
    of the query/body keys: language / interview_language / lang) before
    falling back to the user's profile-stored language.
    """
    for raw in values:
        v = (raw or "").strip().lower()
        if v in ("ar", "en"):
            return v
    return None


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
    projects = data.get("projects", [])
    if isinstance(projects, list) and projects:
        random.shuffle(projects)
        proj_text = "; ".join(str(p) for p in projects[:5])
        parts.append(f"Projects: {proj_text[:300]}")
    experience = data.get("experience", [])
    if isinstance(experience, list) and experience:
        random.shuffle(experience)
        exp_text = "; ".join(str(e) for e in experience[:5])
        parts.append(f"Experience: {exp_text[:300]}")
    certs = data.get("certifications", []) or data.get("certificates", [])
    if isinstance(certs, list) and certs:
        cert_text = "; ".join(str(c) for c in certs[:5])
        parts.append(f"Certifications: {cert_text[:300]}")
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
        s.finished_at = datetime.now(timezone.utc)
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
        s.phase = "outro"
        s.finished_at = datetime.now(timezone.utc)
        db.commit()
        return {"phase": "outro", "prompt_type": "outro",
                "prompt_text": OUTRO_TEXT.get(language, OUTRO_TEXT["en"]),
                "transcript": transcript, "total_score": s.total_score}

    q_text = _get_sq_question_text(sq, db, language)
    q_type = sq.question_type or "technical"

    eval_question_text = q_text
    is_followup_answer = s.followup_count > 0
    if is_followup_answer:
        attempts = (sq.evaluation_json or {}).get("attempts", [])
        for att in reversed(attempts):
            if att.get("action") == "follow_up" and att.get("follow_up_question"):
                eval_question_text = att["follow_up_question"]
                break

    classification = classify_user_input(
        user_text=answer,
        current_question=eval_question_text,
        role=s.role_name,
        language=language,
    )

    # ── Clarification: explain WITHOUT giving the answer ──
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
                s.phase = "outro"
                s.finished_at = datetime.now(timezone.utc)
                db.commit()
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

    # ── Evaluate normal answer ──
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
        "tip": result.get("tip", ""),
        "answer_type": result.get("answer_type", "answered"),
        "correct_answer": result.get("correct_answer", ""),
    }

    action = result.get("action", "next")
    followup_q = (result.get("follow_up_question") or "").strip()
    answer_type = result.get("answer_type", "answered")

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
                s.phase = "outro"
                s.finished_at = datetime.now(timezone.utc)
                db.commit()
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
            s.phase = "outro"
            s.finished_at = datetime.now(timezone.utc)
            db.commit()
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

    if action in ("follow_up", "clarify") and s.followup_count < followup_max and followup_q:
        s.followup_count += 1
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

    s.followup_count = 0
    if sq.user_answer is None:
        sq.user_answer = answer
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
        s.phase = "outro"
        s.finished_at = datetime.now(timezone.utc)
        db.commit()
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