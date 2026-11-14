"""Saved mastery: what other modules call to read or change a student's skill levels.

Changes are added to the caller's database session but never committed here, so a lesson
turn that fails (for example, the AI is down) leaves mastery exactly as it was.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.adaptive import mastery
from app.modules.adaptive import repository as repo
from app.modules.adaptive.engine import QuestionResult
from app.modules.adaptive.models import MasteryEvent, TopicMastery

HISTORY_POINTS = 12  # mastery changes shown per skill on the progress page


async def current_mastery(db: AsyncSession, student_id: uuid.UUID, topic_id: uuid.UUID) -> float:
    row = await repo.get_mastery(db, student_id, topic_id)
    return row.mastery_score if row else 0.0


async def next_difficulty(db: AsyncSession, student_id: uuid.UUID, topic_id: uuid.UUID) -> int:
    return mastery.target_difficulty(await current_mastery(db, student_id, topic_id))


async def record_question(
    db: AsyncSession,
    *,
    student_id: uuid.UUID,
    topic_id: uuid.UUID,
    difficulty: int,
    result: QuestionResult,
    attempt_id: uuid.UUID | None,
) -> float:
    """Update mastery after a finished question. Returns the new score."""
    row = await repo.get_mastery(db, student_id, topic_id)
    if row is None:
        row = TopicMastery(
            student_id=student_id,
            topic_id=topic_id,
            mastery_score=0.0,
            difficulty_level=1,
            attempts=0,
            correct=0,
            streak=0,
        )
        db.add(row)
    old = row.mastery_score
    outcome = mastery.question_outcome(
        solved=result.solved, wrong_tries=result.wrong_tries, hints_used=result.hints_used
    )
    new = mastery.update(old, difficulty, outcome)

    row.mastery_score = new
    row.difficulty_level = mastery.target_difficulty(new)
    row.attempts += 1  # questions finished
    first_try = result.solved and result.wrong_tries == 0 and result.hints_used == 0
    row.correct += 1 if result.solved else 0
    row.streak = row.streak + 1 if first_try else 0
    row.last_practiced_at = datetime.now(UTC)
    db.add(
        MasteryEvent(
            student_id=student_id,
            topic_id=topic_id,
            old_score=old,
            new_score=new,
            attempt_id=attempt_id,
        )
    )
    return new


async def masteries_for(db: AsyncSession, student_id: uuid.UUID) -> dict[uuid.UUID, TopicMastery]:
    return {m.topic_id: m for m in await repo.masteries_for(db, student_id)}


async def history(db: AsyncSession, student_id: uuid.UUID, topic_id: uuid.UUID) -> list[float]:
    """Recent mastery scores for one skill, oldest first (for a small trend line)."""
    events = await repo.recent_events(db, student_id, topic_id, HISTORY_POINTS)
    return [e.new_score for e in events]
