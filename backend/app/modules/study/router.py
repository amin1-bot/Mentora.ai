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
from app.modules.study import service
from app.modules.study.schemas import ChatOut, ChatTurnIn

router = APIRouter(prefix="/documents/{document_id}/chat", tags=["study"])


@router.get("")
async def get_chat(document_id: uuid.UUID, student: StudentUser, session: SessionDep) -> ChatOut:
    """Your conversation about this document (owner only)."""
    return await service.get_chat(session, student, document_id)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
async def clear_chat(document_id: uuid.UUID, student: StudentUser, session: SessionDep) -> Response:
    """Start over: deletes the conversation's messages."""
    await service.clear_chat(session, student, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _sse(events: AsyncIterator[dict[str, Any]]) -> AsyncIterator[str]:
    async for e in events:
        yield f"event: {e['event']}\ndata: {json.dumps(e['data'])}\n\n"


@router.post(
    "/messages",
    dependencies=[Depends(require_csrf)],
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def ask(
    document_id: uuid.UUID,
    body: ChatTurnIn,
    student: StudentUser,
    session: SessionDep,
    provider: Annotated[AIProvider | None, Depends(get_ai_provider)],
) -> StreamingResponse:
    """Ask about the document; the reply streams as Server-Sent Events.

    Events: `status`, `delta`, `reset`, `done` {message}, `error` {code, message}.
    """
    plan = await service.prepare_turn(session, student, document_id, body.text)
    return StreamingResponse(
        _sse(service.stream_turn(plan, provider)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
