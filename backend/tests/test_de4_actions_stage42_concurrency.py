"""DE-4 Stage 4.2 — concurrency / idempotency hardening (PostgreSQL)."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from auth import create_access_token
from config import settings
from database import AiAction, Lead, LeadActivity, SessionLocal, User
from main import app
from security import hash_password

# Reuse helpers from stage42 functional tests
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
        pytest.skip("Concurrency hardening tests require PostgreSQL (SELECT FOR UPDATE)")


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


def _cleanup_action(action_id: str, activity_id: int | None = None) -> None:
    db = SessionLocal()
    try:
        if activity_id:
            db.query(LeadActivity).filter(LeadActivity.id == activity_id).delete()
        db.query(AiAction).filter(AiAction.action_id == action_id).delete()
        db.commit()
    finally:
        db.close()


def test_parallel_execute_single_mutation(require_postgres, owner_lead):
    """Two concurrent execute HTTP calls → one LeadActivity, one executed transition."""
    token, user, lead = owner_lead
    key = f"conc-exec-{uuid.uuid4().hex[:12]}"
    client = TestClient(app)
    action_id = _propose_approve(client, token, lead.id, key=key)

    before = _activity_count(user.id, lead.id)
    barrier = threading.Barrier(2)

    def _execute_once() -> tuple[int, dict]:
        local_client = TestClient(app)
        barrier.wait(timeout=10)
        resp = local_client.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token}"},
        )
        return resp.status_code, resp.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_execute_once)
        f2 = pool.submit(_execute_once)
        (code1, body1), (code2, body2) = f1.result(timeout=30), f2.result(timeout=30)

    assert code1 == 200
    assert code2 == 200

    already_flags = [body1.get("already_executed"), body2.get("already_executed")]
    assert already_flags.count(True) == 1
    assert already_flags.count(False) == 1

    activity_ids = {body1.get("activity_id"), body2.get("activity_id")}
    activity_ids.discard(None)
    assert len(activity_ids) == 1

    after = _activity_count(user.id, lead.id)
    assert after == before + 1

    db = SessionLocal()
    try:
        row = db.query(AiAction).filter(AiAction.action_id == action_id).one()
        assert row.status == "executed"
        assert row.executed_at is not None
    finally:
        db.close()

    aid = body1.get("activity_id") or body2.get("activity_id")
    _cleanup_action(action_id, int(aid) if aid else None)


def test_sequential_triple_execute_idempotent(owner_lead):
    token, user, lead = owner_lead
    client = TestClient(app)
    action_id = _propose_approve(client, token, lead.id)

    before = _activity_count(user.id, lead.id)
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
    assert bodies[0].get("already_executed") is False
    assert bodies[1].get("already_executed") is True
    assert bodies[2].get("already_executed") is True
    assert _activity_count(user.id, lead.id) == before + 1

    aid = bodies[0].get("activity_id")
    _cleanup_action(action_id, int(aid) if aid else None)


def test_executor_failure_no_activity_and_session_usable(owner_lead):
    token, user, lead = owner_lead
    client = TestClient(app)
    action_id = _propose_approve(client, token, lead.id)

    before = _activity_count(user.id, lead.id)
    with patch("ai.actions.executors.log_activity", side_effect=RuntimeError("boom")):
        r = client.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 502
    detail = r.json().get("detail", "")
    assert isinstance(detail, str)
    assert "boom" not in detail
    assert "Traceback" not in detail

    assert _activity_count(user.id, lead.id) == before

    db = SessionLocal()
    try:
        row = db.query(AiAction).filter(AiAction.action_id == action_id).first()
        assert row is not None
        assert row.status == "failed"
    finally:
        db.close()

    # Independent follow-up request still works (DB session / app healthy)
    body = _log_activity_propose(lead.id)
    r2 = client.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    new_id = r2.json()["action_id"]
    _cleanup_action(action_id)
    _cleanup_action(new_id)


def test_parallel_approve_once(require_postgres, owner_lead):
    token, _user, lead = owner_lead
    key = f"conc-appr-{uuid.uuid4().hex[:12]}"
    client = TestClient(app)
    body = _log_activity_propose(lead.id, key=key)
    r = client.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    action_id = r.json()["action_id"]
    barrier = threading.Barrier(2)

    def _approve_once() -> tuple[int, dict]:
        local_client = TestClient(app)
        barrier.wait(timeout=10)
        resp = local_client.post(
            f"/api/ai/actions/{action_id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )
        return resp.status_code, resp.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut1 = pool.submit(_approve_once)
        fut2 = pool.submit(_approve_once)
        (c1, b1), (c2, b2) = fut1.result(timeout=30), fut2.result(timeout=30)

    ok_codes = {c1, c2}
    assert 200 in ok_codes
    assert 422 in ok_codes

    db = SessionLocal()
    try:
        row = db.query(AiAction).filter(AiAction.action_id == action_id).one()
        assert row.status == "approved"
        assert row.approved_at is not None
    finally:
        db.close()

    _cleanup_action(action_id)


def test_parallel_execute_org_b_cannot_mutate(require_postgres, owner_lead):
    token_a, user_a, lead_a = owner_lead
    client_a = TestClient(app)
    action_id = _propose_approve(client_a, token_a, lead_a.id)

    db = SessionLocal()
    try:
        user_b = User(
            username=f"de42hc_{uuid.uuid4().hex[:8]}",
            email=f"hc_{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("testpass123"),
            role="owner",
            email_verified=True,
        )
        db.add(user_b)
        db.commit()
        db.refresh(user_b)
        token_b, _ = create_access_token(user_b.id, user_b.username, token_version=0)
        user_b_id = user_b.id
    finally:
        db.close()

    before = _activity_count(user_a.id, lead_a.id)
    result_holder: dict = {}

    def _exec_a():
        c = TestClient(app)
        result_holder["resp"] = c.post(
            f"/api/ai/actions/{action_id}/execute",
            headers={"Authorization": f"Bearer {token_a}"},
        )

    thread_a = threading.Thread(target=_exec_a, daemon=True)
    thread_a.start()

    rb = TestClient(app).post(
        f"/api/ai/actions/{action_id}/execute",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    thread_a.join(timeout=30)
    assert not thread_a.is_alive(), "Org A execute did not finish in time"
    ra = result_holder["resp"]

    assert ra.status_code == 200
    assert rb.status_code == 404
    assert _activity_count(user_a.id, lead_a.id) == before + 1

    db = SessionLocal()
    try:
        db.query(AiAction).filter(AiAction.action_id == action_id).delete()
        db.query(User).filter(User.id == user_b_id).delete()
        db.commit()
    finally:
        db.close()
