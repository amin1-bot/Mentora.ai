"""The AI provider interface.

Every model vendor is wrapped in a class with this shape, so switching or comparing
vendors is a configuration change. The teacher service never imports a vendor SDK.

One "turn" = one request: fixed teaching rules (system), the recent conversation, and a
per-turn instruction from the teaching engine. The provider streams back:
  - TextDelta: words the teacher says (shown to the student as they arrive)
  - BoardBlocks: raw whiteboard blocks from the model (validated by the caller)
  - TurnFinished: stop reason and token usage, for cost tracking
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Role = Literal["user", "assistant", "system"]


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str


@dataclass(frozen=True)
class TurnRequest:
    system: str
    messages: list[ChatMessage]
    max_tokens: int


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class BoardBlocks:
    blocks: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class TurnFinished:
    model: str
    stop_reason: str  # "end_turn", "tool_use", "max_tokens", "refusal", ...
    tokens_in: int
    tokens_out: int


ProviderEvent = TextDelta | BoardBlocks | TurnFinished


class AIProviderError(Exception):
    """The provider could not answer (network, rate limit, outage, bad key)."""


class AIProvider(Protocol):
    name: str

    def stream_turn(self, request: TurnRequest) -> AsyncIterator[ProviderEvent]:
        """Stream one teacher turn. Must end with exactly one TurnFinished."""
        ...


# The whiteboard tool every provider offers the model. Block types are deliberately
# few; the backend validates them again and the frontend draws only known types.
BOARD_TOOL_NAME = "write_on_board"
BOARD_TOOL_DESCRIPTION = (
    "Write short steps, examples or equations on the classroom whiteboard. Call this at "
    "most once per reply, after speaking. Use 'equation' only for maths or formulas "
    "written in LaTeX, 'step' for one numbered step, 'text' for a short heading or note."
)
BOARD_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["text", "step", "equation"]},
                    "content": {"type": "string"},
                },
                "required": ["type", "content"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["blocks"],
    "additionalProperties": False,
}
