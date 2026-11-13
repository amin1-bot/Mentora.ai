"""Sending email (guardian consent invitations for now).

There is no real email provider yet. Locally, LocalOutbox keeps sent emails in memory and
prints the link to the server console, so you can click it while developing. It is
refused in staging and production: a real provider must be added before then.
"""

import logging
from dataclasses import dataclass
from typing import Protocol

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    body: str
    link: str | None = None


class EmailSender(Protocol):
    async def send(self, email: Email) -> None: ...


class LocalOutbox:
    """DEVELOPMENT ONLY. Does not send anything."""

    def __init__(self) -> None:
        self.sent: list[Email] = []

    async def send(self, email: Email) -> None:
        self.sent.append(email)
        # The recipient address is deliberately not printed (personal data stays out of logs).
        print(f"[local outbox] '{email.subject}' -> link: {email.link}")  # noqa: T201


_outbox = LocalOutbox()


def get_email_sender() -> EmailSender:
    """FastAPI dependency. Swap in a real provider here before staging."""
    if get_settings().environment not in ("local", "test"):
        raise RuntimeError("No email provider configured for this environment")
    return _outbox
