"""DE-4 Stage 4.12 — PriorityChangeExecutor (propose_priority_change execute v1)."""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ai.actions import get, validate_params
from ai.actions.executors import PriorityChangeExecutor
from auth import create_access_token
from config import settings
from database import AiAction, Lead, LeadActivity, SessionLocal, User
from main import app
from security import hash_password
from tests.test_de4_actions_stage411 import (
    _propose_approve_status,
    _status_propose,
)
from tests.test_de4_actions_stage42 import _owner_token, _propose_approve
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


def _priority_propose(lead_id: int, priority: str, key: str | None = None) -> dict:
    return {
        "action_type": "propose_priority_change",
        "target_entity": "lead",
        "target_entity_id": lead_id,
        "parameters": {"lead_id": lead_id, "priority": priority},
        "reason": "DE-4 Stage 4.12 priority test",
        "idempotency_key": key or f"pr412-{uuid.uuid4().hex[:14]}",
    }


def _propose_approve_priority(client, token, lead_id, priority: str) -> str:
    r = client.post(
        "/api/ai/actions/propose",
        json=_priority_propose(lead_id, priority),
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


def _set_oncelik(lead_id: int, oncelik: str) -> str:
    db = SessionLocal()
    try:
        row = db.query(Lead).filter(Lead.id == lead_id).first()
        assert row is not None
        old = (row.oncelik or "orta").strip().lower() or "orta"
        row.oncelik = oncelik
        db.commit()
        return old
    finally:
        db.close()


def test_registry_priority_change_executor():
    ex = get("propose_priority_change").executor
    assert isinstance(ex, PriorityChangeExecutor)


def test_invalid_priority_rejected():
    with pytest.raises(Exception):
        validate_params("propose_priority_change", {"lead_id": 1, "priority": "urgent"})


def test_valid_priority_accepted():
    m = validate_params("propose_priority_change", {"lead_id": 1, "priority": "yuksek"})
    assert m.priority == "yuksek"


def test_propose_execute_enabled_v1(client, owner_lead):
    token, _user, lead = owner_lead
    r = client.post(
        "/api/ai/actions/propose",
        json=_priority_propose(lead.id, "orta"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["action_type"] == "propose_priority_change"
    assert body["execute_enabled_v1"] is True
    _cleanup(body["action_id"])


def test_priority_execute_updates_lead(client, owner_lead):
    token, user, lead = owner_lead
    original = _set_oncelik(lead.id, "dusuk")
    target = "yuksek"
    action_id = _propose_approve_priority(client, token, lead.id, target)
    before_act = _activity_count(user.id, lead.id)

    r = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["already_executed"] is False
    assert body.get("activity_id") is None
    er = body["action"]["execution_result"]
    assert er.get("priority_changed") is True
    assert er.get("previous_priority") == "dusuk"
    assert er.get("new_priority") == target

    db = SessionLocal()
    try:
        row = db.query(Lead).filter(Lead.id == lead.id).first()
        assert row.oncelik == target
        after_act = (
            db.query(LeadActivity)
            .filter(LeadActivity.user_id == user.id, LeadActivity.lead_id == lead.id)
            .count()
        )
        assert after_act == before_act
    finally:
        db.close()

    _set_oncelik(lead.id, original)
    _cleanup(action_id)


def test_priority_unchanged_no_op(client, owner_lead):
    token, user, lead = owner_lead
    _set_oncelik(lead.id, "orta")
    action_id = _propose_approve_priority(client, token, lead.id, "orta")
    before_act = _activity_count(user.id, lead.id)

    r = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    er = r.json()["action"]["execution_result"]
    assert er.get("priority_changed") is False
    assert er.get("message") == "priority_unchanged" or er.get("priority_changed") is False
    assert r.json().get("activity_id") is None
    assert _activity_count(user.id, lead.id) == before_act
    _cleanup(action_id)


def test_execute_without_approve_422(client, owner_lead):
    token, _user, lead = owner_lead
    r = client.post(
        "/api/ai/actions/propose",
        json=_priority_propose(lead.id, "orta"),
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
    orig = _set_oncelik(lead.id, "orta")
    action_id = _propose_approve_priority(client, token, lead.id, "dusuk")
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
    assert _activity_count(user.id, lead.id) == count1

    db = SessionLocal()
    try:
        assert db.query(Lead).filter(Lead.id == lead.id).first().oncelik == "dusuk"
    finally:
        db.close()

    _set_oncelik(lead.id, orig)
    _cleanup(action_id)


def test_parallel_execute_single_mutation(require_postgres, owner_lead):
    token, user, lead = owner_lead
    orig = _set_oncelik(lead.id, "orta")
    client = TestClient(app)
    action_id = _propose_approve_priority(client, token, lead.id, "yuksek")
    before_act = _activity_count(user.id, lead.id)
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
    flags = [body1.get("already_executed"), body2.get("already_executed")]
    assert flags.count(True) == 1 and flags.count(False) == 1
    assert _activity_count(user.id, lead.id) == before_act

    db = SessionLocal()
    try:
        row = db.query(AiAction).filter(AiAction.action_id == action_id).one()
        assert row.status == "executed"
        assert db.query(Lead).filter(Lead.id == lead.id).first().oncelik == "yuksek"
    finally:
        db.close()

    _set_oncelik(lead.id, orig)
    _cleanup(action_id)


def test_org_isolation_execute(client, owner_lead):
    token_a, _ua, lead_a = owner_lead
    action_id = _propose_approve_priority(client, token_a, lead_a.id, "dusuk")
    db = SessionLocal()
    try:
        user_b = User(
            username=f"de412_{uuid.uuid4().hex[:8]}",
            email=f"de412_{uuid.uuid4().hex[:8]}@example.com",
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


def test_employee_cannot_execute_priority(client, owner_lead):
    token_owner, _user, lead = owner_lead
    action_id = _propose_approve_priority(client, token_owner, lead.id, "yuksek")
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
    body = _priority_propose(lead.id, "orta")
    body["action_type"] = "propose_not_a_real_action"
    assert (
        client.post("/api/ai/actions/propose", json=body, headers={"Authorization": f"Bearer {token}"}).status_code
        in (400, 422, 403)
    )


def test_executor_failure_sets_failed(client, owner_lead):
    token, _user, lead = owner_lead
    action_id = _propose_approve_priority(client, token, lead.id, "dusuk")
    with patch.object(PriorityChangeExecutor, "execute", side_effect=RuntimeError("boom")):
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
    token, _user, lead = owner_lead
    action_id = _propose_approve(client, token, lead.id)
    r = client.post(f"/api/ai/actions/{action_id}/execute", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    _cleanup(action_id, [r.json().get("activity_id")] if r.json().get("activity_id") else None)


def test_follow_up_regression(client, owner_lead):
    token, _user, lead = owner_lead
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


def test_status_change_regression(client, owner_lead):
    token, user, lead = owner_lead
    orig = lead.durum
    db = SessionLocal()
    try:
        row = db.query(Lead).filter(Lead.id == lead.id).first()
        row.durum = "Yeni"
        db.commit()
    finally:
        db.close()
    action_id = _propose_approve_status(client, token, lead.id, "Takip Bekliyor")
    r = client.post(f"/api/ai/actions/{action_id}/execute", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    _cleanup(action_id, [r.json().get("activity_id")] if r.json().get("activity_id") else None)
    db = SessionLocal()
    try:
        row = db.query(Lead).filter(Lead.id == lead.id).first()
        row.durum = orig or "Yeni"
        db.commit()
    finally:
        db.close()
