from pydantic import BaseModel
from uuid import UUID


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