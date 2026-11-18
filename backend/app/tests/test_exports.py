"""PDF exports (phase 7): student copies never contain answers, teacher copies do, text from
the AI or the document cannot inject markup, and only the owner can download."""

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.modules.exports.pdf import QuizItem, clean, fonts, material_pdf, quiz_pdf
from app.tests.fakes import ScriptedProvider
from app.tests.helpers import new_client, query, with_csrf
from app.tests.test_classroom import adult_student
from app.tests.test_document_processing import run_jobs, upload_and_process
from app.tests.test_materials import GUIDE, SUMMARY, cards
from app.tests.test_quizzes import FB, MC, TF

QUESTIONS = [
    QuizItem(
        "multiple_choice",
        "What does a foreign key point at?",
        {
            "options": ["A server", "The primary key of another table", "A spreadsheet"],
            "correct_index": 1,
        },
        "It refers to another table's key.",
        [2],
    ),
    QuizItem(
        "true_false",
        "Two rows may share a primary key value.",
        {"value": False},
        "Primary key values are unique.",
        [1],
    ),
    QuizItem(
        "fill_blank",
        "Normalisation stores each fact ___.",
        {"answers": ["once"]},
        "Each fact is stored only one time.",
        [4],
    ),
]


def text_of(pdf: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


# ---------- the PDF builder ----------


def test_the_student_copy_has_questions_but_never_answers() -> None:
    pdf = quiz_pdf("Week 3 quiz", "Week 3.pdf", QUESTIONS, teacher=False, minutes=10)
    assert pdf.startswith(b"%PDF-")
    text = text_of(pdf)
    assert "What does a foreign key point at?" in text and "Name:" in text and "10 minutes" in text
    assert "The primary key of another table" in text  # the options themselves are shown
    for secret in (
        "Answer key",
        "once",
        "It refers to",
        "Primary key values are unique",
        "one time",
        "teacher",
    ):
        assert secret not in text, secret


def test_the_teacher_copy_adds_the_answer_key() -> None:
    text = text_of(quiz_pdf("Week 3 quiz", "Week 3.pdf", QUESTIONS, teacher=True))
    assert "Answer key" in text and "teacher version" in text
    assert "B) The primary key of another table" in text
    assert "False" in text and "once" in text
    assert "Each fact is stored only one time." in text and "p. 4" in text


def test_text_cannot_inject_markup_or_read_files() -> None:
    evil = "<img src='C:/Windows/win.ini'/> <font size=40>big</font> & <b>bold"
    assert clean(evil).startswith("&lt;img")
    pdf = quiz_pdf(
        evil, evil, [QuizItem("true_false", evil, {"value": True}, evil, [1])], teacher=True
    )
    text = text_of(pdf)
    assert "<img src=" in text  # shown as plain text, not interpreted


def test_turkish_and_russian_letters_survive_with_a_unicode_font() -> None:
    if not fonts().unicode:
        pytest.skip("no TrueType font with wide coverage on this machine")
    pdf = material_pdf(
        "Öğrenci notları",
        "Ders.pdf",
        "flashcards",
        {"cards": [{"front": "Veritabanı nedir?", "back": "Ключ — это поле.", "pages": [1]}]},
    )
    text = text_of(pdf)
    assert "Veritabanı nedir?" in text and "Ключ" in text


@pytest.mark.parametrize(
    ("kind", "content", "expected"),
    [
        (
            "summary",
            {
                "sections": [
                    {"heading": "Keys", "points": [{"text": "Keys identify rows.", "pages": [1]}]}
                ]
            },
            ["Keys", "Keys identify rows.", "p. 1"],
        ),
        (
            "guide",
            {**GUIDE, "key_terms": GUIDE["key_terms"][:1]},
            ["Overview", "Primary key", "Check yourself", "Links tables."],
        ),
        ("flashcards", cards(3), ["Front", "Question 0?", "Answer number 2."]),
    ],
)
def test_each_material_kind_renders(kind: str, content: dict, expected: list[str]) -> None:
    text = text_of(material_pdf("My notes", "W3.pdf", kind, content))
    for piece in expected:
        assert piece in text, piece


def test_guide_answers_are_on_a_later_page_than_the_questions() -> None:
    pdf = material_pdf("Guide", "W3.pdf", "guide", GUIDE)
    pages = [p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages]
    question_page = next(i for i, t in enumerate(pages) if "What does a foreign key do?" in t)
    answer_page = next(i for i, t in enumerate(pages) if "Links tables." in t)
    assert answer_page > question_page


# ---------- downloading ----------


@pytest.fixture
def lecture(client: TestClient, private_storage: Path) -> dict:
    adult_student(client)
    return upload_and_process(client, private_storage)


def test_downloading_a_quiz_in_both_versions(
    client: TestClient, private_storage: Path, teacher: ScriptedProvider, lecture: dict
) -> None:
    teacher.structured.append({"questions": [MC, TF, FB]})
    quiz = client.post(
        f"/api/v1/documents/{lecture['id']}/quizzes", json={"count": 3}, headers=with_csrf(client)
    ).json()
    run_jobs(private_storage)

    r = client.get(f"/api/v1/quizzes/{quiz['id']}/export")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].startswith("attachment;")
    assert r.headers["cache-control"] == "private, no-store"
    student = text_of(r.content)
    assert "What does a foreign key point at?" in student
    assert "Answer key" not in student and "stored once" not in student

    r = client.get(f"/api/v1/quizzes/{quiz['id']}/export?version=teacher")
    assert "answers" in r.headers["content-disposition"]
    assert "Answer key" in text_of(r.content)
    assert client.get(f"/api/v1/quizzes/{quiz['id']}/export?version=solutions").status_code == 422
    assert query("SELECT count(*) FROM audit_log WHERE action = 'export'")[0][0] == 2


def test_downloading_a_material(
    client: TestClient, private_storage: Path, teacher: ScriptedProvider, lecture: dict
) -> None:
    teacher.structured.append(SUMMARY)
    m = client.post(
        f"/api/v1/documents/{lecture['id']}/materials",
        json={"kind": "summary"},
        headers=with_csrf(client),
    ).json()
    r = client.get(f"/api/v1/materials/{m['id']}/export")
    assert r.status_code == 409  # still being written
    run_jobs(private_storage)
    r = client.get(f"/api/v1/materials/{m['id']}/export")
    assert r.status_code == 200 and "A primary key identifies each row uniquely." in text_of(
        r.content
    )


def test_only_the_owner_can_download(private_storage: Path, teacher: ScriptedProvider) -> None:
    with new_client() as owner, new_client() as other:
        adult_student(owner, "owner@example.com")
        doc = upload_and_process(owner, private_storage)
        teacher.structured += [{"questions": [MC, TF, FB]}, SUMMARY]
        quiz = owner.post(
            f"/api/v1/documents/{doc['id']}/quizzes", json={"count": 3}, headers=with_csrf(owner)
        ).json()
        m = owner.post(
            f"/api/v1/documents/{doc['id']}/materials",
            json={"kind": "summary"},
            headers=with_csrf(owner),
        ).json()
        run_jobs(private_storage)
        adult_student(other, "other@example.com")
        assert other.get(f"/api/v1/quizzes/{quiz['id']}/export?version=teacher").status_code == 404
        assert other.get(f"/api/v1/materials/{m['id']}/export").status_code == 404
        assert owner.get(f"/api/v1/quizzes/{quiz['id']}/export").status_code == 200
    with new_client() as anonymous:
        assert anonymous.get(f"/api/v1/quizzes/{quiz['id']}/export").status_code == 401
