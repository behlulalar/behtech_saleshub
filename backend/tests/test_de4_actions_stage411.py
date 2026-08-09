"""DE-4 Stage 4.11 — StatusChangeExecutor (propose_status_change execute v1)."""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ai.actions import get, validate_params
from ai.actions.executors import StatusChangeExecutor
from auth import create_access_token
from config import settings
from database import AiAction, Lead, LeadActivity, SessionLocal, User
from main import app
from security import hash_password
from tests.test_de4_actions_stage42 import _log_activity_propose, _owner_token, _propose_approve
from tests.test_de4_actions_stage42_concurrency import _is_postgres
from tests.test_de4_actions_stage49 import _propose_approve_follow_up


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


def _activity_count(user_id: int, lead_id: int) -> int:
    db = SessionLocal()
    try:
        return (
            db.query(LeadActivity)
            .filter(LeadActivity.user_id == user_id, LeadActivity.lead_id == lead_id)
            .count()
        )
    finally:
        db.close()


def _status_propose(lead_id: int, target: str, key: str | None = None) -> dict:
    return {
        "action_type": "propose_status_change",
        "target_entity": "lead",
        "target_entity_id": lead_id,
        "parameters": {"lead_id": lead_id, "target_status": target},
        "reason": "DE-4 Stage 4.11 status test",
        "idempotency_key": key or f"st411-{uuid.uuid4().hex[:14]}",
    }


def _propose_approve_status(client, token, lead_id, target: str) -> str:
    r = client.post(
        "/api/ai/actions/propose",
        json=_status_propose(lead_id, target),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["execute_enabled_v1"] is True
    action_id = r.json()["action_id"]
    assert client.post(
        f"/api/ai/actions/{action_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    ).status_code == 200
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


def _set_durum(lead_id: int, durum: str) -> str:
    db = SessionLocal()
    try:
        row = db.query(Lead).filter(Lead.id == lead_id).first()
        assert row is not None
        old = row.durum or "Yeni"
        row.durum = durum
        db.commit()
        return old
    finally:
        db.close()


def test_propose_status_change_execute_enabled_v1(client, owner_lead):
    token, _user, lead = owner_lead
    r = client.post(
        "/api/ai/actions/propose",
        json=_status_propose(lead.id, "Takip Bekliyor"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["action_type"] == "propose_status_change"
    assert body["execute_enabled_v1"] is True
    assert body["status"] == "proposed"
    _cleanup(body["action_id"])


def test_employee_cannot_execute_status_change(client, owner_lead):
    token_owner, _user, lead = owner_lead
    action_id = _propose_approve_status(client, token_owner, lead.id, "Olumsuz")
    db = SessionLocal()
    try:
        emp = db.query(User).filter(User.role == "employee").first()
        if not emp:
            pytest.skip("No employee")
        token_emp, _ = create_access_token(emp.id, emp.username, token_version=emp.token_version or 0)
    finally:
        db.close()
    assert (
        client.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token_emp}"},
        ).status_code
        == 403
    )
    _cleanup(action_id)


def test_unknown_action_type_propose_rejected(client, owner_lead):
    token, _user, lead = owner_lead
    body = _status_propose(lead.id, "Yeni")
    body["action_type"] = "propose_not_a_real_action"
    assert (
        client.post("/api/ai/actions/propose", json=body, headers={"Authorization": f"Bearer {token}"}).status_code
        in (400, 422, 403)
    )


def test_registry_status_change_executor():
    ex = get("propose_status_change").executor
    assert isinstance(ex, StatusChangeExecutor)


def test_invalid_target_status_rejected():
    with pytest.raises(Exception):
        validate_params("propose_status_change", {"lead_id": 1, "target_status": "NotARealStatus"})


def test_valid_target_status_accepted():
    m = validate_params("propose_status_change", {"lead_id": 1, "target_status": "Takip Bekliyor"})
    assert m.target_status == "Takip Bekliyor"


def test_status_change_execute_updates_lead(client, owner_lead):
    token, user, lead = owner_lead
    original = _set_durum(lead.id, "Yeni")
    target = "İletişime Geçildi"
    action_id = _propose_approve_status(client, token, lead.id, target)
    before_act = _activity_count(user.id, lead.id)

    r = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["already_executed"] is False
    er = body["action"]["execution_result"]
    assert er["message"] == "status_changed" or body["action"]["execution_result"].get("previous_status")
    assert er.get("new_status") == target
    assert er.get("status_changed") is True
    assert body.get("activity_id")

    db = SessionLocal()
    try:
        row = db.query(Lead).filter(Lead.id == lead.id).first()
        assert row.durum == target
        after_act = (
            db.query(LeadActivity)
            .filter(LeadActivity.user_id == user.id, LeadActivity.lead_id == lead.id)
            .count()
        )
        assert after_act == before_act + 1
        act = db.query(LeadActivity).filter(LeadActivity.id == body["activity_id"]).first()
        assert act.activity_type == "durum_degisti"
    finally:
        db.close()

    _set_durum(lead.id, original)
    _cleanup(action_id, [body["activity_id"]])


def test_status_unchanged_no_extra_activity(client, owner_lead):
    token, user, lead = owner_lead
    current = "Demo Gönderildi"
    _set_durum(lead.id, current)
    action_id = _propose_approve_status(client, token, lead.id, current)
    before_act = _activity_count(user.id, lead.id)

    r = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    er = r.json()["action"]["execution_result"]
    assert er.get("message") == "status_unchanged" or r.json()["action"]["execution_result"].get("status_changed") is False
    assert r.json()["activity_id"] is None

    after_act = _activity_count(user.id, lead.id)
    assert after_act == before_act
    _cleanup(action_id)


def test_execute_without_approve_422(client, owner_lead):
    token, _user, lead = owner_lead
    r = client.post(
        "/api/ai/actions/propose",
        json=_status_propose(lead.id, "Takip Bekliyor"),
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
    orig = _set_durum(lead.id, "Yeni")
    action_id = _propose_approve_status(client, token, lead.id, "Cevap Yok")
    r1 = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200
    count1 = _activity_count(user.id, lead.id)

    r2 = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.json()["already_executed"] is True
    count2 = _activity_count(user.id, lead.id)
    assert count2 == count1

    _set_durum(lead.id, orig)
    _cleanup(action_id, [r1.json().get("activity_id")] if r1.json().get("activity_id") else None)


def test_parallel_execute_single_mutation(require_postgres, owner_lead):
    """Two concurrent execute calls → one durum_degisti activity (PostgreSQL row lock)."""
    token, user, lead = owner_lead
    orig = _set_durum(lead.id, "Yeni")
    client = TestClient(app)
    action_id = _propose_approve_status(client, token, lead.id, "Teklif Verildi")
    before = _activity_count(user.id, lead.id)
    barrier = threading.Barrier(2)

    def _execute_once() -> tuple[int, dict]:
        local_client = TestClient(app)
        barrier.wait(timeout=10)
        for _ in range(40):
            resp = local_client.post(
                f"/api/ai/actions/{action_id}/execute",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code != 409:
                return resp.status_code, resp.json()
            time.sleep(0.05)
        return resp.status_code, resp.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_execute_once)
        f2 = pool.submit(_execute_once)
        (code1, body1), (code2, body2) = f1.result(timeout=60), f2.result(timeout=60)

    assert code1 == 200 and code2 == 200
    already_flags = [body1.get("already_executed"), body2.get("already_executed")]
    assert already_flags.count(True) == 1
    assert already_flags.count(False) == 1
    activity_ids = {body1.get("activity_id"), body2.get("activity_id")}
    activity_ids.discard(None)
    assert len(activity_ids) == 1
    assert _activity_count(user.id, lead.id) == before + 1

    db = SessionLocal()
    try:
        row = db.query(AiAction).filter(AiAction.action_id == action_id).one()
        assert row.status == "executed"
        assert db.query(Lead).filter(Lead.id == lead.id).first().durum == "Teklif Verildi"
    finally:
        db.close()

    _set_durum(lead.id, orig)
    aid = body1.get("activity_id") or body2.get("activity_id")
    _cleanup(action_id, [int(aid)] if aid else None)


def test_org_isolation_execute(client, owner_lead):
    token_a, _ua, lead_a = owner_lead
    action_id = _propose_approve_status(client, token_a, lead_a.id, "Takip Bekliyor")
    db = SessionLocal()
    try:
        user_b = User(
            username=f"de411_{uuid.uuid4().hex[:8]}",
            email=f"de411_{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("testpass123"),
            role="owner",
            email_verified=True,
        )
        db.add(user_b)
        db.commit()
        db.refresh(user_b)
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


def test_executor_failure_sets_failed(client, owner_lead):
    token, _user, lead = owner_lead
    action_id = _propose_approve_status(client, token, lead.id, "Görüşme Planlandı")
    with patch.object(StatusChangeExecutor, "execute", side_effect=RuntimeError("boom")):
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


def test_priority_still_execute_403(client, owner_lead):
    token, _user, lead = owner_lead
    body = {
        "action_type": "propose_priority_change",
        "target_entity": "lead",
        "target_entity_id": lead.id,
        "parameters": {"lead_id": lead.id, "priority": "orta"},
        "reason": "t",
        "idempotency_key": f"pri411-{uuid.uuid4().hex[:12]}",
    }
    r = client.post("/api/ai/actions/propose", json=body, headers={"Authorization": f"Bearer {token}"})
    aid = r.json()["action_id"]
    client.post(f"/api/ai/actions/{aid}/approve", headers={"Authorization": f"Bearer {token}"})
    assert client.post(f"/api/ai/actions/{aid}/execute", headers={"Authorization": f"Bearer {token}"}).status_code == 403
    _cleanup(aid)


def test_log_activity_regression(client, owner_lead):
    token, user, lead = owner_lead
    action_id = _propose_approve(client, token, lead.id)
    r = client.post(f"/api/ai/actions/{action_id}/execute", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    _cleanup(action_id, [r.json().get("activity_id")] if r.json().get("activity_id") else None)


def test_follow_up_regression_still_works(client, owner_lead):
    token, user, lead = owner_lead
    db = SessionLocal()
    try:
        row = db.query(Lead).filter(Lead.id == lead.id).first()
        row.takip_1 = ""
        row.takip_2 = ""
        db.commit()
    finally:
        db.close()
    action_id = _propose_approve_follow_up(client, token, lead.id)
    r = client.post(f"/api/ai/actions/{action_id}/execute", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    _cleanup(action_id, [r.json().get("activity_id")] if r.json().get("activity_id") else None)
