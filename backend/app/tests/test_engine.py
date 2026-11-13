"""The teaching engine's rules: hint ladder, solution gating, difficulty changes."""

from app.modules.adaptive.answers import AnswerCheck
from app.modules.adaptive.engine import LessonState, decide

CORRECT = AnswerCheck(20, True, None)
WRONG = AnswerCheck(2000, False, "percent_forgot_divide_100")
ON_QUESTION = LessonState(has_question=True, difficulty=3)


def test_start_introduces_and_asks_a_question() -> None:
    d = decide(LessonState(has_question=False), "start")
    assert d.action == "introduce" and d.ask_new_question


def test_hint_ladder_climbs_one_rung_at_a_time() -> None:
    state = ON_QUESTION
    for rung in (1, 2, 3):
        d = decide(state, "hint")
        assert d.action == "give_hint"
        assert d.state.hint_level == rung
        assert not d.reveal_current_answer
        state = d.state


def test_no_solution_without_an_honest_attempt() -> None:
    all_hints_no_attempt = LessonState(has_question=True, hint_level=3)
    d = decide(all_hints_no_attempt, "hint")
    assert d.action == "encourage_attempt"
    assert not d.reveal_current_answer


def test_solution_after_attempt_and_all_hints_then_a_similar_question() -> None:
    state = LessonState(has_question=True, hint_level=3, attempts_on_current=1, difficulty=3)
    d = decide(state, "hint")
    assert d.action == "show_solution"
    assert d.reveal_current_answer and d.ask_new_question
    assert d.state.hint_level == 0  # fresh ladder for the new question


def test_wrong_answer_after_all_hints_shows_solution() -> None:
    state = LessonState(has_question=True, hint_level=3, difficulty=3)
    assert decide(state, "answer", WRONG).action == "show_solution"


def test_first_wrong_answer_addresses_the_misconception() -> None:
    d = decide(ON_QUESTION, "answer", WRONG)
    assert d.action == "address_mistake"
    assert d.misconception_code == "percent_forgot_divide_100"
    assert not d.reveal_current_answer
    assert d.state.attempts_on_current == 1


def test_second_wrong_answer_gives_the_next_hint() -> None:
    once = decide(ON_QUESTION, "answer", WRONG).state
    d = decide(once, "answer", WRONG)
    assert d.action == "give_hint"
    assert d.state.hint_level == 1


def test_difficulty_rises_after_three_correct_in_a_row() -> None:
    state = ON_QUESTION
    levels = []
    for _ in range(3):
        d = decide(state, "answer", CORRECT)
        assert d.action == "praise_and_next" and d.reveal_current_answer
        levels.append(d.state.difficulty)
        state = d.state
    assert levels == [3, 3, 4]


def test_difficulty_drops_after_repeated_mistakes() -> None:
    state = LessonState(has_question=True, hint_level=3, wrong_on_current=1, difficulty=3)
    d = decide(state, "answer", WRONG)
    assert d.action == "show_solution"
    assert d.state.difficulty == 2


def test_difficulty_stays_within_1_and_5() -> None:
    top = LessonState(has_question=True, difficulty=5, correct_streak=2)
    assert decide(top, "answer", CORRECT).state.difficulty == 5
    bottom = LessonState(has_question=True, hint_level=3, wrong_on_current=1, difficulty=1)
    assert decide(bottom, "answer", WRONG).state.difficulty == 1


def test_dont_get_it_explains_differently_without_revealing() -> None:
    d = decide(ON_QUESTION, "dont_get_it")
    assert d.action == "explain_differently"
    assert not d.reveal_current_answer


def test_free_messages_get_a_response() -> None:
    assert decide(ON_QUESTION, "message").action == "respond"
