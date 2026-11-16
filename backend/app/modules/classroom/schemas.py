import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class StartSessionRequest(BaseModel):
    topic_id: uuid.UUID


class TopicRef(BaseModel):
    id: uuid.UUID
    name: str


class LessonOut(BaseModel):
    """What the browser may know about the lesson. Never contains an answer."""

    has_question: bool
    question_text: str | None
    # How to reply: numeric, multiple_choice, true_false or fill_blank (None: no question).
    question_type: str | None = None
    question_options: list[str] | None = None  # multiple choice only; never says which is right
    hint_level: int
    max_hint_level: int = 3
    mastery: float = 0.0  # saved mastery for this topic, 0..1
    mastery_level: str = "not_started"


class MessageOut(BaseModel):
    id: uuid.UUID
    role: Literal["student", "teacher", "system"]
    content: str
    whiteboard: list[dict[str, Any]] | None
    created_at: datetime


class SessionOut(BaseModel):
    id: uuid.UUID
    topic: TopicRef
    status: str
    started_at: datetime
    lesson: LessonOut
    messages: list[MessageOut]


Intent = Literal["start", "message", "hint", "dont_get_it"]


class TurnIn(BaseModel):
    intent: Intent
    text: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _text_for_messages(self) -> "TurnIn":
        if self.intent == "message":
            if not self.text or not self.text.strip():
                raise ValueError("text is required for a message")
            self.text = self.text.strip()
        else:
            self.text = None
        return self
