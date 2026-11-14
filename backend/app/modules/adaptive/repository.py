"""Database queries for mastery. Only adaptive/service.py calls these."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.adaptive.models import MasteryEvent, TopicMastery


async def get_mastery(
    db: AsyncSession, student_id: uuid.UUID, topic_id: uuid.UUID
) -> TopicMastery | None:
    return await db.get(TopicMastery, (student_id, topic_id))


async def masteries_for(db: AsyncSession, student_id: uuid.UUID) -> list[TopicMastery]:
    rows = await db.scalars(select(TopicMastery).where(TopicMastery.student_id == student_id))
    return list(rows)


async def recent_events(
    db: AsyncSession, student_id: uuid.UUID, topic_id: uuid.UUID, limit: int
) -> list[MasteryEvent]:
    rows = await db.scalars(
        select(MasteryEvent)
        .where(MasteryEvent.student_id == student_id, MasteryEvent.topic_id == topic_id)
        .order_by(MasteryEvent.created_at.desc(), MasteryEvent.id.desc())
        .limit(limit)
    )
    return list(reversed(list(rows)))
