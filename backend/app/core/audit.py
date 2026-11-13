import uuid

from sqlalchemy import ForeignKey, String
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
