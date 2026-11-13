"""Who may see a student's data, profile updates, and the guardian consent flow.

The first test is the Phase 3 gate from the blueprint: a student provably cannot read
another student's data.
"""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.email import Email
from app.tests.helpers import (
    new_client,
    query,
    signup_guardian,
    signup_student,
    token_from_link,
    with_csrf,
)

INVITE = "/api/v1/guardians/invite"
INVITE_INFO = "/api/v1/guardians/invite-info"
CONSENT = "/api/v1/guardians/consent"


def _student(path_id: str) -> str:
    return f"/api/v1/students/{path_id}"


def _consent(client: TestClient, token: str, **overrides: object) -> object:
    body = {
        "token": token,
        "confirm_is_guardian": True,
        "consent_version": get_settings().consent_version,
    }
    body.update(overrides)
    return client.post(CONSENT, json=body, headers=with_csrf(client))


# ---------- The Phase 3 gate ----------


def test_student_cannot_read_another_students_data() -> None:
    with new_client() as alice, new_client() as bob:
        alice_id = signup_student(alice, "alice@example.com", name="Alice")["user"]["id"]
        bob_id = signup_student(bob, "bob@example.com", name="Bob")["user"]["id"]

        # Each student sees only themselves through /me.
        assert alice.get("/api/v1/students/me").json()["user_id"] == alice_id
        assert bob.get("/api/v1/students/me").json()["user_id"] == bob_id

        # Reading your own profile by id works...
        assert alice.get(_student(alice_id)).status_code == 200

        # ...reading someone else's is refused, in both directions.
        for client, other_id in ((alice, bob_id), (bob, alice_id)):
            response = client.get(_student(other_id))
            assert response.status_code == 403
            assert response.json()["error"]["code"] == "forbidden"
            assert "Alice" not in response.text and "Bob" not in response.text


def test_unknown_student_id_is_also_forbidden(client: TestClient) -> None:
    signup_student(client, "alice@example.com")
    response = client.get(_student("00000000-0000-0000-0000-000000000000"))
    assert response.status_code == 403  # does not reveal whether the id exists


# ---------- Profile ----------


def test_student_updates_own_profile_but_not_birth_date(client: TestClient) -> None:
    before = signup_student(client, "alice@example.com", name="Alice")
    original_dob = client.get("/api/v1/students/me").json()["date_of_birth"]

    response = client.patch(
        "/api/v1/students/me",
        json={"display_name": "  Ally ", "grade_level": 10, "date_of_birth": "2000-01-01"},
        headers=with_csrf(client),
    )
    assert response.status_code == 200, response.text
    profile = response.json()
    assert profile["display_name"] == "Ally"
    assert profile["grade_level"] == 10
    assert profile["date_of_birth"] == original_dob
    assert profile["user_id"] == before["user"]["id"]


def test_profile_update_needs_csrf_header(client: TestClient) -> None:
    signup_student(client, "alice@example.com")
    response = client.patch("/api/v1/students/me", json={"grade_level": 10})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_guardian_has_no_student_profile_route(client: TestClient) -> None:
    signup_guardian(client, "parent@example.com")
    assert client.get("/api/v1/students/me").status_code == 403


# ---------- Guardian consent ----------


def test_full_guardian_consent_flow(outbox: list[Email]) -> None:
    with new_client() as alice, new_client() as parent, new_client() as bob:
        alice_id = signup_student(alice, "alice@example.com", name="Alice")["user"]["id"]
        bob_id = signup_student(bob, "bob@example.com", guardian_email="other@example.com")[
            "user"
        ]["id"]
        token = token_from_link(outbox[0].link)

        signup_guardian(parent, "Parent@example.com")

        # Before approving, the guardian cannot see the student.
        assert parent.get(_student(alice_id)).status_code == 403

        info = parent.post(INVITE_INFO, json={"token": token})
        assert info.status_code == 200
        assert info.json()["student_display_name"] == "Alice"

        response = _consent(parent, token)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "approved"

        # The student's account is now approved...
        assert alice.get("/api/v1/students/me").json()["consent_status"] == "approved"
        # ...the guardian can see their teen, and the access is audited...
        assert parent.get(_student(alice_id)).status_code == 200
        actions = {r[0] for r in query("SELECT action FROM audit_log")}
        assert {"consent_given", "read"} <= actions
        # ...but still not a student they are not linked to.
        assert parent.get(_student(bob_id)).status_code == 403


def test_consent_needs_the_invited_email(outbox: list[Email]) -> None:
    with new_client() as alice, new_client() as stranger:
        signup_student(alice, "alice@example.com")
        token = token_from_link(outbox[0].link)
        signup_guardian(stranger, "stranger@example.com")
        response = _consent(stranger, token)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "invite_email_mismatch"


def test_consent_link_works_only_once(outbox: list[Email]) -> None:
    with new_client() as alice, new_client() as parent:
        signup_student(alice, "alice@example.com")
        token = token_from_link(outbox[0].link)
        signup_guardian(parent, "parent@example.com")
        assert _consent(parent, token).status_code == 200
        again = _consent(parent, token)
        assert again.status_code == 404
        assert again.json()["error"]["code"] == "invite_invalid"


def test_consent_requires_the_current_consent_text(outbox: list[Email]) -> None:
    with new_client() as alice, new_client() as parent:
        signup_student(alice, "alice@example.com")
        token = token_from_link(outbox[0].link)
        signup_guardian(parent, "parent@example.com")
        response = _consent(parent, token, consent_version="2020-old")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "consent_version_outdated"


def test_consent_requires_confirming_guardianship(outbox: list[Email]) -> None:
    with new_client() as alice, new_client() as parent:
        signup_student(alice, "alice@example.com")
        token = token_from_link(outbox[0].link)
        signup_guardian(parent, "parent@example.com")
        assert _consent(parent, token, confirm_is_guardian=False).status_code == 422


def test_expired_invite_is_refused(outbox: list[Email]) -> None:
    with new_client() as alice, new_client() as parent:
        signup_student(alice, "alice@example.com")
        token = token_from_link(outbox[0].link)
        query("UPDATE guardian_invites SET expires_at = now() - interval '1 minute'")
        signup_guardian(parent, "parent@example.com")
        assert _consent(parent, token).status_code == 404


def test_students_cannot_give_consent(outbox: list[Email]) -> None:
    with new_client() as alice:
        signup_student(alice, "alice@example.com")
        token = token_from_link(outbox[0].link)
        assert _consent(alice, token).status_code == 403


def test_resending_the_invite_cancels_the_old_link(outbox: list[Email]) -> None:
    with new_client() as alice, new_client() as parent:
        signup_student(alice, "alice@example.com", guardian_email="typo@example.com")
        old_token = token_from_link(outbox[0].link)

        response = alice.post(
            INVITE, json={"guardian_email": "parent@example.com"}, headers=with_csrf(alice)
        )
        assert response.status_code == 201
        assert len(outbox) == 2 and outbox[1].to == "parent@example.com"
        new_token = token_from_link(outbox[1].link)

        assert parent.post(INVITE_INFO, json={"token": old_token}).status_code == 404
        signup_guardian(parent, "parent@example.com")
        assert _consent(parent, new_token).status_code == 200


def test_only_token_hashes_are_stored(outbox: list[Email]) -> None:
    with new_client() as alice:
        signup_student(alice, "alice@example.com")
        token = token_from_link(outbox[0].link)
        stored = [r[0] for r in query("SELECT token_hash FROM guardian_invites")]
        assert stored and token not in stored
