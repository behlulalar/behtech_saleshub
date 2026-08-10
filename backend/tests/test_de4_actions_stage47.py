"""DE-4 Stage 4.7 — DE-3 interpret → DE-4 proposed bridge (acceptance suite)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ai.actions.mapper import MapperResult
from ai.actions.proposal_bridge import (
    bridge_recommended_actions_to_proposals,
    build_bridge_idempotency_key,
)
from ai.store import create_run, finish_run_success
from auth import create_access_token
from config import settings
from database import AiAction, AiRun, Lead, LeadActivity, SessionLocal, User
from main import app
from schemas import DiagnosisRecommendedAction
from security import hash_password
from tests.test_de4_actions_stage42 import _owner_token
from tests.test_de4_actions_stage44 import _compute_payload
from tests.test_de4_actions_stage45 import _create_interpret_run


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

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


def _cleanup_run_actions(db, run_id: int, action_ids: list[str]) -> None:
    for aid in action_ids:
        db.query(AiAction).filter(AiAction.action_id == aid).delete()
    db.query(AiRun).filter(AiRun.id == run_id).delete()
    db.commit()


def test_stage47_flag_false_no_bridge_in_response(owner_lead, monkeypatch):
    from ai.capabilities.diagnosis_interpreter import run_diagnosis_interpret

    prev = settings.ai_de4_interpret_proposal_bridge_enabled
    settings.ai_de4_interpret_proposal_bridge_enabled = False
    monkeypatch.setattr("config.settings.diagnosis_engine_enabled", True)
    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_enabled", True)
    monkeypatch.setattr("config.settings.openai_api_key", "sk-test")
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        interp = (
            '{"summary":"s","why_it_matters":"w","key_findings":[],"confidence":"high",'
            '"recommended_actions":[{"title":"Not ekle","reason":"n","priority":"medium"}]}'
        )
        with patch("ai.capabilities.diagnosis_interpreter.compute_diagnoses", return_value=_compute_payload(lead.id)):
            with patch("ai.capabilities.diagnosis_interpreter.ensure_quota"):
                with patch(
                    "ai.capabilities.diagnosis_interpreter.chat_completion_structured",
                    return_value=(interp, {"total_tokens": 3}),
                ):
                    result = run_diagnosis_interpret(
                        db, user=user, org_id=user.id, diagnosis_id="follow_up_idle_leads"
                    )
        assert result["interpretation"] is not None
        assert result.get("proposal_bridge") is None
        assert db.query(AiAction).filter(AiAction.source_interpret_run_id == result["run_id"]).count() == 0
        db.query(AiRun).filter(AiRun.id == result["run_id"]).delete()
        db.commit()
    finally:
        db.close()
        settings.ai_de4_interpret_proposal_bridge_enabled = prev


def test_stage47_flag_true_creates_proposed(owner_lead):
    prev = settings.ai_de4_interpret_proposal_bridge_enabled
    settings.ai_de4_interpret_proposal_bridge_enabled = True
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        recs = [DiagnosisRecommendedAction(title="Not ekle", reason="Stage47 bridge", priority="high")]
        summary = bridge_recommended_actions_to_proposals(
            db,
            user_id=user.id,
            org_id=user.id,
            role="owner",
            diagnosis_id="follow_up_idle_leads",
            interpret_run_id=run_id,
            recommended_actions=recs,
            primary_lead_id=lead.id,
        )
        db.commit()
        assert summary.proposed_count == 1
        row = db.query(AiAction).filter(AiAction.action_id == summary.action_ids[0]).first()
        assert row.status == "proposed"
        assert row.source_diagnosis_id == "follow_up_idle_leads"
        assert row.source_interpret_run_id == run_id
        _cleanup_run_actions(db, run_id, summary.action_ids)
    finally:
        db.close()
        settings.ai_de4_interpret_proposal_bridge_enabled = prev


def test_stage47_no_action_no_insert(owner_lead):
    prev = settings.ai_de4_interpret_proposal_bridge_enabled
    settings.ai_de4_interpret_proposal_bridge_enabled = True
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        recs = [DiagnosisRecommendedAction(title="Belirsiz", reason="xyz", priority="low")]
        summary = bridge_recommended_actions_to_proposals(
            db,
            user_id=user.id,
            org_id=user.id,
            role="owner",
            diagnosis_id="dx",
            interpret_run_id=run_id,
            recommended_actions=recs,
            primary_lead_id=lead.id,
        )
        db.commit()
        assert summary.no_action_count == 1
        assert summary.proposed_count == 0
        assert db.query(AiAction).filter(AiAction.source_interpret_run_id == run_id).count() == 0
        db.query(AiRun).filter(AiRun.id == run_id).delete()
        db.commit()
    finally:
        db.close()
        settings.ai_de4_interpret_proposal_bridge_enabled = prev


def test_stage47_deterministic_idempotency_key():
    k1 = build_bridge_idempotency_key(
        organization_id=1,
        diagnosis_id="dx",
        interpret_run_id=100,
        recommendation_index=0,
        action_type="propose_note_append",
        target_entity="lead",
        target_entity_id=210,
    )
    k2 = build_bridge_idempotency_key(
        organization_id=1,
        diagnosis_id="dx",
        interpret_run_id=100,
        recommendation_index=0,
        action_type="propose_note_append",
        target_entity="lead",
        target_entity_id=210,
    )
    assert k1 == k2
    k3 = build_bridge_idempotency_key(
        organization_id=1,
        diagnosis_id="dx",
        interpret_run_id=101,
        recommendation_index=0,
        action_type="propose_note_append",
        target_entity="lead",
        target_entity_id=210,
    )
    assert k3 != k1


def test_stage47_cache_hit_same_run_no_duplicate(owner_lead, monkeypatch):
    from ai.capabilities.diagnosis_interpreter import run_diagnosis_interpret

    prev = settings.ai_de4_interpret_proposal_bridge_enabled
    settings.ai_de4_interpret_proposal_bridge_enabled = True
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
                {"title": "Not ekle", "reason": "Cache stage47 not metni", "priority": "medium"}
            ],
        }
        run = create_run(
            db,
            org_id=user.id,
            requested_by=user.id,
            run_type="diagnosis_interpret",
            input_data={"diagnosis_id": "follow_up_idle_leads", "context_fingerprint": "fp47"},
        )
        finish_run_success(db, run, output_data={"interpretation": interp})
        db.commit()
        run_id = run.id
        with patch("ai.capabilities.diagnosis_interpreter.compute_diagnoses", return_value=_compute_payload(lead.id)):
            with patch("ai.capabilities.diagnosis_interpreter.ensure_quota"):
                with patch("ai.capabilities.diagnosis_interpreter._find_cached_run", return_value=run):
                    with patch("ai.capabilities.diagnosis_interpreter.chat_completion_structured") as mock_llm:
                        r1 = run_diagnosis_interpret(
                            db, user=user, org_id=user.id, diagnosis_id="follow_up_idle_leads"
                        )
                        r2 = run_diagnosis_interpret(
                            db, user=user, org_id=user.id, diagnosis_id="follow_up_idle_leads"
                        )
        mock_llm.assert_not_called()
        assert r1["run_id"] == run_id
        assert r2["run_id"] == run_id
        assert r1["cached"] is True
        assert r2["cached"] is True
        assert r1["proposal_bridge"]["action_ids"] == r2["proposal_bridge"]["action_ids"]
        assert db.query(AiAction).filter(AiAction.source_interpret_run_id == run_id).count() == 1
        _cleanup_run_actions(db, run_id, r1["proposal_bridge"]["action_ids"])
    finally:
        db.close()
        settings.ai_de4_interpret_proposal_bridge_enabled = prev


def test_stage47_refresh_new_run_reuses_active_proposal(owner_lead):
    prev = settings.ai_de4_interpret_proposal_bridge_enabled
    settings.ai_de4_interpret_proposal_bridge_enabled = True
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        run_x = _create_interpret_run(db, user.id, user.id)
        run_y = _create_interpret_run(db, user.id, user.id)
        recs = [DiagnosisRecommendedAction(title="Not ekle", reason="Refresh run Y", priority="medium")]
        sx = bridge_recommended_actions_to_proposals(
            db,
            user_id=user.id,
            org_id=user.id,
            role="owner",
            diagnosis_id="follow_up_idle_leads",
            interpret_run_id=run_x,
            recommended_actions=recs,
            primary_lead_id=lead.id,
        )
        sy = bridge_recommended_actions_to_proposals(
            db,
            user_id=user.id,
            org_id=user.id,
            role="owner",
            diagnosis_id="follow_up_idle_leads",
            interpret_run_id=run_y,
            recommended_actions=recs,
            primary_lead_id=lead.id,
        )
        db.commit()
        assert sx.action_ids == sy.action_ids
        assert sy.created_count == 0
        rx = db.query(AiAction).filter(AiAction.action_id == sx.action_ids[0]).first()
        assert rx.status == "proposed"
        assert rx.source_interpret_run_id == run_x
        _cleanup_run_actions(db, run_x, sx.action_ids)
        _cleanup_run_actions(db, run_y, [])
    finally:
        db.close()
        settings.ai_de4_interpret_proposal_bridge_enabled = prev


def test_stage47_partial_batch_continues(owner_lead):
    prev = settings.ai_de4_interpret_proposal_bridge_enabled
    settings.ai_de4_interpret_proposal_bridge_enabled = True
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        recs = [
            DiagnosisRecommendedAction(title="Not ekle", reason="Valid note text here", priority="medium"),
            DiagnosisRecommendedAction(title="Teklif takip", reason="ambiguous offer", priority="medium"),
            DiagnosisRecommendedAction(title="Aktivite kaydet", reason="Takip log", priority="medium"),
        ]
        summary = bridge_recommended_actions_to_proposals(
            db,
            user_id=user.id,
            org_id=user.id,
            role="owner",
            diagnosis_id="follow_up_idle_leads",
            interpret_run_id=run_id,
            recommended_actions=recs,
            primary_lead_id=lead.id,
        )
        db.commit()
        assert summary.proposed_count >= 2
        assert summary.no_action_count >= 1
        db.query(AiAction).filter(AiAction.source_interpret_run_id == run_id).delete()
        db.query(AiRun).filter(AiRun.id == run_id).delete()
        db.commit()
    finally:
        db.close()
        settings.ai_de4_interpret_proposal_bridge_enabled = prev


def test_stage47_bridge_never_approve_execute(owner_lead):
    prev = settings.ai_de4_interpret_proposal_bridge_enabled
    settings.ai_de4_interpret_proposal_bridge_enabled = True
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        with patch("ai.actions.execute_service.approve_ai_action") as mock_a:
            with patch("ai.actions.execute_service.execute_ai_action") as mock_e:
                bridge_recommended_actions_to_proposals(
                    db,
                    user_id=user.id,
                    org_id=user.id,
                    role="owner",
                    diagnosis_id="dx",
                    interpret_run_id=run_id,
                    recommended_actions=[
                        DiagnosisRecommendedAction(title="Not ekle", reason="No lifecycle", priority="medium")
                    ],
                    primary_lead_id=lead.id,
                )
                db.rollback()
        mock_a.assert_not_called()
        mock_e.assert_not_called()
    finally:
        db.close()
        settings.ai_de4_interpret_proposal_bridge_enabled = prev


def test_stage47_bridge_no_crm_mutation(owner_lead):
    prev = settings.ai_de4_interpret_proposal_bridge_enabled
    settings.ai_de4_interpret_proposal_bridge_enabled = True
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        before = db.query(LeadActivity).filter(LeadActivity.lead_id == lead.id).count()
        run_id = _create_interpret_run(db, user.id, user.id)
        bridge_recommended_actions_to_proposals(
            db,
            user_id=user.id,
            org_id=user.id,
            role="owner",
            diagnosis_id="dx",
            interpret_run_id=run_id,
            recommended_actions=[
                DiagnosisRecommendedAction(title="Aktivite kaydet", reason="log activity", priority="medium")
            ],
            primary_lead_id=lead.id,
        )
        db.commit()
        after = db.query(LeadActivity).filter(LeadActivity.lead_id == lead.id).count()
        assert after == before
        db.query(AiAction).filter(AiAction.source_interpret_run_id == run_id).delete()
        db.query(AiRun).filter(AiRun.id == run_id).delete()
        db.commit()
    finally:
        db.close()
        settings.ai_de4_interpret_proposal_bridge_enabled = prev


def test_stage47_reason_not_raw_llm_blob(owner_lead):
    prev = settings.ai_de4_interpret_proposal_bridge_enabled
    settings.ai_de4_interpret_proposal_bridge_enabled = True
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        summary = bridge_recommended_actions_to_proposals(
            db,
            user_id=user.id,
            org_id=user.id,
            role="owner",
            diagnosis_id="dx",
            interpret_run_id=run_id,
            recommended_actions=[
                DiagnosisRecommendedAction(title="Not ekle", reason="Kısa güvenli özet", priority="medium")
            ],
            primary_lead_id=lead.id,
        )
        db.commit()
        row = db.query(AiAction).filter(AiAction.action_id == summary.action_ids[0]).first()
        assert "{" not in (row.reason or "")[:20]
        assert len(row.reason or "") <= 600
        db.query(AiAction).filter(AiAction.action_id == row.action_id).delete()
        db.query(AiRun).filter(AiRun.id == run_id).delete()
        db.commit()
    finally:
        db.close()
        settings.ai_de4_interpret_proposal_bridge_enabled = prev


def test_stage47_org_isolation_bridge(client, owner_lead):
    prev = settings.ai_de4_interpret_proposal_bridge_enabled
    settings.ai_de4_interpret_proposal_bridge_enabled = True
    token_a, user_a, lead_a = owner_lead
    db = SessionLocal()
    try:
        other = User(
            username=f"stage47b{user_a.id}",
            email=f"stage47b{user_a.id}@example.com",
            password_hash=hash_password("TestPass123!"),
            role="owner",
            email_verified=True,
        )
        db.add(other)
        db.flush()
        lead_b = Lead(user_id=other.id, category="berber", isletme_adi="B Lead")
        db.add(lead_b)
        db.flush()
        run_id = _create_interpret_run(db, user_a.id, user_a.id)
        summary = bridge_recommended_actions_to_proposals(
            db,
            user_id=user_a.id,
            org_id=user_a.id,
            role="owner",
            diagnosis_id="dx",
            interpret_run_id=run_id,
            recommended_actions=[
                DiagnosisRecommendedAction(title="Not ekle", reason="Org A", priority="medium")
            ],
            primary_lead_id=lead_a.id,
        )
        db.commit()
        action_id = summary.action_ids[0]
        token_b, _expires = create_access_token(other.id, other.username, token_version=0)
        assert client.get(f"/api/ai/actions/{action_id}", headers={"Authorization": f"Bearer {token_b}"}).status_code == 404
        db.query(AiAction).filter(AiAction.action_id == action_id).delete()
        db.query(AiRun).filter(AiRun.id == run_id).delete()
        db.query(Lead).filter(Lead.id == lead_b.id).delete()
        db.query(User).filter(User.id == other.id).delete()
        db.commit()
    finally:
        db.close()
        settings.ai_de4_interpret_proposal_bridge_enabled = prev


def test_stage47_top_level_bridge_error_preserves_interpret(owner_lead, monkeypatch):
    from ai.capabilities.diagnosis_interpreter import run_diagnosis_interpret

    prev = settings.ai_de4_interpret_proposal_bridge_enabled
    settings.ai_de4_interpret_proposal_bridge_enabled = True
    monkeypatch.setattr("config.settings.diagnosis_engine_enabled", True)
    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_enabled", True)
    monkeypatch.setattr("config.settings.openai_api_key", "sk-test")
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        interp = (
            '{"summary":"s","why_it_matters":"w","key_findings":[],"confidence":"high",'
            '"recommended_actions":[{"title":"Not ekle","reason":"n","priority":"medium"}]}'
        )

        def _boom(*_a, **_k):
            raise RuntimeError("simulated bridge failure")

        with patch("ai.capabilities.diagnosis_interpreter.compute_diagnoses", return_value=_compute_payload(lead.id)):
            with patch("ai.capabilities.diagnosis_interpreter.ensure_quota"):
                with patch(
                    "ai.capabilities.diagnosis_interpreter.chat_completion_structured",
                    return_value=(interp, {"total_tokens": 2}),
                ):
                    with patch(
                        "ai.capabilities.diagnosis_interpreter.bridge_recommended_actions_to_proposals",
                        side_effect=_boom,
                    ):
                        result = run_diagnosis_interpret(
                            db, user=user, org_id=user.id, diagnosis_id="follow_up_idle_leads"
                        )
        assert result["interpretation"] is not None
        assert result.get("proposal_bridge", {}).get("bridge_error") is True
        db.query(AiRun).filter(AiRun.id == result["run_id"]).delete()
        db.commit()
    finally:
        db.close()
        settings.ai_de4_interpret_proposal_bridge_enabled = prev


def test_stage47_disabled_mapped_action_skipped(owner_lead):
    prev = settings.ai_de4_interpret_proposal_bridge_enabled
    settings.ai_de4_interpret_proposal_bridge_enabled = True
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        fake = MapperResult(
            outcome="mapped",
            action_type="send_whatsapp_message",
            parameters={"lead_id": lead.id, "message": "hi"},
        )
        with patch("ai.actions.proposal_bridge.map_recommended_action", return_value=fake):
            summary = bridge_recommended_actions_to_proposals(
                db,
                user_id=user.id,
                org_id=user.id,
                role="owner",
                diagnosis_id="dx",
                interpret_run_id=run_id,
                recommended_actions=[
                    DiagnosisRecommendedAction(title="x", reason="y", priority="medium")
                ],
                primary_lead_id=lead.id,
            )
        db.commit()
        assert summary.proposed_count == 0
        db.query(AiRun).filter(AiRun.id == run_id).delete()
        db.commit()
    finally:
        db.close()
        settings.ai_de4_interpret_proposal_bridge_enabled = prev
