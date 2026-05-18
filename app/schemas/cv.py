from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class CVEvaluateRequest(BaseModel):
    role_id: UUID


class CVEvaluateResponse(BaseModel):
    evaluation_id: UUID
    cv_id: UUID
    role_id: UUID | None
    target_role: str
    overall_score: int | None
    ats_score: int | None
    evaluation_json: dict
    # Optional achievement awards piggy-backed on the response. Always present
    # in successful responses; empty list when nothing new was earned.
    new_achievements: list[dict] = []


class CVEvaluationItemResponse(BaseModel):
    evaluation_id: UUID
    cv_id: UUID
    role_id: UUID | None
    target_role: str
    overall_score: int | None
    ats_score: int | None
    created_at: datetime


class CVEvaluationDetailResponse(BaseModel):
    evaluation_id: UUID
    cv_id: UUID
    role_id: UUID | None
    target_role: str
    overall_score: int | None
    ats_score: int | None
    evaluation_json: dict
    created_at: datetime

class CVLatestEvaluationSummary(BaseModel):
    evaluation_id: UUID
    target_role: str
    overall_score: int | None
    ats_score: int | None
    created_at: datetime


class CVDocumentListItemResponse(BaseModel):
    cv_id: UUID
    filename: str | None
    mime_type: str | None
    file_size: int | None
    language: str
    created_at: datetime
    latest_evaluation: CVLatestEvaluationSummary | None


class JobMatchRequest(BaseModel):
    job_description: str
    job_title: str | None = None


class JobMatchResponse(BaseModel):
    match_score: int
    matched_keywords: dict
    missing_keywords: dict
    hard_requirement_flags: list[dict]
    recommendation: str
    radar_scores: dict