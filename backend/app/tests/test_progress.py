"""Mastery through the real API, and the Phase 7-8 gate:
"Mastery changes after answers and survives logout"."""

from fastapi.testclient import TestClient

from app.modules.curriculum.seed_data import (
    CHANGE_ID,
    CONVERT_ID,
    EXPRESS_ID,
    PERCENT_OF_ID,
    PERCENTAGES_ID,
)
from app.tests.fakes import Reply, ScriptedProvider
from app.tests.helpers import PASSWORD, new_client, query, signup_guardian, with_csrf
from app.tests.test_classroom import adult_student, set_question, start, turn


def progress(client: TestClient) -> dict:
    r = client.get("/api/v1/progress")
    assert r.status_code == 200, r.text
    return r.json()


def skill(data: dict, name: str) -> dict:
    return next(s for a in data["areas"] for s in a["skills"] if s["name"] == name)


def test_a_new_student_starts_at_the_beginning(client: TestClient) -> None:
    adult_student(client)
    data = progress(client)
    # A school student (grade 9) sees the school course first, then the university one.
    area, mis = data["areas"]
    assert area["id"] == str(PERCENTAGES_ID) and area["name"] == "Percentages"
    assert mis["name"] == "Introduction to MIS"
    assert {s["course_level"] for s in mis["skills"]} == {"university"}
    assert area["mastery"] == 0
    assert [s["id"] for s in area["skills"]] == [
        str(CONVERT_ID),
        str(EXPRESS_ID),
        str(PERCENT_OF_ID),
        str(CHANGE_ID),
    ]
    assert {s["level"] for s in area["skills"]} == {"not_started"}
    # Start with the skill everything else builds on.
    assert data["recommended_skill_id"] == str(CONVERT_ID)
    assert skill(data, "Percent of an amount")["needs_first"] == [
        "Percents, decimals and fractions"
    ]


def test_mastery_changes_after_answers_and_survives_logout(
    client: TestClient, teacher: ScriptedProvider
) -> None:
    """The phase gate, end to end."""
    adult_student(client, "gate@example.com")
    session = start(client)
    turn(client, session["id"], "start")
    set_question(session["id"])  # What is 25% of 80?

    _, events = turn(client, session["id"], "message", "20")
    lesson = events[-1][1]["lesson"]
    assert lesson["mastery"] > 0 and lesson["mastery_level"] == "learning"
    after_answer = skill(progress(client), "Percent of an amount")
    assert after_answer["mastery"] == lesson["mastery"]
    assert after_answer["questions_done"] == 1 and after_answer["questions_solved"] == 1
    assert len(after_answer["history"]) == 1
    assert query("SELECT count(*) FROM mastery_events") == [(1,)]

    # Log out, then log back in with a fresh browser: the mastery is still there.
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/progress").status_code == 401
    with new_client() as fresh:
        r = fresh.post(
            "/api/v1/auth/login", json={"email": "gate@example.com", "password": PASSWORD}
        )
        assert r.status_code == 200, r.text
        again = skill(progress(fresh), "Percent of an amount")
        assert again["mastery"] == after_answer["mastery"]
        assert again["last_practiced_at"] is not None


def test_needing_the_solution_lowers_mastery(client: TestClient, teacher: ScriptedProvider) -> None:
    student = adult_student(client)
    query(
        "INSERT INTO topic_mastery (student_id, topic_id, mastery_score, difficulty_level, "
        "attempts, correct, streak) VALUES (:s, :t, 0.5, 3, 4, 3, 0)",
        s=student,
        t=PERCENT_OF_ID,
    )
    session = start(client)
    turn(client, session["id"], "start")
    set_question(session["id"])
    turn(client, session["id"], "message", "2000")  # wrong: forgot to divide by 100
    for _ in range(3):
        turn(client, session["id"], "hint")
    _, events = turn(client, session["id"], "hint")
    assert "Action: show_solution" in teacher.last_instruction
    assert events[-1][1]["lesson"]["mastery"] < 0.5
    assert skill(progress(client), "Percent of an amount")["questions_solved"] == 3


def test_saved_mastery_sets_the_difficulty_of_the_next_lesson(
    client: TestClient, teacher: ScriptedProvider
) -> None:
    student = adult_student(client)
    query(
        "INSERT INTO topic_mastery (student_id, topic_id, mastery_score, difficulty_level, "
        "attempts, correct, streak) VALUES (:s, :t, 0.9, 5, 12, 12, 4)",
        s=student,
        t=PERCENT_OF_ID,
    )
    session = start(client)
    turn(client, session["id"], "start")
    [(difficulty,)] = query(
        "SELECT q.difficulty FROM learning_sessions s JOIN questions q "
        "ON q.id = s.current_question_id WHERE s.id = :s",
        s=session["id"],
    )
    assert difficulty >= 4


def test_a_failed_turn_leaves_mastery_unchanged(
    client: TestClient, teacher: ScriptedProvider
) -> None:
    adult_student(client)
    session = start(client)
    turn(client, session["id"], "start")
    set_question(session["id"])
    teacher.replies.append(Reply([], error="unavailable"))
    _, events = turn(client, session["id"], "message", "20")
    assert events[-1][0] == "error"
    assert query("SELECT count(*) FROM topic_mastery") == [(0,)]
    assert query("SELECT count(*) FROM mastery_events") == [(0,)]


def test_progress_is_only_for_the_student_themself(client: TestClient) -> None:
    signup_guardian(client, "parent@example.com")
    assert client.get("/api/v1/progress").status_code == 403
    with new_client() as anonymous:
        assert anonymous.get("/api/v1/progress").status_code == 401


def test_students_never_see_each_others_mastery(
    client: TestClient, teacher: ScriptedProvider
) -> None:
    adult_student(client, "first@example.com")
    session = start(client)
    turn(client, session["id"], "start")
    set_question(session["id"])
    turn(client, session["id"], "message", "20")
    assert skill(progress(client), "Percent of an amount")["questions_done"] == 1

    with new_client() as other:
        adult_student(other, "second@example.com")
        assert skill(progress(other), "Percent of an amount")["questions_done"] == 0


def test_recommendation_moves_on_once_a_skill_is_mastered(client: TestClient) -> None:
    student = adult_student(client)
    query(
        "INSERT INTO topic_mastery (student_id, topic_id, mastery_score, difficulty_level, "
        "attempts, correct, streak) VALUES (:s, :t, 0.85, 5, 10, 10, 5)",
        s=student,
        t=CONVERT_ID,
    )
    data = progress(client)
    assert skill(data, "Percents, decimals and fractions")["level"] == "mastered"
    assert skill(data, "Percent of an amount")["needs_first"] == []
    assert data["recommended_skill_id"] == str(EXPRESS_ID)  # next in learning order
    with_csrf(client)  # the session is still usable after reading progress
