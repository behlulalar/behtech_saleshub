"""Faz 2 — priorities owner-only smoke (DB required)."""

import pytest
from fastapi.testclient import TestClient

from auth import create_access_token
from config import settings
from database import SessionLocal, User
from main import app


@pytest.fixture
def client():
    return TestClient(app)


def _token_for_role(role: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.role == role).first()
        if not user:
            pytest.skip(f"No {role} user")
        token, _ = create_access_token(user.id, user.username, token_version=user.token_version or 0)
        return token
    finally:
        db.close()


def test_priorities_requires_owner(client):
    prev = settings.ai_enabled
    settings.ai_enabled = True
    try:
        employee = _token_for_role("employee")
        res = client.post(
            "/api/ai/priorities",
            json={"limit": 5},
            headers={"Authorization": f"Bearer {employee}"},
        )
        assert res.status_code == 403
    finally:
        settings.ai_enabled = prev
