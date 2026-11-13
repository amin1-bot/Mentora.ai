import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAt, UUIDPrimaryKey

USER_ROLES = ("student", "guardian", "teacher", "admin")


class User(UUIDPrimaryKey, CreatedAt, Base):
    """Every person who can log in. Parent of every user-owned table."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(f"role IN {USER_ROLES}", name="role_valid"),
        CheckConstraint("failed_login_count >= 0", name="failed_logins_non_negative"),
    )

    # Always stored lower-case, so Ali@x.com and ali@x.com are the same account.
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    # Argon2id hash only; the password itself is never stored.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    # Login protection: temporary lockout after repeated wrong passwords.
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshToken(CreatedAt, Base):
    """One row per issued refresh token, so logout and theft detection can revoke it."""

    __tablename__ = "refresh_tokens"

    # The token's jti claim. Only the id is stored, never the token itself.
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
