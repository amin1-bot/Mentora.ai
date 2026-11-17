import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAt, UUIDPrimaryKey

# The file is stored and viewable in every status. "processing": text is being read;
# "ready": text read (search works for pages that have a text layer); "failed": reading
# the text failed, see error_code (the student can retry).
DOCUMENT_STATUSES = ("ready", "processing", "failed")


class Document(UUIDPrimaryKey, CreatedAt, Base):
    """One uploaded file. The file itself lives in private storage under `storage_key`;
    this row only describes it. Nothing here is ever shown to another user."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(f"status IN {DOCUMENT_STATUSES}", name="status_valid"),
        CheckConstraint("size_bytes > 0", name="size_positive"),
        CheckConstraint("page_count IS NULL OR page_count > 0", name="page_count_positive"),
        # The same file is stored once per owner.
        Index("uq_documents_owner_sha256", "owner_id", "sha256", unique=True),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Who uploaded it. Today always the owner; later a guardian may upload for a child.
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # Random, server-generated, never sent to the browser.
    storage_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ready")
    # Set by processing: why it failed, or "no_text_layer" when every page is a scan.
    error_code: Mapped[str | None] = mapped_column(String(50))
    pages_with_text: Mapped[int | None] = mapped_column(Integer)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentPage(CreatedAt, Base):
    """The text of one page, exactly as read from the PDF's text layer. Page numbers are
    the PDF's own (1 = first page), so citations always point at the right page."""

    __tablename__ = "document_pages"
    __table_args__ = (CheckConstraint("page_number > 0", name="page_number_positive"),)

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    page_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    # False for scanned pages (an image without text); those need OCR, planned with AI.
    has_text: Mapped[bool] = mapped_column(Boolean, nullable=False)


class DocumentChunk(UUIDPrimaryKey, CreatedAt, Base):
    """A searchable section of a document (a few hundred words), with the pages it covers.

    owner_id is copied from the document so every search filters by owner directly."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        CheckConstraint("page_start > 0 AND page_end >= page_start", name="pages_valid"),
        Index("ix_document_chunks_search", "search", postgresql_using="gin"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)  # order in the document
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str | None] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)  # an estimate
    # "mentora_text" (created in the migration) is PostgreSQL's "simple" configuration plus
    # unaccent: no language-specific stemming, so English, Turkish and Russian notes work
    # the same way, and accents are ignored. Kept up to date by PostgreSQL itself.
    search: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('mentora_text'::regconfig, coalesce(heading, '') || ' ' || text)",
            persisted=True,
        ),
    )
