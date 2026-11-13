"""The answer-leak guard: stops the teacher from giving away an answer too early.

The model is told not to reveal the answer, but rules in a prompt are not enough
(blueprint section 8: "an automatic check that blocks a reply containing the final answer
too early and regenerates it"). This guard checks the reply *while it streams*:

- Text is released to the student up to the last complete number. A number at the very
  end of what has arrived so far ("2", "20", "20.") is held back until the next words
  arrive, because it might still grow into the answer.
- If a complete number equals a protected answer, the guard reports a leak before that
  number is ever sent. The caller then stops the stream and regenerates.

Limitations (documented, tested): answers written as words ("twenty") are not caught,
and a protected answer that also appears in the question text cannot be protected, which
is why the question bank never contains such questions.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from app.modules.adaptive.answers import same_number

_NUM = re.compile(r"\d+(?:[.,]\d+)*")
_TRAILING_PARTIAL = re.compile(r"[\d.,]+$")


def _values(text: str) -> list[float]:
    out = []
    for token in _NUM.findall(text):
        try:
            out.append(
                float(
                    token.replace(",", "")
                    if re.fullmatch(r"\d{1,3}(,\d{3})+", token)
                    else token.replace(",", ".")
                )
            )
        except ValueError:
            continue
    return out


def contains_any(text: str, protected: list[float]) -> bool:
    return any(same_number(v, p) for v in _values(text) for p in protected)


@dataclass
class LeakGuard:
    protected: list[float]
    _pending: str = ""
    leaked: bool = False
    released: list[str] = field(default_factory=list)

    def feed(self, chunk: str) -> str:
        """Add streamed text; return the part that is safe to show now."""
        if self.leaked:
            return ""
        self._pending += chunk
        match = _TRAILING_PARTIAL.search(self._pending)
        cut = match.start() if match else len(self._pending)
        safe, self._pending = self._pending[:cut], self._pending[cut:]
        return self._release(safe)

    def finish(self) -> str:
        """End of stream: check and release whatever is still held back."""
        if self.leaked:
            return ""
        safe, self._pending = self._pending, ""
        return self._release(safe)

    def _release(self, text: str) -> str:
        if not text:
            return ""
        # Check the new text together with the end of what was already released, so a
        # number is always judged whole.
        if contains_any(text, self.protected):
            self.leaked = True
            return ""
        self.released.append(text)
        return text

    @property
    def text(self) -> str:
        return "".join(self.released)


def filter_board(
    blocks: list[dict[str, Any]], protected: list[float]
) -> tuple[list[dict[str, Any]], bool]:
    """Drop whiteboard blocks that would reveal a protected answer."""
    kept = [b for b in blocks if not contains_any(str(b.get("content", "")), protected)]
    return kept, len(kept) != len(blocks)
