import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.cv import CVDocument
from app.models.cv_quiz import CVQuiz, CVQuizAttempt
from app.models.role import Role
from app.schemas.cv_quiz import (
    CVQuizGenerateRequest,
    CVQuizGenerateResponse,
    CVQuizSubmitRequest,
    CVQuizSubmitResponse,
    CVQuizListItemResponse,
)
from app.services.cv_quiz_service import (
    generate_questions_from_cv,
    score_quiz_submission,
    generate_quiz_feedback,
)

router = APIRouter(prefix="/cv", tags=["cv-quiz"])


@router.post("/{cv_id}/quiz/generate", response_model=CVQuizGenerateResponse)
def generate_cv_quiz(
    cv_id: str,
    payload: CVQuizGenerateRequest,
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

    role = None
    role_name = None
    if payload.role_id:
        role = db.query(Role).filter(Role.id == payload.role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
        role_name = role.name

    questions = generate_questions_from_cv(
        raw_text=doc.raw_text or "",
        extracted_data=doc.extracted_data or {},
        role_name=role_name,
        max_questions=payload.max_questions,
        language=doc.language,
    )

    quiz = CVQuiz(
        cv_id=doc.id,
        role_id=role.id if role else None,
        title=f"CV Skill Quiz - {role_name}" if role_name else "CV Skill Quiz",
        questions_json=questions,
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)

    return CVQuizGenerateResponse(
        quiz_id=quiz.id,
        cv_id=quiz.cv_id,
        role_id=quiz.role_id,
        title=quiz.title,
        questions=quiz.questions_json or [],
    )


@router.post("/quizzes/{quiz_id}/submit", response_model=CVQuizSubmitResponse)
def submit_cv_quiz(
    quiz_id: str,
    payload: CVQuizSubmitRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        quiz_uuid = uuid.UUID(quiz_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid quiz_id")

    quiz = db.query(CVQuiz).filter(CVQuiz.id == quiz_uuid).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    doc = db.query(CVDocument).filter(CVDocument.id == quiz.cv_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Parent CV not found")

    if str(doc.user_id) != user_id:
        raise HTTPException(status_code=403, detail="Not your quiz")

    role_name = None
    if quiz.role_id:
        role = db.query(Role).filter(Role.id == quiz.role_id).first()
        if role:
            role_name = role.name

    result = score_quiz_submission(
        questions=quiz.questions_json or [],
        answers=[a.model_dump() for a in payload.answers],
    )

    feedback = generate_quiz_feedback(result=result, role_name=role_name)
    result["feedback"] = feedback

    attempt = CVQuizAttempt(
        quiz_id=quiz.id,
        user_id=uuid.UUID(user_id),
        answers_json=[a.model_dump() for a in payload.answers],
        result_json=result,
        overall_score=result.get("overall_score"),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return CVQuizSubmitResponse(
        attempt_id=attempt.id,
        quiz_id=quiz.id,
        overall_score=attempt.overall_score or 0,
        result_json=attempt.result_json or {},
    )


@router.get("/{cv_id}/quizzes", response_model=list[CVQuizListItemResponse])
def list_cv_quizzes(
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

    quizzes = (
        db.query(CVQuiz)
        .filter(CVQuiz.cv_id == doc.id)
        .order_by(CVQuiz.created_at.desc())
        .all()
    )

    return [
        CVQuizListItemResponse(
            quiz_id=q.id,
            cv_id=q.cv_id,
            role_id=q.role_id,
            title=q.title,
            question_count=len(q.questions_json or []),
            created_at=q.created_at,
        )
        for q in quizzes
    ]