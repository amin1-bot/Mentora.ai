from fastapi import APIRouter

from app.core.database import SessionDep
from app.modules.auth.dependencies import StudentUser
from app.modules.progress import service
from app.modules.progress.service import ProgressOut

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("")
async def my_progress(student: StudentUser, session: SessionDep) -> ProgressOut:
    """Your mastery for every skill, grouped by topic area, and what to practise next."""
    return await service.progress_for(session, student)
