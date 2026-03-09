from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class CVQuizGenerateRequest(BaseModel):
    role_id: UUID | None = None
    max_questions: int = 12


class CVQuizQuestion(BaseModel):
    question: str
    options: list[str]
    correct_index: int
    skill: str
    difficulty: str
    category: str


class CVQuizGenerateResponse(BaseModel):
    quiz_id: UUID
    cv_id: UUID
    role_id: UUID | None
    title: str | None
    questions: list[dict]


class CVQuizAnswerItem(BaseModel):
    question_index: int
    selected_index: int


class CVQuizSubmitRequest(BaseModel):
    answers: list[CVQuizAnswerItem]


class CVQuizSubmitResponse(BaseModel):
    attempt_id: UUID
    quiz_id: UUID
    overall_score: int
    result_json: dict


class CVQuizListItemResponse(BaseModel):
    quiz_id: UUID
    cv_id: UUID
    role_id: UUID | None
    title: str | None
    question_count: int
    created_at: datetime