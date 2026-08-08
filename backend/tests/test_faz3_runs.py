"""Faz 3 — AI runs and tools."""

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


def test_ai_runs_batch_score_requires_owner(client):
    db = SessionLocal()
    try:
        emp = db.query(User).filter(User.role == "employee").first()
        if not emp:
            pytest.skip("No employee user")
        token, _ = create_access_token(emp.id, emp.username, token_version=emp.token_version or 0)
    finally:
        db.close()

    prev = settings.ai_enabled
    settings.ai_enabled = True
    try:
        response = client.post(
            "/api/ai/runs",
            json={"run_type": "batch_score"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
    finally:
        settings.ai_enabled = prev


def test_ai_runs_batch_score_owner(client, owner_token):
    prev = settings.ai_enabled
    settings.ai_enabled = True
    try:
        response = client.post(
            "/api/ai/runs",
            json={"run_type": "batch_score"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["run_type"] == "batch_score"
        assert data["status"] in ("done", "queued", "running", "failed")
        run_id = data["run_id"]
        detail = client.get(
            f"/api/ai/runs/{run_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert detail.status_code == 200
        assert detail.json()["id"] == run_id
    finally:
        settings.ai_enabled = prev
