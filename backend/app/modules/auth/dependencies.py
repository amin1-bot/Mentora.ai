"""FastAPI dependencies other modules use to require a logged-in user."""

from typing import Annotated

from fastapi import Depends, Request

from app.core.database import SessionDep
from app.core.errors import Forbidden
from app.core.security import ACCESS_COOKIE, CSRF_COOKIE, CSRF_HEADER, csrf_matches
from app.modules.auth import service
from app.modules.auth.models import User


async def get_current_user(request: Request, session: SessionDep) -> User:
    return await service.get_active_user(session, request.cookies.get(ACCESS_COOKIE))


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: str):  # noqa: ANN201
    async def _check(user: CurrentUser) -> User:
        if user.role not in roles:
            raise Forbidden()
        return user

    return _check


StudentUser = Annotated[User, Depends(require_role("student"))]
GuardianUser = Annotated[User, Depends(require_role("guardian"))]


def require_csrf(request: Request) -> None:
    """Add to every POST, PATCH and DELETE route that uses the login cookies."""
    if not csrf_matches(request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER)):
        raise Forbidden("Missing or invalid CSRF token.", code="csrf_failed")
