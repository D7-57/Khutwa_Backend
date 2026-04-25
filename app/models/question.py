import uuid
from sqlalchemy import String, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    role_name: Mapped[str] = mapped_column(String(120), nullable=False)   # MVP: simple
    difficulty: Mapped[int] = mapped_column(Integer, default=1)          # 1..5
    # Current DB schema stores bilingual text, not a single question_text column.
    question_text_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_text_ar: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[str] = mapped_column(String(30), default="seed")       # seed/community

    @property
    def question_text(self) -> str:
        """Backward-compatible unified text accessor used by older code paths."""
        return (self.question_text_en or self.question_text_ar or "").strip()
