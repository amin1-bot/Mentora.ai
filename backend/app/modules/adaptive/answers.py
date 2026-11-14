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
    """Misconception code -> the wrong answer that misconception produces.

    Codes match curriculum/seed_data.py MISCONCEPTIONS. When two mistakes give the same
    number, the first one listed wins.
    """
    kind = answer_data.get("kind")
    if kind == "percent_to_decimal":
        p = float(answer_data["percent"])
        return {
            "decimal_no_divide": p,
            "decimal_divided_by_10": p / 10,
            "decimal_divided_by_1000": p / 1000,
        }
    if kind == "fraction_to_percent":
        num, den = int(answer_data["numerator"]), int(answer_data["denominator"])
        return {
            "fraction_digits_joined": float(f"{num}{den}"),
            "fraction_forgot_100": num / den,
            "fraction_upside_down": den / num * 100,
        }
    if kind == "percent_of":
        p, n = float(answer_data["percent"]), float(answer_data["of"])
        wrong = {
            "percent_forgot_divide_100": p * n,
            "percent_subtracted": n - p,
            "percent_gave_percent": p,
        }
        if p:
            wrong["percent_divided_by_percent"] = n / p
        return wrong
    if kind == "percent_change":
        start, p = float(answer_data["start"]), float(answer_data["percent"])
        sign = 1 if answer_data["direction"] == "up" else -1
        return {
            "change_gave_amount": start * p / 100,
            "change_used_percent_as_number": start + sign * p,
            "change_wrong_direction": start * (1 - sign * p / 100),
        }
    if kind == "percent_express":
        part, whole = float(answer_data["part"]), float(answer_data["whole"])
        return {
            "express_upside_down": whole / part * 100,
            "express_forgot_100": part / whole,
            "express_gave_difference": whole - part,
        }
    return {}


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
