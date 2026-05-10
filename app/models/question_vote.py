"""
Per-user vote on a community-submitted question.
Two votes per user max (upvote OR downvote, not both — enforced by UNIQUE).

Used for community moderation: pending questions get auto-promoted to
'approved' once they collect enough upvotes, or auto-rejected when the
ratio is too negative. The actual flip happens in a Postgres trigger
(see migration 001_v2_interview_rework.sql) so the logic is consistent
no matter where the vote comes from.
"""

import uuid
from sqlalchemy import SmallInteger, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class QuestionVote(Base):
    __tablename__ = "question_votes"
    __table_args__ = (
        UniqueConstraint("question_id", "user_id", name="uq_question_votes_q_u"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # +1 = like, -1 = dislike. Stored as smallint for compactness.
    vote: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class QuestionRelevanceFeedback(Base):
    """
    Live in-interview "was this question relevant?" feedback. Independent
    from community votes so the user can flag a bad question without
    polluting the moderation signal — but a later background job can
    aggregate this into community votes if we want.
    """

    __tablename__ = "question_relevance_feedback"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "question_id", "user_id",
            name="uq_relevance_session_q_user",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    relevant: Mapped[bool] = mapped_column(nullable=False)

    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
