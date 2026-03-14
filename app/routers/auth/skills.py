from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.career.skill import Skill, UserSkill
from app.schemas.auth.skills import UserSkillAdd, UserSkillOut, UserSkillBulkAdd

router = APIRouter(prefix="/auth/me/skills", tags=["auth-skills"])


# ── GET /auth/me/skills ──


@router.get("", response_model=list[UserSkillOut])
def list_my_skills(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    rows = (
        db.query(UserSkill, Skill)
        .join(Skill, UserSkill.skill_id == Skill.id)
        .filter(UserSkill.user_id == uid)
        .all()
    )
    return [
        UserSkillOut(
            id=us.id,
            skill_id=us.skill_id,
            skill_name=sk.name,
            skill_category=sk.category,
            level=us.level,
            years_experience=us.years_experience,
            source=us.source,
        )
        for us, sk in rows
    ]


# ── POST /auth/me/skills  (add one) ──


@router.post("", response_model=UserSkillOut, status_code=201)
def add_my_skill(
    body: UserSkillAdd,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)

    skill = db.get(Skill, body.skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    existing = (
        db.query(UserSkill)
        .filter(UserSkill.user_id == uid, UserSkill.skill_id == body.skill_id)
        .first()
    )
    if existing:
        # update instead of duplicate
        existing.level = body.level
        existing.years_experience = body.years_experience
        db.commit()
        db.refresh(existing)
        return UserSkillOut(
            id=existing.id,
            skill_id=existing.skill_id,
            skill_name=skill.name,
            skill_category=skill.category,
            level=existing.level,
            years_experience=existing.years_experience,
            source=existing.source,
        )

    us = UserSkill(
        user_id=uid,
        skill_id=body.skill_id,
        level=body.level,
        years_experience=body.years_experience,
        source="manual",
    )
    db.add(us)
    db.commit()
    db.refresh(us)

    return UserSkillOut(
        id=us.id,
        skill_id=us.skill_id,
        skill_name=skill.name,
        skill_category=skill.category,
        level=us.level,
        years_experience=us.years_experience,
        source=us.source,
    )


# ── PUT /auth/me/skills/bulk  (replace all – for onboarding) ──


@router.put("/bulk", response_model=list[UserSkillOut])
def bulk_set_my_skills(
    body: UserSkillBulkAdd,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)

    # validate all skill IDs first
    skill_ids = [s.skill_id for s in body.skills]
    skills_map = {
        sk.id: sk
        for sk in db.query(Skill).filter(Skill.id.in_(skill_ids)).all()
    }
    missing = set(skill_ids) - set(skills_map.keys())
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Skills not found: {[str(m) for m in missing]}",
        )

    # delete old
    db.query(UserSkill).filter(UserSkill.user_id == uid).delete()

    # insert new
    results = []
    for item in body.skills:
        us = UserSkill(
            user_id=uid,
            skill_id=item.skill_id,
            level=item.level,
            years_experience=item.years_experience,
            source="manual",
        )
        db.add(us)
        db.flush()
        sk = skills_map[item.skill_id]
        results.append(
            UserSkillOut(
                id=us.id,
                skill_id=us.skill_id,
                skill_name=sk.name,
                skill_category=sk.category,
                level=us.level,
                years_experience=us.years_experience,
                source=us.source,
            )
        )

    db.commit()
    return results


# ── DELETE /auth/me/skills/{skill_id} ──


@router.delete("/{skill_id}", status_code=204)
def remove_my_skill(
    skill_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    try:
        sid = UUID(skill_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid skill_id")

    deleted = (
        db.query(UserSkill)
        .filter(UserSkill.user_id == uid, UserSkill.skill_id == sid)
        .delete()
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Skill not in your profile")

    db.commit()