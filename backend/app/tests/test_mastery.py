"""The mastery model's rules (pure code, no database)."""

import pytest

from app.modules.adaptive import mastery as m


def test_a_clean_first_try_earns_full_credit_and_help_costs_some() -> None:
    assert m.question_outcome(solved=True, wrong_tries=0, hints_used=0) == 1.0
    one_hint = m.question_outcome(solved=True, wrong_tries=0, hints_used=1)
    one_wrong = m.question_outcome(solved=True, wrong_tries=1, hints_used=0)
    assert 0 < one_wrong < one_hint < 1.0
    # Solving it in the end always counts for something; needing the solution does not.
    assert m.question_outcome(solved=True, wrong_tries=5, hints_used=3) == m.MIN_CREDIT_WHEN_SOLVED
    assert m.question_outcome(solved=False, wrong_tries=1, hints_used=3) == 0.0


def test_doing_well_raises_mastery_and_doing_badly_lowers_it() -> None:
    assert m.update(0.5, 3, 1.0) > 0.5
    assert m.update(0.5, 3, 0.0) < 0.5


def test_a_hard_question_solved_counts_more_than_an_easy_one() -> None:
    assert m.update(0.5, 5, 1.0) > m.update(0.5, 1, 1.0)


def test_failing_an_easy_question_costs_more_than_failing_a_hard_one() -> None:
    assert m.update(0.5, 1, 0.0) < m.update(0.5, 5, 0.0)


def test_mastery_stays_between_0_and_1() -> None:
    assert m.update(0.0, 1, 0.0) == 0.0
    assert m.update(1.0, 1, 1.0) == 1.0


def test_next_question_is_aimed_at_about_70_percent_success() -> None:
    for score in (0.2, 0.5, 0.7):
        d = m.target_difficulty(score)
        # The best available difficulty: no other level is closer to the target.
        gaps = {lvl: abs(m.expected_success(score, lvl) - m.TARGET_SUCCESS) for lvl in range(1, 6)}
        assert gaps[d] == pytest.approx(min(gaps.values()), abs=0.1)


def test_difficulty_rises_with_mastery_and_stays_within_1_and_5() -> None:
    levels = [m.target_difficulty(s / 10) for s in range(11)]
    assert levels == sorted(levels)
    assert levels[0] == 1 and levels[-1] == 5


def test_a_student_who_keeps_getting_it_right_reaches_mastery_in_about_ten_questions() -> None:
    score, questions = 0.0, 0
    while score < m.MASTERED_FROM:
        score = m.update(score, m.target_difficulty(score), 1.0)
        questions += 1
    assert 5 <= questions <= 12


@pytest.mark.parametrize(
    ("score", "done", "level"),
    [
        (0.0, 0, "not_started"),
        (0.1, 2, "learning"),
        (0.5, 6, "practising"),
        (0.85, 9, "mastered"),
    ],
)
def test_levels(score: float, done: int, level: str) -> None:
    assert m.level(score, done) == level
