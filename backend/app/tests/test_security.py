"""Unit tests: passwords, tokens, CSRF and age rules. No database needed."""

import uuid
from datetime import date

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import (
    JWT_ALGORITHM,
    create_token,
    csrf_matches,
    decode_token,
    hash_password,
    password_problem,
    verify_password,
)
from app.modules.students.service import age_on


def test_password_is_hashed_with_argon2id() -> None:
    hashed = hash_password("correct-horse-battery")
    assert hashed.startswith("$argon2id$")
    assert "correct-horse-battery" not in hashed
    assert verify_password("correct-horse-battery", hashed)
    assert not verify_password("wrong-password-here", hashed)


def test_unknown_user_never_verifies() -> None:
    assert not verify_password("anything-at-all", None)


@pytest.mark.parametrize(
    ("password", "ok"),
    [
        ("short", False),
        ("aaaaaaaaaaaa", False),  # too few different characters
        ("ada.lovelace-2026", False),  # contains the email name
        ("x" * 129, False),
        ("correct-horse-battery", True),
    ],
)
def test_password_rules(password: str, ok: bool) -> None:
    assert (password_problem(password, "ada.lovelace@example.com") is None) is ok


def test_token_round_trip() -> None:
    user_id = uuid.uuid4()
    token, data = create_token(user_id, "student", "access")
    decoded = decode_token(token, "access")
    assert decoded is not None
    assert decoded.user_id == user_id
    assert decoded.jti == data.jti


def test_refresh_token_is_not_accepted_as_access_token() -> None:
    token, _ = create_token(uuid.uuid4(), "student", "refresh")
    assert decode_token(token, "access") is None


def test_forged_token_is_rejected() -> None:
    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "access", "jti": str(uuid.uuid4()), "exp": 9999999999},
        "some-other-secret-that-is-long-enough-to-use",
        algorithm=JWT_ALGORITHM,
    )
    assert decode_token(forged, "access") is None


def test_expired_token_is_rejected() -> None:
    expired = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "access", "jti": str(uuid.uuid4()), "exp": 1},
        get_settings().jwt_secret,
        algorithm=JWT_ALGORITHM,
    )
    assert decode_token(expired, "access") is None


def test_csrf_tokens_must_match() -> None:
    assert csrf_matches("abc123", "abc123")
    assert not csrf_matches("abc123", "abc124")
    assert not csrf_matches("abc123", None)
    assert not csrf_matches(None, None)


@pytest.mark.parametrize(
    ("born", "today", "age"),
    [
        (date(2013, 11, 13), date(2026, 11, 13), 13),  # birthday today
        (date(2013, 11, 14), date(2026, 11, 13), 12),  # birthday tomorrow
        (date(2008, 2, 29), date(2026, 2, 28), 17),  # leap-day birthday
        (date(2008, 2, 29), date(2026, 3, 1), 18),
    ],
)
def test_age_on(born: date, today: date, age: int) -> None:
    assert age_on(born, today) == age
