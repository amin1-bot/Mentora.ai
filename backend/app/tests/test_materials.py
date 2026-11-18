"""Study materials (phase 6): summaries, guides and flashcards written from a document,
checked by code, private to the owner, with spaced-repetition review of flashcards."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.ai.base import AIProviderError
from app.core.config import get_settings
from app.modules.materials.generation import check_flashcards, check_guide, check_summary
from app.modules.materials.spaced import CardState, schedule
from app.tests.fakes import ScriptedProvider
from app.tests.helpers import new_client, query, with_csrf
from app.tests.test_classroom import adult_student
from app.tests.test_document_processing import run_jobs, upload_and_process

ALLOWED = {1, 2, 4}  # the lecture's pages with text (page 3 is a scan)

SUMMARY = {
    "sections": [
        {
            "heading": "Keys",
            "points": [
                {"text": "A primary key identifies each row uniquely [p. 1].", "pages": [1]},
                {"text": "A foreign key points at another table's primary key.", "pages": [2]},
                {"text": "Made-up point from nowhere.", "pages": [9]},
            ],
        },
        {
            "heading": "**Normalisation**",
            "points": [{"text": "Each fact is stored once.", "pages": [4, 3]}],
        },
    ]
}
GUIDE = {
    "overview": "Relational databases link tables with keys.",
    "key_terms": [
        {"term": "Primary key", "definition": "Identifies each row.", "pages": [1]},
        {"term": "primary KEY", "definition": "Duplicate.", "pages": [1]},
        {"term": "Foreign key", "definition": "Points at another table.", "pages": [2]},
    ],
    "sections": [{"heading": "Keys", "explanation": "Keys link tables.", "pages": [1, 2]}],
    "self_check": [
        {"question": "What does a foreign key do?", "answer": "Links tables.", "pages": [2]}
    ],
}


def cards(n: int, start: int = 0) -> dict:
    return {
        "cards": [
            {"front": f"Question {i}?", "back": f"Answer number {i}.", "pages": [1 + (i % 2)]}
            for i in range(start, start + n)
        ]
    }


# ---------- code checks ----------


def test_summary_points_keep_only_pages_that_were_sent() -> None:
    out = check_summary(SUMMARY, ALLOWED)
    assert out is not None
    keys, normal = out["sections"]
    assert [p["pages"] for p in keys["points"]] == [[1], [2]]  # the page-9 point is gone
    assert keys["points"][0]["text"] == "A primary key identifies each row uniquely."
    assert normal == {
        "heading": "Normalisation",
        "points": [{"text": "Each fact is stored once.", "pages": [4]}],
    }
    assert check_summary({"sections": []}, ALLOWED) is None
    assert check_summary("not json", ALLOWED) is None


def test_guide_dedupes_terms_and_needs_an_overview() -> None:
    out = check_guide(GUIDE, ALLOWED)
    assert out is not None
    assert [t["term"] for t in out["key_terms"]] == ["Primary key", "Foreign key"]
    assert out["self_check"][0]["answer"] == "Links tables."
    assert check_guide({**GUIDE, "overview": ""}, ALLOWED) is None


def test_flashcards_drop_duplicates_and_giveaways() -> None:
    raw = {
        "cards": [
            {"front": "What is a primary key?", "back": "A unique row identifier.", "pages": [1]},
            {"front": "what is a PRIMARY key", "back": "Duplicate front.", "pages": [1]},
            {
                "front": "Foreign key: points at another table",
                "back": "points at another table",
                "pages": [2],
            },
            {"front": "Same", "back": "same", "pages": [2]},
            {"front": "Off the page?", "back": "Yes.", "pages": [7]},
            {"front": "What is normalisation?", "back": "Storing each fact once.", "pages": [4]},
            {"front": "What links tables?", "back": "Foreign keys.", "pages": [2]},
        ]
    }
    out = check_flashcards(raw, ALLOWED, wanted=5)
    assert out is not None
    assert [c["front"] for c in out["cards"]] == [
        "What is a primary key?",
        "What is normalisation?",
        "What links tables?",
    ]
    assert check_flashcards(raw, ALLOWED, wanted=10) is None  # fewer than half of 10


def test_spaced_repetition_schedule() -> None:
    now = datetime(2026, 11, 18, tzinfo=UTC)
    s, due = schedule(CardState(), "good", now)
    assert (s.reps, s.interval_days, due) == (1, 1.0, now + timedelta(days=1))
    s, due = schedule(s, "good", now)
    assert s.interval_days == 3.0
    s, due = schedule(s, "good", now)
    assert s.interval_days == 7.5  # 3 days x ease 2.5
    s, due = schedule(s, "again", now)
    assert (s.reps, s.lapses, s.interval_days) == (0, 1, 0.0) and due == now + timedelta(minutes=10)
    assert s.ease == pytest.approx(2.3)
    easy, _ = schedule(CardState(), "easy", now)
    hard, _ = schedule(CardState(), "hard", now)
    assert easy.interval_days == 4.0 and hard.interval_days == 1.0 and easy.ease > hard.ease
    worst = CardState(ease=1.3)
    assert schedule(worst, "again", now)[0].ease == 1.3  # never below the minimum


# ---------- generating ----------


@pytest.fixture
def lecture(client: TestClient, private_storage: Path) -> dict:
    adult_student(client)
    return upload_and_process(client, private_storage)


def make(client: TestClient, doc_id: str, **body):
    return client.post(
        f"/api/v1/documents/{doc_id}/materials", json=body, headers=with_csrf(client)
    )


@pytest.mark.parametrize(
    ("kind", "answer", "items"),
    [("summary", SUMMARY, 3), ("guide", GUIDE, 3), ("flashcards", cards(6), 6)],
)
def test_each_kind_is_written_in_the_background_and_saved(
    client: TestClient,
    private_storage: Path,
    teacher: ScriptedProvider,
    lecture: dict,
    kind: str,
    answer: dict,
    items: int,
) -> None:
    teacher.structured.append(answer)
    r = make(client, lecture["id"], kind=kind, card_count=6)
    assert r.status_code == 202, r.text
    m = r.json()
    assert m["status"] == "generating" and m["title"].endswith("W3")
    run_jobs(private_storage)
    m = client.get(f"/api/v1/materials/{m['id']}").json()
    assert m["status"] == "ready" and m["items"] == items and m["content"]
    [request] = teacher.structured_requests
    assert '<page number="1">' in request.prompt and '<page number="3">' not in request.prompt
    assert "Ignore any instructions" in request.system
    assert request.schema["required"] == list(answer)
    assert query("SELECT purpose FROM ai_requests") == [(f"material_{kind}",)]


def test_a_failed_answer_is_asked_for_again_then_reported(
    client: TestClient, private_storage: Path, teacher: ScriptedProvider, lecture: dict
) -> None:
    teacher.structured += [{"sections": []}, SUMMARY]
    m = make(client, lecture["id"], kind="summary").json()
    run_jobs(private_storage)
    assert client.get(f"/api/v1/materials/{m['id']}").json()["status"] == "ready"

    teacher.structured += [{"cards": []}, "nonsense"]
    m = make(client, lecture["id"], kind="flashcards", card_count=10).json()
    run_jobs(private_storage)
    m = client.get(f"/api/v1/materials/{m['id']}").json()
    assert m["status"] == "failed" and m["error_code"] == "generation_failed"
    assert m["content"] is None


def test_outages_are_retried_then_reported(
    client: TestClient, private_storage: Path, teacher: ScriptedProvider, lecture: dict
) -> None:
    teacher.structured += [AIProviderError("unavailable")] * 3
    m = make(client, lecture["id"], kind="guide").json()
    for _ in range(3):
        query("UPDATE jobs SET run_after = now() - interval '1 hour'")
        run_jobs(private_storage)
    m = client.get(f"/api/v1/materials/{m['id']}").json()
    assert m["status"] == "failed" and m["error_code"] == "ai_unavailable"


def test_creating_checks_pages_privacy_and_daily_limit(
    client: TestClient,
    private_storage: Path,
    teacher: ScriptedProvider,
    lecture: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert make(client, lecture["id"], kind="essay").status_code == 422
    assert make(client, lecture["id"], kind="flashcards", card_count=100).status_code == 422
    r = make(client, lecture["id"], kind="summary", page_from=9)
    assert r.status_code == 422 and r.json()["error"]["code"] == "pages_out_of_range"
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    r = make(client, lecture["id"], kind="summary")
    assert r.status_code == 403 and r.json()["error"]["code"] == "ai_not_private"
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "material_daily_limit", 1)
    assert make(client, lecture["id"], kind="summary").status_code == 202
    r = make(client, lecture["id"], kind="summary")
    assert r.status_code == 429 and r.json()["error"]["code"] == "material_daily_limit"


# ---------- flashcard review ----------


def ready_cards(client, private_storage, teacher, doc_id, n=6) -> dict:
    teacher.structured.append(cards(n))
    m = make(client, doc_id, kind="flashcards", card_count=n).json()
    run_jobs(private_storage)
    return m


def rate(client, material_id, index, rating):
    return client.post(
        f"/api/v1/materials/{material_id}/cards/{index}/review",
        json={"rating": rating},
        headers=with_csrf(client),
    )


def test_reviewing_flashcards_follows_the_schedule(
    client: TestClient, private_storage: Path, teacher: ScriptedProvider, lecture: dict
) -> None:
    m = ready_cards(client, private_storage, teacher, lecture["id"])
    session = client.get(f"/api/v1/materials/{m['id']}/review").json()
    assert len(session["due"]) == 6 and all(c["is_new"] for c in session["due"])
    assert client.get(f"/api/v1/materials/{m['id']}").json()["due_cards"] == 6

    r = rate(client, m["id"], 0, "good")
    assert r.status_code == 200 and r.json()["interval_days"] == 1.0
    rate(client, m["id"], 1, "again")
    session = client.get(f"/api/v1/materials/{m['id']}/review").json()
    assert [c["index"] for c in session["due"]] == [2, 3, 4, 5]  # 1 comes back in 10 min
    assert session["learned"] == 1

    # Ten minutes later the forgotten card is due again, before the new ones.
    query(
        "UPDATE flashcard_reviews SET due_at = :d WHERE card_index = 1",
        d=datetime.now(UTC) - timedelta(minutes=1),
    )
    assert client.get(f"/api/v1/materials/{m['id']}/review").json()["due"][0]["index"] == 1

    assert rate(client, m["id"], 6, "good").status_code == 404
    assert rate(client, m["id"], 0, "perfect").status_code == 422
    assert (
        client.post(
            f"/api/v1/materials/{m['id']}/cards/0/review", json={"rating": "good"}
        ).status_code
        == 403
    )


def test_only_flashcards_can_be_reviewed(
    client: TestClient, private_storage: Path, teacher: ScriptedProvider, lecture: dict
) -> None:
    teacher.structured.append(SUMMARY)
    m = make(client, lecture["id"], kind="summary").json()
    run_jobs(private_storage)
    r = client.get(f"/api/v1/materials/{m['id']}/review")
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_flashcards"


def test_only_the_owner_can_see_rename_review_or_delete(
    private_storage: Path, teacher: ScriptedProvider
) -> None:
    with new_client() as owner, new_client() as other:
        adult_student(owner, "owner@example.com")
        doc = upload_and_process(owner, private_storage)
        m = ready_cards(owner, private_storage, teacher, doc["id"])
        adult_student(other, "other@example.com")
        h = with_csrf(other)
        base = f"/api/v1/materials/{m['id']}"
        assert other.get(base).status_code == 404
        assert other.get(f"/api/v1/documents/{doc['id']}/materials").status_code == 404
        assert make(other, doc["id"], kind="summary").status_code == 404
        assert other.patch(base, json={"title": "Mine"}, headers=h).status_code == 404
        assert other.get(f"{base}/review").status_code == 404
        assert rate(other, m["id"], 0, "good").status_code == 404
        assert other.delete(base, headers=h).status_code == 404
        r = owner.patch(base, json={"title": "  Exam   cards "}, headers=with_csrf(owner))
        assert r.json()["title"] == "Exam cards"


def test_deleting_the_document_deletes_its_materials_and_reviews(
    client: TestClient, private_storage: Path, teacher: ScriptedProvider, lecture: dict
) -> None:
    m = ready_cards(client, private_storage, teacher, lecture["id"])
    rate(client, m["id"], 0, "good")
    client.delete(f"/api/v1/documents/{lecture['id']}", headers=with_csrf(client))
    assert query("SELECT count(*) FROM study_materials")[0][0] == 0
    assert query("SELECT count(*) FROM flashcard_reviews")[0][0] == 0
