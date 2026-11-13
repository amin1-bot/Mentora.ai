"""Database engine, sessions and the shared base class for all tables.

Every request gets its own AsyncSession through the `get_session` dependency.
Table definitions live in each module's models.py and inherit from `Base`.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated

from fastapi import Depends
from sqlalchemy import DateTime, MetaData, func, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

# Predictable constraint names, so Alembic migrations are stable and readable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPrimaryKey:
    """UUID ids cannot be guessed or counted by outsiders."""

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )


class CreatedAt:
    """Every table records when a row was created, in UTC."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


_settings = get_settings()
engine = create_async_engine(
    _settings.database_url,
    pool_pre_ping=True,
    # Tests run each client on its own event loop, so connections must not be shared.
    poolclass=NullPool if _settings.environment == "test" else None,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    async with SessionLocal() as session:
        yield session


# Use in route signatures:  async def route(session: SessionDep): ...
SessionDep = Annotated[AsyncSession, Depends(get_session)]
