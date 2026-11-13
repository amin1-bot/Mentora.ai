import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAt, UUIDPrimaryKey

GUARDIAN_LINK_STATUSES = ("pending", "approved", "revoked")


class StudentProfile(CreatedAt, Base):
    """One-to-one with users. Never sent to the AI model (names and birth dates stay here)."""

    __tablename__ = "student_profiles"
    __table_args__ = (
        CheckConstraint("grade_level BETWEEN 1 AND 12", name="grade_level_range"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    grade_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False, server_default="en")


class GuardianLink(UUIDPrimaryKey, CreatedAt, Base):
    """Links a student to a guardian and records their consent."""

    __tablename__ = "guardian_links"
    __table_args__ = (
        UniqueConstraint("student_id", "guardian_id", name="uq_guardian_links_pair"),
        CheckConstraint(f"status IN {GUARDIAN_LINK_STATUSES}", name="status_valid"),
        CheckConstraint("student_id <> guardian_id", name="not_self"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    guardian_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    consent_given_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_version: Mapped[str | None] = mapped_column(String(20))
