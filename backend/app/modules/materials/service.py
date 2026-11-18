"""Study materials from your documents (multi-subject plan, phase 6).

Rules (each has a test in test_materials.py):
- Everything is private to the owner; anyone else's material is "not found".
- Content is AI-written but code-checked JSON; every item cites pages that were sent.
- Private documents go to the AI only under the same rule as document study.
- Flashcard reviews follow the spaced-repetition schedule in spaced.py.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import Conflict, NotFound, TooManyRequests, Unprocessable
from app.modules.auth.models import User
from app.modules.documents import service as documents
from app.modules.jobs.queue import enqueue
from app.modules.materials import generation
from app.modules.materials.models import FlashcardReview, StudyMaterial
from app.modules.materials.schemas import (
    MaterialCreate,
    MaterialOut,
    MaterialSummaryOut,
    ReviewCard,
    ReviewIn,
    ReviewOut,
    ReviewResult,
)
from app.modules.materials.spaced import CardState, schedule
from app.modules.study.service import ai_notice

NEW_CARDS_PER_SESSION = 20
KIND_NAMES = {"summary": "Summary", "guide": "Study guide", "flashcards": "Flashcards"}


def _now() -> datetime:
    return datetime.now(UTC)


def _items(m: StudyMaterial) -> int:
    c = m.content or {}
    if m.kind == "summary":
        return sum(len(s["points"]) for s in c.get("sections", []))
    if m.kind == "guide":
        return len(c.get("key_terms", [])) + len(c.get("sections", []))
    return len(c.get("cards", []))


async def _reviews(db: AsyncSession, material_id: uuid.UUID) -> dict[int, FlashcardReview]:
    rows = await db.scalars(
        select(FlashcardReview).where(FlashcardReview.material_id == material_id)
    )
    return {r.card_index: r for r in rows}


async def _due_cards(db: AsyncSession, m: StudyMaterial) -> list[ReviewCard]:
    if m.kind != "flashcards" or m.status != "ready" or not m.content:
        return []
    reviews = await _reviews(db, m.id)
    now = _now()
    due, new = [], []
    for i, card in enumerate(m.content["cards"]):
        r = reviews.get(i)
        item = ReviewCard(
            index=i, front=card["front"], back=card["back"], pages=card["pages"], is_new=r is None
        )
        if r is None:
            new.append(item)
        elif r.due_at <= now:
            due.append((r.due_at, item))
    due.sort(key=lambda x: x[0])
    return [item for _, item in due] + new[:NEW_CARDS_PER_SESSION]


async def _summary(db: AsyncSession, m: StudyMaterial) -> MaterialSummaryOut:
    s = m.settings
    return MaterialSummaryOut(
        id=m.id,
        document_id=m.document_id,
        kind=m.kind,  # type: ignore[arg-type]
        title=m.title,
        status=m.status,
        error_code=m.error_code,
        page_from=s.get("page_from"),
        page_to=s.get("page_to"),
        items=_items(m),
        due_cards=len(await _due_cards(db, m)),
        created_at=m.created_at,
    )


async def _own(db: AsyncSession, user: User, material_id: uuid.UUID) -> StudyMaterial:
    m = await db.scalar(
        select(StudyMaterial).where(
            StudyMaterial.id == material_id, StudyMaterial.owner_id == user.id
        )
    )
    if m is None:
        raise NotFound("Study material not found.", code="material_not_found")
    return m


async def create(
    db: AsyncSession, user: User, document_id: uuid.UUID, data: MaterialCreate
) -> MaterialSummaryOut:
    doc = await documents.get_owned(db, user, document_id)
    if doc.status != "ready" or not doc.pages_with_text:
        raise Conflict(
            "This document has no readable text yet, so nothing can be written from it.",
            code="document_not_ready",
        )
    pages = doc.page_count or 0
    if (data.page_from and data.page_from > pages) or (data.page_to and data.page_to > pages):
        raise Unprocessable(f"This document has {pages} pages.", code="pages_out_of_range")
    ai_notice()  # private documents never go to an AI that may train on them
    made_today = await db.scalar(
        select(func.count(StudyMaterial.id)).where(
            StudyMaterial.owner_id == user.id,
            StudyMaterial.created_at >= _now() - timedelta(days=1),
        )
    )
    if (made_today or 0) >= get_settings().material_daily_limit:
        raise TooManyRequests(
            "You've made a lot of study materials today. Come back tomorrow for more.",
            code="material_daily_limit",
        )
    label = ""
    if data.page_from or data.page_to:
        label = f", pages {data.page_from or 1}–{data.page_to or pages}"
    m = StudyMaterial(
        owner_id=user.id,
        document_id=doc.id,
        kind=data.kind,
        title=f"{KIND_NAMES[data.kind]}: {doc.title}{label}"[:200],
        settings=data.model_dump(),
        status="generating",
    )
    db.add(m)
    await db.flush()
    enqueue(db, generation.JOB_KIND, {"material_id": str(m.id)}, user_id=user.id)
    await db.commit()
    await db.refresh(m)
    return await _summary(db, m)


async def list_for_document(
    db: AsyncSession, user: User, document_id: uuid.UUID
) -> list[MaterialSummaryOut]:
    doc = await documents.get_owned(db, user, document_id)
    rows = await db.scalars(
        select(StudyMaterial)
        .where(StudyMaterial.document_id == doc.id, StudyMaterial.owner_id == user.id)
        .order_by(StudyMaterial.created_at.desc())
    )
    return [await _summary(db, m) for m in rows]


async def get(db: AsyncSession, user: User, material_id: uuid.UUID) -> MaterialOut:
    m = await _own(db, user, material_id)
    return MaterialOut(**(await _summary(db, m)).model_dump(), content=m.content)


async def rename(db: AsyncSession, user: User, material_id: uuid.UUID, title: str) -> MaterialOut:
    m = await _own(db, user, material_id)
    m.title = " ".join(title.split())[:200] or m.title
    await db.commit()
    return await get(db, user, material_id)


async def delete(db: AsyncSession, user: User, material_id: uuid.UUID) -> None:
    await db.delete(await _own(db, user, material_id))
    await db.commit()


# ---------- flashcard review ----------


async def _own_cards(db: AsyncSession, user: User, material_id: uuid.UUID) -> StudyMaterial:
    m = await _own(db, user, material_id)
    if m.kind != "flashcards":
        raise Conflict("Only flashcards can be reviewed.", code="not_flashcards")
    if m.status != "ready" or not m.content:
        raise Conflict("These flashcards are not ready yet.", code="material_not_ready")
    return m


async def review_session(db: AsyncSession, user: User, material_id: uuid.UUID) -> ReviewOut:
    m = await _own_cards(db, user, material_id)
    reviews = await _reviews(db, m.id)
    return ReviewOut(
        due=await _due_cards(db, m),
        total_cards=len(m.content["cards"]),  # type: ignore[index]
        learned=sum(1 for r in reviews.values() if r.reps > 0),
    )


async def review(
    db: AsyncSession, user: User, material_id: uuid.UUID, index: int, data: ReviewIn
) -> ReviewResult:
    m = await _own_cards(db, user, material_id)
    if not 0 <= index < len(m.content["cards"]):  # type: ignore[index]
        raise NotFound("Card not found.", code="card_not_found")
    now = _now()
    row = await db.scalar(
        select(FlashcardReview).where(
            FlashcardReview.material_id == m.id, FlashcardReview.card_index == index
        )
    )
    state = (
        CardState(row.reps, row.lapses, row.ease, row.interval_days)
        if row is not None
        else CardState()
    )
    new, due_at = schedule(state, data.rating, now)
    if row is None:
        row = FlashcardReview(
            material_id=m.id,
            student_id=user.id,
            card_index=index,
            due_at=due_at,
            last_reviewed_at=now,
        )
        db.add(row)
    row.reps, row.lapses, row.ease, row.interval_days = (
        new.reps,
        new.lapses,
        new.ease,
        new.interval_days,
    )
    row.due_at, row.last_reviewed_at = due_at, now
    try:
        await db.commit()
    except IntegrityError as exc:  # two reviews of a new card at the same moment
        await db.rollback()
        raise Conflict("This card was just reviewed.", code="already_reviewed") from exc
    return ReviewResult(index=index, due_at=due_at, interval_days=new.interval_days)
