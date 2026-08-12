"""DE-6.5 — Redis working memory tests (in-memory / fail-open; no production Redis)."""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from ai.assistant_memory import (
    InMemoryAssistantMemoryStore,
    NullAssistantMemoryStore,
    RedisAssistantMemoryStore,
    best_effort_memory_append,
    best_effort_memory_clear,
    get_assistant_memory_store,
    memory_key,
    merge_working_memory_with_postgres,
    reset_assistant_memory_store_for_tests,
    sanitize_memory_messages,
)
from ai.conversations_store import append_message, create_conversation
from auth import create_access_token
from database import AssistantConversation, AssistantMessage, SessionLocal, User
from main import app
from migrate_auth import run_migrations
from security import hash_password


@pytest.fixture(autouse=True)
def _reset_memory_store():
    reset_assistant_memory_store_for_tests(None)
    yield
    reset_assistant_memory_store_for_tests(None)


@pytest.fixture
def client():
    return TestClient(app)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_owner() -> tuple[str, User]:
    db = SessionLocal()
    try:
        run_migrations(db)
        username = f"de65_{uuid.uuid4().hex[:10]}"
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


def _cleanup(org_id: int) -> None:
    db = SessionLocal()
    try:
        db.query(AssistantMessage).filter(AssistantMessage.organization_id == org_id).delete(
            synchronize_session=False
        )
        db.query(AssistantConversation).filter(AssistantConversation.organization_id == org_id).delete(
            synchronize_session=False
        )
        db.query(User).filter(User.id == org_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def owner_a():
    token, user = _make_owner()
    yield token, user
    _cleanup(user.id)


@pytest.fixture
def owner_b():
    token, user = _make_owner()
    yield token, user
    _cleanup(user.id)


def test_a_flag_disabled_uses_postgres_path(owner_a):
    _token, user = owner_a
    store = InMemoryAssistantMemoryStore()
    reset_assistant_memory_store_for_tests(store)
    with patch("ai.assistant_memory.settings.assistant_memory_enabled", False):
        reset_assistant_memory_store_for_tests(None)
        s = get_assistant_memory_store()
        assert isinstance(s, NullAssistantMemoryStore)
        hist, src = merge_working_memory_with_postgres(
            organization_id=user.id,
            user_id=user.id,
            conversation_id=1,
            postgres_history=[{"role": "user", "content": "hello"}],
        )
        assert src == "disabled"
        assert hist[0]["content"] == "hello"


def test_b_redis_hit(owner_a):
    _token, user = owner_a
    store = InMemoryAssistantMemoryStore()
    reset_assistant_memory_store_for_tests(store)
    pg = [
        {"role": "user", "content": "Roof Tattoo teklif?"},
        {"role": "assistant", "content": "8500 TL"},
    ]
    store.set(organization_id=user.id, user_id=user.id, conversation_id=42, messages=pg)
    with patch("ai.assistant_memory.settings.assistant_memory_enabled", True):
        hist, src = merge_working_memory_with_postgres(
            organization_id=user.id,
            user_id=user.id,
            conversation_id=42,
            postgres_history=pg,
        )
    assert src == "hit"
    assert hist[-1]["content"] == "8500 TL"


def test_c_redis_miss_falls_back_to_postgres(owner_a):
    _token, user = owner_a
    store = InMemoryAssistantMemoryStore()
    reset_assistant_memory_store_for_tests(store)
    pg = [{"role": "user", "content": "from-pg"}]
    with patch("ai.assistant_memory.settings.assistant_memory_enabled", True):
        hist, src = merge_working_memory_with_postgres(
            organization_id=user.id,
            user_id=user.id,
            conversation_id=99,
            postgres_history=pg,
        )
    assert src == "miss"
    assert hist[0]["content"] == "from-pg"
    # Warm write happened
    warmed = store.get(organization_id=user.id, user_id=user.id, conversation_id=99)
    assert warmed and warmed[0]["content"] == "from-pg"


def test_d_redis_write_and_append(owner_a):
    _token, user = owner_a
    store = InMemoryAssistantMemoryStore()
    reset_assistant_memory_store_for_tests(store)
    assert store.set(
        organization_id=user.id,
        user_id=user.id,
        conversation_id=7,
        messages=[{"role": "user", "content": "a"}],
    )
    assert store.append(
        organization_id=user.id,
        user_id=user.id,
        conversation_id=7,
        message={"role": "assistant", "content": "b"},
    )
    got = store.get(organization_id=user.id, user_id=user.id, conversation_id=7)
    assert [m["content"] for m in got] == ["a", "b"]


def test_e_ttl_applied_on_redis_set():
    client = MagicMock()
    store = RedisAssistantMemoryStore(client)
    with patch("ai.assistant_memory.settings.assistant_memory_ttl_seconds", 86400), patch(
        "ai.assistant_memory.settings.assistant_memory_enabled", True
    ):
        ok = store.set(
            organization_id=1,
            user_id=1,
            conversation_id=1,
            messages=[{"role": "user", "content": "hi"}],
        )
    assert ok is True
    args, kwargs = client.set.call_args
    assert kwargs.get("ex") == 86400


def test_e2_invalid_ttl_skips_infinite_write():
    client = MagicMock()
    store = RedisAssistantMemoryStore(client)
    with patch("ai.assistant_memory.settings.assistant_memory_ttl_seconds", 0):
        ok = store.set(
            organization_id=1,
            user_id=1,
            conversation_id=1,
            messages=[{"role": "user", "content": "hi"}],
        )
    assert ok is False
    client.set.assert_not_called()


def test_f_max_messages_bound():
    msgs = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(40)]
    with patch("ai.assistant_memory.settings.assistant_memory_max_messages", 6):
        cleaned = sanitize_memory_messages(msgs)
    assert len(cleaned) <= 6
    assert cleaned[-1]["content"] == "m39"


def test_g_max_chars_bound():
    msgs = [
        {"role": "user", "content": "x" * 5000},
        {"role": "assistant", "content": "y" * 5000},
        {"role": "user", "content": "tail"},
    ]
    with patch("ai.assistant_memory.settings.assistant_memory_max_chars", 2000), patch(
        "ai.assistant_memory.settings.assistant_memory_max_messages", 12
    ):
        cleaned = sanitize_memory_messages(msgs)
    assert any(m["content"] == "tail" for m in cleaned)
    assert sum(len(m["content"]) for m in cleaned) <= 2000 + 200  # placeholder headroom


def test_h_malformed_redis_payload_fallback(owner_a):
    _token, user = owner_a
    client = MagicMock()
    client.get.return_value = "{not-json"
    store = RedisAssistantMemoryStore(client)
    reset_assistant_memory_store_for_tests(store)
    with patch("ai.assistant_memory.settings.assistant_memory_enabled", True):
        hist, src = merge_working_memory_with_postgres(
            organization_id=user.id,
            user_id=user.id,
            conversation_id=3,
            postgres_history=[{"role": "user", "content": "pg-ok"}],
        )
    assert hist[0]["content"] == "pg-ok"
    assert src in ("miss", "stale_refresh", "fallback", "hit")


def test_i_redis_unavailable_chat_still_works(client, owner_a):
    token, user = owner_a
    created = client.post("/api/ai/conversations", headers=_auth(token), json={}).json()
    cid = created["id"]

    def boom_get(*_a, **_k):
        raise RuntimeError("redis down")

    bad = MagicMock()
    bad.get.side_effect = boom_get
    bad.set.side_effect = boom_get
    bad.append.side_effect = boom_get
    reset_assistant_memory_store_for_tests(RedisAssistantMemoryStore(bad))

    def fake_chat(db, **kwargs):
        from ai.conversations_store import ROLE_ASSISTANT, append_message

        append_message(
            db,
            conversation=kwargs["conversation"],
            user_id=user.id,
            role=ROLE_ASSISTANT,
            content="OK without redis",
        )
        db.commit()
        return "OK without redis", 65001

    with patch("ai.assistant_memory.settings.assistant_memory_enabled", True), patch(
        "ai.deps.settings.ai_enabled", True
    ), patch("ai.deps.settings.ai_chat_enabled", True), patch(
        "ai.router.ai_is_configured", return_value=True
    ), patch("ai.router.run_sales_chat", side_effect=fake_chat):
        res = client.post(
            "/api/ai/chat",
            headers=_auth(token),
            json={"message": "hello", "conversation_id": cid},
        )
    assert res.status_code == 200
    assert res.json()["reply"] == "OK without redis"


def test_j_cross_org_isolation(owner_a, owner_b):
    _ta, user_a = owner_a
    _tb, user_b = owner_b
    store = InMemoryAssistantMemoryStore()
    store.set(
        organization_id=user_a.id,
        user_id=user_a.id,
        conversation_id=10,
        messages=[{"role": "user", "content": "secret-a"}],
    )
    assert (
        store.get(organization_id=user_b.id, user_id=user_b.id, conversation_id=10) is None
    )
    key_a = memory_key(organization_id=user_a.id, user_id=user_a.id, conversation_id=10)
    key_b = memory_key(organization_id=user_b.id, user_id=user_b.id, conversation_id=10)
    assert key_a != key_b


def test_k_cross_user_isolation_same_org_key_differs():
    k1 = memory_key(organization_id=1, user_id=16, conversation_id=49)
    k2 = memory_key(organization_id=1, user_id=17, conversation_id=49)
    assert k1 == "assistant:memory:1:16:49"
    assert k1 != k2


def test_l_archive_clears_redis(client, owner_a):
    token, user = owner_a
    store = InMemoryAssistantMemoryStore()
    reset_assistant_memory_store_for_tests(store)
    created = client.post("/api/ai/conversations", headers=_auth(token), json={"title": "X"}).json()
    cid = created["id"]
    store.set(
        organization_id=user.id,
        user_id=user.id,
        conversation_id=cid,
        messages=[{"role": "user", "content": "bye"}],
    )
    with patch("ai.assistant_memory.settings.assistant_memory_enabled", True):
        # Ensure clear path uses our injected store via get_assistant_memory_store
        reset_assistant_memory_store_for_tests(store)
        res = client.delete(f"/api/ai/conversations/{cid}", headers=_auth(token))
    assert res.status_code == 200
    assert store.get(organization_id=user.id, user_id=user.id, conversation_id=cid) is None


def test_m_tool_json_not_persisted():
    dirty = [
        {"role": "tool", "content": '{"ok": true, "result": {"lead_id": 3}}'},
        {"role": "user", "content": "ok"},
        {
            "role": "assistant",
            "content": '{"ok": true, "result": {"offer_text": "8500 TL"}}',
        },
    ]
    cleaned = sanitize_memory_messages(dirty)
    assert all(m["role"] in ("user", "assistant") for m in cleaned)
    assert not any("lead_id" in m["content"] for m in cleaned)
    assert not any(m["content"].startswith("{") and '"ok"' in m["content"] for m in cleaned)


def test_n_internal_ids_not_persisted():
    cleaned = sanitize_memory_messages(
        [
            {
                "role": "user",
                "content": "organization_id: 99 fingerprint=abc lead_id: 3 please help",
            }
        ]
    )
    text = cleaned[0]["content"]
    assert "organization_id" not in text
    assert "fingerprint" not in text


def test_o_streaming_memory_path_does_not_500(client, owner_a):
    token, user = owner_a
    store = InMemoryAssistantMemoryStore()
    reset_assistant_memory_store_for_tests(store)
    cid = client.post("/api/ai/conversations", headers=_auth(token), json={}).json()["id"]

    def fake_events(db, **kwargs):
        from ai.conversations_store import ROLE_ASSISTANT, append_message

        append_message(
            db,
            conversation=kwargs["conversation"],
            user_id=user.id,
            role=ROLE_ASSISTANT,
            content="streamed",
        )
        db.commit()
        yield {"type": "delta", "content": "streamed"}
        yield {"type": "done", "run_id": 1, "conversation_id": kwargs["conversation"].id}

    with patch("ai.assistant_memory.settings.assistant_memory_enabled", True), patch(
        "ai.deps.settings.ai_enabled", True
    ), patch("ai.deps.settings.ai_chat_enabled", True), patch(
        "ai.router.ai_is_configured", return_value=True
    ), patch("ai.router.iter_sales_chat_events", side_effect=fake_events):
        res = client.post(
            "/api/ai/chat/stream",
            headers=_auth(token),
            json={"message": "hi stream", "conversation_id": cid},
        )
    assert res.status_code == 200
    assert "streamed" in res.text


def test_p_follow_up_memory_append(owner_a):
    _token, user = owner_a
    store = InMemoryAssistantMemoryStore()
    reset_assistant_memory_store_for_tests(store)
    with patch("ai.assistant_memory.settings.assistant_memory_enabled", True):
        reset_assistant_memory_store_for_tests(store)
        best_effort_memory_append(
            organization_id=user.id,
            user_id=user.id,
            conversation_id=5,
            role="user",
            content="Bugün ne yapmalıyım?",
        )
        best_effort_memory_append(
            organization_id=user.id,
            user_id=user.id,
            conversation_id=5,
            role="assistant",
            content="Roof Tattoo öncelikli",
        )
    got = store.get(organization_id=user.id, user_id=user.id, conversation_id=5)
    assert len(got) == 2
    assert "Roof Tattoo" in got[1]["content"]


def test_q_postgres_source_of_truth_on_stale_redis(owner_a):
    _token, user = owner_a
    store = InMemoryAssistantMemoryStore()
    reset_assistant_memory_store_for_tests(store)
    store.set(
        organization_id=user.id,
        user_id=user.id,
        conversation_id=8,
        messages=[{"role": "assistant", "content": "stale-redis"}],
    )
    pg = [
        {"role": "user", "content": "new-pg-user"},
        {"role": "assistant", "content": "new-pg-assistant"},
    ]
    with patch("ai.assistant_memory.settings.assistant_memory_enabled", True):
        hist, src = merge_working_memory_with_postgres(
            organization_id=user.id,
            user_id=user.id,
            conversation_id=8,
            postgres_history=pg,
        )
    assert src == "stale_refresh"
    assert hist[-1]["content"] == "new-pg-assistant"
    refreshed = store.get(organization_id=user.id, user_id=user.id, conversation_id=8)
    assert refreshed[-1]["content"] == "new-pg-assistant"


def test_r_redis_loss_conversation_still_in_pg(client, owner_a):
    token, user = owner_a
    db = SessionLocal()
    try:
        conv = create_conversation(db, organization_id=user.id, user_id=user.id, title="Keep")
        append_message(db, conversation=conv, user_id=user.id, role="user", content="persisted")
        append_message(db, conversation=conv, user_id=user.id, role="assistant", content="also-pg")
        db.commit()
        cid = conv.id
    finally:
        db.close()

    # Clear any redis and disable memory — PG detail still loads
    reset_assistant_memory_store_for_tests(InMemoryAssistantMemoryStore())
    with patch("ai.assistant_memory.settings.assistant_memory_enabled", False):
        detail = client.get(f"/api/ai/conversations/{cid}", headers=_auth(token))
    assert detail.status_code == 200
    contents = [m["content"] for m in detail.json()["messages"]]
    assert "persisted" in contents and "also-pg" in contents


def test_best_effort_clear_never_raises(owner_a):
    _token, user = owner_a
    bad = MagicMock()
    bad.clear.side_effect = RuntimeError("nope")
    reset_assistant_memory_store_for_tests(bad)
    with patch("ai.assistant_memory.settings.assistant_memory_enabled", True):
        best_effort_memory_clear(organization_id=user.id, user_id=user.id, conversation_id=1)
