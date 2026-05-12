from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.career.skill import Skill, UserSkill
from app.schemas.auth.skills import (
    UserSkillAdd, UserSkillOut, UserSkillBulkAdd,
)

router = APIRouter(prefix="/auth/me/skills", tags=["auth-skills"])


# ── Helpers ─────────────────────────────────────────────────────────────


def _to_out(us: UserSkill, sk: Skill | None) -> UserSkillOut:
    """
    Build a UserSkillOut from a UserSkill row + (optional) joined Skill.
    When `sk` is None, the user_skill is a free-text custom entry and
    we surface `custom_name` as `skill_name` so the client gets a single
    field to display.
    """
    is_custom = us.skill_id is None
    display_name = (
        sk.name if sk is not None
        else (us.custom_name or "Unknown skill")
    )
    return UserSkillOut(
        id=us.id,
        skill_id=us.skill_id,
        skill_name=display_name,
        skill_category=sk.category if sk else None,
        custom_name=us.custom_name,
        is_custom=is_custom,
        level=us.level,
        years_experience=us.years_experience,
        source=us.source,
    )


# ── GET /auth/me/skills ──


@router.get("", response_model=list[UserSkillOut])
def list_my_skills(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    # OUTER JOIN — was INNER, but now skill_id can be NULL for free-text
    # entries. Inner join would silently drop those rows.
    rows = (
        db.query(UserSkill, Skill)
        .outerjoin(Skill, UserSkill.skill_id == Skill.id)
        .filter(UserSkill.user_id == uid)
        .all()
    )
    return [_to_out(us, sk) for us, sk in rows]


# ── POST /auth/me/skills  (add one) ──


@router.post("", response_model=UserSkillOut, status_code=201)
def add_my_skill(
    body: UserSkillAdd,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)

    # ── Catalog-skill branch ────────────────────────────────────────────
    if body.skill_id is not None:
        skill = db.get(Skill, body.skill_id)
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")

        existing = (
            db.query(UserSkill)
            .filter(
                UserSkill.user_id == uid,
                UserSkill.skill_id == body.skill_id,
            )
            .first()
        )
        if existing:
            # Update rather than 409 — POST is treated as "ensure this
            # skill is on my profile with these values".
            existing.level = body.level
            existing.years_experience = body.years_experience
            db.commit()
            db.refresh(existing)
            return _to_out(existing, skill)

        us = UserSkill(
            user_id=uid,
            skill_id=body.skill_id,
            custom_name=None,
            level=body.level,
            years_experience=body.years_experience,
            source="manual",
        )
        db.add(us)
        db.commit()
        db.refresh(us)
        return _to_out(us, skill)

    # ── Custom-name branch ──────────────────────────────────────────────
    # Before creating a free-text entry, check if a catalog Skill with
    # the same name (case-insensitive) exists. If yes, prefer the
    # catalog version — keeps the data tidy and lets future skill-gap
    # analysis treat it correctly.
    name_input = (body.custom_name or "").strip()
    if not name_input:
        raise HTTPException(status_code=400, detail="custom_name required")

    catalog_match = (
        db.query(Skill)
        .filter(func.lower(Skill.name) == name_input.lower())
        .first()
    )
    if catalog_match:
        existing = (
            db.query(UserSkill)
            .filter(
                UserSkill.user_id == uid,
                UserSkill.skill_id == catalog_match.id,
            )
            .first()
        )
        if existing:
            existing.level = body.level
            existing.years_experience = body.years_experience
            db.commit()
            db.refresh(existing)
            return _to_out(existing, catalog_match)

        us = UserSkill(
            user_id=uid,
            skill_id=catalog_match.id,
            custom_name=None,
            level=body.level,
            years_experience=body.years_experience,
            source="manual",
        )
        db.add(us)
        db.commit()
        db.refresh(us)
        return _to_out(us, catalog_match)

    # No catalog match — check existing free-text entry (case-insensitive).
    existing_custom = (
        db.query(UserSkill)
        .filter(
            UserSkill.user_id == uid,
            UserSkill.skill_id.is_(None),
            func.lower(UserSkill.custom_name) == name_input.lower(),
        )
        .first()
    )
    if existing_custom:
        # Update rather than fail
        existing_custom.level = body.level
        existing_custom.years_experience = body.years_experience
        db.commit()
        db.refresh(existing_custom)
        return _to_out(existing_custom, None)

    us = UserSkill(
        user_id=uid,
        skill_id=None,
        custom_name=name_input,
        level=body.level,
        years_experience=body.years_experience,
        source="manual",
    )
    db.add(us)
    db.commit()
    db.refresh(us)
    return _to_out(us, None)


# ── PUT /auth/me/skills/bulk  (replace all – for onboarding) ──


@router.put("/bulk", response_model=list[UserSkillOut])
def bulk_set_my_skills(
    body: UserSkillBulkAdd,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Onboarding bulk-set: replaces ALL of the user's skills with the
    provided list. Mixes catalog and custom entries freely.

    Catalog IDs are validated up front; failures here mean abort the
    whole call (no partial replacement).
    """
    uid = UUID(user_id)

    # Validate any provided catalog IDs first.
    catalog_ids = [s.skill_id for s in body.skills if s.skill_id is not None]
    skills_map: dict[UUID, Skill] = {}
    if catalog_ids:
        skills_map = {
            sk.id: sk
            for sk in db.query(Skill).filter(Skill.id.in_(catalog_ids)).all()
        }
        missing = set(catalog_ids) - set(skills_map.keys())
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"Skills not found: {[str(m) for m in missing]}",
            )

    # Wipe existing.
    db.query(UserSkill).filter(UserSkill.user_id == uid).delete(
        synchronize_session="fetch",
    )

    # Insert new.
    results: list[UserSkillOut] = []
    for item in body.skills:
        if item.skill_id is not None:
            us = UserSkill(
                user_id=uid,
                skill_id=item.skill_id,
                custom_name=None,
                level=item.level,
                years_experience=item.years_experience,
                source="manual",
            )
            sk = skills_map[item.skill_id]
        else:
            us = UserSkill(
                user_id=uid,
                skill_id=None,
                custom_name=(item.custom_name or "").strip(),
                level=item.level,
                years_experience=item.years_experience,
                source="manual",
            )
            sk = None
        db.add(us)
        db.flush()
        results.append(_to_out(us, sk))

    db.commit()
    return results


# ── DELETE /auth/me/skills/{user_skill_id} ──
#
# BREAKING CHANGE: this used to delete by skill_id. That only works
# for catalog skills — for free-text entries skill_id is NULL, so the
# old endpoint couldn't delete them. We now delete by the UserSkill
# row's primary-key id, which works for both kinds.


@router.delete("/{user_skill_id}", status_code=204)
def remove_my_skill(
    user_skill_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    try:
        sid = UUID(user_skill_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_skill_id")

    deleted = (
        db.query(UserSkill)
        .filter(UserSkill.id == sid, UserSkill.user_id == uid)
        .delete(synchronize_session="fetch")
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Skill not in your profile")

    db.commit()