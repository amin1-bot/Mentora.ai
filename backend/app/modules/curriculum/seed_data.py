"""The first approved question bank: Percentages (grades 6-8).

Every question is "What is P% of N?". Rules for adding questions:
- The answer must not appear as a number in the question text (the leak guard relies on it).
- No known wrong answer (see adaptive/answers.py) may equal the correct answer.
`app/tests/test_answers.py` checks both rules for every question below.

Ids are fixed (uuid5), so the seed migration is repeatable and tests can refer to them.
"""

import uuid

_NS = uuid.UUID("6f1c1c2e-6a59-4f8e-9f57-1e0b8f1a6c00")


def seed_id(name: str) -> uuid.UUID:
    return uuid.uuid5(_NS, name)


MATH_ID = seed_id("subject:math")
PERCENTAGES_ID = seed_id("topic:percentages")

SUBJECTS = [{"id": MATH_ID, "name": "Mathematics", "slug": "math"}]

TOPICS = [
    {"id": PERCENTAGES_ID, "subject_id": MATH_ID, "parent_topic_id": None,
     "name": "Percentages", "grade_band": "6-8"},
]

MISCONCEPTIONS = [
    {"code": "percent_forgot_divide_100",
     "description": "Multiplies the percent by the number without dividing by 100 "
                    "(says 25% of 80 is 2000)."},
    {"code": "percent_subtracted",
     "description": "Subtracts the percent from the number (says 25% of 80 is 55)."},
    {"code": "percent_divided_by_percent",
     "description": "Divides the number by the percent (says 25% of 80 is 3.2)."},
    {"code": "percent_gave_percent",
     "description": "Gives the percent itself as the answer (says 25% of 80 is 25)."},
]

# (difficulty, percent, of)
_PERCENT_OF = [
    (1, 50, 10), (1, 20, 30), (1, 50, 8),
    (2, 25, 40), (2, 20, 15), (2, 5, 60),
    (3, 25, 80), (3, 75, 12), (3, 30, 50),
    (4, 15, 60), (4, 40, 35), (4, 12, 25),
    (5, 35, 120), (5, 2.5, 400), (5, 120, 45),
]


def _fmt(x: float) -> str:
    return f"{x:g}"


QUESTIONS = [
    {
        "id": seed_id(f"question:percent_of:{_fmt(p)}:{_fmt(n)}"),
        "topic_id": PERCENTAGES_ID,
        "difficulty": d,
        "text": f"What is {_fmt(p)}% of {_fmt(n)}?",
        "answer_data": {
            "kind": "percent_of",
            "percent": p,
            "of": n,
            "value": round(p * n / 100, 6),
        },
        "source": "bank",
        "is_approved": True,
    }
    for d, p, n in _PERCENT_OF
]
