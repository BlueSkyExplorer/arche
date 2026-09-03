from fastapi.testclient import TestClient

from app.main import app


def test_health_does_not_require_auth() -> None:
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_workspace_me_requires_bearer_token() -> None:
    response = TestClient(app).get("/api/v1/workspaces/me")
    assert response.status_code == 401
