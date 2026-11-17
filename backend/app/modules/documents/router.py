import re
import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status

from app.core.config import get_settings
from app.core.database import SessionDep
from app.core.errors import PayloadTooLarge
from app.core.storage import Storage, get_storage
from app.modules.auth.dependencies import CurrentUser, StudentUser, require_csrf
from app.modules.documents import service
from app.modules.documents.schemas import (
    DocumentAccessOut,
    DocumentOut,
    DocumentRename,
    SearchOut,
)

router = APIRouter(prefix="/documents", tags=["documents"])

StorageDep = Annotated[Storage, Depends(get_storage)]


def _refuse_huge_requests(request: Request) -> None:
    """Refuse an obviously oversized upload before its body is read at all.

    The exact limit is checked again while reading. In production the web server in front
    (nginx, a load balancer) should also cap request sizes."""
    limit = get_settings().document_max_mb * 1024 * 1024 + 64 * 1024  # room for form fields
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > limit:
        raise PayloadTooLarge("That file is too large.", code="file_too_large")


@router.get("/access")
async def upload_access(user: CurrentUser, session: SessionDep) -> DocumentAccessOut:
    """Whether you can upload, your limits and your usage."""
    return await service.access(session, user)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf), Depends(_refuse_huge_requests)],
)
async def upload_document(
    student: StudentUser,
    session: SessionDep,
    storage: StorageDep,
    file: Annotated[UploadFile, File(description="A PDF file")],
) -> DocumentOut:
    """Upload a PDF. It is checked, then stored privately; only you can open it."""
    return await service.upload(session, storage, student, file)


@router.get("")
async def list_documents(student: StudentUser, session: SessionDep) -> list[DocumentOut]:
    """Your documents, newest first."""
    return await service.list_documents(session, student)


# Declared before /{document_id} so "search" is never read as a document id.
@router.get("/search")
async def search_documents(
    student: StudentUser,
    session: SessionDep,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    document_id: uuid.UUID | None = None,
) -> SearchOut:
    """Search the text of your own documents. Returns pages and short snippets."""
    return await service.search(session, student, q, document_id)


@router.get("/{document_id}")
async def get_document(
    document_id: uuid.UUID, student: StudentUser, session: SessionDep
) -> DocumentOut:
    return service.to_out(await service.get_owned(session, student, document_id))


def _disposition(kind: str, filename: str) -> str:
    """Content-Disposition with a plain-ASCII fallback and the real name (RFC 6266)."""
    ascii_name = re.sub(r"[^A-Za-z0-9._ -]", "_", filename) or "document.pdf"
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


@router.get("/{document_id}/file")
async def document_file(
    document_id: uuid.UUID,
    student: StudentUser,
    session: SessionDep,
    storage: StorageDep,
    download: bool = False,
) -> Response:
    """The PDF itself: shown in the browser, or saved with ?download=true. Owner only."""
    doc, data = await service.read_file(session, storage, student, document_id)
    return Response(
        content=data,
        media_type=doc.mime_type,
        headers={
            "Content-Disposition": _disposition(
                "attachment" if download else "inline", doc.original_filename
            ),
            # Never cached by the browser or anything in between (shared computers).
            "Cache-Control": "private, no-store",
            # The browser must treat it as a PDF, never guess another type.
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


@router.post("/{document_id}/process", dependencies=[Depends(require_csrf)])
async def process_document(
    document_id: uuid.UUID, student: StudentUser, session: SessionDep
) -> DocumentOut:
    """Try reading the text of a document again after processing failed."""
    return await service.reprocess(session, student, document_id)


@router.patch("/{document_id}", dependencies=[Depends(require_csrf)])
async def rename_document(
    document_id: uuid.UUID, data: DocumentRename, student: StudentUser, session: SessionDep
) -> DocumentOut:
    return await service.rename(session, student, document_id, data.title)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_document(
    document_id: uuid.UUID, student: StudentUser, session: SessionDep, storage: StorageDep
) -> Response:
    """Delete the document and its file permanently."""
    await service.delete(session, storage, student, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
