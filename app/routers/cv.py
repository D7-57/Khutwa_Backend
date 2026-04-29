import html
import json
import uuid
from fastapi import  Depends, HTTPException
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import HTMLResponse
from app.core.security import bearer_scheme
from sqlalchemy.orm import Session
from app.schemas.cv import (
    CVEvaluationItemResponse,
    CVEvaluationDetailResponse,
    CVDocumentListItemResponse,
    CVLatestEvaluationSummary,
)

from app.services.cv_service import (
    _supabase_storage_upload,
    extract_text,
    llm_extract_structured_cv,
)
from app.services.supabase_storage import create_signed_url

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.cv import CVDocument, CVEvaluation
from app.models.career.role import Role
from app.schemas.cv import CVEvaluateRequest, CVEvaluateResponse
from app.services.cv_evaluation import run_full_cv_evaluation

router = APIRouter(prefix="/cv", tags=["cv"])



@router.post("/upload")
async def upload_cv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    creds=Depends(bearer_scheme),
):
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")

    user_jwt = creds.credentials

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    obj_id = uuid.uuid4().hex
    safe_name = (file.filename or "cv").replace("/", "_").replace("\\", "_")
    object_path = f"{user_id}/{obj_id}_{safe_name}"

    # 1) Supabase Storage (optional — bucket/RLS may be missing in dev)
    storage_ref: str
    try:
        storage_ref = _supabase_storage_upload(
            bucket="cvs",
            object_path=object_path,
            content=content,
            content_type=file.content_type or "application/octet-stream",
            user_jwt=user_jwt,
        )
    except HTTPException as e:
        detail = e.detail
        dtext = detail if isinstance(detail, str) else str(detail)
        if e.status_code == 400 and "Supabase upload failed" in dtext:
            storage_ref = f"inline/{object_path}"
        else:
            raise
    except Exception:
        storage_ref = f"inline/{object_path}"

    # 2) extract text (pdf/docx)
    try:
        raw_text, language = extract_text(file, content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read CV file: {e!s}") from e

    # 3) LLM -> structured JSON (never fail the whole upload on LLM errors)
    try:
        extracted = llm_extract_structured_cv(raw_text=raw_text, language=language)
    except Exception:
        extracted = {
            "parse_error": True,
            "contact_info": {},
            "skills": {},
            "raw_text_excerpt": (raw_text or "")[:2000],
        }

    # 4) store in DB
    doc = CVDocument(
        user_id=uuid.UUID(user_id),
        raw_file_url=storage_ref,  # "cvs/<user>/<file>"
        filename=file.filename,
        mime_type=file.content_type,
        file_size=len(content),
        language=language,
        raw_text=raw_text,
        extracted_data=extracted,
        parser_version="v1",
        model_version="gpt-4o-mini",
    )

    db.add(doc)
    db.commit()
    db.refresh(doc)

    return {
        "cv_id": str(doc.id),
        "raw_file_ref": doc.raw_file_url,
        "language": doc.language,
        "extracted_preview": {
            "name": (doc.extracted_data or {}).get("contact_info", {}).get("name"),
            "skills": (doc.extracted_data or {}).get("skills", {}),
        },
    }

# That’s it: Flutter calls this endpoint, gets a URL, opens it in webview/pdf viewer.
@router.get("/{cv_id}/download-url")
def get_cv_download_url(
    cv_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    creds=Depends(bearer_scheme),
):
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")

    doc = db.query(CVDocument).filter(CVDocument.id == uuid.UUID(cv_id)).first()
    if not doc:
        raise HTTPException(status_code=404, detail="CV not found")

    if str(doc.user_id) != user_id:
        raise HTTPException(status_code=403, detail="Not your CV")

    if doc.raw_file_url.startswith("inline/"):
        raise HTTPException(
            status_code=404,
            detail="File is stored locally only (storage not configured). Parsed CV data is still available.",
        )

    # doc.raw_file_url stored like: "cvs/<uid>/<file>"
    # split to bucket + path
    parts = doc.raw_file_url.split("/", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=500, detail="Invalid raw_file_url format")
    bucket, object_path = parts[0], parts[1]

    url = create_signed_url(bucket=bucket, object_path=object_path, expires_in=600, user_jwt=creds.credentials)
    return {"url": url, "expires_in": 600}


@router.post("/{cv_id}/evaluate", response_model=CVEvaluateResponse)
def evaluate_cv(
    cv_id: str,
    payload: CVEvaluateRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        cv_uuid = uuid.UUID(cv_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cv_id")

    doc = db.query(CVDocument).filter(CVDocument.id == cv_uuid).first()
    if not doc:
        raise HTTPException(status_code=404, detail="CV not found")

    if str(doc.user_id) != user_id:
        raise HTTPException(status_code=403, detail="Not your CV")

    role = db.query(Role).filter(Role.id == payload.role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    evaluation_json = run_full_cv_evaluation(
        raw_text=doc.raw_text or "",
        extracted_data=doc.extracted_data or {},
        role_name=role.name,
        role_description=role.description,
        language=doc.language,
    )

    overall_score = None
    ats_score = None

    try:
        overall_score = int(evaluation_json.get("role_fit", {}).get("score"))
    except Exception:
        pass

    try:
        ats_score = int(evaluation_json.get("ats", {}).get("score"))
    except Exception:
        pass

    evaluation = CVEvaluation(
        cv_id=doc.id,
        role_id=role.id,
        target_role=role.name,
        overall_score=overall_score,
        ats_score=ats_score,
        evaluation_json=evaluation_json,
    )

    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)

    return CVEvaluateResponse(
        evaluation_id=evaluation.id,
        cv_id=evaluation.cv_id,
        role_id=evaluation.role_id,
        target_role=evaluation.target_role,
        overall_score=evaluation.overall_score,
        ats_score=evaluation.ats_score,
        evaluation_json=evaluation.evaluation_json or {},
    )

@router.get("/{cv_id}/evaluations", response_model=list[CVEvaluationItemResponse])
def list_cv_evaluations(
    cv_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        cv_uuid = uuid.UUID(cv_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cv_id")

    doc = db.query(CVDocument).filter(CVDocument.id == cv_uuid).first()
    if not doc:
        raise HTTPException(status_code=404, detail="CV not found")

    if str(doc.user_id) != user_id:
        raise HTTPException(status_code=403, detail="Not your CV")

    evaluations = (
        db.query(CVEvaluation)
        .filter(CVEvaluation.cv_id == doc.id)
        .order_by(CVEvaluation.created_at.desc())
        .all()
    )

    return [
        CVEvaluationItemResponse(
            evaluation_id=e.id,
            cv_id=e.cv_id,
            role_id=e.role_id,
            target_role=e.target_role,
            overall_score=e.overall_score,
            ats_score=e.ats_score,
            created_at=e.created_at,
        )
        for e in evaluations
    ]


@router.get("/evaluations/{evaluation_id}", response_model=CVEvaluationDetailResponse)
def get_cv_evaluation(
    evaluation_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        evaluation_uuid = uuid.UUID(evaluation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid evaluation_id")

    evaluation = (
        db.query(CVEvaluation)
        .filter(CVEvaluation.id == evaluation_uuid)
        .first()
    )
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    doc = db.query(CVDocument).filter(CVDocument.id == evaluation.cv_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Parent CV not found")

    if str(doc.user_id) != user_id:
        raise HTTPException(status_code=403, detail="Not your evaluation")

    return CVEvaluationDetailResponse(
        evaluation_id=evaluation.id,
        cv_id=evaluation.cv_id,
        role_id=evaluation.role_id,
        target_role=evaluation.target_role,
        overall_score=evaluation.overall_score,
        ats_score=evaluation.ats_score,
        evaluation_json=evaluation.evaluation_json or {},
        created_at=evaluation.created_at,
    )

@router.get("/my-documents", response_model=list[CVDocumentListItemResponse])
def list_my_cv_documents(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    docs = (
        db.query(CVDocument)
        .filter(CVDocument.user_id == uuid.UUID(user_id))
        .order_by(CVDocument.created_at.desc())
        .all()
    )

    result = []

    for doc in docs:
        latest_eval = (
            db.query(CVEvaluation)
            .filter(CVEvaluation.cv_id == doc.id)
            .order_by(CVEvaluation.created_at.desc())
            .first()
        )

        latest_evaluation = None
        if latest_eval:
            latest_evaluation = CVLatestEvaluationSummary(
                evaluation_id=latest_eval.id,
                target_role=latest_eval.target_role,
                overall_score=latest_eval.overall_score,
                ats_score=latest_eval.ats_score,
                created_at=latest_eval.created_at,
            )

        result.append(
            CVDocumentListItemResponse(
                cv_id=doc.id,
                filename=doc.filename,
                mime_type=doc.mime_type,
                file_size=doc.file_size,
                language=doc.language,
                created_at=doc.created_at,
                latest_evaluation=latest_evaluation,
            )
        )

    return result


# ---- Builder compatibility endpoints (legacy frontend support) ----

def _render_builder_html(cv_data: dict, title: str = "CV Preview") -> str:
    contact = cv_data.get("contactInfo", {}) if isinstance(cv_data, dict) else {}
    summary = str(cv_data.get("summary", "")) if isinstance(cv_data, dict) else ""
    name = str(contact.get("name", "")).strip() or "My CV"
    email = str(contact.get("email", "")).strip()
    phone = str(contact.get("phone", "")).strip()
    location = str(contact.get("location", "")).strip()
    meta = " | ".join([x for x in [email, phone, location] if x])

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #111; }}
    h1 {{ margin: 0 0 6px 0; font-size: 28px; }}
    h2 {{ margin: 18px 0 6px 0; font-size: 16px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }}
    .meta {{ color: #555; font-size: 12px; }}
    .card {{ border: 1px solid #eee; border-radius: 8px; padding: 10px; margin: 8px 0; }}
  </style>
</head>
<body>
  <h1>{html.escape(name)}</h1>
  <div class="meta">{html.escape(meta)}</div>
  <h2>Summary</h2>
  <div>{html.escape(summary)}</div>
</body>
</html>"""


@router.get("/builder/templates")
def builder_templates():
    return [
        {"id": "classic", "name": "Classic", "description": "Clean single-column, ATS-friendly"},
        {"id": "modern", "name": "Modern", "description": "Contemporary with accent colors"},
        {"id": "minimal", "name": "Minimal", "description": "Simple and elegant"},
    ]


@router.post("/builder")
def builder_create(
    payload: dict,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    title = str(payload.get("title") or "My CV")
    language = str(payload.get("language") or "en")
    cv_data = payload.get("cv_data") or {}
    if not isinstance(cv_data, dict):
        raise HTTPException(status_code=400, detail="cv_data must be an object")

    raw_text = json.dumps(cv_data, ensure_ascii=False)
    doc = CVDocument(
        user_id=uuid.UUID(user_id),
        raw_file_url=f"inline/generated/{uuid.uuid4().hex}.json",
        filename=f"{title}.json",
        mime_type="application/json",
        file_size=len(raw_text.encode("utf-8")),
        language=language,
        raw_text=raw_text,
        extracted_data=cv_data,
        parser_version="builder-v1",
        model_version="builder-v1",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {
        "cv_id": str(doc.id),
        "title": title,
        "language": language,
        "cv_data": cv_data,
    }


@router.get("/builder/{cv_id}")
def builder_get(
    cv_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        cv_uuid = uuid.UUID(cv_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cv_id")
    doc = db.query(CVDocument).filter(CVDocument.id == cv_uuid).first()
    if not doc:
        raise HTTPException(status_code=404, detail="CV not found")
    if str(doc.user_id) != user_id:
        raise HTTPException(status_code=403, detail="Not your CV")
    return {
        "cv_id": str(doc.id),
        "title": (doc.filename or "My CV").replace(".json", ""),
        "language": doc.language or "en",
        "cv_data": doc.extracted_data or {},
    }


@router.patch("/builder/{cv_id}")
def builder_save(
    cv_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        cv_uuid = uuid.UUID(cv_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cv_id")
    doc = db.query(CVDocument).filter(CVDocument.id == cv_uuid).first()
    if not doc:
        raise HTTPException(status_code=404, detail="CV not found")
    if str(doc.user_id) != user_id:
        raise HTTPException(status_code=403, detail="Not your CV")

    title = payload.get("title")
    language = payload.get("language")
    cv_data = payload.get("cv_data")
    if title is not None:
        doc.filename = f"{str(title)}.json"
    if language is not None:
        doc.language = str(language)
    if cv_data is not None:
        if not isinstance(cv_data, dict):
            raise HTTPException(status_code=400, detail="cv_data must be an object")
        doc.extracted_data = cv_data
        doc.raw_text = json.dumps(cv_data, ensure_ascii=False)
        doc.file_size = len((doc.raw_text or "").encode("utf-8"))
    db.commit()
    db.refresh(doc)
    return {
        "cv_id": str(doc.id),
        "title": (doc.filename or "My CV").replace(".json", ""),
        "language": doc.language or "en",
        "cv_data": doc.extracted_data or {},
    }


@router.post("/builder/preview", response_class=HTMLResponse)
def builder_preview(payload: dict):
    cv_data = payload.get("cv_data") or {}
    title = str(payload.get("title") or "CV Preview")
    return _render_builder_html(cv_data=cv_data, title=title)


@router.get("/builder/{cv_id}/preview", response_class=HTMLResponse)
def builder_preview_saved(
    cv_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        cv_uuid = uuid.UUID(cv_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cv_id")
    doc = db.query(CVDocument).filter(CVDocument.id == cv_uuid).first()
    if not doc:
        raise HTTPException(status_code=404, detail="CV not found")
    if str(doc.user_id) != user_id:
        raise HTTPException(status_code=403, detail="Not your CV")
    title = (doc.filename or "CV Preview").replace(".json", "")
    return _render_builder_html(cv_data=doc.extracted_data or {}, title=title)