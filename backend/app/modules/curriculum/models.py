import uuid
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, SmallInteger, String, Text, false
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAt, UUIDPrimaryKey

QUESTION_SOURCES = ("bank", "ai")


class Subject(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "subjects"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class Topic(UUIDPrimaryKey, CreatedAt, Base):
    """Topics form a tree inside a subject (e.g. Percentages under Number)."""

    __tablename__ = "topics"

    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_topic_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    grade_band: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "6-7"


class TopicPrerequisite(CreatedAt, Base):
    """Fractions before percentages: topic_id needs prerequisite_topic_id first."""

    __tablename__ = "topic_prerequisites"
    __table_args__ = (
        CheckConstraint("topic_id <> prerequisite_topic_id", name="not_self"),
    )

    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    prerequisite_topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )


class Misconception(UUIDPrimaryKey, CreatedAt, Base):
    """A known wrong idea, e.g. code 'percent_no_divide_100' for 25% of 80 = 2000."""

    __tablename__ = "misconceptions"
    __table_args__ = (
        CheckConstraint("code <> ''", name="code_not_empty"),
    )

    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class Question(UUIDPrimaryKey, CreatedAt, Base):
    """A practice question. AI-written questions start unapproved."""

    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="difficulty_range"),
        CheckConstraint(f"source IN {QUESTION_SOURCES}", name="source_valid"),
    )

    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    difficulty: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Shape varies by question type (number, expression, multiple choice), hence JSONB.
    answer_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(String(10), nullable=False, server_default="bank")
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
