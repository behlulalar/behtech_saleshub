"""DE-4 Stage 4.2 — approve, execute v1 (propose_log_activity only)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from auth import create_access_token
from config import settings
from database import AiAction, Lead, LeadActivity, SessionLocal, User
from main import app
from security import hash_password


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


def _owner_token(db) -> tuple[str, User]:
    user = db.query(User).filter(User.role == "owner").first()
    if not user:
        pytest.skip("No owner user")
    token, _ = create_access_token(user.id, user.username, token_version=user.token_version or 0)
    return token, user


def _log_activity_propose(lead_id: int, key: str | None = None) -> dict:
    return {
        "action_type": "propose_log_activity",
        "target_entity": "lead",
        "target_entity_id": lead_id,
        "parameters": {
            "lead_id": lead_id,
            "activity_type": "takip_yapildi",
            "title": "DE-4 execute test",
            "description": "Stage 4.2",
        },
        "reason": "Test",
        "idempotency_key": key or f"exec-{uuid.uuid4().hex[:14]}",
    }


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


def _propose_approve(client, token, lead_id, key: str | None = None) -> str:
    body = _log_activity_propose(lead_id, key)
    r = client.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    action_id = r.json()["action_id"]
    r2 = client.post(
        f"/api/ai/actions/{action_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "approved"
    return action_id


def test_approve_unauthenticated(client, owner_lead):
    token, _user, lead = owner_lead
    action_id = _propose_approve(client, token, lead.id)
    r = client.post(f"/api/ai/actions/{action_id}/approve")
    assert r.status_code == 401


def test_execute_unauthenticated(client, owner_lead):
    token, _user, lead = owner_lead
    action_id = _propose_approve(client, token, lead.id)
    r = client.post(f"/api/ai/actions/{action_id}/execute")
    assert r.status_code == 401


def test_get_action_other_org(client, owner_lead):
    token_a, _user_a, lead_a = owner_lead
    action_id = _propose_approve(client, token_a, lead_a.id)

    db = SessionLocal()
    try:
        user_b = User(
            username=f"de42_{uuid.uuid4().hex[:8]}",
            email=f"de42_{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("testpass123"),
            role="owner",
            email_verified=True,
        )
        db.add(user_b)
        db.commit()
        db.refresh(user_b)
        token_b, _ = create_access_token(user_b.id, user_b.username, token_version=0)
    finally:
        db.close()

    assert (
        client.get(
            f"/api/ai/actions/{action_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token_b}"},
        ).status_code
        == 404
    )

    db = SessionLocal()
    try:
        db.query(AiAction).filter(AiAction.action_id == action_id).delete()
        db.query(User).filter(User.id == user_b.id).delete()
        db.commit()
    finally:
        db.close()


def test_proposed_to_approved(client, owner_lead):
    token, _user, lead = owner_lead
    body = _log_activity_propose(lead.id)
    r = client.post(
        "/api/ai/actions/propose",
        json=body,
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

    db = SessionLocal()
    try:
        db.query(AiAction).filter(AiAction.action_id == action_id).delete()
        db.commit()
    finally:
        db.close()


def test_approve_twice_rejected(client, owner_lead):
    token, _user, lead = owner_lead
    action_id = _propose_approve(client, token, lead.id)
    r = client.post(
        f"/api/ai/actions/{action_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422

    db = SessionLocal()
    try:
        db.query(AiAction).filter(AiAction.action_id == action_id).delete()
        db.commit()
    finally:
        db.close()


def test_execute_creates_activity(client, owner_lead):
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

    r = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload["action"]["status"] == "executed"
    assert payload["activity_id"] is not None

    db = SessionLocal()
    try:
        after = (
            db.query(LeadActivity)
            .filter(LeadActivity.user_id == user.id, LeadActivity.lead_id == lead.id)
            .count()
        )
        assert after == before + 1
        db.query(LeadActivity).filter(LeadActivity.id == payload["activity_id"]).delete()
        db.query(AiAction).filter(AiAction.action_id == action_id).delete()
        db.commit()
    finally:
        db.close()


def test_proposed_execute_rejected(client, owner_lead):
    token, _user, lead = owner_lead
    body = _log_activity_propose(lead.id)
    r = client.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    action_id = r.json()["action_id"]
    r2 = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 422

    db = SessionLocal()
    try:
        db.query(AiAction).filter(AiAction.action_id == action_id).delete()
        db.commit()
    finally:
        db.close()


def test_execute_stub_action_rejected(client, owner_lead):
    token, _user, lead = owner_lead
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
        "idempotency_key": f"stub-{uuid.uuid4().hex[:12]}",
    }
    r = client.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    action_id = r.json()["action_id"]
    client.post(
        f"/api/ai/actions/{action_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    r_exec = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_exec.status_code == 403

    db = SessionLocal()
    try:
        db.query(AiAction).filter(AiAction.action_id == action_id).delete()
        db.commit()
    finally:
        db.close()


def test_execute_duplicate_no_double_mutation(client, owner_lead):
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
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json()["already_executed"] is True

    db = SessionLocal()
    try:
        after = (
            db.query(LeadActivity)
            .filter(LeadActivity.user_id == user.id, LeadActivity.lead_id == lead.id)
            .count()
        )
        assert after == before + 1
        aid = r1.json()["activity_id"]
        if aid:
            db.query(LeadActivity).filter(LeadActivity.id == aid).delete()
        db.query(AiAction).filter(AiAction.action_id == action_id).delete()
        db.commit()
    finally:
        db.close()


def test_execute_missing_idempotency_key(client, owner_lead):
    token, _user, lead = owner_lead
    body = _log_activity_propose(lead.id)
    del body["idempotency_key"]
    r = client.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    action_id = r.json()["action_id"]
    client.post(
        f"/api/ai/actions/{action_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    r_exec = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_exec.status_code == 422

    db = SessionLocal()
    try:
        db.query(AiAction).filter(AiAction.action_id == action_id).delete()
        db.commit()
    finally:
        db.close()


def test_executor_failure_sets_failed(client, owner_lead):
    token, _user, lead = owner_lead
    action_id = _propose_approve(client, token, lead.id)

    with patch("ai.actions.executors.log_activity", side_effect=RuntimeError("boom")):
        r = client.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 502

    db = SessionLocal()
    try:
        row = db.query(AiAction).filter(AiAction.action_id == action_id).first()
        assert row.status == "failed"
        db.query(AiAction).filter(AiAction.action_id == action_id).delete()
        db.commit()
    finally:
        db.close()


def test_execute_other_org_lead(client, owner_lead):
    token, _user, _lead = owner_lead
    db = SessionLocal()
    other_id = None
    foreign_lead_id = None
    try:
        other = User(
            username=f"de42l_{uuid.uuid4().hex[:8]}",
            email=f"l_{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("testpass123"),
            role="owner",
            email_verified=True,
        )
        db.add(other)
        db.flush()
        other_id = other.id
        fl = Lead(user_id=other.id, isletme_adi="X", durum="Yeni", category="genel")
        db.add(fl)
        db.commit()
        foreign_lead_id = fl.id
    finally:
        db.close()

    body = _log_activity_propose(foreign_lead_id)
    r = client.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404

    db = SessionLocal()
    try:
        db.query(Lead).filter(Lead.id == foreign_lead_id).delete()
        db.query(User).filter(User.id == other_id).delete()
        db.commit()
    finally:
        db.close()
