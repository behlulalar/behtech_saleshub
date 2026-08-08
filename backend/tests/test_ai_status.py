import pytest
from fastapi.testclient import TestClient

from auth import create_access_token
from config import settings
from database import SessionLocal, User
from main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def owner_token():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.role == "owner").first()
        if not user:
            pytest.skip("No owner user in database")
        token, _ = create_access_token(user.id, user.username, token_version=user.token_version or 0)
        return token
    finally:
        db.close()


def test_ai_status_requires_auth(client):
    response = client.get("/api/ai/status")
    assert response.status_code == 401


def test_ai_status_disabled(client, owner_token):
    prev = settings.ai_enabled
    settings.ai_enabled = False
    try:
        response = client.get("/api/ai/status", headers={"Authorization": f"Bearer {owner_token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["suggest_message_available"] is False
    finally:
        settings.ai_enabled = prev


def test_health_includes_ai_flag(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert "ai_enabled" in response.json()
