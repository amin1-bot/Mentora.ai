"""Creates the FastAPI app and registers routers.

Run locally (from the backend folder):  uvicorn app.main:app --reload
Then open http://127.0.0.1:8000/docs
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.database import SessionDep, engine
from app.core.errors import register_error_handlers
from app.core.storage import get_storage
from app.modules.auth.router import router as auth_router
from app.modules.classroom.router import router as classroom_router
from app.modules.curriculum.router import router as curriculum_router
from app.modules.documents.router import router as documents_router
from app.modules.jobs.worker import run_forever
from app.modules.progress.router import router as progress_router
from app.modules.students.router import guardians_router, students_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    stop = asyncio.Event()
    worker = None
    # Local development: background jobs (reading uploaded PDFs) run inside the API.
    # Tests run jobs themselves; production runs `python -m app.modules.jobs.worker`.
    if settings.job_worker_in_api and settings.environment != "test":
        worker = asyncio.create_task(run_forever(get_storage(), stop, settings.job_poll_seconds))
    yield
    if worker is not None:
        stop.set()
        try:
            await asyncio.wait_for(worker, timeout=10)
        except TimeoutError:
            worker.cancel()
    # Close pooled database connections cleanly when the server stops.
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Backend for Mentora, an AI personal teacher.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    api = APIRouter(prefix=settings.api_prefix)

    @api.get("/hello", tags=["system"])
    def hello() -> dict[str, str]:
        """First endpoint: proves the app runs."""
        return {"message": "Hello from Mentora"}

    @api.get("/health", tags=["system"])
    async def health(response: Response, session: SessionDep) -> dict[str, str]:
        """Used by uptime checks and the deploy pipeline. Returns 503 if the database is down."""
        try:
            await session.execute(text("SELECT 1"))
            database = "ok"
        except (SQLAlchemyError, OSError):
            logger.exception("Health check: database unreachable")
            database = "unavailable"
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "ok" if database == "ok" else "degraded",
            "database": database,
            "environment": settings.environment,
        }

    # Feature module routers. Add new modules here as they are built.
    api.include_router(auth_router)
    api.include_router(students_router)
    api.include_router(guardians_router)
    api.include_router(curriculum_router)
    api.include_router(classroom_router)
    api.include_router(progress_router)
    api.include_router(documents_router)

    app.include_router(api)
    register_error_handlers(app)
    return app


app = create_app()
