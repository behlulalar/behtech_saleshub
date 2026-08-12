"""DE-6 — Sales Assistant conversation persistence API tests."""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from auth import create_access_token
from database import AssistantConversation, AssistantMessage, SessionLocal, User
from main import app
from migrate_auth import run_migrations
from security import hash_password


@pytest.fixture
def client():
    return TestClient(app)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _ensure_migrations():
    db = SessionLocal()
    try:
        run_migrations(db)
    finally:
        db.close()


def _make_owner() -> tuple[str, User]:
    db = SessionLocal()
    try:
        run_migrations(db)
        username = f"de6_{uuid.uuid4().hex[:10]}"
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=hash_password("TestPass123!"),
            role="owner",
            email_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token, _ = create_access_token(user.id, user.username, token_version=user.token_version or 0)
        return token, user
    finally:
        db.close()


def _cleanup_user(user_id: int) -> None:
    db = SessionLocal()
    try:
        db.query(AssistantMessage).filter(AssistantMessage.organization_id == user_id).delete(
            synchronize_session=False
        )
        db.query(AssistantConversation).filter(AssistantConversation.organization_id == user_id).delete(
            synchronize_session=False
        )
        db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def owner_a():
    _ensure_migrations()
    token, user = _make_owner()
    yield token, user
    _cleanup_user(user.id)


@pytest.fixture
def owner_b():
    _ensure_migrations()
    token, user = _make_owner()
    yield token, user
    _cleanup_user(user.id)


def test_create_conversation(client, owner_a):
    token, user = owner_a
    res = client.post(
        "/api/ai/conversations",
        headers=_auth(token),
        json={"title": "Pipeline check"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["id"] > 0
    assert body["organization_id"] == user.id
    assert body["user_id"] == user.id
    assert body["title"] == "Pipeline check"
    assert body["archived_at"] is None


def test_list_conversations(client, owner_a):
    token, _user = owner_a
    client.post("/api/ai/conversations", headers=_auth(token), json={"title": "A"})
    client.post("/api/ai/conversations", headers=_auth(token), json={"title": "B"})
    res = client.get("/api/ai/conversations", headers=_auth(token))
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) >= 2
    titles = {x["title"] for x in items}
    assert "A" in titles and "B" in titles


def test_conversation_detail(client, owner_a):
    token, _user = owner_a
    created = client.post("/api/ai/conversations", headers=_auth(token), json={}).json()
    cid = created["id"]
    db = SessionLocal()
    try:
        db.add(
            AssistantMessage(
                conversation_id=cid,
                organization_id=_user.id,
                user_id=_user.id,
                role="user",
                content="Merhaba",
                created_at=datetime.utcnow(),
            )
        )
        db.commit()
    finally:
        db.close()

    res = client.get(f"/api/ai/conversations/{cid}", headers=_auth(token))
    assert res.status_code == 200
    detail = res.json()
    assert detail["conversation"]["id"] == cid
    assert len(detail["messages"]) == 1
    assert detail["messages"][0]["content"] == "Merhaba"
    assert detail["messages"][0]["role"] == "user"


def test_cross_org_conversation_denied(client, owner_a, owner_b):
    token_a, _user_a = owner_a
    token_b, _user_b = owner_b
    created = client.post("/api/ai/conversations", headers=_auth(token_a), json={"title": "Private"}).json()
    cid = created["id"]

    res = client.get(f"/api/ai/conversations/{cid}", headers=_auth(token_b))
    assert res.status_code == 404

    res = client.patch(
        f"/api/ai/conversations/{cid}",
        headers=_auth(token_b),
        json={"title": "Hijack"},
    )
    assert res.status_code == 404

    res = client.delete(f"/api/ai/conversations/{cid}", headers=_auth(token_b))
    assert res.status_code == 404

    # Chat with foreign conversation_id must 404 (chat may be disabled → 503; enable flags)
    with patch("ai.deps.settings.ai_enabled", True), patch("ai.deps.settings.ai_chat_enabled", True), patch(
        "ai.router.ai_is_configured", return_value=True
    ):
        res = client.post(
            "/api/ai/chat",
            headers=_auth(token_b),
            json={"message": "hi", "conversation_id": cid, "locale": "tr"},
        )
        assert res.status_code == 404


def test_archive_conversation(client, owner_a):
    token, _user = owner_a
    created = client.post("/api/ai/conversations", headers=_auth(token), json={"title": "Old"}).json()
    cid = created["id"]
    res = client.delete(f"/api/ai/conversations/{cid}", headers=_auth(token))
    assert res.status_code == 200
    assert res.json()["archived_at"] is not None

    listed = client.get("/api/ai/conversations", headers=_auth(token)).json()["items"]
    assert all(x["id"] != cid for x in listed)

    detail = client.get(f"/api/ai/conversations/{cid}", headers=_auth(token))
    assert detail.status_code == 404


def test_user_and_assistant_message_persistence(client, owner_a):
    token, user = owner_a
    created = client.post("/api/ai/conversations", headers=_auth(token), json={}).json()
    cid = created["id"]

    def fake_chat(db, **kwargs):
        from ai.conversations_store import ROLE_ASSISTANT, append_message

        conv = kwargs.get("conversation")
        assert conv is not None
        append_message(
            db,
            conversation=conv,
            user_id=user.id,
            role=ROLE_ASSISTANT,
            content="Merhaba, yardımcı olayım.",
            run_id=None,
        )
        db.commit()
        return "Merhaba, yardımcı olayım.", 424242

    with patch("ai.deps.settings.ai_enabled", True), patch("ai.deps.settings.ai_chat_enabled", True), patch(
        "ai.router.ai_is_configured", return_value=True
    ), patch("ai.router.run_sales_chat", side_effect=fake_chat):
        res = client.post(
            "/api/ai/chat",
            headers=_auth(token),
            json={"message": "Selam asistan", "conversation_id": cid, "locale": "tr"},
        )
        assert res.status_code == 200
        assert res.json()["conversation_id"] == cid
        assert res.json()["run_id"] == 424242

    detail = client.get(f"/api/ai/conversations/{cid}", headers=_auth(token)).json()
    roles = [m["role"] for m in detail["messages"]]
    contents = [m["content"] for m in detail["messages"]]
    assert roles == ["user", "assistant"]
    assert contents[0] == "Selam asistan"
    assert contents[1] == "Merhaba, yardımcı olayım."
    assert detail["messages"][0]["run_id"] is None
    # Auto title from first user message
    assert "Selam" in detail["conversation"]["title"]


def test_archived_hidden_from_list(client, owner_a):
    token, _user = owner_a
    a = client.post("/api/ai/conversations", headers=_auth(token), json={"title": "Keep"}).json()
    b = client.post("/api/ai/conversations", headers=_auth(token), json={"title": "Drop"}).json()
    client.delete(f"/api/ai/conversations/{b['id']}", headers=_auth(token))
    items = client.get("/api/ai/conversations", headers=_auth(token)).json()["items"]
    ids = {x["id"] for x in items}
    assert a["id"] in ids
    assert b["id"] not in ids
