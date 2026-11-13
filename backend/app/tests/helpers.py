"""Shared helpers for API tests. Imported after conftest has pointed the app at the test DB."""

import asyncio
import os
from datetime import date
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.security import CSRF_COOKIE, CSRF_HEADER
from app.main import app

PASSWORD = "correct-horse-battery"


def years_ago(years: int) -> date:
    """A birth date that makes someone exactly `years` old today (born on 1 January)."""
    return date(date.today().year - years, 1, 1)


def new_client() -> TestClient:
    # https, because the login cookies are Secure and only sent over HTTPS.
    return TestClient(app, base_url="https://testserver")


def with_csrf(client: TestClient) -> dict[str, str]:
    return {CSRF_HEADER: client.cookies.get(CSRF_COOKIE) or ""}


def signup_student(
    client: TestClient,
    email: str,
    *,
    age: int = 15,
    guardian_email: str | None = "parent@example.com",
    name: str = "Ada",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "account_type": "student",
            "email": email,
            "password": PASSWORD,
            "display_name": name,
            "date_of_birth": years_ago(age).isoformat(),
            "grade_level": 9,
            "guardian_email": guardian_email,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def signup_guardian(client: TestClient, email: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/signup",
        json={"account_type": "guardian", "email": email, "password": PASSWORD},
    )
    assert response.status_code == 201, response.text
    return response.json()


def token_from_link(link: str | None) -> str:
    assert link and "#token=" in link
    return link.split("#token=", 1)[1]


def query(sql: str, **params: Any) -> list[tuple[Any, ...]]:
    """Run SQL against the test database and commit (to check or change stored data)."""

    async def run() -> list[tuple[Any, ...]]:
        engine = create_async_engine(os.environ["DATABASE_URL"])
        try:
            async with engine.begin() as conn:
                result = await conn.execute(text(sql), params)
                return [tuple(r) for r in result.all()] if result.returns_rows else []
        finally:
            await engine.dispose()

    return asyncio.run(run())
