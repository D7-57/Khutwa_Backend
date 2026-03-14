from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.career.skill import Skill
from app.schemas.career.skills import SkillOut

router = APIRouter(prefix="/career/skills", tags=["career-skills"])


# ── GET /career/skills  (browse / search skills catalog) ──


@router.get("", response_model=list[SkillOut])
def list_skills(
    category: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Skill)

    if category:
        q = q.filter(Skill.category == category)

    if search:
        q = q.filter(Skill.name.ilike(f"%{search}%"))

    return q.order_by(Skill.category, Skill.name).limit(100).all()


# ── GET /career/skills/categories ──


@router.get("/categories", response_model=list[str])
def list_skill_categories(db: Session = Depends(get_db)):
    rows = (
        db.query(Skill.category)
        .filter(Skill.category.isnot(None))
        .distinct()
        .order_by(Skill.category)
        .all()
    )
    return [r[0] for r in rows]