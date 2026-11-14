import uuid

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.core.database import SessionDep
from app.modules.auth.dependencies import CurrentUser
from app.modules.curriculum import service
from app.modules.curriculum.models import Subject

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
    area_id: uuid.UUID  # the topic area (parent topic) this skill belongs to
    area_name: str


@router.get("/subjects")
async def list_subjects(_: CurrentUser, session: SessionDep) -> list[SubjectOut]:
    rows = await session.scalars(select(Subject).order_by(Subject.name))
    return [SubjectOut(id=s.id, name=s.name, slug=s.slug) for s in rows]


@router.get("/topics")
async def list_topics(_: CurrentUser, session: SessionDep) -> list[TopicOut]:
    """Topics that have approved practice questions, in learning order."""
    return [
        TopicOut(
            id=t.id,
            subject_id=t.subject_id,
            name=t.name,
            grade_band=t.grade_band,
            question_count=t.question_count,
            area_id=t.area_id,
            area_name=t.area_name,
        )
        for t in await service.lesson_topics(session)
    ]
