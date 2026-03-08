import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi import APIRouter, UploadFile, File
from app.core.security import bearer_scheme
from sqlalchemy.orm import Session

from app.services.cv_service import (
    _supabase_storage_upload,
    extract_text,
    llm_extract_structured_cv,
)
from app.services.supabase_storage import create_signed_url

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.cv import CVDocument, CVEvaluation
from app.models.role import Role
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

    # 1) upload raw file to Supabase Storage
    obj_id = uuid.uuid4().hex
    safe_name = (file.filename or "cv").replace("/", "_").replace("\\", "_")
    object_path = f"{user_id}/{obj_id}_{safe_name}"

    storage_ref = _supabase_storage_upload(
        bucket="cvs",
        object_path=object_path,
        content=content,
        content_type=file.content_type or "application/octet-stream",
        user_jwt=user_jwt,
    )

    # 2) extract text (pdf/docx)
    raw_text, language = extract_text(file, content)

    # 3) LLM -> structured JSON
    extracted = llm_extract_structured_cv(raw_text=raw_text, language=language)

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