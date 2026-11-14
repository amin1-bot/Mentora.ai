"""Writes the question bank from seed_data.py into the database.

Used by the seed migrations and by the test setup, so every database has the same rows.
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
        _upsert(Subject, d.SUBJECTS, ["name", "slug"]),
        _upsert(Topic, d.TOPICS, ["subject_id", "parent_topic_id", "name", "grade_band"]),
        insert(TopicPrerequisite).values(prerequisites).on_conflict_do_nothing(),
        _upsert(Misconception, misconceptions, ["topic_id", "description"]),
        _upsert(
            Question,
            d.QUESTIONS,
            ["topic_id", "difficulty", "text", "answer_data", "source", "is_approved"],
        ),
        update(Question)
        .where(Question.source == "bank", Question.id.not_in([q["id"] for q in d.QUESTIONS]))
        .values(is_approved=False),
    ]
