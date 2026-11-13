"""Signup, login, token refresh and logout. Knows nothing about HTTP or cookies."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.email import EmailSender
from app.core.errors import AppError, Conflict, Forbidden, TooManyRequests, Unauthorized
from app.core.security import (
    create_token,
    decode_token,
    hash_password,
    new_csrf_token,
    password_problem,
    verify_password,
)
from app.modules.auth import repository as repo
from app.modules.auth.models import User
from app.modules.auth.schemas import GuardianSignup, StudentSignup
from app.modules.students import service as students

INVALID_LOGIN = "Invalid email or password."


@dataclass(frozen=True)
class IssuedSession:
    user: User
    access_token: str
    refresh_token: str
    csrf_token: str


def _now() -> datetime:
    return datetime.now(UTC)


async def _issue_session(session: AsyncSession, user: User) -> IssuedSession:
    access, _ = create_token(user.id, user.role, "access")
    refresh, data = create_token(user.id, user.role, "refresh")
    repo.add_refresh_token(session, jti=data.jti, user_id=user.id, expires_at=data.expires_at)
    await session.commit()
    return IssuedSession(user, access, refresh, new_csrf_token())


def _check_password(password: str, email: str) -> None:
    problem = password_problem(password, email)
    if problem:
        raise AppError(problem, code="weak_password")


async def signup(
    session: AsyncSession,
    data: StudentSignup | GuardianSignup,
    email_sender: EmailSender,
    today: date | None = None,
) -> IssuedSession:
    email = str(data.email).lower()
    _check_password(data.password, email)

    if isinstance(data, StudentSignup):
        # Age rules are checked before anything is stored.
        students.check_signup_age(data.date_of_birth, data.guardian_email, email, today)

    if await repo.email_exists(session, email):
        raise Conflict("An account with this email already exists.", code="email_taken")

    role = "student" if isinstance(data, StudentSignup) else "guardian"
    user = repo.add_user(
        session, email=email, password_hash=hash_password(data.password), role=role
    )
    invite_link: str | None = None
    if isinstance(data, StudentSignup):
        students.add_profile(session, user, data)
        if data.guardian_email:
            _, invite_link = students.add_guardian_invite(
                session, user.id, str(data.guardian_email)
            )
    try:
        await session.flush()
    except IntegrityError as exc:  # two signups with the same email at the same moment
        await session.rollback()
        raise Conflict("An account with this email already exists.", code="email_taken") from exc

    issued = await _issue_session(session, user)  # commits user, profile and invite together
    if isinstance(data, StudentSignup) and invite_link:
        await students.send_guardian_invite(
            email_sender, str(data.guardian_email), data.display_name, invite_link
        )
    return issued


async def login(session: AsyncSession, email: str, password: str) -> IssuedSession:
    settings = get_settings()
    user = await repo.get_user_by_email(session, email)
    now = _now()

    if user and user.locked_until and user.locked_until > now:
        raise TooManyRequests(
            "Too many wrong passwords. Try again in a few minutes.", code="account_locked"
        )

    # verify_password also runs when the user is unknown, so timing does not reveal accounts.
    if not verify_password(password, user.password_hash if user else None) or user is None:
        if user is not None:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.max_failed_logins:
                user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
                user.failed_login_count = 0
            await session.commit()
        raise Unauthorized(INVALID_LOGIN, code="invalid_credentials")

    if not user.is_active:
        raise Forbidden("This account is disabled.", code="account_disabled")

    user.failed_login_count = 0
    user.locked_until = None
    return await _issue_session(session, user)


async def refresh(session: AsyncSession, refresh_token: str | None) -> IssuedSession:
    """Swap a refresh token for a new pair. Each refresh token works only once."""
    data = decode_token(refresh_token, "refresh") if refresh_token else None
    if data is None:
        raise Unauthorized(code="session_expired")

    stored = await repo.get_refresh_token(session, data.jti)
    now = _now()
    if stored is None or stored.user_id != data.user_id:
        raise Unauthorized(code="session_expired")
    if stored.revoked_at is not None:
        # A used token came back: it may have been stolen. End every session of this user.
        await repo.revoke_all_refresh_tokens(session, stored.user_id, now)
        await session.commit()
        raise Unauthorized("Please log in again.", code="session_revoked")
    if stored.expires_at <= now:
        raise Unauthorized(code="session_expired")

    user = await repo.get_user_by_id(session, stored.user_id)
    if user is None or not user.is_active:
        raise Unauthorized(code="session_expired")

    stored.revoked_at = now
    return await _issue_session(session, user)


async def logout(session: AsyncSession, refresh_token: str | None) -> None:
    data = decode_token(refresh_token, "refresh") if refresh_token else None
    if data is None:
        return
    stored = await repo.get_refresh_token(session, data.jti)
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = _now()
        await session.commit()


async def get_active_user(session: AsyncSession, access_token: str | None) -> User:
    data = decode_token(access_token, "access") if access_token else None
    if data is None:
        raise Unauthorized()
    user = await repo.get_user_by_id(session, data.user_id)
    if user is None or not user.is_active:
        raise Unauthorized()
    return user
