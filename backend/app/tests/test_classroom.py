"""Lessons through the real API, with the scripted provider standing in for the model."""

import json

from fastapi.testclient import TestClient

from app.ai.factory import get_ai_provider
from app.core.config import get_settings
from app.main import app
from app.modules.curriculum.seed_data import PERCENT_OF_ID, PERCENTAGES_ID, seed_id
from app.tests.fakes import Reply, ScriptedProvider
from app.tests.helpers import new_client, query, signup_student, with_csrf

Q_25_OF_80 = seed_id("question:percent_of:25:80")


def sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def shown_text(events: list[tuple[str, dict]]) -> str:
    text = ""
    for name, data in events:
        if name == "reset":
            text = ""
        elif name == "delta":
            text += data["text"]
    return text


def adult_student(client: TestClient, email: str = "sam@example.com") -> str:
    return signup_student(client, email, age=18, guardian_email=None)["user"]["id"]


def start(client: TestClient) -> dict:
    r = client.post(
        "/api/v1/sessions", json={"topic_id": str(PERCENT_OF_ID)}, headers=with_csrf(client)
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


def turn(client: TestClient, session_id: str, intent: str, text: str | None = None):
    r = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"intent": intent, "text": text},
        headers=with_csrf(client),
    )
    return r, (sse(r.text) if r.status_code == 200 else [])


def set_question(session_id: str, question_id=Q_25_OF_80) -> None:
    query(
        "UPDATE learning_sessions SET current_question_id = :q WHERE id = :s",
        q=question_id,
        s=session_id,
    )


# ---------- Topics and sessions ----------


def test_topics_list_the_seeded_question_bank(client: TestClient) -> None:
    adult_student(client)
    topics = client.get("/api/v1/topics").json()
    percentages = [t for t in topics if t["area_id"] == str(PERCENTAGES_ID)]
    # Four skills of the Percentages area, in learning order (prerequisites first).
    assert [t["name"] for t in percentages] == [
        "Percents, decimals and fractions",
        "One number as a percentage of another",
        "Percent of an amount",
        "Percentage increase and decrease",
    ]
    assert {t["area_name"] for t in percentages} == {"Percentages"}
    assert [t["question_count"] for t in percentages] == [20, 15, 15, 15]
    # The first non-maths course sits next to it.
    mis = [t["name"] for t in topics if t["area_name"] == "Introduction to MIS"]
    assert mis == ["Information systems basics", "Databases and data management"]


def test_the_topic_area_itself_cannot_be_taught(client: TestClient) -> None:
    adult_student(client)
    r = client.post(
        "/api/v1/sessions", json={"topic_id": str(PERCENTAGES_ID)}, headers=with_csrf(client)
    )
    assert r.status_code == 404


def test_lessons_need_guardian_consent(client: TestClient) -> None:
    signup_student(client, "teen@example.com", age=15)
    r = client.post(
        "/api/v1/sessions", json={"topic_id": str(PERCENT_OF_ID)}, headers=with_csrf(client)
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "consent_required"


def test_starting_twice_continues_the_same_lesson(client: TestClient) -> None:
    adult_student(client)
    first, second = start(client), start(client)
    assert first["id"] == second["id"]


def test_students_cannot_open_each_others_lessons(teacher: ScriptedProvider) -> None:
    with new_client() as alice, new_client() as bob:
        adult_student(alice, "alice@example.com")
        adult_student(bob, "bob@example.com")
        session_id = start(alice)["id"]
        assert bob.get(f"/api/v1/sessions/{session_id}").status_code == 403
        r, _ = turn(bob, session_id, "start")
        assert r.status_code == 403
        assert teacher.requests == []  # the model was never called


# ---------- Teacher turns ----------


def test_opening_turn_streams_the_reply_and_puts_a_question_on_the_board(
    client: TestClient, teacher: ScriptedProvider
) -> None:
    adult_student(client)
    session = start(client)
    teacher.replies.append(
        Reply(
            ["Welcome to ", "percentages!"],
            board=[{"type": "text", "content": "Percent = out of 100"}],
        )
    )
    r, events = turn(client, session["id"], "start")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    names = [n for n, _ in events]
    assert names[0] == "status" and names[-1] == "done"
    assert shown_text(events) == "Welcome to percentages!"

    done = events[-1][1]
    board = done["message"]["whiteboard"]
    assert board[0] == {"type": "text", "text": "Percent = out of 100"}
    assert board[-1]["type"] == "question" and board[-1]["text"].startswith("What is")
    assert done["lesson"]["has_question"] is True
    assert "answer" not in json.dumps(done["lesson"])  # the answer never reaches the browser

    stored = client.get(f"/api/v1/sessions/{session['id']}").json()
    assert [m["role"] for m in stored["messages"]] == ["teacher"]


def test_model_never_receives_personal_data(client: TestClient, teacher: ScriptedProvider) -> None:
    signup_student(client, "ada.lovelace@example.com", age=18, guardian_email=None, name="Ada")
    session = start(client)
    turn(client, session["id"], "start")
    sent = (
        json.dumps([m.content for m in teacher.requests[0].messages]) + teacher.requests[0].system
    )
    assert "Ada" not in sent and "lovelace" not in sent and "example.com" not in sent
    assert "grade 9" in teacher.last_instruction  # grade level is the only profile detail


def test_the_blueprint_example_wrong_answer_2000(
    client: TestClient, teacher: ScriptedProvider
) -> None:
    adult_student(client)
    session = start(client)
    turn(client, session["id"], "start")
    set_question(session["id"])

    teacher.replies.append(Reply(["Not quite. What does 25% mean?"]))
    _, events = turn(client, session["id"], "message", "2000")
    instruction = teacher.last_instruction
    assert "Action: address_mistake" in instruction
    assert "divid" in instruction and "100" in instruction  # misconception described to model
    assert "Never say or write this number" in instruction

    [(is_correct, code)] = query(
        "SELECT a.is_correct, m.code FROM question_attempts a "
        "JOIN misconceptions m ON m.id = a.misconception_id"
    )
    assert is_correct is False and code == "percent_forgot_divide_100"
    assert events[-1][1]["lesson"]["question_text"] == "What is 25% of 80?"


def test_answer_leak_is_blocked_while_streaming(
    client: TestClient, teacher: ScriptedProvider
) -> None:
    adult_student(client)
    session = start(client)
    turn(client, session["id"], "start")
    set_question(session["id"])

    teacher.replies += [Reply(["Here you go: 2", "0."]), Reply(["Try dividing by 100 first."])]
    _, events = turn(client, session["id"], "message", "can you just tell me the answer")
    assert "reset" in [n for n, _ in events] or all(
        "20" not in d.get("text", "") for _, d in events
    )
    assert all("20" not in d.get("text", "") for n, d in events if n == "delta")
    assert shown_text(events) == "Try dividing by 100 first."
    assert events[-1][1]["message"]["content"] == "Try dividing by 100 first."


def test_correct_answer_moves_on_to_a_new_question(
    client: TestClient, teacher: ScriptedProvider
) -> None:
    adult_student(client)
    session = start(client)
    turn(client, session["id"], "start")
    set_question(session["id"])
    _, events = turn(client, session["id"], "message", "20")
    assert "Action: praise_and_next" in teacher.last_instruction
    lesson = events[-1][1]["lesson"]
    assert lesson["question_text"] != "What is 25% of 80?"
    assert query("SELECT is_correct FROM question_attempts") == [(True,)]


def test_hint_ladder_through_the_api(client: TestClient, teacher: ScriptedProvider) -> None:
    adult_student(client)
    session = start(client)
    turn(client, session["id"], "start")
    set_question(session["id"])

    for rung in (1, 2, 3):
        _, events = turn(client, session["id"], "hint")
        assert f"Hint {rung} of 3" in teacher.last_instruction
        assert events[-1][1]["lesson"]["hint_level"] == rung

    # All hints used but no attempt: no solution yet.
    turn(client, session["id"], "hint")
    assert "Action: encourage_attempt" in teacher.last_instruction

    turn(client, session["id"], "message", "15")  # an honest (wrong) attempt
    assert "Action: show_solution" in teacher.last_instruction
    assert "you may say it now" in teacher.last_instruction

    roles = [
        m["content"]
        for m in client.get(f"/api/v1/sessions/{session['id']}").json()["messages"]
        if m["role"] == "student"
    ]
    assert roles[:2] == ["Give me a hint", "Give me a hint"]


def test_distress_gets_a_fixed_reply_and_never_reaches_the_model(
    client: TestClient, teacher: ScriptedProvider
) -> None:
    adult_student(client)
    session = start(client)
    turn(client, session["id"], "start")
    calls = len(teacher.requests)
    _, events = turn(client, session["id"], "message", "i want to die")
    assert len(teacher.requests) == calls
    assert "trusted adult" in shown_text(events)
    assert query("SELECT action FROM audit_log") == [("safety_flag",)]


def test_ai_usage_is_logged_without_any_text(client: TestClient, teacher: ScriptedProvider) -> None:
    adult_student(client)
    session = start(client)
    turn(client, session["id"], "start")
    rows = query("SELECT * FROM ai_requests")
    assert len(rows) == 1
    columns = {
        r[0]
        for r in query(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'ai_requests'"
        )
    }
    assert columns == {
        "id",
        "session_id",
        "model",
        "tokens_in",
        "tokens_out",
        "latency_ms",
        "created_at",
    }


def test_provider_outage_reports_an_error_and_keeps_nothing(
    client: TestClient, teacher: ScriptedProvider
) -> None:
    adult_student(client)
    session = start(client)
    turn(client, session["id"], "start")
    teacher.replies.append(Reply([], error="unavailable"))
    _, events = turn(client, session["id"], "message", "what is a percent?")
    assert events[-1][0] == "error" and events[-1][1]["code"] == "ai_unavailable"
    messages = client.get(f"/api/v1/sessions/{session['id']}").json()["messages"]
    assert [m["role"] for m in messages] == ["teacher"]  # the failed student turn was removed


def test_no_provider_configured_is_reported_clearly(client: TestClient) -> None:
    app.dependency_overrides[get_ai_provider] = lambda: None
    try:
        adult_student(client)
        session = start(client)
        _, events = turn(client, session["id"], "start")
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)
    assert events == [
        (
            "error",
            {
                "code": "ai_not_configured",
                "message": "The AI teacher is not set up on this server yet.",
            },
        )
    ]


def test_turn_order_rules(client: TestClient, teacher: ScriptedProvider) -> None:
    adult_student(client)
    session = start(client)
    r, _ = turn(client, session["id"], "message", "hi")
    assert r.json()["error"]["code"] == "not_started"
    turn(client, session["id"], "start")
    r, _ = turn(client, session["id"], "start")
    assert r.json()["error"]["code"] == "already_started"
    r, _ = turn(client, session["id"], "message", "   ")
    assert r.status_code == 422


def test_daily_message_limit(client: TestClient, teacher: ScriptedProvider, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "daily_message_limit", 2)
    adult_student(client)
    session = start(client)
    turn(client, session["id"], "start")
    turn(client, session["id"], "hint")
    turn(client, session["id"], "hint")
    r, _ = turn(client, session["id"], "hint")
    assert r.status_code == 429 and r.json()["error"]["code"] == "daily_limit"


def test_ended_lessons_take_no_more_turns(client: TestClient, teacher: ScriptedProvider) -> None:
    adult_student(client)
    session = start(client)
    turn(client, session["id"], "start")
    ended = client.post(f"/api/v1/sessions/{session['id']}/end", headers=with_csrf(client))
    assert ended.json()["status"] == "ended"
    r, _ = turn(client, session["id"], "hint")
    assert r.json()["error"]["code"] == "session_ended"
