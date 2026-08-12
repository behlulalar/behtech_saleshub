"""DE-6.2 — read-only CRM tool layer tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ai.capabilities.chat_tools import MAX_TOOL_ITERATIONS, run_tool_loop
from ai.crm_tools import (
    execute_crm_tool,
    get_diagnosis,
    get_diagnoses,
    get_followup_candidates,
    get_lead,
    get_lead_activities,
    get_lead_offer,
    get_sales_metrics,
    search_leads,
)
from auth import create_access_token
from database import AiAction, Lead, LeadActivity, SessionLocal, User
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
        username = f"de62_{uuid.uuid4().hex[:10]}"
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
        db.query(LeadActivity).filter(LeadActivity.user_id == org_id).delete(synchronize_session=False)
        db.query(Lead).filter(Lead.user_id == org_id).delete(synchronize_session=False)
        db.query(AiAction).filter(AiAction.organization_id == org_id).delete(synchronize_session=False)
        db.query(User).filter(User.id == org_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def org_a():
    token, user = _make_owner()
    yield token, user
    _cleanup(user.id)


@pytest.fixture
def org_b():
    token, user = _make_owner()
    yield token, user
    _cleanup(user.id)


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
        lead_id = lead.id
        return lead
    finally:
        db.close()


def _add_activity(org_id: int, lead_id: int, *, activity_type: str, description: str = "") -> None:
    db = SessionLocal()
    try:
        db.add(
            LeadActivity(
                user_id=org_id,
                lead_id=lead_id,
                activity_type=activity_type,
                title=activity_type,
                description=description,
                activity_date=datetime.utcnow() - timedelta(days=2),
            )
        )
        db.commit()
    finally:
        db.close()


def test_search_leads_success(org_a):
    _token, user = org_a
    lead = _add_lead(user.id, isletme_adi="Roof Tattoo Sakarya", sehir="Sakarya")
    db = SessionLocal()
    try:
        result = search_leads(db, user.id, query="Roof Tattoo")
        assert result["count"] >= 1
        assert any(x["lead_id"] == lead.id for x in result["leads"])
        assert "business_name" in result["leads"][0]
        assert "whatsapp" not in result["leads"][0]
    finally:
        db.close()


def test_search_leads_no_result(org_a):
    _token, user = org_a
    db = SessionLocal()
    try:
        result = search_leads(db, user.id, query="zzz_no_such_business_xyz")
        assert result["count"] == 0
        assert result["leads"] == []
    finally:
        db.close()


def test_get_lead_success(org_a):
    _token, user = org_a
    lead = _add_lead(user.id, isletme_adi="Demo Shop", teklif="12.000 TL paket")
    db = SessionLocal()
    try:
        out = get_lead(db, user.id, lead_id=lead.id)
        assert out["lead_id"] == lead.id
        assert out["business_name"] == "Demo Shop"
        assert out["offer_text"] == "12.000 TL paket"
    finally:
        db.close()


def test_get_lead_unknown(org_a):
    _token, user = org_a
    db = SessionLocal()
    try:
        wrapped = execute_crm_tool(db, user.id, "get_lead", {"lead_id": 999999})
        assert wrapped["ok"] is False
        assert wrapped["error"] == "not_found"
    finally:
        db.close()


def test_get_lead_offer_success(org_a):
    _token, user = org_a
    lead = _add_lead(user.id, isletme_adi="Offer Co", teklif="8500 TL")
    _add_activity(user.id, lead.id, activity_type="teklif_verildi", description="8500 TL yıllık")
    db = SessionLocal()
    try:
        out = get_lead_offer(db, user.id, lead_id=lead.id)
        assert out["lead_id"] == lead.id
        assert out["offer_text"] == "8500 TL"
        assert out["offer_date"] is not None
        assert out["latest_offer_activity"] is not None
        assert out["offer_amount"] is None  # no numeric offer field
    finally:
        db.close()


def test_get_lead_offer_missing(org_a):
    _token, user = org_a
    lead = _add_lead(user.id, isletme_adi="No Offer", teklif="")
    db = SessionLocal()
    try:
        out = get_lead_offer(db, user.id, lead_id=lead.id)
        assert out["offer_text"] is None
        assert out["offer_date"] is None
        assert out["latest_offer_activity"] is None
    finally:
        db.close()


def test_get_lead_activities(org_a):
    _token, user = org_a
    lead = _add_lead(user.id, isletme_adi="Act Co")
    _add_activity(user.id, lead.id, activity_type="arama", description="Arandı")
    _add_activity(user.id, lead.id, activity_type="teklif_verildi", description="Teklif")
    db = SessionLocal()
    try:
        out = get_lead_activities(db, user.id, lead_id=lead.id, limit=5)
        assert out["count"] == 2
        assert "activity_type" in out["activities"][0]
    finally:
        db.close()


def test_sales_metrics(org_a):
    _token, user = org_a
    db = SessionLocal()
    try:
        out = get_sales_metrics(db, user.id, period="month")
        assert "sales_count" in out or "won_count" in out
        assert out["period"] == "month"
    finally:
        db.close()


def test_followup_candidates(org_a):
    _token, user = org_a
    db = SessionLocal()
    try:
        out = get_followup_candidates(db, user.id, limit=5)
        assert "candidates" in out
        assert isinstance(out["candidates"], list)
    finally:
        db.close()


def test_diagnosis_tools(org_a):
    _token, user = org_a
    db = SessionLocal()
    try:
        listed = get_diagnoses(db, user.id, limit=5)
        assert "diagnoses" in listed
        if listed["count"] > 0:
            did = listed["diagnoses"][0]["diagnosis_id"]
            one = get_diagnosis(db, user.id, diagnosis_id=did)
            assert one["diagnosis_id"] == did
        else:
            wrapped = execute_crm_tool(db, user.id, "get_diagnosis", {"diagnosis_id": "nope"})
            assert wrapped["ok"] is False
    finally:
        db.close()


def test_cross_org_lead_access(org_a, org_b):
    _ta, user_a = org_a
    _tb, user_b = org_b
    lead = _add_lead(user_a.id, isletme_adi="Private Lead")
    db = SessionLocal()
    try:
        wrapped = execute_crm_tool(db, user_b.id, "get_lead", {"lead_id": lead.id})
        assert wrapped["ok"] is False
        assert wrapped["error"] == "not_found"
        search = search_leads(db, user_b.id, query="Private Lead")
        assert all(x["lead_id"] != lead.id for x in search["leads"])
    finally:
        db.close()


def test_org_id_arg_rejected(org_a):
    _token, user = org_a
    lead = _add_lead(user.id, isletme_adi="Safe")
    db = SessionLocal()
    try:
        wrapped = execute_crm_tool(
            db,
            user.id,
            "get_lead",
            {"lead_id": lead.id, "organization_id": 999},
        )
        assert wrapped["ok"] is False
        assert wrapped["error"] == "forbidden_arg"
    finally:
        db.close()


def test_tool_exception_invalid_args(org_a):
    _token, user = org_a
    db = SessionLocal()
    try:
        wrapped = execute_crm_tool(db, user.id, "get_lead", {})
        assert wrapped["ok"] is False
        assert wrapped["error"] in ("invalid_args", "not_found")
    finally:
        db.close()


def test_tool_iteration_limit(org_a):
    _token, user = org_a
    calls = {"n": 0}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        calls["n"] += 1
        if tool_choice == "none":
            return {"role": "assistant", "content": "Limit final"}, {"total_tokens": 10}
        # Always request another tool to force limit
        return (
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": f"call_{calls['n']}",
                        "type": "function",
                        "function": {
                            "name": "search_leads",
                            "arguments": '{"query":"x"}',
                        },
                    }
                ],
            },
            {"total_tokens": 5},
        )

    db = SessionLocal()
    try:
        with patch("ai.capabilities.chat_tools.assert_llm_configured"), patch(
            "ai.capabilities.chat_tools.chat_completion_messages_with_tools",
            side_effect=fake_llm,
        ):
            reply, _usage, trace = run_tool_loop(
                db,
                org_id=user.id,
                messages=[{"role": "user", "content": "test"}],
            )
        assert len(trace) == MAX_TOOL_ITERATIONS
        assert "Limit" in reply or reply
    finally:
        db.close()


def test_tool_result_final_ai_response(org_a):
    _token, user = org_a
    lead = _add_lead(user.id, isletme_adi="Roof Tattoo Sakarya", teklif="15.000 TL")
    _add_activity(user.id, lead.id, activity_type="teklif_verildi", description="15.000 TL")

    state = {"step": 0}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        if state["step"] == 1:
            return (
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "1",
                            "type": "function",
                            "function": {
                                "name": "search_leads",
                                "arguments": '{"query":"Roof Tattoo Sakarya"}',
                            },
                        }
                    ],
                },
                {"total_tokens": 8},
            )
        if state["step"] == 2:
            return (
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "2",
                            "type": "function",
                            "function": {
                                "name": "get_lead_offer",
                                "arguments": f'{{"lead_id": {lead.id}}}',
                            },
                        }
                    ],
                },
                {"total_tokens": 8},
            )
        return (
            {
                "role": "assistant",
                "content": "Roof Tattoo Sakarya için CRM'de teklif: 15.000 TL kayıtlı.",
            },
            {"total_tokens": 12},
        )

    db = SessionLocal()
    try:
        leads_before = db.query(Lead).filter(Lead.user_id == user.id).count()
        acts_before = db.query(LeadActivity).filter(LeadActivity.user_id == user.id).count()
        actions_before = db.query(AiAction).filter(AiAction.organization_id == user.id).count()

        with patch("ai.capabilities.chat_tools.assert_llm_configured"), patch(
            "ai.capabilities.chat_tools.chat_completion_messages_with_tools",
            side_effect=fake_llm,
        ):
            reply, _usage, trace = run_tool_loop(
                db,
                org_id=user.id,
                messages=[{"role": "user", "content": "Roof Tattoo Sakarya'ya ne teklif vermiştik?"}],
            )

        assert [t["tool"] for t in trace] == ["search_leads", "get_lead_offer"]
        assert "15.000" in reply
        assert db.query(Lead).filter(Lead.user_id == user.id).count() == leads_before
        assert db.query(LeadActivity).filter(LeadActivity.user_id == user.id).count() == acts_before
        assert db.query(AiAction).filter(AiAction.organization_id == user.id).count() == actions_before
    finally:
        db.close()


def test_no_hallucination_without_tools_instruction_present():
    from ai.capabilities.chat_tools import SYSTEM_TOOLS

    assert "UYDURMA" in SYSTEM_TOOLS or "uydurma" in SYSTEM_TOOLS.lower()
    assert "tool" in SYSTEM_TOOLS.lower()


def test_streaming_tool_flow_events(org_a):
    _token, user = org_a
    lead = _add_lead(user.id, isletme_adi="Stream Co", teklif="1000")
    state = {"step": 0}

    def fake_llm(*, messages, tools, tool_choice="auto", temperature=0.3):
        state["step"] += 1
        if state["step"] == 1:
            return (
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "s1",
                            "type": "function",
                            "function": {
                                "name": "get_lead_offer",
                                "arguments": f'{{"lead_id": {lead.id}}}',
                            },
                        }
                    ],
                },
                {"total_tokens": 4},
            )
        return {"role": "assistant", "content": "Teklif: 1000"}, {"total_tokens": 6}

    from ai.capabilities.chat_tools import iter_tool_aware_chat_events
    from ai.store import create_run

    db = SessionLocal()
    try:
        run = create_run(
            db,
            org_id=user.id,
            requested_by=user.id,
            run_type="chat",
            input_data={"test": True},
        )
        db.flush()
        with patch("ai.capabilities.chat_tools.assert_llm_configured"), patch(
            "ai.capabilities.chat_tools.chat_completion_messages_with_tools",
            side_effect=fake_llm,
        ):
            events = list(
                iter_tool_aware_chat_events(
                    db,
                    org_id=user.id,
                    messages=[{"role": "user", "content": "teklif?"}],
                    run=run,
                )
            )
        types = [e["type"] for e in events]
        assert "tool_start" in types
        assert "tool_done" in types
        assert "delta" in types
        assert types[-1] == "_internal_done"
    finally:
        db.close()


def test_cross_org_conversation_isolation_still(client, org_a, org_b):
    token_a, _ua = org_a
    token_b, _ub = org_b
    created = client.post("/api/ai/conversations", headers=_auth(token_a), json={"title": "A"}).json()
    res = client.get(f"/api/ai/conversations/{created['id']}", headers=_auth(token_b))
    assert res.status_code == 404
