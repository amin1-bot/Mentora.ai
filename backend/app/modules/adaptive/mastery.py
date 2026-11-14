"""The mastery model: how well a student knows one skill, and how hard the next question
should be. Pure code, no database (covered by test_mastery.py).

Mastery is a score from 0 (new) to 1 (fully mastered), one per student per topic. It is
updated once per finished question, not on every message:

1. How well did that question go? (`question_outcome`)
   Correct at the first try without hints = 1.0. Each hint and each wrong try lowers it.
   A question that ended with the solution being shown = 0.0.
2. How well did we expect it to go? (`expected_success`)
   A student with high mastery is expected to solve an easy question; a hard question is
   less certain. This is a simple logistic curve, the same idea as the Elo rating in chess.
3. Move the score by the surprise: score += STEP x (outcome - expected).
   Doing better than expected raises mastery; doing worse lowers it. Easy questions done
   well raise it only a little, hard questions done well raise it a lot.

The next question is picked so the expected success is about 70%: hard enough to learn
from, easy enough not to discourage ("desirable difficulty"). The numbers below are
starting values to be tuned with pilot data (blueprint Phase 8 gate).
"""

import math
from typing import Literal

STEP = 0.3  # how far one question can move the score
SLOPE = 6.0  # how sharply success chances change with the gap between skill and difficulty
TARGET_SUCCESS = 0.7
MIN_DIFFICULTY, MAX_DIFFICULTY = 1, 5

HINT_COST = 0.2
WRONG_TRY_COST = 0.25
MIN_CREDIT_WHEN_SOLVED = 0.2  # solving it in the end always counts for something

PRACTISING_FROM = 0.4
MASTERED_FROM = 0.8

Level = Literal["not_started", "learning", "practising", "mastered"]


def difficulty_point(difficulty: int) -> float:
    """Where a difficulty sits on the 0..1 mastery scale: 1 -> 0.1 ... 5 -> 0.9."""
    return (difficulty - 0.5) / MAX_DIFFICULTY


def expected_success(mastery: float, difficulty: int) -> float:
    return 1 / (1 + math.exp(-SLOPE * (mastery - difficulty_point(difficulty))))


def question_outcome(*, solved: bool, wrong_tries: int, hints_used: int) -> float:
    if not solved:
        return 0.0
    credit = 1.0 - HINT_COST * hints_used - WRONG_TRY_COST * wrong_tries
    return max(MIN_CREDIT_WHEN_SOLVED, credit)


def update(mastery: float, difficulty: int, outcome: float) -> float:
    new = mastery + STEP * (outcome - expected_success(mastery, difficulty))
    return round(min(1.0, max(0.0, new)), 4)


def target_difficulty(mastery: float) -> int:
    """The difficulty at which this student should succeed about TARGET_SUCCESS of the time."""
    point = mastery - math.log(TARGET_SUCCESS / (1 - TARGET_SUCCESS)) / SLOPE
    level = round(point * MAX_DIFFICULTY + 0.5)
    return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, level))


def level(mastery: float, questions_done: int) -> Level:
    if questions_done == 0:
        return "not_started"
    if mastery >= MASTERED_FROM:
        return "mastered"
    if mastery >= PRACTISING_FROM:
        return "practising"
    return "learning"
