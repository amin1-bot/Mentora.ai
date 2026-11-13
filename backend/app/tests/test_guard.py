"""The streaming answer-leak guard."""

from app.modules.teacher.guard import LeakGuard, filter_board


def _run(chunks: list[str], protected: list[float]) -> tuple[str, bool]:
    guard = LeakGuard(protected)
    shown = "".join(guard.feed(c) for c in chunks) + guard.finish()
    return shown, guard.leaked


def test_clean_reply_passes_through_unchanged() -> None:
    shown, leaked = _run(["Think about what ", "25% means. ", "Try again!"], [20])
    assert shown == "Think about what 25% means. Try again!"
    assert not leaked


def test_answer_is_caught_before_it_is_shown() -> None:
    shown, leaked = _run(["Close! The answer is ", "20", " because..."], [20])
    assert leaked
    assert "20" not in shown


def test_answer_split_across_chunks_is_caught() -> None:
    shown, leaked = _run(["So 25% of 80 is 2", "0 in total."], [20])
    assert leaked and "2" not in shown.split("is")[-1]


def test_answer_at_the_very_end_is_caught() -> None:
    _, leaked = _run(["It equals 2", "0"], [20])
    assert leaked


def test_similar_numbers_are_not_mistaken_for_the_answer() -> None:
    shown, leaked = _run(["You said 200, and 20.5 is close to 2.0 times..."], [20])
    assert not leaked
    assert shown.startswith("You said 200")


def test_decimal_answers() -> None:
    _, leaked = _run(["That gives 3.", "2 exactly"], [3.2])
    assert leaked
    shown, leaked = _run(["Sentence ends with 3."], [3.2])
    assert not leaked and shown == "Sentence ends with 3."


def test_text_held_back_is_released_at_the_end() -> None:
    guard = LeakGuard([20])
    assert guard.feed("There are 1") == "There are "
    assert guard.finish() == "1"


def test_board_blocks_with_the_answer_are_dropped() -> None:
    blocks = [
        {"type": "equation", "content": "0.25 \\times 80"},
        {"type": "equation", "content": "0.25 \\times 80 = 20"},
    ]
    kept, dropped = filter_board(blocks, [20])
    assert dropped and kept == blocks[:1]
