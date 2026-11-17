import uuid

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAt, UUIDPrimaryKey

# "ready": stored and viewable. Phase 3 adds "processing" and "failed" for text extraction.
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
