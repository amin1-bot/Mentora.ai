import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAt, UUIDPrimaryKey

QUIZ_STATUSES = ("generating", "ready", "failed")
QUIZ_QUESTION_TYPES = ("multiple_choice", "true_false", "fill_blank")


class Quiz(UUIDPrimaryKey, CreatedAt, Base):
    """A practice quiz written by the AI from one of the student's documents. Private to
    its owner; deleted with the document."""

    __tablename__ = "quizzes"
    __table_args__ = (CheckConstraint(f"status IN {QUIZ_STATUSES}", name="status_valid"),)

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # What the student asked for: count, types, difficulty, pages, time limit.
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="generating")
    error_code: Mapped[str | None] = mapped_column(String(50))


class QuizQuestion(UUIDPrimaryKey, CreatedAt, Base):
    """One checked question. `answer_data` has the same shape as the question bank's, so
    the same code checkers grade it. It never leaves the server before it is answered."""

    __tablename__ = "quiz_questions"
    __table_args__ = (
        CheckConstraint(f"question_type IN {QUIZ_QUESTION_TYPES}", name="type_valid"),
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="difficulty_range"),
        UniqueConstraint("quiz_id", "position", name="position_unique"),
    )

    quiz_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    question_type: Mapped[str] = mapped_column(String(20), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    answer_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    source_pages: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False)


class QuizAttempt(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (Index("ix_quiz_attempts_quiz_student", "quiz_id", "student_id"),)

    quiz_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Set from the quiz's time limit when the attempt starts; the server enforces it.
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[int | None] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer, nullable=False)


class QuizAnswer(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "quiz_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="one_per_question"),)

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_questions.id", ondelete="CASCADE"), nullable=False
    )
    answer: Mapped[str] = mapped_column(String(300), nullable=False)  # as the student gave it
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
