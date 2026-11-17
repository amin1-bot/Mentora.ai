import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    """What the owner sees about a document. Never the storage key or file hash."""

    id: uuid.UUID
    title: str
    original_filename: str
    size_bytes: int
    page_count: int | None
    status: str  # processing | ready | failed
    error_code: str | None  # why it failed, or "no_text_layer" for scans
    pages_with_text: int | None  # how many pages are searchable
    created_at: datetime


class DocumentLimits(BaseModel):
    max_file_mb: int
    max_pages: int
    max_documents: int
    quota_mb: int


class DocumentUsage(BaseModel):
    documents: int
    bytes_used: int


class DocumentAccessOut(BaseModel):
    """Whether this user may upload, and the limits, so the page can explain itself."""

    can_upload: bool
    reason_code: str | None
    reason: str | None
    limits: DocumentLimits
    usage: DocumentUsage


class DocumentRename(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class SearchHit(BaseModel):
    document_id: uuid.UUID
    document_title: str
    page_start: int
    page_end: int
    heading: str | None
    # Plain text; matched words are wrapped in U+27E6 and U+27E7 (never HTML).
    snippet: str


class SearchOut(BaseModel):
    query: str
    terms: list[str]
    results: list[SearchHit]
