"""Quizzes from your documents (multi-subject plan, phase 5): create, play, grade, report.

Rules (each has a test in test_quizzes.py):
- Everything is private to the owner; someone else's quiz or attempt is "not found".
- Answers never reach the browser before the question is answered.
- Grading is done by code (the same checkers as the question bank), never by the AI.
- A time limit is enforced by the server, not only shown by the page.
- Each question is answered once per attempt.
"""

import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import Conflict, NotFound, TooManyRequests, Unprocessable
from app.modules.adaptive.checkers import LETTERS, checker_for
from app.modules.auth.models import User
from app.modules.documents import service as documents
from app.modules.documents.models import DocumentChunk
from app.modules.jobs.queue import enqueue
from app.modules.quizzes import generation
from app.modules.quizzes.models import Quiz, QuizAnswer, QuizAttempt, QuizQuestion
from app.modules.quizzes.schemas import (
    AnswerIn,
    AttemptOut,
    AttemptQuestion,
    Feedback,
    QuizCreate,
    QuizOut,
    Report,
    ReviewPage,
)
from app.modules.study.service import ai_notice

GRACE = timedelta(seconds=5)  # network delay allowance on timed quizzes


def _now() -> datetime:
    return datetime.now(UTC)


# ---------- quizzes ----------


async def _quiz_out(db: AsyncSession, quiz: Quiz, student_id: uuid.UUID) -> QuizOut:
    count = await db.scalar(
        select(func.count(QuizQuestion.id)).where(QuizQuestion.quiz_id == quiz.id)
    )
    best, attempts = (
        await db.execute(
            select(func.max(QuizAttempt.score), func.count(QuizAttempt.id)).where(
                QuizAttempt.quiz_id == quiz.id, QuizAttempt.student_id == student_id
            )
        )
    ).one()
    s = quiz.settings
    return QuizOut(
        id=quiz.id,
        document_id=quiz.document_id,
        title=quiz.title,
        status=quiz.status,
        error_code=quiz.error_code,
        question_count=count or 0,
        count_requested=s["count"],
        types=s["types"],
        difficulty=s.get("difficulty", "mixed"),
        page_from=s.get("page_from"),
        page_to=s.get("page_to"),
        time_limit_minutes=s.get("time_limit_minutes", 0),
        best_score=best,
        attempts=attempts or 0,
        created_at=quiz.created_at,
    )


async def _own_quiz(db: AsyncSession, user: User, quiz_id: uuid.UUID) -> Quiz:
    quiz = await db.scalar(select(Quiz).where(Quiz.id == quiz_id, Quiz.owner_id == user.id))
    if quiz is None:
        raise NotFound("Quiz not found.", code="quiz_not_found")
    return quiz


async def create(db: AsyncSession, user: User, document_id: uuid.UUID, data: QuizCreate) -> QuizOut:
    doc = await documents.get_owned(db, user, document_id)
    if doc.status != "ready" or not doc.pages_with_text:
        raise Conflict(
            "This document has no readable text yet, so a quiz cannot be written from it.",
            code="document_not_ready",
        )
    pages = doc.page_count or 0
    if (data.page_from and data.page_from > pages) or (data.page_to and data.page_to > pages):
        raise Unprocessable(f"This document has {pages} pages.", code="pages_out_of_range")
    ai_notice()  # private documents never go to an AI that may train on them
    since = _now() - timedelta(days=1)
    made_today = await db.scalar(
        select(func.count(Quiz.id)).where(Quiz.owner_id == user.id, Quiz.created_at >= since)
    )
    if (made_today or 0) >= get_settings().quiz_daily_limit:
        raise TooManyRequests(
            "You've made a lot of quizzes today. Practise with the ones you have, and make "
            "more tomorrow.",
            code="quiz_daily_limit",
        )
    pages_label = ""
    if data.page_from or data.page_to:
        pages_label = f" (pages {data.page_from or 1}–{data.page_to or pages})"
    quiz = Quiz(
        owner_id=user.id,
        document_id=doc.id,
        title=f"{doc.title}{pages_label}"[:200],
        settings=data.model_dump(),
        status="generating",
    )
    db.add(quiz)
    await db.flush()
    enqueue(db, generation.JOB_KIND, {"quiz_id": str(quiz.id)}, user_id=user.id)
    await db.commit()
    await db.refresh(quiz)
    return await _quiz_out(db, quiz, user.id)


async def list_for_document(db: AsyncSession, user: User, document_id: uuid.UUID) -> list[QuizOut]:
    doc = await documents.get_owned(db, user, document_id)
    quizzes = await db.scalars(
        select(Quiz)
        .where(Quiz.document_id == doc.id, Quiz.owner_id == user.id)
        .order_by(Quiz.created_at.desc())
    )
    return [await _quiz_out(db, q, user.id) for q in quizzes]


async def get(db: AsyncSession, user: User, quiz_id: uuid.UUID) -> QuizOut:
    return await _quiz_out(db, await _own_quiz(db, user, quiz_id), user.id)


async def delete(db: AsyncSession, user: User, quiz_id: uuid.UUID) -> None:
    await db.delete(await _own_quiz(db, user, quiz_id))
    await db.commit()


# ---------- attempts ----------


async def _questions(db: AsyncSession, quiz_id: uuid.UUID) -> list[QuizQuestion]:
    return list(
        await db.scalars(
            select(QuizQuestion)
            .where(QuizQuestion.quiz_id == quiz_id)
            .order_by(QuizQuestion.position)
        )
    )


async def _own_attempt(db: AsyncSession, user: User, attempt_id: uuid.UUID) -> QuizAttempt:
    attempt = await db.scalar(
        select(QuizAttempt).where(QuizAttempt.id == attempt_id, QuizAttempt.student_id == user.id)
    )
    if attempt is None:
        raise NotFound("Attempt not found.", code="attempt_not_found")
    return attempt


async def start(db: AsyncSession, user: User, quiz_id: uuid.UUID) -> AttemptOut:
    """Continue an unfinished attempt, or start a new one."""
    quiz = await _own_quiz(db, user, quiz_id)
    if quiz.status != "ready":
        raise Conflict("This quiz is not ready yet.", code="quiz_not_ready")
    open_attempt = await db.scalar(
        select(QuizAttempt).where(
            QuizAttempt.quiz_id == quiz.id,
            QuizAttempt.student_id == user.id,
            QuizAttempt.finished_at.is_(None),
        )
    )
    if open_attempt is not None and not _expired(open_attempt):
        return await attempt_out(db, open_attempt)
    if open_attempt is not None:
        await _finish(db, open_attempt)
    questions = await _questions(db, quiz.id)
    minutes = quiz.settings.get("time_limit_minutes", 0)
    now = _now()
    attempt = QuizAttempt(
        quiz_id=quiz.id,
        student_id=user.id,
        started_at=now,
        deadline=now + timedelta(minutes=minutes) if minutes else None,
        total=len(questions),
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return await attempt_out(db, attempt)


def _expired(attempt: QuizAttempt) -> bool:
    return attempt.deadline is not None and _now() > attempt.deadline + GRACE


def _display(q: QuizQuestion, value: int | bool | str) -> str:
    if q.question_type == "multiple_choice" and isinstance(value, int):
        options = q.answer_data["options"]
        return f"{LETTERS[value]}) {options[value]}" if 0 <= value < len(options) else str(value)
    if q.question_type == "true_false":
        return "True" if value else "False"
    return str(value)


def _correct_display(q: QuizQuestion) -> str:
    if q.question_type == "multiple_choice":
        return _display(q, q.answer_data["correct_index"])
    if q.question_type == "true_false":
        return _display(q, q.answer_data["value"])
    return q.answer_data["answers"][0]


def _feedback(q: QuizQuestion, a: QuizAnswer) -> Feedback:
    return Feedback(
        is_correct=a.is_correct,
        your_answer=a.answer,
        correct_answer=_correct_display(q),
        explanation=q.explanation,
        source_pages=list(q.source_pages),
    )


async def attempt_out(db: AsyncSession, attempt: QuizAttempt) -> AttemptOut:
    quiz = await db.get(Quiz, attempt.quiz_id)
    assert quiz is not None
    questions = await _questions(db, quiz.id)
    answers = {
        a.question_id: a
        for a in await db.scalars(select(QuizAnswer).where(QuizAnswer.attempt_id == attempt.id))
    }
    return AttemptOut(
        id=attempt.id,
        quiz_id=quiz.id,
        quiz_title=quiz.title,
        document_id=quiz.document_id,
        started_at=attempt.started_at,
        deadline=attempt.deadline,
        finished_at=attempt.finished_at,
        questions=[
            AttemptQuestion(
                id=q.id,
                position=q.position,
                question_type=q.question_type,  # type: ignore[arg-type]
                prompt=q.prompt,
                options=list(q.answer_data["options"])
                if q.question_type == "multiple_choice"
                else None,
                feedback=_feedback(q, answers[q.id]) if q.id in answers else None,
            )
            for q in questions
        ],
        report=await _report(db, attempt, questions, answers) if attempt.finished_at else None,
    )


async def get_attempt(db: AsyncSession, user: User, attempt_id: uuid.UUID) -> AttemptOut:
    attempt = await _own_attempt(db, user, attempt_id)
    if attempt.finished_at is None and _expired(attempt):
        await _finish(db, attempt)
    return await attempt_out(db, attempt)


def _interpret(q: QuizQuestion, value: int | bool | str) -> int | bool | str:
    """The answer in the type's own form, or a 422 if it does not fit the question."""
    if q.question_type == "multiple_choice":
        if isinstance(value, bool) or not isinstance(value, int):
            raise Unprocessable("Choose one of the options.", code="invalid_answer")
        if not 0 <= value < len(q.answer_data["options"]):
            raise Unprocessable("Choose one of the options.", code="invalid_answer")
        return value
    if q.question_type == "true_false":
        if not isinstance(value, bool):
            raise Unprocessable("Answer true or false.", code="invalid_answer")
        return value
    if not isinstance(value, str) or not value:
        raise Unprocessable("Type the missing word or words.", code="invalid_answer")
    return value


async def answer(db: AsyncSession, user: User, attempt_id: uuid.UUID, data: AnswerIn) -> Feedback:
    attempt = await _own_attempt(db, user, attempt_id)
    if attempt.finished_at is not None:
        raise Conflict("This attempt is finished.", code="attempt_finished")
    if _expired(attempt):
        await _finish(db, attempt)
        raise Conflict("Time is up for this quiz.", code="time_up")
    q = await db.scalar(
        select(QuizQuestion).where(
            QuizQuestion.id == data.question_id, QuizQuestion.quiz_id == attempt.quiz_id
        )
    )
    if q is None:
        raise NotFound("Question not found.", code="question_not_found")
    value = _interpret(q, data.answer)
    checker = checker_for(q.question_type)
    if q.question_type == "fill_blank":
        said = checker.interpret(str(value), q.answer_data) or generation.norm(str(value))
        is_correct = checker.check(q.answer_data, said).is_correct or any(
            generation.norm(str(value)) == generation.norm(a) for a in q.answer_data["answers"]
        )
    else:
        is_correct = checker.check(q.answer_data, value).is_correct
    a = QuizAnswer(
        attempt_id=attempt.id,
        question_id=q.id,
        answer=_display(q, value)[:300],
        is_correct=is_correct,
    )
    db.add(a)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise Conflict("You already answered this question.", code="already_answered") from exc
    return _feedback(q, a)


async def finish(db: AsyncSession, user: User, attempt_id: uuid.UUID) -> AttemptOut:
    attempt = await _own_attempt(db, user, attempt_id)
    if attempt.finished_at is None:
        await _finish(db, attempt)
    return await attempt_out(db, attempt)


async def _finish(db: AsyncSession, attempt: QuizAttempt) -> None:
    correct = await db.scalar(
        select(func.count(QuizAnswer.id)).where(
            QuizAnswer.attempt_id == attempt.id, QuizAnswer.is_correct.is_(True)
        )
    )
    now = _now()
    attempt.finished_at = min(now, attempt.deadline + GRACE) if attempt.deadline else now
    attempt.score = correct or 0
    await db.commit()


async def _report(
    db: AsyncSession,
    attempt: QuizAttempt,
    questions: list[QuizQuestion],
    answers: dict[uuid.UUID, QuizAnswer],
) -> Report:
    by_type: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})
    missed_pages: Counter[int] = Counter()
    for q in questions:
        a = answers.get(q.id)
        by_type[q.question_type]["total"] += 1
        if a is not None and a.is_correct:
            by_type[q.question_type]["correct"] += 1
        else:
            missed_pages.update(q.source_pages)
    quiz = await db.get(Quiz, attempt.quiz_id)
    headings: dict[int, str] = {}
    if quiz is not None and missed_pages:
        for c in await db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == quiz.document_id)
            .order_by(DocumentChunk.position)
        ):
            if c.heading:
                for p in range(c.page_start, c.page_end + 1):
                    headings.setdefault(p, c.heading)
    score = attempt.score or 0
    total = attempt.total or len(questions)
    finished = attempt.finished_at or _now()
    return Report(
        score=score,
        total=total,
        answered=len(answers),
        percent=round(100 * score / total) if total else 0,
        seconds=max(0, int((finished - attempt.started_at).total_seconds())),
        by_type=dict(by_type),
        review_pages=[
            ReviewPage(page=p, heading=headings.get(p), missed=n)
            for p, n in sorted(missed_pages.items(), key=lambda x: (-x[1], x[0]))
        ],
        timed_out=bool(attempt.deadline and len(answers) < total and finished >= attempt.deadline),
    )
