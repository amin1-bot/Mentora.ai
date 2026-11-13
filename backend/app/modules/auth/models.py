from sqlalchemy import Boolean, CheckConstraint, String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAt, UUIDPrimaryKey

USER_ROLES = ("student", "guardian", "teacher", "admin")


class User(UUIDPrimaryKey, CreatedAt, Base):
    """Every person who can log in. Parent of every user-owned table."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(f"role IN {USER_ROLES}", name="role_valid"),
    )

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    # Argon2id hash only; the password itself is never stored (Phase 3).
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
