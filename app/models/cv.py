import uuid
from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CVDocument(Base):
    __tablename__ = "cv_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    raw_file_url: Mapped[str] = mapped_column(Text, nullable=False)

    filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    language: Mapped[str] = mapped_column(Text, nullable=False, default="en")

    extracted_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    parser_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())

    evaluations: Mapped[list["CVEvaluation"]] = relationship(
        back_populates="cv",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CVEvaluation(Base):
    __tablename__ = "cv_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    cv_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cv_documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    role_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="SET NULL"),
        nullable=True,
    )

    target_role: Mapped[str] = mapped_column(Text, nullable=False)

    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ats_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    evaluation_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())

    cv: Mapped["CVDocument"] = relationship(back_populates="evaluations")