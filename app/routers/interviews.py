import random
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.question import Question
from app.models.interview import InterviewSession, SessionQuestion
from app.services.ai_interview import score_answer, next_action
from app.services.tts import synthesize_question_audio
from sqlalchemy import and_

from io import BytesIO
from fastapi.responses import StreamingResponse


router = APIRouter(prefix="/interviews", tags=["interviews"])

@router.post("/start")
def start_interview(
    role_name: str,
    num_questions: int = 5,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)

    # pick questions from DB question bank
    qs = db.query(Question).filter(Question.role_name == role_name).all()
    if not qs:
        raise HTTPException(400, detail="No questions for this role")

    chosen = random.sample(qs, k=min(num_questions, len(qs)))

    session = InterviewSession(user_id=uid, role_name=role_name)
    db.add(session)
    db.flush()

    # create session_questions rows (empty answers initially)
    for q in chosen:
        db.add(SessionQuestion(session_id=session.id, question_id=q.id))

    db.commit()

    first_q = chosen[0]
    return {
        "session_id": str(session.id),
        "question_id": str(first_q.id),
        "question_text": first_q.question_text,
    }

@router.get(
    "/{session_id}/question-audio/{question_id}",
    responses={200: {"content": {"audio/mpeg": {}}}},
)
def question_audio(
    session_id: str,
    question_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    s = db.get(InterviewSession, UUID(session_id))
    if not s or str(s.user_id) != user_id:
        raise HTTPException(404, detail="Session not found")

    q = db.get(Question, UUID(question_id))
    if not q:
        raise HTTPException(404, detail="Question not found")

    audio_bytes = synthesize_question_audio(q.question_text)

    return StreamingResponse(
        BytesIO(audio_bytes),
        media_type="audio/mpeg",
        headers={"Content-Disposition": 'inline; filename="question.mp3"'},
    )

@router.post("/{session_id}/answer")
def submit_answer(
    session_id: str,
    question_id: str,
    answer: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    s = db.get(InterviewSession, UUID(session_id))
    if not s or str(s.user_id) != user_id:
        raise HTTPException(404, detail="Session not found")

    q = db.get(Question, UUID(question_id))
    if not q:
        raise HTTPException(404, detail="Question not found")

    # find the session_question row
    sq = (
        db.query(SessionQuestion)
        .filter(SessionQuestion.session_id == s.id, SessionQuestion.question_id == q.id)
        .first()
    )
    if not sq:
        raise HTTPException(400, detail="Question not in this session")

    evaluation = score_answer(answer=answer, question=q.question_text, role=s.role_name)
    nxt = next_action(question=q.question_text, answer=answer, evaluation=evaluation, role=s.role_name)

    # store per-question results
    sq.user_answer = answer
    sq.score = int(evaluation.get("score", 0))
    sq.ai_feedback = evaluation.get("final_feedback", "")
    sq.evaluation_json = evaluation

    db.commit()

    return {
        "evaluation": evaluation,
        "next_action": nxt,
    }

@router.get("/{session_id}/next")
def get_next_question(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    s = db.get(InterviewSession, UUID(session_id))
    if not s or str(s.user_id) != user_id:
        raise HTTPException(404, detail="Session not found")

    sq = (
        db.query(SessionQuestion)
        .filter(and_(SessionQuestion.session_id == s.id, SessionQuestion.user_answer.is_(None)))
        .first()
    )

    if not sq:
        return {"done": True}

    q = db.get(Question, sq.question_id)
    return {
        "done": False,
        "question_id": str(q.id),
        "question_text": q.question_text,
    }
