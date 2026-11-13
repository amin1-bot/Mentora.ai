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


async def _empty_all_tables() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE {tables} CASCADE"))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def test_database() -> None:
    asyncio.run(_create_test_database())
    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")


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
