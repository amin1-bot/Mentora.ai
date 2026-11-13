"""Passwords, login tokens and CSRF tokens.

- Passwords: Argon2id hashes only. The password itself is never stored or logged.
- Access token: short-lived JWT in an HttpOnly cookie, sent with every API request.
- Refresh token: longer-lived JWT in an HttpOnly cookie, sent only to /auth. Each one has
  an id (jti) stored in the database, so logout and theft detection can revoke it.
- CSRF: double-submit token. A readable cookie whose value the frontend copies into
  the X-CSRF-Token header on every POST, PATCH or DELETE.
"""

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

_hasher = PasswordHasher()  # Argon2id with the library's recommended parameters
# Verified against when the email is unknown, so both cases take the same time.
_DUMMY_HASH = _hasher.hash("not-a-real-password-used-for-timing-only")

JWT_ALGORITHM = "HS256"
ACCESS_COOKIE = "mentora_access"
REFRESH_COOKIE = "mentora_refresh"
CSRF_COOKIE = "mentora_csrf"
CSRF_HEADER = "X-CSRF-Token"

TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def password_problem(password: str, email: str) -> str | None:
    """Return a message if the password is too weak, otherwise None."""
    if len(password) < 10:
        return "Use at least 10 characters."
    if len(password) > 128:
        return "Use at most 128 characters."
    if len(set(password)) < 4:
        return "Use a mix of different characters."
    local_part = email.split("@", 1)[0].lower()
    if len(local_part) >= 4 and local_part in password.lower():
        return "Do not include your email address in your password."
    return None


@dataclass(frozen=True)
class TokenData:
    user_id: uuid.UUID
    role: str
    token_type: TokenType
    jti: uuid.UUID
    expires_at: datetime


def create_token(
    user_id: uuid.UUID, role: str, token_type: TokenType
) -> tuple[str, TokenData]:
    settings = get_settings()
    lifetime = (
        timedelta(minutes=settings.access_token_minutes)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_days)
    )
    now = datetime.now(UTC)
    data = TokenData(user_id, role, token_type, uuid.uuid4(), now + lifetime)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "jti": str(data.jti),
        "iat": now,
        "exp": data.expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM), data


def decode_token(token: str, expected_type: TokenType) -> TokenData | None:
    """Return the token's data, or None if it is invalid, expired or the wrong type."""
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "type", "jti", "exp"]},
        )
        if payload["type"] != expected_type:
            return None
        return TokenData(
            user_id=uuid.UUID(payload["sub"]),
            role=str(payload.get("role", "")),
            token_type=expected_type,
            jti=uuid.UUID(payload["jti"]),
            expires_at=datetime.fromtimestamp(payload["exp"], UTC),
        )
    except (jwt.PyJWTError, ValueError, KeyError):
        return None


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_matches(cookie_value: str | None, header_value: str | None) -> bool:
    if not cookie_value or not header_value:
        return False
    return hmac.compare_digest(cookie_value, header_value)


def new_url_token() -> tuple[str, str]:
    """A random token for emailed links. Returns (token for the link, hash to store)."""
    token = secrets.token_urlsafe(32)
    return token, hash_url_token(token)


def hash_url_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
