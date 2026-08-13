"""DE-6.9 — pending-offer tool consistency (portfolio vs daily brief)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from ai.capabilities.chat_tools import SYSTEM_TOOLS, build_chat_messages, run_tool_loop
from ai.conversations_store import create_conversation
from ai.crm_tools import get_daily_sales_brief, get_pending_offers, lead_has_pending_offer_signal
from ai.entity_continuity import (
    ActiveEntity,
    is_pending_offers_portfolio_intent,
    resolve_conversational_entity,
    set_conversation_active_entity,
)
from database import AiAction, Lead, LeadActivity, SessionLocal, User
from migrate_auth import run_migrations
from security import hash_password


def _make_owner() -> User:
    db = SessionLocal()
    try:
        run_migrations(db)
        username = f"de69p_{uuid.uuid4().hex[:10]}"
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
        return user
    finally:
        db.close()


def _cleanup(org_id: int) -> None:
    db = SessionLocal()
    try:
        db.query(LeadActivity).filter(LeadActivity.user_id == org_id).delete(synchronize_session=False)
        db.query(Lead).filter(Lead.user_id == org_id).delete(synchronize_session=False)
        db.query(AiAction).filter(AiAction.organization_id == org_id).delete(synchronize_session=False)
        db.query(User).filter(User.id == org_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def org_a():
    user = _make_owner()
    yield user
    _cleanup(user.id)


def _counts(org_id: int) -> dict:
    db = SessionLocal()
    try:
        return {
            "leads": db.query(Lead).filter(Lead.user_id == org_id).count(),
            "activities": db.query(LeadActivity).filter(LeadActivity.user_id == org_id).count(),
            "ai_actions": db.query(AiAction).filter(AiAction.organization_id == org_id).count(),
        }
    finally:
        db.close()


def _add_lead(org_id: int, **kwargs) -> Lead:
    db = SessionLocal()
    try:
        lead = Lead(
            user_id=org_id,
            category=kwargs.get("category", "tattoo"),
            isletme_adi=kwargs.get("isletme_adi", "Test Biz"),
            sehir=kwargs.get("sehir", "Sakarya"),
            durum=kwargs.get("durum", "Demo Gönderildi"),
            oncelik=kwargs.get("oncelik", "orta"),
            teklif=kwargs.get("teklif", ""),
            satis_tutari=kwargs.get("satis_tutari", 0),
            intelligence_score=kwargs.get("intelligence_score", 70),
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        return lead
    finally:
        db.close()


def _add_activity(org_id: int, lead_id: int, *, days_ago: int = 5) -> None:
    db = SessionLocal()
    try:
        db.add(
            LeadActivity(
                user_id=org_id,
                lead_id=lead_id,
                activity_type="teklif_verildi",
                title="teklif_verildi",
                description="8500 TL",
                activity_date=datetime.utcnow() - timedelta(days=days_ago),
            )
        )
        db.commit()
    finally:
        db.close()


def _tool_call(name: str, args: dict, call_id: str = "c1"):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
        ],
    }


def test_intent_pending_portfolio_vs_entity_scoped():
    assert is_pending_offers_portfolio_intent("Bekleyen teklifler neler?")
    assert is_pending_offers_portfolio_intent("Bekleyen teklifler var mı?")
    assert is_pending_offers_portfolio_intent("Hangi teklifler bekliyor?")
    assert is_pending_offers_portfolio_intent("Teklif verip satış yapmadığımız müşteriler?")
    assert is_pending_offers_portfolio_intent("Açık teklifler neler?")
    assert is_pending_offers_portfolio_intent("Satışa dönüşmeyen teklifler?")
    assert is_pending_offers_portfolio_intent("Hangi müşterilere teklif verdik?")
    assert is_pending_offers_portfolio_intent("Bekleyen teklifleri göster")
    assert not is_pending_offers_portfolio_intent("Bugün ne yapmalıyım?")
    assert not is_pending_offers_portfolio_intent("Hakan'ın bekleyen teklifi var mı?")
    assert not is_pending_offers_portfolio_intent("Roof Tattoo'nun bekleyen teklifi ne?")
    assert not is_pending_offers_portfolio_intent("Peki onun teklifi neydi?")


def test_unit_pending_offers_demo_gonderildi_with_teklif(org_a):
    user = org_a
    roof = _add_lead(
        user.id,
        isletme_adi="Roof Tattoo Sakarya",
        teklif="8500 TL",
        durum="Demo Gönderildi",
    )
    _add_lead(user.id, isletme_adi="Hakan Çapa Kuaför", teklif="", durum="Demo Gönderildi")
    _add_activity(user.id, roof.id, days_ago=10)
    before = _counts(user.id)
    db = SessionLocal()
    try:
        live = db.query(Lead).filter(Lead.id == roof.id).one()
        assert lead_has_pending_offer_signal(live) is True
        pending = get_pending_offers(db, user.id, limit=10)
        assert pending["count"] >= 1
        hit = next(x for x in pending["offers"] if x["lead_id"] == roof.id)
        assert "8500" in (hit.get("offer_text") or "")
        assert hit["business_name"] == "Roof Tattoo Sakarya"
        assert all(x["business_name"] != "Hakan Çapa Kuaför" for x in pending["offers"])
        brief = get_daily_sales_brief(db, user.id, limit=8)
        assert brief["summary"]["pending_offer_count"] == pending["count"]
    finally:
        db.close()
    assert _counts(user.id) == before


def test_direct_chat_must_call_get_pending_offers(org_a):
    user = org_a
    roof = _add_lead(
        user.id,
        isletme_adi="Roof Tattoo Sakarya",
        teklif="8500 TL",
        durum="Demo Gönderildi",
    )
    _add_activity(user.id, roof.id, days_ago=8)
    state = {"step": 0}
    choices: list = []

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        choices.append(tool_choice)
        if state["step"] == 1:
            # Model tries to answer without tools — force/fallback must still run CRM tool.
            return {"role": "assistant", "content": "Bekleyen teklif görünmüyor."}, {"total_tokens": 3}
        blob = " ".join(str(m.get("content") or "") for m in messages if m.get("role") == "tool")
        assert "Roof Tattoo" in blob and "8500" in blob
        return (
            {"role": "assistant", "content": "Bekleyen teklif: Roof Tattoo Sakarya — 8500 TL."},
            {"total_tokens": 5},
        )

    db = SessionLocal()
    try:
        with patch("ai.capabilities.chat_tools.assert_llm_configured"), patch(
            "ai.capabilities.chat_tools.chat_completion_messages_with_tools", side_effect=fake_llm
        ):
            reply, _u, trace = run_tool_loop(
                db,
                org_id=user.id,
                messages=build_chat_messages(
                    locale="tr",
                    history=[
                        {"role": "user", "content": "Bugün ne yapmalıyım?"},
                        {"role": "assistant", "content": "Özet: tek bekleyen teklif var."},
                    ],
                    user_message="Bekleyen teklifler neler?",
                ),
            )
        assert trace[0]["tool"] == "get_pending_offers"
        assert "Roof Tattoo" in reply
        assert "8500" in reply
        assert isinstance(choices[0], dict)
        assert choices[0]["function"]["name"] == "get_pending_offers"
    finally:
        db.close()


def test_zero_pending_only_when_tool_empty(org_a):
    user = org_a
    _add_lead(
        user.id,
        isletme_adi="Closed Co",
        teklif="1000 TL",
        durum="Müşteri",
        satis_tutari=1000,
    )
    state = {"step": 0}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        if state["step"] == 1:
            return _tool_call("get_pending_offers", {}, "1"), {"total_tokens": 2}
        tool_blob = " ".join(str(m.get("content") or "") for m in messages if m.get("role") == "tool")
        compact = tool_blob.replace(" ", "")
        assert '"count":0' in compact
        return {"role": "assistant", "content": "Bekleyen teklif görünmüyor."}, {"total_tokens": 3}

    db = SessionLocal()
    try:
        with patch("ai.capabilities.chat_tools.assert_llm_configured"), patch(
            "ai.capabilities.chat_tools.chat_completion_messages_with_tools", side_effect=fake_llm
        ):
            reply, _u, trace = run_tool_loop(
                db,
                org_id=user.id,
                messages=[{"role": "user", "content": "Bekleyen teklifler neler?"}],
            )
        assert trace[0]["tool"] == "get_pending_offers"
        assert "görünmüyor" in reply.lower() or "yok" in reply.lower()
    finally:
        db.close()


def test_daily_brief_consistent_with_pending(org_a):
    user = org_a
    roof = _add_lead(
        user.id,
        isletme_adi="Roof Tattoo Sakarya",
        teklif="8500 TL",
        durum="Demo Gönderildi",
        intelligence_score=88,
    )
    _add_activity(user.id, roof.id, days_ago=12)
    db = SessionLocal()
    try:
        pending = get_pending_offers(db, user.id, limit=10)
        brief = get_daily_sales_brief(db, user.id, limit=8)
        assert brief["summary"]["pending_offer_count"] == pending["count"]
        assert brief["summary"]["empty_pending_offers"] is (pending["count"] == 0)
        assert any(o.get("lead_id") == roof.id for o in pending["offers"])
    finally:
        db.close()


def test_active_hakan_does_not_scope_portfolio_pending(org_a):
    user = org_a
    roof = _add_lead(
        user.id,
        isletme_adi="Roof Tattoo Sakarya",
        teklif="8500 TL",
        durum="Demo Gönderildi",
    )
    hakan = _add_lead(user.id, isletme_adi="Hakan Çapa Kuaför", teklif="", durum="Demo Gönderildi")
    _add_activity(user.id, roof.id, days_ago=9)
    db = SessionLocal()
    try:
        conv = create_conversation(db, organization_id=user.id, user_id=user.id, title="t")
        set_conversation_active_entity(
            db, conv, ActiveEntity("lead", hakan.id, "Hakan Çapa Kuaför")
        )
        db.commit()
        res = resolve_conversational_entity(
            db,
            org_id=user.id,
            conversation=conv,
            user_message="Bekleyen teklifler neler?",
        )
        assert res.bind_for_tools is False
        pending = get_pending_offers(db, user.id, limit=10)
        assert any(x["lead_id"] == roof.id for x in pending["offers"])
    finally:
        db.close()


def test_prompt_requires_pending_tool():
    assert "get_pending_offers" in SYSTEM_TOOLS
    assert "MUTLAKA get_pending_offers" in SYSTEM_TOOLS
    assert "get_daily_sales_brief bu sorular için yeterli DEĞİL" in SYSTEM_TOOLS


def test_no_mutation_on_pending_tools(org_a):
    user = org_a
    _add_lead(user.id, isletme_adi="Roof Tattoo Sakarya", teklif="8500 TL", durum="Demo Gönderildi")
    before = _counts(user.id)
    db = SessionLocal()
    try:
        get_pending_offers(db, user.id, limit=5)
        get_daily_sales_brief(db, user.id, limit=5)
    finally:
        db.close()
    assert _counts(user.id) == before
