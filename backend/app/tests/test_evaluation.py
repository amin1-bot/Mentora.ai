"""The evaluation harness itself, run with the scripted provider (no network, no cost)."""

import asyncio

from app.tests.fakes import Reply, ScriptedProvider
from evaluation.cases import CASES
from evaluation.run_eval import number_words, run, word_leak


def test_every_case_runs_and_the_report_has_all_metrics() -> None:
    provider = ScriptedProvider()
    summary, results = asyncio.run(run(provider, "claude-opus-5-5"))
    assert len(results) == len(CASES)
    assert summary["raw_leak_rate"] == 0 and summary["final_leak_rate"] == 0
    assert summary["estimated_cost_usd"] is not None
    actions = {r.case: r.action for r in results}
    assert actions["wrong_forgot_divide_100"] == "address_mistake"
    assert actions["solution_after_attempts"] == "show_solution"
    assert actions["hint_3_worked_example"] == "give_hint"


def test_a_leaking_model_shows_up_in_the_raw_leak_rate() -> None:
    leaky = ScriptedProvider(default=Reply(["The answer is 20."]))
    case = next(c for c in CASES if c.id == "ask_for_answer")
    summary, results = asyncio.run(run(leaky, "claude-opus-5-5", cases=[case]))
    assert summary["raw_leak_rate"] == 1.0
    assert summary["final_leak_rate"] == 0  # the guard still protected the student
    assert results[0].fallback == "leak"


def test_word_form_leaks_are_counted() -> None:
    assert number_words(20) == "twenty" and number_words(42) == "forty-two"
    assert word_leak("It is twenty!", [20])
    assert not word_leak("twenty-five percent", [20])
    wordy = ScriptedProvider(default=Reply(["It is twenty."]))
    case = next(c for c in CASES if c.id == "words_instead_of_digits")
    summary, _ = asyncio.run(run(wordy, "claude-opus-5-5", cases=[case]))
    assert summary["word_leaks"] == 1 and summary["final_leak_rate"] == 1.0
