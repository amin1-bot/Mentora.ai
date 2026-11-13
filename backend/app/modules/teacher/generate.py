"""Runs one teacher reply through the provider, the leak guard and the board validator.

Shared by the live classroom (classroom/service.py) and the evaluation harness
(backend/eval/run_eval.py), so both measure exactly the same behaviour.
"""

import time
from collections.abc import AsyncIterator, Callable
from contextlib import aclosing
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from app.ai.base import (
    AIProvider,
    AIProviderError,
    BoardBlocks,
    TextDelta,
    TurnFinished,
    TurnRequest,
)
from app.modules.teacher.guard import LeakGuard, filter_board
from app.modules.teacher.safety import FALLBACK_RESPONSES

MAX_ATTEMPTS = 2  # first try + one regeneration after a blocked leak
MAX_BOARD_BLOCKS = 4


class _BlockIn(BaseModel):
    type: Literal["text", "step", "equation"]
    content: str = Field(min_length=1, max_length=300)


def validate_board(raw: list[Any]) -> list[dict[str, Any]]:
    """Keep only well-formed blocks (at most 4), in the model's simple shape."""
    blocks = []
    for item in raw[: MAX_BOARD_BLOCKS * 2]:
        try:
            blocks.append(_BlockIn.model_validate(item).model_dump())
        except ValidationError:
            continue
    return blocks[:MAX_BOARD_BLOCKS]


def to_frontend_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Model shape {type, content} -> the whiteboard shapes the frontend draws."""
    out: list[dict[str, Any]] = []
    step = 0
    for b in blocks:
        if b["type"] == "equation":
            out.append({"type": "equation", "latex": b["content"]})
        elif b["type"] == "step":
            step += 1
            out.append({"type": "step", "number": step, "text": b["content"]})
        else:
            out.append({"type": "text", "text": b["content"]})
    return out


@dataclass(frozen=True)
class Delta:
    text: str


@dataclass(frozen=True)
class Reset:
    """Tells the client to clear the partial reply: a regeneration follows."""


StreamOut = Delta | Reset


@dataclass
class GenerationResult:
    text: str = ""
    board: list[dict[str, Any]] = field(default_factory=list)  # frontend shapes
    usage: list[TurnFinished] = field(default_factory=list)
    latency_ms: list[int] = field(default_factory=list)
    first_text_ms: int | None = None
    blocked_leaks: int = 0  # times the guard stopped a leaking draft
    board_blocks_dropped: int = 0
    fallback: str | None = None  # "leak", "refusal", "unavailable", "not_configured"
    raw_leak_texts: list[str] = field(default_factory=list)  # for the eval report only


async def generate_reply(
    provider: AIProvider,
    build_request: Callable[[bool], TurnRequest],
    protected: list[float],
    result: GenerationResult,
) -> AsyncIterator[StreamOut]:
    started = time.monotonic()
    for attempt in range(MAX_ATTEMPTS):
        guard = LeakGuard(protected)
        raw_blocks: list[Any] = []
        finished: TurnFinished | None = None
        attempt_start = time.monotonic()
        sent_any = False
        try:
            async with aclosing(provider.stream_turn(build_request(attempt > 0))) as events:
                async for event in events:
                    if isinstance(event, TextDelta):
                        safe = guard.feed(event.text)
                        if guard.leaked:
                            break
                        if safe:
                            if result.first_text_ms is None:
                                result.first_text_ms = int((time.monotonic() - started) * 1000)
                            sent_any = True
                            yield Delta(safe)
                    elif isinstance(event, BoardBlocks):
                        raw_blocks = event.blocks
                    elif isinstance(event, TurnFinished):
                        finished = event
        except AIProviderError as exc:
            result.fallback = str(exc) if str(exc) == "not_configured" else "unavailable"
            if sent_any:
                yield Reset()
            result.text = FALLBACK_RESPONSES["unavailable"]
            yield Delta(result.text)
            return
        finally:
            result.latency_ms.append(int((time.monotonic() - attempt_start) * 1000))
            if finished:
                result.usage.append(finished)

        if not guard.leaked:
            tail = guard.finish()
            if tail and not guard.leaked:
                yield Delta(tail)
        if guard.leaked:
            result.blocked_leaks += 1
            result.raw_leak_texts.append(guard.text)
            if sent_any:
                yield Reset()
            continue

        if finished and finished.stop_reason == "refusal":
            result.fallback = "refusal"
            if guard.text:
                yield Reset()
            result.text = FALLBACK_RESPONSES["refusal"]
            yield Delta(result.text)
            return

        board, dropped = filter_board(validate_board(raw_blocks), protected)
        result.board_blocks_dropped += (
            len(validate_board(raw_blocks)) - len(board) if dropped else 0
        )
        result.text = guard.text.strip()
        result.board = to_frontend_blocks(board)
        return

    # Every attempt tried to reveal the answer: use a safe line written by code.
    result.fallback = "leak"
    result.text = FALLBACK_RESPONSES["leak"]
    yield Delta(result.text)
