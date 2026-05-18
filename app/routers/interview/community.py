"""
Community questions router — v2.

Changes vs v1:
  • Two-tier intake based on AI quality_score:
        ≥ 55 → status='approved' immediately
        < 55 → status='rejected'
  • Like/Dislike voting on approved questions.
  • Browse endpoint supports approved/rejected/all.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.question import Question
from app.models.question_vote import QuestionVote
from app.models.interview import SessionQuestion
from app.services.question_review import validate_and_translate
from app.services.achievements import check_and_award

router = APIRouter(prefix="/questions/community", tags=["community-questions"])


# ─────────────────────────────────────────
#  SCHEMAS
# ─────────────────────────────────────────

class CommunityQuestionItem(BaseModel):
    question_text: str = Field(..., min_length=10, max_length=1000)
    question_type: str = "technical"  # technical | soft | behavioral | general


class CommunitySubmitRequest(BaseModel):
    role_name: str = Field(..., min_length=2)
    company: str | None = None
    language: str = "en"
    questions: list[CommunityQuestionItem] = Field(..., min_length=1, max_length=20)


class CommunityQuestionOut(BaseModel):
    id: UUID
    role_name: str
    question_text_en: str | None
    question_text_ar: str | None
    question_type: str
    difficulty: int
    company: str | None
    original_language: str
    status: str
    rejection_reason: str | None = None
    quality_score: int | None = None
    upvotes: int = 0
    downvotes: int = 0
    my_vote: int | None = None  # +1, -1, or None if user hasn't voted
    created_at: str | None

    class Config:
        from_attributes = True


class CommunityQuestionUpdate(BaseModel):
    question_text: str | None = None
    question_type: str | None = None
    company: str | None = None


class VoteRequest(BaseModel):
    vote: int = Field(..., description="+1 like, -1 dislike, 0 to clear vote")


class CommunitySubmitResponse(BaseModel):
    """
    Wrapper response so we can fold `new_achievements` alongside the list
    of created questions. The earlier shape (bare list) wouldn't let us
    piggyback achievement awards on the submit response.
    """
    questions: list[CommunityQuestionOut]
    new_achievements: list[dict] = []


# ─────────────────────────────────────────
#  SUBMIT
# ─────────────────────────────────────────

def _status_from_quality(quality_score: int) -> str:
    """Two-tier intake: approve high quality, reject everything else."""
    if quality_score >= 55:
        return "approved"
    return "rejected"


def _difficulty_from_quality(quality_score: int) -> int:
    """Map AI quality score (0..100) to 1..5 stars."""
    if quality_score >= 90:
        return 5
    if quality_score >= 75:
        return 4
    if quality_score >= 60:
        return 3
    if quality_score >= 45:
        return 2
    return 1


@router.post("", response_model=CommunitySubmitResponse, status_code=201)
def submit_community_questions(
    body: CommunitySubmitRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    created = []

    for item in body.questions:
        result = validate_and_translate(
            question_text=item.question_text.strip(),
            source_language=body.language,
            role_name=body.role_name,
        )

        quality_score = int(result.get("quality_score", 50))
        status = _status_from_quality(quality_score)

        q = Question(
            role_name=body.role_name,
            question_text_en=result["text_en"],
            question_text_ar=result["text_ar"],
            question_type=item.question_type,
            difficulty=_difficulty_from_quality(quality_score),
            source="community",
            submitted_by=uid,
            status=status,
            rejection_reason=result.get("rejection_reason") if status == "rejected" else None,
            quality_score=quality_score,
            company=body.company.strip() if body.company else None,
            original_language=body.language,
        )
        db.add(q)
        db.flush()
        created.append(q)

    # Award achievements after rows are flushed so the predicate's COUNT
    # query sees the new submissions. community_first fires on submit
    # regardless of status; community_star / community_legend gate on
    # approved count.
    new_achievements = check_and_award(uid, db, trigger="community_submit")
    db.commit()

    return CommunitySubmitResponse(
        questions=[_to_out(q, db, uid) for q in created],
        new_achievements=new_achievements,
    )


# ─────────────────────────────────────────
#  LIST MY SUBMISSIONS
# ─────────────────────────────────────────

@router.get("", response_model=list[CommunityQuestionOut])
def list_my_community_questions(
    status: str | None = None,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    q = db.query(Question).filter(
        Question.submitted_by == uid,
        Question.source == "community",
    )
    if status:
        q = q.filter(Question.status == status)
    rows = q.order_by(Question.created_at.desc()).limit(100).all()
    return [_to_out(r, db, uid) for r in rows]


# ─────────────────────────────────────────
#  UPDATE / DELETE (own, editable when not approved)
# ─────────────────────────────────────────

@router.patch("/{question_id}", response_model=CommunityQuestionOut)
def update_my_community_question(
    question_id: str,
    body: CommunityQuestionUpdate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    q = _get_own_question(question_id, user_id, db)

    if q.status == "approved":
        raise HTTPException(
            status_code=400,
            detail="Cannot edit an approved question.",
        )

    if body.question_text is not None:
        result = validate_and_translate(
            question_text=body.question_text.strip(),
            source_language=q.original_language,
            role_name=q.role_name,
        )
        q.question_text_en = result["text_en"]
        q.question_text_ar = result["text_ar"]
        q.quality_score = int(result.get("quality_score", q.quality_score or 50))
        new_status = _status_from_quality(q.quality_score or 50)
        q.status = new_status
        q.difficulty = _difficulty_from_quality(q.quality_score or 0)
        q.rejection_reason = (
            result.get("rejection_reason") if new_status == "rejected" else None
        )

    if body.question_type is not None:
        q.question_type = body.question_type
    if body.company is not None:
        q.company = body.company.strip() or None

    db.commit()
    db.refresh(q)
    return _to_out(q, db, UUID(user_id))


@router.delete("/{question_id}", status_code=204)
def delete_my_community_question(
    question_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Withdraw one of your own submissions.

    - approved → soft-deleted: status set to 'rejected' with a "withdrawn by
                 author" reason. This stops it appearing in future interviews
                 (selection only pulls 'approved' rows) without breaking the
                 history of sessions that already used the question. Hard
                 deletion would FK-violate against session_questions.
    - rejected → already invisible to selection, hard-delete only if no
                 session ever used it; otherwise soft-update the reason.
    """
    q = _get_own_question(question_id, user_id, db)

    # Check if any session has referenced this question — if so, we can't
    # hard-delete without breaking history.
    referenced = db.query(
        db.query(SessionQuestion).filter(SessionQuestion.question_id == q.id).exists()
    ).scalar()

    if q.status != "approved" and not referenced:
        db.delete(q)
        db.commit()
        return

    # Soft delete: mark rejected with a clear reason.
    q.status = "rejected"
    q.rejection_reason = "Withdrawn by author"
    db.commit()


# ─────────────────────────────────────────
#  BROWSE / ROLES
# ─────────────────────────────────────────

@router.get("/roles", response_model=list[str])
def list_question_roles(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Question.role_name)
        .filter(Question.status == "approved")
        .distinct()
        .all()
    )
    return sorted(set(r[0] for r in rows if r[0]))


@router.get("/browse", response_model=list[CommunityQuestionOut])
def browse_community_questions(
    role_name: str | None = None,
    company: str | None = None,
    question_type: str | None = None,
    status: str = Query("approved", description="approved | rejected | all"),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Browse community questions. Defaults to approved.
    """
    uid = UUID(user_id)
    q = db.query(Question).filter(Question.source == "community")

    if status == "approved":
        q = q.filter(Question.status == "approved")
    elif status == "rejected":
        q = q.filter(Question.status == "rejected")
    elif status == "all":
        q = q.filter(Question.status.in_(("approved", "rejected")))
    else:
        raise HTTPException(400, detail="status must be approved | rejected | all")

    if role_name:
        q = q.filter(Question.role_name == role_name)
    if company:
        q = q.filter(Question.company.ilike(f"%{company}%"))
    if question_type:
        q = q.filter(Question.question_type == question_type)

    rows = q.order_by(Question.created_at.desc()).limit(50).all()

    return [_to_out(r, db, uid) for r in rows]


# ─────────────────────────────────────────
#  VOTE on an approved community question
# ─────────────────────────────────────────

@router.post("/{question_id}/vote", response_model=CommunityQuestionOut)
def vote_on_community_question(
    question_id: str,
    body: VoteRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Like (+1), dislike (-1), or clear (0) your vote on a community question.

    The auto-promote/demote logic lives in the Postgres trigger
    `fn_recompute_question_status` so the rule stays consistent.
    """
    try:
        qid = UUID(question_id)
    except ValueError:
        raise HTTPException(400, detail="Invalid question_id")

    if body.vote not in (-1, 0, 1):
        raise HTTPException(400, detail="vote must be -1, 0, or +1")

    q = db.get(Question, qid)
    if not q:
        raise HTTPException(404, detail="Question not found")
    # AI-generated questions are session-specific synthesis, not bank entries —
    # voting on them doesn't help anyone else. Seed and community questions
    # are both in the shared bank, so both are valid vote targets.
    if q.source == "ai_generated":
        raise HTTPException(
            400, detail="AI-generated questions can't be voted on (not in the bank)"
        )

    # Don't let users vote on their own submissions — bias problem.
    uid = UUID(user_id)
    if q.submitted_by == uid:
        raise HTTPException(400, detail="You can't vote on your own submission")

    # Voting is only allowed on approved questions in the bank.
    if q.status != "approved":
        raise HTTPException(400, detail=f"Question is {q.status}; voting closed")

    existing = (
        db.query(QuestionVote)
        .filter(QuestionVote.question_id == qid, QuestionVote.user_id == uid)
        .one_or_none()
    )

    # Compute the diff to apply to question counters.
    old_vote = existing.vote if existing else 0
    new_vote = body.vote

    if old_vote == new_vote:
        # No-op
        return _to_out(q, db, uid)

    # Adjust counters atomically.
    if old_vote == 1:
        q.upvotes = max(0, q.upvotes - 1)
    elif old_vote == -1:
        q.downvotes = max(0, q.downvotes - 1)

    if new_vote == 1:
        q.upvotes += 1
    elif new_vote == -1:
        q.downvotes += 1

    # Persist the vote row (or remove it for clear).
    if new_vote == 0:
        if existing:
            db.delete(existing)
    else:
        if existing:
            existing.vote = new_vote
        else:
            db.add(QuestionVote(question_id=qid, user_id=uid, vote=new_vote))

    db.commit()
    db.refresh(q)
    return _to_out(q, db, uid)


# ─────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────

def _get_own_question(question_id: str, user_id: str, db: Session) -> Question:
    try:
        qid = UUID(question_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid question_id")

    q = db.get(Question, qid)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    if str(q.submitted_by) != user_id:
        raise HTTPException(status_code=403, detail="Not your question")

    return q


def _to_out(q: Question, db: Session, viewer_uid: UUID | None = None) -> CommunityQuestionOut:
    status = q.status
    if status == "pending":
        # Backward compatibility for legacy rows after removing pending.
        status = "rejected"

    my_vote = None
    if viewer_uid is not None:
        v = (
            db.query(QuestionVote.vote)
            .filter(
                QuestionVote.question_id == q.id,
                QuestionVote.user_id == viewer_uid,
            )
            .one_or_none()
        )
        if v:
            my_vote = int(v[0])

    return CommunityQuestionOut(
        id=q.id,
        role_name=q.role_name,
        question_text_en=q.question_text_en,
        question_text_ar=q.question_text_ar,
        question_type=q.question_type,
        difficulty=q.difficulty,
        company=q.company,
        original_language=q.original_language,
        status=status,
        rejection_reason=q.rejection_reason,
        quality_score=q.quality_score,
        upvotes=q.upvotes or 0,
        downvotes=q.downvotes or 0,
        my_vote=my_vote,
        created_at=q.created_at.isoformat() if q.created_at else None,
    )
