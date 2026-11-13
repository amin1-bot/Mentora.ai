from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_hello() -> None:
    response = client.get("/api/v1/hello")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello from Mentora"}


def test_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_docs_page_is_served() -> None:
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()
