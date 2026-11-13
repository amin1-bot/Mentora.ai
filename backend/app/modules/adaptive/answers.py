"""Answer checking by code, never by asking the model (blueprint section 8).

Example from the blueprint: "What is 25% of 80?" answered with 2000. Code sees that
2000 is not 20, and that 2000 = 25 x 80, which matches the known misconception
"forgot to divide by 100".
"""

import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

# A number as students type it: 20, -3, 2.5, 2,5 (comma decimal), 1/2, 1,000.
_NUMBER = re.compile(r"-?\d+(?:[.,]\d+)*(?:\s*/\s*\d+)?")


def _to_float(token: str) -> float | None:
    token = token.replace(" ", "")
    try:
        if "/" in token:
            num, den = token.split("/", 1)
            return float(Fraction(_to_float(num) or 0).limit_denominator() / Fraction(den))
        if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", token):  # 1,000 or 1,000.5
            token = token.replace(",", "")
        else:
            token = token.replace(",", ".")
        return float(token)
    except (ValueError, ZeroDivisionError):
        return None


def parse_number(text: str) -> float | None:
    """The number a student means, or None if the message is not a single answer.

    "20", "20%", "it is 20", "0.25 x 80 = 20" -> 20.0
    "is it 20 or 30?" -> None (ambiguous: treated as a question, not an answer)
    """
    if "=" in text:
        text = text.rsplit("=", 1)[1]
    tokens = _NUMBER.findall(text)
    if len(tokens) != 1:
        return None
    return _to_float(tokens[0])


def same_number(a: float, b: float) -> bool:
    return abs(a - b) <= max(1e-6, abs(b) * 1e-6)


def known_wrong_answers(answer_data: dict[str, Any]) -> dict[str, float]:
    """Misconception code -> the wrong answer that misconception produces."""
    if answer_data.get("kind") != "percent_of":
        return {}
    p, n = float(answer_data["percent"]), float(answer_data["of"])
    wrong = {
        "percent_forgot_divide_100": p * n,
        "percent_subtracted": n - p,
        "percent_gave_percent": p,
    }
    if p:
        wrong["percent_divided_by_percent"] = n / p
    return wrong


@dataclass(frozen=True)
class AnswerCheck:
    value: float
    is_correct: bool
    misconception_code: str | None


def check_answer(answer_data: dict[str, Any], value: float) -> AnswerCheck:
    correct = float(answer_data["value"])
    if same_number(value, correct):
        return AnswerCheck(value, True, None)
    for code, wrong in known_wrong_answers(answer_data).items():
        if same_number(value, round(wrong, 6)) or round(value, 2) == round(wrong, 2):
            return AnswerCheck(value, False, code)
    return AnswerCheck(value, False, None)
