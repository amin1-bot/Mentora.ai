import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAt, UUIDPrimaryKey

SESSION_STATUSES = ("active", "ended")
MESSAGE_ROLES = ("student", "teacher", "system")


class LearningSession(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "learning_sessions"
    __table_args__ = (
        CheckConstraint(f"status IN {SESSION_STATUSES}", name="status_valid"),
        Index("ix_learning_sessions_student_topic", "student_id", "topic_id"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="RESTRICT"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="active")


class Message(UUIDPrimaryKey, CreatedAt, Base):
    """One turn in a lesson. `whiteboard` holds validated board blocks, never HTML."""

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(f"role IN {MESSAGE_ROLES}", name="role_valid"),
        Index("ix_messages_session_created", "session_id", "created_at"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    whiteboard: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
