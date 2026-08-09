"""DE-4 Stage 4.9 — FollowUpTaskExecutor (propose_follow_up_task execute v1)."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ai.actions.executors import FollowUpTaskExecutor
from auth import create_access_token
from config import settings
from database import AiAction, Lead, LeadActivity, SessionLocal, User
from main import app
from security import hash_password
from tests.test_de4_actions_stage42 import _log_activity_propose, _owner_token, _propose_approve
from tests.test_de4_actions_stage42_concurrency import _is_postgres
from tests.test_de4_actions_stage43 import _note_append_propose, _propose_approve_note


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


def _follow_up_propose(lead_id: int, key: str | None = None, note: str = "DE-4 Stage 4.9 follow-up") -> dict:
    return {
        "action_type": "propose_follow_up_task",
        "target_entity": "lead",
        "target_entity_id": lead_id,
        "parameters": {"lead_id": lead_id, "note": note},
        "reason": "Stage 4.9 test",
        "idempotency_key": key or f"fu49-{uuid.uuid4().hex[:14]}",
    }


def _propose_approve_follow_up(client, token, lead_id, key: str | None = None) -> str:
    r = client.post(
        "/api/ai/actions/propose",
        json=_follow_up_propose(lead_id, key),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "proposed"
    assert r.json()["execute_enabled_v1"] is True
    action_id = r.json()["action_id"]
    r2 = client.post(
        f"/api/ai/actions/{action_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "approved"
    return action_id


def _cleanup(action_id: str, activity_ids: list[int] | None = None) -> None:
    db = SessionLocal()
    try:
        for aid in activity_ids or []:
            db.query(LeadActivity).filter(LeadActivity.id == aid).delete()
        db.query(AiAction).filter(AiAction.action_id == action_id).delete()
        db.commit()
    finally:
        db.close()


def _save_takip(lead_id: int) -> tuple[str, str]:
    db = SessionLocal()
    try:
        row = db.query(Lead).filter(Lead.id == lead_id).first()
        assert row is not None
        return row.takip_1 or "", row.takip_2 or ""
    finally:
        db.close()


def _restore_takip(lead_id: int, t1: str, t2: str) -> None:
    db = SessionLocal()
    try:
        row = db.query(Lead).filter(Lead.id == lead_id).first()
        if row:
            row.takip_1 = t1
            row.takip_2 = t2
            db.commit()
    finally:
        db.close()


def test_follow_up_task_scheduled_on_execute(client, owner_lead):
    token, user, lead = owner_lead
    t1, t2 = _save_takip(lead.id)
    db = SessionLocal()
    try:
        row = db.query(Lead).filter(Lead.id == lead.id).first()
        row.takip_1 = ""
        row.takip_2 = ""
        db.commit()
    finally:
        db.close()

    action_id = _propose_approve_follow_up(client, token, lead.id)
    before_act = (
        SessionLocal()
        .query(LeadActivity)
        .filter(LeadActivity.user_id == user.id, LeadActivity.lead_id == lead.id)
        .count()
    )
    SessionLocal().close()

    r = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["already_executed"] is False
    assert body["action"]["status"] == "executed"
    er = body["action"]["execution_result"]
    assert er.get("action_type") == "propose_follow_up_task"
    assert er.get("lead_id") == lead.id
    assert er.get("task_scheduled") is True
    assert er.get("takip_field") in ("takip_1", "takip_2")
    assert er.get("scheduled_date")

    db = SessionLocal()
    try:
        row = db.query(Lead).filter(Lead.id == lead.id).first()
        assert getattr(row, er["takip_field"]) == er["scheduled_date"]
        after_act = (
            db.query(LeadActivity)
            .filter(LeadActivity.user_id == user.id, LeadActivity.lead_id == lead.id)
            .count()
        )
        assert after_act == before_act + 1
    finally:
        db.close()

    activity_id = body.get("activity_id")
    _restore_takip(lead.id, t1, t2)
    _cleanup(action_id, [activity_id] if activity_id else None)


def test_execute_without_approve_returns_422(client, owner_lead):
    token, _user, lead = owner_lead
    r = client.post(
        "/api/ai/actions/propose",
        json=_follow_up_propose(lead.id),
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


def test_duplicate_execute_idempotent(client, owner_lead):
    token, user, lead = owner_lead
    t1, t2 = _save_takip(lead.id)
    action_id = _propose_approve_follow_up(client, token, lead.id)
    r1 = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200
    act_count_after_first = (
        SessionLocal()
        .query(LeadActivity)
        .filter(LeadActivity.user_id == user.id, LeadActivity.lead_id == lead.id)
        .count()
    )
    SessionLocal().close()

    r2 = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    assert r2.json()["already_executed"] is True
    assert r2.json()["activity_id"] == r1.json()["activity_id"]

    act_count_after_second = (
        SessionLocal()
        .query(LeadActivity)
        .filter(LeadActivity.user_id == user.id, LeadActivity.lead_id == lead.id)
        .count()
    )
    SessionLocal().close()
    assert act_count_after_second == act_count_after_first

    _restore_takip(lead.id, t1, t2)
    _cleanup(action_id, [r1.json()["activity_id"]] if r1.json().get("activity_id") else None)


def test_parallel_execute_single_task(client, owner_lead):
    if not _is_postgres():
        pytest.skip("PostgreSQL required")
    token, user, lead = owner_lead
    t1, t2 = _save_takip(lead.id)
    action_id = _propose_approve_follow_up(client, token, lead.id)
    before = (
        SessionLocal()
        .query(LeadActivity)
        .filter(LeadActivity.user_id == user.id, LeadActivity.lead_id == lead.id)
        .count()
    )
    SessionLocal().close()

    def _exec():
        c = TestClient(app)
        return c.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token}"},
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: _exec(), range(4)))

    success_runs = [r for r in results if r.status_code == 200]
    assert len(success_runs) >= 1
    assert sum(1 for r in success_runs if r.json().get("already_executed") is False) == 1

    after = (
        SessionLocal()
        .query(LeadActivity)
        .filter(LeadActivity.user_id == user.id, LeadActivity.lead_id == lead.id)
        .count()
    )
    SessionLocal().close()
    assert after == before + 1

    first = next(r for r in success_runs if r.json().get("already_executed") is False)
    _restore_takip(lead.id, t1, t2)
    _cleanup(action_id, [first.json().get("activity_id")] if first.json().get("activity_id") else None)


def test_follow_up_org_isolation_execute(client, owner_lead):
    token_a, _ua, lead_a = owner_lead
    action_id = _propose_approve_follow_up(client, token_a, lead_a.id)
    db = SessionLocal()
    try:
        user_b = User(
            username=f"de49_{uuid.uuid4().hex[:8]}",
            email=f"de49_{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("testpass123"),
            role="owner",
            email_verified=True,
        )
        db.add(user_b)
        db.commit()
        token_b, _ = create_access_token(user_b.id, user_b.username, token_version=0)
        uid_b = user_b.id
    finally:
        db.close()

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


def test_invalid_parameters_execute_422(client, owner_lead):
    token, _user, lead = owner_lead
    body = _follow_up_propose(lead.id)
    body["parameters"] = {"lead_id": 0, "note": "x"}
    r = client.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code in (400, 422, 404)


def test_executor_failure_safe_error(client, owner_lead):
    token, _user, lead = owner_lead
    action_id = _propose_approve_follow_up(client, token, lead.id)
    with patch.object(FollowUpTaskExecutor, "execute", side_effect=RuntimeError("secret boom")):
        r = client.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 502
    assert "boom" not in (r.json().get("detail") or "")
    db = SessionLocal()
    try:
        assert db.query(AiAction).filter(AiAction.action_id == action_id).first().status == "failed"
    finally:
        db.close()
    _cleanup(action_id)


def test_log_activity_regression(client, owner_lead):
    token, user, lead = owner_lead
    action_id = _propose_approve(client, token, lead.id)
    r = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    _cleanup(action_id, [r.json().get("activity_id")] if r.json().get("activity_id") else None)


def test_note_append_regression(client, owner_lead):
    token, _user, lead = owner_lead
    action_id = _propose_approve_note(client, token, lead.id)
    r = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    _cleanup(action_id)


def test_priority_change_still_execute_403(client, owner_lead):
    token, _user, lead = owner_lead
    body = {
        "action_type": "propose_priority_change",
        "target_entity": "lead",
        "target_entity_id": lead.id,
        "parameters": {"lead_id": lead.id, "priority": "orta"},
        "reason": "t",
        "idempotency_key": f"pri-{uuid.uuid4().hex[:12]}",
    }
    r = client.post("/api/ai/actions/propose", json=body, headers={"Authorization": f"Bearer {token}"})
    action_id = r.json()["action_id"]
    client.post(f"/api/ai/actions/{action_id}/approve", headers={"Authorization": f"Bearer {token}"})
    assert (
        client.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 403
    )
    _cleanup(action_id)
