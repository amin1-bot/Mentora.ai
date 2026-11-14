"""The curriculum other modules may read: teachable topics, their areas and prerequisites."""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.curriculum.models import Question, Topic, TopicPrerequisite


@dataclass(frozen=True)
class LessonTopic:
    """A topic with approved questions, so it can be taught."""

    id: uuid.UUID
    subject_id: uuid.UUID
    name: str
    grade_band: str
    question_count: int
    area_id: uuid.UUID  # the parent topic, or the topic itself when it has no parent
    area_name: str
    needs: tuple[uuid.UUID, ...]  # prerequisite topics (a recommendation, never a lock)


async def lesson_topics(db: AsyncSession) -> list[LessonTopic]:
    """Teachable topics in learning order: topics come after what they need first."""
    count = func.count(Question.id)
    rows = (
        await db.execute(
            select(Topic, count)
            .join(Question, (Question.topic_id == Topic.id) & Question.is_approved)
            .group_by(Topic.id)
        )
    ).all()
    parent_ids = {t.parent_topic_id for t, _ in rows if t.parent_topic_id}
    parents = {t.id: t for t in await db.scalars(select(Topic).where(Topic.id.in_(parent_ids)))}
    needs: dict[uuid.UUID, list[uuid.UUID]] = {}
    for p in await db.scalars(select(TopicPrerequisite)):
        needs.setdefault(p.topic_id, []).append(p.prerequisite_topic_id)

    topics = []
    for t, n in rows:
        area = parents.get(t.parent_topic_id) if t.parent_topic_id else None
        topics.append(
            LessonTopic(
                id=t.id,
                subject_id=t.subject_id,
                name=t.name,
                grade_band=t.grade_band,
                question_count=n,
                area_id=area.id if area else t.id,
                area_name=area.name if area else t.name,
                needs=tuple(needs.get(t.id, ())),
            )
        )
    depth = _depths(needs)
    return sorted(topics, key=lambda t: (t.area_name, depth.get(t.id, 0), t.name))


def _depths(needs: dict[uuid.UUID, list[uuid.UUID]]) -> dict[uuid.UUID, int]:
    """Length of the longest chain of prerequisites before each topic."""
    memo: dict[uuid.UUID, int] = {}

    def depth(topic: uuid.UUID, seen: frozenset[uuid.UUID]) -> int:
        if topic in memo:
            return memo[topic]
        if topic in seen:  # a loop in the data: stop rather than recurse forever
            return 0
        before = [depth(n, seen | {topic}) + 1 for n in needs.get(topic, [])]
        memo[topic] = max(before, default=0)
        return memo[topic]

    for topic in needs:
        depth(topic, frozenset())
    return memo
