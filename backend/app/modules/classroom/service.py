"""Lessons: starting a session, and running one teacher turn.

One turn, in the order of the blueprint's "How one lesson turn flows":
 1. Check access: the student owns the session, consent is in place, daily limit not hit.
 2. Safety check on the student's message (distress never reaches the model).
 3. Code checks the answer and spots a known misconception.
 4. The engine decides the teaching action and, if needed, picks the next question.
 5. The prompt is built from fixed rules, grade level, the action and recent messages.
 6. The model streams its reply through the leak guard; the board is validated.
 7. Messages, the attempt, the new lesson state and AI cost are saved.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import AIProvider, TurnRequest
from app.ai.models import AIRequest
from app.core.audit import record_audit
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import Conflict, Forbidden, NotFound, TooManyRequests
from app.modules.adaptive.answers import AnswerCheck, check_answer, parse_number
from app.modules.adaptive.engine import MAX_HINT, EventKind, LessonState, decide
from app.modules.adaptive.models import QuestionAttempt
from app.modules.auth.models import User
from app.modules.classroom import repository as repo
from app.modules.classroom.models import LearningSession, Message
from app.modules.classroom.schemas import (
    LessonOut,
    MessageOut,
    SessionOut,
    TopicRef,
    TurnIn,
)
from app.modules.curriculum.models import Question
from app.modules.students import repository as students_repo
from app.modules.students import service as students
from app.modules.teacher.generate import Delta, GenerationResult, Reset, generate_reply
from app.modules.teacher.prompts import SYSTEM_RULES, QuestionInfo, TurnContext, build_messages
from app.modules.teacher.safety import FALLBACK_RESPONSES, SAFE_RESPONSE, is_distress

BUTTON_TEXT = {"hint": "Give me a hint", "dont_get_it": "I don't get it"}


def _now() -> datetime:
    return datetime.now(UTC)


# ---------- Access ----------


async def _require_lessons_allowed(db: AsyncSession, student: User) -> None:
    if await students.consent_status(db, student.id) == "pending":
        raise Forbidden(
            "A parent or guardian needs to approve your account before lessons.",
            code="consent_required",
        )


async def _own_session(db: AsyncSession, student: User, session_id: uuid.UUID) -> LearningSession:
    ls = await repo.get_session(db, session_id)
    if ls is None or ls.student_id != student.id:
        raise Forbidden()  # same answer whether it exists or not
    return ls


# ---------- Sessions ----------


async def _lesson_out(db: AsyncSession, ls: LearningSession) -> LessonOut:
    question = await repo.get_question(db, ls.current_question_id)
    return LessonOut(
        has_question=question is not None,
        question_text=question.text if question else None,
        hint_level=ls.hint_level,
        max_hint_level=MAX_HINT,
    )


def _message_out(m: Message) -> MessageOut:
    return MessageOut(
        id=m.id,
        role=m.role,
        content=m.content,
        whiteboard=m.whiteboard,  # type: ignore[arg-type]
        created_at=m.created_at,
    )


async def session_out(db: AsyncSession, ls: LearningSession) -> SessionOut:
    topic = await repo.get_topic(db, ls.topic_id)
    assert topic is not None
    return SessionOut(
        id=ls.id,
        topic=TopicRef(id=topic.id, name=topic.name),
        status=ls.status,
        started_at=ls.started_at,
        lesson=await _lesson_out(db, ls),
        messages=[_message_out(m) for m in await repo.messages_for(db, ls.id)],
    )


async def start_session(
    db: AsyncSession, student: User, topic_id: uuid.UUID
) -> tuple[SessionOut, bool]:
    """Continue the active lesson on this topic, or start a new one. Returns (session, created)."""
    await _require_lessons_allowed(db, student)
    if await repo.get_topic(db, topic_id) is None or not await repo.topic_has_questions(
        db, topic_id
    ):
        raise NotFound("This topic is not available yet.", code="topic_not_found")
    existing = await repo.active_session_for(db, student.id, topic_id)
    if existing:
        return await session_out(db, existing), False
    ls = LearningSession(
        id=uuid.uuid4(), student_id=student.id, topic_id=topic_id, started_at=_now()
    )
    db.add(ls)
    await db.commit()
    await db.refresh(ls)
    return await session_out(db, ls), True


async def get_session(db: AsyncSession, student: User, session_id: uuid.UUID) -> SessionOut:
    return await session_out(db, await _own_session(db, student, session_id))


async def end_session(db: AsyncSession, student: User, session_id: uuid.UUID) -> SessionOut:
    ls = await _own_session(db, student, session_id)
    if ls.status == "active":
        ls.status, ls.ended_at = "ended", _now()
        await db.commit()
    return await session_out(db, ls)


# ---------- One teacher turn ----------


@dataclass(frozen=True)
class TurnPlan:
    session_id: uuid.UUID
    student_id: uuid.UUID
    intent: str
    text: str | None


async def prepare_turn(
    db: AsyncSession, student: User, session_id: uuid.UUID, body: TurnIn
) -> TurnPlan:
    """All checks that can fail with a normal HTTP error, before the stream starts."""
    ls = await _own_session(db, student, session_id)
    await _require_lessons_allowed(db, student)
    if ls.status != "active":
        raise Conflict(
            "This lesson has ended. Start a new one from your topics.", code="session_ended"
        )
    has_messages = bool(await repo.recent_messages(db, ls.id, 1))
    if body.intent == "start" and has_messages:
        raise Conflict("This lesson has already started.", code="already_started")
    if body.intent != "start" and not has_messages:
        raise Conflict("Start the lesson first.", code="not_started")
    if await repo.student_messages_today(db, student.id) >= get_settings().daily_message_limit:
        raise TooManyRequests(
            "That's a lot of maths for one day! Take a break and come back tomorrow.",
            code="daily_limit",
        )
    return TurnPlan(ls.id, student.id, body.intent, body.text)


def _event(name: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"event": name, "data": data}


def _question_info(q: Question | None) -> QuestionInfo | None:
    return QuestionInfo(q.text, float(q.answer_data["value"])) if q else None


async def stream_turn(plan: TurnPlan, provider: AIProvider | None) -> AsyncIterator[dict[str, Any]]:
    """Runs the turn and yields stream events. Uses its own database session, because the
    request's session may be closed while the response is still streaming."""
    async with SessionLocal() as db:
        async for event in _run_turn(db, plan, provider):
            yield event


async def _save_message(
    db: AsyncSession,
    session_id: uuid.UUID,
    role: str,
    content: str,
    whiteboard: list[dict[str, Any]] | None = None,
) -> Message:
    m = Message(
        id=uuid.uuid4(),
        session_id=session_id,
        role=role,
        content=content,
        whiteboard=whiteboard,
        created_at=_now(),
    )
    db.add(m)
    await db.commit()
    return m


async def _run_turn(
    db: AsyncSession, plan: TurnPlan, provider: AIProvider | None
) -> AsyncIterator[dict[str, Any]]:
    settings = get_settings()
    ls = await repo.get_session(db, plan.session_id)
    assert ls is not None
    student_text = plan.text if plan.intent == "message" else BUTTON_TEXT.get(plan.intent)

    # 2. Safety: distress never goes to the model.
    if student_text and is_distress(student_text):
        student_msg = await _save_message(db, ls.id, "student", student_text)
        record_audit(
            db, actor_id=None, action="safety_flag", entity="message", entity_id=student_msg.id
        )
        teacher_msg = await _save_message(db, ls.id, "teacher", SAFE_RESPONSE)
        yield _event("delta", {"text": SAFE_RESPONSE})
        yield _event(
            "done",
            {
                "message": _message_out(teacher_msg).model_dump(mode="json"),
                "lesson": (await _lesson_out(db, ls)).model_dump(mode="json"),
            },
        )
        return

    if provider is None:
        yield _event(
            "error",
            {
                "code": "ai_not_configured",
                "message": "The AI teacher is not set up on this server yet.",
            },
        )
        return

    topic = await repo.get_topic(db, ls.topic_id)
    profile = await students_repo.get_profile(db, plan.student_id)
    assert topic is not None and profile is not None
    current = await repo.get_question(db, ls.current_question_id)

    # 3. Code checks the answer.
    event: EventKind = "start" if plan.intent == "start" else plan.intent  # type: ignore[assignment]
    check: AnswerCheck | None = None
    misconception_text: str | None = None
    if plan.intent == "message" and current is not None and student_text:
        value = parse_number(student_text)
        if value is not None:
            event, check = "answer", check_answer(current.answer_data, value)

    history = [
        {"role": m.role, "content": m.content}
        for m in await repo.recent_messages(db, ls.id, settings.ai_history_messages)
    ]
    student_msg: Message | None = None
    if student_text:
        student_msg = await _save_message(db, ls.id, "student", student_text)
        history.append({"role": "student", "content": student_text})

    if check is not None and current is not None:
        misconception = (
            await repo.misconception_by_code(db, check.misconception_code)
            if check.misconception_code
            else None
        )
        misconception_text = misconception.description if misconception else None
        db.add(
            QuestionAttempt(
                session_id=ls.id,
                student_id=plan.student_id,
                question_id=current.id,
                student_answer=student_text or "",
                is_correct=check.is_correct,
                misconception_id=misconception.id if misconception else None,
                hints_used=ls.hint_level,
            )
        )

    # 4. The engine decides.
    state = LessonState(
        has_question=current is not None,
        hint_level=ls.hint_level,
        attempts_on_current=ls.attempts_on_current,
        wrong_on_current=ls.wrong_on_current,
        difficulty=ls.difficulty,
        correct_streak=ls.correct_streak,
    )
    decision = decide(state, event, check)
    next_q: Question | None = None
    if decision.ask_new_question:
        avoid = {float(current.answer_data["value"])} if current else set()
        next_q = await repo.pick_question(
            db,
            topic_id=topic.id,
            session_id=ls.id,
            difficulty=decision.state.difficulty,
            exclude={current.id} if current else set(),
            avoid_answers=avoid,
        )

    protected: list[float] = []
    if current is not None and not decision.reveal_current_answer:
        protected.append(float(current.answer_data["value"]))
    if next_q is not None:
        protected.append(float(next_q.answer_data["value"]))

    ctx = TurnContext(
        decision=decision,
        grade_level=profile.grade_level,
        topic_name=topic.name,
        current=_question_info(current),
        next_question=_question_info(next_q),
        student_answer=check.value if check else None,
        misconception=misconception_text,
    )

    def build_request(stricter: bool) -> TurnRequest:
        return TurnRequest(
            system=SYSTEM_RULES,
            messages=build_messages(history, replace(ctx, stricter=stricter)),
            max_tokens=settings.ai_max_output_tokens,
        )

    # 6. Stream the reply through the guard.
    yield _event("status", {"state": "thinking"})
    result = GenerationResult()
    async for out in generate_reply(provider, build_request, protected, result):
        if isinstance(out, Delta):
            yield _event("delta", {"text": out.text})
        elif isinstance(out, Reset):
            yield _event("reset", {})

    if result.fallback in ("unavailable", "not_configured"):
        # Nothing was taught: undo the student's message and attempt so they can retry.
        await db.rollback()
        if student_msg is not None:
            await db.delete(student_msg)
            await db.commit()
        code = "ai_not_configured" if result.fallback == "not_configured" else "ai_unavailable"
        yield _event("error", {"code": code, "message": FALLBACK_RESPONSES["unavailable"]})
        return

    board = list(result.board)
    if next_q is not None:
        board.append({"type": "question", "text": next_q.text})

    # 7. Save everything.
    s = decision.state
    ls.hint_level, ls.attempts_on_current, ls.wrong_on_current = (
        s.hint_level,
        s.attempts_on_current,
        s.wrong_on_current,
    )
    ls.difficulty, ls.correct_streak = s.difficulty, s.correct_streak
    if next_q is not None:
        ls.current_question_id = next_q.id
    for usage, latency in zip(result.usage, result.latency_ms, strict=False):
        db.add(
            AIRequest(
                session_id=ls.id,
                model=usage.model,
                tokens_in=usage.tokens_in,
                tokens_out=usage.tokens_out,
                latency_ms=latency,
            )
        )
    teacher_msg = await _save_message(db, ls.id, "teacher", result.text, board or None)
    yield _event(
        "done",
        {
            "message": _message_out(teacher_msg).model_dump(mode="json"),
            "lesson": (await _lesson_out(db, ls)).model_dump(mode="json"),
        },
    )
