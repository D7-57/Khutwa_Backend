"""
Roadmap generation service.

Supports up to MAX_ROADMAPS_PER_USER (3) roadmaps per user.
Each roadmap is for a specific role — one roadmap per role.
"""

import json
import re
import uuid
from datetime import datetime, timezone
from uuid import UUID

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.profile import Profile
from app.models.career.role import Role, UserRole
from app.models.career.skill import Skill, UserSkill
from app.models.career.role_skill import RoleSkill
from app.models.roadmap.models import (
    RoadmapTemplate,
    UserRoadmap,
    RoadmapStage,
    RoadmapTask,
)
from app.services.roadmap.prompts import (
    ROADMAP_SYSTEM_PROMPT,
    build_roadmap_prompt,
)

client = OpenAI(api_key=settings.OPENAI_API_KEY)

MAX_ROADMAPS_PER_USER = 3


# ────────────────────────────────────────────────────────────
#  PUBLIC API
# ────────────────────────────────────────────────────────────

def get_user_roadmaps(user_id: UUID, db: Session) -> list[UserRoadmap]:
    """Fetch all of the user's roadmaps, newest first."""
    return (
        db.query(UserRoadmap)
        .filter(UserRoadmap.user_id == user_id)
        .order_by(UserRoadmap.created_at.desc())
        .all()
    )


def get_user_roadmap(user_id: UUID, db: Session, roadmap_id: UUID | None = None) -> UserRoadmap | None:
    """Fetch a specific roadmap, or the most recent one."""
    if roadmap_id:
        rm = db.get(UserRoadmap, roadmap_id)
        if rm and rm.user_id == user_id:
            return rm
        return None
    return (
        db.query(UserRoadmap)
        .filter(UserRoadmap.user_id == user_id)
        .order_by(UserRoadmap.created_at.desc())
        .first()
    )


def get_roadmap_full(roadmap: UserRoadmap, db: Session) -> dict:
    """Load a roadmap with all its stages and tasks, return as dict."""
    stages = (
        db.query(RoadmapStage)
        .filter(RoadmapStage.roadmap_id == roadmap.id)
        .order_by(RoadmapStage.order)
        .all()
    )

    stage_ids = [s.id for s in stages]
    tasks = (
        db.query(RoadmapTask)
        .filter(RoadmapTask.stage_id.in_(stage_ids))
        .order_by(RoadmapTask.order)
        .all()
    ) if stage_ids else []

    tasks_by_stage: dict[UUID, list] = {}
    for t in tasks:
        tasks_by_stage.setdefault(t.stage_id, []).append(t)

    role_name = None
    if roadmap.role_id:
        role = db.get(Role, roadmap.role_id)
        if role:
            role_name = role.name

    return {
        "id": roadmap.id,
        "title": roadmap.title,
        "title_ar": roadmap.title_ar,
        "role_id": roadmap.role_id,
        "role_name": role_name,
        "source": roadmap.source,
        "is_ai_generated": roadmap.is_ai_generated,
        "overall_progress": roadmap.overall_progress,
        "created_at": roadmap.created_at,
        "stages": [
            {
                "id": s.id,
                "order": s.order,
                "title": s.title,
                "title_ar": s.title_ar,
                "description": s.description,
                "description_ar": s.description_ar,
                "is_unlocked": s.is_unlocked,
                "is_completed": s.is_completed,
                "progress": s.progress,
                "tasks": [
                    {
                        "id": t.id,
                        "order": t.order,
                        "title": t.title,
                        "title_ar": t.title_ar,
                        "description": t.description,
                        "description_ar": t.description_ar,
                        "skill_name": t.skill_name,
                        "resources": t.resources or [],
                        "is_completed": t.is_completed,
                        "completed_at": t.completed_at,
                    }
                    for t in tasks_by_stage.get(s.id, [])
                ],
            }
            for s in stages
        ],
    }


def generate_roadmap(
    user_id: UUID,
    db: Session,
    *,
    role_id_override: UUID | None = None,
    force_ai: bool = False,
    language: str = "en",
) -> dict:
    """
    Generate a roadmap for the user.
    - Max 3 roadmaps per user.
    - One roadmap per role — if a roadmap for this role already exists, replace it.
    """
    profile = db.get(Profile, user_id)
    if not profile:
        raise ValueError("Profile not found")

    # ── Resolve target role ─────────────────────────────
    role, role_id = _resolve_role(user_id, db, role_id_override)
    if not role:
        raise ValueError(
            "No role selected. Please pick a role first via /career/roles/me/selected."
        )

    # ── Delete existing roadmap for THIS role (if any) ──
    _delete_roadmap_for_role(user_id, role.id, db)

    # ── Enforce max 3: if at limit, delete oldest ───────
    existing = get_user_roadmaps(user_id, db)
    if len(existing) >= MAX_ROADMAPS_PER_USER:
        oldest = existing[-1]  # list is newest-first, so last = oldest
        _delete_single_roadmap(oldest, db)

    # ── Decide strategy ─────────────────────────────────
    existing_skills, gap_skills, existing_names, gap_names = _compute_skill_gap(
        user_id, role.id, db,
    )

    template = (
        db.query(RoadmapTemplate)
        .filter(RoadmapTemplate.role_id == role.id)
        .first()
    )

    if force_ai or (gap_names and not template):
        roadmap_data = _generate_with_ai(
            role=role,
            profile=profile,
            existing_names=existing_names,
            gap_names=gap_names,
            language=language,
        )
        source = "ai"
        is_ai = True
    elif template and gap_names:
        roadmap_data = _personalize_template(template, existing_names)
        source = "personalized_template"
        is_ai = False
    elif template:
        roadmap_data = template.stages_json
        source = "template"
        is_ai = False
    else:
        roadmap_data = _generate_with_ai(
            role=role,
            profile=profile,
            existing_names=existing_names,
            gap_names=gap_names,
            language=language,
        )
        source = "ai"
        is_ai = True

    # ── Persist to DB ───────────────────────────────────
    title = roadmap_data.get("title", f"{role.name} Roadmap")
    title_ar = roadmap_data.get("title_ar")
    roadmap = _persist_roadmap(
        user_id=user_id,
        role_id=role.id,
        title=title,
        title_ar=title_ar,
        source=source,
        is_ai=is_ai,
        stages_data=roadmap_data.get("stages", []),
        db=db,
    )

    db.commit()
    db.refresh(roadmap)

    return {
        "roadmap": get_roadmap_full(roadmap, db),
        "source": source,
        "skill_gap": gap_names,
        "skills_matched": existing_names,
    }


def delete_roadmap_by_id(user_id: UUID, roadmap_id: UUID, db: Session):
    """Delete a specific roadmap belonging to the user."""
    rm = db.get(UserRoadmap, roadmap_id)
    if not rm or rm.user_id != user_id:
        raise ValueError("Roadmap not found or not yours")
    _delete_single_roadmap(rm, db)
    db.commit()


def complete_task(user_id: UUID, task_id: UUID, db: Session) -> dict:
    """Mark a task as completed and recalculate progress."""
    task = db.get(RoadmapTask, task_id)
    if not task:
        raise ValueError("Task not found")

    stage = db.get(RoadmapStage, task.stage_id)
    if not stage:
        raise ValueError("Stage not found")

    roadmap = db.get(UserRoadmap, stage.roadmap_id)
    if not roadmap or roadmap.user_id != user_id:
        raise ValueError("Roadmap not found or not yours")

    if not stage.is_unlocked:
        raise ValueError("This stage is locked. Complete previous stages first.")

    task.is_completed = True
    task.completed_at = datetime.now(timezone.utc)

    all_tasks = (
        db.query(RoadmapTask)
        .filter(RoadmapTask.stage_id == stage.id)
        .all()
    )
    completed = sum(1 for t in all_tasks if t.is_completed)
    stage.progress = round(completed / len(all_tasks) * 100, 1) if all_tasks else 0

    stage_completed = completed == len(all_tasks)
    stage.is_completed = stage_completed

    next_stage_unlocked = False
    if stage_completed:
        next_stage = (
            db.query(RoadmapStage)
            .filter(
                RoadmapStage.roadmap_id == roadmap.id,
                RoadmapStage.order == stage.order + 1,
            )
            .first()
        )
        if next_stage and not next_stage.is_unlocked:
            next_stage.is_unlocked = True
            next_stage_unlocked = True

    all_stages = (
        db.query(RoadmapStage)
        .filter(RoadmapStage.roadmap_id == roadmap.id)
        .all()
    )
    if all_stages:
        roadmap.overall_progress = round(
            sum(s.progress for s in all_stages) / len(all_stages), 1,
        )

    db.commit()

    return {
        "task_id": task.id,
        "stage_progress": stage.progress,
        "overall_progress": roadmap.overall_progress,
        "stage_completed": stage_completed,
        "next_stage_unlocked": next_stage_unlocked,
    }


def uncomplete_task(user_id: UUID, task_id: UUID, db: Session) -> dict:
    """Undo task completion."""
    task = db.get(RoadmapTask, task_id)
    if not task:
        raise ValueError("Task not found")

    stage = db.get(RoadmapStage, task.stage_id)
    if not stage:
        raise ValueError("Stage not found")

    roadmap = db.get(UserRoadmap, stage.roadmap_id)
    if not roadmap or roadmap.user_id != user_id:
        raise ValueError("Roadmap not found or not yours")

    task.is_completed = False
    task.completed_at = None

    all_tasks = (
        db.query(RoadmapTask)
        .filter(RoadmapTask.stage_id == stage.id)
        .all()
    )
    completed = sum(1 for t in all_tasks if t.is_completed)
    stage.progress = round(completed / len(all_tasks) * 100, 1) if all_tasks else 0
    stage.is_completed = False

    all_stages = (
        db.query(RoadmapStage)
        .filter(RoadmapStage.roadmap_id == roadmap.id)
        .all()
    )
    if all_stages:
        roadmap.overall_progress = round(
            sum(s.progress for s in all_stages) / len(all_stages), 1,
        )

    db.commit()

    return {
        "task_id": task.id,
        "stage_progress": stage.progress,
        "overall_progress": roadmap.overall_progress,
        "stage_completed": False,
        "next_stage_unlocked": False,
    }


# ────────────────────────────────────────────────────────────
#  PRIVATE HELPERS
# ────────────────────────────────────────────────────────────

def _resolve_role(
    user_id: UUID, db: Session, override: UUID | None,
) -> tuple[Role | None, UUID | None]:
    if override:
        role = db.get(Role, override)
        return role, override

    primary = (
        db.query(UserRole)
        .filter(UserRole.user_id == user_id, UserRole.is_primary == True)
        .first()
    )
    if not primary:
        any_role = (
            db.query(UserRole)
            .filter(UserRole.user_id == user_id)
            .first()
        )
        if not any_role:
            return None, None
        role = db.get(Role, any_role.role_id)
        return role, any_role.role_id

    role = db.get(Role, primary.role_id)
    return role, primary.role_id


def _compute_skill_gap(
    user_id: UUID, role_id: UUID, db: Session,
) -> tuple[list, list, list[str], list[str]]:
    required = (
        db.query(RoleSkill)
        .filter(RoleSkill.role_id == role_id)
        .all()
    )
    user_skills = (
        db.query(UserSkill)
        .filter(UserSkill.user_id == user_id)
        .all()
    )
    user_skill_ids = {us.skill_id for us in user_skills}

    existing = [rs for rs in required if rs.skill_id in user_skill_ids]
    gap = [rs for rs in required if rs.skill_id not in user_skill_ids]

    existing_names = []
    for rs in existing:
        skill = db.get(Skill, rs.skill_id)
        if skill:
            existing_names.append(skill.name)

    gap_names = []
    for rs in gap:
        skill = db.get(Skill, rs.skill_id)
        if skill:
            gap_names.append(skill.name)

    return existing, gap, existing_names, gap_names


def _delete_single_roadmap(rm: UserRoadmap, db: Session):
    """Delete one roadmap and its stages/tasks."""
    stages = (
        db.query(RoadmapStage)
        .filter(RoadmapStage.roadmap_id == rm.id)
        .all()
    )
    for s in stages:
        db.query(RoadmapTask).filter(RoadmapTask.stage_id == s.id).delete()
        db.delete(s)
    db.delete(rm)
    db.flush()


def _delete_roadmap_for_role(user_id: UUID, role_id: UUID, db: Session):
    """Delete existing roadmap for a specific role (if any)."""
    existing = (
        db.query(UserRoadmap)
        .filter(UserRoadmap.user_id == user_id, UserRoadmap.role_id == role_id)
        .all()
    )
    for rm in existing:
        _delete_single_roadmap(rm, db)


def _generate_with_ai(
    role: Role,
    profile: Profile,
    existing_names: list[str],
    gap_names: list[str],
    language: str = "en",
) -> dict:
    profile_context = {}
    if profile.major:
        profile_context["major"] = profile.major
    if profile.university:
        profile_context["university"] = profile.university
    if profile.current_status:
        profile_context["current_status"] = profile.current_status
    if profile.graduation_year:
        profile_context["graduation_year"] = profile.graduation_year

    user_prompt = build_roadmap_prompt(
        role_name=role.name,
        existing_skills=existing_names,
        gap_skills=gap_names if gap_names else [f"Core skills for {role.name}"],
        profile_context=profile_context or None,
        language=language,
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": ROADMAP_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
            timeout=45,
        )
    except Exception as e:
        raise RuntimeError(f"OpenAI API call failed: {e}") from e

    content = resp.choices[0].message.content or "{}"

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
        else:
            raise RuntimeError("Failed to parse AI roadmap response")

    return data


def _personalize_template(
    template: RoadmapTemplate,
    existing_skill_names: list[str],
) -> dict:
    data = template.stages_json.copy()
    existing_lower = {s.lower() for s in existing_skill_names}

    stages = data.get("stages", [])
    filtered_stages = []

    for stage in stages:
        tasks = stage.get("tasks", [])
        remaining_tasks = [
            t for t in tasks
            if not t.get("skill_name")
            or t["skill_name"].lower() not in existing_lower
        ]

        if remaining_tasks:
            stage = {**stage, "tasks": remaining_tasks}
            for i, t in enumerate(stage["tasks"], 1):
                t["order"] = i
            filtered_stages.append(stage)

    for i, s in enumerate(filtered_stages, 1):
        s["order"] = i

    data["stages"] = filtered_stages
    return data


def _persist_roadmap(
    user_id: UUID,
    role_id: UUID,
    title: str,
    title_ar: str | None,
    source: str,
    is_ai: bool,
    stages_data: list[dict],
    db: Session,
) -> UserRoadmap:
    roadmap = UserRoadmap(
        user_id=user_id,
        role_id=role_id,
        title=title,
        title_ar=title_ar,
        source=source,
        is_ai_generated=is_ai,
        overall_progress=0.0,
    )
    db.add(roadmap)
    db.flush()

    for stage_data in stages_data:
        stage = RoadmapStage(
            roadmap_id=roadmap.id,
            order=stage_data.get("order", 0),
            title=stage_data.get("title", "Untitled Stage"),
            title_ar=stage_data.get("title_ar"),
            description=stage_data.get("description"),
            description_ar=stage_data.get("description_ar"),
            is_unlocked=(stage_data.get("order", 0) == 1),
            is_completed=False,
            progress=0.0,
        )
        db.add(stage)
        db.flush()

        for task_data in stage_data.get("tasks", []):
            task = RoadmapTask(
                stage_id=stage.id,
                order=task_data.get("order", 0),
                title=task_data.get("title", "Untitled Task"),
                title_ar=task_data.get("title_ar"),
                description=task_data.get("description"),
                description_ar=task_data.get("description_ar"),
                skill_name=task_data.get("skill_name"),
                resources=task_data.get("resources", []),
                is_completed=False,
            )
            db.add(task)

    db.flush()
    return roadmap
