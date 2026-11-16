"""Multi-subject phase 1 gate: a non-maths topic is taught end to end, through the real API,
with the hint ladder, code-checked answers, the leak guard and mastery."""

from fastapi.testclient import TestClient

from app.modules.curriculum.content_mis import DATABASES_ID, IS_BASICS_ID
from app.modules.curriculum.seed_data import seed_id
from app.tests.fakes import Reply, ScriptedProvider
from app.tests.helpers import query, signup_student, with_csrf
from app.tests.test_classroom import adult_student, set_question, sse

Q_ORDERS = seed_id("question:db_orders_customer")  # multiple choice, B) Foreign key
Q_DUPLICATE_PK = seed_id("question:db_duplicate_pk")  # true/false, answer: false
Q_REFERS = seed_id("question:db_refers_called")  # fill in the blank, answer: foreign


def start_topic(client: TestClient, topic_id) -> dict:
    r = client.post("/api/v1/sessions", json={"topic_id": str(topic_id)}, headers=with_csrf(client))
    assert r.status_code in (200, 201), r.text
    return r.json()


def turn(client: TestClient, session_id: str, intent: str, text: str | None = None):
    r = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"intent": intent, "text": text},
        headers=with_csrf(client),
    )
    assert r.status_code == 200, r.text
    return sse(r.text)


def lesson_with(client: TestClient, question_id) -> str:
    session = start_topic(client, DATABASES_ID)
    turn(client, session["id"], "start")
    set_question(session["id"], question_id)
    return session["id"]


def test_mis_lesson_uses_the_business_teacher_and_the_students_level(
    client: TestClient, teacher: ScriptedProvider
) -> None:
    adult_student(client)
    session = start_topic(client, IS_BASICS_ID)
    events = turn(client, session["id"], "start")
    request = teacher.requests[-1]
    assert "teacher of business and information systems" in request.system
    assert "maths" not in request.system
    assert "Topic: Information systems basics" in teacher.last_instruction
    assert "high-school student (grade 9)" in teacher.last_instruction
    # The first question goes on the board with its options, never with the answer.
    lesson = events[-1][1]["lesson"]
    question_block = events[-1][1]["message"]["whiteboard"][-1]
    assert question_block["type"] == "question" and lesson["has_question"]
    assert lesson["question_type"] in ("multiple_choice", "true_false", "fill_blank")
    assert "correct" not in str(lesson) and "answers" not in str(lesson)


def test_multiple_choice_correct_letter_is_praised_and_raises_mastery(
    client: TestClient, teacher: ScriptedProvider
) -> None:
    adult_student(client)
    sid = lesson_with(client, Q_ORDERS)
    lesson = client.get(f"/api/v1/sessions/{sid}").json()["lesson"]
    assert lesson["question_type"] == "multiple_choice"
    assert lesson["question_options"] == [
        "Primary key",
        "Foreign key",
        "Derived attribute",
        "Composite index",
    ]
    events = turn(client, sid, "message", "B")
    assert "Action: praise_and_next" in teacher.last_instruction
    assert "The student answered: B) Foreign key." in teacher.last_instruction
    assert events[-1][1]["lesson"]["mastery"] > 0
    assert query("SELECT student_answer, is_correct FROM question_attempts") == [("B", True)]


def test_wrong_option_reveals_its_misconception_to_the_teacher(
    client: TestClient, teacher: ScriptedProvider
) -> None:
    adult_student(client)
    sid = lesson_with(client, Q_ORDERS)
    turn(client, sid, "message", "a")
    instruction = teacher.last_instruction
    assert "Action: address_mistake" in instruction
    assert "Mixes up primary keys" in instruction
    assert "Its answer is B) Foreign key. Never say, hint at or write which option" in instruction
    [(code,)] = query(
        "SELECT m.code FROM question_attempts a JOIN misconceptions m ON m.id = a.misconception_id"
    )
    assert code == "db_primary_foreign_confusion"


def test_saying_the_correct_option_is_blocked_and_regenerated(
    client: TestClient, teacher: ScriptedProvider
) -> None:
    adult_student(client)
    sid = lesson_with(client, Q_ORDERS)
    teacher.replies += [
        Reply(["Close! It is actually a foreign", " key, because it points elsewhere."]),
        Reply(["Close! Think about which table the column points to."]),
    ]
    events = turn(client, sid, "message", "A")
    shown = events[-1][1]["message"]["content"]
    assert shown == "Close! Think about which table the column points to."
    assert all("foreign" not in d.get("text", "").lower() for n, d in events if n == "delta")


def test_true_false_and_its_leak_guard(client: TestClient, teacher: ScriptedProvider) -> None:
    adult_student(client)
    sid = lesson_with(client, Q_DUPLICATE_PK)
    teacher.replies += [
        Reply(["Not quite: the statement is false."]),
        Reply(["Not quite. What is a primary key for?"]),
    ]
    events = turn(client, sid, "message", "true")
    assert "Action: address_mistake" in teacher.last_instruction
    assert events[-1][1]["message"]["content"] == "Not quite. What is a primary key for?"
    turn(client, sid, "message", "false")
    assert "Action: praise_and_next" in teacher.last_instruction


def test_fill_in_the_blank_marks_words_and_leaves_questions_alone(
    client: TestClient, teacher: ScriptedProvider
) -> None:
    adult_student(client)
    sid = lesson_with(client, Q_REFERS)
    turn(client, sid, "message", "why is it called that?")
    assert "Action: respond" in teacher.last_instruction  # a question, not an answer
    turn(client, sid, "message", "primary")
    assert "Action: address_mistake" in teacher.last_instruction
    turn(client, sid, "message", "Foreign")
    assert "Action: praise_and_next" in teacher.last_instruction
    assert query("SELECT is_correct FROM question_attempts ORDER BY created_at") == [
        (False,),
        (True,),
    ]


def test_hint_ladder_uses_the_business_profile(
    client: TestClient, teacher: ScriptedProvider
) -> None:
    adult_student(client)
    sid = lesson_with(client, Q_REFERS)
    turn(client, sid, "hint")
    assert "Hint 1 of 3: a conceptual nudge only: remind the student what a key term means" in (
        teacher.last_instruction
    )
    turn(client, sid, "hint")
    turn(client, sid, "hint")
    assert "a similar example from a different business situation" in teacher.last_instruction


def test_university_students_can_sign_up_and_get_the_university_course_first(
    client: TestClient,
) -> None:
    r = client.post(
        "/api/v1/auth/signup",
        json={
            "account_type": "student",
            "email": "uni@example.com",
            "password": "correct-horse-battery",
            "display_name": "Uni",
            "date_of_birth": "2000-01-01",
            "grade_level": 13,
            "guardian_email": None,
        },
    )
    assert r.status_code == 201, r.text
    data = client.get("/api/v1/progress").json()
    assert data["areas"][0]["name"] == "Introduction to MIS"
    assert data["recommended_skill_id"] == str(IS_BASICS_ID)


def test_grade_14_is_still_refused(client: TestClient) -> None:
    signup_student(client, "teen@example.com", age=15)
    r = client.patch("/api/v1/students/me", json={"grade_level": 14}, headers=with_csrf(client))
    assert r.status_code == 422
