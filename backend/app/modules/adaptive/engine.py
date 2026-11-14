"""The teaching engine: decides what the teacher does next. Pure code, no AI, no database.

The model is the teacher's voice; this module is the teacher's judgment. Every rule here
is deterministic and covered by tests (test_engine.py).

Hint ladder for one question:
  1 = conceptual nudge, 2 = the first step, 3 = a worked example of a similar problem.
  The full solution is shown only after the student has tried at least once AND has
  used all three hints. Then a similar question checks that it stuck.

The engine decides *what* happens next. How hard the next question is comes from the
student's saved mastery (adaptive/mastery.py), so it carries over between lessons.
"""

from dataclasses import dataclass, replace
from typing import Literal

from app.modules.adaptive.answers import AnswerCheck

MAX_HINT = 3
HINT_AFTER_WRONG = 2  # wrong tries on the same question before the next hint rung

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
    correct_streak: int = 0


@dataclass(frozen=True)
class Decision:
    action: Action
    state: LessonState  # the state after this turn
    ask_new_question: bool = False
    # True when the current question's answer may be said (student got it, or solution).
    reveal_current_answer: bool = False
    misconception_code: str | None = None
    # Set when the current question is finished: how it went, for the mastery update.
    finished_question: "QuestionResult | None" = None


@dataclass(frozen=True)
class QuestionResult:
    solved: bool  # False when the solution had to be shown
    wrong_tries: int
    hints_used: int


def _next_question_state(streak: int) -> LessonState:
    return LessonState(has_question=True, correct_streak=streak)


def decide(state: LessonState, event: EventKind, check: AnswerCheck | None = None) -> Decision:
    if event == "start" or (event == "answer" and not state.has_question):
        if not state.has_question:
            return Decision(
                "introduce", _next_question_state(state.correct_streak), ask_new_question=True
            )
        return Decision("respond", state)

    if event == "answer":
        assert check is not None
        attempts = state.attempts_on_current + 1
        if check.is_correct:
            return Decision(
                "praise_and_next",
                _next_question_state(state.correct_streak + 1),
                ask_new_question=True,
                reveal_current_answer=True,
                finished_question=QuestionResult(
                    solved=True, wrong_tries=state.wrong_on_current, hints_used=state.hint_level
                ),
            )
        wrong = state.wrong_on_current + 1
        after = replace(
            state, attempts_on_current=attempts, wrong_on_current=wrong, correct_streak=0
        )
        if state.hint_level >= MAX_HINT:
            # Tried, and all hints were used: now the solution, then another question.
            return _solution(after)
        if wrong >= HINT_AFTER_WRONG:
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
    # The mastery update makes the next question easier when this one went badly.
    return Decision(
        "show_solution",
        _next_question_state(0),
        ask_new_question=True,
        reveal_current_answer=True,
        finished_question=QuestionResult(
            solved=False, wrong_tries=state.wrong_on_current, hints_used=state.hint_level
        ),
    )
