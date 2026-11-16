import uuid
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

# Length is checked here; strength rules live in core/security.py (password_problem).
Password = Annotated[str, Field(min_length=1, max_length=128)]
DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class StudentSignup(BaseModel):
    account_type: Literal["student"]
    email: EmailStr
    password: Password
    display_name: DisplayName
    date_of_birth: date
    grade_level: int = Field(ge=1, le=13)  # school grade 1-12; 13 = university or adult
    # Required for students younger than the consent age (checked in the service).
    guardian_email: EmailStr | None = None


class GuardianSignup(BaseModel):
    account_type: Literal["guardian"]
    email: EmailStr
    password: Password


SignupRequest = Annotated[StudentSignup | GuardianSignup, Field(discriminator="account_type")]


class LoginRequest(BaseModel):
    email: EmailStr
    password: Password


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: str


ConsentStatus = Literal["approved", "pending", "not_required"]


class AuthResponse(BaseModel):
    user: UserOut
    # Only for students: whether a guardian still needs to approve the account.
    consent_status: ConsentStatus | None = None
