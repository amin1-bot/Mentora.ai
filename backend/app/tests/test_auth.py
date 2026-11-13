"""Signup, login, lockout, refresh and logout through the real API and test database."""

from fastapi.testclient import TestClient

from app.core.email import Email
from app.core.security import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE
from app.tests.helpers import (
    PASSWORD,
    new_client,
    query,
    signup_guardian,
    signup_student,
    with_csrf,
    years_ago,
)

SIGNUP = "/api/v1/auth/signup"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/students/me"


def _student_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "account_type": "student",
        "email": "ada@example.com",
        "password": PASSWORD,
        "display_name": "Ada",
        "date_of_birth": years_ago(15).isoformat(),
        "grade_level": 9,
        "guardian_email": "parent@example.com",
    }
    body.update(overrides)
    return body


# ---------- Signup ----------


def test_teen_signup_logs_in_and_emails_the_guardian(
    client: TestClient, outbox: list[Email]
) -> None:
    body = signup_student(client, "Ada@Example.com")
    assert body["user"]["email"] == "ada@example.com"  # stored lower-case
    assert body["user"]["role"] == "student"
    assert body["consent_status"] == "pending"

    assert len(outbox) == 1
    assert outbox[0].to == "parent@example.com"
    assert "#token=" in (outbox[0].link or "")

    me = client.get(ME)
    assert me.status_code == 200
    assert me.json()["display_name"] == "Ada"


def test_login_cookies_are_httponly_secure_and_samesite(client: TestClient) -> None:
    response = client.post(SIGNUP, json=_student_body())
    cookies = {c.split("=", 1)[0]: c for c in response.headers.get_list("set-cookie")}
    for name in (ACCESS_COOKIE, REFRESH_COOKIE):
        assert "HttpOnly" in cookies[name]
        assert "Secure" in cookies[name]
        assert "SameSite" in cookies[name]
    assert "Path=/api/v1/auth" in cookies[REFRESH_COOKIE]
    assert "HttpOnly" not in cookies[CSRF_COOKIE]  # the frontend must be able to read it


def test_password_is_stored_as_argon2id_hash(client: TestClient) -> None:
    signup_student(client, "ada@example.com")
    [(password_hash,)] = query("SELECT password_hash FROM users")
    assert password_hash.startswith("$argon2id$")
    assert PASSWORD not in password_hash


def test_adult_student_needs_no_guardian(client: TestClient, outbox: list[Email]) -> None:
    body = signup_student(client, "sam@example.com", age=18, guardian_email=None)
    assert body["consent_status"] == "not_required"
    assert outbox == []


def test_under_13_is_refused_and_nothing_is_stored(client: TestClient) -> None:
    response = client.post(SIGNUP, json=_student_body(date_of_birth=years_ago(12).isoformat()))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "age_below_minimum"
    assert query("SELECT count(*) FROM users") == [(0,)]


def test_teen_without_guardian_email_is_refused(client: TestClient) -> None:
    response = client.post(SIGNUP, json=_student_body(guardian_email=None))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "guardian_email_required"


def test_guardian_email_cannot_be_the_students_own(client: TestClient) -> None:
    response = client.post(SIGNUP, json=_student_body(guardian_email="ada@example.com"))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "guardian_email_same_as_student"


def test_weak_password_is_refused(client: TestClient) -> None:
    response = client.post(SIGNUP, json=_student_body(password="password"))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "weak_password"


def test_email_can_only_be_used_once_ignoring_case(client: TestClient) -> None:
    signup_student(client, "ada@example.com")
    with new_client() as other:
        response = other.post(SIGNUP, json=_student_body(email="ADA@example.com"))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


def test_validation_errors_use_the_standard_shape_without_echoing_input(
    client: TestClient,
) -> None:
    response = client.post(SIGNUP, json=_student_body(email="not-an-email", grade_level=99))
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert {d["field"] for d in error["details"]} >= {"student.email", "student.grade_level"}
    assert PASSWORD not in response.text


# ---------- Login ----------


def test_login_with_correct_password(client: TestClient) -> None:
    signup_student(client, "ada@example.com")
    with new_client() as fresh:
        response = fresh.post(LOGIN, json={"email": "ADA@example.com", "password": PASSWORD})
        assert response.status_code == 200
        assert response.json()["user"]["email"] == "ada@example.com"
        assert fresh.get(ME).status_code == 200


def test_wrong_password_and_unknown_email_look_the_same(client: TestClient) -> None:
    signup_student(client, "ada@example.com")
    wrong = client.post(LOGIN, json={"email": "ada@example.com", "password": "wrong-password-1"})
    unknown = client.post(LOGIN, json={"email": "nobody@example.com", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["error"]["code"] == "invalid_credentials"


def test_account_locks_after_five_wrong_passwords(client: TestClient) -> None:
    signup_student(client, "ada@example.com")
    for _ in range(5):
        client.post(LOGIN, json={"email": "ada@example.com", "password": "wrong-password-1"})
    # Even the right password is refused while locked.
    response = client.post(LOGIN, json={"email": "ada@example.com", "password": PASSWORD})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "account_locked"


def test_login_is_rate_limited_per_ip(client: TestClient) -> None:
    for _ in range(10):
        client.post(LOGIN, json={"email": "nobody@example.com", "password": PASSWORD})
    response = client.post(LOGIN, json={"email": "nobody@example.com", "password": PASSWORD})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "too_many_requests"


def test_guardian_signup(client: TestClient) -> None:
    body = signup_guardian(client, "parent@example.com")
    assert body["user"]["role"] == "guardian"
    assert body["consent_status"] is None


def test_auth_me_reports_who_is_logged_in(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401
    signup_student(client, "ada@example.com")
    body = client.get("/api/v1/auth/me").json()
    assert body["user"]["email"] == "ada@example.com"
    assert body["consent_status"] == "pending"


# ---------- Protected routes, refresh, logout ----------


def test_protected_route_needs_login(client: TestClient) -> None:
    response = client.get(ME)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_refresh_needs_the_csrf_header(client: TestClient) -> None:
    signup_student(client, "ada@example.com")
    response = client.post(REFRESH)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_refresh_rotates_tokens_and_detects_reuse(client: TestClient) -> None:
    signup_student(client, "ada@example.com")
    first_refresh = client.cookies.get(REFRESH_COOKIE)

    response = client.post(REFRESH, headers=with_csrf(client))
    assert response.status_code == 200
    second_refresh = client.cookies.get(REFRESH_COOKIE)
    assert second_refresh and second_refresh != first_refresh

    # Someone replays the old (already used) refresh token...
    with new_client() as attacker:
        attacker.cookies.set(REFRESH_COOKIE, first_refresh or "", path="/api/v1/auth")
        attacker.cookies.set(CSRF_COOKIE, "x")
        stolen = attacker.post(REFRESH, headers={"X-CSRF-Token": "x"})
    assert stolen.status_code == 401
    assert stolen.json()["error"]["code"] == "session_revoked"

    # ...so every session of that user is ended, including the real one.
    assert client.post(REFRESH, headers=with_csrf(client)).status_code == 401


def test_logout_revokes_the_refresh_token(client: TestClient) -> None:
    signup_student(client, "ada@example.com")
    old_refresh = client.cookies.get(REFRESH_COOKIE) or ""
    assert client.post(LOGOUT).status_code == 204
    assert client.get(ME).status_code == 401  # cookies cleared

    with new_client() as replay:
        replay.cookies.set(REFRESH_COOKIE, old_refresh, path="/api/v1/auth")
        replay.cookies.set(CSRF_COOKIE, "x")
        assert replay.post(REFRESH, headers={"X-CSRF-Token": "x"}).status_code == 401


def test_disabled_account_cannot_use_its_token(client: TestClient) -> None:
    signup_student(client, "ada@example.com")
    query("UPDATE users SET is_active = false")
    assert client.get(ME).status_code == 401
