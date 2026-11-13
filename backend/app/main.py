"""Creates the FastAPI app and registers routers.

Run locally (from the backend folder):  uvicorn app.main:app --reload
Then open http://127.0.0.1:8000/docs
"""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Backend for Mentora, an AI personal teacher.",
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
    def health() -> dict[str, str]:
        """Used by uptime checks and the deploy pipeline. Database check is added in Phase 2b."""
        return {"status": "ok", "environment": settings.environment}

    # Feature module routers (auth, students, classroom, ...) are registered here as they are built.
    app.include_router(api)
    return app


app = create_app()
