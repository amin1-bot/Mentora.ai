"""The teaching engine: decides what the teacher does next. Pure code, no AI, no database.

The model is the teacher's voice; this module is the teacher's judgment. Every rule here
is deterministic and covered by tests (test_engine.py).

Hint ladder for one question:
  1 = conceptual nudge, 2 = the first step, 3 = a worked example of a similar problem.
  The full solution is shown only after the student has tried at least once AND has
  used all three hints. Then a similar question checks that it stuck.
"""

from dataclasses import dataclass, replace
from typing import Literal

from app.modules.adaptive.answers import AnswerCheck

MAX_HINT = 3
MIN_DIFFICULTY, MAX_DIFFICULTY = 1, 5
LEVEL_UP_AFTER_CORRECT = 3  # in a row
LEVEL_DOWN_AFTER_WRONG = 2  # in a row, on the same question

Action = Literal[
    "introduce",  # start of lesson: short welcome, then the first question
    "praise_and_next",  # correct answer: praise, then a new question
    "address_mistake",  # wrong answer: explain the likely mistake, no answer
    "give_hint",  # next rung of the hint ladder
    "encourage_attempt",  # all hints used but no attempt yet: ask them to try
    "explain_differently",  # "I don't get it": a new explanation from another angle
    "show_solution",  # full worked solution, then a similar question
    "respond",  # a question or comment: answer it and steer back
]

EventKind = Literal["start", "answer", "hint", "dont_get_it", "message"]


@dataclass(frozen=True)
class LessonState:
    has_question: bool
    hint_level: int = 0
    attempts_on_current: int = 0
    wrong_on_current: int = 0
    difficulty: int = 1
    correct_streak: int = 0


@dataclass(frozen=True)
class Decision:
    action: Action
    state: LessonState  # the state after this turn
    ask_new_question: bool = False
    # True when the current question's answer may be said (student got it, or solution).
    reveal_current_answer: bool = False
    misconception_code: str | None = None


def _clamp(level: int) -> int:
    return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, level))


def _next_question_state(state: LessonState, difficulty: int, streak: int) -> LessonState:
    return LessonState(has_question=True, difficulty=_clamp(difficulty), correct_streak=streak)


def decide(state: LessonState, event: EventKind, check: AnswerCheck | None = None) -> Decision:
    if event == "start" or (event == "answer" and not state.has_question):
        if not state.has_question:
            return Decision(
                "introduce",
                _next_question_state(state, state.difficulty, state.correct_streak),
                ask_new_question=True,
            )
        return Decision("respond", state)

    if event == "answer":
        assert check is not None
        attempts = state.attempts_on_current + 1
        if check.is_correct:
            streak = state.correct_streak + 1
            difficulty = state.difficulty
            if streak >= LEVEL_UP_AFTER_CORRECT:
                difficulty, streak = difficulty + 1, 0
            return Decision(
                "praise_and_next",
                _next_question_state(state, difficulty, streak),
                ask_new_question=True,
                reveal_current_answer=True,
            )
        wrong = state.wrong_on_current + 1
        after = replace(
            state, attempts_on_current=attempts, wrong_on_current=wrong, correct_streak=0
        )
        if state.hint_level >= MAX_HINT:
            # Tried, and all hints were used: now the solution, then an easier question.
            return _solution(after)
        if wrong >= LEVEL_DOWN_AFTER_WRONG:
            # Repeated mistakes on the same question: climb one rung of the hint ladder.
            return Decision(
                "give_hint",
                replace(after, hint_level=state.hint_level + 1),
                misconception_code=check.misconception_code,
            )
        return Decision("address_mistake", after, misconception_code=check.misconception_code)

    if event == "hint":
        if not state.has_question:
            return Decision("respond", state)
        if state.hint_level < MAX_HINT:
            return Decision("give_hint", replace(state, hint_level=state.hint_level + 1))
        if state.attempts_on_current >= 1:
            return _solution(state)
        return Decision("encourage_attempt", state)

    if event == "dont_get_it":
        return Decision(
            "explain_differently",
            replace(state, hint_level=max(state.hint_level, 1)) if state.has_question else state,
        )

    return Decision("respond", state)


def _solution(state: LessonState) -> Decision:
    easier = (
        state.difficulty - 1
        if state.wrong_on_current >= LEVEL_DOWN_AFTER_WRONG
        else state.difficulty
    )
    return Decision(
        "show_solution",
        _next_question_state(state, easier, 0),
        ask_new_question=True,
        reveal_current_answer=True,
    )
