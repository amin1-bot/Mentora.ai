"""Documents (multi-subject plan, phase 2): secure upload, private storage, listing,
viewing, renaming and deletion. Most tests here are about who must NOT get access."""

import io
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.core.config import get_settings
from app.core.storage import LocalStorage, StorageError
from app.tests.helpers import new_client, query, signup_guardian, signup_student, with_csrf
from app.tests.test_classroom import adult_student


def make_pdf(pages: int = 1, *, password: str | None = None, script: bool = False) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    if password:
        writer.encrypt(password)
    out = io.BytesIO()
    writer.write(out)
    data = out.getvalue()
    if script:
        # A JavaScript action, as a malicious PDF would carry it.
        data += b"\n99 0 obj << /Type /Action /S /JavaScript /JS (app.alert(1)) >> endobj\n"
    return data


def upload(client: TestClient, data: bytes, name: str = "Lecture 1.pdf", csrf: bool = True):
    return client.post(
        "/api/v1/documents",
        files={"file": (name, data, "application/pdf")},
        headers=with_csrf(client) if csrf else {},
    )


def stored_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()] if root.exists() else []


# ---------- the happy path ----------


def test_upload_list_view_and_download_your_own_pdf(
    client: TestClient, private_storage: Path
) -> None:
    owner = adult_student(client)
    pdf = make_pdf(3)
    r = upload(client, pdf, "Week 1 - Databases.pdf")
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["title"] == "Week 1 - Databases"
    assert doc["original_filename"] == "Week 1 - Databases.pdf"
    assert doc["page_count"] == 3 and doc["size_bytes"] == len(pdf)
    # Viewable at once; its text is read in the background (test_document_processing.py).
    assert doc["status"] == "processing" and doc["pages_with_text"] is None
    # Server-side details never reach the browser.
    assert "storage_key" not in doc and "sha256" not in doc and "owner_id" not in doc

    # Stored privately under a random name inside the owner's folder.
    [path] = stored_files(private_storage)
    assert path.read_bytes() == pdf
    assert path.parent.name == uuid.UUID(owner).hex and "Week" not in path.name

    assert [d["id"] for d in client.get("/api/v1/documents").json()] == [doc["id"]]
    assert client.get(f"/api/v1/documents/{doc['id']}").json() == doc

    view = client.get(f"/api/v1/documents/{doc['id']}/file")
    assert view.status_code == 200 and view.content == pdf
    assert view.headers["content-type"] == "application/pdf"
    assert view.headers["content-disposition"].startswith("inline;")
    assert view.headers["cache-control"] == "private, no-store"
    assert view.headers["x-content-type-options"] == "nosniff"
    download = client.get(f"/api/v1/documents/{doc['id']}/file?download=true")
    assert download.headers["content-disposition"].startswith("attachment;")

    # The audit trail records the upload by id only.
    assert query("SELECT action, entity FROM audit_log WHERE entity = 'document'") == [
        ("upload", "document")
    ]


def test_rename_and_delete(client: TestClient, private_storage: Path) -> None:
    adult_student(client)
    doc = upload(client, make_pdf()).json()
    r = client.patch(
        f"/api/v1/documents/{doc['id']}",
        json={"title": "  Exam   revision  "},
        headers=with_csrf(client),
    )
    assert r.status_code == 200 and r.json()["title"] == "Exam revision"
    bad = client.patch(
        f"/api/v1/documents/{doc['id']}", json={"title": ""}, headers=with_csrf(client)
    )
    assert bad.status_code == 422

    r = client.delete(f"/api/v1/documents/{doc['id']}", headers=with_csrf(client))
    assert r.status_code == 204
    assert stored_files(private_storage) == []  # the file is gone from disk
    assert query("SELECT count(*) FROM documents") == [(0,)]
    assert client.get(f"/api/v1/documents/{doc['id']}").status_code == 404
    again = client.delete(f"/api/v1/documents/{doc['id']}", headers=with_csrf(client))
    assert again.status_code == 404


# ---------- who must NOT get access ----------


def test_another_student_cannot_see_open_rename_or_delete_your_document(
    client: TestClient, private_storage: Path
) -> None:
    adult_student(client, "owner@example.com")
    doc = upload(client, make_pdf()).json()

    with new_client() as other:
        adult_student(other, "other@example.com")
        assert other.get("/api/v1/documents").json() == []
        missing = other.get(f"/api/v1/documents/{uuid.uuid4()}")
        attempts = [
            other.get(f"/api/v1/documents/{doc['id']}"),
            other.get(f"/api/v1/documents/{doc['id']}/file"),
            other.get(f"/api/v1/documents/{doc['id']}/file?download=true"),
            other.patch(
                f"/api/v1/documents/{doc['id']}", json={"title": "mine"}, headers=with_csrf(other)
            ),
            other.delete(f"/api/v1/documents/{doc['id']}", headers=with_csrf(other)),
        ]
        for r in attempts:
            # Exactly the same answer as for a document that does not exist: no probing.
            assert r.status_code == 404, r.text
            assert r.json() == missing.json()

    # Nothing changed for the owner.
    assert client.get(f"/api/v1/documents/{doc['id']}").json()["title"] == doc["title"]
    assert client.get(f"/api/v1/documents/{doc['id']}/file").status_code == 200
    assert len(stored_files(private_storage)) == 1


def test_logged_out_visitors_get_nothing(client: TestClient) -> None:
    adult_student(client)
    doc = upload(client, make_pdf()).json()
    with new_client() as anonymous:
        for r in (
            anonymous.get("/api/v1/documents"),
            anonymous.get(f"/api/v1/documents/{doc['id']}/file"),
            anonymous.get("/api/v1/documents/access"),
        ):
            assert r.status_code == 401


def test_guardians_cannot_upload_or_list(client: TestClient) -> None:
    signup_guardian(client, "parent@example.com")
    assert upload(client, make_pdf()).status_code == 403
    assert client.get("/api/v1/documents").status_code == 403
    access = client.get("/api/v1/documents/access").json()
    assert access["can_upload"] is False and access["reason_code"] == "documents_students_only"


def test_students_under_18_cannot_upload_yet(client: TestClient, private_storage: Path) -> None:
    signup_student(client, "teen@example.com", age=16)
    access = client.get("/api/v1/documents/access").json()
    assert access["can_upload"] is False
    assert access["reason_code"] == "documents_age_restricted"
    assert "parent" in access["reason"]
    r = upload(client, make_pdf())
    assert r.status_code == 403 and r.json()["error"]["code"] == "documents_age_restricted"
    assert stored_files(private_storage) == []
    # Listing their (empty) library still works.
    assert client.get("/api/v1/documents").json() == []


def test_upload_rename_and_delete_need_the_csrf_token(client: TestClient) -> None:
    adult_student(client)
    assert upload(client, make_pdf(), csrf=False).status_code == 403
    doc = upload(client, make_pdf()).json()
    assert client.patch(f"/api/v1/documents/{doc['id']}", json={"title": "x"}).status_code == 403
    assert client.delete(f"/api/v1/documents/{doc['id']}").status_code == 403


# ---------- file validation ----------


@pytest.mark.parametrize(
    ("name", "data", "status", "code"),
    [
        ("notes.txt", b"just text", 415, "not_a_pdf"),
        ("virus.pdf", b"MZ\x90\x00 this is really a program", 415, "not_a_pdf"),
        ("empty.pdf", b"", 422, "empty_file"),
        ("broken.pdf", b"%PDF-1.7\n this is not really a pdf at all", 422, "pdf_unreadable"),
    ],
)
def test_files_that_are_not_valid_pdfs_are_refused(
    client: TestClient, private_storage: Path, name: str, data: bytes, status: int, code: str
) -> None:
    adult_student(client)
    r = upload(client, data, name)
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code
    assert stored_files(private_storage) == []


def test_password_protected_pdfs_are_refused(client: TestClient) -> None:
    adult_student(client)
    r = upload(client, make_pdf(password="secret"))
    assert r.status_code == 422 and r.json()["error"]["code"] == "pdf_encrypted"


def test_pdfs_with_scripts_are_refused(client: TestClient) -> None:
    adult_student(client)
    r = upload(client, make_pdf(script=True))
    assert r.status_code == 422 and r.json()["error"]["code"] == "pdf_active_content"


def test_page_and_size_limits(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    adult_student(client)
    settings = get_settings()
    monkeypatch.setattr(settings, "document_max_pages", 2)
    r = upload(client, make_pdf(3))
    assert r.status_code == 422 and r.json()["error"]["code"] == "too_many_pages"

    monkeypatch.setattr(settings, "document_max_mb", 1)
    big = make_pdf() + b"%" + b"0" * (1024 * 1024 + 10)  # valid PDF padded past 1 MB
    r = upload(client, big)
    assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"


def test_dangerous_file_names_are_cleaned(client: TestClient, private_storage: Path) -> None:
    adult_student(client)
    r = upload(client, make_pdf(), "../../etc/passwd.pdf")
    assert r.status_code == 201
    assert r.json()["original_filename"] == "passwd.pdf"
    [path] = stored_files(private_storage)
    assert private_storage.resolve() in path.resolve().parents


def test_duplicates_and_quotas(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    adult_student(client)
    pdf = make_pdf()
    assert upload(client, pdf).status_code == 201
    r = upload(client, pdf, "same file again.pdf")
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_document"

    settings = get_settings()
    monkeypatch.setattr(settings, "document_max_count", 1)
    r = upload(client, make_pdf(2))
    assert r.status_code == 409 and r.json()["error"]["code"] == "document_limit_reached"

    monkeypatch.setattr(settings, "document_max_count", 50)
    monkeypatch.setattr(settings, "document_quota_mb", 0)
    r = upload(client, make_pdf(2))
    assert r.status_code == 409 and r.json()["error"]["code"] == "storage_quota_exceeded"

    usage = client.get("/api/v1/documents/access").json()
    assert usage["can_upload"] is True
    assert usage["usage"]["documents"] == 1 and usage["usage"]["bytes_used"] == len(pdf)


def test_deleting_all_of_a_users_documents_removes_their_files(
    client: TestClient, private_storage: Path
) -> None:
    import asyncio

    from app.core.database import SessionLocal
    from app.modules.documents import service

    owner = uuid.UUID(adult_student(client))
    upload(client, make_pdf(1))
    upload(client, make_pdf(2))
    assert len(stored_files(private_storage)) == 2

    async def run() -> int:
        async with SessionLocal() as db:
            return await service.delete_all_for_owner(db, LocalStorage(private_storage), owner)

    assert asyncio.run(run()) == 2
    assert stored_files(private_storage) == []
    assert query("SELECT count(*) FROM documents") == [(0,)]


def test_file_name_cleaning() -> None:
    from app.modules.documents.validation import clean_filename

    assert clean_filename("C:\\Users\\me\\notes.pdf") == "notes.pdf"
    assert clean_filename("bad\x00\x1fname\n.pdf") == "badname.pdf"
    assert clean_filename("   ") == "document.pdf"
    long = clean_filename("a" * 300 + ".pdf")
    assert len(long) == 150 and long.endswith(".pdf")


# ---------- the storage layer itself ----------


@pytest.mark.parametrize("key", ["../outside.pdf", "documents/../../x", "/etc/passwd", "a\\b"])
def test_storage_refuses_keys_that_could_escape_its_folder(tmp_path: Path, key: str) -> None:
    store = LocalStorage(tmp_path / "store")
    with pytest.raises(StorageError):
        store.save(key, b"x")


def test_storage_round_trip(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "store")
    store.save("documents/abc/file.pdf", b"data")
    assert store.exists("documents/abc/file.pdf")
    assert store.read("documents/abc/file.pdf") == b"data"
    store.delete("documents/abc/file.pdf")
    store.delete("documents/abc/file.pdf")  # deleting twice is fine
    assert not store.exists("documents/abc/file.pdf")
