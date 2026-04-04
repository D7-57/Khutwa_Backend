"""Community question bank submissions (used by Flutter question bank UI)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.question import Question

router = APIRouter(tags=["questions"])


class QuestionSubmitIn(BaseModel):
    role_name: str
    question_text: str
    difficulty: int = Field(default=2, ge=1, le=5)


def _norm_role_name(s: str) -> str:
    t = (s or "").strip().lower().replace(" ", "_")
    return t or "general"


@router.post("/questions/submit")
def submit_community_question(
    body: QuestionSubmitIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    _ = user_id
    text = body.question_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="question_text is required")

    q = Question(
        role_name=_norm_role_name(body.role_name),
        question_text=text,
        difficulty=max(1, min(5, body.difficulty)),
        source="community",
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return {"id": str(q.id), "ok": True}
