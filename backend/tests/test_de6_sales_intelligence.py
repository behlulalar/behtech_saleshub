"""DE-6.4 — Sales Intelligence Assistant tests (mock LLM)."""

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
    get_lead_offer,
    get_pending_offers,
    search_leads,
)
from database import AiAction, Lead, LeadActivity, SessionLocal, User
from migrate_auth import run_migrations
from security import hash_password


def _make_owner() -> User:
    db = SessionLocal()
    try:
        run_migrations(db)
        username = f"de64_{uuid.uuid4().hex[:10]}"
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
            notlar=kwargs.get("notlar", ""),
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
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": __import__("json").dumps(args)},
            }
        ],
    }


def test_prompt_has_factuality_rules():
    assert "FACTUALITY" in SYSTEM_TOOLS or "Gerçeklik" in SYSTEM_TOOLS
    assert "Uydurma" in SYSTEM_TOOLS or "UYDURMA" in SYSTEM_TOOLS.upper() or "uydurma" in SYSTEM_TOOLS
    assert "ambiguous" in SYSTEM_TOOLS.lower() or "eşleşme" in SYSTEM_TOOLS.lower()
    msgs = build_chat_messages(locale="tr", history=[], user_message="test", context_json=None)
    assert msgs[0]["role"] == "system"
    assert "READ-ONLY" in msgs[0]["content"] or "read-only" in msgs[0]["content"].lower() or "okuma" in msgs[0]["content"].lower()


def test_a_roof_tattoo_offer(org_a):
    user = org_a
    lead = _add_lead(user.id, isletme_adi="Roof Tattoo Sakarya", teklif="8500 TL", durum="Demo Gönderildi")
    _add_activity(user.id, lead.id, activity_type="teklif_verildi", description="8500 TL", days_ago=30)
    before = _counts(user.id)
    state = {"step": 0}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        if state["step"] == 1:
            return _tool_call("search_leads", {"query": "Roof Tattoo Sakarya"}, "1"), {"total_tokens": 5}
        if state["step"] == 2:
            return _tool_call("get_lead_offer", {"lead_id": lead.id}, "2"), {"total_tokens": 5}
        return (
            {"role": "assistant", "content": "CRM kaydına göre Roof Tattoo'ya 8500 TL teklif verilmiş."},
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
                    user_message="Roof Tattoo Sakarya'ya ne teklif vermiştik?",
                ),
            )
        assert [t["tool"] for t in trace] == ["search_leads", "get_lead_offer"]
        assert "8500" in reply
        assert "15.000" not in reply and "15000" not in reply.replace(".", "")
        offer = get_lead_offer(db, user.id, lead_id=lead.id)
        assert offer["offer_text"] == "8500 TL"
    finally:
        db.close()
    assert _counts(user.id) == before


def test_b_followup_why_not_closed_uses_activities(org_a):
    user = org_a
    lead = _add_lead(user.id, isletme_adi="Roof Tattoo Sakarya", teklif="8500 TL")
    _add_activity(user.id, lead.id, activity_type="diger", description="DE-4 takip", days_ago=2)
    state = {"step": 0}
    tools_seen: list[str] = []

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        if state["step"] == 1:
            tools_seen.append("search_leads")
            return _tool_call("search_leads", {"query": "Roof Tattoo"}, "1"), {"total_tokens": 4}
        if state["step"] == 2:
            tools_seen.append("get_lead")
            return _tool_call("get_lead", {"lead_id": lead.id}, "2"), {"total_tokens": 4}
        if state["step"] == 3:
            tools_seen.append("get_lead_activities")
            return _tool_call("get_lead_activities", {"lead_id": lead.id}, "3"), {"total_tokens": 4}
        return (
            {
                "role": "assistant",
                "content": (
                    "CRM'de kapanmama nedenini doğrudan belirten bir kayıt yok. "
                    "Son aktivite yakın zamanda görünüyor ve satışa geçtiğine dair kayıt bulunmuyor."
                ),
            },
            {"total_tokens": 10},
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
                        {"role": "user", "content": "Roof Tattoo'ya ne teklif vermiştik?"},
                        {"role": "assistant", "content": "8500 TL."},
                    ],
                    user_message="Peki neden hâlâ kapanmadı?",
                ),
            )
        assert "get_lead_activities" in [t["tool"] for t in trace]
        assert "fiyatı yüksek" not in reply.lower()
        assert "kayıt yok" in reply.lower() or "bulunmuyor" in reply.lower()
    finally:
        db.close()


def test_c_activities(org_a):
    user = org_a
    lead = _add_lead(user.id, isletme_adi="Roof Tattoo Sakarya")
    _add_activity(user.id, lead.id, activity_type="diger", days_ago=2)
    state = {"step": 0}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        if state["step"] == 1:
            return _tool_call("search_leads", {"query": "Roof Tattoo"}, "1"), {"total_tokens": 3}
        if state["step"] == 2:
            return _tool_call("get_lead_activities", {"lead_id": lead.id}, "2"), {"total_tokens": 3}
        return {"role": "assistant", "content": "Son aktivite CRM'de diger olarak kayıtlı."}, {"total_tokens": 5}

    db = SessionLocal()
    try:
        with patch("ai.capabilities.chat_tools.assert_llm_configured"), patch(
            "ai.capabilities.chat_tools.chat_completion_messages_with_tools", side_effect=fake_llm
        ):
            _reply, _u, trace = run_tool_loop(
                db,
                org_id=user.id,
                messages=[{"role": "user", "content": "Roof Tattoo ile en son ne zaman iletişim?"}],
            )
        assert [t["tool"] for t in trace][-1] == "get_lead_activities"
    finally:
        db.close()


def test_d_unknown_lead(org_a):
    user = org_a
    before = _counts(user.id)
    state = {"step": 0}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        if state["step"] == 1:
            return _tool_call("search_leads", {"query": "Google XYZ Sakarya"}, "1"), {"total_tokens": 3}
        return (
            {"role": "assistant", "content": "CRM'de bu bilgi kayıtlı görünmüyor."},
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
                messages=[{"role": "user", "content": "Google XYZ Sakarya'ya ne teklif?"}],
            )
        assert trace[0]["tool"] == "search_leads"
        assert "kayıtlı görünmüyor" in reply.lower() or "bulunamad" in reply.lower() or "yok" in reply.lower()
        assert "8500" not in reply
    finally:
        db.close()
    assert _counts(user.id) == before


def test_e_multiple_matching_leads_ambiguous(org_a):
    user = org_a
    _add_lead(user.id, isletme_adi="Roof Tattoo Merkez", sehir="Sakarya")
    _add_lead(user.id, isletme_adi="Roof Tattoo Akyazı", sehir="Sakarya")
    db = SessionLocal()
    try:
        result = search_leads(db, user.id, query="Roof Tattoo")
        assert result["count"] >= 2
        assert result["ambiguous"] is True
        assert result["clarification_hint"]
    finally:
        db.close()

    state = {"step": 0}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        if state["step"] == 1:
            return _tool_call("search_leads", {"query": "Roof Tattoo"}, "1"), {"total_tokens": 3}
        return (
            {
                "role": "assistant",
                "content": "Roof Tattoo için 2 kayıt buldum. Hangisini kastediyorsunuz?",
            },
            {"total_tokens": 5},
        )

    db = SessionLocal()
    try:
        with patch("ai.capabilities.chat_tools.assert_llm_configured"), patch(
            "ai.capabilities.chat_tools.chat_completion_messages_with_tools", side_effect=fake_llm
        ):
            reply, _u, _t = run_tool_loop(
                db,
                org_id=user.id,
                messages=[{"role": "user", "content": "Roof Tattoo teklifi?"}],
            )
        assert "2" in reply or "Hangisini" in reply
        assert "8500" not in reply  # no invented single offer
    finally:
        db.close()


def test_f_sales_metrics(org_a):
    user = org_a
    state = {"step": 0}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        if state["step"] == 1:
            return _tool_call("get_sales_metrics", {"period": "month"}, "1"), {"total_tokens": 3}
        return {"role": "assistant", "content": "Bu ay CRM metriklerine göre satış özeti hazır."}, {"total_tokens": 4}

    db = SessionLocal()
    try:
        with patch("ai.capabilities.chat_tools.assert_llm_configured"), patch(
            "ai.capabilities.chat_tools.chat_completion_messages_with_tools", side_effect=fake_llm
        ):
            _r, _u, trace = run_tool_loop(
                db, org_id=user.id, messages=[{"role": "user", "content": "Bu ay satışlar nasıl?"}]
            )
        assert trace[0]["tool"] == "get_sales_metrics"
        assert trace[0]["success"] is True
    finally:
        db.close()


def test_g_followup_candidates(org_a):
    user = org_a
    state = {"step": 0}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        if state["step"] == 1:
            return _tool_call("get_followup_candidates", {"limit": 5}, "1"), {"total_tokens": 3}
        return {"role": "assistant", "content": "Takip adayları CRM teşhisinden alındı."}, {"total_tokens": 4}

    db = SessionLocal()
    try:
        with patch("ai.capabilities.chat_tools.assert_llm_configured"), patch(
            "ai.capabilities.chat_tools.chat_completion_messages_with_tools", side_effect=fake_llm
        ):
            _r, _u, trace = run_tool_loop(
                db,
                org_id=user.id,
                messages=[{"role": "user", "content": "Bugün takip etmem gereken leadler?"}],
            )
        assert trace[0]["tool"] == "get_followup_candidates"
    finally:
        db.close()


def test_h_diagnosis_query(org_a):
    user = org_a
    state = {"step": 0}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        if state["step"] == 1:
            return _tool_call("get_diagnoses", {"limit": 5}, "1"), {"total_tokens": 3}
        return {"role": "assistant", "content": "En kritik teşhisler CRM diagnosis çıktısına göre listelendi."}, {
            "total_tokens": 4
        }

    db = SessionLocal()
    try:
        with patch("ai.capabilities.chat_tools.assert_llm_configured"), patch(
            "ai.capabilities.chat_tools.chat_completion_messages_with_tools", side_effect=fake_llm
        ):
            _r, _u, trace = run_tool_loop(
                db, org_id=user.id, messages=[{"role": "user", "content": "En riskli leadler hangileri?"}]
            )
        assert trace[0]["tool"] == "get_diagnoses"
        assert trace[0]["success"] is True
    finally:
        db.close()


def test_i_multi_tool_what_do_we_know(org_a):
    user = org_a
    lead = _add_lead(user.id, isletme_adi="Roof Tattoo Sakarya", teklif="8500 TL")
    _add_activity(user.id, lead.id, activity_type="diger", days_ago=1)
    state = {"step": 0}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        seq = [
            ("search_leads", {"query": "Roof Tattoo"}),
            ("get_lead", {"lead_id": lead.id}),
            ("get_lead_offer", {"lead_id": lead.id}),
            ("get_lead_activities", {"lead_id": lead.id}),
        ]
        if state["step"] <= len(seq):
            name, args = seq[state["step"] - 1]
            return _tool_call(name, args, str(state["step"])), {"total_tokens": 4}
        return (
            {
                "role": "assistant",
                "content": (
                    "Roof Tattoo için CRM'de teklif 8500 TL. Son aktivite mevcut. "
                    "Kapanmama nedeni kayıtlı değil."
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
                messages=[{"role": "user", "content": "Roof Tattoo hakkında elimizde ne biliyorsun?"}],
            )
        names = [t["tool"] for t in trace]
        assert "search_leads" in names
        assert len(names) >= 3
        assert len(names) <= MAX_TOOL_ITERATIONS
        assert "8500" in reply
    finally:
        db.close()


def test_j_k_no_crm_or_aiaction_mutation(org_a):
    user = org_a
    lead = _add_lead(user.id, isletme_adi="Roof Tattoo Sakarya", teklif="8500 TL", durum="Teklif Verildi")
    before = _counts(user.id)
    db = SessionLocal()
    try:
        pending = get_pending_offers(db, user.id, limit=10)
        assert pending["count"] >= 1
        assert any(x["lead_id"] == lead.id for x in pending["offers"])
        wrapped = execute_crm_tool(db, user.id, "get_pending_offers", {"limit": 5})
        assert wrapped["ok"] is True
    finally:
        db.close()
    assert _counts(user.id) == before


def test_l_cross_org_isolation(org_a, org_b):
    lead = _add_lead(org_a.id, isletme_adi="Private Roof")
    db = SessionLocal()
    try:
        w = execute_crm_tool(db, org_b.id, "get_lead", {"lead_id": lead.id})
        assert w["ok"] is False and w["error"] == "not_found"
        w2 = execute_crm_tool(db, org_b.id, "get_pending_offers", {})
        assert w2["ok"] is True
        assert all(x["lead_id"] != lead.id for x in (w2.get("result") or {}).get("offers") or [])
    finally:
        db.close()


def test_m_memory_plus_crm_tools(org_a):
    """Conversation history present + still calls CRM tools for follow-up."""
    user = org_a
    lead = _add_lead(user.id, isletme_adi="Roof Tattoo Sakarya", teklif="8500 TL")
    history = [
        {"role": "user", "content": "Roof Tattoo'ya ne teklif vermiştik?"},
        {"role": "assistant", "content": "8500 TL."},
    ]
    state = {"step": 0}
    saw_history = {"ok": False}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        blob = " ".join(str(m.get("content") or "") for m in messages)
        if "8500" in blob and "Roof Tattoo" in blob:
            saw_history["ok"] = True
        if state["step"] == 1:
            return _tool_call("get_lead_activities", {"lead_id": lead.id}, "1"), {"total_tokens": 4}
        return (
            {
                "role": "assistant",
                "content": "Roof Tattoo bağlamında CRM aktiviteleri kontrol edildi; net kapanmama nedeni yok.",
            },
            {"total_tokens": 6},
        )

    db = SessionLocal()
    try:
        with patch("ai.capabilities.chat_tools.assert_llm_configured"), patch(
            "ai.capabilities.chat_tools.chat_completion_messages_with_tools", side_effect=fake_llm
        ):
            _r, _u, trace = run_tool_loop(
                db,
                org_id=user.id,
                messages=build_chat_messages(
                    locale="tr",
                    history=history,
                    user_message="Peki neden?",
                ),
            )
        assert saw_history["ok"] is True
        assert trace[0]["tool"] == "get_lead_activities"
    finally:
        db.close()


def test_n_no_hallucinated_offer(org_a):
    user = org_a
    lead = _add_lead(user.id, isletme_adi="Roof Tattoo Sakarya", teklif="8500 TL")
    state = {"step": 0}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        if state["step"] == 1:
            return _tool_call("get_lead_offer", {"lead_id": lead.id}, "1"), {"total_tokens": 3}
        # Simulate model that only reports tool fact
        tool_blob = ""
        for m in messages:
            if m.get("role") == "tool":
                tool_blob += str(m.get("content") or "")
        assert "8500" in tool_blob
        assert "15000" not in tool_blob.replace(".", "")
        return {"role": "assistant", "content": "Teklif: 8500 TL (CRM)."}, {"total_tokens": 5}

    db = SessionLocal()
    try:
        with patch("ai.capabilities.chat_tools.assert_llm_configured"), patch(
            "ai.capabilities.chat_tools.chat_completion_messages_with_tools", side_effect=fake_llm
        ):
            reply, _u, _t = run_tool_loop(
                db, org_id=user.id, messages=[{"role": "user", "content": "teklif?"}]
            )
        assert "8500" in reply
        assert "15.000" not in reply
    finally:
        db.close()


def test_o_no_hallucinated_reason_in_prompt_contract():
    assert "YANLIŞ" in SYSTEM_TOOLS
    assert "Fiyatı yüksek bulduğu için almadı" in SYSTEM_TOOLS  # negative example only
    assert "nedenini doğrudan" in SYSTEM_TOOLS
    assert "Unknown" in SYSTEM_TOOLS


def test_pending_offers_rejects_org_arg(org_a):
    user = org_a
    db = SessionLocal()
    try:
        w = execute_crm_tool(db, user.id, "get_pending_offers", {"organization_id": 1})
        assert w["ok"] is False
        assert w["error"] == "forbidden_arg"
    finally:
        db.close()


def test_tool_iteration_hard_cap(org_a):
    user = org_a
    calls = {"n": 0}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        calls["n"] += 1
        if tool_choice == "none":
            return {"role": "assistant", "content": "Limit final"}, {"total_tokens": 2}
        return _tool_call("search_leads", {"query": "x"}, f"c{calls['n']}"), {"total_tokens": 2}

    db = SessionLocal()
    try:
        with patch("ai.capabilities.chat_tools.assert_llm_configured"), patch(
            "ai.capabilities.chat_tools.chat_completion_messages_with_tools", side_effect=fake_llm
        ):
            reply, _u, trace = run_tool_loop(
                db, org_id=user.id, messages=[{"role": "user", "content": "loop"}]
            )
        assert len(trace) == MAX_TOOL_ITERATIONS
        assert reply
    finally:
        db.close()
