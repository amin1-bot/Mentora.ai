import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAt, UUIDPrimaryKey

MATERIAL_KINDS = ("summary", "guide", "flashcards")
MATERIAL_STATUSES = ("generating", "ready", "failed")


class StudyMaterial(UUIDPrimaryKey, CreatedAt, Base):
    """A summary, study guide or flashcard set written from one of the student's
    documents. `content` is validated JSON (never HTML); every item cites its pages."""

    __tablename__ = "study_materials"
    __table_args__ = (
        CheckConstraint(f"kind IN {MATERIAL_KINDS}", name="kind_valid"),
        CheckConstraint(f"status IN {MATERIAL_STATUSES}", name="status_valid"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="generating")
    error_code: Mapped[str | None] = mapped_column(String(50))
    content: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class FlashcardReview(UUIDPrimaryKey, CreatedAt, Base):
    """Spaced-repetition state of one card for its owner (cards without a row are new)."""

    __tablename__ = "flashcard_reviews"
    __table_args__ = (
        UniqueConstraint("material_id", "card_index", name="one_per_card"),
        Index("ix_flashcard_reviews_student_due", "student_id", "due_at"),
    )

    material_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("study_materials.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    card_index: Mapped[int] = mapped_column(Integer, nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    lapses: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    ease: Mapped[float] = mapped_column(Float, nullable=False, server_default="2.5")
    interval_days: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
