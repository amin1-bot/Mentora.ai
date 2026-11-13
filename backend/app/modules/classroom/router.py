import json
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import StreamingResponse

from app.ai.base import AIProvider
from app.ai.factory import get_ai_provider
from app.core.database import SessionDep
from app.modules.auth.dependencies import StudentUser, require_csrf
from app.modules.classroom import service
from app.modules.classroom.schemas import SessionOut, StartSessionRequest, TurnIn

router = APIRouter(prefix="/sessions", tags=["classroom"])


@router.post("", dependencies=[Depends(require_csrf)])
async def start_session(
    data: StartSessionRequest, response: Response, student: StudentUser, session: SessionDep
) -> SessionOut:
    """Continue the active lesson on a topic, or start a new one (201)."""
    out, created = await service.start_session(session, student, data.topic_id)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return out


@router.get("/{session_id}")
async def get_session(
    session_id: uuid.UUID, student: StudentUser, session: SessionDep
) -> SessionOut:
    return await service.get_session(session, student, session_id)


@router.post("/{session_id}/end", dependencies=[Depends(require_csrf)])
async def end_session(
    session_id: uuid.UUID, student: StudentUser, session: SessionDep
) -> SessionOut:
    return await service.end_session(session, student, session_id)


async def _sse(events: AsyncIterator[dict[str, Any]]) -> AsyncIterator[str]:
    async for e in events:
        yield f"event: {e['event']}\ndata: {json.dumps(e['data'])}\n\n"


@router.post(
    "/{session_id}/messages",
    dependencies=[Depends(require_csrf)],
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def send_message(
    session_id: uuid.UUID,
    body: TurnIn,
    student: StudentUser,
    session: SessionDep,
    provider: Annotated[AIProvider | None, Depends(get_ai_provider)],
) -> StreamingResponse:
    """Send the student's turn and stream the teacher's reply (Server-Sent Events).

    Events: `status` (thinking), `delta` (text to append), `reset` (clear the partial
    reply, a safer version follows), `done` (saved message and lesson state), `error`.
    """
    plan = await service.prepare_turn(session, student, session_id, body)
    return StreamingResponse(
        _sse(service.stream_turn(plan, provider)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
