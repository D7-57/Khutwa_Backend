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
from sqlalchemy import func
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

# Role-aware standard certification shortlist used to guide AI suggestions.
# We keep this concise and recognizable across hiring markets.
STANDARD_CERTS_BY_ROLE_KEYWORD: dict[str, list[str]] = {
    "siem": [
        "SC-200 (Microsoft Security Operations Analyst)",
        "CompTIA CySA+",
        "Splunk Core Certified User",
        "Elastic Certified Analyst",
    ],
    "blue team": [
        "BTL1 (Blue Team Level 1)",
        "eCIR",
        "CompTIA CySA+",
        "SC-200 (Microsoft Security Operations Analyst)",
    ],
    "incident": [
        "eCIR",
        "GCFA (GIAC Certified Forensic Analyst)",
        "BTL1 (Blue Team Level 1)",
        "SC-200 (Microsoft Security Operations Analyst)",
    ],
    "threat": [
        "SC-200 (Microsoft Security Operations Analyst)",
        "BTL1 (Blue Team Level 1)",
        "CompTIA CySA+",
    ],
    "pentest": [
        "eJPT",
        "PNPT",
        "OSCP",
        "CompTIA PenTest+",
    ],
    "red team": [
        "PNPT",
        "OSCP",
        "CRTO (Certified Red Team Operator)",
    ],
    "soc": [
        "CompTIA Security+",
        "eJPT",
        "BTL1 (Blue Team Level 1)",
        "eCIR",
        "CompTIA CySA+",
        "SC-200 (Microsoft Security Operations Analyst)",
    ],
    "cyber": [
        "CompTIA Security+",
        "eJPT",
        "BTL1 (Blue Team Level 1)",
        "eCIR",
        "CompTIA CySA+",
        "PNPT",
        "OSCP",
        "SC-200 (Microsoft Security Operations Analyst)",
    ],
    "security": [
        "CompTIA Security+",
        "eJPT",
        "BTL1 (Blue Team Level 1)",
        "eCIR",
        "CompTIA CySA+",
        "PNPT",
        "OSCP",
        "SC-200 (Microsoft Security Operations Analyst)",
    ],
    "cloud": [
        "AWS Certified Solutions Architect – Associate",
        "AWS Certified Developer – Associate",
        "AZ-104 (Azure Administrator Associate)",
        "AZ-305 (Azure Solutions Architect Expert)",
        "Google Professional Cloud Architect",
        "CKA (Certified Kubernetes Administrator)",
    ],
    "devops": [
        "AWS Certified DevOps Engineer – Professional",
        "Docker Certified Associate",
        "CKA (Certified Kubernetes Administrator)",
        "HashiCorp Terraform Associate",
        "AZ-400 (Designing and Implementing Microsoft DevOps Solutions)",
    ],
    "data": [
        "PL-300 (Microsoft Power BI Data Analyst)",
        "DP-203 (Azure Data Engineer Associate)",
        "AWS Certified Data Engineer – Associate",
        "Google Professional Data Engineer",
        "Databricks Certified Data Engineer Associate",
    ],
    "analytics": [
        "PL-300 (Microsoft Power BI Data Analyst)",
        "Google Data Analytics Professional Certificate",
        "Tableau Certified Data Analyst",
    ],
    "software": [
        "AWS Certified Developer – Associate",
        "AZ-204 (Azure Developer Associate)",
        "Oracle Certified Professional: Java SE",
        "PCAP (Certified Associate in Python Programming)",
    ],
    "network": [
        "Cisco CCNA",
        "Cisco CCNP Enterprise",
        "CompTIA Network+",
    ],
    "product": [
        "PSPO I (Professional Scrum Product Owner)",
        "CSPO (Certified Scrum Product Owner)",
        "Pragmatic Institute Product Certifications",
    ],
    "project": [
        "PMP (Project Management Professional)",
        "CAPM (Certified Associate in Project Management)",
        "PRINCE2 Practitioner",
    ],
}

# Skill-level cert guidance (cross-role). This helps map specific gaps
# like "threat hunting" to relevant professional certs.
STANDARD_CERTS_BY_SKILL_KEYWORD: dict[str, list[str]] = {
    "threat hunting": [
        "eCTHP (Certified Threat Hunting Professional)",
        "BTL1 (Blue Team Level 1)",
        "SC-200 (Microsoft Security Operations Analyst)",
    ],
    "incident response": [
        "eCIR",
        "GCFA (GIAC Certified Forensic Analyst)",
        "SC-200 (Microsoft Security Operations Analyst)",
    ],
    "siem": [
        "SC-200 (Microsoft Security Operations Analyst)",
        "Splunk Core Certified User",
        "Elastic Certified Analyst",
    ],
    "digital forensics": [
        "GCFA (GIAC Certified Forensic Analyst)",
        "CHFI (Computer Hacking Forensic Investigator)",
    ],
    "cloud security": [
        "CCSP (Certified Cloud Security Professional)",
        "AZ-500 (Azure Security Engineer Associate)",
        "AWS Certified Security – Specialty",
    ],
    "machine learning": [
        "TensorFlow Developer Certificate",
        "AWS Certified Machine Learning – Specialty",
    ],
    "data engineering": [
        "DP-203 (Azure Data Engineer Associate)",
        "Google Professional Data Engineer",
        "Databricks Certified Data Engineer Associate",
    ],
    "project management": [
        "PMP (Project Management Professional)",
        "CAPM (Certified Associate in Project Management)",
    ],
    "business analysis": [
        "CBAP (Certified Business Analysis Professional)",
        "PMI-PBA (Professional in Business Analysis)",
    ],
}

# Alias map for certification matching so we don't re-suggest an already
# earned cert just because of formatting differences.
CERT_ALIAS_MAP: dict[str, set[str]] = {
    "CompTIA Security+": {"security+", "sec+", "comptia security+"},
    "eJPT": {"ejpt", "ejptv2", "elearn ejpt", "e jpt"},
    "BTL1 (Blue Team Level 1)": {"btl1", "blue team level 1", "security blue team level 1"},
    "eCIR": {"ecir", "e cir", "ine ecir"},
    "CompTIA CySA+": {"cysa+", "comptia cysa+", "cybersecurity analyst+"},
    "SC-200 (Microsoft Security Operations Analyst)": {"sc-200", "microsoft sc-200"},
    "CompTIA PenTest+": {"pentest+", "comptia pentest+", "pt0-002"},
    "GCFA (GIAC Certified Forensic Analyst)": {"gcfa", "giac forensic analyst"},
    "CRTO (Certified Red Team Operator)": {"crto", "certified red team operator"},
    "Splunk Core Certified User": {"splunk core certified user", "splunk core user"},
    "Elastic Certified Analyst": {"elastic certified analyst", "elastic analyst"},
    "eCTHP (Certified Threat Hunting Professional)": {
        "ecthp",
        "e cthp",
        "certified threat hunting professional",
    },
    "CHFI (Computer Hacking Forensic Investigator)": {
        "chfi",
        "computer hacking forensic investigator",
    },
    "CCSP (Certified Cloud Security Professional)": {"ccsp"},
    "AZ-500 (Azure Security Engineer Associate)": {"az-500", "azure security engineer associate"},
    "AWS Certified Security – Specialty": {"aws certified security specialty", "aws security specialty"},
    "TensorFlow Developer Certificate": {"tensorflow developer certificate"},
    "CBAP (Certified Business Analysis Professional)": {"cbap"},
    "PMI-PBA (Professional in Business Analysis)": {"pmi-pba", "pmi pba"},
}


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
        # Per-roadmap generation context — surfaced so the UI can show
        # a "Focused on: X" badge and pre-fill the Regenerate sheet.
        "skill_focus": roadmap.skill_focus,
        "include_tangible_outcome": roadmap.include_tangible_outcome,
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
    # ── Task 1: Custom Skill Input ──────────────────────────────────────
    skill_focus: str | None = None,
    # ── Task 5: Tangible Outcomes ───────────────────────────────────────
    include_tangible_outcome: bool = False,
) -> dict:
    """
    Generate a roadmap for the user.
    - Max 3 roadmaps per user.
    - One roadmap per role — if a roadmap for this role already exists, replace it.

    Privacy gating (PDPL):
      If profile.privacy_settings.roadmap_personalization is OFF, the
      user has not consented to skill-derived personalization. We:
        - DO NOT query UserSkill (no skill-gap computation)
        - DO NOT summarize previous roadmaps (no behavioural inference)
        - Still respect role + skill_focus + include_tangible_outcome
          (these are explicit per-request inputs, not derived data)
      This is the "soft gate" — generation still works, just with
      less context. Users see a working app instead of a 403.
    """
    profile = db.get(Profile, user_id)
    if not profile:
        raise ValueError("Profile not found")

    # ── PDPL: check roadmap_personalization consent ─────────────────────
    privacy_settings = profile.privacy_settings or {}
    personalize = bool(privacy_settings.get("roadmap_personalization"))

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

    # ── Skill-gap analysis (privacy-gated) ──────────────
    if personalize:
        existing_skills, gap_skills, existing_names, gap_names = (
            _compute_skill_gap(user_id, role.id, db)
        )
        # Task 4: also gather what previous roadmaps covered (skills
        # AND specific task titles, for sharper dedup).
        previously_covered, previously_covered_titles = (
            _summarize_previous_roadmaps(user_id, role.id, db)
        )
    else:
        # No personalization — pretend the user has no recorded skills
        # and no roadmap history. Generation falls back to "everything
        # needed for the role" + whatever the user explicitly typed
        # into skill_focus.
        existing_skills, gap_skills, existing_names, gap_names = [], [], [], []
        previously_covered = []
        previously_covered_titles = []

    template = (
        db.query(RoadmapTemplate)
        .filter(RoadmapTemplate.role_id == role.id)
        .first()
    )

    # When the user provided an explicit skill_focus OR asked for a
    # tangible outcome, we ALWAYS go AI — templates can't honor those.
    user_provided_extras = bool(
        (skill_focus and skill_focus.strip()) or include_tangible_outcome
    )

    # Personalization requirement:
    # If the user has profile level signals (experience/certs/work history),
    # prefer AI so roadmap depth matches their level instead of static template.
    has_level_signals = bool(
        profile.years_of_experience
        or profile.current_status
        or (profile.certifications and len(profile.certifications) > 0)
        or (profile.experiences and len(profile.experiences) > 0)
    )
    prefer_ai_personalized = has_level_signals

    if (
        force_ai
        or user_provided_extras
        or prefer_ai_personalized
        or (gap_names and not template)
    ):
        roadmap_data = _generate_with_ai(
            role=role,
            profile=profile,
            existing_names=existing_names,
            gap_names=gap_names,
            language=language,
            skill_focus=skill_focus,
            include_tangible_outcome=include_tangible_outcome,
            previously_covered_skills=previously_covered,
            previously_covered_task_titles=previously_covered_titles,
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
            skill_focus=skill_focus,
            include_tangible_outcome=include_tangible_outcome,
            previously_covered_skills=previously_covered,
            previously_covered_task_titles=previously_covered_titles,
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
        # Store the generation context on the row so /regenerate can
        # inherit it and the UI can render badges.
        skill_focus=(skill_focus.strip() if skill_focus and skill_focus.strip() else None),
        include_tangible_outcome=include_tangible_outcome,
    )

    db.commit()
    db.refresh(roadmap)

    return {
        "roadmap": get_roadmap_full(roadmap, db),
        "source": source,
        "skill_gap": gap_names,
        "skills_matched": existing_names,
        "previously_covered_skills": previously_covered,
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
    """
    Compute role-skill gap based on the user's CATALOG skills.

    Note on free-text (custom_name) UserSkill entries: those have
    skill_id == NULL and can't match RoleSkill.skill_id, so they're
    not factored into this gap calculation. Periodic dedup jobs that
    merge custom names into catalog rows are the path to fixing that.
    For now: if the user has "React Hooks" as a free-text skill but
    not a catalog "React" entry, the gap will still include React.
    Acceptable trade-off — users can always add catalog skills manually.
    """
    required = (
        db.query(RoleSkill)
        .filter(RoleSkill.role_id == role_id)
        .all()
    )
    # Only consider user-skills that link to the catalog.
    user_skills = (
        db.query(UserSkill)
        .filter(
            UserSkill.user_id == user_id,
            UserSkill.skill_id.isnot(None),
        )
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


def _summarize_previous_roadmaps(
    user_id: UUID, role_id: UUID, db: Session,
) -> tuple[list[str], list[str]]:
    """
    Task 4 — Skill Gap Analysis.

    Returns (previously_covered_skills, previously_covered_task_titles):
      - skills: deduped skill names from prior roadmaps
      - task titles: specific task titles, so the prompt can avoid
        repeating "Build a To-Do app in React" type duplicates that
        the skill-name signal alone would miss.

    We look at ALL of the user's roadmaps (not just the current role's)
    because skills overlap between roles. e.g. "Python" learned for
    Data Analyst is still Python when they switch to ML Engineer.

    Completed-task skill names rank ahead of enrolled-but-incomplete
    ones (stronger evidence of mastery). Both lists capped (30 skills,
    40 titles) to keep prompt size sane.

    Caveat (spec note): we rely on the user's self-reported task
    completion. If the user marked things complete without actually
    learning them, this signal is noisy. The prompt instructs the
    model to revisit at a different angle for these.
    """
    user_roadmaps = (
        db.query(UserRoadmap)
        .filter(UserRoadmap.user_id == user_id)
        .all()
    )
    if not user_roadmaps:
        return [], []

    roadmap_ids = [rm.id for rm in user_roadmaps]
    stage_rows = (
        db.query(RoadmapStage)
        .filter(RoadmapStage.roadmap_id.in_(roadmap_ids))
        .all()
    )
    if not stage_rows:
        return [], []

    stage_ids = [s.id for s in stage_rows]
    tasks = (
        db.query(RoadmapTask)
        .filter(RoadmapTask.stage_id.in_(stage_ids))
        .all()
    )

    completed_skills: list[str] = []
    other_skills: list[str] = []
    completed_titles: list[str] = []
    other_titles: list[str] = []
    for t in tasks:
        if t.skill_name:
            (completed_skills if t.is_completed else other_skills).append(
                t.skill_name
            )
        if t.title:
            (completed_titles if t.is_completed else other_titles).append(
                t.title
            )

    # Dedup skills, case-insensitive, preserving order.
    seen_s: set[str] = set()
    ordered_skills: list[str] = []
    for name in completed_skills + other_skills:
        key = name.strip().lower()
        if key and key not in seen_s:
            seen_s.add(key)
            ordered_skills.append(name.strip())
        if len(ordered_skills) >= 30:
            break

    # Dedup titles, case-insensitive, preserving order.
    seen_t: set[str] = set()
    ordered_titles: list[str] = []
    for title in completed_titles + other_titles:
        key = title.strip().lower()
        if key and key not in seen_t:
            seen_t.add(key)
            ordered_titles.append(title.strip())
        if len(ordered_titles) >= 40:
            break

    return ordered_skills, ordered_titles


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
    *,
    skill_focus: str | None = None,
    include_tangible_outcome: bool = False,
    previously_covered_skills: list[str] | None = None,
    previously_covered_task_titles: list[str] | None = None,
) -> dict:
    profile_context = _build_profile_context(profile, role.name, gap_names)
    user_cert_names = _extract_certification_names(profile)
    recommended_certs = list(profile_context.get("recommended_standard_certs") or [])

    user_prompt = build_roadmap_prompt(
        role_name=role.name,
        existing_skills=existing_names,
        gap_skills=gap_names if gap_names else [f"Core skills for {role.name}"],
        profile_context=profile_context or None,
        language=language,
        skill_focus=skill_focus,
        include_tangible_outcome=include_tangible_outcome,
        previously_covered_skills=previously_covered_skills or [],
        previously_covered_task_titles=previously_covered_task_titles or [],
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

    _enforce_cert_milestones(
        roadmap_data=data,
        recommended_certs=recommended_certs,
        user_cert_names=user_cert_names,
        language=language,
    )

    return data


def _standard_certs_for_role(role_name: str) -> list[str]:
    lower = (role_name or "").strip().lower()
    if not lower:
        return []

    for key, certs in STANDARD_CERTS_BY_ROLE_KEYWORD.items():
        if key in lower:
            return certs
    return []


def _cert_aliases(cert_name: str) -> set[str]:
    aliases = {cert_name.strip().lower()}
    aliases.update(CERT_ALIAS_MAP.get(cert_name, set()))
    return {a.strip().lower() for a in aliases if a and a.strip()}


def _extract_certification_names(profile: Profile) -> list[str]:
    raw = profile.certifications or []
    names: list[str] = []
    for item in raw:
        name = ""
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        if name:
            names.append(name)

    # dedupe while preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for n in names:
        k = n.lower()
        if k in seen:
            continue
        seen.add(k)
        ordered.append(n)
    return ordered


def _normalize_user_cert_tokens(cert_names: list[str]) -> set[str]:
    tokens: set[str] = set()
    for cert in cert_names:
        c = cert.strip().lower()
        if not c:
            continue
        tokens.add(c)
        # Add compact variant for matching strings like "eJPT v2".
        tokens.add(re.sub(r"[^a-z0-9+]", "", c))
    return tokens


def _normalize_token(text: str) -> str:
    return re.sub(r"[^a-z0-9+]", "", (text or "").strip().lower())


def _filter_unearned_certs(candidate_certs: list[str], user_cert_names: list[str]) -> list[str]:
    user_tokens = _normalize_user_cert_tokens(user_cert_names)
    filtered: list[str] = []
    for cert in candidate_certs:
        aliases = _cert_aliases(cert)
        alias_tokens = set(aliases)
        alias_tokens.update(re.sub(r"[^a-z0-9+]", "", a) for a in aliases)
        if user_tokens.intersection(alias_tokens):
            continue
        filtered.append(cert)
    return filtered


def _recommended_certs_for_user(
    role_name: str,
    gap_names: list[str],
    user_cert_names: list[str],
) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    def _add_many(certs: list[str]):
        for cert in certs:
            key = cert.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            ordered.append(cert)

    _add_many(_standard_certs_for_role(role_name))

    gap_text = " ".join(gap_names or []).lower()
    for kw, certs in STANDARD_CERTS_BY_SKILL_KEYWORD.items():
        if kw in gap_text:
            _add_many(certs)

    return _filter_unearned_certs(ordered, user_cert_names)


def _roadmap_text_mentions_cert(roadmap_data: dict, cert_name: str) -> bool:
    aliases = _cert_aliases(cert_name)
    compact_aliases = {_normalize_token(a) for a in aliases}

    stages = roadmap_data.get("stages") or []
    for stage in stages:
        stage_text = " ".join(
            [
                str(stage.get("title") or ""),
                str(stage.get("description") or ""),
            ]
        ).lower()
        stage_compact = _normalize_token(stage_text)
        if any(a in stage_text for a in aliases) or any(
            a in stage_compact for a in compact_aliases
        ):
            return True

        for task in stage.get("tasks") or []:
            task_text = " ".join(
                [
                    str(task.get("title") or ""),
                    str(task.get("description") or ""),
                ]
            ).lower()
            task_compact = _normalize_token(task_text)
            if any(a in task_text for a in aliases) or any(
                a in task_compact for a in compact_aliases
            ):
                return True

            for res in task.get("resources") or []:
                res_text = " ".join(
                    [
                        str(res.get("title") or ""),
                        str(res.get("search_query") or ""),
                        str(res.get("url") or ""),
                    ]
                ).lower()
                res_compact = _normalize_token(res_text)
                if any(a in res_text for a in aliases) or any(
                    a in res_compact for a in compact_aliases
                ):
                    return True
    return False


def _enforce_cert_milestones(
    roadmap_data: dict,
    recommended_certs: list[str],
    user_cert_names: list[str],
    language: str = "en",
) -> None:
    if not recommended_certs:
        return

    # Remove already-owned certs from candidate list defensively.
    remaining = _filter_unearned_certs(recommended_certs, user_cert_names)
    if not remaining:
        return

    missing = [
        cert for cert in remaining if not _roadmap_text_mentions_cert(roadmap_data, cert)
    ]
    if not missing:
        return

    stages = roadmap_data.get("stages")
    if not isinstance(stages, list):
        roadmap_data["stages"] = []
        stages = roadmap_data["stages"]

    if language == "ar":
        stage_title = "مسار الشهادات المهنية"
        stage_desc = "التركيز على شهادات مهنية معترف بها في المجال مع تطبيق عملي."
        task_title_tpl = "التحضير لشهادة {cert}"
        task_desc_tpl = (
            "أنشئ خطة مذاكرة واختبارات تجريبية ومختبرات عملية للحصول على {cert}."
        )
    else:
        stage_title = "Professional Certification Track"
        stage_desc = "Focus on recognized industry certifications with practical lab validation."
        task_title_tpl = "Prepare for {cert}"
        task_desc_tpl = (
            "Build a study plan, exam-practice workflow, and hands-on labs for {cert}."
        )

    stage_order = len(stages) + 1
    tasks: list[dict] = []
    for i, cert in enumerate(missing[:2], 1):
        tasks.append(
            {
                "order": i,
                "title": task_title_tpl.format(cert=cert),
                "description": task_desc_tpl.format(cert=cert),
                "skill_name": None,
                "resources": [
                    {
                        "type": "certification",
                        "title": cert,
                        "url": "",
                        "search_query": f"{cert} official exam guide",
                    },
                    {
                        "type": "documentation",
                        "title": "Official objectives / blueprint",
                        "url": "",
                        "search_query": f"{cert} exam objectives",
                    },
                ],
            }
        )

    stages.append(
        {
            "order": stage_order,
            "title": stage_title,
            "description": stage_desc,
            "tasks": tasks,
        }
    )


def _infer_experience_level(profile: Profile) -> str:
    yoe = (profile.years_of_experience or "").strip()
    cert_count = len(_extract_certification_names(profile))
    exp_count = len(profile.experiences or [])

    if yoe in {"3+"} or exp_count >= 2 or cert_count >= 3:
        return "advanced"
    if yoe in {"1", "2"} or exp_count >= 1 or cert_count >= 1:
        return "intermediate"
    return "beginner"


def _build_profile_context(profile: Profile, role_name: str, gap_names: list[str] | None = None) -> dict:
    ctx: dict = {}
    if profile.major:
        ctx["major"] = profile.major
    if profile.university:
        ctx["university"] = profile.university
    if profile.current_status:
        ctx["current_status"] = profile.current_status
    if profile.graduation_year:
        ctx["graduation_year"] = profile.graduation_year
    if profile.years_of_experience:
        ctx["years_of_experience"] = profile.years_of_experience

    cert_names = _extract_certification_names(profile)
    role_certs = _recommended_certs_for_user(
        role_name=role_name,
        gap_names=gap_names or [],
        user_cert_names=cert_names,
    )
    if cert_names:
        ctx["certifications"] = cert_names
    if role_certs:
        ctx["recommended_standard_certs"] = role_certs

    ctx["experience_level"] = _infer_experience_level(profile)
    ctx["role_name"] = role_name
    return ctx


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
    *,
    skill_focus: str | None = None,
    include_tangible_outcome: bool = False,
) -> UserRoadmap:
    roadmap = UserRoadmap(
        user_id=user_id,
        role_id=role_id,
        title=title,
        title_ar=title_ar,
        source=source,
        is_ai_generated=is_ai,
        overall_progress=0.0,
        skill_focus=skill_focus,
        include_tangible_outcome=include_tangible_outcome,
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


# ════════════════════════════════════════════════════════════════════
#  SAVE TASK TO PROFILE
# ════════════════════════════════════════════════════════════════════


# Heuristics used by classify_task_for_profile() — kept as module-level
# constants so tests can import & tweak them.
_PROJECT_KEYWORDS = (
    "build", "create", "develop", "design", "make", "ship",
    "deploy", "implement", "project", "portfolio", "capstone",
    "clone", "prototype", "app", "tool", "site", "website",
)
_CERT_KEYWORDS = (
    "certif", "certified", "certification", "exam",
    "saa-c03", "az-900", "aws certified", "google professional",
    "comptia", "cissp", "pmp", "capm", "scrum master",
)


def classify_task_for_profile(task: "RoadmapTask") -> str:
    """
    Pick the most appropriate "save as" kind for a completed task.

    Returns one of: "certification", "project", "skill".

    Heuristic order matters — certifications are checked first because
    "Build certification prep notes" should still be classified as
    project unless the cert keyword is strong; conversely "Earn AWS
    Certified Solutions Architect" should always be cert.
    """
    title_lower = (task.title or "").lower()
    desc_lower = (task.description or "").lower()
    combined = f"{title_lower} {desc_lower}"

    if any(k in combined for k in _CERT_KEYWORDS):
        return "certification"
    if any(k in title_lower for k in _PROJECT_KEYWORDS):
        return "project"
    # Default: if the task has an explicit skill_name, save as skill.
    if task.skill_name:
        return "skill"
    # Fallback for tasks with no skill_name and no project/cert signal —
    # treat as a skill using the task title.
    return "skill"


def save_task_to_profile(
    user_id: UUID, task_id: UUID, kind: str, db: Session,
) -> dict:
    """
    Save a completed roadmap task to the user's profile, as either:
      - a UserSkill (catalog match if possible, else free-text)
      - a project entry (appended to profile.projects JSONB list)
      - a certification entry (appended to profile.certifications)

    Returns { kind, item } where item is the persisted shape.

    NOTE: this is intentionally permissive — it will save the same
    task multiple times if the user does so. The dedup safety net
    sits in the UserSkill table (unique constraints), and on the
    JSONB lists we check by name and skip duplicates.
    """
    if kind not in {"skill", "project", "certification"}:
        raise ValueError(
            f"Invalid kind: {kind}. Must be skill | project | certification."
        )

    task = db.get(RoadmapTask, task_id)
    if not task:
        raise ValueError("Task not found")

    # Ensure the task belongs to a roadmap owned by this user.
    stage = db.get(RoadmapStage, task.stage_id)
    if not stage:
        raise ValueError("Task's stage not found")
    roadmap = db.get(UserRoadmap, stage.roadmap_id)
    if not roadmap or roadmap.user_id != user_id:
        raise ValueError("Task does not belong to this user")

    profile = db.get(Profile, user_id)
    if not profile:
        raise ValueError("Profile not found")

    # ── Save as skill ────────────────────────────────────────────────
    if kind == "skill":
        skill_name = (task.skill_name or task.title).strip()
        if not skill_name:
            raise ValueError("Task has no skill_name or title to save")

        # Look for a catalog match first (case-insensitive).
        catalog = (
            db.query(Skill)
            .filter(func.lower(Skill.name) == skill_name.lower())
            .first()
        )

        if catalog:
            # Dedup against existing catalog-linked entry for this user.
            existing = (
                db.query(UserSkill)
                .filter(
                    UserSkill.user_id == user_id,
                    UserSkill.skill_id == catalog.id,
                )
                .first()
            )
            if existing:
                # Already saved — don't overwrite level/years they may
                # have set manually. Just bump the source if it makes
                # sense (manual > roadmap).
                return {
                    "kind": "skill",
                    "created": False,
                    "item": {
                        "id": str(existing.id),
                        "skill_name": catalog.name,
                        "is_custom": False,
                    },
                }
            us = UserSkill(
                user_id=user_id,
                skill_id=catalog.id,
                custom_name=None,
                source="roadmap",
            )
            db.add(us)
            db.commit()
            db.refresh(us)
            return {
                "kind": "skill",
                "created": True,
                "item": {
                    "id": str(us.id),
                    "skill_name": catalog.name,
                    "is_custom": False,
                },
            }

        # No catalog match — create a free-text entry. Dedup
        # case-insensitive against the user's existing custom names.
        existing_custom = (
            db.query(UserSkill)
            .filter(
                UserSkill.user_id == user_id,
                UserSkill.skill_id.is_(None),
                func.lower(UserSkill.custom_name) == skill_name.lower(),
            )
            .first()
        )
        if existing_custom:
            return {
                "kind": "skill",
                "created": False,
                "item": {
                    "id": str(existing_custom.id),
                    "skill_name": existing_custom.custom_name,
                    "is_custom": True,
                },
            }

        us = UserSkill(
            user_id=user_id,
            skill_id=None,
            custom_name=skill_name,
            source="roadmap",
        )
        db.add(us)
        db.commit()
        db.refresh(us)
        return {
            "kind": "skill",
            "created": True,
            "item": {
                "id": str(us.id),
                "skill_name": skill_name,
                "is_custom": True,
            },
        }

    # ── Save as project ──────────────────────────────────────────────
    if kind == "project":
        # profile.projects is a JSONB list of dicts. We append, dedup
        # by lower(name).
        project_name = task.title.strip()
        if not project_name:
            raise ValueError("Task has no title to save as a project")

        # Reassign with a NEW list to ensure SQLAlchemy detects the change.
        # In-place .append on a JSONB column doesn't always flag the
        # attribute as dirty.
        current = list(profile.projects or [])
        already = any(
            (p.get("name") or "").lower() == project_name.lower()
            for p in current
        )
        if already:
            return {"kind": "project", "created": False, "item": {"name": project_name}}

        new_entry = {
            "name": project_name,
            "description": task.description or "",
            "tech": [task.skill_name] if task.skill_name else [],
            "url": "",
            "source": "roadmap",
        }
        current.append(new_entry)
        profile.projects = current
        # Belt+suspenders on JSONB mutation detection.
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(profile, "projects")
        db.commit()
        return {"kind": "project", "created": True, "item": new_entry}

    # ── Save as certification ────────────────────────────────────────
    cert_name = task.title.strip()
    if not cert_name:
        raise ValueError("Task has no title to save as a certification")

    current = list(profile.certifications or [])
    already = any(
        (c.get("name") or "").lower() == cert_name.lower()
        for c in current
    )
    if already:
        return {
            "kind": "certification",
            "created": False,
            "item": {"name": cert_name},
        }

    new_entry = {
        "name": cert_name,
        "issuer": "",
        "date": "",
        "url": "",
        "source": "roadmap",
    }
    current.append(new_entry)
    profile.certifications = current
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(profile, "certifications")
    db.commit()
    return {"kind": "certification", "created": True, "item": new_entry}