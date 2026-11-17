"""Imports every table so Alembic sees the full schema. Add new models.py files here."""

from app.ai.models import AIRequest
from app.core.audit import AuditLog
from app.core.database import Base
from app.modules.adaptive.models import MasteryEvent, QuestionAttempt, TopicMastery
from app.modules.auth.models import RefreshToken, User
from app.modules.classroom.models import LearningSession, Message
from app.modules.curriculum.models import (
    Course,
    Discipline,
    LearningObjective,
    Misconception,
    Question,
    Subject,
    Topic,
    TopicPrerequisite,
)
from app.modules.documents.models import Document, DocumentChunk, DocumentPage
from app.modules.jobs.models import Job
from app.modules.students.models import GuardianInvite, GuardianLink, StudentProfile

__all__ = [
    "AIRequest",
    "AuditLog",
    "Base",
    "Course",
    "Discipline",
    "Document",
    "DocumentChunk",
    "DocumentPage",
    "GuardianInvite",
    "GuardianLink",
    "Job",
    "LearningObjective",
    "LearningSession",
    "MasteryEvent",
    "Message",
    "Misconception",
    "Question",
    "QuestionAttempt",
    "RefreshToken",
    "StudentProfile",
    "Subject",
    "Topic",
    "TopicMastery",
    "TopicPrerequisite",
    "User",
]
