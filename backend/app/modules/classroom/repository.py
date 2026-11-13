"""All database queries for lessons: sessions, messages, attempts and AI usage."""

import random
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.adaptive.models import QuestionAttempt
from app.modules.classroom.models import LearningSession, Message
from app.modules.curriculum.models import Misconception, Question, Topic


async def get_session(db: AsyncSession, session_id: uuid.UUID) -> LearningSession | None:
    return await db.get(LearningSession, session_id)


async def active_session_for(
    db: AsyncSession, student_id: uuid.UUID, topic_id: uuid.UUID
) -> LearningSession | None:
    return await db.scalar(
        select(LearningSession)
        .where(
            LearningSession.student_id == student_id,
            LearningSession.topic_id == topic_id,
            LearningSession.status == "active",
        )
        .order_by(LearningSession.started_at.desc())
        .limit(1)
    )


async def get_topic(db: AsyncSession, topic_id: uuid.UUID) -> Topic | None:
    return await db.get(Topic, topic_id)


async def get_question(db: AsyncSession, question_id: uuid.UUID | None) -> Question | None:
    return await db.get(Question, question_id) if question_id else None


async def topic_has_questions(db: AsyncSession, topic_id: uuid.UUID) -> bool:
    found = await db.scalar(
        select(Question.id).where(Question.topic_id == topic_id, Question.is_approved).limit(1)
    )
    return found is not None


async def messages_for(db: AsyncSession, session_id: uuid.UUID) -> list[Message]:
    rows = await db.scalars(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at, Message.id)
    )
    return list(rows)


async def recent_messages(db: AsyncSession, session_id: uuid.UUID, limit: int) -> list[Message]:
    rows = await db.scalars(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
    )
    return list(reversed(list(rows)))


async def student_messages_today(db: AsyncSession, student_id: uuid.UUID) -> int:
    start_of_day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    count = await db.scalar(
        select(func.count(Message.id))
        .join(LearningSession, LearningSession.id == Message.session_id)
        .where(
            LearningSession.student_id == student_id,
            Message.role == "student",
            Message.created_at >= start_of_day,
        )
    )
    return count or 0


async def misconception_by_code(db: AsyncSession, code: str) -> Misconception | None:
    return await db.scalar(select(Misconception).where(Misconception.code == code))


async def pick_question(
    db: AsyncSession,
    *,
    topic_id: uuid.UUID,
    session_id: uuid.UUID,
    difficulty: int,
    exclude: set[uuid.UUID],
    avoid_answers: set[float],
) -> Question | None:
    """An approved question near the target difficulty, preferring ones not yet tried."""
    questions = list(
        await db.scalars(
            select(Question).where(Question.topic_id == topic_id, Question.is_approved)
        )
    )
    tried = set(
        await db.scalars(
            select(QuestionAttempt.question_id).where(QuestionAttempt.session_id == session_id)
        )
    )

    def usable(q: Question) -> bool:
        return q.id not in exclude and float(q.answer_data["value"]) not in avoid_answers

    candidates = [q for q in questions if usable(q) and q.id not in tried] or [
        q for q in questions if usable(q)
    ]
    if not candidates:
        return None
    best = min(abs(q.difficulty - difficulty) for q in candidates)
    return random.choice([q for q in candidates if abs(q.difficulty - difficulty) == best])
