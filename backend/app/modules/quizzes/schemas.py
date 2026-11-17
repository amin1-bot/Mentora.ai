import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

QuestionType = Literal["multiple_choice", "true_false", "fill_blank"]


class QuizCreate(BaseModel):
    count: int = Field(default=8, ge=3, le=15)
    types: list[QuestionType] = Field(
        default=["multiple_choice", "true_false", "fill_blank"], min_length=1
    )
    difficulty: Literal["easy", "medium", "hard", "mixed"] = "mixed"
    page_from: int | None = Field(default=None, ge=1)
    page_to: int | None = Field(default=None, ge=1)
    time_limit_minutes: int = Field(default=0, ge=0, le=120)  # 0: no timer

    @model_validator(mode="after")
    def _clean(self) -> "QuizCreate":
        self.types = list(dict.fromkeys(self.types))
        if self.page_from and self.page_to and self.page_to < self.page_from:
            raise ValueError("page_to must not be before page_from")
        return self


class QuizOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    title: str
    status: str  # generating | ready | failed
    error_code: str | None
    question_count: int
    count_requested: int
    types: list[str]
    difficulty: str
    page_from: int | None
    page_to: int | None
    time_limit_minutes: int
    best_score: int | None  # best finished attempt
    attempts: int
    created_at: datetime


class Feedback(BaseModel):
    """Shown after a question is answered, never before."""

    is_correct: bool
    your_answer: str
    correct_answer: str
    explanation: str
    source_pages: list[int]


class AttemptQuestion(BaseModel):
    """What the student sees of a question: never the answer, unless already answered."""

    id: uuid.UUID
    position: int
    question_type: QuestionType
    prompt: str
    options: list[str] | None  # multiple choice only
    feedback: Feedback | None


class ReviewPage(BaseModel):
    page: int
    heading: str | None
    missed: int


class Report(BaseModel):
    score: int
    total: int
    answered: int
    percent: int
    seconds: int
    by_type: dict[str, dict[str, int]]  # {"true_false": {"correct": 2, "total": 3}}
    review_pages: list[ReviewPage]  # pages behind wrong or skipped questions
    timed_out: bool


class AttemptOut(BaseModel):
    id: uuid.UUID
    quiz_id: uuid.UUID
    quiz_title: str
    document_id: uuid.UUID
    started_at: datetime
    deadline: datetime | None
    finished_at: datetime | None
    questions: list[AttemptQuestion]
    report: Report | None


class AnswerIn(BaseModel):
    question_id: uuid.UUID
    # Option index (multiple choice), true/false, or the words for the blank.
    answer: int | bool | str

    @model_validator(mode="after")
    def _short(self) -> "AnswerIn":
        if isinstance(self.answer, str):
            self.answer = self.answer.strip()[:200]
        return self
