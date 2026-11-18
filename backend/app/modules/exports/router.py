"""PDF downloads of quizzes and study materials (phase 7). Owner only; nothing is stored.

The PDFs are small and take well under a second to build, so they are made on request
(in a worker thread, off the event loop) instead of through the job queue.
"""

import re
import uuid
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Response
from fastapi.concurrency import run_in_threadpool

from app.core.audit import record_audit
from app.core.database import SessionDep
from app.core.errors import Conflict
from app.modules.auth.dependencies import StudentUser
from app.modules.documents.models import Document
from app.modules.exports.pdf import QuizItem, material_pdf, quiz_pdf
from app.modules.materials import service as materials
from app.modules.quizzes import service as quizzes

router = APIRouter(tags=["exports"])


def _pdf_response(data: bytes, title: str) -> Response:
    name = f"{title[:80]}.pdf"
    ascii_name = re.sub(r"[^A-Za-z0-9._ -]", "_", name) or "mentora.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"
            ),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/quizzes/{quiz_id}/export")
async def export_quiz(
    quiz_id: uuid.UUID,
    student: StudentUser,
    session: SessionDep,
    version: Literal["student", "teacher"] = "student",
) -> Response:
    """The quiz as a PDF. "student": questions only, never answers. "teacher": with the
    answer key, explanations and pages."""
    quiz = await quizzes._own_quiz(session, student, quiz_id)
    if quiz.status != "ready":
        raise Conflict("This quiz is not ready yet.", code="quiz_not_ready")
    doc = await session.get(Document, quiz.document_id)
    items = [
        QuizItem(q.question_type, q.prompt, q.answer_data, q.explanation, list(q.source_pages))
        for q in await quizzes._questions(session, quiz.id)
    ]
    teacher = version == "teacher"
    data = await run_in_threadpool(
        quiz_pdf,
        quiz.title,
        doc.title if doc else "",
        items,
        teacher=teacher,
        minutes=quiz.settings.get("time_limit_minutes", 0),
    )
    record_audit(session, actor_id=student.id, action="export", entity="quiz", entity_id=quiz.id)
    await session.commit()
    return _pdf_response(data, f"{quiz.title}{' - answers' if teacher else ''}")


@router.get("/materials/{material_id}/export")
async def export_material(
    material_id: uuid.UUID, student: StudentUser, session: SessionDep
) -> Response:
    """A summary, study guide or flashcard sheet as a PDF."""
    m = await materials._own(session, student, material_id)
    if m.status != "ready" or not m.content:
        raise Conflict("This is not ready yet.", code="material_not_ready")
    doc = await session.get(Document, m.document_id)
    data = await run_in_threadpool(
        material_pdf, m.title, doc.title if doc else "", m.kind, m.content
    )
    record_audit(session, actor_id=student.id, action="export", entity="material", entity_id=m.id)
    await session.commit()
    return _pdf_response(data, m.title)
