from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

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


# ── Domain names allowed in the AI detect flow ────────────────────────────────
# "UX & Design" is excluded — the platform supports IT, Engineering, Business only.
# This list contains DOMAIN-level names (role_type == "domain"), not field names.
_SUPPORTED_DETECT_DOMAINS = frozenset({
    # ── IT ──
    "Software Engineering",
    "Data & AI",
    "Cybersecurity",
    "Networking & Cloud",
    "Information Systems & Business",
    # ── Engineering ──
    "Industrial Engineering",
    "Petroleum Engineering",
    "Chemical Engineering",
    "Mechanical Engineering",
    "Civil Engineering",
    # ── Business ──
    "Business Administration",
    "Accounting",
    "Finance",
    "Economics",
    "Management Information Systems",
})


# ── GET /career/roles/questionnaire-options ───────────────────────────────────
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


# Question option key groups
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

# Arabic labels for questionnaire options
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


# ── GET /career/roles/tree ────────────────────────────────────────────────────
# Returns domain-level nodes with their selectable child roles.
# The top-level fields (IT / Engineering / Business) are not included
# here to keep the response backward-compatible with the existing frontend
# catalog builder. Use GET /career/roles/fields for the field list.

@router.get("/tree", response_model=list[RoleTreeNode])
def get_role_tree(db: Session = Depends(get_db)):
    domains = (
        db.query(Role)
        .filter(Role.role_type == "domain")
        .order_by(Role.name)
        .all()
    )
    domain_ids = [d.id for d in domains]

    leaf_roles = (
        db.query(Role)
        .filter(Role.role_type == "role", Role.parent_id.in_(domain_ids))
        .order_by(Role.name)
        .all()
    )

    children_map: dict[UUID, list[Role]] = {}
    for r in leaf_roles:
        children_map.setdefault(r.parent_id, []).append(r)

    # Resolve parent field names in one query
    field_ids = {d.parent_id for d in domains if d.parent_id}
    fields_map: dict[UUID, Role] = {
        f.id: f
        for f in db.query(Role).filter(Role.id.in_(field_ids)).all()
    }

    return [
        RoleTreeNode(
            id=d.id,
            name=d.name,
            name_en=d.name_en,
            name_ar=d.name_ar,
            description=d.description,
            role_type=d.role_type,
            field_name=fields_map[d.parent_id].name if d.parent_id in fields_map else None,
            children=[
                RoleChild(
                    id=c.id,
                    name=c.name,
                    name_en=c.name_en,
                    name_ar=c.name_ar,
                    description=c.description,
                    role_type=c.role_type,
                )
                for c in children_map.get(d.id, [])
            ],
        )
        for d in domains
    ]


# ── GET /career/roles/fields ──────────────────────────────────────────────────
# Returns the three top-level fields with their domain children
# (full 3-level tree for richer frontends / admin use).

@router.get("/fields", response_model=list[RoleTreeNode])
def get_role_fields(db: Session = Depends(get_db)):
    fields = (
        db.query(Role)
        .filter(Role.role_type == "field")
        .order_by(Role.name)
        .all()
    )
    field_ids = [f.id for f in fields]

    domains = (
        db.query(Role)
        .filter(Role.role_type == "domain", Role.parent_id.in_(field_ids))
        .order_by(Role.name)
        .all()
    )

    domains_by_field: dict[UUID, list[Role]] = {}
    for d in domains:
        domains_by_field.setdefault(d.parent_id, []).append(d)

    return [
        RoleTreeNode(
            id=f.id,
            name=f.name,
            name_en=f.name_en,
            name_ar=f.name_ar,
            description=f.description,
            role_type=f.role_type,
            children=[
                RoleChild(
                    id=d.id,
                    name=d.name,
                    name_en=d.name_en,
                    name_ar=d.name_ar,
                    description=d.description,
                    role_type=d.role_type,
                )
                for d in domains_by_field.get(f.id, [])
            ],
        )
        for f in fields
    ]


# ── GET /career/roles  (flat list, optional ?role_type= filter) ───────────────

@router.get("", response_model=list[RoleOut])
def list_roles(
    role_type: str | None = None,
    parent_id: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Role)
    if role_type is not None:
        q = q.filter(Role.role_type == role_type)
    if parent_id is not None:
        try:
            pid = UUID(parent_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid parent_id")
        q = q.filter(Role.parent_id == pid)
    return q.order_by(Role.name).all()


# ── GET /career/roles/{role_id} ───────────────────────────────────────────────

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


# ── GET /career/roles/{role_id}/skills ────────────────────────────────────────

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


# ── GET /career/roles/me/selected ─────────────────────────────────────────────

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
            role_name_ar=r.name_ar,
            confidence=ur.confidence,
            source=ur.source,
            is_primary=ur.is_primary,
        )
        for ur, r in rows
    ]


# ── POST /career/roles/me/selected ────────────────────────────────────────────

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

    # Only leaf roles (role_type == "role") are selectable
    if role.role_type != "role":
        raise HTTPException(
            status_code=400,
            detail="Please select a specific job role, not a field or domain category.",
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
            role_name_ar=role.name_ar,
            confidence=existing.confidence,
            source=existing.source,
            is_primary=existing.is_primary,
        )

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
        role_name_ar=role.name_ar,
        confidence=ur.confidence,
        source=ur.source,
        is_primary=ur.is_primary,
    )


# ── PUT /career/roles/me/selected/bulk ───────────────────────────────────────

@router.put("/me/selected/bulk", response_model=list[UserRoleOut])
def bulk_set_my_roles(
    body: UserRoleBulkSet,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)

    if len(body.roles) > 3:
        raise HTTPException(status_code=400, detail="Maximum 3 roles allowed.")

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

    # Only leaf roles are selectable
    for rid, role in roles_map.items():
        if role.role_type != "role":
            raise HTTPException(
                status_code=400,
                detail=f"'{role.name}' is a {role.role_type}, not a selectable job role.",
            )

    db.query(UserRole).filter(UserRole.user_id == uid).delete()

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
                role_name_ar=role.name_ar,
                confidence=ur.confidence,
                source=ur.source,
                is_primary=ur.is_primary,
            )
        )

    db.commit()
    return results


# ── DELETE /career/roles/me/selected/{role_id} ───────────────────────────────

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


# ── POST /career/roles/detect ─────────────────────────────────────────────────

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

    # Fetch only leaf roles whose domain is in the supported set.
    # UX & Design is excluded since it is not in _SUPPORTED_DETECT_DOMAINS.
    supported_domains = (
        db.query(Role)
        .filter(
            Role.role_type == "domain",
            Role.name.in_(_SUPPORTED_DETECT_DOMAINS),
        )
        .all()
    )
    supported_domain_ids = {d.id for d in supported_domains}

    all_roles = (
        db.query(Role)
        .filter(
            Role.role_type == "role",
            Role.parent_id.in_(supported_domain_ids),
        )
        .all()
    )

    if not all_roles:
        raise HTTPException(
            status_code=500,
            detail="No roles configured in the system yet.",
        )

    # If the user explicitly selected a field (IT / Engineering / Business),
    # narrow the catalog to that field's domains for tighter suggestions.
    if body.context and (field_name := body.context.get("field")):
        field_row = (
            db.query(Role)
            .filter(Role.role_type == "field", Role.name == field_name)
            .first()
        )
        if field_row:
            field_domain_ids = {
                d.id
                for d in db.query(Role)
                .filter(Role.role_type == "domain", Role.parent_id == field_row.id)
                .all()
            }
            all_roles = [r for r in all_roles if r.parent_id in field_domain_ids]

        if not all_roles:
            raise HTTPException(
                status_code=404,
                detail=f"No roles found for field '{field_name}'.",
            )

    return detect_roles(
        roles=all_roles,
        answers=body.answers,
        message=body.message,
        context=body.context,
    )