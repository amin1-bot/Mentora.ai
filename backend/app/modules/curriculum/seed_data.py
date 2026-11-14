"""The approved question bank: the Percentages topic area (grades 6-8).

"Percentages" is a topic area made of four skills. Each skill is a topic of its own, with
its own lessons, questions and mastery score:

  1. Percents, decimals and fractions     "Write 25% as a decimal."
  2. Percent of an amount                 "What is 25% of 80?"
  3. Percentage increase and decrease     "A jacket costs 40. It is reduced by 25%..."
  4. One number as a percentage of another "What percentage of 48 is 12?"

Rules for adding questions (app/tests/test_answers.py checks every question below):
- The answer must not appear as a number in the question text (the leak guard relies on it).
- No known wrong answer (adaptive/answers.py) may equal the correct answer.
- answer_data["value"] must equal what compute_answer() works out from the inputs.

Ids are fixed (uuid5), so the seed migration is repeatable and tests can refer to them.
"""

import uuid
from typing import Any

_NS = uuid.UUID("6f1c1c2e-6a59-4f8e-9f57-1e0b8f1a6c00")


def seed_id(name: str) -> uuid.UUID:
    return uuid.uuid5(_NS, name)


def _fmt(x: float) -> str:
    return f"{x:g}"


MATH_ID = seed_id("subject:math")
PERCENTAGES_ID = seed_id("topic:percentages")  # the topic area (no questions of its own)
CONVERT_ID = seed_id("topic:percent_convert")
PERCENT_OF_ID = seed_id("topic:percent_of")
CHANGE_ID = seed_id("topic:percent_change")
EXPRESS_ID = seed_id("topic:percent_express")

SUBJECTS = [{"id": MATH_ID, "name": "Mathematics", "slug": "math"}]

# Listed in teaching order: the progress page and recommendations follow this order.
TOPICS: list[dict[str, Any]] = [
    {"id": PERCENTAGES_ID, "parent_topic_id": None, "name": "Percentages"},
    {"id": CONVERT_ID, "parent_topic_id": PERCENTAGES_ID,
     "name": "Percents, decimals and fractions"},
    {"id": PERCENT_OF_ID, "parent_topic_id": PERCENTAGES_ID, "name": "Percent of an amount"},
    {"id": CHANGE_ID, "parent_topic_id": PERCENTAGES_ID,
     "name": "Percentage increase and decrease"},
    {"id": EXPRESS_ID, "parent_topic_id": PERCENTAGES_ID,
     "name": "One number as a percentage of another"},
]
for _t in TOPICS:
    _t.update(subject_id=MATH_ID, grade_band="6-8")

TOPIC_ORDER = [t["id"] for t in TOPICS]

# (topic, needs this topic first). A recommendation, never a lock.
PREREQUISITES = [
    (PERCENT_OF_ID, CONVERT_ID),
    (CHANGE_ID, PERCENT_OF_ID),
    (EXPRESS_ID, CONVERT_ID),
]

MISCONCEPTIONS: list[dict[str, Any]] = [
    # Percents, decimals and fractions
    {"topic_id": CONVERT_ID, "code": "decimal_no_divide",
     "description": "Writes the percent unchanged as the decimal (says 25% is 25)."},
    {"topic_id": CONVERT_ID, "code": "decimal_divided_by_10",
     "description": "Divides by 10 instead of 100 (says 5% is 0.5)."},
    {"topic_id": CONVERT_ID, "code": "decimal_divided_by_1000",
     "description": "Moves the decimal point three places (says 25% is 0.025)."},
    {"topic_id": CONVERT_ID, "code": "fraction_digits_joined",
     "description": "Joins the digits of the fraction (says 3/4 is 34%)."},
    {"topic_id": CONVERT_ID, "code": "fraction_forgot_100",
     "description": "Stops at the decimal and forgets to multiply by 100 (says 3/4 is 0.75%)."},
    {"topic_id": CONVERT_ID, "code": "fraction_upside_down",
     "description": "Divides the bottom by the top (says 1/4 is 400%)."},
    # Percent of an amount
    {"topic_id": PERCENT_OF_ID, "code": "percent_forgot_divide_100",
     "description": "Multiplies the percent by the number without dividing by 100 "
                    "(says 25% of 80 is 2000)."},
    {"topic_id": PERCENT_OF_ID, "code": "percent_subtracted",
     "description": "Subtracts the percent from the number (says 25% of 80 is 55)."},
    {"topic_id": PERCENT_OF_ID, "code": "percent_divided_by_percent",
     "description": "Divides the number by the percent (says 25% of 80 is 3.2)."},
    {"topic_id": PERCENT_OF_ID, "code": "percent_gave_percent",
     "description": "Gives the percent itself as the answer (says 25% of 80 is 25)."},
    # Percentage increase and decrease
    {"topic_id": CHANGE_ID, "code": "change_gave_amount",
     "description": "Gives only the size of the change, not the new amount "
                    "(says 40 reduced by 25% is 10)."},
    {"topic_id": CHANGE_ID, "code": "change_used_percent_as_number",
     "description": "Adds or subtracts the percent as if it were a number "
                    "(says 40 reduced by 25% is 15)."},
    {"topic_id": CHANGE_ID, "code": "change_wrong_direction",
     "description": "Increases instead of decreasing, or the other way round "
                    "(says 40 reduced by 25% is 50)."},
    # One number as a percentage of another
    {"topic_id": EXPRESS_ID, "code": "express_upside_down",
     "description": "Divides the whole by the part (says 12 out of 48 is 400%)."},
    {"topic_id": EXPRESS_ID, "code": "express_forgot_100",
     "description": "Stops at the decimal and forgets to multiply by 100 "
                    "(says 12 out of 48 is 0.25%)."},
    {"topic_id": EXPRESS_ID, "code": "express_gave_difference",
     "description": "Gives the difference between the numbers (says 12 out of 48 is 36%)."},
]


def _question(topic_id: uuid.UUID, difficulty: int, key: str, text: str, data: dict) -> dict:
    return {
        "id": seed_id(f"question:{key}"),
        "topic_id": topic_id,
        "difficulty": difficulty,
        "text": text,
        "answer_data": data,
        "source": "bank",
        "is_approved": True,
    }


# --- 1. Percents, decimals and fractions ---
# (difficulty, percent)
_TO_DECIMAL = [(1, 50), (1, 10), (2, 25), (2, 75), (3, 5), (3, 60),
               (4, 12.5), (4, 125), (5, 2.5), (5, 0.5)]
# (difficulty, numerator, denominator)
_FRACTION_TO_PERCENT = [(1, 1, 2), (1, 1, 4), (2, 3, 4), (2, 1, 5), (3, 2, 5), (3, 3, 10),
                        (4, 3, 20), (4, 7, 25), (5, 3, 8), (5, 5, 4)]

# --- 2. Percent of an amount: (difficulty, percent, of) ---
_PERCENT_OF = [
    (1, 50, 10), (1, 20, 30), (1, 50, 8),
    (2, 25, 40), (2, 20, 15), (2, 5, 60),
    (3, 25, 80), (3, 75, 12), (3, 30, 50),
    (4, 15, 60), (4, 40, 35), (4, 12, 25),
    (5, 35, 120), (5, 2.5, 400), (5, 120, 45),
]

# --- 3. Percentage increase and decrease: (difficulty, direction, start, percent) ---
_CHANGE = [
    (1, "down", 40, 10), (1, "up", 30, 10), (1, "up", 60, 10),
    (2, "down", 40, 25), (2, "up", 80, 25), (2, "down", 50, 20),
    (3, "up", 120, 15), (3, "down", 90, 30), (3, "up", 250, 40),
    (4, "down", 64, 12.5), (4, "up", 45, 20), (4, "down", 360, 35),
    (5, "up", 80, 2.5), (5, "down", 1200, 7.5), (5, "up", 64, 37.5),
]
_CHANGE_TEXT = {
    "up": [
        "A plant is {start} cm tall. It grows by {p}%. How tall is it now, in cm?",
        "A club has {start} members. Membership rises by {p}%. How many members are there now?",
    ],
    "down": [
        "A jacket costs {start}. Its price is reduced by {p}%. What is the new price?",
        "A tank holds {start} litres of water. It loses {p}% of it. How many litres are left?",
    ],
}

# --- 4. One number as a percentage of another: (difficulty, part, whole) ---
_EXPRESS = [
    (1, 1, 4), (1, 3, 10), (1, 10, 20),
    (2, 12, 48), (2, 9, 12), (2, 6, 30),
    (3, 14, 40), (3, 27, 90), (3, 18, 24),
    (4, 7, 8), (4, 33, 60), (4, 13, 20),
    (5, 45, 36), (5, 3, 16), (5, 51, 68),
]
_EXPRESS_TEXT = [
    "What percentage of {whole} is {part}?",
    "{part} out of {whole} students walk to school. What percentage of the students walk?",
    "A student scored {part} out of {whole} on a test. What is that score as a percentage?",
]


def compute_answer(data: dict[str, Any]) -> float:
    """The correct answer, worked out from a question's inputs."""
    kind = data["kind"]
    if kind == "percent_to_decimal":
        value = data["percent"] / 100
    elif kind == "fraction_to_percent":
        value = data["numerator"] / data["denominator"] * 100
    elif kind == "percent_of":
        value = data["percent"] * data["of"] / 100
    elif kind == "percent_change":
        sign = 1 if data["direction"] == "up" else -1
        value = data["start"] * (1 + sign * data["percent"] / 100)
    elif kind == "percent_express":
        value = data["part"] / data["whole"] * 100
    else:
        raise ValueError(f"unknown question kind {kind}")
    return round(value, 6)


def _build_questions() -> list[dict]:
    out: list[dict] = []
    for d, p in _TO_DECIMAL:
        data = {"kind": "percent_to_decimal", "percent": p}
        out.append(_question(CONVERT_ID, d, f"percent_to_decimal:{_fmt(p)}",
                             f"Write {_fmt(p)}% as a decimal.", data))
    for d, num, den in _FRACTION_TO_PERCENT:
        data = {"kind": "fraction_to_percent", "numerator": num, "denominator": den}
        out.append(_question(CONVERT_ID, d, f"fraction_to_percent:{num}/{den}",
                             f"Write {num}/{den} as a percentage.", data))
    for d, p, n in _PERCENT_OF:
        # Key kept from the first question bank, so these questions keep their ids.
        data = {"kind": "percent_of", "percent": p, "of": n}
        out.append(_question(PERCENT_OF_ID, d, f"percent_of:{_fmt(p)}:{_fmt(n)}",
                             f"What is {_fmt(p)}% of {_fmt(n)}?", data))
    used = {"up": 0, "down": 0}
    for d, direction, start, p in _CHANGE:
        template = _CHANGE_TEXT[direction][used[direction] % 2]
        used[direction] += 1
        data = {"kind": "percent_change", "direction": direction, "start": start, "percent": p}
        out.append(_question(CHANGE_ID, d, f"percent_change:{direction}:{_fmt(start)}:{_fmt(p)}",
                             template.format(start=_fmt(start), p=_fmt(p)), data))
    for i, (d, part, whole) in enumerate(_EXPRESS):
        data = {"kind": "percent_express", "part": part, "whole": whole}
        out.append(_question(EXPRESS_ID, d, f"percent_express:{part}:{whole}",
                             _EXPRESS_TEXT[i % 3].format(part=part, whole=whole), data))
    for q in out:
        q["answer_data"]["value"] = compute_answer(q["answer_data"])
    return out


QUESTIONS = _build_questions()
