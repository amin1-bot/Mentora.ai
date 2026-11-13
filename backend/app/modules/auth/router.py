from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request, Response, status

from app.core.config import get_settings
from app.core.database import SessionDep
from app.core.email import EmailSender, get_email_sender
from app.core.rate_limit import limit_auth_attempts
from app.core.security import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE
from app.modules.auth import service
from app.modules.auth.dependencies import CurrentUser, require_csrf
from app.modules.auth.schemas import AuthResponse, LoginRequest, SignupRequest, UserOut
from app.modules.students import service as students

router = APIRouter(prefix="/auth", tags=["auth"])


def _refresh_path() -> str:
    return f"{get_settings().api_prefix}/auth"


def _set_session_cookies(response: Response, issued: service.IssuedSession) -> None:
    settings = get_settings()
    common = {"secure": True, "httponly": True}
    response.set_cookie(
        ACCESS_COOKIE, issued.access_token, max_age=settings.access_token_minutes * 60,
        path="/", samesite="lax", **common,
    )
    response.set_cookie(
        REFRESH_COOKIE, issued.refresh_token, max_age=settings.refresh_token_days * 86400,
        path=_refresh_path(), samesite="strict", **common,
    )
    # Readable by the frontend on purpose: it copies this into the X-CSRF-Token header.
    response.set_cookie(
        CSRF_COOKIE, issued.csrf_token, max_age=settings.refresh_token_days * 86400,
        path="/", samesite="strict", secure=True, httponly=False,
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/", secure=True, httponly=True)
    response.delete_cookie(REFRESH_COOKIE, path=_refresh_path(), secure=True, httponly=True)
    response.delete_cookie(CSRF_COOKIE, path="/", secure=True)


async def _auth_response(session: SessionDep, issued: service.IssuedSession) -> AuthResponse:
    consent = None
    if issued.user.role == "student":
        consent = await students.consent_status(session, issued.user.id)
    return AuthResponse(user=UserOut.model_validate(issued.user), consent_status=consent)


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_auth_attempts)],
)
async def signup(
    data: Annotated[SignupRequest, Body()],
    response: Response,
    session: SessionDep,
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> AuthResponse:
    """Create a student or guardian account and log in.

    Students must be at least 13. Students under 18 must give a guardian email; the
    guardian receives a link to approve the account.
    """
    issued = await service.signup(session, data, email_sender)
    _set_session_cookies(response, issued)
    return await _auth_response(session, issued)


@router.post("/login", dependencies=[Depends(limit_auth_attempts)])
async def login(data: LoginRequest, response: Response, session: SessionDep) -> AuthResponse:
    issued = await service.login(session, str(data.email), data.password)
    _set_session_cookies(response, issued)
    return await _auth_response(session, issued)


@router.post("/refresh", dependencies=[Depends(require_csrf)])
async def refresh(request: Request, response: Response, session: SessionDep) -> AuthResponse:
    """Call when a request returns 401: swaps the refresh cookie for new cookies."""
    issued = await service.refresh(session, request.cookies.get(REFRESH_COOKIE))
    _set_session_cookies(response, issued)
    return await _auth_response(session, issued)


@router.get("/me")
async def me(user: CurrentUser, session: SessionDep) -> AuthResponse:
    """Who is logged in. The frontend calls this on page load."""
    consent = None
    if user.role == "student":
        consent = await students.consent_status(session, user.id)
    return AuthResponse(user=UserOut.model_validate(user), consent_status=consent)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, session: SessionDep) -> None:
    await service.logout(session, request.cookies.get(REFRESH_COOKIE))
    _clear_session_cookies(response)
