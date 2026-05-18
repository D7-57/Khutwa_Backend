"""
Achievements router.

Endpoints
─────────
GET  /achievements             — public catalog. Secret achievements that
                                 the caller hasn't unlocked yet are masked
                                 (title/description replaced with '???',
                                 icon kept generic).
GET  /achievements/me          — caller's full state: every catalog row +
                                 unlocked/earned_at info. Locked secrets stay
                                 masked.
GET  /achievements/unseen      — queue for offline-earned pop-ups. Returns
                                 unlocked-but-not-yet-seen rows so the client
                                 can flash them on app resume.
POST /achievements/mark-seen   — batch-flip `seen=True` for a list of
                                 user_achievement IDs. Idempotent.
POST /achievements/trigger/{trigger_name}
                               — for frontend-only events (bilingual_switch,
                                 cv_enhance). Body is an optional context
                                 dict that the service can read.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.achievement import Achievement, UserAchievement
from app.services.achievements import check_and_award

router = APIRouter(prefix="/achievements", tags=["achievements"])


# ─────────────────────────────────────────────
#  Schemas
# ─────────────────────────────────────────────

class AchievementOut(BaseModel):
    id: str
    key: str
    title_en: str
    title_ar: str
    description_en: str
    description_ar: str
    icon: str
    tier: str
    category: str
    is_secret: bool
    sort_order: int
    # Per-user state — populated by /me and /unseen, null on /catalog.
    unlocked: bool = False
    earned_at: str | None = None
    seen: bool | None = None
    user_achievement_id: str | None = None


class MarkSeenRequest(BaseModel):
    user_achievement_ids: list[str]


class TriggerRequest(BaseModel):
    # Free-form context the predicate can read. Frontend can stuff
    # things like {"enhance_count": 3} for cv_enhance, or
    # {"during_active_session": true} for bilingual_switch.
    context: dict[str, Any] = {}


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def _mask_secret(a: Achievement, unlocked: bool) -> dict:
    """Catalog/me serialization with secret-masking."""
    if a.is_secret and not unlocked:
        return {
            "id": str(a.id),
            "key": a.key,                # key isn't sensitive — frontend may want it
            "title_en": "???",
            "title_ar": "؟؟؟",
            "description_en": "???",
            "description_ar": "؟؟؟",
            "icon": "❓",
            "tier": a.tier,
            "category": a.category,
            "is_secret": True,
            "sort_order": a.sort_order,
        }
    return {
        "id": str(a.id),
        "key": a.key,
        "title_en": a.title_en,
        "title_ar": a.title_ar,
        "description_en": a.description_en,
        "description_ar": a.description_ar,
        "icon": a.icon,
        "tier": a.tier,
        "category": a.category,
        "is_secret": a.is_secret,
        "sort_order": a.sort_order,
    }


# ─────────────────────────────────────────────
#  GET /achievements — public catalog
# ─────────────────────────────────────────────

@router.get("", response_model=list[AchievementOut])
def list_catalog(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Returns the full catalog. Secrets the caller hasn't earned are masked.
    The endpoint still requires auth so we can do per-user masking.
    """
    uid = UUID(user_id)
    owned: set[UUID] = {
        row[0]
        for row in db.query(UserAchievement.achievement_id)
        .filter(UserAchievement.user_id == uid)
        .all()
    }

    rows = db.query(Achievement).order_by(Achievement.sort_order, Achievement.key).all()
    out = []
    for a in rows:
        unlocked = a.id in owned
        out.append({**_mask_secret(a, unlocked), "unlocked": unlocked})
    return out


# ─────────────────────────────────────────────
#  GET /achievements/me — catalog + my state
# ─────────────────────────────────────────────

@router.get("/me", response_model=list[AchievementOut])
def list_mine(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Returns every catalog row paired with the caller's unlock state. Secrets
    still mask if unearned, but unlocked secrets reveal in full (with tier
    and earned_at). One pass — used by the AchievementsPage grid.
    """
    uid = UUID(user_id)

    mine: dict[UUID, UserAchievement] = {
        ua.achievement_id: ua
        for ua in db.query(UserAchievement)
        .filter(UserAchievement.user_id == uid)
        .all()
    }

    rows = db.query(Achievement).order_by(Achievement.sort_order, Achievement.key).all()
    out = []
    for a in rows:
        ua = mine.get(a.id)
        unlocked = ua is not None
        item = _mask_secret(a, unlocked)
        item["unlocked"] = unlocked
        if ua is not None:
            item["earned_at"] = ua.earned_at.isoformat() if ua.earned_at else None
            item["seen"] = ua.seen
            item["user_achievement_id"] = str(ua.id)
        out.append(item)
    return out


# ─────────────────────────────────────────────
#  GET /achievements/unseen — pop-up queue
# ─────────────────────────────────────────────

@router.get("/unseen", response_model=list[AchievementOut])
def list_unseen(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Returns unlocked-but-unseen achievements for offline-earned pop-ups.
    Called on app startup and on AppLifecycleState.resumed. The composite
    index (user_id, seen) makes this an index scan even on big tables.

    Caller is expected to display each as a toast and then either let the
    overlay's auto-mark hook fire, or batch the IDs into /mark-seen.
    """
    uid = UUID(user_id)
    rows = (
        db.query(UserAchievement)
        .filter(UserAchievement.user_id == uid, UserAchievement.seen.is_(False))
        .order_by(UserAchievement.earned_at.asc())
        .all()
    )
    out = []
    for ua in rows:
        a = ua.achievement
        # Pop-ups always show the full data — by the time we're showing the
        # toast the user has earned it, so secrets reveal.
        out.append({
            **_mask_secret(a, unlocked=True),
            "unlocked": True,
            "earned_at": ua.earned_at.isoformat() if ua.earned_at else None,
            "seen": ua.seen,
            "user_achievement_id": str(ua.id),
        })
    return out


# ─────────────────────────────────────────────
#  POST /achievements/mark-seen — batch flip
# ─────────────────────────────────────────────

@router.post("/mark-seen")
def mark_seen(
    body: MarkSeenRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Flip seen=True for the given user_achievement rows. Scoped to caller."""
    uid = UUID(user_id)
    if not body.user_achievement_ids:
        return {"marked": 0}

    try:
        ids = [UUID(s) for s in body.user_achievement_ids]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid id in payload")

    updated = (
        db.query(UserAchievement)
        .filter(
            UserAchievement.id.in_(ids),
            UserAchievement.user_id == uid,
        )
        .update({UserAchievement.seen: True}, synchronize_session=False)
    )
    db.commit()
    return {"marked": int(updated)}


# ─────────────────────────────────────────────
#  POST /achievements/trigger/{name} — for frontend events
# ─────────────────────────────────────────────

# Whitelist — only triggers that originate purely on the client are exposed.
# Backend-driven triggers (interview_complete, cv_evaluate, …) are NOT in
# this list so a hostile client can't forge them; they only fire from
# the corresponding domain endpoint.
_CLIENT_TRIGGERS = {"bilingual_switch", "cv_enhance"}


@router.post("/trigger/{trigger_name}", response_model=list[AchievementOut])
def fire_trigger(
    trigger_name: str,
    body: TriggerRequest | None = None,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Frontend-only events. The bilingual_switch trigger fires when the user
    flips locale mid-active-interview; cv_enhance fires after a successful
    /cv/builder/enhance call (with an enhance_count in ctx).
    """
    if trigger_name not in _CLIENT_TRIGGERS:
        raise HTTPException(status_code=400, detail="Unknown or non-client trigger")

    ctx: dict[str, Any] = (body.context if body else {}) or {}
    uid = UUID(user_id)
    awarded = check_and_award(uid, db, trigger=trigger_name, **ctx)
    db.commit()

    # The serialized shape from the service is already pop-up-ready, but
    # AchievementOut also has sort_order/unlocked — fill them in.
    out = []
    for item in awarded:
        out.append({
            **item,
            "sort_order": 0,
            "unlocked": True,
        })
    return out