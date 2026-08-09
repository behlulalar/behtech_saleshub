"""DE-4 Stage 4.5 — proposal lifecycle & production safety hardening."""

from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ai.actions.mapper import MapperResult
from ai.actions.proposal_bridge import bridge_recommended_actions_to_proposals
from ai.store import create_run, finish_run_success
from auth import create_access_token
from config import settings
from database import AiAction, AiRun, Lead, LeadActivity, SessionLocal, User
from main import app
from schemas import DiagnosisRecommendedAction
from security import hash_password
from tests.test_de4_actions_stage42 import (
    _log_activity_propose,
    _owner_token,
    _propose_approve,
)


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
def require_postgres():
    if not _is_postgres():
        pytest.skip("PostgreSQL required")


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


def _cleanup(action_id: str, activity_id: int | None = None) -> None:
    db = SessionLocal()
    try:
        if activity_id:
            db.query(LeadActivity).filter(LeadActivity.id == activity_id).delete()
        db.query(AiAction).filter(AiAction.action_id == action_id).delete()
        db.commit()
    finally:
        db.close()


def _set_status(action_id: str, status: str) -> None:
    db = SessionLocal()
    try:
        row = db.query(AiAction).filter(AiAction.action_id == action_id).first()
        assert row is not None
        row.status = status
        db.commit()
    finally:
        db.close()


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


def _other_org_token() -> tuple[str, int]:
    db = SessionLocal()
    try:
        user = User(
            username=f"de45_{uuid.uuid4().hex[:8]}",
            email=f"de45_{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("testpass123"),
            role="owner",
            email_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token, _ = create_access_token(user.id, user.username, token_version=0)
        return token, user.id
    finally:
        db.close()


def test_lifecycle_proposed_to_approved(client, owner_lead):
    token, _, lead = owner_lead
    r = client.post(
        "/api/ai/actions/propose",
        json=_log_activity_propose(lead.id),
        headers={"Authorization": f"Bearer {token}"},
    )
    action_id = r.json()["action_id"]
    r2 = client.post(
        f"/api/ai/actions/{action_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "approved"
    assert r2.json()["approved_at"]
    _cleanup(action_id)


def test_proposed_execute_rejected_422(client, owner_lead):
    token, _, lead = owner_lead
    r = client.post(
        "/api/ai/actions/propose",
        json=_log_activity_propose(lead.id),
        headers={"Authorization": f"Bearer {token}"},
    )
    action_id = r.json()["action_id"]
    assert (
        client.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 422
    )
    _cleanup(action_id)


def test_approved_to_execute(client, owner_lead):
    token, _, lead = owner_lead
    action_id = _propose_approve(client, token, lead.id)
    r = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["action"]["status"] == "executed"
    _cleanup(action_id, r.json().get("activity_id"))


def test_executed_execute_idempotent(client, owner_lead):
    token, user, lead = owner_lead
    action_id = _propose_approve(client, token, lead.id)
    db = SessionLocal()
    try:
        before = (
            db.query(LeadActivity)
            .filter(LeadActivity.user_id == user.id, LeadActivity.lead_id == lead.id)
            .count()
        )
    finally:
        db.close()
    r1 = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    r2 = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.json()["already_executed"] is True
    db = SessionLocal()
    try:
        after = (
            db.query(LeadActivity)
            .filter(LeadActivity.user_id == user.id, LeadActivity.lead_id == lead.id)
            .count()
        )
        assert after == before + 1
    finally:
        db.close()
    _cleanup(action_id, r1.json().get("activity_id"))


def test_executed_approve_rejected(client, owner_lead):
    token, _, lead = owner_lead
    action_id = _propose_approve(client, token, lead.id)
    client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert (
        client.post(
            f"/api/ai/actions/{action_id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 422
    )
    _cleanup(action_id)


def test_failed_execute_rejected(client, owner_lead):
    token, _, lead = owner_lead
    action_id = _propose_approve(client, token, lead.id)
    with patch("ai.actions.executors.log_activity", side_effect=RuntimeError("secret-boom")):
        r = client.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 502
    assert "secret-boom" not in r.text
    assert (
        client.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 502
    )
    _cleanup(action_id)


def test_failed_approve_rejected(client, owner_lead):
    token, _, lead = owner_lead
    action_id = _propose_approve(client, token, lead.id)
    _set_status(action_id, "failed")
    assert (
        client.post(
            f"/api/ai/actions/{action_id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 422
    )
    _cleanup(action_id)


def test_cancelled_execute_rejected(client, owner_lead):
    token, _, lead = owner_lead
    action_id = _propose_approve(client, token, lead.id)
    _set_status(action_id, "cancelled")
    assert (
        client.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 422
    )
    _cleanup(action_id)


def test_expired_execute_rejected(client, owner_lead):
    token, _, lead = owner_lead
    action_id = _propose_approve(client, token, lead.id)
    _set_status(action_id, "expired")
    assert (
        client.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 422
    )
    _cleanup(action_id)


def test_expired_approve_rejected(client, owner_lead):
    token, _, lead = owner_lead
    r = client.post(
        "/api/ai/actions/propose",
        json=_log_activity_propose(lead.id),
        headers={"Authorization": f"Bearer {token}"},
    )
    action_id = r.json()["action_id"]
    _set_status(action_id, "expired")
    assert (
        client.post(
            f"/api/ai/actions/{action_id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 422
    )
    _cleanup(action_id)


def test_parallel_approve_one_success(require_postgres, owner_lead):
    token, _, lead = owner_lead
    client_a = TestClient(app)
    body = _log_activity_propose(lead.id, key=f"appr-{uuid.uuid4().hex[:10]}")
    action_id = client_a.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    ).json()["action_id"]
    barrier = threading.Barrier(2)

    def _approve():
        c = TestClient(app)
        barrier.wait(timeout=10)
        return c.post(
            f"/api/ai/actions/{action_id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_approve)
        f2 = pool.submit(_approve)
        r1, r2 = f1.result(timeout=30), f2.result(timeout=30)

    codes = sorted([r1.status_code, r2.status_code])
    assert codes == [200, 422]
    _cleanup(action_id)


def test_parallel_execute_single_mutation(require_postgres, owner_lead):
    token, user, lead = owner_lead
    key = f"conc45-{uuid.uuid4().hex[:12]}"
    c = TestClient(app)
    action_id = _propose_approve(c, token, lead.id, key=key)
    db = SessionLocal()
    try:
        before = (
            db.query(LeadActivity)
            .filter(LeadActivity.user_id == user.id, LeadActivity.lead_id == lead.id)
            .count()
        )
    finally:
        db.close()
    barrier = threading.Barrier(2)

    def _exec_once():
        local = TestClient(app)
        barrier.wait(timeout=10)
        return local.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token}"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_exec_once)
        f2 = pool.submit(_exec_once)
        r1, r2 = f1.result(timeout=30), f2.result(timeout=30)
    assert r1.status_code == 200 and r2.status_code == 200
    flags = [r1.json().get("already_executed"), r2.json().get("already_executed")]
    assert flags.count(True) == 1
    db = SessionLocal()
    try:
        after = (
            db.query(LeadActivity)
            .filter(LeadActivity.user_id == user.id, LeadActivity.lead_id == lead.id)
            .count()
        )
        assert after == before + 1
    finally:
        db.close()
    _cleanup(action_id, r1.json().get("activity_id"))


def test_triple_execute_one_mutation(client, owner_lead):
    token, user, lead = owner_lead
    action_id = _propose_approve(client, token, lead.id)
    db = SessionLocal()
    try:
        before = (
            db.query(LeadActivity)
            .filter(LeadActivity.user_id == user.id, LeadActivity.lead_id == lead.id)
            .count()
        )
    finally:
        db.close()
    codes = []
    bodies = []
    for _ in range(3):
        r = client.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token}"},
        )
        codes.append(r.status_code)
        bodies.append(r.json())
    assert all(c == 200 for c in codes)
    assert sum(1 for b in bodies if b.get("already_executed")) == 2
    db = SessionLocal()
    try:
        after = (
            db.query(LeadActivity)
            .filter(LeadActivity.user_id == user.id, LeadActivity.lead_id == lead.id)
            .count()
        )
        assert after == before + 1
    finally:
        db.close()
    _cleanup(action_id, bodies[0].get("activity_id"))


def test_executor_failure_marks_failed(client, owner_lead):
    token, _, lead = owner_lead
    action_id = _propose_approve(client, token, lead.id)
    with patch("ai.actions.executors.log_activity", side_effect=RuntimeError("x")):
        client.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token}"},
        )
    db = SessionLocal()
    try:
        row = db.query(AiAction).filter(AiAction.action_id == action_id).first()
        assert row.status == "failed"
    finally:
        db.close()
    _cleanup(action_id)


def test_after_failed_executor_session_usable(client, owner_lead):
    token, _, lead = owner_lead
    action_id = _propose_approve(client, token, lead.id)
    with patch("ai.actions.executors.log_activity", side_effect=RuntimeError("x")):
        client.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token}"},
        )
    r = client.post(
        "/api/ai/actions/propose",
        json=_log_activity_propose(lead.id),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    _cleanup(action_id)
    _cleanup(r.json()["action_id"])


def test_execution_result_persisted(client, owner_lead):
    token, _, lead = owner_lead
    action_id = _propose_approve(client, token, lead.id)
    r = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    db = SessionLocal()
    try:
        row = db.query(AiAction).filter(AiAction.action_id == action_id).first()
        assert row.executed_at is not None
        assert row.execution_result_json
        data = json.loads(row.execution_result_json)
        assert data.get("activity_id") is not None
        assert data.get("action_type") == "propose_log_activity"
    finally:
        db.close()
    _cleanup(action_id, r.json().get("activity_id"))


def test_org_b_cannot_get(client, owner_lead):
    token_a, _, lead = owner_lead
    action_id = _propose_approve(client, token_a, lead.id)
    token_b, uid_b = _other_org_token()
    assert (
        client.get(
            f"/api/ai/actions/{action_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        ).status_code
        == 404
    )
    _cleanup(action_id)
    db = SessionLocal()
    try:
        db.query(User).filter(User.id == uid_b).delete()
        db.commit()
    finally:
        db.close()


def test_org_b_cannot_approve(client, owner_lead):
    token_a, _, lead = owner_lead
    action_id = _propose_approve(client, token_a, lead.id)
    token_b, uid_b = _other_org_token()
    assert (
        client.post(
            f"/api/ai/actions/{action_id}/approve",
            headers={"Authorization": f"Bearer {token_b}"},
        ).status_code
        == 404
    )
    _cleanup(action_id)
    db = SessionLocal()
    try:
        db.query(User).filter(User.id == uid_b).delete()
        db.commit()
    finally:
        db.close()


def test_org_b_cannot_execute(client, owner_lead):
    token_a, _, lead = owner_lead
    action_id = _propose_approve(client, token_a, lead.id)
    token_b, uid_b = _other_org_token()
    assert (
        client.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token_b}"},
        ).status_code
        == 404
    )
    _cleanup(action_id)
    db = SessionLocal()
    try:
        db.query(User).filter(User.id == uid_b).delete()
        db.commit()
    finally:
        db.close()


def test_bridge_flag_false_no_proposal(owner_lead, monkeypatch):
    prev = settings.ai_de4_interpret_proposal_bridge_enabled
    settings.ai_de4_interpret_proposal_bridge_enabled = False
    try:
        from ai.capabilities.diagnosis_interpreter import run_diagnosis_interpret

        monkeypatch.setattr("config.settings.diagnosis_engine_enabled", True)
        monkeypatch.setattr("config.settings.ai_diagnosis_interpret_enabled", True)
        monkeypatch.setattr("config.settings.openai_api_key", "sk-test")
        _, user, lead = owner_lead
        db = SessionLocal()
        try:
            payload = {
                "period_type": "monthly",
                "anchor": "2026-08-01",
                "items": [
                    {
                        "diagnosis_id": "follow_up_idle_leads",
                        "top_priority_leads": [{"lead_id": lead.id}],
                        "evidence": {},
                    }
                ],
            }
            interp = (
                '{"summary":"s","why_it_matters":"w","key_findings":[],"confidence":"high",'
                '"recommended_actions":[{"title":"Not ekle","reason":"n","priority":"medium"}]}'
            )
            with patch("ai.capabilities.diagnosis_interpreter.compute_diagnoses", return_value=payload):
                with patch("ai.capabilities.diagnosis_interpreter.ensure_quota"):
                    with patch(
                        "ai.capabilities.diagnosis_interpreter.chat_completion_structured",
                        return_value=(interp, {"total_tokens": 5}),
                    ):
                        result = run_diagnosis_interpret(
                            db,
                            user=user,
                            org_id=user.id,
                            diagnosis_id="follow_up_idle_leads",
                        )
            assert result["interpretation"] is not None
            assert result.get("proposal_bridge") is None
            run_id = result["run_id"]
            assert db.query(AiAction).filter(AiAction.source_interpret_run_id == run_id).count() == 0
            db.query(AiRun).filter(AiRun.id == run_id).delete()
            db.commit()
        finally:
            db.close()
    finally:
        settings.ai_de4_interpret_proposal_bridge_enabled = prev


def test_bridge_flag_true_creates_proposal(owner_lead):
    prev = settings.ai_de4_interpret_proposal_bridge_enabled
    settings.ai_de4_interpret_proposal_bridge_enabled = True
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        recs = [DiagnosisRecommendedAction(title="Not ekle", reason="Bridge on", priority="medium")]
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
        db.query(AiAction).filter(AiAction.action_id == summary.action_ids[0]).delete()
        db.query(AiRun).filter(AiRun.id == run_id).delete()
        db.commit()
    finally:
        db.close()
        settings.ai_de4_interpret_proposal_bridge_enabled = prev


def test_bridge_idempotent_same_run(owner_lead):
    prev = settings.ai_de4_interpret_proposal_bridge_enabled
    settings.ai_de4_interpret_proposal_bridge_enabled = True
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        recs = [DiagnosisRecommendedAction(title="Not ekle", reason="Dup", priority="medium")]
        s1 = bridge_recommended_actions_to_proposals(
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
        for _ in range(9):
            s2 = bridge_recommended_actions_to_proposals(
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
            assert s2.action_ids == s1.action_ids
        assert db.query(AiAction).filter(AiAction.source_interpret_run_id == run_id).count() == 1
        db.query(AiAction).filter(AiAction.source_interpret_run_id == run_id).delete()
        db.query(AiRun).filter(AiRun.id == run_id).delete()
        db.commit()
    finally:
        db.close()
        settings.ai_de4_interpret_proposal_bridge_enabled = prev


def test_bridge_partial_success(owner_lead):
    prev = settings.ai_de4_interpret_proposal_bridge_enabled
    settings.ai_de4_interpret_proposal_bridge_enabled = True
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        recs = [
            DiagnosisRecommendedAction(title="Not ekle", reason="Müşteri için uzun not metni", priority="medium"),
            DiagnosisRecommendedAction(title="Teklifleri takip et", reason="Belirsiz teklif", priority="medium"),
            DiagnosisRecommendedAction(title="Aktivite kaydet", reason="Takip aktivitesi log", priority="medium"),
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


def test_bridge_no_action_no_row(owner_lead):
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
        assert summary.proposed_count == 0
        assert db.query(AiAction).filter(AiAction.source_interpret_run_id == run_id).count() == 0
        db.query(AiRun).filter(AiRun.id == run_id).delete()
        db.commit()
    finally:
        db.close()
        settings.ai_de4_interpret_proposal_bridge_enabled = prev


def test_bridge_disabled_action_skipped(owner_lead):
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


def test_bridge_never_calls_approve_execute(owner_lead):
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
                        DiagnosisRecommendedAction(title="Not ekle", reason="n", priority="medium")
                    ],
                    primary_lead_id=lead.id,
                )
                db.rollback()
        mock_a.assert_not_called()
        mock_e.assert_not_called()
    finally:
        db.close()
        settings.ai_de4_interpret_proposal_bridge_enabled = prev


def test_refresh_new_run_different_source(owner_lead):
    prev = settings.ai_de4_interpret_proposal_bridge_enabled
    settings.ai_de4_interpret_proposal_bridge_enabled = True
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        run1 = _create_interpret_run(db, user.id, user.id)
        run2 = _create_interpret_run(db, user.id, user.id)
        recs = [DiagnosisRecommendedAction(title="Not ekle", reason="Refresh run notu uzun", priority="medium")]
        s1 = bridge_recommended_actions_to_proposals(
            db,
            user_id=user.id,
            org_id=user.id,
            role="owner",
            diagnosis_id="follow_up_idle_leads",
            interpret_run_id=run1,
            recommended_actions=recs,
            primary_lead_id=lead.id,
        )
        s2 = bridge_recommended_actions_to_proposals(
            db,
            user_id=user.id,
            org_id=user.id,
            role="owner",
            diagnosis_id="follow_up_idle_leads",
            interpret_run_id=run2,
            recommended_actions=recs,
            primary_lead_id=lead.id,
        )
        db.commit()
        assert s1.action_ids != s2.action_ids
        r1 = db.query(AiAction).filter(AiAction.action_id == s1.action_ids[0]).first()
        r2 = db.query(AiAction).filter(AiAction.action_id == s2.action_ids[0]).first()
        assert r1.source_interpret_run_id == run1
        assert r2.source_interpret_run_id == run2
        db.query(AiAction).filter(AiAction.action_id.in_(s1.action_ids + s2.action_ids)).delete()
        db.query(AiRun).filter(AiRun.id.in_([run1, run2])).delete()
        db.commit()
    finally:
        db.close()
        settings.ai_de4_interpret_proposal_bridge_enabled = prev


def test_regression_note_append_execute(client, owner_lead):
    token, _, lead = owner_lead
    body = {
        "action_type": "propose_note_append",
        "target_entity": "lead",
        "target_entity_id": lead.id,
        "parameters": {"lead_id": lead.id, "note_text": "Stage 4.5"},
        "reason": "regression",
        "idempotency_key": f"n45-{uuid.uuid4().hex[:10]}",
    }
    r = client.post("/api/ai/actions/propose", json=body, headers={"Authorization": f"Bearer {token}"})
    action_id = r.json()["action_id"]
    client.post(f"/api/ai/actions/{action_id}/approve", headers={"Authorization": f"Bearer {token}"})
    assert (
        client.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 200
    )
    _cleanup(action_id)


def test_cache_hit_bridge_no_duplicate(owner_lead, monkeypatch):
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
                {"title": "Not ekle", "reason": "Cache hit uzun not metni", "priority": "medium"}
            ],
        }
        run = create_run(
            db,
            org_id=user.id,
            requested_by=user.id,
            run_type="diagnosis_interpret",
            input_data={"diagnosis_id": "follow_up_idle_leads"},
        )
        finish_run_success(db, run, output_data={"interpretation": interp})
        db.commit()
        payload = {
            "period_type": "monthly",
            "anchor": "2026-08-01",
            "items": [
                {
                    "diagnosis_id": "follow_up_idle_leads",
                    "top_priority_leads": [{"lead_id": lead.id}],
                    "evidence": {},
                }
            ],
        }
        with patch("ai.capabilities.diagnosis_interpreter.compute_diagnoses", return_value=payload):
            with patch("ai.capabilities.diagnosis_interpreter.ensure_quota"):
                with patch("ai.capabilities.diagnosis_interpreter._find_cached_run", return_value=run):
                    with patch(
                        "ai.capabilities.diagnosis_interpreter.chat_completion_structured",
                    ) as mock_llm:
                        r1 = run_diagnosis_interpret(
                            db, user=user, org_id=user.id, diagnosis_id="follow_up_idle_leads"
                        )
                        r2 = run_diagnosis_interpret(
                            db, user=user, org_id=user.id, diagnosis_id="follow_up_idle_leads"
                        )
        mock_llm.assert_not_called()
        assert r1["proposal_bridge"]["action_ids"] == r2["proposal_bridge"]["action_ids"]
        assert db.query(AiAction).filter(AiAction.source_interpret_run_id == run.id).count() == 1
        db.query(AiAction).filter(AiAction.source_interpret_run_id == run.id).delete()
        db.query(AiRun).filter(AiRun.id == run.id).delete()
        db.commit()
    finally:
        db.close()
        settings.ai_de4_interpret_proposal_bridge_enabled = prev


def test_ai_action_reason_not_raw_llm(owner_lead):
    prev = settings.ai_de4_interpret_proposal_bridge_enabled
    settings.ai_de4_interpret_proposal_bridge_enabled = True
    _, user, lead = owner_lead
    db = SessionLocal()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        recs = [DiagnosisRecommendedAction(title="Not ekle", reason="Güvenli özet", priority="medium")]
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
        row = db.query(AiAction).filter(AiAction.action_id == summary.action_ids[0]).first()
        assert "SECRET_LLM_RAW" not in (row.reason or "")
        assert "Güvenli" in row.reason
        db.query(AiAction).filter(AiAction.action_id == row.action_id).delete()
        db.query(AiRun).filter(AiRun.id == run_id).delete()
        db.commit()
    finally:
        db.close()
        settings.ai_de4_interpret_proposal_bridge_enabled = prev


def test_regression_log_activity_execute(client, owner_lead):
    token, _, lead = owner_lead
    action_id = _propose_approve(client, token, lead.id)
    r = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    _cleanup(action_id, r.json().get("activity_id"))


def test_regression_note_parallel_execute(require_postgres, owner_lead):
    token, user, lead = owner_lead
    c = TestClient(app)
    body = {
        "action_type": "propose_note_append",
        "target_entity": "lead",
        "target_entity_id": lead.id,
        "parameters": {"lead_id": lead.id, "note_text": "conc45"},
        "reason": "c",
        "idempotency_key": f"nc45-{uuid.uuid4().hex[:10]}",
    }
    action_id = c.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    ).json()["action_id"]
    c.post(f"/api/ai/actions/{action_id}/approve", headers={"Authorization": f"Bearer {token}"})
    barrier = threading.Barrier(2)

    def _run():
        local = TestClient(app)
        barrier.wait(timeout=10)
        return local.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token}"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_run)
        f2 = pool.submit(_run)
        r1, r2 = f1.result(timeout=30), f2.result(timeout=30)
    assert r1.status_code == 200 and r2.status_code == 200
    db = SessionLocal()
    try:
        row = db.query(Lead).filter(Lead.id == lead.id).first()
        assert row is not None
    finally:
        db.close()
    _cleanup(action_id)
