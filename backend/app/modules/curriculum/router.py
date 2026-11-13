import uuid

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.database import SessionDep
from app.modules.auth.dependencies import CurrentUser
from app.modules.curriculum.models import Question, Subject, Topic

router = APIRouter(tags=["curriculum"])


class SubjectOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


class TopicOut(BaseModel):
    id: uuid.UUID
    subject_id: uuid.UUID
    name: str
    grade_band: str
    question_count: int


@router.get("/subjects")
async def list_subjects(_: CurrentUser, session: SessionDep) -> list[SubjectOut]:
    rows = await session.scalars(select(Subject).order_by(Subject.name))
    return [SubjectOut(id=s.id, name=s.name, slug=s.slug) for s in rows]


@router.get("/topics")
async def list_topics(_: CurrentUser, session: SessionDep) -> list[TopicOut]:
    """Topics that have approved practice questions (others cannot be taught yet)."""
    count = func.count(Question.id)
    rows = await session.execute(
        select(Topic, count)
        .join(Question, (Question.topic_id == Topic.id) & Question.is_approved)
        .group_by(Topic.id)
        .order_by(Topic.name)
    )
    return [
        TopicOut(
            id=t.id,
            subject_id=t.subject_id,
            name=t.name,
            grade_band=t.grade_band,
            question_count=n,
        )
        for t, n in rows.all()
    ]
