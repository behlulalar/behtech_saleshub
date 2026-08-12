"""DE-6.7 — Conversational entity continuity tests."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ai.assistant_memory import (
    InMemoryAssistantMemoryStore,
    reset_assistant_memory_store_for_tests,
)
from ai.capabilities.chat_tools import _execute_bound_tool
from ai.conversations_store import append_message, create_conversation
from ai.entity_continuity import (
    ActiveEntity,
    extract_explicit_entity,
    get_conversation_active_entity,
    is_broad_portfolio_intent,
    is_implicit_followup,
    resolve_conversational_entity,
    rewrite_tool_call_for_entity,
    set_conversation_active_entity,
)
from auth import create_access_token
from config import settings
from database import AiAction, Lead, LeadActivity, SessionLocal, User
from main import app
from migrate_auth import run_migrations
from security import hash_password


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _ai_flags():
    prev = (
        settings.ai_enabled,
        settings.ai_chat_enabled,
        getattr(settings, "assistant_memory_enabled", False),
    )
    settings.ai_enabled = True
    settings.ai_chat_enabled = True
    settings.assistant_memory_enabled = False
    reset_assistant_memory_store_for_tests(None)
    try:
        yield
    finally:
        settings.ai_enabled, settings.ai_chat_enabled, settings.assistant_memory_enabled = prev
        reset_assistant_memory_store_for_tests(None)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_owner_with_leads() -> tuple[str, User, Lead, Lead]:
    db = SessionLocal()
    try:
        run_migrations(db)
        username = f"de67_{uuid.uuid4().hex[:10]}"
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
        roof = Lead(
            user_id=user.id,
            isletme_adi="Roof Tattoo Sakarya",
            sehir="Sakarya",
            durum="Demo Gönderildi",
            teklif="8500 TL",
            category="Dövme Salonları",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        togi = Lead(
            user_id=user.id,
            isletme_adi="Togi Erkek Kuaförü",
            sehir="Sakarya",
            durum="Demo Gönderildi",
            teklif="12000 TL",
            category="Kuaför",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(roof)
        db.add(togi)
        db.commit()
        db.refresh(roof)
        db.refresh(togi)
        token, _ = create_access_token(user.id, user.username, token_version=user.token_version or 0)
        return token, user, roof, togi
    finally:
        db.close()


def _cleanup(org_id: int) -> None:
    db = SessionLocal()
    try:
        from database import AssistantConversation, AssistantMessage

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


def test_implicit_and_broad_detectors():
    assert is_implicit_followup("Peki neden kapanmadı?")
    assert is_implicit_followup("Son aktivitesi ne?")
    assert is_implicit_followup("Teklif tarihi neydi?")
    assert is_implicit_followup("Onun teklifi ne?")
    assert is_broad_portfolio_intent("Bugün ne yapmalıyım?")
    assert is_broad_portfolio_intent("Bekleyen teklifler neler?")
    assert is_broad_portfolio_intent("En kritik leadler hangileri?")
    assert not is_implicit_followup("Bugün ne yapmalıyım?")


def test_a_roof_followup_why_stays_on_roof():
    token, user, roof, togi = _make_owner_with_leads()
    db = SessionLocal()
    try:
        conv = create_conversation(db, organization_id=user.id, user_id=user.id, title="t")
        db.commit()
        r1 = resolve_conversational_entity(
            db,
            org_id=user.id,
            conversation=conv,
            user_message="Roof Tattoo Sakarya'ya ne teklif vermiştik?",
        )
        assert r1.entity is not None
        assert r1.entity.lead_id == roof.id
        set_conversation_active_entity(db, conv, r1.entity)
        db.commit()

        r2 = resolve_conversational_entity(
            db,
            org_id=user.id,
            conversation=conv,
            user_message="Peki neden kapanmadı?",
        )
        assert r2.bind_for_tools is True
        assert r2.entity is not None
        assert r2.entity.lead_id == roof.id
        assert r2.entity.lead_id != togi.id

        name, args = rewrite_tool_call_for_entity(
            tool_name="search_leads",
            args={"query": "kapanmayan lead"},
            entity=r2.entity,
            bind_for_tools=True,
            user_message="Peki neden kapanmadı?",
        )
        assert name == "get_lead"
        assert args["lead_id"] == roof.id
    finally:
        db.close()
        _cleanup(user.id)


def test_b_c_activity_and_offer_date_followups():
    token, user, roof, _togi = _make_owner_with_leads()
    db = SessionLocal()
    try:
        conv = create_conversation(db, organization_id=user.id, user_id=user.id, title="t")
        set_conversation_active_entity(
            db,
            conv,
            ActiveEntity("lead", roof.id, "Roof Tattoo Sakarya"),
        )
        db.commit()
        for msg in ("Son aktivitesi ne?", "Teklif tarihi neydi?"):
            res = resolve_conversational_entity(
                db, org_id=user.id, conversation=conv, user_message=msg
            )
            assert res.entity and res.entity.lead_id == roof.id
            assert res.bind_for_tools
            name, args = rewrite_tool_call_for_entity(
                tool_name="get_lead_activities",
                args={},
                entity=res.entity,
                bind_for_tools=True,
                user_message=msg,
            )
            assert args["lead_id"] == roof.id
    finally:
        db.close()
        _cleanup(user.id)


def test_d_e_explicit_switch_then_pronoun():
    _token, user, roof, togi = _make_owner_with_leads()
    db = SessionLocal()
    try:
        conv = create_conversation(db, organization_id=user.id, user_id=user.id, title="t")
        set_conversation_active_entity(
            db, conv, ActiveEntity("lead", roof.id, "Roof Tattoo Sakarya")
        )
        db.commit()
        switched = resolve_conversational_entity(
            db,
            org_id=user.id,
            conversation=conv,
            user_message="Togi'de durum ne?",
        )
        assert switched.entity is not None
        assert switched.entity.lead_id == togi.id
        set_conversation_active_entity(db, conv, switched.entity)
        db.commit()

        pronoun = resolve_conversational_entity(
            db,
            org_id=user.id,
            conversation=conv,
            user_message="Onun teklifi ne?",
        )
        assert pronoun.entity is not None
        assert pronoun.entity.lead_id == togi.id
        assert pronoun.bind_for_tools
    finally:
        db.close()
        _cleanup(user.id)


def test_f_broad_daily_brief_not_forced():
    _token, user, roof, _togi = _make_owner_with_leads()
    db = SessionLocal()
    try:
        conv = create_conversation(db, organization_id=user.id, user_id=user.id, title="t")
        set_conversation_active_entity(
            db, conv, ActiveEntity("lead", roof.id, "Roof Tattoo Sakarya")
        )
        db.commit()
        res = resolve_conversational_entity(
            db,
            org_id=user.id,
            conversation=conv,
            user_message="Bugün ne yapmalıyım?",
        )
        assert res.bind_for_tools is False
        assert res.entity is not None  # retained for context
        name, args = rewrite_tool_call_for_entity(
            tool_name="get_daily_sales_brief",
            args={},
            entity=res.entity,
            bind_for_tools=res.bind_for_tools,
            user_message="Bugün ne yapmalıyım?",
        )
        assert name == "get_daily_sales_brief"
        assert "lead_id" not in args
    finally:
        db.close()
        _cleanup(user.id)


def test_g_unknown_lead_no_hallucinated_entity():
    _token, user, _roof, _togi = _make_owner_with_leads()
    db = SessionLocal()
    try:
        conv = create_conversation(db, organization_id=user.id, user_id=user.id, title="t")
        db.commit()
        res = resolve_conversational_entity(
            db,
            org_id=user.id,
            conversation=conv,
            user_message="XYZ Olmayan Firma'ya ne teklif vermiştik?",
        )
        assert res.entity is None
        assert res.bind_for_tools is False
    finally:
        db.close()
        _cleanup(user.id)


def test_h_cross_org_isolation():
    _t1, user_a, roof_a, _ = _make_owner_with_leads()
    _t2, user_b, _roof_b, _ = _make_owner_with_leads()
    db = SessionLocal()
    try:
        # Org B must not resolve Org A's Roof Tattoo by id ownership checks
        ent = extract_explicit_entity(db, user_b.id, "Roof Tattoo Sakarya'ya ne teklif?")
        # user_b has its own Roof Tattoo lead from fixture — both have same name.
        # Force id mismatch: resolve lead belonging to A with org B.
        from ai.entity_continuity import _lead_entity

        assert _lead_entity(db, user_b.id, roof_a.id) is None
        conv_b = create_conversation(db, organization_id=user_b.id, user_id=user_b.id, title="x")
        set_conversation_active_entity(
            db, conv_b, ActiveEntity("lead", roof_a.id, "Roof Tattoo Sakarya")
        )
        db.commit()
        # Stale foreign id cleared on implicit follow-up
        res = resolve_conversational_entity(
            db,
            org_id=user_b.id,
            conversation=conv_b,
            user_message="Peki neden kapanmadı?",
        )
        assert res.entity is None
        assert res.reason == "stale_entity_cleared"
    finally:
        db.close()
        _cleanup(user_a.id)
        _cleanup(user_b.id)


def test_i_redis_off_pg_entity_continuity(client):
    token, user, roof, _ = _make_owner_with_leads()
    settings.assistant_memory_enabled = False
    db = SessionLocal()
    try:
        conv = create_conversation(db, organization_id=user.id, user_id=user.id, title="pg")
        set_conversation_active_entity(
            db, conv, ActiveEntity("lead", roof.id, "Roof Tattoo Sakarya")
        )
        append_message(
            db,
            conversation=conv,
            user_id=user.id,
            role="user",
            content="Roof Tattoo Sakarya'ya ne teklif vermiştik?",
        )
        append_message(
            db,
            conversation=conv,
            user_id=user.id,
            role="assistant",
            content="Teklif 8500 TL.",
        )
        db.commit()
        cid = conv.id
    finally:
        db.close()

    with patch("ai.capabilities.chat.run_tool_loop") as loop:
        loop.return_value = (
            "CRM'de doğrulanmış bir kapanmama nedeni yok. Roof Tattoo için teklif 8500 TL.",
            {"total_tokens": 10},
            [{"tool": "get_lead"}],
        )
        res = client.post(
            "/api/ai/chat",
            headers=_auth(token),
            json={"message": "Peki neden kapanmadı?", "conversation_id": cid},
        )
    assert res.status_code == 200
    # Entity context was bound into tool loop
    kwargs = loop.call_args.kwargs
    assert kwargs["entity_ctx"]["bind_for_tools"] is True
    assert kwargs["entity_ctx"]["entity"].lead_id == roof.id
    _cleanup(user.id)


def test_j_redis_on_entity_continuity_persists(client):
    token, user, roof, _ = _make_owner_with_leads()
    settings.assistant_memory_enabled = True
    store = InMemoryAssistantMemoryStore()
    reset_assistant_memory_store_for_tests(store)
    db = SessionLocal()
    try:
        conv = create_conversation(db, organization_id=user.id, user_id=user.id, title="redis")
        db.commit()
        cid = conv.id
    finally:
        db.close()

    with patch("ai.capabilities.chat.run_tool_loop") as loop:
        loop.return_value = ("8500 TL", {"total_tokens": 5}, [{"tool": "get_lead_offer"}])

        # Simulate tool-driven entity refresh by setting dirty entity in side effect
        def _side(*_a, **kw):
            ctx = kw.get("entity_ctx") or {}
            ctx["entity"] = ActiveEntity("lead", roof.id, "Roof Tattoo Sakarya")
            ctx["dirty"] = True
            return ("8500 TL", {"total_tokens": 5}, [{"tool": "get_lead_offer"}])

        loop.side_effect = _side
        r1 = client.post(
            "/api/ai/chat",
            headers=_auth(token),
            json={
                "message": "Roof Tattoo Sakarya'ya ne teklif vermiştik?",
                "conversation_id": cid,
            },
        )
        assert r1.status_code == 200

    db = SessionLocal()
    try:
        from database import AssistantConversation

        conv = db.query(AssistantConversation).filter(AssistantConversation.id == cid).one()
        ent = get_conversation_active_entity(conv)
        assert ent is not None
        assert ent.lead_id == roof.id
    finally:
        db.close()

    with patch("ai.capabilities.chat.run_tool_loop") as loop2:
        loop2.return_value = (
            "Roof Tattoo için CRM'de doğrulanmış neden yok.",
            {"total_tokens": 5},
            [{"tool": "get_lead"}],
        )
        r2 = client.post(
            "/api/ai/chat",
            headers=_auth(token),
            json={"message": "Peki neden kapanmadı?", "conversation_id": cid},
        )
        assert r2.status_code == 200
        assert loop2.call_args.kwargs["entity_ctx"]["entity"].lead_id == roof.id
    _cleanup(user.id)


def test_k_streaming_entity_bind(client):
    token, user, roof, _ = _make_owner_with_leads()
    db = SessionLocal()
    try:
        conv = create_conversation(db, organization_id=user.id, user_id=user.id, title="s")
        set_conversation_active_entity(
            db, conv, ActiveEntity("lead", roof.id, "Roof Tattoo Sakarya")
        )
        db.commit()
        cid = conv.id
    finally:
        db.close()

    def _fake_events(*_a, **kw):
        assert kw.get("entity_ctx", {}).get("bind_for_tools") is True
        assert kw["entity_ctx"]["entity"].lead_id == roof.id
        yield {"type": "tool_start", "tool": "get_lead", "status": "x"}
        yield {"type": "tool_done", "tool": "get_lead", "status": "y"}
        yield {"type": "delta", "content": "Roof Tattoo "}
        yield {"type": "_internal_done", "reply": "Roof Tattoo için CRM'de neden yok.", "usage": {}}

    with patch("ai.capabilities.chat_stream.iter_tool_aware_chat_events", side_effect=_fake_events):
        with client.stream(
            "POST",
            "/api/ai/chat/stream",
            headers=_auth(token),
            json={"message": "Son aktivitesi ne?", "conversation_id": cid},
        ) as resp:
            assert resp.status_code == 200
            body = "".join(resp.iter_text())
    assert "tool_start" in body and "done" in body
    _cleanup(user.id)


def test_l_conversation_reload_preserves_entity():
    _token, user, roof, _ = _make_owner_with_leads()
    db = SessionLocal()
    try:
        conv = create_conversation(db, organization_id=user.id, user_id=user.id, title="reload")
        set_conversation_active_entity(
            db, conv, ActiveEntity("lead", roof.id, "Roof Tattoo Sakarya")
        )
        db.commit()
        cid = conv.id
        org = user.id
    finally:
        db.close()

    db2 = SessionLocal()
    try:
        from database import AssistantConversation

        live = db2.query(AssistantConversation).filter(AssistantConversation.id == cid).one()
        ent = get_conversation_active_entity(live)
        assert ent and ent.lead_id == roof.id
        res = resolve_conversational_entity(
            db2,
            org_id=org,
            conversation=live,
            user_message="Peşinden ne yapmalıyım?",
        )
        # "Peşinden" is implicit follow-up → still bound
        assert res.bind_for_tools and res.entity and res.entity.lead_id == roof.id
    finally:
        db2.close()
        _cleanup(user.id)


def test_m_n_no_crm_or_aiaction_mutation(client):
    token, user, roof, _ = _make_owner_with_leads()
    db = SessionLocal()
    try:
        leads_before = db.query(Lead).filter(Lead.user_id == user.id).count()
        acts_before = db.query(LeadActivity).filter(LeadActivity.user_id == user.id).count()
        actions_before = db.query(AiAction).filter(AiAction.organization_id == user.id).count()
        conv = create_conversation(db, organization_id=user.id, user_id=user.id, title="mut")
        set_conversation_active_entity(
            db, conv, ActiveEntity("lead", roof.id, "Roof Tattoo Sakarya")
        )
        db.commit()
        cid = conv.id
    finally:
        db.close()

    with patch("ai.capabilities.chat.run_tool_loop") as loop:
        loop.return_value = ("ok", {"total_tokens": 3}, [])
        client.post(
            "/api/ai/chat",
            headers=_auth(token),
            json={"message": "Peki neden kapanmadı?", "conversation_id": cid},
        )

    db = SessionLocal()
    try:
        assert db.query(Lead).filter(Lead.user_id == user.id).count() == leads_before
        assert db.query(LeadActivity).filter(LeadActivity.user_id == user.id).count() == acts_before
        assert db.query(AiAction).filter(AiAction.organization_id == user.id).count() == actions_before
    finally:
        db.close()
        _cleanup(user.id)


def test_execute_bound_tool_rewrites_search():
    _token, user, roof, _ = _make_owner_with_leads()
    db = SessionLocal()
    try:
        ctx = {
            "entity": ActiveEntity("lead", roof.id, "Roof Tattoo Sakarya"),
            "bind_for_tools": True,
            "user_message": "Peki neden kapanmadı?",
            "dirty": False,
        }
        name, args, result = _execute_bound_tool(
            db,
            user.id,
            name="search_leads",
            args={"query": "başka bir şey"},
            entity_ctx=ctx,
        )
        assert name == "get_lead"
        assert args["lead_id"] == roof.id
        assert result.get("ok") is True
        assert ctx["dirty"] is True
        assert ctx["entity"].lead_id == roof.id
    finally:
        db.close()
        _cleanup(user.id)
