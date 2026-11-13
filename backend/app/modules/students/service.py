"""Student profiles, guardian consent, and the rule for who may see a student's data."""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.config import get_settings
from app.core.email import Email, EmailSender
from app.core.errors import AppError, Conflict, Forbidden, NotFound
from app.core.security import hash_url_token, new_url_token
from app.modules.auth.models import User
from app.modules.auth.schemas import ConsentStatus, StudentSignup
from app.modules.students import repository as repo
from app.modules.students.models import GuardianInvite, GuardianLink, StudentProfile
from app.modules.students.schemas import ConsentOut, InviteInfoOut, ProfileOut, ProfileUpdate

INVALID_INVITE = "This invitation link is invalid or has expired."


def _now() -> datetime:
    return datetime.now(UTC)


def age_on(date_of_birth: date, today: date) -> int:
    had_birthday = (today.month, today.day) >= (date_of_birth.month, date_of_birth.day)
    return today.year - date_of_birth.year - (0 if had_birthday else 1)


def needs_guardian(date_of_birth: date, today: date | None = None) -> bool:
    today = today or _now().date()
    return age_on(date_of_birth, today) < get_settings().guardian_consent_required_under


# ---------- Signup (called by the auth service) ----------


def check_signup_age(
    date_of_birth: date, guardian_email: str | None, student_email: str, today: date | None = None
) -> None:
    settings = get_settings()
    today = today or _now().date()
    if date_of_birth > today:
        raise AppError("Date of birth cannot be in the future.", code="invalid_date_of_birth")
    if age_on(date_of_birth, today) < settings.min_student_age:
        # Nothing is stored for under-age signups.
        raise Forbidden(
            f"Mentora is for students aged {settings.min_student_age} and over.",
            code="age_below_minimum",
        )
    if needs_guardian(date_of_birth, today):
        if not guardian_email:
            raise AppError(
                "A parent or guardian email is required for students under "
                f"{settings.guardian_consent_required_under}.",
                code="guardian_email_required",
            )
        if guardian_email.lower() == student_email.lower():
            raise AppError(
                "The guardian email must be different from your own.",
                code="guardian_email_same_as_student",
            )


def add_profile(session: AsyncSession, user: User, data: StudentSignup) -> None:
    session.add(
        StudentProfile(
            user_id=user.id,
            display_name=data.display_name,
            date_of_birth=data.date_of_birth,
            grade_level=data.grade_level,
        )
    )


def add_guardian_invite(
    session: AsyncSession, student_id: uuid.UUID, guardian_email: str
) -> tuple[GuardianInvite, str]:
    """Store an invite and return it with the link to email. Only the token's hash is stored."""
    settings = get_settings()
    token, token_hash = new_url_token()
    invite = GuardianInvite(
        student_id=student_id,
        guardian_email=guardian_email.lower(),
        token_hash=token_hash,
        expires_at=_now() + timedelta(days=settings.guardian_invite_days),
    )
    session.add(invite)
    # Token goes after '#' so it never reaches server logs when the guardian opens the link.
    return invite, f"{settings.frontend_url}/guardian/consent#token={token}"


async def send_guardian_invite(
    sender: EmailSender, guardian_email: str, student_display_name: str, link: str
) -> None:
    await sender.send(
        Email(
            to=guardian_email,
            subject="Please approve your child's Mentora account",
            body=(
                f"{student_display_name} has created an account on Mentora, an AI teacher "
                "for math. Because they are under 18, they need your approval before they can "
                f"start lessons. Review what we store and approve here: {link}\n\n"
                "If you did not expect this email, you can ignore it."
            ),
            link=link,
        )
    )


# ---------- Consent status and access rules ----------


async def consent_status(session: AsyncSession, student_id: uuid.UUID) -> ConsentStatus:
    profile = await repo.get_profile(session, student_id)
    if profile is None or not needs_guardian(profile.date_of_birth):
        return "not_required"
    return "approved" if await repo.has_approved_guardian(session, student_id) else "pending"


async def ensure_can_view_student(
    session: AsyncSession, actor: User, student_id: uuid.UUID
) -> None:
    """The one place that decides who may see a student's data.

    Allowed: the student themselves, and a guardian whose consent link is approved.
    Everyone else gets 403, including other students and unapproved guardians.
    """
    if actor.role == "student" and actor.id == student_id:
        return
    if actor.role == "guardian":
        link = await repo.get_link(session, student_id, actor.id)
        if link is not None and link.status == "approved":
            return
    raise Forbidden()


async def _profile_out(session: AsyncSession, profile: StudentProfile) -> ProfileOut:
    return ProfileOut(
        user_id=profile.user_id,
        display_name=profile.display_name,
        date_of_birth=profile.date_of_birth,
        grade_level=profile.grade_level,
        language=profile.language,
        consent_status=await consent_status(session, profile.user_id),
    )


async def get_profile(session: AsyncSession, actor: User, student_id: uuid.UUID) -> ProfileOut:
    await ensure_can_view_student(session, actor, student_id)
    profile = await repo.get_profile(session, student_id)
    if profile is None:
        raise NotFound()
    if actor.id != student_id:
        record_audit(
            session, actor_id=actor.id, action="read", entity="student_profile",
            entity_id=student_id,
        )
        await session.commit()
    return await _profile_out(session, profile)


async def update_own_profile(
    session: AsyncSession, student: User, changes: ProfileUpdate
) -> ProfileOut:
    profile = await repo.get_profile(session, student.id)
    if profile is None:
        raise NotFound()
    for field, value in changes.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(profile, field, value)
    await session.commit()
    return await _profile_out(session, profile)


# ---------- Guardian invitations and consent ----------


async def invite_guardian(
    session: AsyncSession, sender: EmailSender, student: User, guardian_email: str
) -> GuardianInvite:
    """Send (or re-send to a new address) the approval email. Older open invites stop working."""
    profile = await repo.get_profile(session, student.id)
    if profile is None:
        raise NotFound()
    if guardian_email.lower() == student.email.lower():
        raise AppError(
            "The guardian email must be different from your own.",
            code="guardian_email_same_as_student",
        )
    await repo.cancel_open_invites(session, student.id, _now())
    invite, link = add_guardian_invite(session, student.id, guardian_email)
    await session.commit()
    await send_guardian_invite(sender, guardian_email, profile.display_name, link)
    return invite


async def _open_invite(session: AsyncSession, token: str) -> GuardianInvite:
    invite = await repo.get_invite_by_token_hash(session, hash_url_token(token))
    if (
        invite is None
        or invite.accepted_at is not None
        or invite.cancelled_at is not None
        or invite.expires_at <= _now()
    ):
        raise NotFound(INVALID_INVITE, code="invite_invalid")
    return invite


async def invite_info(session: AsyncSession, token: str) -> InviteInfoOut:
    invite = await _open_invite(session, token)
    profile = await repo.get_profile(session, invite.student_id)
    if profile is None:
        raise NotFound(INVALID_INVITE, code="invite_invalid")
    return InviteInfoOut(
        student_display_name=profile.display_name,
        consent_version=get_settings().consent_version,
        expires_at=invite.expires_at,
    )


async def give_consent(
    session: AsyncSession, guardian: User, token: str, consent_version: str
) -> ConsentOut:
    invite = await _open_invite(session, token)
    if guardian.email.lower() != invite.guardian_email:
        raise Forbidden(
            "Log in with the email address this invitation was sent to.",
            code="invite_email_mismatch",
        )
    current = get_settings().consent_version
    if consent_version != current:
        raise Conflict(
            "The consent text has changed. Please reload and review it again.",
            code="consent_version_outdated",
        )

    now = _now()
    link = await repo.get_link(session, invite.student_id, guardian.id)
    if link is None:
        link = GuardianLink(student_id=invite.student_id, guardian_id=guardian.id)
        session.add(link)
    link.status = "approved"
    link.consent_given_at = now
    link.consent_version = current
    invite.accepted_at = now
    await session.flush()
    record_audit(
        session, actor_id=guardian.id, action="consent_given", entity="guardian_link",
        entity_id=link.id,
    )
    await session.commit()
    return ConsentOut(
        student_id=invite.student_id, status="approved", consent_version=current,
        consent_given_at=now,
    )
