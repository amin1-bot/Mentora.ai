"""Test setup: a separate `mentora_test` database, emptied before every test.

The environment variables below are set before the app is imported, so tests can never
touch the development database.
"""

import os

TEST_DB_NAME = "mentora_test"
_SERVER = "mentora:mentora_local_only@localhost:5432"
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = f"postgresql+asyncpg://{_SERVER}/{TEST_DB_NAME}"

import asyncio  # noqa: E402
from collections.abc import Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import asyncpg  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.core.email import Email, _outbox  # noqa: E402
from app.core.rate_limit import auth_limiter  # noqa: E402
from app.db_models import Base  # noqa: E402
from app.tests.fakes import ScriptedProvider  # noqa: E402
from app.tests.helpers import new_client  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[2]


async def _create_test_database() -> None:
    conn = await asyncpg.connect(f"postgresql://{_SERVER}/postgres")
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB_NAME)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        await conn.close()


# Seeded by migrations (the approved question bank) and only read by the app: kept.
CURRICULUM_TABLES = {"subjects", "topics", "topic_prerequisites", "misconceptions", "questions"}


async def _empty_all_tables() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    tables = ", ".join(
        f'"{t.name}"' for t in Base.metadata.sorted_tables if t.name not in CURRICULUM_TABLES
    )
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE {tables} CASCADE"))
    finally:
        await engine.dispose()


async def _ensure_curriculum_seed() -> None:
    """Same rows as the seed migrations (added or updated, never removed)."""
    from app.modules.curriculum.seed import seed_statements

    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        async with engine.begin() as conn:
            for stmt in seed_statements():
                await conn.execute(stmt)
    finally:
        await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def test_database() -> None:
    asyncio.run(_create_test_database())
    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")
    asyncio.run(_ensure_curriculum_seed())


@pytest.fixture(autouse=True)
def clean_state(test_database: None) -> None:
    asyncio.run(_empty_all_tables())
    auth_limiter.reset()
    _outbox.sent.clear()


@pytest.fixture
def outbox() -> list[Email]:
    return _outbox.sent


@pytest.fixture
def client() -> Iterator[TestClient]:
    with new_client() as c:
        yield c


@pytest.fixture
def teacher() -> Iterator[ScriptedProvider]:
    """The scripted stand-in for the AI model, used by every lesson test."""
    from app.ai.factory import get_ai_provider
    from app.main import app

    provider = ScriptedProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_ai_provider, None)
