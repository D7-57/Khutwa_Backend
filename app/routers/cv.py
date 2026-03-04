import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.core.security import bearer_scheme, get_current_user_id
from app.db.session import get_db
from app.models.cv import CVDocument
from app.services.cv_service import (
    _supabase_storage_upload,
    extract_text,
    llm_extract_structured_cv,
)

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