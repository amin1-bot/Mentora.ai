"""Who may upload documents. The one place to change when younger students get access.

Today: students aged `documents_min_age` (18) or older. Reading, downloading and deleting
your own documents is always allowed, even if the rules later become stricter, so nobody
is ever locked out of removing their own files.

Planned (not built): a student under 18 may upload when a linked guardian has turned on
document uploads for them. That needs a permission on the guardian link and a privacy
review of uploads by minors (KVKK, GDPR, COPPA); this function is where it plugs in.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.auth.models import User
from app.modules.students import service as students


@dataclass(frozen=True)
class UploadAccess:
    allowed: bool
    code: str | None = None  # why not, for the API error and the UI
    message: str | None = None


async def upload_access(db: AsyncSession, user: User) -> UploadAccess:
    if user.role != "student":
        return UploadAccess(False, "documents_students_only", "Only student accounts can upload.")
    profile = await students.get_profile(db, user, user.id)
    min_age = get_settings().documents_min_age
    if students.age_on(profile.date_of_birth, datetime.now(UTC).date()) < min_age:
        return UploadAccess(
            False,
            "documents_age_restricted",
            f"Uploading your own documents is available from age {min_age} for now. "
            "We are working on a safe way for younger students, with a parent's permission.",
        )
    return UploadAccess(True)
