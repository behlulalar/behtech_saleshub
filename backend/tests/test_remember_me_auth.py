"""Remember-me: HttpOnly refresh cookie sessions (no password in browser)."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from config import settings
from database import RefreshSession, SessionLocal, User, init_db
from main import app
from refresh_sessions import REFRESH_COOKIE_NAME
from security import hash_password


@pytest.fixture(scope="module", autouse=True)
def _ensure_refresh_table():
    init_db()


@pytest.fixture
def client():
    return TestClient(app)


def _ensure_owner(db, username: str = "remember_me_test_user") -> User:
    user = db.query(User).filter(User.username == username).first()
    if user:
        return user
    user = User(
        username=username,
        email=f"{username}@example.test",
        password_hash=hash_password("TestPass123!"),
        role="owner",
        account_type="company",
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_remember_me_off_no_refresh_cookie(client):
    db = SessionLocal()
    try:
        user = _ensure_owner(db)
        password = "TestPass123!"
    finally:
        db.close()

    r = client.post(
        "/api/auth/login",
        json={"username": user.username, "password": password, "remember_me": False},
    )
    assert r.status_code == 200
    refresh = client.post("/api/auth/refresh")
    assert refresh.status_code == 401


def test_remember_me_on_sets_httponly_cookie(client):
    db = SessionLocal()
    try:
        user = _ensure_owner(db)
        password = "TestPass123!"
    finally:
        db.close()

    r = client.post(
        "/api/auth/login",
        json={"username": user.username, "password": password, "remember_me": True},
    )
    assert r.status_code == 200
    cookie_header = r.headers.get("set-cookie") or ""
    assert REFRESH_COOKIE_NAME in cookie_header.lower()
    assert "httponly" in cookie_header.lower()


def test_refresh_after_remember_login(client):
    db = SessionLocal()
    try:
        user = _ensure_owner(db, "remember_rotate_user")
        password = "TestPass123!"
    finally:
        db.close()

    login = client.post(
        "/api/auth/login",
        json={"username": user.username, "password": password, "remember_me": True},
    )
    assert login.status_code == 200

    refresh1 = client.post("/api/auth/refresh")
    assert refresh1.status_code == 200
    assert refresh1.json().get("access_token")


def test_logout_revokes_refresh(client):
    db = SessionLocal()
    try:
        user = _ensure_owner(db, "remember_logout_user")
        password = "TestPass123!"
    finally:
        db.close()

    client.post(
        "/api/auth/login",
        json={"username": user.username, "password": password, "remember_me": True},
    )
    out = client.post("/api/auth/logout")
    assert out.status_code == 200

    denied = client.post("/api/auth/refresh")
    assert denied.status_code == 401


def test_expired_refresh_rejected(client):
    db = SessionLocal()
    try:
        user = _ensure_owner(db, "remember_expired_user")
        password = "TestPass123!"
    finally:
        db.close()

    login = client.post(
        "/api/auth/login",
        json={"username": user.username, "password": password, "remember_me": True},
    )
    assert login.status_code == 200

    db = SessionLocal()
    try:
        rows = db.query(RefreshSession).filter(RefreshSession.user_id == user.id).all()
        assert rows
        for row in rows:
            row.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    denied = client.post("/api/auth/refresh")
    assert denied.status_code == 401


def test_access_token_short_lived_even_with_remember_me(client):
    db = SessionLocal()
    try:
        user = _ensure_owner(db, "remember_short_jwt_user")
        password = "TestPass123!"
    finally:
        db.close()

    with patch.object(settings, "access_token_expire_minutes", 30):
        r = client.post(
            "/api/auth/login",
            json={"username": user.username, "password": password, "remember_me": True},
        )
    assert r.status_code == 200
    assert r.json().get("expires_in") == 30 * 60
