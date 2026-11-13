import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAt, UUIDPrimaryKey


class QuestionAttempt(UUIDPrimaryKey, CreatedAt, Base):
    """One answer to one question, with the misconception it revealed (if any)."""

    __tablename__ = "question_attempts"
    __table_args__ = (
        CheckConstraint("hints_used >= 0", name="hints_non_negative"),
        CheckConstraint("time_ms IS NULL OR time_ms >= 0", name="time_non_negative"),
        Index("ix_question_attempts_student_question", "student_id", "question_id"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False
    )
    student_answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    misconception_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("misconceptions.id", ondelete="SET NULL")
    )
    hints_used: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    time_ms: Mapped[int | None] = mapped_column(Integer)


class TopicMastery(CreatedAt, Base):
    """How well one student knows one topic. Drives every teaching decision."""

    __tablename__ = "topic_mastery"
    __table_args__ = (
        CheckConstraint("mastery_score BETWEEN 0 AND 1", name="score_range"),
        CheckConstraint("difficulty_level BETWEEN 1 AND 5", name="difficulty_range"),
        CheckConstraint("correct <= attempts", name="correct_le_attempts"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    mastery_score: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")
    difficulty_level: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    correct: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    streak: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_practiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MasteryEvent(UUIDPrimaryKey, CreatedAt, Base):
    """History of every mastery change, for progress charts and tuning the model later."""

    __tablename__ = "mastery_events"
    __table_args__ = (
        Index("ix_mastery_events_student_topic", "student_id", "topic_id"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    old_score: Mapped[float] = mapped_column(Float, nullable=False)
    new_score: Mapped[float] = mapped_column(Float, nullable=False)
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_attempts.id", ondelete="SET NULL")
    )
