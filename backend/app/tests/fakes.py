"""TEST-ONLY scripted AI provider. Returns fixed replies so the engine, guard and streaming
can be tested deterministically and for free. It lives in the test folder on purpose:
the product never ships a fake teacher or presents simulated AI as real."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from app.ai.base import (
    AIProviderError,
    BoardBlocks,
    ProviderEvent,
    StructuredRequest,
    StructuredResult,
    TextDelta,
    TurnFinished,
    TurnRequest,
)


@dataclass
class Reply:
    chunks: list[str]
    board: list[dict[str, Any]] | None = None
    stop_reason: str = "end_turn"
    error: str | None = None  # raise AIProviderError(error) instead of answering


@dataclass
class ScriptedProvider:
    replies: list[Reply] = field(default_factory=list)
    default: Reply = field(default_factory=lambda: Reply(["Let's think about it together."]))
    requests: list[TurnRequest] = field(default_factory=list)
    name: str = "scripted"
    # Structured answers (quizzes): each item is returned in turn as the parsed JSON;
    # an AIProviderError instance is raised instead.
    structured: list[Any] = field(default_factory=list)
    structured_requests: list[StructuredRequest] = field(default_factory=list)

    async def generate_structured(self, request: StructuredRequest) -> StructuredResult:
        self.structured_requests.append(request)
        data = self.structured.pop(0) if self.structured else None
        if isinstance(data, AIProviderError):
            raise data
        return StructuredResult(data, "scripted-model", "end_turn", 900, 400)

    async def stream_turn(self, request: TurnRequest) -> AsyncIterator[ProviderEvent]:
        self.requests.append(request)
        reply = self.replies.pop(0) if self.replies else self.default
        if reply.error:
            raise AIProviderError(reply.error)
        for chunk in reply.chunks:
            yield TextDelta(chunk)
        if reply.board is not None:
            yield BoardBlocks(reply.board)
        yield TurnFinished("scripted-model", reply.stop_reason, tokens_in=120, tokens_out=30)

    @property
    def last_instruction(self) -> str:
        return self.requests[-1].messages[-1].content
