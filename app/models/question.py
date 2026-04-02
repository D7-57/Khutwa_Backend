import uuid
from sqlalchemy import String, Text, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    role_name: Mapped[str] = mapped_column(String(120), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)

    # technical | soft | general | behavioral
    question_type: Mapped[str] = mapped_column(String(30), default="technical", nullable=False)

    difficulty: Mapped[int] = mapped_column(Integer, default=1)  # 1..5

    # seed | community | ai_generated
    source: Mapped[str] = mapped_column(String(30), default="seed")

    # community contribution tracking
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="approved", nullable=False)  # approved | pending | rejected

    # optional: target company
    company: Mapped[str | None] = mapped_column(String(150), nullable=True)

    # question language
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)

    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )