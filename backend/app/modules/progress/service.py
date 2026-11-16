"""The student's progress: mastery per skill, grouped by topic area, plus what to do next.

Reads only through other modules' services (curriculum, adaptive), never their tables.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.adaptive import mastery
from app.modules.adaptive import service as adaptive
from app.modules.auth.models import User
from app.modules.curriculum import service as curriculum
from app.modules.students import service as students


class SkillProgress(BaseModel):
    id: uuid.UUID
    name: str
    course_level: str | None  # school / university / professional
    grade_band: str
    question_count: int
    mastery: float  # 0..1
    level: mastery.Level
    questions_done: int  # questions finished (solved, or solution shown)
    questions_solved: int
    last_practiced_at: datetime | None
    needs_first: list[str]  # prerequisite skills not yet at "practising" (advice only)
    history: list[float]  # recent mastery scores, oldest first


class AreaProgress(BaseModel):
    id: uuid.UUID
    name: str
    mastery: float  # average over the area's skills
    skills: list[SkillProgress]


class ProgressOut(BaseModel):
    areas: list[AreaProgress]
    # The skill to practise next, or None when everything is mastered.
    recommended_skill_id: uuid.UUID | None


def _matches_level(course_level: str | None, grade_level: int) -> bool:
    """School courses suit grades 1-12; university and professional courses suit grade 13
    (university or adult). Topics outside any course suit everyone."""
    if course_level is None:
        return True
    return (course_level == "school") == (grade_level <= 12)


async def progress_for(db: AsyncSession, student: User) -> ProgressOut:
    student_id = student.id
    grade = (await students.get_profile(db, student, student.id)).grade_level
    topics = await curriculum.lesson_topics(db)
    # Courses at the student's level come first; everything stays available.
    topics.sort(key=lambda t: not _matches_level(t.course_level, grade))
    saved = await adaptive.masteries_for(db, student_id)
    names = {t.id: t.name for t in topics}

    def score(topic_id: uuid.UUID) -> float:
        row = saved.get(topic_id)
        return row.mastery_score if row else 0.0

    skills: list[tuple[uuid.UUID, SkillProgress]] = []
    for t in topics:
        row = saved.get(t.id)
        done = row.attempts if row else 0
        skills.append(
            (
                t.area_id,
                SkillProgress(
                    id=t.id,
                    name=t.name,
                    course_level=t.course_level,
                    grade_band=t.grade_band,
                    question_count=t.question_count,
                    mastery=score(t.id),
                    level=mastery.level(score(t.id), done),
                    questions_done=done,
                    questions_solved=row.correct if row else 0,
                    last_practiced_at=row.last_practiced_at if row else None,
                    needs_first=[
                        names[n]
                        for n in t.needs
                        if n in names and score(n) < mastery.PRACTISING_FROM
                    ],
                    history=await adaptive.history(db, student_id, t.id) if row else [],
                ),
            )
        )

    areas: dict[uuid.UUID, AreaProgress] = {}
    for t, (area_id, skill) in zip(topics, skills, strict=True):
        area = areas.setdefault(
            area_id, AreaProgress(id=area_id, name=t.area_name, mastery=0.0, skills=[])
        )
        area.skills.append(skill)
    for area in areas.values():
        area.mastery = round(sum(s.mastery for s in area.skills) / len(area.skills), 4)

    return ProgressOut(
        areas=list(areas.values()), recommended_skill_id=_recommend(skills, grade)
    )


def _recommend(skills: list[tuple[uuid.UUID, SkillProgress]], grade: int) -> uuid.UUID | None:
    """The first skill, in learning order, that is not mastered and is ready to learn.

    "Ready" means every prerequisite is at least at "practising". Preference order:
    a skill already started; a ready skill in an area the student has started; a ready
    skill at the student's level; any ready skill; any unmastered skill.
    """
    open_skills = [(a, s) for a, s in skills if s.level != "mastered"]
    ready = [(a, s) for a, s in open_skills if not s.needs_first]
    started_areas = {a for a, s in skills if s.level != "not_started"}
    groups = [
        [s for _, s in ready if s.level != "not_started"],
        [s for a, s in ready if a in started_areas],
        [s for _, s in ready if _matches_level(s.course_level, grade)],
        [s for _, s in ready],
        [s for _, s in open_skills],
    ]
    for group in groups:
        if group:
            return group[0].id
    return None
