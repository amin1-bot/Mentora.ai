"""Studying with your own document (multi-subject plan, phase 4).

One turn:
 1. Checks: the student owns the document, its text is ready, consent is in place, the
    configured AI may receive private documents, the daily limit is not reached.
 2. Safety check on the question (distress never reaches the model).
 3. Retrieval picks the excerpts (retrieval.py), labelled with their pages.
 4. The model streams a grounded reply.
 5. Citations are checked against the pages it was given; invalid ones are removed.
 6. Both messages and the AI cost are saved.

Lessons on topics (classroom/) are separate and unchanged.
"""

import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import AIProvider, TurnRequest
from app.ai.models import AIRequest
from app.core.audit import record_audit
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import Conflict, Forbidden, TooManyRequests
from app.modules.auth.models import User
from app.modules.classroom import repository as classroom_repo
from app.modules.documents import service as documents
from app.modules.documents.models import Document
from app.modules.students import repository as students_repo
from app.modules.students import service as students
from app.modules.study import grounding
from app.modules.study.models import DocumentChat, DocumentChatMessage
from app.modules.study.retrieval import build_context
from app.modules.study.schemas import ChatMessageOut, ChatOut, DocumentRef
from app.modules.teacher.generate import Delta, GenerationResult, Reset, generate_reply
from app.modules.teacher.safety import FALLBACK_RESPONSES, SAFE_RESPONSE, is_distress

logger = logging.getLogger(__name__)

HISTORY_MESSAGES = 8  # earlier turns the model sees (without their excerpts)


def _now() -> datetime:
    return datetime.now(UTC)


# ---------- the AI privacy rule ----------


def ai_notice() -> str | None:
    """Free AI plans may keep or train on what they receive (plan, section 9). Private
    documents go to the model only when AI_PRIVATE_DOCUMENTS=true, which is set for a
    paid plan that does not train on inputs. Local development may use a free plan with
    test documents, and the page shows a clear notice."""
    s = get_settings()
    if s.ai_private_documents:
        return None
    if s.environment in ("local", "test"):
        return "development_only"
    raise Forbidden("Studying with your documents is not available yet.", code="ai_not_private")


# ---------- reading and clearing ----------


def _message_out(m: DocumentChatMessage) -> ChatMessageOut:
    return ChatMessageOut(
        id=m.id,
        role=m.role,  # type: ignore[arg-type]
        content=m.content,
        cited_pages=list(m.cited_pages or []),
        whiteboard=m.whiteboard,
        created_at=m.created_at,
    )


def _document_ref(doc: Document) -> DocumentRef:
    return DocumentRef(
        id=doc.id,
        title=doc.title,
        original_filename=doc.original_filename,
        page_count=doc.page_count,
        pages_with_text=doc.pages_with_text,
    )


async def _chat(db: AsyncSession, student_id: uuid.UUID, document_id: uuid.UUID):
    return await db.scalar(
        select(DocumentChat).where(
            DocumentChat.student_id == student_id, DocumentChat.document_id == document_id
        )
    )


async def _messages(db: AsyncSession, chat_id: uuid.UUID, limit: int | None = None):
    stmt = (
        select(DocumentChatMessage)
        .where(DocumentChatMessage.chat_id == chat_id)
        .order_by(DocumentChatMessage.created_at.desc(), DocumentChatMessage.id.desc())
    )
    if limit:
        stmt = stmt.limit(limit)
    return list(reversed(list(await db.scalars(stmt))))


async def get_chat(db: AsyncSession, student: User, document_id: uuid.UUID) -> ChatOut:
    doc = await documents.get_owned(db, student, document_id)
    chat = await _chat(db, student.id, doc.id)
    msgs = await _messages(db, chat.id) if chat else []
    return ChatOut(
        document=_document_ref(doc),
        messages=[_message_out(m) for m in msgs],
        ai_notice=ai_notice(),
    )


async def clear_chat(db: AsyncSession, student: User, document_id: uuid.UUID) -> None:
    doc = await documents.get_owned(db, student, document_id)
    chat = await _chat(db, student.id, doc.id)
    if chat is not None:
        await db.execute(delete(DocumentChatMessage).where(DocumentChatMessage.chat_id == chat.id))
        await db.commit()


# ---------- one turn ----------


@dataclass(frozen=True)
class TurnPlan:
    chat_id: uuid.UUID
    document_id: uuid.UUID
    student_id: uuid.UUID
    text: str


async def _questions_today(db: AsyncSession, student_id: uuid.UUID) -> int:
    start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    in_chats = await db.scalar(
        select(func.count(DocumentChatMessage.id))
        .join(DocumentChat, DocumentChat.id == DocumentChatMessage.chat_id)
        .where(
            DocumentChat.student_id == student_id,
            DocumentChatMessage.role == "student",
            DocumentChatMessage.created_at >= start,
        )
    )
    # One daily limit for lessons and documents together.
    return (in_chats or 0) + await classroom_repo.student_messages_today(db, student_id)


async def prepare_turn(
    db: AsyncSession, student: User, document_id: uuid.UUID, text: str
) -> TurnPlan:
    """Every check that can fail with a normal HTTP error, before the stream starts."""
    doc = await documents.get_owned(db, student, document_id)
    if await students.consent_status(db, student.id) == "pending":
        raise Forbidden(
            "A parent or guardian needs to approve your account first.", code="consent_required"
        )
    if doc.status != "ready":
        raise Conflict(
            "This document is still being read. Try again in a moment.",
            code="document_not_ready",
        )
    if not doc.pages_with_text:
        raise Conflict(
            "This document has no readable text yet (it looks scanned).", code="document_no_text"
        )
    ai_notice()  # raises when private documents may not go to this AI
    if await _questions_today(db, student.id) >= get_settings().daily_message_limit:
        raise TooManyRequests(
            "That's a lot of learning for one day! Take a break and come back tomorrow.",
            code="daily_limit",
        )
    chat = await _chat(db, student.id, doc.id)
    if chat is None:
        chat = DocumentChat(student_id=student.id, document_id=doc.id)
        db.add(chat)
        await db.commit()
    return TurnPlan(chat.id, doc.id, student.id, text)


def _event(name: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"event": name, "data": data}


async def stream_turn(plan: TurnPlan, provider: AIProvider | None) -> AsyncIterator[dict[str, Any]]:
    """Its own database session: the request's session may close while streaming."""
    async with SessionLocal() as db:
        async for event in _run_turn(db, plan, provider):
            yield event


async def _save(db: AsyncSession, chat_id: uuid.UUID, role: str, content: str, **extra: Any):
    m = DocumentChatMessage(
        id=uuid.uuid4(), chat_id=chat_id, role=role, content=content, created_at=_now(), **extra
    )
    db.add(m)
    await db.commit()
    return m


async def _run_turn(
    db: AsyncSession, plan: TurnPlan, provider: AIProvider | None
) -> AsyncIterator[dict[str, Any]]:
    settings = get_settings()
    doc = await db.get(Document, plan.document_id)
    if doc is None or doc.owner_id != plan.student_id:  # deleted meanwhile
        yield _event("error", {"code": "document_not_found", "message": "Document not found."})
        return

    # 2. Safety first.
    if is_distress(plan.text):
        question = await _save(db, plan.chat_id, "student", plan.text)
        record_audit(
            db,
            actor_id=None,
            action="safety_flag",
            entity="document_chat_message",
            entity_id=question.id,
        )
        reply = await _save(db, plan.chat_id, "teacher", SAFE_RESPONSE)
        yield _event("delta", {"text": SAFE_RESPONSE})
        yield _event("done", {"message": _message_out(reply).model_dump(mode="json")})
        return

    if provider is None:
        yield _event(
            "error",
            {"code": "ai_not_configured", "message": "The AI teacher is not set up yet."},
        )
        return

    earlier = await _messages(db, plan.chat_id, HISTORY_MESSAGES)
    previous_pages = next(
        (list(m.source_pages or []) for m in reversed(earlier) if m.role == "teacher"), []
    )
    question = await _save(db, plan.chat_id, "student", plan.text)

    # 3. Retrieval.
    ctx = await build_context(db, doc, plan.text, previous_pages)
    profile = await students_repo.get_profile(db, plan.student_id)
    grade = profile.grade_level if profile else 13
    history = [(m.role, m.content) for m in earlier]

    def build_request(stricter: bool) -> TurnRequest:
        return TurnRequest(
            system=grounding.SYSTEM_RULES,
            messages=grounding.build_messages(
                history, doc.title, doc.page_count or 0, ctx, plan.text, grade, stricter
            ),
            max_tokens=settings.ai_max_output_tokens,
        )

    # 4. Stream. Nothing secret to protect here, so the leak guard has no answers to hide.
    yield _event("status", {"state": "thinking"})
    result = GenerationResult()
    async for out in generate_reply(provider, build_request, [], result):
        if isinstance(out, Delta):
            yield _event("delta", {"text": out.text})
        elif isinstance(out, Reset):
            yield _event("reset", {})

    if result.fallback in ("unavailable", "not_configured"):
        await db.delete(question)  # nothing was answered: the student can simply retry
        await db.commit()
        code = "ai_not_configured" if result.fallback == "not_configured" else "ai_unavailable"
        yield _event("error", {"code": code, "message": FALLBACK_RESPONSES["unavailable"]})
        return

    # 5. Check citations against the pages the teacher was given.
    checked = grounding.check_citations(result.text, ctx.pages)
    if checked.invalid_citations:
        logger.info(
            "Removed %s citation(s) of pages not given, document %s",
            checked.invalid_citations,
            doc.id,
        )

    # 6. Save.
    for usage, latency in zip(result.usage, result.latency_ms, strict=False):
        db.add(
            AIRequest(
                document_chat_id=plan.chat_id,
                purpose="document_chat",
                model=usage.model,
                tokens_in=usage.tokens_in,
                tokens_out=usage.tokens_out,
                latency_ms=latency,
            )
        )
    reply = await _save(
        db,
        plan.chat_id,
        "teacher",
        checked.text or result.text,
        cited_pages=checked.cited_pages,
        source_pages=sorted(ctx.pages),
        whiteboard=result.board or None,
    )
    yield _event("done", {"message": _message_out(reply).model_dump(mode="json")})
