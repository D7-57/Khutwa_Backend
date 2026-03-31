import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.cv import CVDocument
from app.schemas.cv_dir.builder import (
    CVCreateRequest,
    CVCreateResponse,
    CVUpdateRequest,
    CVBuilderDocumentResponse,
    AIEnhanceRequest,
    AIEnhanceResponse,
    CVPreviewRequest,
)
from app.services.cv.ai_enhance import enhance_section
from app.services.cv.renderer import render_cv_html, render_cv_pdf, list_templates

router = APIRouter(prefix="/cv/builder", tags=["cv-builder"])


# ══════════════════════════════════════════════════════════════
#  STATIC ROUTES FIRST — must come before any /{cv_id} routes
#  otherwise FastAPI matches "templates" / "enhance" / "preview"
#  as a cv_id path parameter
# ══════════════════════════════════════════════════════════════


# ── GET /cv/builder/templates ──


@router.get("/templates")
def get_available_templates():
    """No auth needed — public catalog of templates."""
    return list_templates()


# ── POST /cv/builder/enhance  (AI improve a section) ──


@router.post("/enhance", response_model=AIEnhanceResponse)
def ai_enhance_cv_section(
    body: AIEnhanceRequest,
    user_id: str = Depends(get_current_user_id),
):
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty.")

    result = enhance_section(
        section=body.section,
        content=body.content,
        context=body.context,
        language=body.language,
    )

    return AIEnhanceResponse(
        original=result["original"],
        improved=result["improved"],
        changes_summary=result["changes_summary"],
    )


# ── POST /cv/builder/preview  (HTML from raw data, no save) ──


@router.post("/preview")
def preview_cv_html_from_data(
    body: CVPreviewRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        html = render_cv_html(
            cv_data=body.cv_data.model_dump(),
            template_id=body.template,
            language=body.language,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return HTMLResponse(content=html)


# ── POST /cv/builder  (create a new CV from scratch) ──


@router.post("", response_model=CVCreateResponse, status_code=201)
def create_cv_from_scratch(
    body: CVCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = uuid.UUID(user_id)

    doc = CVDocument(
        user_id=uid,
        raw_file_url="builder://scratch",
        filename=body.title,
        mime_type="application/json",
        file_size=0,
        language=body.language,
        raw_text=None,
        extracted_data=body.cv_data.model_dump(),
        parser_version="builder-v1",
        model_version=None,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return CVCreateResponse(
        cv_id=doc.id,
        title=doc.filename or "My CV",
        language=doc.language,
        cv_data=doc.extracted_data or {},
        created_at=doc.created_at,
    )


# ══════════════════════════════════════════════════════════════
#  DYNAMIC {cv_id} ROUTES — after all static routes
# ══════════════════════════════════════════════════════════════


# ── GET /cv/builder/{cv_id} ──


@router.get("/{cv_id}", response_model=CVBuilderDocumentResponse)
def get_cv_for_editor(
    cv_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    doc = _get_user_cv(cv_id, user_id, db)
    source = "builder" if (doc.raw_file_url or "").startswith("builder://") else "upload"
    return CVBuilderDocumentResponse(
        cv_id=doc.id,
        title=doc.filename,
        language=doc.language,
        cv_data=doc.extracted_data or {},
        source=source,
        created_at=doc.created_at,
    )


# ── PATCH /cv/builder/{cv_id} ──


@router.patch("/{cv_id}", response_model=CVBuilderDocumentResponse)
def save_cv_editor_state(
    cv_id: str,
    body: CVUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    doc = _get_user_cv(cv_id, user_id, db)

    if body.title is not None:
        doc.filename = body.title
    if body.language is not None:
        doc.language = body.language
    if body.cv_data is not None:
        doc.extracted_data = body.cv_data.model_dump()

    db.commit()
    db.refresh(doc)

    source = "builder" if (doc.raw_file_url or "").startswith("builder://") else "upload"
    return CVBuilderDocumentResponse(
        cv_id=doc.id,
        title=doc.filename,
        language=doc.language,
        cv_data=doc.extracted_data or {},
        source=source,
        created_at=doc.created_at,
    )


# ── GET /cv/builder/{cv_id}/preview ──


@router.get("/{cv_id}/preview")
def preview_cv_html(
    cv_id: str,
    template: str = "classic",
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    doc = _get_user_cv(cv_id, user_id, db)
    try:
        html = render_cv_html(
            cv_data=doc.extracted_data or {},
            template_id=template,
            language=doc.language,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return HTMLResponse(content=html)


# ── GET /cv/builder/{cv_id}/export/pdf ──


@router.get("/{cv_id}/export/pdf")
def export_cv_pdf(
    cv_id: str,
    template: str = "classic",
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    doc = _get_user_cv(cv_id, user_id, db)
    try:
        pdf_bytes = render_cv_pdf(
            cv_data=doc.extracted_data or {},
            template_id=template,
            language=doc.language,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    contact_name = (doc.extracted_data or {}).get("contact_info", {}).get("name", "CV")
    safe_name = "".join(c for c in contact_name if c.isalnum() or c in " _-").strip() or "CV"
    filename = f"{safe_name}_CV.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ══════════════════════════════════════════════════════════════
#  HELPER
# ══════════════════════════════════════════════════════════════


def _get_user_cv(cv_id: str, user_id: str, db: Session) -> CVDocument:
    try:
        cv_uuid = uuid.UUID(cv_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cv_id")

    doc = db.query(CVDocument).filter(CVDocument.id == cv_uuid).first()
    if not doc:
        raise HTTPException(status_code=404, detail="CV not found")

    if str(doc.user_id) != user_id:
        raise HTTPException(status_code=403, detail="Not your CV")

    return doc