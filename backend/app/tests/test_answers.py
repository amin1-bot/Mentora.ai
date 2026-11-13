"""Answer checking by code, misconception detection, and question-bank rules."""

import re

import pytest

from app.modules.adaptive.answers import check_answer, known_wrong_answers, parse_number
from app.modules.curriculum.seed_data import QUESTIONS

Q_25_OF_80 = {"kind": "percent_of", "percent": 25, "of": 80, "value": 20}


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("20", 20),
        ("20%", 20),
        ("it's 20", 20),
        ("  20.0 ", 20),
        ("0.25 x 80 = 20", 20),
        ("2,5", 2.5),
        ("1,000", 1000),
        ("1/2", 0.5),
        ("-3", -3),
    ],
)
def test_parse_number(text: str, value: float) -> None:
    assert parse_number(text) == pytest.approx(value)


@pytest.mark.parametrize("text", ["is it 20 or 30?", "I don't know", "what does percent mean", ""])
def test_not_a_single_answer(text: str) -> None:
    assert parse_number(text) is None


def test_the_blueprint_example_2000() -> None:
    """25% of 80 answered with 2000: wrong, and 'forgot to divide by 100'."""
    result = check_answer(Q_25_OF_80, 2000)
    assert not result.is_correct
    assert result.misconception_code == "percent_forgot_divide_100"


@pytest.mark.parametrize(
    ("value", "code"),
    [(55, "percent_subtracted"), (3.2, "percent_divided_by_percent"), (25, "percent_gave_percent")],
)
def test_other_known_misconceptions(value: float, code: str) -> None:
    assert check_answer(Q_25_OF_80, value).misconception_code == code


def test_correct_and_unknown_wrong_answers() -> None:
    assert check_answer(Q_25_OF_80, 20).is_correct
    unknown = check_answer(Q_25_OF_80, 21)
    assert not unknown.is_correct and unknown.misconception_code is None


@pytest.mark.parametrize("q", QUESTIONS, ids=lambda q: q["text"])
def test_question_bank_rules(q: dict) -> None:
    data = q["answer_data"]
    assert data["value"] == pytest.approx(data["percent"] * data["of"] / 100)
    # The leak guard needs the answer to be absent from the question text.
    numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", q["text"])]
    assert data["value"] not in numbers
    # No misconception may produce the correct answer, or it could never be detected.
    for wrong in known_wrong_answers(data).values():
        assert wrong != pytest.approx(data["value"])
