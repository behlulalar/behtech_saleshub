"""DE-6.3-A — Sales Assistant conversation memory tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ai.conversation_context import (
    MAX_CONTEXT_MESSAGES,
    TRUNCATION_PLACEHOLDER,
    build_conversation_history_for_llm,
    resolve_owned_conversation,
    sanitize_content_for_model,
)
from ai.conversations_store import append_message, create_conversation
from auth import create_access_token
from database import (
    AiAction,
    AssistantConversation,
    AssistantMessage,
    Lead,
    LeadActivity,
    SessionLocal,
    User,
)
from main import app
from migrate_auth import run_migrations
from security import hash_password


@pytest.fixture
def client():
    return TestClient(app)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_owner() -> tuple[str, User]:
    db = SessionLocal()
    try:
        run_migrations(db)
        username = f"de63a_{uuid.uuid4().hex[:10]}"
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
        db.query(LeadActivity).filter(LeadActivity.user_id == org_id).delete(synchronize_session=False)
        db.query(Lead).filter(Lead.user_id == org_id).delete(synchronize_session=False)
        db.query(AiAction).filter(AiAction.organization_id == org_id).delete(synchronize_session=False)
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


def _counts(org_id: int) -> dict:
    db = SessionLocal()
    try:
        return {
            "leads": db.query(Lead).filter(Lead.user_id == org_id).count(),
            "lead_activities": db.query(LeadActivity).filter(LeadActivity.user_id == org_id).count(),
            "ai_actions": db.query(AiAction).filter(AiAction.organization_id == org_id).count(),
        }
    finally:
        db.close()


def test_a_second_request_sees_prior_message(client, owner_a):
    """A: Conversation memory — turn 2 receives turn 1 in history."""
    token, user = owner_a
    cid = client.post("/api/ai/conversations", headers=_auth(token), json={}).json()["id"]
    captured: list[list] = []

    def fake_chat(db, **kwargs):
        from ai.conversations_store import ROLE_ASSISTANT, append_message

        captured.append(list(kwargs.get("history") or []))
        conv = kwargs["conversation"]
        n = len(captured)
        reply = f"Yanıt {n}"
        append_message(
            db,
            conversation=conv,
            user_id=user.id,
            role=ROLE_ASSISTANT,
            content=reply,
        )
        db.commit()
        return reply, 63001 + n

    with patch("ai.deps.settings.ai_enabled", True), patch("ai.deps.settings.ai_chat_enabled", True), patch(
        "ai.router.ai_is_configured", return_value=True
    ), patch("ai.router.run_sales_chat", side_effect=fake_chat):
        r1 = client.post(
            "/api/ai/chat",
            headers=_auth(token),
            json={"message": "Roof Tattoo teklifi neydi?", "conversation_id": cid},
        )
        r2 = client.post(
            "/api/ai/chat",
            headers=_auth(token),
            json={"message": "Peki neden?", "conversation_id": cid},
        )

    assert r1.status_code == 200 and r2.status_code == 200
    assert captured[0] == []  # first turn: no prior history
    hist2 = captured[1]
    assert any(t["role"] == "user" and "Roof Tattoo" in t["content"] for t in hist2)
    assert any(t["role"] == "assistant" and "Yanıt 1" in t["content"] for t in hist2)


def test_b_cross_org_conversation_denied(client, owner_a, owner_b):
    """B: Org isolation — foreign conversation_id → 404, no leak."""
    token_a, _ = owner_a
    token_b, user_b = owner_b
    cid = client.post(
        "/api/ai/conversations", headers=_auth(token_a), json={"title": "Secret"}
    ).json()["id"]

    db = SessionLocal()
    try:
        assert (
            resolve_owned_conversation(
                db,
                organization_id=user_b.id,
                user_id=user_b.id,
                conversation_id=cid,
            )
            is None
        )
    finally:
        db.close()

    with patch("ai.deps.settings.ai_enabled", True), patch("ai.deps.settings.ai_chat_enabled", True), patch(
        "ai.router.ai_is_configured", return_value=True
    ):
        res = client.post(
            "/api/ai/chat",
            headers=_auth(token_b),
            json={"message": "leak?", "conversation_id": cid},
        )
        assert res.status_code == 404
        assert "Secret" not in res.text
        assert "Roof" not in res.text


def test_c_chat_without_conversation_id_preserves_body_history(client, owner_a):
    """C: No conversation_id → client history contract intact."""
    token, _user = owner_a
    seen = {}

    def fake_chat(db, **kwargs):
        seen["history"] = list(kwargs.get("history") or [])
        seen["conversation"] = kwargs.get("conversation")
        return "OK legacy", 63010

    with patch("ai.deps.settings.ai_enabled", True), patch("ai.deps.settings.ai_chat_enabled", True), patch(
        "ai.router.ai_is_configured", return_value=True
    ), patch("ai.router.run_sales_chat", side_effect=fake_chat):
        res = client.post(
            "/api/ai/chat",
            headers=_auth(token),
            json={
                "message": "Devam",
                "locale": "tr",
                "history": [
                    {"role": "user", "content": "Önceki soru"},
                    {"role": "assistant", "content": "Önceki yanıt"},
                ],
            },
        )
    assert res.status_code == 200
    assert seen["conversation"] is None
    assert seen["history"][0]["content"] == "Önceki soru"
    assert seen["history"][1]["content"] == "Önceki yanıt"
    assert res.json()["conversation_id"] is None


def test_d_long_conversation_applies_context_limit(owner_a):
    """D: Long conversation → newest kept + truncation placeholder."""
    _token, user = owner_a
    db = SessionLocal()
    try:
        conv = create_conversation(db, organization_id=user.id, user_id=user.id, title="Long")
        db.commit()
        base = datetime.utcnow() - timedelta(hours=2)
        for i in range(40):
            role = "user" if i % 2 == 0 else "assistant"
            db.add(
                AssistantMessage(
                    conversation_id=conv.id,
                    organization_id=user.id,
                    user_id=user.id,
                    role=role,
                    content=f"msg-{i:02d} unique-{i}",
                    created_at=base + timedelta(minutes=i),
                )
            )
        db.commit()

        history = build_conversation_history_for_llm(
            db,
            organization_id=user.id,
            conversation_id=conv.id,
            max_messages=MAX_CONTEXT_MESSAGES,
            max_chars=8_000,
        )
        assert len(history) <= MAX_CONTEXT_MESSAGES + 1  # + optional placeholder
        assert history[0]["content"] == TRUNCATION_PLACEHOLDER
        joined = " ".join(t["content"] for t in history)
        assert "msg-00" not in joined
        assert "msg-39" in joined
        # No DB ids leaked as structured fields
        assert all(set(t.keys()) == {"role", "content"} for t in history)
    finally:
        db.close()


def test_e_crm_tools_with_conversation_memory(client, owner_a):
    """E: CRM tool path still works when conversation memory is present."""
    from ai.crm_tools import execute_crm_tool

    token, user = owner_a
    before = _counts(user.id)
    cid = client.post("/api/ai/conversations", headers=_auth(token), json={}).json()["id"]

    db = SessionLocal()
    try:
        lead = Lead(
            user_id=user.id,
            category="tattoo",
            isletme_adi="Roof Tattoo Sakarya",
            sehir="Sakarya",
            durum="Demo Gönderildi",
            teklif="8500 TL",
            oncelik="orta",
        )
        db.add(lead)
        db.commit()
    finally:
        db.close()

    # Seed prior memory turns
    db = SessionLocal()
    try:
        conv = db.query(AssistantConversation).filter(AssistantConversation.id == cid).one()
        append_message(
            db,
            conversation=conv,
            user_id=user.id,
            role="user",
            content="Roof Tattoo hakkında bilgi ver",
        )
        append_message(
            db,
            conversation=conv,
            user_id=user.id,
            role="assistant",
            content="Kayıt var, detay için sorun.",
        )
        db.commit()
        history = build_conversation_history_for_llm(
            db,
            organization_id=user.id,
            conversation_id=cid,
        )
        assert any("Roof Tattoo" in t["content"] for t in history)
        tool = execute_crm_tool(db, user.id, "search_leads", {"query": "Roof Tattoo"})
        assert tool.get("ok") is True
        leads = (tool.get("result") or {}).get("leads") or []
        assert len(leads) >= 1
    finally:
        db.close()

    tool_seen = {"ok": False}

    def fake_chat(db, **kwargs):
        from ai.conversations_store import ROLE_ASSISTANT, append_message
        from ai.crm_tools import execute_crm_tool as _exec

        hist = kwargs.get("history") or []
        assert any("Roof Tattoo" in (t.get("content") or "") for t in hist)
        found = _exec(db, user.id, "search_leads", {"query": "Roof Tattoo"})
        leads = (found.get("result") or {}).get("leads") or []
        assert leads
        result = _exec(db, user.id, "get_lead_offer", {"lead_id": leads[0]["lead_id"]})
        tool_seen["ok"] = bool(result.get("ok"))
        reply = "CRM tool + memory OK"
        append_message(
            db,
            conversation=kwargs["conversation"],
            user_id=user.id,
            role=ROLE_ASSISTANT,
            content=reply,
        )
        db.commit()
        return reply, 63050

    with patch("ai.deps.settings.ai_enabled", True), patch("ai.deps.settings.ai_chat_enabled", True), patch(
        "ai.router.ai_is_configured", return_value=True
    ), patch("ai.router.run_sales_chat", side_effect=fake_chat):
        res = client.post(
            "/api/ai/chat",
            headers=_auth(token),
            json={"message": "Teklifi hatırla", "conversation_id": cid},
        )

    assert res.status_code == 200
    assert tool_seen["ok"] is True
    after = _counts(user.id)
    assert after["lead_activities"] == before["lead_activities"]
    assert after["ai_actions"] == before["ai_actions"]
    assert after["leads"] == before["leads"] + 1


def test_f_followup_uses_memory_and_tools(client, owner_a):
    """F: Offer question then 'Peki neden?' — memory + tool-capable path."""
    token, user = owner_a
    before = _counts(user.id)
    cid = client.post("/api/ai/conversations", headers=_auth(token), json={}).json()["id"]
    histories: list[list] = []

    def fake_chat(db, **kwargs):
        from ai.conversations_store import ROLE_ASSISTANT, append_message

        histories.append(list(kwargs.get("history") or []))
        conv = kwargs["conversation"]
        if len(histories) == 1:
            reply = "Roof Tattoo'ya 8500 TL teklif verilmiş."
        else:
            # Follow-up should see prior offer context in memory.
            hist_text = " ".join(t["content"] for t in histories[-1])
            assert "8500" in hist_text or "Roof Tattoo" in hist_text
            reply = "Çünkü demo gönderildi ve teklif CRM'de kayıtlı."
        append_message(
            db,
            conversation=conv,
            user_id=user.id,
            role=ROLE_ASSISTANT,
            content=reply,
        )
        db.commit()
        return reply, 63100 + len(histories)

    with patch("ai.deps.settings.ai_enabled", True), patch("ai.deps.settings.ai_chat_enabled", True), patch(
        "ai.router.ai_is_configured", return_value=True
    ), patch("ai.router.run_sales_chat", side_effect=fake_chat):
        r1 = client.post(
            "/api/ai/chat",
            headers=_auth(token),
            json={
                "message": "Roof Tattoo'ya ne teklif vermiştik?",
                "conversation_id": cid,
            },
        )
        r2 = client.post(
            "/api/ai/chat",
            headers=_auth(token),
            json={"message": "Peki neden?", "conversation_id": cid},
        )

    assert r1.status_code == 200 and r2.status_code == 200
    assert "8500" in r1.json()["reply"]
    assert len(histories[1]) >= 2
    after = _counts(user.id)
    assert after == before  # G + H


def test_g_h_no_crm_or_aiaction_mutation_on_memory_chat(client, owner_a):
    """G/H: Conversation memory chat does not mutate CRM or AiAction."""
    token, user = owner_a
    before = _counts(user.id)
    cid = client.post("/api/ai/conversations", headers=_auth(token), json={}).json()["id"]

    def fake_chat(db, **kwargs):
        from ai.conversations_store import ROLE_ASSISTANT, append_message

        append_message(
            db,
            conversation=kwargs["conversation"],
            user_id=user.id,
            role=ROLE_ASSISTANT,
            content="Tamam",
        )
        db.commit()
        return "Tamam", 63200

    with patch("ai.deps.settings.ai_enabled", True), patch("ai.deps.settings.ai_chat_enabled", True), patch(
        "ai.router.ai_is_configured", return_value=True
    ), patch("ai.router.run_sales_chat", side_effect=fake_chat):
        for msg in ("Soru 1", "Soru 2", "Soru 3"):
            assert (
                client.post(
                    "/api/ai/chat",
                    headers=_auth(token),
                    json={"message": msg, "conversation_id": cid},
                ).status_code
                == 200
            )

    assert _counts(user.id) == before
    detail = client.get(f"/api/ai/conversations/{cid}", headers=_auth(token)).json()
    assert len(detail["messages"]) == 6  # 3 user + 3 assistant


def test_sanitize_strips_internal_and_tool_dumps():
    dirty = 'organization_id: 99 fingerprint=abc {"ok": true, "result": {"x": 1}}'
    # key=value style redacted
    assert "organization_id" not in sanitize_content_for_model("organization_id: 42 secret")
    assert "fingerprint" not in sanitize_content_for_model("fingerprint: deadbeef")
    toolish = '{"ok": true, "result": {"offer_text": "8500 TL"}}'
    cleaned = sanitize_content_for_model(toolish)
    assert "8500" not in cleaned
    assert "tool" in cleaned.lower() or "veri" in cleaned.lower()
    _ = dirty
