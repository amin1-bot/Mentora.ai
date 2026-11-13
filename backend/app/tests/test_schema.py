"""Checks the migrated database matches the blueprint. Run `alembic upgrade head` first."""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.db_models import Base

EXPECTED_TABLES = {
    "users", "student_profiles", "guardian_links",
    "subjects", "topics", "topic_prerequisites", "misconceptions", "questions",
    "learning_sessions", "messages", "question_attempts", "topic_mastery", "mastery_events",
    "ai_requests", "audit_log",
}


def _query(sql: str) -> list[tuple]:
    async def run() -> list[tuple]:
        engine = create_async_engine(get_settings().database_url)
        try:
            async with engine.connect() as conn:
                return [tuple(r) for r in (await conn.execute(text(sql))).all()]
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_models_define_the_15_mvp_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_migrated_database_has_all_tables() -> None:
    rows = _query(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    )
    assert EXPECTED_TABLES <= {r[0] for r in rows}


def test_every_table_has_created_at() -> None:
    rows = _query(
        "SELECT table_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND column_name = 'created_at'"
    )
    assert EXPECTED_TABLES <= {r[0] for r in rows}


def test_student_data_is_deleted_with_the_user() -> None:
    """Deletion really deletes: every FK from student data to users cascades."""
    rows = _query(
        """
        SELECT tc.table_name, kcu.column_name, rc.delete_rule
        FROM information_schema.referential_constraints rc
        JOIN information_schema.table_constraints tc ON tc.constraint_name = rc.constraint_name
        JOIN information_schema.key_column_usage kcu ON kcu.constraint_name = rc.constraint_name
        JOIN information_schema.constraint_column_usage ccu
             ON ccu.constraint_name = rc.constraint_name
        WHERE ccu.table_name = 'users'
        """
    )
    rules = {(t, c): rule for t, c, rule in rows}
    assert rules.pop(("audit_log", "actor_id")) == "SET NULL"
    assert rules, "expected foreign keys to users"
    assert all(rule == "CASCADE" for rule in rules.values()), rules
