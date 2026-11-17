import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    role: Literal["student", "teacher"]
    content: str
    cited_pages: list[int]
    whiteboard: list[dict[str, Any]] | None
    created_at: datetime


class DocumentRef(BaseModel):
    id: uuid.UUID
    title: str
    original_filename: str
    page_count: int | None
    pages_with_text: int | None


class ChatOut(BaseModel):
    document: DocumentRef
    messages: list[ChatMessageOut]
    # "development_only": the configured AI is a free or trial plan that may keep or
    # train on what it is sent, so only test documents should be used. None: no notice.
    ai_notice: str | None


class ChatTurnIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)

    @field_validator("text")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("text is required")
        return v
