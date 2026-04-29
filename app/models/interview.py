import uuid
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    role_name: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False, default="en")

    # ── session configuration ──
    question_source: Mapped[str] = mapped_column(Text, nullable=False, default="bank")
    company: Mapped[str | None] = mapped_column(Text, nullable=True)
    tech_ratio: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    use_cv: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_rapid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── flow control ──
    phase: Mapped[str] = mapped_column(Text, nullable=False, default="intro")
    current_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    followup_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_sq_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # ── intro evaluation ──
    intro_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    intro_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    intro_evaluation_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── overall ──
    total_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session_questions: Mapped[list["SessionQuestion"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SessionQuestion(Base):
    __tablename__ = "session_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ── CHANGED: nullable for CV-generated questions that aren't in the bank ──
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id"),
        nullable=True,  # was nullable=False
    )

    # ── NEW: stores question text directly for CV-generated questions ──
    # When question_id is set, this can be null (text comes from the Question row).
    # When question_id is null (CV question), this holds the text.
    question_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    question_type: Mapped[str | None] = mapped_column(Text, nullable=True)

    user_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    evaluation_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    session: Mapped["InterviewSession"] = relationship(back_populates="session_questions")

    def get_question_text(self, db) -> str:
        """Get question text — from this row if CV-generated, or from the Question table."""
        if self.question_text:
            return self.question_text
        if self.question_id:
            from app.models.question import Question
            q = db.get(Question, self.question_id)
            if q:
                return q.question_text
        return ""
