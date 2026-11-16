"""The answer-leak guard: stops the teacher from giving away an answer too early.

The model is told not to reveal the answer, but rules in a prompt are not enough
(blueprint section 8: "an automatic check that blocks a reply containing the final answer
too early and regenerates it"). This guard checks the reply *while it streams*.

What can be protected (each question's checker decides, see adaptive/checkers.py):
- ProtectedNumber: a numeric answer (20, 2.5). Matched as a whole number in the text.
- ProtectedPhrase: words that are the answer ("foreign", "primary key", the correct option's
  text). Matched case-insensitively, as whole words, with flexible spacing.
- ProtectedPattern: a regular expression for answer statements that are not a fixed
  phrase ("the answer is B", "it's true").

How streaming stays safe:
- A number at the very end of what has arrived so far ("2", "20", "20.") is held back,
  because it might still grow into the answer.
- When words are protected, the last few characters (as long as the longest protected
  phrase) are held back too, so the start of a protected phrase is never shown before the
  guard can see the whole phrase.
- If a protected answer appears, the guard reports a leak before it is ever sent. The
  caller then stops the stream and regenerates.

Limitations (documented, tested): numbers written as words ("twenty") are not caught; an
answer that also appears in the question text or the topic name cannot be protected
(the checkers leave it out), so the question bank avoids such questions where it can.
"""

import re
from collections.abc import Sequence
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


@dataclass(frozen=True)
class ProtectedNumber:
    value: float

    def found_in(self, text: str) -> bool:
        return any(same_number(v, self.value) for v in _values(text))

    @property
    def hold_chars(self) -> int:
        return 0  # numbers are held back by the trailing-digit rule instead


@dataclass(frozen=True)
class ProtectedPhrase:
    phrase: str

    def _regex(self) -> re.Pattern[str]:
        words = [re.escape(w) for w in self.phrase.split()]
        return re.compile(r"(?<!\w)" + r"[\s\-]+".join(words) + r"(?!\w)", re.IGNORECASE)

    def found_in(self, text: str) -> bool:
        return bool(self._regex().search(text))

    @property
    def hold_chars(self) -> int:
        return len(self.phrase) + 2


@dataclass(frozen=True)
class ProtectedPattern:
    regex: str
    hold: int = 40  # longest text the pattern can match

    def found_in(self, text: str) -> bool:
        return bool(re.search(self.regex, text, re.IGNORECASE))

    @property
    def hold_chars(self) -> int:
        return self.hold


Protected = ProtectedNumber | ProtectedPhrase | ProtectedPattern


def as_protected(items: Sequence[float | Protected]) -> list[Protected]:
    """Plain numbers are accepted for convenience (the maths tests and the eval use them)."""
    return [
        ProtectedNumber(float(i)) if isinstance(i, int | float) else i for i in items
    ]


def contains_any(text: str, protected: Sequence[float | Protected]) -> bool:
    return any(p.found_in(text) for p in as_protected(protected))


@dataclass
class LeakGuard:
    protected: Sequence[float | Protected]
    _pending: str = ""
    leaked: bool = False
    released: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._items = as_protected(self.protected)
        self._hold = max((p.hold_chars for p in self._items), default=0)

    def feed(self, chunk: str) -> str:
        """Add streamed text; return the part that is safe to show now."""
        if self.leaked:
            return ""
        self._pending += chunk
        match = _TRAILING_PARTIAL.search(self._pending)
        cut = match.start() if match else len(self._pending)
        cut = min(cut, max(0, len(self._pending) - self._hold))
        # Never split a number between two releases.
        if 0 < cut < len(self._pending) and self._pending[cut] in "0123456789.,":
            inside = _TRAILING_PARTIAL.search(self._pending[:cut])
            if inside:
                cut = inside.start()
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
        # Judge the new text together with the end of what was already released, so a
        # phrase split across two releases is still seen whole.
        window = self.text[-self._hold :] + text if self._hold else text
        if any(p.found_in(window) for p in self._items):
            self.leaked = True
            return ""
        self.released.append(text)
        return text

    @property
    def text(self) -> str:
        return "".join(self.released)


def filter_board(
    blocks: list[dict[str, Any]], protected: Sequence[float | Protected]
) -> tuple[list[dict[str, Any]], bool]:
    """Drop whiteboard blocks that would reveal a protected answer."""
    kept = [b for b in blocks if not contains_any(str(b.get("content", "")), protected)]
    return kept, len(kept) != len(blocks)
