import uuid

from fastapi import APIRouter, Depends, Response, status

from app.core.database import SessionDep
from app.modules.auth.dependencies import StudentUser, require_csrf
from app.modules.quizzes import service
from app.modules.quizzes.schemas import AnswerIn, AttemptOut, Feedback, QuizCreate, QuizOut

router = APIRouter(tags=["quizzes"])


@router.post(
    "/documents/{document_id}/quizzes",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_csrf)],
)
async def create_quiz(
    document_id: uuid.UUID, data: QuizCreate, student: StudentUser, session: SessionDep
) -> QuizOut:
    """Ask for a quiz from your document. It is written in the background (status
    "generating"); check back with GET /quizzes/{id}."""
    return await service.create(session, student, document_id, data)


@router.get("/documents/{document_id}/quizzes")
async def list_quizzes(
    document_id: uuid.UUID, student: StudentUser, session: SessionDep
) -> list[QuizOut]:
    return await service.list_for_document(session, student, document_id)


@router.get("/quizzes/{quiz_id}")
async def get_quiz(quiz_id: uuid.UUID, student: StudentUser, session: SessionDep) -> QuizOut:
    return await service.get(session, student, quiz_id)


@router.delete(
    "/quizzes/{quiz_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_quiz(quiz_id: uuid.UUID, student: StudentUser, session: SessionDep) -> Response:
    await service.delete(session, student, quiz_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/quizzes/{quiz_id}/attempts", dependencies=[Depends(require_csrf)])
async def start_attempt(
    quiz_id: uuid.UUID, student: StudentUser, session: SessionDep
) -> AttemptOut:
    """Start the quiz, or continue the attempt you have not finished."""
    return await service.start(session, student, quiz_id)


@router.get("/quiz-attempts/{attempt_id}")
async def get_attempt(
    attempt_id: uuid.UUID, student: StudentUser, session: SessionDep
) -> AttemptOut:
    return await service.get_attempt(session, student, attempt_id)


@router.post("/quiz-attempts/{attempt_id}/answers", dependencies=[Depends(require_csrf)])
async def answer(
    attempt_id: uuid.UUID, data: AnswerIn, student: StudentUser, session: SessionDep
) -> Feedback:
    """Answer one question. The feedback (right answer, explanation, pages) comes back."""
    return await service.answer(session, student, attempt_id, data)


@router.post("/quiz-attempts/{attempt_id}/finish", dependencies=[Depends(require_csrf)])
async def finish(attempt_id: uuid.UUID, student: StudentUser, session: SessionDep) -> AttemptOut:
    """Finish the attempt (unanswered questions count as missed) and get the report."""
    return await service.finish(session, student, attempt_id)
