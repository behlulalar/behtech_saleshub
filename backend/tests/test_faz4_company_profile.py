"""Faz 4 — company profile owner endpoint."""

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


def test_company_profile_owner(client, owner_token):
    response = client.get(
        "/api/intelligence/company-profile",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "computed_at" in data
    assert "total_leads" in data
