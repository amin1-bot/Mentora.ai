"""Writes the catalogue and question bank from seed_data.py into the database.

Run after migrations:  python -m app.modules.curriculum.seed
Also used by the test setup, so every database has the same rows. (Migrations do not seed:
they must not depend on today's models.)
Safe to run any number of times: missing rows are added and changed rows are updated
(e.g. a question moved to another topic keeps its id, so past attempts stay linked).
Bank questions removed from seed_data.py are retired (unapproved), never deleted, because
students' past attempts point at them.
"""

from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert

from app.modules.curriculum import seed_data as d
from app.modules.curriculum.models import (
    Course,
    Discipline,
    LearningObjective,
    Misconception,
    Question,
    Subject,
    Topic,
    TopicPrerequisite,
)


def _upsert(model: Any, rows: list[dict[str, Any]], update: list[str]) -> Any:
    stmt = insert(model).values(rows)
    return stmt.on_conflict_do_update(
        index_elements=["id"], set_={col: stmt.excluded[col] for col in update}
    )


def seed_statements() -> list[Any]:
    misconceptions = [
        {**m, "id": d.seed_id(f"misconception:{m['code']}")} for m in d.MISCONCEPTIONS
    ]
    prerequisites = [
        {"topic_id": topic, "prerequisite_topic_id": needs} for topic, needs in d.PREREQUISITES
    ]
    return [
        _upsert(Discipline, d.DISCIPLINES, ["name", "slug"]),
        _upsert(Subject, d.SUBJECTS, ["discipline_id", "name", "slug", "profile"]),
        _upsert(Course, d.COURSES, ["subject_id", "name", "level"]),
        _upsert(
            Topic, d.TOPICS, ["subject_id", "parent_topic_id", "course_id", "name", "grade_band"]
        ),
        _upsert(LearningObjective, d.LEARNING_OBJECTIVES, ["topic_id", "text", "position"]),
        insert(TopicPrerequisite).values(prerequisites).on_conflict_do_nothing(),
        _upsert(Misconception, misconceptions, ["topic_id", "description"]),
        _upsert(
            Question,
            d.QUESTIONS,
            [
                "topic_id",
                "learning_objective_id",
                "question_type",
                "difficulty",
                "text",
                "answer_data",
                "explanation",
                "source",
                "is_approved",
            ],
        ),
        update(Question)
        .where(Question.source == "bank", Question.id.not_in([q["id"] for q in d.QUESTIONS]))
        .values(is_approved=False),
    ]


async def _main() -> None:
    from app.core.database import engine

    async with engine.begin() as conn:
        for stmt in seed_statements():
            await conn.execute(stmt)
    await engine.dispose()
    print(f"Seeded {len(d.TOPICS)} topics and {len(d.QUESTIONS)} questions.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())
