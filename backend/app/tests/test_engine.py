"""The teaching engine's rules: hint ladder, solution gating, finished-question results."""

from app.modules.adaptive.answers import AnswerCheck
from app.modules.adaptive.engine import LessonState, QuestionResult, decide

CORRECT = AnswerCheck(20, True, None)
WRONG = AnswerCheck(2000, False, "percent_forgot_divide_100")
ON_QUESTION = LessonState(has_question=True)


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
    state = LessonState(has_question=True, hint_level=3, attempts_on_current=1)
    d = decide(state, "hint")
    assert d.action == "show_solution"
    assert d.reveal_current_answer and d.ask_new_question
    assert d.state.hint_level == 0  # fresh ladder for the new question


def test_wrong_answer_after_all_hints_shows_solution() -> None:
    state = LessonState(has_question=True, hint_level=3)
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


def test_correct_answer_reports_how_the_question_went() -> None:
    state = LessonState(has_question=True, hint_level=1, attempts_on_current=1, wrong_on_current=1)
    d = decide(state, "answer", CORRECT)
    assert d.action == "praise_and_next" and d.reveal_current_answer and d.ask_new_question
    assert d.finished_question == QuestionResult(solved=True, wrong_tries=1, hints_used=1)
    assert d.state.hint_level == 0 and d.state.wrong_on_current == 0


def test_solution_reports_an_unsolved_question_including_the_last_wrong_try() -> None:
    state = LessonState(has_question=True, hint_level=3, attempts_on_current=1, wrong_on_current=1)
    d = decide(state, "answer", WRONG)
    assert d.action == "show_solution"
    assert d.finished_question == QuestionResult(solved=False, wrong_tries=2, hints_used=3)


def test_unfinished_questions_report_nothing() -> None:
    for event, check in (("answer", WRONG), ("hint", None), ("dont_get_it", None)):
        assert decide(ON_QUESTION, event, check).finished_question is None  # type: ignore[arg-type]
    assert decide(LessonState(has_question=False), "start").finished_question is None


def test_dont_get_it_explains_differently_without_revealing() -> None:
    d = decide(ON_QUESTION, "dont_get_it")
    assert d.action == "explain_differently"
    assert not d.reveal_current_answer


def test_free_messages_get_a_response() -> None:
    assert decide(ON_QUESTION, "message").action == "respond"
