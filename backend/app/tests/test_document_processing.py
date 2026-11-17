"""Documents, phase 3: reading the text in the background, chunks with page numbers, and
full-text search that only ever looks at the searching student's own documents."""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.storage import LocalStorage
from app.modules.documents.processing import (
    MARK_END,
    MARK_START,
    MAX_WORDS,
    PageText,
    clean_text,
    extract_pages,
    looks_like_heading,
    make_chunks,
)
from app.modules.documents.service import search_terms
from app.modules.jobs.worker import run_until_idle
from app.tests.helpers import new_client, query, with_csrf
from app.tests.pdfs import blank_pdf, text_pdf
from app.tests.test_classroom import adult_student
from app.tests.test_documents import upload

LECTURE = text_pdf(
    [
        [
            "Week 3 Relational Databases",
            "A primary key identifies each row of a table uniquely.",
            "No two rows may share the same primary key value.",
        ],
        [
            "Foreign Keys",
            "A foreign key in one table points at the primary key of another table.",
            "This is how an order row knows which customer placed it.",
        ],
        [],  # a scanned page: no text layer
        [
            "Normalisation",
            "Normalisation removes repeated data so each fact is stored once.",
        ],
    ]
)


def run_jobs(storage_root: Path) -> int:
    return asyncio.run(run_until_idle(LocalStorage(storage_root)))


def upload_and_process(client: TestClient, root: Path, data: bytes = LECTURE, name="W3.pdf"):
    r = upload(client, data, name)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "processing"
    run_jobs(root)
    return client.get(f"/api/v1/documents/{r.json()['id']}").json()


def search(client: TestClient, q: str, **params):
    return client.get("/api/v1/documents/search", params={"q": q, **params})


# ---------- pure functions: no database ----------


def test_clean_text_makes_text_safe_to_store() -> None:
    raw = "data-\nbase\x00 key­ s\t\tpace " + MARK_START + "x" + MARK_END + "\n\n\n\nend"
    assert clean_text(raw) == "database key s pace x\n\nend"


@pytest.mark.parametrize(
    ("line", "heading"),
    [
        ("Chapter 2 Normal Forms", True),
        ("2.1 Primary keys", True),
        ("INTRODUCTION", True),
        ("Foreign Keys and Joins", True),
        ("A primary key identifies each row.", False),
        ("this starts in lower case", False),
        ("Ends with a colon:", False),
        ("A very long line that goes on and on with many more words than any heading has", False),
    ],
)
def test_heading_guess(line: str, heading: bool) -> None:
    assert looks_like_heading(line) is heading


def test_extract_pages_keeps_page_numbers_and_spots_scans() -> None:
    pages = extract_pages(LECTURE, time_limit_s=30)
    assert [p.number for p in pages] == [1, 2, 3, 4]
    assert [p.has_text for p in pages] == [True, True, False, True]
    assert "primary key identifies" in pages[0].text and pages[2].text == ""


def test_chunks_follow_headings_and_record_their_pages() -> None:
    words = " ".join(["word"] * 70)
    pages = [
        PageText(1, f"Introduction\n{words}", True),
        PageText(2, f"Primary Keys\n{words}", True),
        PageText(3, "", False),
        PageText(4, f"more about keys {words}", True),
    ]
    chunks = make_chunks(pages)
    assert [(c.page_start, c.page_end, c.heading) for c in chunks] == [
        (1, 1, "Introduction"),
        (2, 4, "Primary Keys"),  # runs on past the scanned page; both ends are recorded
    ]
    assert all(c.token_count > 0 for c in chunks)


def test_a_very_long_paragraph_is_split() -> None:
    pages = [PageText(1, " ".join(["long"] * (MAX_WORDS * 2 + 10)), True)]
    chunks = make_chunks(pages)
    assert len(chunks) == 3 and all(len(c.text.split()) <= MAX_WORDS for c in chunks)
    assert [c.position for c in chunks] == [0, 1, 2]


def test_search_terms_never_pass_search_syntax_through() -> None:
    assert search_terms("Primary KEY") == ["primary", "key"]
    assert search_terms("a & b | !c:* <-> 'x') (") == []  # single letters and symbols
    assert search_terms("normal_form 3NF") == ["normal", "form", "3nf"]
    assert search_terms("öğrenci ключ") == ["öğrenci", "ключ"]


# ---------- the background job ----------


def test_upload_queues_processing_and_the_worker_makes_it_searchable(
    client: TestClient, private_storage: Path
) -> None:
    adult_student(client)
    r = upload(client, LECTURE, "Week 3.pdf")
    doc_id = r.json()["id"]
    # The job is stored together with the document, holding only its id.
    [(kind, status, payload)] = query("SELECT kind, status, payload FROM jobs")
    assert (kind, status) == ("process_document", "queued")
    assert payload == {"document_id": doc_id}

    assert run_jobs(private_storage) == 1
    doc = client.get(f"/api/v1/documents/{doc_id}").json()
    assert doc["status"] == "ready" and doc["error_code"] is None
    assert doc["page_count"] == 4 and doc["pages_with_text"] == 3
    assert query("SELECT status, attempts FROM jobs") == [("done", 1)]

    pages = query(
        "SELECT page_number, has_text FROM document_pages WHERE document_id = :d "
        "ORDER BY page_number",
        d=doc_id,
    )
    assert pages == [(1, True), (2, True), (3, False), (4, True)]
    assert query("SELECT count(*) FROM document_chunks WHERE document_id = :d", d=doc_id)[0][0]


def test_search_finds_the_right_page_with_highlighted_snippets(
    client: TestClient, private_storage: Path
) -> None:
    adult_student(client)
    doc = upload_and_process(client, private_storage)
    r = search(client, "foreign key")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["terms"] == ["foreign", "key"]
    [hit] = body["results"]
    assert hit["document_id"] == doc["id"] and hit["document_title"] == "W3"
    assert hit["page_start"] <= 2 <= hit["page_end"]
    assert f"{MARK_START}foreign{MARK_END}" in hit["snippet"].lower()
    assert "<" not in hit["snippet"]  # plain text, never HTML

    # Prefix matching: part of a word still finds it; words not in the document do not.
    assert search(client, "normalis").json()["results"]
    # Accents are ignored both ways.
    assert search(client, "normalisätion").json()["results"]
    assert search(client, "photosynthesis").json()["results"] == []
    # Search within one document.
    assert search(client, "primary", document_id=doc["id"]).json()["results"]


def test_odd_search_input_is_handled_safely(client: TestClient, private_storage: Path) -> None:
    adult_student(client)
    upload_and_process(client, private_storage)
    for q in ["'; DROP TABLE documents; --", "key:* | !primary", "(((", "\\", "a"]:
        r = search(client, q)
        assert r.status_code in (200, 422), (q, r.text)
    assert search(client, "!").json()["error"]["code"] == "search_too_short"
    assert search(client, "x" * 201).status_code == 422
    assert query("SELECT count(*) FROM documents")[0][0] == 1


def test_a_student_never_finds_text_from_another_students_documents(
    private_storage: Path,
) -> None:
    with new_client() as owner, new_client() as other:
        adult_student(owner, "owner@example.com")
        doc = upload_and_process(owner, private_storage)
        adult_student(other, "other@example.com")

        assert search(owner, "primary key").json()["results"]
        assert search(other, "primary key").json()["results"] == []
        # Naming the other student's document id is "not found", as for every endpoint.
        r = search(other, "primary key", document_id=doc["id"])
        assert r.status_code == 404 and r.json()["error"]["code"] == "document_not_found"
        r = other.post(f"/api/v1/documents/{doc['id']}/process", headers=with_csrf(other))
        assert r.status_code == 404


def test_search_requires_login(client: TestClient) -> None:
    assert search(client, "primary").status_code == 401


def test_a_scanned_pdf_is_ready_to_view_but_has_no_searchable_text(
    client: TestClient, private_storage: Path
) -> None:
    adult_student(client)
    doc = upload_and_process(client, private_storage, blank_pdf(2), "Scan.pdf")
    assert doc["status"] == "ready" and doc["error_code"] == "no_text_layer"
    assert doc["pages_with_text"] == 0
    assert client.get(f"/api/v1/documents/{doc['id']}/file").status_code == 200


def test_a_damaged_file_fails_and_can_be_retried(client: TestClient, private_storage: Path) -> None:
    adult_student(client)
    r = upload(client, LECTURE, "W3.pdf")
    doc_id = r.json()["id"]
    [path] = [p for p in private_storage.rglob("*.pdf")]
    path.write_bytes(b"%PDF-1.4 this is not really a pdf any more")
    run_jobs(private_storage)
    doc = client.get(f"/api/v1/documents/{doc_id}").json()
    assert doc["status"] == "failed" and doc["error_code"] == "pdf_unreadable"

    # Retrying needs the CSRF token, and works once the file is readable again.
    assert client.post(f"/api/v1/documents/{doc_id}/process").status_code == 403
    path.write_bytes(LECTURE)
    r = client.post(f"/api/v1/documents/{doc_id}/process", headers=with_csrf(client))
    assert r.status_code == 200 and r.json()["status"] == "processing"
    run_jobs(private_storage)
    assert client.get(f"/api/v1/documents/{doc_id}").json()["status"] == "ready"
    # A document that did not fail is not processed again.
    r = client.post(f"/api/v1/documents/{doc_id}/process", headers=with_csrf(client))
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_failed"


def test_storage_errors_are_retried_then_reported(
    client: TestClient, private_storage: Path
) -> None:
    adult_student(client)
    doc_id = upload(client, LECTURE).json()["id"]
    for f in private_storage.rglob("*.pdf"):
        f.unlink()  # the stored file is missing: reading it raises a storage error
    for attempt in (1, 2, 3):
        query("UPDATE jobs SET run_after = now()")  # skip the wait between attempts
        assert run_jobs(private_storage) == 1
        status = client.get(f"/api/v1/documents/{doc_id}").json()["status"]
        assert status == ("processing" if attempt < 3 else "failed")
    assert query("SELECT status, attempts, error FROM jobs") == [("failed", 3, "StorageError")]
    doc = client.get(f"/api/v1/documents/{doc_id}").json()
    assert doc["error_code"] == "processing_failed"


def test_deleting_a_document_removes_its_text_and_a_queued_job_is_harmless(
    client: TestClient, private_storage: Path
) -> None:
    adult_student(client)
    doc = upload_and_process(client, private_storage)
    assert client.delete(f"/api/v1/documents/{doc['id']}", headers=with_csrf(client)).status_code
    assert query("SELECT count(*) FROM document_pages")[0][0] == 0
    assert query("SELECT count(*) FROM document_chunks")[0][0] == 0
    assert search(client, "primary").json()["results"] == []

    # Deleted before the worker got to it: the job finishes without error.
    other = upload(client, LECTURE, "Again.pdf").json()
    client.delete(f"/api/v1/documents/{other['id']}", headers=with_csrf(client))
    run_jobs(private_storage)
    assert query("SELECT status FROM jobs ORDER BY created_at DESC LIMIT 1") == [("done",)]


def test_search_ignores_accents(client: TestClient, private_storage: Path) -> None:
    adult_student(client)
    pdf = text_pdf([["Load the Pokémon dataset and count the légendary rows in each generation."]])
    upload_and_process(client, private_storage, pdf, "Pokemon.pdf")
    [hit] = search(client, "pokemon legendary").json()["results"]
    assert f"{MARK_START}Pokémon{MARK_END}" in hit["snippet"]  # shown as written
    assert search(client, "Pokémon").json()["results"]
