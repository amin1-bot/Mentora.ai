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
    status: str
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
