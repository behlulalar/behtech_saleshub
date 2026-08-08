"""Faz 5 — sales chat endpoint flags."""

import pytest
from fastapi.testclient import TestClient

from auth import create_access_token
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


def test_ai_status_includes_chat_available(client, owner_token):
    response = client.get("/api/ai/status", headers={"Authorization": f"Bearer {owner_token}"})
    assert response.status_code == 200
    data = response.json()
    assert "chat_available" in data
    assert isinstance(data["chat_available"], bool)


def test_chat_disabled_by_default(client, owner_token):
    response = client.post(
        "/api/ai/chat",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"message": "Merhaba", "locale": "tr"},
    )
    assert response.status_code == 403
