"""Imports every table so Alembic sees the full schema. Add new models.py files here."""

from app.ai.models import AIRequest
from app.core.audit import AuditLog
from app.core.database import Base
from app.modules.adaptive.models import MasteryEvent, QuestionAttempt, TopicMastery
from app.modules.auth.models import User
from app.modules.classroom.models import LearningSession, Message
from app.modules.curriculum.models import (
    Misconception,
    Question,
    Subject,
    Topic,
    TopicPrerequisite,
)
from app.modules.students.models import GuardianLink, StudentProfile

__all__ = [
    "AIRequest",
    "AuditLog",
    "Base",
    "GuardianLink",
    "LearningSession",
    "MasteryEvent",
    "Message",
    "Misconception",
    "Question",
    "QuestionAttempt",
    "StudentProfile",
    "Subject",
    "Topic",
    "TopicMastery",
    "TopicPrerequisite",
    "User",
]
