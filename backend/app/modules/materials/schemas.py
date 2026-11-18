import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

Kind = Literal["summary", "guide", "flashcards"]


class MaterialCreate(BaseModel):
    kind: Kind
    page_from: int | None = Field(default=None, ge=1)
    page_to: int | None = Field(default=None, ge=1)
    card_count: int = Field(default=15, ge=5, le=40)  # flashcards only

    @model_validator(mode="after")
    def _pages(self) -> "MaterialCreate":
        if self.page_from and self.page_to and self.page_to < self.page_from:
            raise ValueError("page_to must not be before page_from")
        return self


class MaterialRename(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class MaterialSummaryOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    kind: Kind
    title: str
    status: str  # generating | ready | failed
    error_code: str | None
    page_from: int | None
    page_to: int | None
    items: int  # points, terms or cards
    due_cards: int  # flashcards due for review now (new cards included)
    created_at: datetime


class MaterialOut(MaterialSummaryOut):
    content: dict[str, Any] | None


class ReviewCard(BaseModel):
    index: int
    front: str
    back: str
    pages: list[int]
    is_new: bool


class ReviewOut(BaseModel):
    due: list[ReviewCard]
    total_cards: int
    learned: int  # cards reviewed at least once and not currently forgotten


class ReviewIn(BaseModel):
    rating: Literal["again", "hard", "good", "easy"]


class ReviewResult(BaseModel):
    index: int
    due_at: datetime
    interval_days: float
