"""The AI provider interface.

Every model vendor is wrapped in a class that implements AIProvider, so switching
or mixing vendors is a configuration change. Real providers arrive in Phase 5.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


class AIProvider(Protocol):
    name: str

    def stream_reply(
        self, messages: list[ChatMessage], *, max_tokens: int
    ) -> AsyncIterator[str]:
        """Stream the model's reply as text chunks."""
        ...
