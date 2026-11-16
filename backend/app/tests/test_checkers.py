"""Answer checkers for every question type, and the leak guard protecting words."""

import pytest

from app.modules.adaptive.checkers import (
    answer_key,
    answers_clash,
    checker_for,
    question_for_teacher,
)
from app.modules.teacher.guard import (
    LeakGuard,
    ProtectedPhrase,
    contains_any,
    filter_board,
)

MC = {
    "kind": "multiple_choice",
    "options": ["Primary key", "Foreign key", "Derived attribute", "Composite index"],
    "correct_index": 1,
    "misconceptions": {"0": "db_primary_foreign_confusion"},
}
MC_TEXT = "In the Orders table, CustomerID is a..."
TF = {"kind": "true_false", "value": False, "misconception_if_wrong": "db_key_not_unique"}
BLANK = {
    "kind": "fill_blank",
    "answers": ["foreign"],
    "wrong_answers": {"primary": "db_primary_foreign_confusion"},
}


# ---------- multiple choice ----------


@pytest.mark.parametrize(
    ("text", "index"),
    [
        ("B", 1),
        ("b", 1),
        ("(b)", 1),
        ("B) Foreign key", 1),
        ("my answer is b", 1),
        ("I think B", 1),
        ("option a", 0),
        ("foreign key", 1),
        ("The foreign key.", 1),
        ("D", 3),
    ],
)
def test_multiple_choice_understands_letters_and_option_text(text: str, index: int) -> None:
    assert checker_for("multiple_choice").interpret(text, MC) == index


@pytest.mark.parametrize("text", ["E", "is it B?", "a bit confused", "what is a key", "B or C"])
def test_multiple_choice_ignores_questions_and_comments(text: str) -> None:
    assert checker_for("multiple_choice").interpret(text, MC) is None


def test_multiple_choice_marking_and_misconception() -> None:
    c = checker_for("multiple_choice")
    assert c.check(MC, 1).is_correct
    wrong = c.check(MC, 0)
    assert not wrong.is_correct and wrong.misconception_code == "db_primary_foreign_confusion"
    assert wrong.display == "A) Primary key"
    assert c.describe(MC) == "B) Foreign key"


def test_multiple_choice_protects_the_letter_and_the_correct_option() -> None:
    visible = question_for_teacher("multiple_choice", MC_TEXT, MC)
    protected = checker_for("multiple_choice").protected(MC, visible)
    for leak in ("The answer is B.", "option B is the one", "It's (B)!", "it is a foreign key"):
        assert contains_any(leak, protected), leak
    for fine in (
        "Look at what each option means.",
        "Option A refers to its own table.",
        "Think about which table the column points to.",
    ):
        assert not contains_any(fine, protected), fine


# ---------- true / false ----------


@pytest.mark.parametrize(
    ("text", "value"),
    [("true", True), ("False", False), ("it's false", False), ("F", False), ("doğru", True)],
)
def test_true_false_understands_answers(text: str, value: bool) -> None:
    assert checker_for("true_false").interpret(text, TF) is value


@pytest.mark.parametrize("text", ["is it true?", "maybe", "yes", "I don't know"])
def test_true_false_ignores_everything_else(text: str) -> None:
    assert checker_for("true_false").interpret(text, TF) is None


def test_true_false_marking_and_protection() -> None:
    c = checker_for("true_false")
    assert c.check(TF, False).is_correct
    wrong = c.check(TF, True)
    assert not wrong.is_correct and wrong.misconception_code == "db_key_not_unique"
    protected = c.protected(TF, "True or false: two rows may share a primary key value.")
    # Any verdict gives it away, even the wrong one.
    for leak in ("The statement is false.", "It's true, actually.", "that is not true"):
        assert contains_any(leak, protected), leak
    assert not contains_any("Think about what a primary key is for.", protected)


# ---------- fill in the blank ----------


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("foreign", "foreign"),
        ("Foreign.", "foreign"),
        ("the foreign", "foreign"),
        ("a foreign key", "foreign key"),
    ],
)
def test_fill_blank_normalises_answers(text: str, answer: str) -> None:
    assert checker_for("fill_blank").interpret(text, BLANK) == answer


@pytest.mark.parametrize(
    "text", ["why?", "I don't know", "ok", "hint", "can you explain this to me again please"]
)
def test_fill_blank_ignores_non_answers(text: str) -> None:
    assert checker_for("fill_blank").interpret(text, BLANK) is None


def test_fill_blank_marking_protection_and_visible_words() -> None:
    c = checker_for("fill_blank")
    assert c.check(BLANK, "foreign").is_correct
    wrong = c.check(BLANK, "primary")
    assert not wrong.is_correct and wrong.misconception_code == "db_primary_foreign_confusion"
    protected = c.protected(BLANK, "A column that refers to another table is a ____ key.")
    assert contains_any("It's called a Foreign key.", protected)
    assert not contains_any("Think about which table it points to.", protected)
    # An answer the student can already see cannot be hidden, so it is not protected.
    assert c.protected({**BLANK, "answers": ["table"]}, "refers to another table") == []


def test_answer_keys_compare_answers_across_question_types() -> None:
    assert answer_key("multiple_choice", MC) == "foreign key"
    assert answer_key("fill_blank", BLANK) == "foreign"
    assert answer_key("numeric", {"value": 20}) == "20"
    # Found live: praising "foreign" must not give away a next answer "Foreign key".
    assert answers_clash("foreign", "foreign key")
    assert answers_clash("20", "20")
    assert not answers_clash("primary", "foreign key")
    assert not answers_clash("2", "20")


# ---------- the guard with words ----------


def _stream(chunks: list[str], protected: list) -> tuple[str, bool]:
    guard = LeakGuard(protected)
    shown = "".join(guard.feed(c) for c in chunks)
    if not guard.leaked:
        shown += guard.finish()
    return shown, guard.leaked


def test_a_protected_phrase_split_across_chunks_is_caught_before_any_of_it_shows() -> None:
    shown, leaked = _stream(
        ["Good thinking. It is called a for", "eign key because it points"],
        [ProtectedPhrase("foreign key")],
    )
    assert leaked
    assert "for" not in shown.split("called a")[-1]  # not even the start of the answer


def test_clean_text_with_protected_words_streams_through_whole() -> None:
    chunks = ["Think about ", "which table ", "the column ", "points to."]
    shown, leaked = _stream(chunks, [ProtectedPhrase("foreign key")])
    assert not leaked and shown == "".join(chunks)


def test_numbers_and_words_can_be_protected_together() -> None:
    protected = [20.0, ProtectedPhrase("primary key")]
    assert _stream(["So it is 2", "0 in the end."], protected)[1]
    assert _stream(["It is the primary", " key."], protected)[1]
    assert not _stream(["Try 25 out of 100 first."], protected)[1]


def test_board_blocks_with_a_protected_phrase_are_dropped() -> None:
    blocks = [
        {"type": "text", "content": "Foreign key = link"},
        {"type": "text", "content": "Rows"},
    ]
    kept, dropped = filter_board(blocks, [ProtectedPhrase("foreign key")])
    assert dropped and kept == [{"type": "text", "content": "Rows"}]
