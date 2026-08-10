"""DE-4 Stage 4.4 — DE-3 interpretation → ai_actions proposal bridge."""

from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from ai.actions.mapper import MapperResult
from ai.actions.proposal_bridge import (
    ProposalBridgeSummary,
    bridge_recommended_actions_to_proposals,
    build_bridge_idempotency_key,
    primary_lead_id_from_diagnosis_item,
)
from ai.store import create_run, finish_run_success
from auth import create_access_token
from config import settings
from database import AiAction, AiRun, Lead, SessionLocal, User
from main import app
from schemas import DiagnosisRecommendedAction
from tests.test_de4_actions_stage42 import _propose_approve


def _is_postgres() -> bool:
    url = (settings.database_url or "").lower()
    return "postgresql" in url or "postgres://" in url


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def ai_on():
    prev = settings.ai_enabled
    settings.ai_enabled = True
    try:
        yield
    finally:
        settings.ai_enabled = prev


@pytest.fixture
def bridge_on():
    prev = settings.ai_de4_interpret_proposal_bridge_enabled
    settings.ai_de4_interpret_proposal_bridge_enabled = True
    try:
        yield
    finally:
        settings.ai_de4_interpret_proposal_bridge_enabled = prev


@pytest.fixture
def require_postgres():
    if not _is_postgres():
        pytest.skip("Concurrency tests require PostgreSQL")


def _owner_token(db) -> tuple[str, User]:
    user = db.query(User).filter(User.role == "owner").first()
    if not user:
        pytest.skip("No owner")
    token, _ = create_access_token(user.id, user.username, token_version=user.token_version or 0)
    return token, user


@pytest.fixture
def owner_lead():
    db = SessionLocal()
    try:
        token, user = _owner_token(db)
        lead = db.query(Lead).filter(Lead.user_id == user.id).first()
        if not lead:
            pytest.skip("No lead")
        yield token, user, lead
    finally:
        db.close()


def _recs(*pairs: tuple[str, str]) -> list[DiagnosisRecommendedAction]:
    return [
        DiagnosisRecommendedAction(title=title, reason=reason, priority="medium")
        for title, reason in pairs
    ]


def _create_interpret_run(db, org_id: int, user_id: int) -> int:
    run = create_run(
        db,
        org_id=org_id,
        requested_by=user_id,
        run_type="diagnosis_interpret",
        input_data={"diagnosis_id": "follow_up_idle_leads"},
    )
    finish_run_success(db, run, output_data={"interpretation": {"summary": "x"}})
    db.flush()
    return run.id


def _cleanup_actions_and_run(db, run_id: int, action_ids: list[str]) -> None:
    for aid in action_ids:
        db.query(AiAction).filter(AiAction.action_id == aid).delete()
    db.query(AiAction).filter(AiAction.source_interpret_run_id == run_id).delete()
    db.query(AiRun).filter(AiRun.id == run_id).delete()
    db.commit()


def _bridge(db, user, org_id, lead_id, run_id, recs, dx_id="follow_up_idle_leads"):
    return bridge_recommended_actions_to_proposals(
        db,
        user_id=user.id,
        org_id=org_id,
        role=user.role or "owner",
        diagnosis_id=dx_id,
        interpret_run_id=run_id,
        recommended_actions=recs,
        primary_lead_id=lead_id,
    )


def test_bridge_maps_note_to_proposal(bridge_on, owner_lead):
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        recs = _recs(("Not ekle", "Müşteri hakkında not yaz"))
        summary = _bridge(db, user, user.id, lead.id, run_id, recs)
        db.commit()
        assert summary.proposed_count == 1
        assert summary.mapped_count == 1
        row = db.query(AiAction).filter(AiAction.action_id == summary.action_ids[0]).first()
        assert row is not None
        assert row.status == "proposed"
        assert row.source_diagnosis_id == "follow_up_idle_leads"
        assert row.source_interpret_run_id == run_id
        assert "not" in (row.reason or "").lower() or "müşteri" in (row.reason or "").lower()
        _cleanup_actions_and_run(db, run_id, summary.action_ids)
    finally:
        db.close()


def test_no_action_no_db_row(bridge_on, owner_lead):
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        recs = _recs(("Teklifleri takip et", "Belirsiz öneri metni"))
        summary = _bridge(db, user, user.id, lead.id, run_id, recs)
        db.commit()
        assert summary.no_action_count >= 1
        assert summary.proposed_count == 0
        assert db.query(AiAction).filter(AiAction.source_interpret_run_id == run_id).count() == 0
        _cleanup_actions_and_run(db, run_id, [])
    finally:
        db.close()


def test_partial_success(bridge_on, owner_lead):
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        recs = _recs(
            ("Not ekle", "Müşteri hakkında not yaz"),
            ("Teklifleri takip et", "Belirsiz"),
            ("Aktivite kaydet", "Takip aktivitesi log"),
        )
        summary = _bridge(db, user, user.id, lead.id, run_id, recs)
        db.commit()
        assert summary.proposed_count >= 2
        assert summary.no_action_count >= 1
        _cleanup_actions_and_run(db, run_id, summary.action_ids)
    finally:
        db.close()


def test_unknown_recommendation_skipped(bridge_on, owner_lead):
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        recs = _recs(("Genel strateji geliştir", "Pazarlama planı"))
        summary = _bridge(db, user, user.id, lead.id, run_id, recs)
        db.commit()
        assert summary.no_action_count == 1
        assert summary.proposed_count == 0
        _cleanup_actions_and_run(db, run_id, [])
    finally:
        db.close()


def test_disabled_action_no_proposal(bridge_on, owner_lead):
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        recs = _recs(("x", "y"))
        fake = MapperResult(
            outcome="mapped",
            action_type="send_whatsapp_message",
            parameters={"lead_id": lead.id, "message": "hi"},
            mapper_reason="test",
        )
        with patch("ai.actions.proposal_bridge.map_recommended_action", return_value=fake):
            summary = _bridge(db, user, user.id, lead.id, run_id, recs)
        db.commit()
        assert summary.skipped_count >= 1
        assert summary.proposed_count == 0
        _cleanup_actions_and_run(db, run_id, [])
    finally:
        db.close()


def test_idempotent_same_run_twice(bridge_on, owner_lead):
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        recs = _recs(("Not ekle", "Tekrar deneme notu"))
        s1 = _bridge(db, user, user.id, lead.id, run_id, recs)
        db.commit()
        s2 = _bridge(db, user, user.id, lead.id, run_id, recs)
        db.commit()
        assert s1.action_ids == s2.action_ids
        assert s2.created_count == 0
        assert db.query(AiAction).filter(AiAction.source_interpret_run_id == run_id).count() == 1
        _cleanup_actions_and_run(db, run_id, s1.action_ids)
    finally:
        db.close()


def test_deterministic_idempotency_key():
    k1 = build_bridge_idempotency_key(
        organization_id=1,
        diagnosis_id="dx1",
        interpret_run_id=10,
        recommendation_index=0,
        action_type="propose_log_activity",
        target_entity="lead",
        target_entity_id=5,
    )
    k2 = build_bridge_idempotency_key(
        organization_id=1,
        diagnosis_id="dx1",
        interpret_run_id=10,
        recommendation_index=0,
        action_type="propose_log_activity",
        target_entity="lead",
        target_entity_id=5,
    )
    assert k1 == k2
    assert k1.startswith("de3bridge-")


def test_refresh_new_run_reuses_active_proposal(bridge_on, owner_lead):
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        run1 = _create_interpret_run(db, user.id, user.id)
        run2 = _create_interpret_run(db, user.id, user.id)
        recs = _recs(("Not ekle", "Refresh sonrası not"))
        s1 = _bridge(db, user, user.id, lead.id, run1, recs)
        s2 = _bridge(db, user, user.id, lead.id, run2, recs)
        db.commit()
        assert s1.action_ids == s2.action_ids
        assert s2.created_count == 0
        assert db.query(AiAction).filter(
            AiAction.organization_id == user.id,
            AiAction.action_type == "propose_note_append",
            AiAction.target_entity_id == lead.id,
            AiAction.status.in_(("proposed", "approved", "executing")),
        ).count() == 1
        _cleanup_actions_and_run(db, run1, s1.action_ids)
        _cleanup_actions_and_run(db, run2, [])
    finally:
        db.close()


def test_bridge_does_not_call_execute_or_approve(bridge_on, owner_lead):
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        with patch("ai.actions.execute_service.approve_ai_action") as mock_a:
            with patch("ai.actions.execute_service.execute_ai_action") as mock_e:
                _bridge(db, user, user.id, lead.id, run_id, _recs(("Not ekle", "Mesaj notu")))
                db.rollback()
        mock_a.assert_not_called()
        mock_e.assert_not_called()
    finally:
        db.close()


def test_bridge_does_not_call_openai(bridge_on, owner_lead):
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        with patch("ai.llm_client.chat_completion_structured") as mock_llm:
            _bridge(db, user, user.id, lead.id, run_id, _recs(("Not ekle", "OpenAI yok")))
            db.rollback()
        mock_llm.assert_not_called()
    finally:
        db.close()


def _compute_payload(lead_id: int):
    return {
        "period_type": "monthly",
        "anchor": "2026-08-01",
        "items": [
            {
                "diagnosis_id": "follow_up_idle_leads",
                "top_priority_leads": [{"lead_id": lead_id, "lead_name": "X"}],
                "evidence": {},
            }
        ],
    }


def test_interpret_bridge_integration_mock(bridge_on, owner_lead, monkeypatch):
    from ai.capabilities.diagnosis_interpreter import run_diagnosis_interpret

    monkeypatch.setattr("config.settings.diagnosis_engine_enabled", True)
    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_enabled", True)
    monkeypatch.setattr("config.settings.openai_api_key", "sk-test")

    _, user, lead = owner_lead
    db = SessionLocal()
    action_ids: list[str] = []
    run_id_holder: list[int] = []
    try:
        interp_json = (
            '{"summary":"s","why_it_matters":"w","key_findings":[],"confidence":"high",'
            '"recommended_actions":[{"title":"Not ekle","reason":"Müşteri hakkında not yaz","priority":"high"}]}'
        )
        llm_calls: list[int] = []

        def _llm(*_a, **_k):
            llm_calls.append(1)
            return (interp_json, {"total_tokens": 10})

        with patch("ai.capabilities.diagnosis_interpreter.compute_diagnoses", return_value=_compute_payload(lead.id)):
            with patch("ai.capabilities.diagnosis_interpreter.ensure_quota"):
                with patch("ai.capabilities.diagnosis_interpreter.chat_completion_structured", side_effect=_llm):
                    result = run_diagnosis_interpret(
                        db,
                        user=user,
                        org_id=user.id,
                        diagnosis_id="follow_up_idle_leads",
                    )
        assert result["interpretation"] is not None
        assert result["proposal_bridge"] is not None
        assert result["proposal_bridge"]["proposed_count"] >= 1
        assert len(llm_calls) == 1
        run_id_holder.append(result["run_id"])
        action_ids.extend(result["proposal_bridge"]["action_ids"])
        _cleanup_actions_and_run(db, run_id_holder[0], action_ids)
    finally:
        db.close()


def test_interpret_failure_still_ok_without_bridge(bridge_on, monkeypatch):
    from ai.capabilities.diagnosis_interpreter import run_diagnosis_interpret

    monkeypatch.setattr("config.settings.diagnosis_engine_enabled", True)
    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_enabled", True)
    monkeypatch.setattr("config.settings.openai_api_key", "sk-test")

    db = SessionLocal()
    user = db.query(User).filter(User.role == "owner").first()
    run_id = None
    try:
        with patch("ai.capabilities.diagnosis_interpreter.compute_diagnoses", return_value=_compute_payload(1)):
            with patch("ai.capabilities.diagnosis_interpreter.ensure_quota"):
                with patch(
                    "ai.capabilities.diagnosis_interpreter.chat_completion_structured",
                    return_value=("not json", {"total_tokens": 1}),
                ):
                    result = run_diagnosis_interpret(
                        db,
                        user=user,
                        org_id=user.id,
                        diagnosis_id="follow_up_idle_leads",
                    )
        assert result["interpretation"] is None
        assert result.get("proposal_bridge") is None
        run_id = result["run_id"]
        if run_id:
            _cleanup_actions_and_run(db, run_id, [])
    finally:
        db.close()


def test_cache_hit_no_duplicate_proposal(bridge_on, owner_lead, monkeypatch):
    from ai.capabilities.diagnosis_interpreter import run_diagnosis_interpret

    monkeypatch.setattr("config.settings.diagnosis_engine_enabled", True)
    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_enabled", True)
    monkeypatch.setattr("config.settings.openai_api_key", "sk-test")

    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        interp = {
            "summary": "s",
            "why_it_matters": "w",
            "key_findings": [],
            "confidence": "high",
            "recommended_actions": [
                {"title": "Not ekle", "reason": "Cache hit notu", "priority": "medium"}
            ],
        }
        run = create_run(
            db,
            org_id=user.id,
            requested_by=user.id,
            run_type="diagnosis_interpret",
            input_data={"diagnosis_id": "follow_up_idle_leads", "context_fingerprint": "fp44"},
            provider="openai",
            model="gpt-test",
            prompt_version="pv44",
        )
        finish_run_success(db, run, output_data={"interpretation": interp})
        db.commit()

        llm_calls: list[int] = []

        def _llm(*_a, **_k):
            llm_calls.append(1)
            return ("{}", {"total_tokens": 1})

        with patch("ai.capabilities.diagnosis_interpreter.compute_diagnoses", return_value=_compute_payload(lead.id)):
            with patch("ai.capabilities.diagnosis_interpreter.ensure_quota"):
                with patch(
                    "ai.capabilities.diagnosis_interpreter._find_cached_run",
                    return_value=run,
                ):
                    with patch(
                        "ai.capabilities.diagnosis_interpreter.chat_completion_structured",
                        side_effect=_llm,
                    ):
                        r1 = run_diagnosis_interpret(
                            db, user=user, org_id=user.id, diagnosis_id="follow_up_idle_leads"
                        )
                        r2 = run_diagnosis_interpret(
                            db, user=user, org_id=user.id, diagnosis_id="follow_up_idle_leads"
                        )
        assert r1["cached"] is True
        assert r2["cached"] is True
        assert len(llm_calls) == 0
        assert r1["proposal_bridge"]["action_ids"] == r2["proposal_bridge"]["action_ids"]
        count = db.query(AiAction).filter(AiAction.source_interpret_run_id == run.id).count()
        assert count == 1
        _cleanup_actions_and_run(db, run.id, r1["proposal_bridge"]["action_ids"])
    finally:
        db.close()


def test_proposal_bridge_failure_does_not_fail_interpret(bridge_on, owner_lead, monkeypatch):
    from ai.capabilities.diagnosis_interpreter import run_diagnosis_interpret

    monkeypatch.setattr("config.settings.diagnosis_engine_enabled", True)
    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_enabled", True)
    monkeypatch.setattr("config.settings.openai_api_key", "sk-test")

    _, user, lead = owner_lead
    db = SessionLocal()
    run_id = None
    try:
        interp_json = (
            '{"summary":"s","why_it_matters":"w","key_findings":[],"confidence":"high",'
            '"recommended_actions":[{"title":"Not ekle","reason":"Fail bridge","priority":"high"}]}'
        )
        with patch("ai.capabilities.diagnosis_interpreter.compute_diagnoses", return_value=_compute_payload(lead.id)):
            with patch("ai.capabilities.diagnosis_interpreter.ensure_quota"):
                with patch(
                    "ai.capabilities.diagnosis_interpreter.chat_completion_structured",
                    return_value=(interp_json, {"total_tokens": 10}),
                ):
                    with patch(
                        "ai.capabilities.diagnosis_interpreter.bridge_recommended_actions_to_proposals",
                        side_effect=RuntimeError("bridge boom"),
                    ):
                        result = run_diagnosis_interpret(
                            db,
                            user=user,
                            org_id=user.id,
                            diagnosis_id="follow_up_idle_leads",
                        )
        assert result["interpretation"] is not None
        assert result.get("proposal_bridge", {}).get("bridge_error") is True
        assert result["proposal_bridge"]["proposed_count"] == 0
        run_id = result["run_id"]
    finally:
        if run_id:
            db = SessionLocal()
            try:
                _cleanup_actions_and_run(db, run_id, [])
            finally:
                db.close()


def test_primary_lead_from_diagnosis_item():
    item = {"top_priority_leads": [{"lead_id": 42}], "evidence": {}}
    assert primary_lead_id_from_diagnosis_item(item) == 42


def test_org_from_jwt_not_client_body(bridge_on, client, owner_lead):
    token, user, lead = owner_lead
    db = SessionLocal()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        recs = _recs(("Not ekle", "Org test"))
        summary = _bridge(db, user, user.id, lead.id, run_id, recs)
        db.commit()
        row = db.query(AiAction).filter(AiAction.action_id == summary.action_ids[0]).first()
        assert row.organization_id == user.id
        _cleanup_actions_and_run(db, run_id, summary.action_ids)
    finally:
        db.close()


def test_concurrent_bridge_idempotent(require_postgres, bridge_on, owner_lead):
    _, user, lead = owner_lead
    db = SessionLocal()
    run_id = _create_interpret_run(db, user.id, user.id)
    db.commit()
    db.close()

    recs = _recs(("Not ekle", "Concurrent not"))
    barrier = threading.Barrier(2)
    results: list[ProposalBridgeSummary] = []

    def _run():
        sess = SessionLocal()
        try:
            barrier.wait(timeout=10)
            results.append(_bridge(sess, user, user.id, lead.id, run_id, recs))
            sess.commit()
        finally:
            sess.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_run)
        f2 = pool.submit(_run)
        f1.result(timeout=30)
        f2.result(timeout=30)

    assert len(results) == 2
    assert results[0].action_ids == results[1].action_ids
    db = SessionLocal()
    try:
        assert db.query(AiAction).filter(AiAction.source_interpret_run_id == run_id).count() == 1
        _cleanup_actions_and_run(db, run_id, results[0].action_ids)
    finally:
        db.close()


def test_note_append_regression_execute(bridge_on, owner_lead):
    token, user, lead = owner_lead
    c = TestClient(app)
    body = {
        "action_type": "propose_note_append",
        "target_entity": "lead",
        "target_entity_id": lead.id,
        "parameters": {"lead_id": lead.id, "note_text": "Stage 4.4 regression"},
        "reason": "regression",
        "idempotency_key": f"note44-{uuid.uuid4().hex[:10]}",
    }
    r = c.post("/api/ai/actions/propose", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    action_id = r.json()["action_id"]
    c.post(f"/api/ai/actions/{action_id}/approve", headers={"Authorization": f"Bearer {token}"})
    assert c.post(f"/api/ai/actions/{action_id}/execute", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    db = SessionLocal()
    try:
        db.query(AiAction).filter(AiAction.action_id == action_id).delete()
        db.commit()
    finally:
        db.close()


def test_log_activity_regression_execute(bridge_on, owner_lead):
    token, _, lead = owner_lead
    c = TestClient(app)
    action_id = _propose_approve(c, token, lead.id)
    r = c.post(f"/api/ai/actions/{action_id}/execute", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    db = SessionLocal()
    try:
        db.query(AiAction).filter(AiAction.action_id == action_id).delete()
        db.commit()
    finally:
        db.close()


def test_meeting_date_still_not_executable(bridge_on, owner_lead):
    token, _user, lead = owner_lead
    c = TestClient(app)
    body = {
        "action_type": "propose_meeting_date",
        "target_entity": "lead",
        "target_entity_id": lead.id,
        "parameters": {
            "lead_id": lead.id,
            "meeting_date": "2026-09-01",
            "meeting_time": "",
        },
        "reason": "t",
        "idempotency_key": f"mt44-{uuid.uuid4().hex[:10]}",
    }
    r = c.post("/api/ai/actions/propose", json=body, headers={"Authorization": f"Bearer {token}"})
    aid = r.json()["action_id"]
    c.post(f"/api/ai/actions/{aid}/approve", headers={"Authorization": f"Bearer {token}"})
    assert c.post(f"/api/ai/actions/{aid}/execute", headers={"Authorization": f"Bearer {token}"}).status_code == 403
    db = SessionLocal()
    try:
        db.query(AiAction).filter(AiAction.action_id == aid).delete()
        db.commit()
    finally:
        db.close()
