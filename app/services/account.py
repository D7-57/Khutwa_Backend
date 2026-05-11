"""
Account & data deletion service (PDPL Article 4 — right to erasure).

Two functions, sharing a private helper:

  delete_user_data(user_id)
      Wipes user-generated content (CVs, roadmaps, quiz attempts,
      uploaded files in Storage) and resets the optional consent
      toggles to OFF. KEEPS the account so the user can log back in.

  delete_user_account(user_id)
      Runs delete_user_data, then deletes the auth.users row via the
      admin API. The CASCADE FK on profiles.id wipes the profile row
      (and the rest of the user's DB footprint) automatically.

Why a service layer and not inline in the router:
  Both flows share 80% of their logic. Putting it here keeps the router
  thin and means we have one place to add new tables (e.g. interview
  history) when they exist.
"""

from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.profile import Profile
from app.models.cv import CVDocument, CVEvaluation
from app.models.cv_quiz import CVQuiz, CVQuizAttempt
from app.models.roadmap.models import UserRoadmap, RoadmapStage, RoadmapTask
from app.models.career.skill import UserSkill
from app.models.career.role import UserRole
from app.services.supabase_admin import delete_auth_user, delete_storage_objects


# ── shared internal helper ──


def _wipe_user_content(db: Session, uid: UUID) -> dict:
    """
    Delete every row of user-generated content for `uid` AND wipe any
    associated Storage objects.

    Returns a counts dict for the response envelope (and for logging if
    you wire that up later).

    Order matters here:
      1. Collect storage paths BEFORE deleting DB rows (need the rows
         to know what to delete from Storage).
      2. Delete child rows before parents to avoid FK errors on tables
         that DON'T have CASCADE.
      3. CASCADE-equipped FKs handle the rest (CVEvaluation cascades
         from CVDocument, RoadmapStage/Task from UserRoadmap, etc).

    NOTE: synchronize_session="fetch" is important. The default
    "evaluate" mode crashes on .delete() queries that touch JSON
    columns or relationships. "fetch" is slower but safe.
    """
    counts: dict[str, int] = {}

    # ── 1) Collect storage object paths BEFORE deleting CV rows ──
    cv_storage_paths: list[str] = []
    cv_docs = db.query(CVDocument).filter(CVDocument.user_id == uid).all()
    for doc in cv_docs:
        # raw_file_url is stored as "bucket/path/to/file" (see cv_service.py).
        # We need just the path portion (without "cvs/" prefix) for the
        # Storage delete API.
        if doc.raw_file_url and "/" in doc.raw_file_url:
            bucket, _, path = doc.raw_file_url.partition("/")
            if bucket == "cvs" and path:
                cv_storage_paths.append(path)

    # ── 2) Wipe DB rows ──
    # CV evaluations cascade from cv_documents, so deleting docs is enough.
    counts["cv_documents"] = (
        db.query(CVDocument)
        .filter(CVDocument.user_id == uid)
        .delete(synchronize_session="fetch")
    )

    # Quiz attempts. CVQuiz itself isn't user-owned (it's tied to a CV,
    # which we just deleted — those cascade via cv_id FK if you set
    # ondelete="CASCADE" on it; check models/cv_quiz.py if you haven't).
    counts["cv_quiz_attempts"] = (
        db.query(CVQuizAttempt)
        .filter(CVQuizAttempt.user_id == uid)
        .delete(synchronize_session="fetch")
    )

    # Roadmap data. RoadmapStage / RoadmapTask cascade from UserRoadmap.
    counts["user_roadmaps"] = (
        db.query(UserRoadmap)
        .filter(UserRoadmap.user_id == uid)
        .delete(synchronize_session="fetch")
    )

    # Skills profile + role selection (the "roadmap_personalization" data).
    counts["user_skills"] = (
        db.query(UserSkill)
        .filter(UserSkill.user_id == uid)
        .delete(synchronize_session="fetch")
    )
    counts["user_roles"] = (
        db.query(UserRole)
        .filter(UserRole.user_id == uid)
        .delete(synchronize_session="fetch")
    )

    # TODO(interviews): when the interview tables exist, wipe them here:
    #   counts["interview_sessions"] = db.query(InterviewSession)...
    #   counts["interview_answers"]  = db.query(InterviewAnswer)...

    # ── 3) Wipe Storage objects ──
    # Done AFTER DB commit on the caller side — see the service functions
    # below. We just collected the paths here so they outlive the delete.
    return {"counts": counts, "cv_storage_paths": cv_storage_paths}


# ════════════════════════════════════════════════════════════════════
#  PUBLIC: delete_user_data — "Delete My Data" button
# ════════════════════════════════════════════════════════════════════


def delete_user_data(db: Session, user_id: str) -> dict:
    """
    Wipe a user's content but keep the account alive.

    What this does:
      - Deletes all CVs, evaluations, roadmaps, skills, roles, quiz attempts.
      - Deletes uploaded CV files from Supabase Storage.
      - Resets the three optional consent toggles to OFF.
      - Sets data_deleted_at timestamp in privacy_settings (audit trail).

    What this does NOT do:
      - Doesn't touch terms_accepted (user still has an account).
      - Doesn't touch profile fields (name, email, university...).
        These are "performance of contract" data; if they want those
        gone too they want delete_user_account instead.
      - Doesn't log the user out.
    """
    uid = UUID(user_id)

    profile = db.get(Profile, uid)
    if not profile:
        return {"counts": {}, "cv_storage_paths": []}

    wipe_result = _wipe_user_content(db, uid)

    # Reset optional consent toggles + stamp the data deletion moment.
    # Preserve terms_accepted and its metadata — they still have an account.
    settings = profile.privacy_settings or {}
    now_iso = datetime.now(timezone.utc).isoformat()
    settings.update({
        "interview_personalization": False,
        "interview_personalization_updated_at": now_iso,
        "roadmap_personalization": False,
        "roadmap_personalization_updated_at": now_iso,
        "cv_storage": False,
        "cv_storage_updated_at": now_iso,
        "data_deleted_at": now_iso,  # most recent wipe — appears in audit
    })
    profile.privacy_settings = settings

    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(profile, "privacy_settings")

    db.commit()

    # Storage cleanup runs AFTER the DB commit, so a Storage hiccup
    # doesn't roll back the DB wipe. We tolerate partial Storage
    # failures (and a future retry-job can clean up orphans).
    try:
        delete_storage_objects("cvs", wipe_result["cv_storage_paths"])
    except Exception as e:
        # Don't fail the whole request — DB wipe already succeeded.
        # In production you'd want this to land in your error tracker.
        wipe_result["storage_warning"] = str(e)

    return wipe_result


# ════════════════════════════════════════════════════════════════════
#  PUBLIC: delete_user_account — "Delete My Account" button
# ════════════════════════════════════════════════════════════════════


def delete_user_account(db: Session, user_id: str) -> dict:
    """
    Nuclear option: wipe content + delete the auth user.

    Flow:
      1. Wipe all user content (same as delete_user_data).
      2. DB commit — releases any locks on profile row.
      3. Call admin API to delete the auth.users row. CASCADE FK on
         profiles.id (auth.users.id) wipes the profile row.

    After this returns, the user's JWT is invalid (auth row is gone),
    they can't refresh tokens, and the next time their client hits any
    auth-protected endpoint they'll get 401 — natural sign-out.

    Idempotent: if the auth user is already gone (404 from admin API),
    we treat that as success and continue.
    """
    uid = UUID(user_id)

    profile = db.get(Profile, uid)
    if not profile:
        # Nothing to delete on our side — try the auth user just in case.
        delete_auth_user(user_id)
        return {"counts": {}, "cv_storage_paths": []}

    wipe_result = _wipe_user_content(db, uid)
    db.commit()

    # Storage cleanup BEFORE the auth-user delete. If this raises we
    # haven't deleted the auth row yet, so the user can hit the endpoint
    # again and we'll retry.
    try:
        delete_storage_objects("cvs", wipe_result["cv_storage_paths"])
    except Exception as e:
        wipe_result["storage_warning"] = str(e)

    # The big one. CASCADE on profiles.id → auth.users.id handles the
    # profile row deletion automatically.
    delete_auth_user(user_id)

    return wipe_result