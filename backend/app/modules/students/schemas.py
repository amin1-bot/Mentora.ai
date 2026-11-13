import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.modules.auth.schemas import ConsentStatus, DisplayName


class ProfileOut(BaseModel):
    user_id: uuid.UUID
    display_name: str
    date_of_birth: date
    grade_level: int
    language: str
    consent_status: ConsentStatus


class ProfileUpdate(BaseModel):
    """Date of birth cannot be changed here, because age rules depend on it."""

    display_name: DisplayName | None = None
    grade_level: int | None = Field(default=None, ge=1, le=12)
    language: Literal["en"] | None = None  # more languages in Phase 13


class GuardianInviteRequest(BaseModel):
    guardian_email: EmailStr


class GuardianInviteOut(BaseModel):
    expires_at: datetime


class InviteTokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=100)


class InviteInfoOut(BaseModel):
    """What the guardian sees before approving."""

    student_display_name: str
    consent_version: str
    expires_at: datetime


class ConsentRequest(InviteTokenRequest):
    # The guardian confirms they are the parent or legal guardian.
    confirm_is_guardian: Literal[True]
    # The version of the consent text the guardian saw; must be the current one.
    consent_version: str = Field(max_length=20)


class ConsentOut(BaseModel):
    student_id: uuid.UUID
    status: Literal["approved"]
    consent_version: str
    consent_given_at: datetime
