"""Answer checking by code, misconception detection, and question-bank rules."""

import re

import pytest

from app.modules.adaptive.answers import check_answer, known_wrong_answers, parse_number
from app.modules.adaptive.checkers import checker_for
from app.modules.curriculum.seed_data import MISCONCEPTIONS, QUESTIONS, compute_answer

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


NUMERIC = [q for q in QUESTIONS if q["question_type"] == "numeric"]
OTHER = [q for q in QUESTIONS if q["question_type"] != "numeric"]
CODES = {m["code"] for m in MISCONCEPTIONS}


@pytest.mark.parametrize("q", NUMERIC, ids=lambda q: q["text"])
def test_numeric_question_bank_rules(q: dict) -> None:
    data = q["answer_data"]
    assert data["value"] == pytest.approx(compute_answer(data))
    # The leak guard needs the answer to be absent from the question text.
    numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", q["text"])]
    assert data["value"] not in numbers
    # No misconception may produce the correct answer, or it could never be detected.
    wrongs = known_wrong_answers(data)
    assert wrongs, "every question kind needs known mistakes"
    for wrong in wrongs.values():
        assert wrong != pytest.approx(data["value"])
    # Every code the checker can return exists in the seeded misconception list.
    assert set(wrongs) <= CODES


@pytest.mark.parametrize("q", OTHER, ids=lambda q: q["text"])
def test_other_question_bank_rules(q: dict) -> None:
    data, kind = q["answer_data"], q["question_type"]
    assert data["kind"] == kind
    checker = checker_for(kind)
    correct = checker.describe(data)
    if kind == "multiple_choice":
        options = data["options"]
        assert 3 <= len(options) <= 4 and len({o.lower() for o in options}) == len(options)
        assert 0 <= data["correct_index"] < len(options)
        assert set(data["misconceptions"]) <= {str(i) for i in range(len(options))}
        assert str(data["correct_index"]) not in data["misconceptions"]
        assert options[data["correct_index"]].lower() not in q["text"].lower()
        codes = set(data["misconceptions"].values())
    elif kind == "true_false":
        assert isinstance(data["value"], bool)
        codes = {data["misconception_if_wrong"]} - {None}
    else:  # fill_blank
        assert "____" in q["text"]
        for accepted in data["answers"]:
            assert accepted.lower() not in q["text"].lower()
        assert not set(data["wrong_answers"]) & set(data["answers"])
        codes = set(data["wrong_answers"].values())
    assert codes <= CODES
    # The correct answer, typed as a student would, is recognised and marked right.
    typed = "ABCD"[data["correct_index"]] if kind == "multiple_choice" else correct
    answer = checker.interpret(typed, data)
    assert answer is not None and checker.check(data, answer).is_correct
    assert q["explanation"]


@pytest.mark.parametrize(
    ("data", "value", "code"),
    [
        ({"kind": "percent_to_decimal", "percent": 5}, 0.5, "decimal_divided_by_10"),
        ({"kind": "percent_to_decimal", "percent": 25}, 25, "decimal_no_divide"),
        (
            {"kind": "fraction_to_percent", "numerator": 3, "denominator": 4},
            34,
            "fraction_digits_joined",
        ),  # noqa: E501
        (
            {"kind": "fraction_to_percent", "numerator": 3, "denominator": 4},
            0.75,
            "fraction_forgot_100",
        ),  # noqa: E501
        (
            {"kind": "percent_change", "direction": "down", "start": 40, "percent": 25},
            10,
            "change_gave_amount",
        ),  # noqa: E501
        (
            {"kind": "percent_change", "direction": "down", "start": 40, "percent": 25},
            15,
            "change_used_percent_as_number",
        ),  # noqa: E501
        (
            {"kind": "percent_change", "direction": "down", "start": 40, "percent": 25},
            50,
            "change_wrong_direction",
        ),  # noqa: E501
        ({"kind": "percent_express", "part": 12, "whole": 48}, 400, "express_upside_down"),
        ({"kind": "percent_express", "part": 12, "whole": 48}, 0.25, "express_forgot_100"),
    ],
)
def test_misconceptions_for_every_question_kind(data: dict, value: float, code: str) -> None:
    data = {**data, "value": compute_answer(data)}
    result = check_answer(data, value)
    assert not result.is_correct and result.misconception_code == code


def test_question_bank_covers_every_skill_at_every_difficulty() -> None:
    from app.modules.curriculum.seed_data import TOPICS

    skills = [t["id"] for t in TOPICS if t["parent_topic_id"] is not None]
    for skill in skills:
        levels = {q["difficulty"] for q in QUESTIONS if q["topic_id"] == skill}
        assert levels == {1, 2, 3, 4, 5}
    assert len({q["id"] for q in QUESTIONS}) == len(QUESTIONS)
