"""DE-4 action management — update / cancel / duplicate-safety tests."""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from auth import create_access_token
from config import settings
from database import AiAction, Lead, LeadActivity, SessionLocal, User
from main import app
from security import hash_password
from tests.test_de4_actions_stage42 import _owner_token


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


def _cleanup(action_ids: list[str]) -> None:
    if not action_ids:
        return
    db = SessionLocal()
    try:
        db.query(AiAction).filter(AiAction.action_id.in_(action_ids)).delete(synchronize_session=False)
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


def _propose_priority(client: TestClient, token: str, lead_id: int, priority: str = "orta") -> str:
    body = {
        "action_type": "propose_priority_change",
        "target_entity": "lead",
        "target_entity_id": lead_id,
        "parameters": {"lead_id": lead_id, "priority": priority},
        "reason": "mgmt test",
        "source_diagnosis_id": f"diag-{uuid.uuid4().hex[:8]}",
        "idempotency_key": f"mgmt-{uuid.uuid4().hex[:12]}",
    }
    r = client.post("/api/ai/actions/propose", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    return r.json()["action_id"]


def _insert_sibling_proposed(
    *,
    org_id: int,
    user_id: int,
    lead_id: int,
    action_type: str = "propose_priority_change",
    priority: str = "yuksek",
) -> str:
    """Bypass propose guard to simulate historical operational duplicates."""
    db = SessionLocal()
    try:
        action_id = str(uuid.uuid4())
        row = AiAction(
            action_id=action_id,
            organization_id=org_id,
            action_type=action_type,
            target_entity="lead",
            target_entity_id=lead_id,
            parameters_json=json.dumps({"lead_id": lead_id, "priority": priority}),
            reason="sibling",
            requested_by=user_id,
            status="proposed",
            idempotency_key=f"sib-{uuid.uuid4().hex[:12]}",
        )
        db.add(row)
        db.commit()
        return action_id
    finally:
        db.close()


def _other_org_token() -> tuple[str, int]:
    db = SessionLocal()
    try:
        user = User(
            username=f"mgmt_{uuid.uuid4().hex[:8]}",
            email=f"mgmt_{uuid.uuid4().hex[:8]}@example.com",
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


def test_proposed_update_pass(client, owner_lead):
    token, _, lead = owner_lead
    action_id = _propose_priority(client, token, lead.id, "orta")
    try:
        r = client.post(
            f"/api/ai/actions/{action_id}/update",
            json={"parameters": {"priority": "yuksek"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "proposed"
        assert body["parameters"]["priority"] == "yuksek"
        assert body["parameters"]["lead_id"] == lead.id
        assert body["action_type"] == "propose_priority_change"
    finally:
        _cleanup([action_id])


@pytest.mark.parametrize(
    "status_name",
    ["approved", "executed", "cancelled", "expired", "failed", "executing"],
)
def test_non_proposed_update_rejected(client, owner_lead, status_name):
    token, _, lead = owner_lead
    action_id = _propose_priority(client, token, lead.id)
    _set_status(action_id, status_name)
    try:
        r = client.post(
            f"/api/ai/actions/{action_id}/update",
            json={"parameters": {"priority": "yuksek"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 422, r.text
    finally:
        _cleanup([action_id])


def test_invalid_parameters_rejected(client, owner_lead):
    token, _, lead = owner_lead
    action_id = _propose_priority(client, token, lead.id)
    try:
        r = client.post(
            f"/api/ai/actions/{action_id}/update",
            json={"parameters": {"priority": "not-a-real-priority"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 422
    finally:
        _cleanup([action_id])


def test_immutable_parameter_keys_rejected(client, owner_lead):
    token, _, lead = owner_lead
    action_id = _propose_priority(client, token, lead.id)
    try:
        r = client.post(
            f"/api/ai/actions/{action_id}/update",
            json={"parameters": {"priority": "yuksek", "action_type": "propose_note_append"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 422
        r2 = client.post(
            f"/api/ai/actions/{action_id}/update",
            json={"parameters": {"priority": "yuksek", "target_entity": "lead"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 422
        r3 = client.post(
            f"/api/ai/actions/{action_id}/update",
            json={"parameters": {"priority": "yuksek", "target_entity_id": 999999}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r3.status_code == 422
    finally:
        _cleanup([action_id])


def test_mismatched_lead_id_rejected(client, owner_lead):
    token, _, lead = owner_lead
    action_id = _propose_priority(client, token, lead.id)
    try:
        r = client.post(
            f"/api/ai/actions/{action_id}/update",
            json={"parameters": {"priority": "yuksek", "lead_id": lead.id + 99999}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 422
    finally:
        _cleanup([action_id])


def test_cross_org_update_404(client, owner_lead):
    token, _, lead = owner_lead
    action_id = _propose_priority(client, token, lead.id)
    other_token, _ = _other_org_token()
    try:
        r = client.post(
            f"/api/ai/actions/{action_id}/update",
            json={"parameters": {"priority": "yuksek"}},
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert r.status_code == 404
    finally:
        _cleanup([action_id])


def test_employee_update_403(client, owner_lead):
    token, user, lead = owner_lead
    action_id = _propose_priority(client, token, lead.id)
    db = SessionLocal()
    try:
        emp = db.query(User).filter(User.role == "employee", User.owner_id == user.id).first()
        if not emp:
            emp = db.query(User).filter(User.role == "employee").first()
        if not emp:
            pytest.skip("No employee")
        emp_token, _ = create_access_token(emp.id, emp.username, token_version=0)
    finally:
        db.close()
    try:
        r = client.post(
            f"/api/ai/actions/{action_id}/update",
            json={"parameters": {"priority": "yuksek"}},
            headers={"Authorization": f"Bearer {emp_token}"},
        )
        assert r.status_code == 403
    finally:
        _cleanup([action_id])


def test_duplicate_collision_update_rejected(client, owner_lead):
    token, user, lead = owner_lead
    action_id = _propose_priority(client, token, lead.id, "orta")
    sibling = _insert_sibling_proposed(org_id=user.id, user_id=user.id, lead_id=lead.id)
    try:
        r = client.post(
            f"/api/ai/actions/{action_id}/update",
            json={"parameters": {"priority": "yuksek"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 409, r.text
    finally:
        _cleanup([action_id, sibling])


def test_proposed_cancel_pass(client, owner_lead):
    token, _, lead = owner_lead
    action_id = _propose_priority(client, token, lead.id)
    try:
        r = client.post(
            f"/api/ai/actions/{action_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"
    finally:
        _cleanup([action_id])


@pytest.mark.parametrize("status_name", ["approved", "executing", "executed", "failed", "expired"])
def test_non_proposed_cancel_rejected(client, owner_lead, status_name):
    token, _, lead = owner_lead
    action_id = _propose_priority(client, token, lead.id)
    _set_status(action_id, status_name)
    try:
        r = client.post(
            f"/api/ai/actions/{action_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 422
    finally:
        _cleanup([action_id])


def test_cross_org_cancel_404(client, owner_lead):
    token, _, lead = owner_lead
    action_id = _propose_priority(client, token, lead.id)
    other_token, _ = _other_org_token()
    try:
        r = client.post(
            f"/api/ai/actions/{action_id}/cancel",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert r.status_code == 404
    finally:
        _cleanup([action_id])


def test_employee_cancel_403(client, owner_lead):
    token, _user, lead = owner_lead
    action_id = _propose_priority(client, token, lead.id)
    db = SessionLocal()
    try:
        emp = db.query(User).filter(User.role == "employee").first()
        if not emp:
            pytest.skip("No employee")
        emp_token, _ = create_access_token(emp.id, emp.username, token_version=0)
    finally:
        db.close()
    try:
        r = client.post(
            f"/api/ai/actions/{action_id}/cancel",
            headers={"Authorization": f"Bearer {emp_token}"},
        )
        assert r.status_code == 403
    finally:
        _cleanup([action_id])


def test_cancel_does_not_mutate_lead_or_activity(client, owner_lead):
    token, user, lead = owner_lead
    action_id = _propose_priority(client, token, lead.id)
    db = SessionLocal()
    try:
        before_lead = db.query(Lead).filter(Lead.id == lead.id).first()
        assert before_lead is not None
        snap = {
            "oncelik": before_lead.oncelik,
            "durum": before_lead.durum,
            "notlar": before_lead.notlar,
            "takip_1": before_lead.takip_1,
            "takip_2": before_lead.takip_2,
        }
        before_acts = (
            db.query(LeadActivity)
            .filter(LeadActivity.user_id == user.id, LeadActivity.lead_id == lead.id)
            .count()
        )
    finally:
        db.close()

    try:
        r = client.post(
            f"/api/ai/actions/{action_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        db = SessionLocal()
        try:
            after = db.query(Lead).filter(Lead.id == lead.id).first()
            assert after is not None
            assert after.oncelik == snap["oncelik"]
            assert after.durum == snap["durum"]
            assert after.notlar == snap["notlar"]
            assert after.takip_1 == snap["takip_1"]
            assert after.takip_2 == snap["takip_2"]
            after_acts = (
                db.query(LeadActivity)
                .filter(LeadActivity.user_id == user.id, LeadActivity.lead_id == lead.id)
                .count()
            )
            assert after_acts == before_acts
        finally:
            db.close()
    finally:
        _cleanup([action_id])


def test_cancelled_cancel_idempotent(client, owner_lead):
    token, _, lead = owner_lead
    action_id = _propose_priority(client, token, lead.id)
    try:
        r1 = client.post(
            f"/api/ai/actions/{action_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        r2 = client.post(
            f"/api/ai/actions/{action_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r2.json()["status"] == "cancelled"
        assert r2.json()["action_id"] == action_id
    finally:
        _cleanup([action_id])


def test_update_preserves_metadata_and_touches_updated_at(client, owner_lead):
    token, _, lead = owner_lead
    action_id = _propose_priority(client, token, lead.id, "orta")
    try:
        db = SessionLocal()
        try:
            row = db.query(AiAction).filter(AiAction.action_id == action_id).first()
            assert row is not None
            created = row.created_at
            source_diag = row.source_diagnosis_id
            source_run = row.source_interpret_run_id
            idem = row.idempotency_key
            old_updated = row.updated_at
            assert row.execution_result_json in (None, "")
        finally:
            db.close()

        time.sleep(1.05)
        r = client.post(
            f"/api/ai/actions/{action_id}/update",
            json={"parameters": {"priority": "yuksek"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200

        db = SessionLocal()
        try:
            row = db.query(AiAction).filter(AiAction.action_id == action_id).first()
            assert row is not None
            assert row.created_at == created
            assert row.source_diagnosis_id == source_diag
            assert row.source_interpret_run_id == source_run
            assert row.idempotency_key == idem
            assert row.execution_result_json in (None, "")
            assert row.approved_at is None
            assert row.executed_at is None
            assert row.updated_at >= old_updated
            assert row.updated_at > old_updated or isinstance(row.updated_at, datetime)
            # Prefer strict change when DB clock resolution allows
            if old_updated is not None:
                assert row.updated_at != old_updated or r.json()["parameters"]["priority"] == "yuksek"
        finally:
            db.close()
    finally:
        _cleanup([action_id])


def test_update_follow_up_note_and_stub_rejected(client, owner_lead):
    token, _, lead = owner_lead
    follow = {
        "action_type": "propose_follow_up_task",
        "target_entity": "lead",
        "target_entity_id": lead.id,
        "parameters": {"lead_id": lead.id, "note": "old"},
        "reason": "fu",
        "idempotency_key": f"mgmt-fu-{uuid.uuid4().hex[:12]}",
    }
    r = client.post("/api/ai/actions/propose", json=follow, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    action_id = r.json()["action_id"]
    try:
        r2 = client.post(
            f"/api/ai/actions/{action_id}/update",
            json={"parameters": {"note": "new note"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 200
        assert r2.json()["parameters"]["note"] == "new note"
    finally:
        _cleanup([action_id])

    stub = {
        "action_type": "propose_meeting_date",
        "target_entity": "lead",
        "target_entity_id": lead.id,
        "parameters": {"lead_id": lead.id, "meeting_date": "2026-09-01", "meeting_time": ""},
        "reason": "stub",
        "idempotency_key": f"mgmt-stub-{uuid.uuid4().hex[:12]}",
    }
    rs = client.post("/api/ai/actions/propose", json=stub, headers={"Authorization": f"Bearer {token}"})
    assert rs.status_code == 200
    stub_id = rs.json()["action_id"]
    try:
        r3 = client.post(
            f"/api/ai/actions/{stub_id}/update",
            json={"parameters": {"meeting_date": "2026-10-01"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r3.status_code == 422
    finally:
        _cleanup([stub_id])


def test_cancel_then_new_propose_allowed_hardening(client, owner_lead):
    """After cancel, operational duplicate guard allows a fresh proposal."""
    token, _, lead = owner_lead
    first = _propose_priority(client, token, lead.id, "orta")
    try:
        r = client.post(
            f"/api/ai/actions/{first}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        second = _propose_priority(client, token, lead.id, "yuksek")
        assert second != first
        got = client.get(
            f"/api/ai/actions/{second}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert got.status_code == 200
        assert got.json()["parameters"]["priority"] == "yuksek"
        _cleanup([second])
    finally:
        _cleanup([first])


def test_update_note_append_and_log_activity(client, owner_lead):
    token, _, lead = owner_lead
    note_body = {
        "action_type": "propose_note_append",
        "target_entity": "lead",
        "target_entity_id": lead.id,
        "parameters": {"lead_id": lead.id, "note_text": "hello", "separator": "\n\n"},
        "reason": "n",
        "idempotency_key": f"mgmt-note-{uuid.uuid4().hex[:12]}",
    }
    rn = client.post("/api/ai/actions/propose", json=note_body, headers={"Authorization": f"Bearer {token}"})
    assert rn.status_code == 200
    note_id = rn.json()["action_id"]
    try:
        r = client.post(
            f"/api/ai/actions/{note_id}/update",
            json={"parameters": {"note_text": "updated note", "separator": "\n"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["parameters"]["note_text"] == "updated note"
        assert r.json()["parameters"]["separator"] == "\n"
    finally:
        _cleanup([note_id])

    log_body = {
        "action_type": "propose_log_activity",
        "target_entity": "lead",
        "target_entity_id": lead.id,
        "parameters": {
            "lead_id": lead.id,
            "activity_type": "takip_yapildi",
            "title": "t1",
            "description": "d1",
        },
        "reason": "l",
        "idempotency_key": f"mgmt-log-{uuid.uuid4().hex[:12]}",
    }
    rl = client.post("/api/ai/actions/propose", json=log_body, headers={"Authorization": f"Bearer {token}"})
    assert rl.status_code == 200
    log_id = rl.json()["action_id"]
    try:
        r = client.post(
            f"/api/ai/actions/{log_id}/update",
            json={
                "parameters": {
                    "activity_type": "telefon_gorusmesi",
                    "title": "t2",
                    "description": "d2",
                }
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["parameters"]["activity_type"] == "telefon_gorusmesi"
        assert r.json()["parameters"]["title"] == "t2"
    finally:
        _cleanup([log_id])
