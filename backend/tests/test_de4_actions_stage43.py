"""DE-4 Stage 4.3 — propose_note_append executor + execute allowlist."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ai.actions.executors import NoteAppendExecutor
from auth import create_access_token
from config import settings
from database import AiAction, Lead, LeadActivity, SessionLocal, User
from main import app
from security import hash_password
from tests.test_de4_actions_stage42 import _log_activity_propose, _owner_token, _propose_approve


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
        pytest.skip("Concurrency tests require PostgreSQL")


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


def _note_append_propose(lead_id: int, key: str | None = None, note: str = "DE-4 Stage 4.3 not") -> dict:
    return {
        "action_type": "propose_note_append",
        "target_entity": "lead",
        "target_entity_id": lead_id,
        "parameters": {
            "lead_id": lead_id,
            "note_text": note,
            "separator": "\n\n",
        },
        "reason": "Not ekleme testi",
        "idempotency_key": key or f"note-{uuid.uuid4().hex[:14]}",
    }


def _cleanup(action_id: str) -> None:
    db = SessionLocal()
    try:
        db.query(AiAction).filter(AiAction.action_id == action_id).delete()
        db.commit()
    finally:
        db.close()


def _propose_approve_note(client, token, lead_id, key: str | None = None) -> str:
    body = _note_append_propose(lead_id, key)
    r = client.post("/api/ai/actions/propose", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    action_id = r.json()["action_id"]
    r2 = client.post(
        f"/api/ai/actions/{action_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    return action_id


def test_note_append_propose_approve_execute(client, owner_lead):
    token, user, lead = owner_lead
    db = SessionLocal()
    try:
        row = db.query(Lead).filter(Lead.id == lead.id).first()
        original = row.notlar or ""
    finally:
        db.close()

    action_id = _propose_approve_note(client, token, lead.id)
    r = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["action"]["status"] == "executed"
    assert data["already_executed"] is False
    assert data["action"]["execution_result"].get("notlar_length_after", 0) > 0

    db = SessionLocal()
    try:
        row = db.query(Lead).filter(Lead.id == lead.id).first()
        assert "DE-4 Stage 4.3 not" in (row.notlar or "")
        row.notlar = original
        db.commit()
    finally:
        db.close()
    _cleanup(action_id)


def test_note_append_invalid_parameters(client, owner_lead):
    token, _user, lead = owner_lead
    body = _note_append_propose(lead.id)
    body["parameters"] = {"lead_id": lead.id}
    r = client.post("/api/ai/actions/propose", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422


def test_note_execute_before_approve(client, owner_lead):
    token, _user, lead = owner_lead
    body = _note_append_propose(lead.id)
    r = client.post("/api/ai/actions/propose", json=body, headers={"Authorization": f"Bearer {token}"})
    action_id = r.json()["action_id"]
    r2 = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 422
    _cleanup(action_id)


def test_note_duplicate_and_triple_execute(client, owner_lead):
    token, _user, lead = owner_lead
    db = SessionLocal()
    try:
        original = (db.query(Lead).filter(Lead.id == lead.id).first().notlar or "")
        original_hits = original.count("DE-4 Stage 4.3 not")
    finally:
        db.close()

    action_id = _propose_approve_note(client, token, lead.id)
    bodies = []
    for _ in range(3):
        r = client.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token}"},
        )
        bodies.append(r.json())
    assert bodies[0]["already_executed"] is False
    assert bodies[1]["already_executed"] is True
    assert bodies[2]["already_executed"] is True
    len_after_first = bodies[0]["action"]["execution_result"]["notlar_length_after"]
    assert bodies[1]["action"]["execution_result"]["notlar_length_after"] == len_after_first

    db = SessionLocal()
    try:
        row = db.query(Lead).filter(Lead.id == lead.id).first()
        assert row.notlar.count("DE-4 Stage 4.3 not") == original_hits + 1
        row.notlar = original
        db.commit()
    finally:
        db.close()
    _cleanup(action_id)


def test_note_executor_failure_and_session_ok(client, owner_lead):
    token, _user, lead = owner_lead
    action_id = _propose_approve_note(client, token, lead.id)
    with patch.object(NoteAppendExecutor, "execute", side_effect=RuntimeError("boom")):
        r = client.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 502
    assert "boom" not in r.json().get("detail", "")

    db = SessionLocal()
    try:
        assert db.query(AiAction).filter(AiAction.action_id == action_id).first().status == "failed"
    finally:
        db.close()

    r2 = client.post(
        "/api/ai/actions/propose",
        json=_note_append_propose(lead.id),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    _cleanup(action_id)
    _cleanup(r2.json()["action_id"])


def test_note_org_isolation_execute(client, owner_lead):
    token_a, _ua, lead_a = owner_lead
    action_id = _propose_approve_note(client, token_a, lead_a.id)

    db = SessionLocal()
    try:
        user_b = User(
            username=f"de43_{uuid.uuid4().hex[:8]}",
            email=f"de43_{uuid.uuid4().hex[:8]}@example.com",
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


def test_employee_cannot_propose_note(client, owner_lead):
    db = SessionLocal()
    try:
        emp = db.query(User).filter(User.role == "employee").first()
        if not emp:
            pytest.skip("No employee")
        token, _ = create_access_token(emp.id, emp.username, token_version=emp.token_version or 0)
        lead = db.query(Lead).filter(Lead.user_id == emp.owner_id).first()
        if not lead:
            pytest.skip("No lead for employee org")
    finally:
        db.close()

    body = _note_append_propose(lead.id)
    r = client.post("/api/ai/actions/propose", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_meeting_still_not_executable(client, owner_lead):
    token, _user, lead = owner_lead
    body = {
        "action_type": "propose_meeting_date",
        "target_entity": "lead",
        "target_entity_id": lead.id,
        "parameters": {
            "lead_id": lead.id,
            "meeting_date": "2026-08-15",
            "meeting_time": "",
        },
        "reason": "t",
        "idempotency_key": f"mt-{uuid.uuid4().hex[:12]}",
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


def test_log_activity_regression_still_executes(client, owner_lead):
    token, user, lead = owner_lead
    action_id = _propose_approve(client, token, lead.id)
    before = SessionLocal().query(LeadActivity).filter(
        LeadActivity.user_id == user.id, LeadActivity.lead_id == lead.id
    ).count()
    SessionLocal().close()
    r = client.post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["activity_id"] is not None
    db = SessionLocal()
    try:
        after = db.query(LeadActivity).filter(
            LeadActivity.user_id == user.id, LeadActivity.lead_id == lead.id
        ).count()
        assert after == before + 1
        db.query(LeadActivity).filter(LeadActivity.id == r.json()["activity_id"]).delete()
        db.query(AiAction).filter(AiAction.action_id == action_id).delete()
        db.commit()
    finally:
        db.close()


def test_note_parallel_execute_single_mutation(require_postgres, client, owner_lead):
    token, _user, lead = owner_lead
    db = SessionLocal()
    try:
        original = (db.query(Lead).filter(Lead.id == lead.id).first().notlar or "")
    finally:
        db.close()

    marker = f"PAR-{uuid.uuid4().hex[:8]}"
    key = f"conc-note-{uuid.uuid4().hex[:12]}"
    body = _note_append_propose(lead.id, key=key, note=marker)
    r = client.post("/api/ai/actions/propose", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    action_id = r.json()["action_id"]
    r2 = client.post(
        f"/api/ai/actions/{action_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200

    barrier = threading.Barrier(2)

    def _exec():
        local = TestClient(app)
        barrier.wait(timeout=10)
        return local.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token}"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_exec)
        f2 = pool.submit(_exec)
        ra, rb = f1.result(timeout=30), f2.result(timeout=30)

    assert ra.status_code == 200 and rb.status_code == 200
    flags = [ra.json()["already_executed"], rb.json()["already_executed"]]
    assert flags.count(False) == 1 and flags.count(True) == 1

    db = SessionLocal()
    try:
        notlar = db.query(Lead).filter(Lead.id == lead.id).first().notlar or ""
        assert notlar.count(marker) == 1
        db.query(Lead).filter(Lead.id == lead.id).update({"notlar": original})
        db.query(AiAction).filter(AiAction.action_id == action_id).delete()
        db.commit()
    finally:
        db.close()


def test_note_unauthenticated(client, owner_lead):
    token, _user, lead = owner_lead
    action_id = _propose_approve_note(client, token, lead.id)
    assert client.post(f"/api/ai/actions/{action_id}/execute").status_code == 401
    _cleanup(action_id)


def test_blocked_whatsapp_not_proposable(client, owner_lead):
    token, _user, lead = owner_lead
    body = {
        "action_type": "send_whatsapp_message",
        "target_entity": "lead",
        "target_entity_id": lead.id,
        "parameters": {"lead_id": lead.id},
        "reason": "x",
        "idempotency_key": f"wa-{uuid.uuid4().hex[:12]}",
    }
    r = client.post("/api/ai/actions/propose", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_note_parallel_approve_once(require_postgres, client, owner_lead):
    token, _user, lead = owner_lead
    body = _note_append_propose(lead.id)
    r = client.post("/api/ai/actions/propose", json=body, headers={"Authorization": f"Bearer {token}"})
    action_id = r.json()["action_id"]
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
        a, b = f1.result(timeout=30), f2.result(timeout=30)
    assert {a.status_code, b.status_code} == {200, 422}
    db = SessionLocal()
    try:
        assert db.query(AiAction).filter(AiAction.action_id == action_id).first().status == "approved"
        db.query(AiAction).filter(AiAction.action_id == action_id).delete()
        db.commit()
    finally:
        db.close()
