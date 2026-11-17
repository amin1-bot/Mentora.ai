import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAt, UUIDPrimaryKey


class AIRequest(UUIDPrimaryKey, CreatedAt, Base):
    """Cost and speed of each model call. Never stores the student's text."""

    __tablename__ = "ai_requests"

    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="SET NULL"), index=True
    )
    # Set instead of session_id for questions about a document (phase 4).
    document_chat_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_chats.id", ondelete="SET NULL"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(30), nullable=False, server_default="lesson")
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
