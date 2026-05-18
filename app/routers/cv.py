import uuid
from fastapi import  Depends, HTTPException
from fastapi import APIRouter, UploadFile, File
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
from app.models.profile import Profile, _privacy_default
from app.schemas.cv import CVEvaluateRequest, CVEvaluateResponse, JobMatchRequest, JobMatchResponse
from app.services.cv_evaluation import run_full_cv_evaluation, build_role_profile, score_ats, build_radar_scores

router = APIRouter(prefix="/cv", tags=["cv"])


def _require_cv_storage_enabled(db: Session, user_id: str):
    """
    CV persistence guard (PDPL optional consent).

    When cv_storage is OFF we block endpoints that persist or read stored CV
    artifacts. This prevents hidden backfilling when the user toggles consent
    back on later.
    """
    profile = db.get(Profile, uuid.UUID(user_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    settings = profile.privacy_settings or _privacy_default()
    if not settings.get("cv_storage", False):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "PRIVACY_CONSENT_REQUIRED",
                "key": "cv_storage",
                "message": (
                    "CV storage is turned off. Enable it in Settings -> Privacy "
                    "to upload, save, and retrieve CV documents."
                ),
            },
        )



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
    _require_cv_storage_enabled(db, user_id)
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

@router.get("/{cv_id}/evaluations", response_model=list[CVEvaluationItemResponse])
def list_cv_evaluations(
    cv_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    _require_cv_storage_enabled(db, user_id)
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
    _require_cv_storage_enabled(db, user_id)
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
    _require_cv_storage_enabled(db, user_id)
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

@router.delete("/{cv_id}", status_code=204)
def delete_cv(cv_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    doc = db.query(CVDocument).filter(CVDocument.id == uuid.UUID(cv_id)).first()
    if not doc: raise HTTPException(404, "CV not found")
    if str(doc.user_id) != user_id: raise HTTPException(403, "Not your CV")
    db.delete(doc)
    db.commit()


@router.post("/{cv_id}/match-job", response_model=JobMatchResponse)
def match_cv_to_job(
    cv_id: str,
    payload: JobMatchRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Match a CV against a pasted job description.
    Reuses existing build_role_profile + score_ats pipeline.
    """
    try:
        cv_uuid = uuid.UUID(cv_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cv_id")

    doc = db.query(CVDocument).filter(CVDocument.id == cv_uuid).first()
    if not doc:
        raise HTTPException(status_code=404, detail="CV not found")
    if str(doc.user_id) != user_id:
        raise HTTPException(status_code=403, detail="Not your CV")

    # Build role profile from the pasted JD
    role_profile = build_role_profile(
        role_name=payload.job_title or "Target Role",
        role_description=payload.job_description,
    )

    # Score ATS using existing pipeline
    ats = score_ats(
        raw_text=doc.raw_text or "",
        extracted_data=doc.extracted_data or {},
        role_profile=role_profile,
    )

    # Build radar scores from the match
    eval_data = {
        "role_fit": {"score": ats.get("keyword_score", 0)},
        "ats": ats,
    }
    radar = build_radar_scores(eval_data)

    # Determine recommendation
    score = ats["score"]
    if score >= 80:
        recommendation = "Strong match — your CV aligns well with this job description."
    elif score >= 60:
        recommendation = "Good match — consider adding missing keywords to strengthen your application."
    elif score >= 40:
        recommendation = "Moderate match — significant gaps exist. Tailor your CV before applying."
    else:
        recommendation = "Weak match — this role may require skills or experience not reflected in your CV."

    return JobMatchResponse(
        match_score=score,
        matched_keywords=ats["matched_keywords"],
        missing_keywords=ats["missing_keywords"],
        hard_requirement_flags=ats.get("hard_requirement_flags", []),
        recommendation=recommendation,
        radar_scores=radar,
    )