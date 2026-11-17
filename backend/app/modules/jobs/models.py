import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAt, UUIDPrimaryKey

JOB_STATUSES = ("queued", "running", "done", "failed")


class Job(UUIDPrimaryKey, CreatedAt, Base):
    """Background work kept in PostgreSQL (no Redis or Celery until load needs them).

    A worker claims one due job at a time with SELECT ... FOR UPDATE SKIP LOCKED, so two
    workers never pick the same job. Payloads hold ids only, never file contents."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(f"status IN {JOB_STATUSES}", name="status_valid"),
        Index("ix_jobs_status_run_after", "status", "run_after"),
    )

    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # A short reason for developers (an exception type), never user content.
    error: Mapped[str | None] = mapped_column(String(300))
    # Whose work this is, so it disappears with their account.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
