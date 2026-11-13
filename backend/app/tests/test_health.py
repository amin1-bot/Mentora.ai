from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.database import get_session
from app.main import app


def test_hello() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/hello")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello from Mentora"}


def test_health_with_database() -> None:
    """Needs the Docker database running: docker compose up -d"""
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


def test_health_reports_database_down() -> None:
    class BrokenSession:
        async def execute(self, *args: object, **kwargs: object) -> None:
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    async def broken_session():  # type: ignore[no-untyped-def]
        yield BrokenSession()

    app.dependency_overrides[get_session] = broken_session
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/health")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "database": "unavailable",
        "environment": "local",
    }


def test_docs_page_is_served() -> None:
    with TestClient(app) as client:
        response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()
