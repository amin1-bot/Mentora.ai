import uuid
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, SmallInteger, String, Text, false
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAt, UUIDPrimaryKey

QUESTION_SOURCES = ("bank", "ai")
# How an answer is checked (adaptive/checkers.py has one checker per type).
QUESTION_TYPES = ("numeric", "multiple_choice", "true_false", "fill_blank")
COURSE_LEVELS = ("school", "university", "professional")


class Discipline(UUIDPrimaryKey, CreatedAt, Base):
    """A broad field: Mathematics, Business and Management, Medicine, Law, ..."""

    __tablename__ = "disciplines"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class Subject(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "subjects"

    discipline_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("disciplines.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    # Teaching profile (teacher/profiles.py): wording, board use, hints for this subject.
    profile: Mapped[str] = mapped_column(String(30), nullable=False, server_default="general")


class Course(UUIDPrimaryKey, CreatedAt, Base):
    """An optional level between a subject and its topics ("Introduction to MIS")."""

    __tablename__ = "courses"
    __table_args__ = (CheckConstraint(f"level IN {COURSE_LEVELS}", name="level_valid"),)

    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)


class Topic(UUIDPrimaryKey, CreatedAt, Base):
    """Topics form a tree inside a subject (e.g. Percentages under Number)."""

    __tablename__ = "topics"

    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_topic_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), index=True
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    grade_band: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "6-7"


class LearningObjective(UUIDPrimaryKey, CreatedAt, Base):
    """What a student should be able to do after a topic ("Identify a foreign key")."""

    __tablename__ = "learning_objectives"

    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")


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
        CheckConstraint(f"question_type IN {QUESTION_TYPES}", name="question_type_valid"),
    )

    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    learning_objective_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("learning_objectives.id", ondelete="SET NULL")
    )
    question_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="numeric"
    )
    difficulty: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Shown after the question is finished (and used in exported answer keys later).
    explanation: Mapped[str | None] = mapped_column(Text)
    # Shape varies by question type (number, expression, multiple choice), hence JSONB.
    answer_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(String(10), nullable=False, server_default="bank")
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
