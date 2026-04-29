from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.career.role import Role
from app.models.roadmap.models import RoadmapTemplate, UserRoadmap, RoadmapStage
from app.schemas.roadmap.schemas import (
    RoadmapOut,
    RoadmapSummary,
    RoadmapGenerateRequest,
    RoadmapGenerateResponse,
    TaskComplete,
    TemplatePreview,
)
from app.services.roadmap.generator import (
    get_user_roadmap,
    get_user_roadmaps,
    get_roadmap_full,
    generate_roadmap,
    delete_roadmap_by_id,
    complete_task,
    uncomplete_task,
)

router = APIRouter(prefix="/roadmap", tags=["roadmap"])


# ── GET /roadmap/me — get user's active roadmap (or by id) ──


@router.get("/me", response_model=RoadmapOut | None)
def get_my_roadmap(
    roadmap_id: str | None = None,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    rid = UUID(roadmap_id) if roadmap_id else None
    roadmap = get_user_roadmap(uid, db, roadmap_id=rid)
    if not roadmap:
        return None
    return get_roadmap_full(roadmap, db)


# ── GET /roadmap/me/all — list all user's roadmaps (summaries) ──


@router.get("/me/all", response_model=list[RoadmapSummary])
def list_my_roadmaps(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    roadmaps = get_user_roadmaps(uid, db)
    result = []
    for rm in roadmaps:
        role_name = None
        if rm.role_id:
            role = db.get(Role, rm.role_id)
            if role:
                role_name = role.name

        stage_count = (
            db.query(RoadmapStage)
            .filter(RoadmapStage.roadmap_id == rm.id)
            .count()
        )
        # Quick task count via stages
        stages = (
            db.query(RoadmapStage)
            .filter(RoadmapStage.roadmap_id == rm.id)
            .all()
        )
        task_count = 0
        from app.models.roadmap.models import RoadmapTask as RT
        for s in stages:
            task_count += db.query(RT).filter(RT.stage_id == s.id).count()

        result.append(
            RoadmapSummary(
                id=rm.id,
                title=rm.title,
                title_ar=rm.title_ar,
                role_id=rm.role_id,
                role_name=role_name,
                source=rm.source,
                is_ai_generated=rm.is_ai_generated,
                overall_progress=rm.overall_progress,
                stage_count=stage_count,
                task_count=task_count,
                created_at=rm.created_at,
            )
        )
    return result


# ── POST /roadmap/me/generate — create roadmap for a role ──


@router.post("/me/generate", response_model=RoadmapGenerateResponse, status_code=201)
def generate_my_roadmap(
    body: RoadmapGenerateRequest | None = None,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)

    try:
        result = generate_roadmap(
            user_id=uid,
            db=db,
            role_id_override=body.role_id if body else None,
            force_ai=body.force_ai if body else False,
            language=body.language if body else "en",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return result


# ── POST /roadmap/me/regenerate ──


@router.post("/me/regenerate", response_model=RoadmapGenerateResponse)
def regenerate_my_roadmap(
    body: RoadmapGenerateRequest | None = None,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)

    try:
        result = generate_roadmap(
            user_id=uid,
            db=db,
            role_id_override=body.role_id if body else None,
            force_ai=body.force_ai if body else False,
            language=body.language if body else "en",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return result


# ── PATCH /roadmap/me/tasks/{task_id}/complete ──


@router.patch("/me/tasks/{task_id}/complete", response_model=TaskComplete)
def complete_roadmap_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    try:
        tid = UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task_id")

    try:
        result = complete_task(uid, tid, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


# ── PATCH /roadmap/me/tasks/{task_id}/uncomplete ──


@router.patch("/me/tasks/{task_id}/uncomplete", response_model=TaskComplete)
def uncomplete_roadmap_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    try:
        tid = UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task_id")

    try:
        result = uncomplete_task(uid, tid, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


# ── DELETE /roadmap/me/{roadmap_id} — delete a specific roadmap ──


@router.delete("/me/{roadmap_id}", status_code=204)
def delete_my_roadmap(
    roadmap_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    try:
        rid = UUID(roadmap_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid roadmap_id")

    try:
        delete_roadmap_by_id(uid, rid, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── GET /roadmap/templates ──


@router.get("/templates", response_model=list[TemplatePreview])
def list_templates(db: Session = Depends(get_db)):
    templates = db.query(RoadmapTemplate).all()
    result = []
    for t in templates:
        role = db.get(Role, t.role_id)
        stages = t.stages_json.get("stages", [])
        task_count = sum(len(s.get("tasks", [])) for s in stages)
        result.append(
            TemplatePreview(
                id=t.id,
                role_id=t.role_id,
                role_name=role.name if role else None,
                title=t.title,
                title_ar=t.title_ar,
                stage_count=len(stages),
                task_count=task_count,
                stages_json=t.stages_json,
            )
        )
    return result


# ── GET /roadmap/templates/{role_id} ──


@router.get("/templates/{role_id}", response_model=TemplatePreview)
def get_template(role_id: str, db: Session = Depends(get_db)):
    try:
        rid = UUID(role_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role_id")

    template = (
        db.query(RoadmapTemplate)
        .filter(RoadmapTemplate.role_id == rid)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="No template for this role")

    role = db.get(Role, rid)
    stages = template.stages_json.get("stages", [])
    task_count = sum(len(s.get("tasks", [])) for s in stages)

    return TemplatePreview(
        id=template.id,
        role_id=template.role_id,
        role_name=role.name if role else None,
        title=template.title,
        title_ar=template.title_ar,
        stage_count=len(stages),
        task_count=task_count,
        stages_json=template.stages_json,
    )
