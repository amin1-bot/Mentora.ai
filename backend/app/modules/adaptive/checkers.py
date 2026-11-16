"""Answer checkers: one per question type, all checked by code, never by the model.

Each checker answers four questions about a question's `answer_data`:
- interpret: does this student message look like an answer? (if not, it is a question or
  a comment, and the teacher responds instead of marking it)
- check: is it correct, and does it match a known misconception?
- protected: what must the leak guard hide while the answer is still secret?
- describe: the answer in words, for the teacher's private instruction.

Adding a question type = adding a checker here and its name to QUESTION_TYPES
(curriculum/models.py). Short answers and essays (marked by the model with a rubric) and
code (run in a sandbox) come in later phases.
"""

import re
import string
from dataclasses import dataclass
from typing import Any, Protocol

from app.modules.adaptive.answers import check_answer, parse_number
from app.modules.teacher.guard import (
    Protected,
    ProtectedNumber,
    ProtectedPattern,
    ProtectedPhrase,
)

LETTERS = string.ascii_uppercase


@dataclass(frozen=True)
class Check:
    is_correct: bool
    misconception_code: str | None
    display: str  # the student's answer as the teacher should hear it ("B) Foreign key")


class Checker(Protocol):
    def interpret(self, text: str, data: dict[str, Any]) -> Any | None: ...

    def check(self, data: dict[str, Any], answer: Any) -> Check: ...

    def protected(self, data: dict[str, Any], visible_text: str) -> list[Protected]: ...

    def describe(self, data: dict[str, Any]) -> str: ...


def _norm(text: str) -> str:
    """Lowercase, no surrounding punctuation, single spaces, no leading article."""
    text = re.sub(r"\s+", " ", text.strip().lower())
    text = text.strip(" .!,;:'\"()")
    return re.sub(r"^(?:a|an|the)\s+", "", text)


def _visible(phrase: str, visible_text: str) -> bool:
    """True when the phrase already appears where the student (and teacher) can see it."""
    return ProtectedPhrase(phrase).found_in(visible_text)


# ---------- numeric ----------


class NumericChecker:
    def interpret(self, text: str, data: dict[str, Any]) -> float | None:
        return parse_number(text)

    def check(self, data: dict[str, Any], answer: float) -> Check:
        result = check_answer(data, answer)
        return Check(result.is_correct, result.misconception_code, f"{answer:g}")

    def protected(self, data: dict[str, Any], visible_text: str) -> list[Protected]:
        return [ProtectedNumber(float(data["value"]))]

    def describe(self, data: dict[str, Any]) -> str:
        return f"{float(data['value']):g}"


# ---------- multiple choice ----------

_LETTER_ANSWER = re.compile(
    r"^(?:(?:my\s+)?answer\s*(?:is|:)?\s*|option\s+|choice\s+|it'?s\s+|it\s+is\s+|i\s+think\s+)?"
    r"\(?([a-z])\)?(?:\s*[.):]\s*.*)?$",
    re.IGNORECASE,
)


class MultipleChoiceChecker:
    def interpret(self, text: str, data: dict[str, Any]) -> int | None:
        options: list[str] = data["options"]
        if "?" in text:
            return None
        match = _LETTER_ANSWER.match(text.strip())
        if match:
            index = LETTERS.index(match.group(1).upper())
            return index if index < len(options) else None
        wanted = _norm(text)
        for i, option in enumerate(options):
            if _norm(option) == wanted:
                return i
        return None

    def check(self, data: dict[str, Any], answer: int) -> Check:
        code = (data.get("misconceptions") or {}).get(str(answer))
        return Check(answer == data["correct_index"], code, self._label(data, answer))

    def protected(self, data: dict[str, Any], visible_text: str) -> list[Protected]:
        letter = LETTERS[data["correct_index"]]
        items: list[Protected] = [
            # "the answer is B", "option B is correct", "B) is right", "(B)"
            ProtectedPattern(
                rf"\b(?:answer|option|choice)\s+(?:is\s+)?\(?{letter}\)?(?![\w'])"
                rf"|(?<![\w'])\(?{letter}\)\s+is\s+(?:correct|right)"
                rf"|\({letter}\)",
                hold=30,
            )
        ]
        correct = data["options"][data["correct_index"]]
        # The options are on the board, so their text is visible; the guard still blocks
        # the teacher repeating the correct one, unless the question text itself uses it.
        question_only = visible_text.split("\nOptions:")[0]
        if len(correct) >= 3 and not _visible(correct, question_only):
            items.append(ProtectedPhrase(correct))
        return items

    def describe(self, data: dict[str, Any]) -> str:
        return self._label(data, data["correct_index"])

    @staticmethod
    def _label(data: dict[str, Any], index: int) -> str:
        return f"{LETTERS[index]}) {data['options'][index]}"


# ---------- true / false ----------

_TRUE = {"true", "t", "correct", "it's true", "it is true", "that's true", "dogru", "doğru"}
_FALSE = {"false", "f", "incorrect", "it's false", "it is false", "that's false", "yanlis",
          "yanlış"}


class TrueFalseChecker:
    def interpret(self, text: str, data: dict[str, Any]) -> bool | None:
        if "?" in text:
            return None
        said = _norm(text)
        if said in _TRUE:
            return True
        if said in _FALSE:
            return False
        return None

    def check(self, data: dict[str, Any], answer: bool) -> Check:
        correct = answer == bool(data["value"])
        code = None if correct else data.get("misconception_if_wrong")
        return Check(correct, code, "true" if answer else "false")

    def protected(self, data: dict[str, Any], visible_text: str) -> list[Protected]:
        # Any verdict on the statement gives the answer away, right or wrong.
        return [
            ProtectedPattern(
                r"\b(?:statement|it|this|that|answer|claim)\s+(?:is|was)\s+(?:not\s+)?"
                r"(?:true|false|correct|incorrect)\b"
                r"|\b(?:it's|that's|this's)\s+(?:not\s+)?(?:true|false)\b",
                hold=40,
            )
        ]

    def describe(self, data: dict[str, Any]) -> str:
        return "true" if data["value"] else "false"


# ---------- fill in the blank ----------

# Short messages that are clearly not an attempt at the blank.
_NOT_ANSWERS = {
    "ok", "okay", "thanks", "thank you", "yes", "no", "why", "how", "what", "help",
    "hint", "idk", "i don't know", "i dont know", "dont know", "don't know", "not sure",
    "i'm not sure", "im not sure", "confused", "i'm confused", "im confused", "hi",
    "hello", "hey", "sorry", "wait", "huh", "explain", "again", "i don't get it",
}
_MAX_BLANK_WORDS = 5


class FillBlankChecker:
    def interpret(self, text: str, data: dict[str, Any]) -> str | None:
        said = _norm(text)
        if not said or "?" in text or said in _NOT_ANSWERS:
            return None
        if len(said.split()) > _MAX_BLANK_WORDS or not re.search(r"\w", said):
            return None
        return said

    def check(self, data: dict[str, Any], answer: str) -> Check:
        accepted = {_norm(a) for a in data["answers"]}
        wrong = {_norm(k): v for k, v in (data.get("wrong_answers") or {}).items()}
        return Check(answer in accepted, wrong.get(answer), answer)

    def protected(self, data: dict[str, Any], visible_text: str) -> list[Protected]:
        return [ProtectedPhrase(a) for a in data["answers"] if not _visible(a, visible_text)]

    def describe(self, data: dict[str, Any]) -> str:
        return data["answers"][0]


_CHECKERS: dict[str, Checker] = {
    "numeric": NumericChecker(),
    "multiple_choice": MultipleChoiceChecker(),
    "true_false": TrueFalseChecker(),
    "fill_blank": FillBlankChecker(),
}


def checker_for(question_type: str) -> Checker:
    return _CHECKERS[question_type]


def question_for_teacher(question_type: str, text: str, data: dict[str, Any]) -> str:
    """The question as the teacher (and the leak guard) should see it, options included."""
    if question_type == "multiple_choice":
        options = " ".join(f"{LETTERS[i]}) {o}" for i, o in enumerate(data["options"]))
        return f"{text}\nOptions: {options}"
    return text


def answer_key(question_type: str, data: dict[str, Any]) -> str:
    """The answer as plain lowercase words (the option's text, not its letter), so answers
    to questions of different types can be compared."""
    if question_type == "multiple_choice":
        return _norm(data["options"][data["correct_index"]])
    return _norm(checker_for(question_type).describe(data))


def answers_clash(a: str, b: str) -> bool:
    """True when one answer contains the other as whole words ("foreign" and "foreign key").

    Two such questions are never asked back to back: praising the first answer would
    give away the next one."""
    if a == b:
        return True
    short, long = sorted((a, b), key=len)
    return bool(short) and ProtectedPhrase(short).found_in(long)
