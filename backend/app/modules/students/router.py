import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.core.database import SessionDep
from app.core.email import EmailSender, get_email_sender
from app.core.errors import TooManyRequests
from app.core.rate_limit import auth_limiter
from app.modules.auth.dependencies import CurrentUser, GuardianUser, StudentUser, require_csrf
from app.modules.students import service
from app.modules.students.schemas import (
    ConsentOut,
    ConsentRequest,
    GuardianInviteOut,
    GuardianInviteRequest,
    InviteInfoOut,
    InviteTokenRequest,
    ProfileOut,
    ProfileUpdate,
)

students_router = APIRouter(prefix="/students", tags=["students"])
guardians_router = APIRouter(prefix="/guardians", tags=["guardians"])


@students_router.get("/me")
async def get_my_profile(student: StudentUser, session: SessionDep) -> ProfileOut:
    return await service.get_profile(session, student, student.id)


@students_router.patch("/me", dependencies=[Depends(require_csrf)])
async def update_my_profile(
    changes: ProfileUpdate, student: StudentUser, session: SessionDep
) -> ProfileOut:
    return await service.update_own_profile(session, student, changes)


@students_router.get("/{student_id}")
async def get_student_profile(
    student_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> ProfileOut:
    """For the student themselves or an approved guardian. Everyone else gets 403."""
    return await service.get_profile(session, user, student_id)


@guardians_router.post(
    "/invite", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)]
)
async def invite_guardian(
    data: GuardianInviteRequest,
    student: StudentUser,
    session: SessionDep,
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> GuardianInviteOut:
    """Send (or re-send) the approval email to a parent or guardian."""
    if not auth_limiter.hit(f"guardian-invite:{student.id}", limit=3):
        raise TooManyRequests()
    invite = await service.invite_guardian(session, email_sender, student, str(data.guardian_email))
    return GuardianInviteOut(expires_at=invite.expires_at)


@guardians_router.post("/invite-info")
async def get_invite_info(
    data: InviteTokenRequest, request: Request, session: SessionDep
) -> InviteInfoOut:
    """What the guardian sees before approving. The token comes from the emailed link."""
    ip = request.client.host if request.client else "unknown"
    if not auth_limiter.hit(f"invite-info:{ip}", limit=20):
        raise TooManyRequests()
    return await service.invite_info(session, data.token)


@guardians_router.post("/consent", dependencies=[Depends(require_csrf)])
async def give_consent(
    data: ConsentRequest, guardian: GuardianUser, session: SessionDep
) -> ConsentOut:
    """The logged-in guardian approves the student's account."""
    return await service.give_consent(session, guardian, data.token, data.consent_version)
