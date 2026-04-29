import uuid
from sqlalchemy import String, Text, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    role_name: Mapped[str] = mapped_column(String(120), nullable=False)

    # Bilingual question text — both always populated (AI translates the missing one)
    question_text_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_text_ar: Mapped[str | None] = mapped_column(Text, nullable=True)

    # technical | soft | general | behavioral
    question_type: Mapped[str] = mapped_column(String(30), default="technical", nullable=False)

    difficulty: Mapped[int] = mapped_column(Integer, default=1)  # 1..5

    # seed | community | ai_generated
    source: Mapped[str] = mapped_column(String(30), default="seed")

    # community contribution tracking
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="approved", nullable=False)  # approved | pending | rejected
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # optional: target company
    company: Mapped[str | None] = mapped_column(String(150), nullable=True)

    # which language the user originally wrote in
    original_language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)

    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )

    @property
    def question_text(self) -> str:
        """Backward-compatible: returns English text by default."""
        return self.question_text_en or self.question_text_ar or ""

    def get_text(self, language: str = "en") -> str:
        """Get question text in the specified language."""
        if language == "ar":
            return self.question_text_ar or self.question_text_en or ""
        return self.question_text_en or self.question_text_ar or ""