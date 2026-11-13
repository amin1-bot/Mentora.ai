import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAt, UUIDPrimaryKey


class AuditLog(UUIDPrimaryKey, CreatedAt, Base):
    """Who accessed or changed sensitive data. Entries outlive the actor's account."""

    __tablename__ = "audit_log"

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "read", "delete"
    entity: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "student_profile"
    entity_id: Mapped[uuid.UUID | None] = mapped_column()


def record_audit(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity: str,
    entity_id: uuid.UUID | None,
) -> None:
    """Add an audit entry to the current transaction (saved when the caller commits)."""
    session.add(AuditLog(actor_id=actor_id, action=action, entity=entity, entity_id=entity_id))
