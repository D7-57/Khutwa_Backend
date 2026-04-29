from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.career.role import Role, UserRole
from app.models.career.skill import Skill
from app.models.career.role_skill import RoleSkill
from app.schemas.career.roles import (
    RoleChild,
    RoleTreeNode,
    RoleOut,
    UserRoleSet,
    UserRoleBulkSet,
    UserRoleOut,
    RoleDetectRequest,
    RoleDetectResponse,
)
from app.schemas.career.skills import RoleSkillOut
from app.services.career.role_detection import detect_roles
from app.services.career.prompts import QUESTION_LABELS

router = APIRouter(prefix="/career/roles", tags=["career-roles"])


# ── GET /career/roles/questionnaire-options ──
# Returns the MCQ structure so the frontend doesn't hardcode labels.

@router.get("/questionnaire-options")
def get_questionnaire_options():
    return {
        "questions": [
            {
                "key": "energy_sources",
                "title_en": "What activities make you lose track of time?",
                "title_ar": "ما الأنشطة التي تنسيك الوقت؟",
                "multi_select": True,
                "max_picks": 3,
                "options": [
                    {"value": k, "label_en": v, "label_ar": _AR.get(k, v)}
                    for k, v in QUESTION_LABELS.items()
                    if k in _Q1_KEYS
                ],
            },
            {
                "key": "work_style",
                "title_en": "How do you prefer to work?",
                "title_ar": "كيف تفضل العمل؟",
                "multi_select": False,
                "options": [
                    {"value": k, "label_en": v, "label_ar": _AR.get(k, v)}
                    for k, v in QUESTION_LABELS.items()
                    if k in _Q2_KEYS
                ],
            },
            {
                "key": "output_preferences",
                "title_en": "What gives you the most satisfaction?",
                "title_ar": "ما الذي يمنحك أكبر شعور بالإنجاز؟",
                "multi_select": True,
                "max_picks": 2,
                "options": [
                    {"value": k, "label_en": v, "label_ar": _AR.get(k, v)}
                    for k, v in QUESTION_LABELS.items()
                    if k in _Q3_KEYS
                ],
            },
            {
                "key": "top_priority",
                "title_en": "What matters most in your first job?",
                "title_ar": "ما الأهم بالنسبة لك في أول وظيفة؟",
                "multi_select": False,
                "options": [
                    {"value": k, "label_en": v, "label_ar": _AR.get(k, v)}
                    for k, v in QUESTION_LABELS.items()
                    if k in _Q4_KEYS
                ],
            },
        ],
    }


# Option key sets for filtering
_Q1_KEYS = {
    "writing_communicating", "analyzing_data", "building_coding",
    "designing_visuals", "helping_advising", "managing_organizing",
    "researching_learning",
}
_Q2_KEYS = {
    "structured_analytical", "creative_openended",
    "people_coordination", "builder_maker",
}
_Q3_KEYS = {
    "shipped_built_something", "helped_someone",
    "made_something_beautiful", "found_an_insight",
    "hit_a_target_closed_deal",
}
_Q4_KEYS = {
    "high_salary", "fast_learning", "creative_freedom",
    "job_stability", "clear_career_ladder",
}

# Arabic labels
_AR = {
    "writing_communicating":    "الكتابة والتواصل",
    "analyzing_data":           "تحليل البيانات والأرقام",
    "building_coding":          "البناء والبرمجة",
    "designing_visuals":        "التصميم المرئي",
    "helping_advising":         "مساعدة وتوجيه الناس",
    "managing_organizing":      "الإدارة والتنظيم",
    "researching_learning":     "البحث والتعلم",
    "structured_analytical":    "منظّم / تحليلي",
    "creative_openended":       "إبداعي / مفتوح",
    "people_coordination":      "تنسيق بين الناس والفرق",
    "builder_maker":            "بناء الأشياء من الصفر",
    "shipped_built_something":  "أنجزت أو بنيت شيئاً",
    "helped_someone":           "ساعدت شخصاً في حل مشكلة",
    "made_something_beautiful": "حسّنت شكل أو تجربة شيء",
    "found_an_insight":         "اكتشفت رؤية في البيانات",
    "hit_a_target_closed_deal": "حققت هدفاً أو أتممت صفقة",
    "high_salary":              "راتب مرتفع",
    "fast_learning":            "منحنى تعلم سريع",
    "creative_freedom":         "حرية إبداعية",
    "job_stability":            "استقرار وظيفي",
    "clear_career_ladder":      "مسار وظيفي واضح",
}


# ── GET /career/roles/tree ──
# Returns top-level fields with their child specializations.


@router.get("/tree", response_model=list[RoleTreeNode])
def get_role_tree(db: Session = Depends(get_db)):
    # get all roles ordered by name
    all_roles = db.query(Role).order_by(Role.name).all()

    # separate parents (parent_id IS NULL) and children
    parents = [r for r in all_roles if r.parent_id is None]
    children_map: dict[UUID, list[Role]] = {}
    for r in all_roles:
        if r.parent_id is not None:
            children_map.setdefault(r.parent_id, []).append(r)

    return [
        RoleTreeNode(
            id=p.id,
            name=p.name,
            description=p.description,
            children=[
                RoleChild(id=c.id, name=c.name, description=c.description)
                for c in children_map.get(p.id, [])
            ],
        )
        for p in parents
    ]


# ── GET /career/roles  (flat list, optional ?parent_id= filter) ──


@router.get("", response_model=list[RoleOut])
def list_roles(
    parent_id: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Role)
    if parent_id is not None:
        try:
            pid = UUID(parent_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid parent_id")
        q = q.filter(Role.parent_id == pid)
    return q.order_by(Role.name).all()


# ── GET /career/roles/{role_id} ──


@router.get("/{role_id}", response_model=RoleOut)
def get_role(role_id: str, db: Session = Depends(get_db)):
    try:
        rid = UUID(role_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role_id")
    role = db.get(Role, rid)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


# ── GET /career/roles/{role_id}/skills ──
# What skills does this role require?


@router.get("/{role_id}/skills", response_model=list[RoleSkillOut])
def get_role_skills(role_id: str, db: Session = Depends(get_db)):
    try:
        rid = UUID(role_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role_id")

    role = db.get(Role, rid)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    rows = (
        db.query(RoleSkill, Skill)
        .join(Skill, RoleSkill.skill_id == Skill.id)
        .filter(RoleSkill.role_id == rid)
        .order_by(RoleSkill.importance_weight.desc())
        .all()
    )
    return [
        RoleSkillOut(
            skill_id=rs.skill_id,
            skill_name=sk.name,
            category=sk.category,
            importance_weight=rs.importance_weight,
        )
        for rs, sk in rows
    ]


# ── GET /career/roles/me  (user's selected roles) ──


@router.get("/me/selected", response_model=list[UserRoleOut])
def get_my_roles(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    rows = (
        db.query(UserRole, Role)
        .join(Role, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == uid)
        .all()
    )
    return [
        UserRoleOut(
            id=ur.id,
            role_id=ur.role_id,
            role_name=r.name,
            confidence=ur.confidence,
            source=ur.source,
            is_primary=ur.is_primary,
        )
        for ur, r in rows
    ]


# ── POST /career/roles/me  (set / add a role) ──


@router.post("/me/selected", response_model=UserRoleOut, status_code=201)
def set_my_role(
    body: UserRoleSet,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)

    role = db.get(Role, body.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # if this is a parent-level field, reject — user must pick a specialization
    has_children = (
        db.query(func.count(Role.id))
        .filter(Role.parent_id == body.role_id)
        .scalar()
    )
    if has_children:
        raise HTTPException(
            status_code=400,
            detail="Please select a specific specialization, not a broad field.",
        )

    existing = (
        db.query(UserRole)
        .filter(UserRole.user_id == uid, UserRole.role_id == body.role_id)
        .first()
    )
    if existing:
        existing.confidence = body.confidence
        existing.source = body.source
        db.commit()
        db.refresh(existing)
        return UserRoleOut(
            id=existing.id,
            role_id=existing.role_id,
            role_name=role.name,
            confidence=existing.confidence,
            source=existing.source,
            is_primary=existing.is_primary,
        )

    # unset any existing primary
    db.query(UserRole).filter(
        UserRole.user_id == uid, UserRole.is_primary == True
    ).update({"is_primary": False})

    ur = UserRole(
        user_id=uid,
        role_id=body.role_id,
        confidence=body.confidence,
        source=body.source,
        is_primary=True,
    )
    db.add(ur)
    db.commit()
    db.refresh(ur)

    return UserRoleOut(
        id=ur.id,
        role_id=ur.role_id,
        role_name=role.name,
        confidence=ur.confidence,
        source=ur.source,
        is_primary=ur.is_primary,
    )


# ── PUT /career/roles/me/selected/bulk  (replace all – for onboarding) ──


@router.put("/me/selected/bulk", response_model=list[UserRoleOut])
def bulk_set_my_roles(
    body: UserRoleBulkSet,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)

    if len(body.roles) > 3:
        raise HTTPException(
            status_code=400,
            detail="Maximum 3 roles allowed.",
        )

    # validate all role IDs and reject parent-level fields
    role_ids = [r.role_id for r in body.roles]
    roles_map = {
        r.id: r
        for r in db.query(Role).filter(Role.id.in_(role_ids)).all()
    }
    missing = set(role_ids) - set(roles_map.keys())
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Roles not found: {[str(m) for m in missing]}",
        )

    for rid in role_ids:
        has_children = (
            db.query(func.count(Role.id))
            .filter(Role.parent_id == rid)
            .scalar()
        )
        if has_children:
            raise HTTPException(
                status_code=400,
                detail=f"Role '{roles_map[rid].name}' is a broad field. Pick a specialization.",
            )

    # delete old
    db.query(UserRole).filter(UserRole.user_id == uid).delete()

    # insert new – first one is primary
    results = []
    for i, item in enumerate(body.roles):
        ur = UserRole(
            user_id=uid,
            role_id=item.role_id,
            confidence=item.confidence,
            source=item.source,
            is_primary=(i == 0),
        )
        db.add(ur)
        db.flush()
        role = roles_map[item.role_id]
        results.append(
            UserRoleOut(
                id=ur.id,
                role_id=ur.role_id,
                role_name=role.name,
                confidence=ur.confidence,
                source=ur.source,
                is_primary=ur.is_primary,
            )
        )

    db.commit()
    return results


# ── DELETE /career/roles/me/{role_id} ──


@router.delete("/me/selected/{role_id}", status_code=204)
def remove_my_role(
    role_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    try:
        rid = UUID(role_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role_id")

    deleted = (
        db.query(UserRole)
        .filter(UserRole.user_id == uid, UserRole.role_id == rid)
        .delete()
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Role not in your profile")
    db.commit()


# ── POST /career/roles/detect  (AI-powered role suggestion) ──


@router.post("/detect", response_model=RoleDetectResponse)
def detect_role(
    body: RoleDetectRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    if not body.answers and not body.message and not body.context:
        raise HTTPException(
            status_code=400,
            detail="Provide questionnaire answers, a chat message, or CV context.",
        )

    # fetch available roles for the AI to choose from
    all_roles = db.query(Role).filter(Role.parent_id.isnot(None)).all()
    if not all_roles:
        raise HTTPException(
            status_code=500,
            detail="No roles configured in the system yet.",
        )

    return detect_roles(
        roles=all_roles,
        answers=body.answers,
        message=body.message,
        context=body.context,
    )