"""Chat-style helpers used by the Flutter onboarding flow."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.career.role import Role
from app.services.cv_service import extract_text
from app.services.career.role_detection import detect_roles

router = APIRouter(prefix="/chat", tags=["chat"])

# Map backend role display names → canonical keys expected by Flutter UI (AppRole).
_SLUG_KEYWORDS: list[tuple[str, list[str]]] = [
    (
        "software_engineering",
        [
            "software",
            "developer",
            "devops",
            "mobile",
            "frontend",
            "backend",
            "full-stack",
            "full stack",
            "qa",
            "test engineer",
        ],
    ),
    (
        "data_science",
        [
            "data scientist",
            "data analyst",
            "data engineer",
            "machine learning",
            "ml engineer",
            "ai research",
        ],
    ),
    (
        "cybersecurity",
        ["security", "penetration", "grc"],
    ),
    (
        "information_systems",
        [
            "business analyst",
            "erp",
            "project manager",
            "product manager",
            "auditor",
            "information systems",
        ],
    ),
    (
        "computer_science",
        ["research engineer", "computer science", "theory"],
    ),
]


def _slug_from_role_name(name: str) -> str:
    n = (name or "").lower()
    for slug, kws in _SLUG_KEYWORDS:
        if any(k in n for k in kws):
            return slug
    return "software_engineering"


@router.post("/detect-role-from-cv")
async def detect_role_from_cv(
    cv: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    _ = user_id
    content = await cv.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    raw_text, _lang = extract_text(cv, content)
    excerpt = (raw_text or "").strip()[:15000]
    if len(excerpt) < 40:
        raise HTTPException(
            status_code=400,
            detail="Could not extract enough text from the CV (PDF/DOCX only).",
        )

    all_roles = db.query(Role).filter(Role.parent_id.isnot(None)).all()
    if not all_roles:
        raise HTTPException(status_code=500, detail="No roles configured in the database.")

    result = detect_roles(
        roles=all_roles,
        message=f"The user uploaded a CV. Here is the extracted text:\n\n{excerpt}",
        answers=None,
        context=None,
    )

    if not result.suggestions:
        return {
            "role": "software_engineering",
            "confidence": 0.0,
            "role_id": None,
            "role_name": None,
            "follow_up": result.follow_up,
        }

    top = result.suggestions[0]
    slug = _slug_from_role_name(top.role_name)
    return {
        "role": slug,
        "confidence": top.confidence,
        "role_id": str(top.role_id),
        "role_name": top.role_name,
        "follow_up": result.follow_up,
    }
