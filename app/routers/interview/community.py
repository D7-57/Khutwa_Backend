from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.question import Question
from app.services.question_review import validate_and_translate

router = APIRouter(prefix="/questions/community", tags=["community-questions"])


# ─────────────────────────────────────────
#  SCHEMAS
# ─────────────────────────────────────────


class CommunityQuestionItem(BaseModel):
    question_text: str = Field(..., min_length=10, max_length=1000)
    question_type: str = "technical"  # technical | soft | behavioral | general
    difficulty: int = Field(default=3, ge=1, le=5)


class CommunitySubmitRequest(BaseModel):
    """Bulk submit: user picks role + optional company, then submits N questions."""
    role_name: str = Field(..., min_length=2)
    company: str | None = None
    language: str = "en"  # language the user wrote in
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
    status: str  # pending | approved | rejected
    rejection_reason: str | None = None
    created_at: str | None

    class Config:
        from_attributes = True


class CommunityQuestionUpdate(BaseModel):
    """Update one of your own questions (only while still pending)."""
    question_text: str | None = None
    question_type: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    company: str | None = None


# ─────────────────────────────────────────
#  SUBMIT (bulk) — with AI validation + translation
# ─────────────────────────────────────────


@router.post("", response_model=list[CommunityQuestionOut], status_code=201)
def submit_community_questions(
    body: CommunitySubmitRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    created = []

    for item in body.questions:
        # AI validates and translates
        result = validate_and_translate(
            question_text=item.question_text.strip(),
            source_language=body.language,
            role_name=body.role_name,
        )

        status = "pending" if result["approved"] else "rejected"

        q = Question(
            role_name=body.role_name,
            question_text_en=result["text_en"],
            question_text_ar=result["text_ar"],
            question_type=item.question_type,
            difficulty=item.difficulty,
            source="community",
            submitted_by=uid,
            status=status,
            rejection_reason=result.get("rejection_reason"),
            company=body.company.strip() if body.company else None,
            original_language=body.language,
        )
        db.add(q)
        db.flush()
        created.append(q)

    db.commit()

    return [_to_out(q) for q in created]


# ─────────────────────────────────────────
#  LIST MY SUBMISSIONS
# ─────────────────────────────────────────


@router.get("", response_model=list[CommunityQuestionOut])
def list_my_community_questions(
    status: str | None = None,  # filter: pending | approved | rejected
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
    return [_to_out(r) for r in rows]


# ─────────────────────────────────────────
#  UPDATE (own, only if pending)
# ─────────────────────────────────────────


@router.patch("/{question_id}", response_model=CommunityQuestionOut)
def update_my_community_question(
    question_id: str,
    body: CommunityQuestionUpdate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    q = _get_own_question(question_id, user_id, db)

    if q.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot edit a question that is already {q.status}.",
        )

    if body.question_text is not None:
        # Re-validate and re-translate
        result = validate_and_translate(
            question_text=body.question_text.strip(),
            source_language=q.original_language,
            role_name=q.role_name,
        )
        q.question_text_en = result["text_en"]
        q.question_text_ar = result["text_ar"]
        if not result["approved"]:
            q.status = "rejected"
            q.rejection_reason = result.get("rejection_reason")
    if body.question_type is not None:
        q.question_type = body.question_type
    if body.difficulty is not None:
        q.difficulty = body.difficulty
    if body.company is not None:
        q.company = body.company.strip() or None

    db.commit()
    db.refresh(q)
    return _to_out(q)


# ─────────────────────────────────────────
#  DELETE (own, only if pending)
# ─────────────────────────────────────────


@router.delete("/{question_id}", status_code=204)
def delete_my_community_question(
    question_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    q = _get_own_question(question_id, user_id, db)

    if q.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete a question that is already {q.status}.",
        )

    db.delete(q)
    db.commit()


# ─────────────────────────────────────────
#  BROWSE APPROVED (public, for discovery)
# ─────────────────────────────────────────


@router.get("/browse", response_model=list[CommunityQuestionOut])
def browse_community_questions(
    role_name: str | None = None,
    company: str | None = None,
    question_type: str | None = None,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Browse approved community questions. Users can see what others have contributed."""
    q = db.query(Question).filter(
        Question.source == "community",
        Question.status == "approved",
    )

    if role_name:
        q = q.filter(Question.role_name == role_name)
    if company:
        q = q.filter(Question.company.ilike(f"%{company}%"))
    if question_type:
        q = q.filter(Question.question_type == question_type)

    rows = q.order_by(Question.created_at.desc()).limit(50).all()
    return [_to_out(r) for r in rows]


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


def _to_out(q: Question) -> CommunityQuestionOut:
    return CommunityQuestionOut(
        id=q.id,
        role_name=q.role_name,
        question_text_en=q.question_text_en,
        question_text_ar=q.question_text_ar,
        question_type=q.question_type,
        difficulty=q.difficulty,
        company=q.company,
        original_language=q.original_language,
        status=q.status,
        rejection_reason=q.rejection_reason,
        created_at=q.created_at.isoformat() if q.created_at else None,
    )
