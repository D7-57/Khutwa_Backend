"""
Achievement awarding logic.

Single public entry point: `check_and_award(user_id, db, trigger, **ctx)`.

Design:
  • Trigger-driven, not poll-driven. Each domain endpoint (interview finalize,
    CV evaluate, community submit, roadmap task complete, etc.) calls this
    with the relevant trigger string. We then re-evaluate ONLY the achievements
    that watch that trigger, query the user's current state, and insert any
    newly-earned rows.
  • Idempotent. We always SELECT existing user_achievements first and skip
    keys the user already has. The DB unique constraint
    (uq_user_achievement) is a belt-and-braces against races.
  • Caller-controlled commit. We `db.flush()` so the new rows get IDs and
    relationships populate, but we never commit — the calling endpoint
    commits as part of its own transaction. This way an achievement award
    that fails halfway can't poison the underlying action (and vice versa:
    if the underlying action rolls back, the award rolls back with it).
  • Returns the list of newly-awarded achievements as plain dicts, ready to
    drop into a response payload as `new_achievements`.

Trigger inventory:
    interview_complete   — fired on finalize / WS-driven phase flip to finished
    cv_upload            — fired by /cv/upload
    cv_evaluate          — fired by /cv/{id}/evaluate
    cv_enhance           — fired via /achievements/trigger/cv_enhance from the
                           builder UI when a section enhancement completes
    community_submit     — fired by POST /questions/community (NOT on approval —
                           First Contribution rewards the act of submitting)
    community_approved   — re-evaluated alongside community_submit; the
                           community_star / question_legend achievements gate
                           on approved-count, which gets recomputed every time
                           a submit fires (cheap, and covers async approvals
                           from the Postgres trigger as soon as the user does
                           anything else)
    roadmap_task         — fired by PATCH /roadmap/me/tasks/{id}/complete
    bilingual_switch     — fired via /achievements/trigger/bilingual_switch
                           when the user toggles locale mid-interview-session
    jrs_update           — fired whenever a JRS recompute would change
                           (today: piggybacked off interview_complete and
                           cv_evaluate as a downstream re-check)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.achievement import Achievement, UserAchievement
from app.models.cv import CVDocument, CVEvaluation
from app.models.interview import InterviewSession
from app.models.question import Question
from app.models.roadmap.models import RoadmapStage, RoadmapTask, UserRoadmap


# ─────────────────────────────────────────────────────────────────────
#  Trigger → list-of-achievement-keys map.
#  Keeping this explicit (vs. evaluating every achievement on every trigger)
#  keeps each request cheap. If you add a new achievement, register it here.
# ─────────────────────────────────────────────────────────────────────

_TRIGGER_KEYS: dict[str, list[str]] = {
    "interview_complete": [
        "interview_first",
        "interview_5",
        "interview_10",
        "interview_50",
        "interview_score_90",
        "interview_perfect_100",
        "interview_weekly_streak",
        "interview_rapid_fire",
        "interview_night_owl",
        "meta_jrs_gold",
        "meta_platinum_10",
    ],
    "cv_upload": [
        "cv_first_upload",
        "meta_platinum_10",
    ],
    "cv_evaluate": [
        "cv_ats_80",
        "meta_jrs_gold",
        "meta_platinum_10",
    ],
    "cv_enhance": [
        "cv_polished",
        "meta_platinum_10",
    ],
    "community_submit": [
        "community_first",
        "community_star",
        "community_legend",
        "meta_platinum_10",
    ],
    "roadmap_task": [
        "roadmap_first_task",
        "roadmap_pathfinder",
        "meta_platinum_10",
    ],
    "bilingual_switch": [
        "meta_bilingual",
        "meta_platinum_10",
    ],
    "jrs_update": [
        "meta_jrs_gold",
        "meta_platinum_10",
    ],
}


# ─────────────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────────────

def check_and_award(
    user_id: UUID | str,
    db: Session,
    trigger: str,
    **ctx: Any,
) -> list[dict]:
    """
    Re-evaluate the achievements bound to `trigger` for `user_id`, insert any
    newly-earned UserAchievement rows, and return them as serializable dicts.

    `ctx` carries optional trigger-specific context — currently only used by:
      • interview_complete: pass `session_id=...` so we can detect the
        rapid-fire/night-owl/perfect-100 conditions from the just-finished
        session directly, without a second query.

    Caller must commit the surrounding transaction. We only flush so PKs
    populate and the returned dicts have IDs.
    """
    uid = UUID(str(user_id)) if not isinstance(user_id, UUID) else user_id

    keys = _TRIGGER_KEYS.get(trigger, [])
    if not keys:
        return []

    # Single query for everything the user already has — cheap, and lets us
    # cheaply skip already-unlocked keys without a per-key SELECT.
    owned_keys: set[str] = set(
        db.execute(
            select(Achievement.key)
            .join(UserAchievement, UserAchievement.achievement_id == Achievement.id)
            .where(UserAchievement.user_id == uid)
        ).scalars()
    )

    # Candidate achievement rows: those bound to this trigger AND not yet owned.
    candidates = (
        db.execute(
            select(Achievement).where(
                Achievement.key.in_(keys),
                Achievement.key.notin_(owned_keys) if owned_keys else True,
            )
        ).scalars().all()
    )
    if not candidates:
        return []

    newly: list[UserAchievement] = []
    for ach in candidates:
        if _is_earned(ach.key, uid, db, ctx):
            ua = UserAchievement(
                user_id=uid,
                achievement_id=ach.id,
                seen=False,
            )
            db.add(ua)
            newly.append(ua)

    if not newly:
        return []

    # Flush so PKs populate and the joined Achievement relationship is loaded.
    db.flush()

    return [_serialize(ua) for ua in newly]


# ─────────────────────────────────────────────────────────────────────
#  Predicate dispatch — one function per achievement key.
# ─────────────────────────────────────────────────────────────────────

def _is_earned(key: str, uid: UUID, db: Session, ctx: dict) -> bool:
    fn = _PREDICATES.get(key)
    if not fn:
        # Unknown key in catalog — never auto-award.
        return False
    try:
        return bool(fn(uid, db, ctx))
    except Exception:
        # Predicate errors must NOT block the underlying action.
        # Awarding fails silently; user will get it next trigger.
        return False


# ── interview achievements ──────────────────────────────────────────

def _interview_finished_q(uid: UUID, db: Session):
    return db.query(InterviewSession).filter(
        InterviewSession.user_id == uid,
        InterviewSession.phase.in_(("finished", "outro")),
    )


def _p_interview_first(uid: UUID, db: Session, _ctx: dict) -> bool:
    return _interview_finished_q(uid, db).limit(1).count() >= 1


def _p_interview_5(uid: UUID, db: Session, _ctx: dict) -> bool:
    return _interview_finished_q(uid, db).count() >= 5


def _p_interview_10(uid: UUID, db: Session, _ctx: dict) -> bool:
    return _interview_finished_q(uid, db).count() >= 10


def _p_interview_50(uid: UUID, db: Session, _ctx: dict) -> bool:
    return _interview_finished_q(uid, db).count() >= 50


def _p_interview_score_90(uid: UUID, db: Session, _ctx: dict) -> bool:
    return _interview_finished_q(uid, db).filter(
        InterviewSession.total_score >= 90
    ).limit(1).count() >= 1


def _p_interview_perfect_100(uid: UUID, db: Session, _ctx: dict) -> bool:
    return _interview_finished_q(uid, db).filter(
        InterviewSession.total_score == 100
    ).limit(1).count() >= 1


def _p_interview_weekly_streak(uid: UUID, db: Session, _ctx: dict) -> bool:
    """3 finished interviews in the last 7 days (calendar window, not strict days-in-a-row)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    return (
        _interview_finished_q(uid, db)
        .filter(InterviewSession.created_at >= cutoff)
        .count()
        >= 3
    )


def _p_interview_rapid_fire(uid: UUID, db: Session, ctx: dict) -> bool:
    """Completed a rapid-fire session. Cheap fast-path via ctx, fallback to query."""
    sid = ctx.get("session_id")
    if sid:
        s = db.get(InterviewSession, UUID(str(sid)))
        if s and s.is_rapid and s.phase in ("finished", "outro"):
            return True
    return (
        _interview_finished_q(uid, db)
        .filter(InterviewSession.is_rapid.is_(True))
        .limit(1)
        .count()
        >= 1
    )


def _p_interview_night_owl(uid: UUID, db: Session, ctx: dict) -> bool:
    """
    Secret: finished an interview between 00:00 and 04:00 local time. Since we
    only have UTC timestamps server-side, we approximate with UTC — a
    reasonable proxy for "the middle of the night somewhere".

    We check the just-finished session (if provided) AND historic sessions,
    so retroactive unlocks work too.
    """
    def _is_night(dt: datetime | None) -> bool:
        if not dt:
            return False
        # Normalize to UTC if naive.
        d = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        return 0 <= d.astimezone(timezone.utc).hour < 4

    sid = ctx.get("session_id")
    if sid:
        s = db.get(InterviewSession, UUID(str(sid)))
        if s and _is_night(s.finished_at or s.created_at):
            return True

    # Fallback historical check — paginate-cheap because finished_at is indexed
    # via the row, and the limit caps the work.
    rows = (
        _interview_finished_q(uid, db)
        .with_entities(InterviewSession.finished_at, InterviewSession.created_at)
        .limit(200)
        .all()
    )
    return any(_is_night(fa or ca) for fa, ca in rows)


# ── CV achievements ─────────────────────────────────────────────────

def _p_cv_first_upload(uid: UUID, db: Session, _ctx: dict) -> bool:
    return db.query(CVDocument).filter(CVDocument.user_id == uid).limit(1).count() >= 1


def _p_cv_ats_80(uid: UUID, db: Session, _ctx: dict) -> bool:
    """
    ATS 80+ on any evaluation of any CV the user owns. We join via cv_documents
    because CVEvaluation doesn't carry user_id directly.
    """
    return (
        db.query(CVEvaluation)
        .join(CVDocument, CVDocument.id == CVEvaluation.cv_id)
        .filter(CVDocument.user_id == uid, CVEvaluation.ats_score >= 80)
        .limit(1)
        .count()
        >= 1
    )


def _p_cv_polished(uid: UUID, db: Session, ctx: dict) -> bool:
    """
    "Polished" = 3 enhance operations. Enhance is a stateless AI call (it
    doesn't persist a row per enhance), so we tally inside the user's profile
    JSONB via the trigger endpoint. The trigger endpoint passes a running
    count in ctx['enhance_count'] — see /achievements/trigger/cv_enhance.
    """
    return int(ctx.get("enhance_count") or 0) >= 3


# ── Community achievements ──────────────────────────────────────────

def _p_community_first(uid: UUID, db: Session, _ctx: dict) -> bool:
    """
    First Contribution fires on submit, not on approval — community questions
    most often land in 'pending' first, and we don't want to leave users
    hanging on a delayed signal. Any community question the user submitted
    counts, regardless of status.
    """
    return (
        db.query(Question)
        .filter(Question.submitted_by == uid, Question.source == "community")
        .limit(1)
        .count()
        >= 1
    )


def _community_approved_count(uid: UUID, db: Session) -> int:
    return (
        db.query(func.count(Question.id))
        .filter(
            Question.submitted_by == uid,
            Question.source == "community",
            Question.status == "approved",
        )
        .scalar()
        or 0
    )


def _p_community_star(uid: UUID, db: Session, _ctx: dict) -> bool:
    return _community_approved_count(uid, db) >= 5


def _p_community_legend(uid: UUID, db: Session, _ctx: dict) -> bool:
    return _community_approved_count(uid, db) >= 20


# ── Roadmap achievements ────────────────────────────────────────────

def _p_roadmap_first_task(uid: UUID, db: Session, _ctx: dict) -> bool:
    return (
        db.query(RoadmapTask)
        .join(RoadmapStage, RoadmapStage.id == RoadmapTask.stage_id)
        .join(UserRoadmap, UserRoadmap.id == RoadmapStage.roadmap_id)
        .filter(UserRoadmap.user_id == uid, RoadmapTask.is_completed.is_(True))
        .limit(1)
        .count()
        >= 1
    )


def _p_roadmap_pathfinder(uid: UUID, db: Session, _ctx: dict) -> bool:
    """Pathfinder = at least one fully-completed stage."""
    return (
        db.query(RoadmapStage)
        .join(UserRoadmap, UserRoadmap.id == RoadmapStage.roadmap_id)
        .filter(UserRoadmap.user_id == uid, RoadmapStage.is_completed.is_(True))
        .limit(1)
        .count()
        >= 1
    )


# ── Meta achievements ───────────────────────────────────────────────

def _p_meta_bilingual(uid: UUID, db: Session, ctx: dict) -> bool:
    """
    Bilingual = switched language mid-active-session. The trigger endpoint
    enforces the "during an interview" check and only fires when appropriate,
    so by the time we get here, the act itself is the qualifier.
    """
    return bool(ctx.get("during_active_session"))


def _p_meta_jrs_gold(uid: UUID, db: Session, _ctx: dict) -> bool:
    """
    Gold Standard: JRS (Job-Readiness Score) >= 80. JRS isn't a persisted
    column today — we approximate with the user's best interview total_score
    combined with their best CV ats_score, weighted 60/40.
    """
    best_interview = (
        db.query(func.max(InterviewSession.total_score))
        .filter(
            InterviewSession.user_id == uid,
            InterviewSession.phase.in_(("finished", "outro")),
        )
        .scalar()
    ) or 0
    best_ats = (
        db.query(func.max(CVEvaluation.ats_score))
        .join(CVDocument, CVDocument.id == CVEvaluation.cv_id)
        .filter(CVDocument.user_id == uid)
        .scalar()
    ) or 0
    jrs = int(0.6 * best_interview + 0.4 * best_ats)
    return jrs >= 80


def _p_meta_platinum_10(uid: UUID, db: Session, _ctx: dict) -> bool:
    """
    Platinum: 10 OTHER achievements unlocked. We check the count BEFORE the
    current trigger's awards land (they haven't been committed yet), so the
    user needs to have already accumulated 10 to qualify on the same trigger.
    In practice this fires on the trigger AFTER hitting 10.
    """
    return (
        db.query(func.count(UserAchievement.id))
        .filter(UserAchievement.user_id == uid)
        .scalar()
        or 0
    ) >= 10


# ─────────────────────────────────────────────────────────────────────
#  Predicate registry (key → callable). Order in the catalog is decoupled —
#  this is just the dispatcher.
# ─────────────────────────────────────────────────────────────────────

_PREDICATES = {
    # interview
    "interview_first":          _p_interview_first,
    "interview_5":              _p_interview_5,
    "interview_10":             _p_interview_10,
    "interview_50":             _p_interview_50,
    "interview_score_90":       _p_interview_score_90,
    "interview_perfect_100":    _p_interview_perfect_100,
    "interview_weekly_streak":  _p_interview_weekly_streak,
    "interview_rapid_fire":     _p_interview_rapid_fire,
    "interview_night_owl":      _p_interview_night_owl,
    # cv
    "cv_first_upload":          _p_cv_first_upload,
    "cv_ats_80":                _p_cv_ats_80,
    "cv_polished":              _p_cv_polished,
    # community
    "community_first":          _p_community_first,
    "community_star":           _p_community_star,
    "community_legend":         _p_community_legend,
    # roadmap
    "roadmap_first_task":       _p_roadmap_first_task,
    "roadmap_pathfinder":       _p_roadmap_pathfinder,
    # meta
    "meta_bilingual":           _p_meta_bilingual,
    "meta_jrs_gold":            _p_meta_jrs_gold,
    "meta_platinum_10":         _p_meta_platinum_10,
}


# ─────────────────────────────────────────────────────────────────────
#  Serialization helper — shared with the router so frontend gets a
#  consistent shape from both inline new_achievements and /achievements/me.
# ─────────────────────────────────────────────────────────────────────

def _serialize(ua: UserAchievement) -> dict:
    a = ua.achievement
    return {
        "id": str(a.id),
        "user_achievement_id": str(ua.id),
        "key": a.key,
        "title_en": a.title_en,
        "title_ar": a.title_ar,
        "description_en": a.description_en,
        "description_ar": a.description_ar,
        "icon": a.icon,
        "tier": a.tier,
        "category": a.category,
        "is_secret": a.is_secret,
        "earned_at": ua.earned_at.isoformat() if ua.earned_at else None,
        "seen": ua.seen,
    }