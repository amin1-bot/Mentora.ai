"""All database queries for accounts and login tokens."""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import RefreshToken, User


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email.lower()))


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def email_exists(session: AsyncSession, email: str) -> bool:
    return await session.scalar(select(User.id).where(User.email == email.lower())) is not None


def add_user(session: AsyncSession, *, email: str, password_hash: str, role: str) -> User:
    user = User(id=uuid.uuid4(), email=email.lower(), password_hash=password_hash, role=role)
    session.add(user)
    return user


def add_refresh_token(
    session: AsyncSession, *, jti: uuid.UUID, user_id: uuid.UUID, expires_at: datetime
) -> None:
    session.add(RefreshToken(id=jti, user_id=user_id, expires_at=expires_at))


async def get_refresh_token(session: AsyncSession, jti: uuid.UUID) -> RefreshToken | None:
    return await session.get(RefreshToken, jti)


async def revoke_all_refresh_tokens(
    session: AsyncSession, user_id: uuid.UUID, now: datetime
) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
