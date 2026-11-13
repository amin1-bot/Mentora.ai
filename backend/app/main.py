"""Creates the FastAPI app and registers routers.

Run locally (from the backend folder):  uvicorn app.main:app --reload
Then open http://127.0.0.1:8000/docs
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.database import SessionDep, engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
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
        allow_headers=["*"],
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

    # Feature module routers (auth, students, classroom, ...) are registered here as they are built.
    app.include_router(api)
    return app


app = create_app()
