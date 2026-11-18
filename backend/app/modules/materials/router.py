import uuid

from fastapi import APIRouter, Depends, Response, status

from app.core.database import SessionDep
from app.modules.auth.dependencies import StudentUser, require_csrf
from app.modules.materials import service
from app.modules.materials.schemas import (
    MaterialCreate,
    MaterialOut,
    MaterialRename,
    MaterialSummaryOut,
    ReviewIn,
    ReviewOut,
    ReviewResult,
)

router = APIRouter(tags=["materials"])


@router.post(
    "/documents/{document_id}/materials",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_csrf)],
)
async def create_material(
    document_id: uuid.UUID, data: MaterialCreate, student: StudentUser, session: SessionDep
) -> MaterialSummaryOut:
    """Ask for a summary, study guide or flashcards. Written in the background."""
    return await service.create(session, student, document_id, data)


@router.get("/documents/{document_id}/materials")
async def list_materials(
    document_id: uuid.UUID, student: StudentUser, session: SessionDep
) -> list[MaterialSummaryOut]:
    return await service.list_for_document(session, student, document_id)


@router.get("/materials/{material_id}")
async def get_material(
    material_id: uuid.UUID, student: StudentUser, session: SessionDep
) -> MaterialOut:
    return await service.get(session, student, material_id)


@router.patch("/materials/{material_id}", dependencies=[Depends(require_csrf)])
async def rename_material(
    material_id: uuid.UUID, data: MaterialRename, student: StudentUser, session: SessionDep
) -> MaterialOut:
    return await service.rename(session, student, material_id, data.title)


@router.delete(
    "/materials/{material_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_material(
    material_id: uuid.UUID, student: StudentUser, session: SessionDep
) -> Response:
    await service.delete(session, student, material_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/materials/{material_id}/review")
async def review_session(
    material_id: uuid.UUID, student: StudentUser, session: SessionDep
) -> ReviewOut:
    """Flashcards due now: earlier cards whose time has come, then up to 20 new ones."""
    return await service.review_session(session, student, material_id)


@router.post("/materials/{material_id}/cards/{index}/review", dependencies=[Depends(require_csrf)])
async def review_card(
    material_id: uuid.UUID, index: int, data: ReviewIn, student: StudentUser, session: SessionDep
) -> ReviewResult:
    """Rate one card (again, hard, good, easy); it comes back on the spaced schedule."""
    return await service.review(session, student, material_id, index, data)
