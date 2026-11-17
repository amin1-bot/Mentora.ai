"""Documents: upload, list, view, rename, delete. Ownership is checked on every call.

Security rules (each has a test in test_documents.py):
- A student only ever sees their own documents. Asking for someone else's gets the same
  "not found" as asking for one that does not exist, so ids cannot be probed.
- Files go to private storage under a random key; there is no public URL.
- The storage key and file hash never leave the server.
- Logs and the audit trail record ids only, never file names or contents.

Other modules (phase 3: text extraction, AI teacher) read documents through `read_file`
and `get_owned`, so the same checks apply to them.
"""

import logging
import uuid

from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.config import get_settings
from app.core.errors import AppError, Conflict, Forbidden, NotFound, PayloadTooLarge
from app.core.storage import Storage, StorageError
from app.modules.auth.models import User
from app.modules.documents import repository as repo
from app.modules.documents.models import Document
from app.modules.documents.permissions import upload_access
from app.modules.documents.schemas import (
    DocumentAccessOut,
    DocumentLimits,
    DocumentOut,
    DocumentUsage,
)
from app.modules.documents.validation import PDF_MIME, check_pdf

logger = logging.getLogger(__name__)

MB = 1024 * 1024
_CHUNK = MB


class StorageUnavailable(AppError):
    status_code = 503
    code = "storage_unavailable"
    message = "Files cannot be saved or opened right now. Please try again later."


def to_out(d: Document) -> DocumentOut:
    return DocumentOut(
        id=d.id,
        title=d.title,
        original_filename=d.original_filename,
        size_bytes=d.size_bytes,
        page_count=d.page_count,
        status=d.status,
        created_at=d.created_at,
    )


async def access(db: AsyncSession, user: User) -> DocumentAccessOut:
    s = get_settings()
    allowed = await upload_access(db, user)
    count, used = await repo.usage(db, user.id) if user.role == "student" else (0, 0)
    return DocumentAccessOut(
        can_upload=allowed.allowed,
        reason_code=allowed.code,
        reason=allowed.message,
        limits=DocumentLimits(
            max_file_mb=s.document_max_mb,
            max_pages=s.document_max_pages,
            max_documents=s.document_max_count,
            quota_mb=s.document_quota_mb,
        ),
        usage=DocumentUsage(documents=count, bytes_used=used),
    )


async def _read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    """Read the upload, stopping as soon as it is too large (never the whole thing)."""
    parts: list[bytes] = []
    size = 0
    while chunk := await upload.read(_CHUNK):
        size += len(chunk)
        if size > max_bytes:
            raise PayloadTooLarge(
                f"That file is larger than {max_bytes // MB} MB.", code="file_too_large"
            )
        parts.append(chunk)
    return b"".join(parts)


async def upload(db: AsyncSession, storage: Storage, user: User, file: UploadFile) -> DocumentOut:
    s = get_settings()
    allowed = await upload_access(db, user)
    if not allowed.allowed:
        raise Forbidden(allowed.message, code=allowed.code)

    max_bytes = s.document_max_mb * MB
    data = await _read_limited(file, max_bytes)
    # Parsing a PDF is CPU work: keep it off the event loop so other requests are not held up.
    checked = await run_in_threadpool(
        check_pdf, data, file.filename, max_bytes=max_bytes, max_pages=s.document_max_pages
    )

    count, used = await repo.usage(db, user.id)
    if count >= s.document_max_count:
        raise Conflict(
            f"You can keep up to {s.document_max_count} documents. Delete one to add another.",
            code="document_limit_reached",
        )
    if used + checked.size_bytes > s.document_quota_mb * MB:
        raise Conflict(
            f"This would go over your {s.document_quota_mb} MB storage limit. "
            "Delete a document to make room.",
            code="storage_quota_exceeded",
        )
    if await repo.by_hash(db, user.id, checked.sha256):
        raise Conflict("You have already uploaded this file.", code="duplicate_document")

    document_id = uuid.uuid4()
    key = f"documents/{user.id.hex}/{document_id.hex}.pdf"
    try:
        await run_in_threadpool(storage.save, key, data)
    except StorageError as exc:
        logger.error("Saving document %s failed: %s", document_id, exc)
        raise StorageUnavailable() from exc

    doc = Document(
        id=document_id,
        owner_id=user.id,
        uploaded_by_id=user.id,
        title=checked.title,
        original_filename=checked.filename,
        mime_type=PDF_MIME,
        size_bytes=checked.size_bytes,
        page_count=checked.page_count,
        sha256=checked.sha256,
        storage_key=key,
        status="ready",
    )
    db.add(doc)
    record_audit(db, actor_id=user.id, action="upload", entity="document", entity_id=document_id)
    try:
        await db.commit()
    except IntegrityError as exc:
        # Two identical uploads at the same moment: keep one, remove this file.
        await db.rollback()
        await run_in_threadpool(storage.delete, key)
        raise Conflict("You have already uploaded this file.", code="duplicate_document") from exc
    except Exception:
        await db.rollback()
        await run_in_threadpool(storage.delete, key)
        raise
    await db.refresh(doc)
    return to_out(doc)


async def list_documents(db: AsyncSession, user: User) -> list[DocumentOut]:
    return [to_out(d) for d in await repo.list_owned(db, user.id)]


async def get_owned(db: AsyncSession, user: User, document_id: uuid.UUID) -> Document:
    doc = await repo.owned(db, user.id, document_id)
    if doc is None:
        raise NotFound("Document not found.", code="document_not_found")
    return doc


async def read_file(
    db: AsyncSession, storage: Storage, user: User, document_id: uuid.UUID
) -> tuple[Document, bytes]:
    doc = await get_owned(db, user, document_id)
    try:
        data = await run_in_threadpool(storage.read, doc.storage_key)
    except StorageError as exc:
        logger.error("Reading document %s failed: %s", doc.id, exc)
        raise StorageUnavailable() from exc
    return doc, data


async def rename(db: AsyncSession, user: User, document_id: uuid.UUID, title: str) -> DocumentOut:
    doc = await get_owned(db, user, document_id)
    doc.title = " ".join(title.split())[:200] or doc.title
    await db.commit()
    await db.refresh(doc)
    return to_out(doc)


async def delete(db: AsyncSession, storage: Storage, user: User, document_id: uuid.UUID) -> None:
    """Delete the record first, then the file. If the file removal fails, the document is
    already gone for the student; the leftover file is logged for clean-up."""
    doc = await get_owned(db, user, document_id)
    key = doc.storage_key
    await db.delete(doc)
    record_audit(db, actor_id=user.id, action="delete", entity="document", entity_id=document_id)
    await db.commit()
    try:
        await run_in_threadpool(storage.delete, key)
    except StorageError as exc:
        logger.error("Document %s deleted but its file was not removed: %s", document_id, exc)


async def delete_all_for_owner(db: AsyncSession, storage: Storage, owner_id: uuid.UUID) -> int:
    """Remove every document of one user (for account deletion). Returns how many."""
    docs = await repo.list_owned(db, owner_id)
    keys = [d.storage_key for d in docs]
    for d in docs:
        await db.delete(d)
    await db.commit()
    for key in keys:
        try:
            await run_in_threadpool(storage.delete, key)
        except StorageError as exc:
            logger.error("Leftover document file after account clean-up: %s", exc)
    return len(docs)
