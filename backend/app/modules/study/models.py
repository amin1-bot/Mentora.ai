import uuid
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAt, UUIDPrimaryKey

CHAT_ROLES = ("student", "teacher")


class DocumentChat(UUIDPrimaryKey, CreatedAt, Base):
    """A student's conversation with the teacher about one of their own documents.
    One per student and document; "start over" deletes its messages."""

    __tablename__ = "document_chats"
    __table_args__ = (UniqueConstraint("student_id", "document_id", name="one_per_document"),)

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )


class DocumentChatMessage(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "document_chat_messages"
    __table_args__ = (
        CheckConstraint(f"role IN {CHAT_ROLES}", name="role_valid"),
        Index("ix_document_chat_messages_chat_created", "chat_id", "created_at"),
    )

    chat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_chats.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Teacher replies: the pages it cited, checked against the pages it was given.
    cited_pages: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    # Teacher replies: the pages it was given (for the eval and for follow-up questions).
    source_pages: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    # Validated board blocks (never HTML), like lesson messages.
    whiteboard: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
