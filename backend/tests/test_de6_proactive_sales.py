"""DE-6.6 — Proactive Sales Assistant / Daily Sales Brief tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from ai.capabilities.chat_tools import (
    MAX_TOOL_ITERATIONS,
    SYSTEM_TOOLS,
    build_chat_messages,
    run_tool_loop,
)
from ai.crm_tools import (
    execute_crm_tool,
    get_daily_sales_brief,
    get_pending_offers,
)
from database import AiAction, Lead, LeadActivity, SessionLocal, User
from migrate_auth import run_migrations
from security import hash_password


def _make_owner() -> User:
    db = SessionLocal()
    try:
        run_migrations(db)
        username = f"de66_{uuid.uuid4().hex[:10]}"
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


@pytest.fixture
def org_b():
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
            durum=kwargs.get("durum", "Teklif Verildi"),
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


def _add_activity(org_id: int, lead_id: int, *, activity_type: str, description: str = "", days_ago: int = 2) -> None:
    db = SessionLocal()
    try:
        db.add(
            LeadActivity(
                user_id=org_id,
                lead_id=lead_id,
                activity_type=activity_type,
                title=activity_type,
                description=description,
                activity_date=datetime.utcnow() - timedelta(days=days_ago),
            )
        )
        db.commit()
    finally:
        db.close()


def _tool_call(name: str, args: dict, call_id: str = "c1"):
    import json

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


def test_prompt_daily_brief_and_readonly():
    assert "get_daily_sales_brief" in SYSTEM_TOOLS
    assert "AiAction" in SYSTEM_TOOLS or "mesaj gönderme" in SYSTEM_TOOLS
    assert "%80" in SYSTEM_TOOLS or "olasılık" in SYSTEM_TOOLS
    assert "Bugün ne yapmalıyım" in SYSTEM_TOOLS


def test_a_today_brief_tool(org_a):
    user = org_a
    lead = _add_lead(user.id, isletme_adi="Roof Tattoo Sakarya", teklif="8500 TL", durum="Teklif Verildi")
    _add_activity(user.id, lead.id, activity_type="teklif_verildi", description="8500 TL", days_ago=12)
    before = _counts(user.id)
    state = {"step": 0}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        if state["step"] == 1:
            return _tool_call("get_daily_sales_brief", {"limit": 5}, "1"), {"total_tokens": 5}
        return (
            {
                "role": "assistant",
                "content": (
                    "## Bugünkü önceliklerin\n"
                    "1. Roof Tattoo Sakarya — bekleyen teklif 8500 TL\n"
                    "Öneri: tekrar iletişime geçmeni öneririm."
                ),
            },
            {"total_tokens": 8},
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
                    history=[],
                    user_message="Bugün ne yapmalıyım?",
                ),
            )
        assert trace[0]["tool"] == "get_daily_sales_brief"
        assert trace[0]["success"] is True
        assert "Roof Tattoo" in reply
        assert "gönderdim" not in reply.lower()
    finally:
        db.close()
    assert _counts(user.id) == before


def test_b_multi_tool_followup_and_offers(org_a):
    user = org_a
    lead = _add_lead(user.id, isletme_adi="Stale Offer Co", teklif="12000 TL", durum="Teklif Verildi")
    _add_activity(user.id, lead.id, activity_type="teklif_verildi", days_ago=20)
    state = {"step": 0}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        if state["step"] == 1:
            return _tool_call("get_followup_candidates", {"limit": 5}, "1"), {"total_tokens": 3}
        if state["step"] == 2:
            return _tool_call("get_pending_offers", {"limit": 5}, "2"), {"total_tokens": 3}
        return (
            {"role": "assistant", "content": "Takip ve bekleyen teklif adayları CRM'den listelendi."},
            {"total_tokens": 4},
        )

    db = SessionLocal()
    try:
        with patch("ai.capabilities.chat_tools.assert_llm_configured"), patch(
            "ai.capabilities.chat_tools.chat_completion_messages_with_tools", side_effect=fake_llm
        ):
            _r, _u, trace = run_tool_loop(
                db,
                org_id=user.id,
                messages=[{"role": "user", "content": "Bugün takip ve teklif önceliklerim?"}],
            )
        assert [t["tool"] for t in trace] == ["get_followup_candidates", "get_pending_offers"]
        assert all(t["success"] for t in trace)
    finally:
        db.close()


def test_c_diagnosis_integration(org_a):
    user = org_a
    state = {"step": 0}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        if state["step"] == 1:
            return _tool_call("get_diagnoses", {"limit": 5}, "1"), {"total_tokens": 3}
        return (
            {"role": "assistant", "content": "Kritik diagnosis CRM çıktısına göre özetlendi."},
            {"total_tokens": 4},
        )

    db = SessionLocal()
    try:
        with patch("ai.capabilities.chat_tools.assert_llm_configured"), patch(
            "ai.capabilities.chat_tools.chat_completion_messages_with_tools", side_effect=fake_llm
        ):
            _r, _u, trace = run_tool_loop(
                db,
                org_id=user.id,
                messages=[{"role": "user", "content": "En kritik leadler hangileri?"}],
            )
        assert trace[0]["tool"] == "get_diagnoses"
    finally:
        db.close()


def test_d_sales_metrics(org_a):
    user = org_a
    state = {"step": 0}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        if state["step"] == 1:
            return _tool_call("get_sales_metrics", {"period": "month"}, "1"), {"total_tokens": 3}
        return {"role": "assistant", "content": "Bu ay satış metrikleri CRM'den alındı."}, {"total_tokens": 4}

    db = SessionLocal()
    try:
        with patch("ai.capabilities.chat_tools.assert_llm_configured"), patch(
            "ai.capabilities.chat_tools.chat_completion_messages_with_tools", side_effect=fake_llm
        ):
            _r, _u, trace = run_tool_loop(
                db, org_id=user.id, messages=[{"role": "user", "content": "Bu ay satışlar nasıl?"}]
            )
        assert trace[0]["tool"] == "get_sales_metrics" and trace[0]["success"]
    finally:
        db.close()


def test_e_empty_candidates(org_a):
    user = org_a
    db = SessionLocal()
    try:
        brief = get_daily_sales_brief(db, user.id, limit=5)
        assert brief["summary"]["empty_follow_up"] is True or brief["summary"]["follow_up_count"] == 0
        assert brief["summary"]["empty_pending_offers"] is True or brief["summary"]["pending_offer_count"] == 0
        assert brief["priority_count"] == 0
        assert brief["priorities"] == []
    finally:
        db.close()


def test_f_insufficient_data_reply_contract(org_a):
    user = org_a
    state = {"step": 0}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        if state["step"] == 1:
            return _tool_call("get_daily_sales_brief", {"limit": 5}, "1"), {"total_tokens": 3}
        return (
            {
                "role": "assistant",
                "content": (
                    "Şu anda CRM'de follow-up adayı görünmüyor. "
                    "Bekleyen teklif görünmüyor. "
                    "Şu anda aktif diagnosis bulunmuyor."
                ),
            },
            {"total_tokens": 4},
        )

    db = SessionLocal()
    try:
        with patch("ai.capabilities.chat_tools.assert_llm_configured"), patch(
            "ai.capabilities.chat_tools.chat_completion_messages_with_tools", side_effect=fake_llm
        ):
            reply, _u, _t = run_tool_loop(
                db, org_id=user.id, messages=[{"role": "user", "content": "Bugün ne yapmalıyım?"}]
            )
        assert "görünmüyor" in reply.lower() or "bulunmuyor" in reply.lower()
        assert "Roof Tattoo" not in reply  # no fake lead
    finally:
        db.close()


def test_g_no_hallucinated_reason_in_prompt():
    assert "Fiyatı yüksek bulduğu için almadı" in SYSTEM_TOOLS
    assert "YANLIŞ" in SYSTEM_TOOLS


def test_h_no_hallucinated_probability_in_prompt():
    assert "%80" in SYSTEM_TOOLS
    assert "yüzde" in SYSTEM_TOOLS.lower() or "olasılık" in SYSTEM_TOOLS


def test_i_conversation_followup(org_a):
    user = org_a
    lead = _add_lead(user.id, isletme_adi="Roof Tattoo Sakarya", teklif="8500 TL")
    history = [
        {"role": "user", "content": "Bugün ne yapmalıyım?"},
        {"role": "assistant", "content": "1. Roof Tattoo Sakarya — bekleyen teklif"},
    ]
    state = {"step": 0}
    saw = {"hist": False}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        blob = " ".join(str(m.get("content") or "") for m in messages)
        if "Roof Tattoo" in blob and "Bugün" in blob:
            saw["hist"] = True
        if state["step"] == 1:
            return _tool_call("get_lead_offer", {"lead_id": lead.id}, "1"), {"total_tokens": 3}
        return {"role": "assistant", "content": "CRM kaydına göre teklif 8500 TL."}, {"total_tokens": 5}

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
                    history=history,
                    user_message="İlk sıradakine ne teklif vermiştik?",
                ),
            )
        assert saw["hist"] is True
        assert trace[0]["tool"] == "get_lead_offer"
        assert "8500" in reply
    finally:
        db.close()


def test_j_k_mutations_zero(org_a):
    user = org_a
    lead = _add_lead(user.id, isletme_adi="Roof Tattoo Sakarya", teklif="8500 TL", durum="Teklif Verildi")
    _add_activity(user.id, lead.id, activity_type="teklif_verildi", days_ago=10)
    before = _counts(user.id)
    db = SessionLocal()
    try:
        brief = get_daily_sales_brief(db, user.id, limit=8)
        assert brief["priority_count"] >= 1
        pending = get_pending_offers(db, user.id, limit=5)
        assert pending["count"] >= 1
        w = execute_crm_tool(db, user.id, "get_daily_sales_brief", {"limit": 5})
        assert w["ok"] is True
    finally:
        db.close()
    assert _counts(user.id) == before


def test_l_cross_org(org_a, org_b):
    lead = _add_lead(org_a.id, isletme_adi="Private Brief Lead", teklif="1 TL", durum="Teklif Verildi")
    db = SessionLocal()
    try:
        brief_b = get_daily_sales_brief(db, org_b.id, limit=10)
        assert all(p.get("lead_id") != lead.id for p in brief_b.get("priorities") or [])
        w = execute_crm_tool(db, org_b.id, "get_lead", {"lead_id": lead.id})
        assert w["ok"] is False and w["error"] == "not_found"
        w2 = execute_crm_tool(db, org_b.id, "get_daily_sales_brief", {"organization_id": org_a.id})
        assert w2["ok"] is False and w2["error"] == "forbidden_arg"
    finally:
        db.close()


def test_m_max_tool_iterations(org_a):
    user = org_a
    calls = {"n": 0}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        calls["n"] += 1
        if tool_choice == "none":
            return {"role": "assistant", "content": "Limit"}, {"total_tokens": 1}
        return _tool_call("get_followup_candidates", {}, f"c{calls['n']}"), {"total_tokens": 1}

    db = SessionLocal()
    try:
        with patch("ai.capabilities.chat_tools.assert_llm_configured"), patch(
            "ai.capabilities.chat_tools.chat_completion_messages_with_tools", side_effect=fake_llm
        ):
            _r, _u, trace = run_tool_loop(
                db, org_id=user.id, messages=[{"role": "user", "content": "loop"}]
            )
        assert len(trace) == MAX_TOOL_ITERATIONS == 6
    finally:
        db.close()


def test_n_de64_offer_regression(org_a):
    user = org_a
    lead = _add_lead(user.id, isletme_adi="Roof Tattoo Sakarya", teklif="8500 TL")
    state = {"step": 0}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        if state["step"] == 1:
            return _tool_call("search_leads", {"query": "Roof Tattoo"}, "1"), {"total_tokens": 2}
        if state["step"] == 2:
            return _tool_call("get_lead_offer", {"lead_id": lead.id}, "2"), {"total_tokens": 2}
        return {"role": "assistant", "content": "CRM kaydına göre 8500 TL teklif."}, {"total_tokens": 3}

    db = SessionLocal()
    try:
        with patch("ai.capabilities.chat_tools.assert_llm_configured"), patch(
            "ai.capabilities.chat_tools.chat_completion_messages_with_tools", side_effect=fake_llm
        ):
            reply, _u, trace = run_tool_loop(
                db,
                org_id=user.id,
                messages=[{"role": "user", "content": "Roof Tattoo'ya ne teklif vermiştik?"}],
            )
        assert [t["tool"] for t in trace] == ["search_leads", "get_lead_offer"]
        assert "8500" in reply
        assert "15.000" not in reply
    finally:
        db.close()


def test_brief_priority_includes_pending_offer(org_a):
    user = org_a
    lead = _add_lead(
        user.id,
        isletme_adi="Roof Tattoo Sakarya",
        teklif="8500 TL",
        durum="Teklif Verildi",
        intelligence_score=90,
    )
    _add_activity(user.id, lead.id, activity_type="teklif_verildi", days_ago=15)
    db = SessionLocal()
    try:
        brief = get_daily_sales_brief(db, user.id, limit=5)
        names = [p.get("business_name") for p in brief["priorities"]]
        assert "Roof Tattoo Sakarya" in names
        assert brief["summary"]["pending_offer_count"] >= 1
        assert "sales_metrics" in brief
        # May surface via follow_up/diagnosis first; pending list still populated.
        pending = get_pending_offers(db, user.id, limit=5)
        assert any(x["lead_id"] == lead.id for x in pending["offers"])
    finally:
        db.close()
