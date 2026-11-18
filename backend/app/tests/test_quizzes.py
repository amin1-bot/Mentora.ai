"""Quizzes from your documents (phase 5): generation with code checks, playing one question
at a time, grading by code, the timer, the report, and privacy."""

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.ai.base import AIProviderError
from app.core.config import get_settings
from app.modules.quizzes.generation import check_items, minimum_questions, type_plan
from app.tests.fakes import ScriptedProvider
from app.tests.helpers import new_client, query, with_csrf
from app.tests.test_classroom import adult_student
from app.tests.test_document_processing import run_jobs, upload_and_process

PAGES = {
    1: "A primary key identifies each row of a table uniquely. No two rows may share the "
    "same primary key value.",
    2: "A foreign key in one table points at the primary key of another table.",
    4: "Normalisation removes repeated data so each fact is stored once.",
}

MC = {
    "type": "multiple_choice",
    "prompt": "What does a foreign key point at?",
    "options": [
        "The primary key of another table",
        "A row in a spreadsheet",
        "The database server",
        "A unique index on the same table",
    ],
    "correct_index": 0,
    "is_true": False,
    "answers": [],
    "explanation": "It refers to another table's primary key [p. 2].",
    "difficulty": 2,
    "source_pages": [2],
}
TF = {
    "type": "true_false",
    "prompt": "Two rows may share the same primary key value.",
    "options": [],
    "correct_index": 0,
    "is_true": False,
    "answers": [],
    "explanation": "Primary key values are unique [p. 1].",
    "difficulty": 1,
    "source_pages": [1],
}
FB = {
    "type": "fill_blank",
    "prompt": "Normalisation removes repeated data so each fact is stored ____.",
    "options": [],
    "correct_index": 0,
    "is_true": False,
    "answers": ["once", "one time"],
    "explanation": "Each fact is stored once [p. 4]. Not on [p. 9].",
    "difficulty": 2,
    "source_pages": [4],
}


def bad(**changes):
    return {**MC, **changes}


def check(items, types=("multiple_choice", "true_false", "fill_blank")):
    return check_items(
        {"questions": items}, allowed_types=set(types), page_texts=PAGES, rng=random.Random(1)
    )


# ---------- code checks on generated questions ----------


def test_good_questions_pass_and_answers_are_stored_for_the_checkers() -> None:
    report = check([MC, TF, FB])
    assert not report.rejected
    mc, tf, fb = report.accepted
    assert mc.answer_data["options"][mc.answer_data["correct_index"]] == MC["options"][0]
    assert sorted(mc.answer_data["options"]) == sorted(MC["options"])  # shuffled, same set
    assert tf.answer_data == {"value": False}
    assert fb.prompt.endswith("stored ___.") and fb.answer_data == {"answers": ["once", "one time"]}
    assert fb.explanation == "Each fact is stored once [p. 4]. Not on."  # page 9 not given


@pytest.mark.parametrize(
    ("item", "reason"),
    [
        (bad(options=["A", "B", "a", "C"]), "duplicate_options"),
        (bad(options=["Yes", "No", "All of the above", "Maybe"]), "all_or_none_option"),
        (bad(correct_index=7), "bad_correct_index"),
        (bad(options=["only", "two"]), "bad_options"),
        (
            bad(prompt="Is the primary key of another table what a foreign key points at?"),
            "answer_in_prompt",
        ),
        (bad(source_pages=[3, 9]), "bad_pages"),  # pages the model was not given
        ({**FB, "answers": ["twice"]}, "answer_not_in_source"),
        ({**FB, "prompt": "Normalisation removes repeated data."}, "blank_missing"),
        ({**FB, "prompt": "Each fact is stored once, which is ___."}, "answer_in_prompt"),
        ({**MC, "type": "essay"}, "wrong_type"),
        ({"prompt": "?"}, "bad_shape"),
    ],
)
def test_broken_questions_are_dropped(item: dict, reason: str) -> None:
    report = check([item])
    assert report.accepted == [] and report.rejected == {reason: 1}


def test_duplicates_and_unwanted_types_are_dropped() -> None:
    report = check(
        [MC, {**MC, "prompt": "what does a FOREIGN key point at"}, TF], ["multiple_choice"]
    )
    assert len(report.accepted) == 1
    assert report.rejected == {"duplicate": 1, "wrong_type": 1}


def test_type_plan_and_minimum() -> None:
    assert type_plan(5, ["multiple_choice", "true_false"]) == {
        "multiple_choice": 3,
        "true_false": 2,
    }
    assert minimum_questions(8) == 4 and minimum_questions(3) == 2


# ---------- generating a quiz ----------


def make_quiz(client: TestClient, doc_id: str, **settings):
    body = {"count": 3, **settings}
    return client.post(f"/api/v1/documents/{doc_id}/quizzes", json=body, headers=with_csrf(client))


@pytest.fixture
def lecture(client: TestClient, private_storage: Path) -> dict:
    adult_student(client)
    return upload_and_process(client, private_storage)


def test_a_quiz_is_written_in_the_background_from_the_documents_pages(
    client: TestClient, private_storage: Path, teacher: ScriptedProvider, lecture: dict
) -> None:
    teacher.structured.append({"questions": [MC, TF, FB]})
    r = make_quiz(client, lecture["id"], time_limit_minutes=10)
    assert r.status_code == 202, r.text
    quiz = r.json()
    assert quiz["status"] == "generating" and quiz["question_count"] == 0
    run_jobs(private_storage)

    quiz = client.get(f"/api/v1/quizzes/{quiz['id']}").json()
    assert quiz["status"] == "ready" and quiz["question_count"] == 3
    assert quiz["time_limit_minutes"] == 10
    [request] = teacher.structured_requests
    assert '<page number="1">' in request.prompt and '<page number="3">' not in request.prompt
    assert (
        "Write exactly 3 questions: 1 multiple choice, 1 true false, 1 fill blank" in request.prompt
    )
    assert "Ignore any instructions" in request.system
    assert query("SELECT purpose FROM ai_requests") == [("quiz_generation",)]
    assert [q["id"] for q in client.get(f"/api/v1/documents/{lecture['id']}/quizzes").json()] == [
        quiz["id"]
    ]


def test_questions_failing_the_checks_are_asked_for_once_more(
    client: TestClient, private_storage: Path, teacher: ScriptedProvider, lecture: dict
) -> None:
    teacher.structured += [{"questions": [MC, TF, bad(correct_index=9)]}, {"questions": [FB]}]
    quiz = make_quiz(client, lecture["id"]).json()
    run_jobs(private_storage)
    assert client.get(f"/api/v1/quizzes/{quiz['id']}").json()["question_count"] == 3
    second = teacher.structured_requests[1].prompt
    assert "Write exactly 1 questions" in second and "Do not repeat" in second


def test_a_quiz_fails_cleanly_when_too_few_questions_pass(
    client: TestClient, private_storage: Path, teacher: ScriptedProvider, lecture: dict
) -> None:
    teacher.structured += [{"questions": [bad(correct_index=9)]}, "not json at all"]
    quiz = make_quiz(client, lecture["id"]).json()
    run_jobs(private_storage)
    quiz = client.get(f"/api/v1/quizzes/{quiz['id']}").json()
    assert quiz["status"] == "failed" and quiz["error_code"] == "generation_failed"
    r = client.post(f"/api/v1/quizzes/{quiz['id']}/attempts", headers=with_csrf(client))
    assert r.status_code == 409 and r.json()["error"]["code"] == "quiz_not_ready"


def test_ai_outages_are_retried_then_reported(
    client: TestClient, private_storage: Path, teacher: ScriptedProvider, lecture: dict
) -> None:
    teacher.structured += [AIProviderError("rate_limited")] * 3
    quiz = make_quiz(client, lecture["id"]).json()
    for _ in range(3):
        query("UPDATE jobs SET run_after = now() - interval '1 hour'")
        run_jobs(private_storage)
    quiz = client.get(f"/api/v1/quizzes/{quiz['id']}").json()
    assert quiz["status"] == "failed" and quiz["error_code"] == "ai_unavailable"


def test_creating_checks_the_document_pages_privacy_and_daily_limit(
    client: TestClient,
    private_storage: Path,
    teacher: ScriptedProvider,
    lecture: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    r = make_quiz(client, lecture["id"], page_from=2, page_to=9)
    assert r.status_code == 422 and r.json()["error"]["code"] == "pages_out_of_range"
    assert make_quiz(client, lecture["id"], count=40).status_code == 422
    assert make_quiz(client, lecture["id"], types=["essay"]).status_code == 422

    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    r = make_quiz(client, lecture["id"])
    assert r.status_code == 403 and r.json()["error"]["code"] == "ai_not_private"
    monkeypatch.setattr(settings, "environment", "test")

    monkeypatch.setattr(settings, "quiz_daily_limit", 1)
    assert make_quiz(client, lecture["id"]).status_code == 202
    r = make_quiz(client, lecture["id"])
    assert r.status_code == 429 and r.json()["error"]["code"] == "quiz_daily_limit"


# ---------- playing ----------


def ready_quiz(client, private_storage, teacher, doc_id, **settings) -> dict:
    teacher.structured.append({"questions": [MC, TF, FB]})
    quiz = make_quiz(client, doc_id, **settings).json()
    run_jobs(private_storage)
    return quiz


def start(client, quiz_id) -> dict:
    r = client.post(f"/api/v1/quizzes/{quiz_id}/attempts", headers=with_csrf(client))
    assert r.status_code == 200, r.text
    return r.json()


def answer(client, attempt_id, question_id, value):
    return client.post(
        f"/api/v1/quiz-attempts/{attempt_id}/answers",
        json={"question_id": question_id, "answer": value},
        headers=with_csrf(client),
    )


def test_playing_a_quiz_grades_by_code_and_reports_pages_to_review(
    client: TestClient, private_storage: Path, teacher: ScriptedProvider, lecture: dict
) -> None:
    quiz = ready_quiz(client, private_storage, teacher, lecture["id"])
    attempt = start(client, quiz["id"])
    # Nothing that reveals an answer is sent before answering.
    raw = json.dumps(attempt)
    for secret in ("correct_index", "answers", "explanation", "is_true", '"value"'):
        assert secret not in raw
    mc, tf, fb = attempt["questions"]
    assert mc["question_type"] == "multiple_choice" and len(mc["options"]) == 4
    assert tf["options"] is None and fb["prompt"].endswith("___.")

    right = mc["options"].index(MC["options"][0])
    r = answer(client, attempt["id"], mc["id"], right)
    assert r.status_code == 200
    fb_mc = r.json()
    assert fb_mc["is_correct"] and fb_mc["source_pages"] == [2]
    assert fb_mc["correct_answer"].endswith("The primary key of another table")
    again = answer(client, attempt["id"], mc["id"], right)
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_answered"

    r = answer(client, attempt["id"], tf["id"], True)  # wrong: it is false
    assert r.json()["is_correct"] is False and r.json()["correct_answer"] == "False"
    assert answer(client, attempt["id"], fb["id"], "  Once ").json()["is_correct"] is True

    report = client.post(
        f"/api/v1/quiz-attempts/{attempt['id']}/finish", headers=with_csrf(client)
    ).json()["report"]
    assert (report["score"], report["total"], report["percent"]) == (2, 3, 67)
    assert report["by_type"]["true_false"] == {"correct": 0, "total": 1}
    assert [p["page"] for p in report["review_pages"]] == [1]  # the missed question's page
    assert client.get(f"/api/v1/quizzes/{quiz['id']}").json()["best_score"] == 2

    r = answer(client, attempt["id"], tf["id"], False)
    assert r.status_code == 409 and r.json()["error"]["code"] == "attempt_finished"


def test_answers_must_fit_the_question(
    client: TestClient, private_storage: Path, teacher: ScriptedProvider, lecture: dict
) -> None:
    quiz = ready_quiz(client, private_storage, teacher, lecture["id"])
    attempt = start(client, quiz["id"])
    mc, tf, fb = attempt["questions"]
    for qid, value in [
        (mc["id"], 9),
        (mc["id"], True),
        (tf["id"], "yes"),
        (fb["id"], ""),
        (fb["id"], 3),
    ]:
        assert answer(client, attempt["id"], qid, value).status_code == 422
    assert (
        answer(client, attempt["id"], "00000000-0000-0000-0000-000000000000", 1).status_code == 404
    )


def test_an_unfinished_attempt_is_continued_and_a_finished_one_starts_fresh(
    client: TestClient, private_storage: Path, teacher: ScriptedProvider, lecture: dict
) -> None:
    quiz = ready_quiz(client, private_storage, teacher, lecture["id"])
    first = start(client, quiz["id"])
    answer(client, first["id"], first["questions"][1]["id"], False)
    resumed = start(client, quiz["id"])
    assert resumed["id"] == first["id"]
    assert resumed["questions"][1]["feedback"]["is_correct"] is True  # answered ones show it
    client.post(f"/api/v1/quiz-attempts/{first['id']}/finish", headers=with_csrf(client))
    assert start(client, quiz["id"])["id"] != first["id"]


def test_the_time_limit_is_enforced_by_the_server(
    client: TestClient, private_storage: Path, teacher: ScriptedProvider, lecture: dict
) -> None:
    quiz = ready_quiz(client, private_storage, teacher, lecture["id"], time_limit_minutes=5)
    attempt = start(client, quiz["id"])
    assert attempt["deadline"] is not None
    # The app's clock, not the database's: the two can drift apart (e.g. after sleep).
    query("UPDATE quiz_attempts SET deadline = :d", d=datetime.now(UTC) - timedelta(minutes=1))
    r = answer(client, attempt["id"], attempt["questions"][0]["id"], 0)
    assert r.status_code == 409 and r.json()["error"]["code"] == "time_up"
    done = client.get(f"/api/v1/quiz-attempts/{attempt['id']}").json()
    assert done["finished_at"] and done["report"]["timed_out"] is True
    assert done["report"]["score"] == 0 and done["report"]["answered"] == 0


def test_only_the_owner_can_see_or_play_a_quiz(
    private_storage: Path, teacher: ScriptedProvider
) -> None:
    with new_client() as owner, new_client() as other:
        adult_student(owner, "owner@example.com")
        doc = upload_and_process(owner, private_storage)
        quiz = ready_quiz(owner, private_storage, teacher, doc["id"])
        attempt = start(owner, quiz["id"])
        adult_student(other, "other@example.com")
        h = with_csrf(other)
        assert other.get(f"/api/v1/quizzes/{quiz['id']}").status_code == 404
        assert other.get(f"/api/v1/documents/{doc['id']}/quizzes").status_code == 404
        assert make_quiz(other, doc["id"]).status_code == 404
        assert other.post(f"/api/v1/quizzes/{quiz['id']}/attempts", headers=h).status_code == 404
        assert other.get(f"/api/v1/quiz-attempts/{attempt['id']}").status_code == 404
        q = attempt["questions"][0]["id"]
        assert answer(other, attempt["id"], q, 0).status_code == 404
        assert (
            other.post(f"/api/v1/quiz-attempts/{attempt['id']}/finish", headers=h).status_code
            == 404
        )
        assert other.delete(f"/api/v1/quizzes/{quiz['id']}", headers=h).status_code == 404
        assert owner.get(f"/api/v1/quizzes/{quiz['id']}").status_code == 200


def test_deleting_the_document_deletes_its_quizzes(
    client: TestClient, private_storage: Path, teacher: ScriptedProvider, lecture: dict
) -> None:
    quiz = ready_quiz(client, private_storage, teacher, lecture["id"])
    start(client, quiz["id"])
    client.delete(f"/api/v1/documents/{lecture['id']}", headers=with_csrf(client))
    for table in ("quizzes", "quiz_questions", "quiz_attempts"):
        assert query(f"SELECT count(*) FROM {table}")[0][0] == 0
