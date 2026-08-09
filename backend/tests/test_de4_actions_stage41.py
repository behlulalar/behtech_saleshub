"""DE-4 Stage 4.1 — propose persist, API, org isolation."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from auth import create_access_token
from config import settings
from database import AiAction, Lead, SessionLocal, User
from main import app
from security import hash_password


@pytest.fixture
def client():
    return TestClient(app)


def _owner_token(db) -> tuple[str, User]:
    user = db.query(User).filter(User.role == "owner").first()
    if not user:
        pytest.skip("No owner user")
    token, _ = create_access_token(user.id, user.username, token_version=user.token_version or 0)
    return token, user


def _valid_log_activity_payload(lead_id: int) -> dict:
    return {
        "action_type": "propose_log_activity",
        "target_entity": "lead",
        "target_entity_id": lead_id,
        "parameters": {
            "lead_id": lead_id,
            "activity_type": "takip_yapildi",
            "title": "Test aktivite",
            "description": "DE-4 test",
        },
        "reason": "Test nedeni",
        "idempotency_key": f"test-key-{uuid.uuid4().hex[:16]}",
    }


@pytest.fixture
def owner_lead():
    db = SessionLocal()
    try:
        token, user = _owner_token(db)
        lead = db.query(Lead).filter(Lead.user_id == user.id).first()
        if not lead:
            pytest.skip("No lead for owner")
        yield token, user, lead
    finally:
        db.close()


@pytest.fixture(autouse=True)
def ai_on():
    prev = settings.ai_enabled
    settings.ai_enabled = True
    try:
        yield
    finally:
        settings.ai_enabled = prev


def test_propose_unauthenticated(client, owner_lead):
    token, _user, lead = owner_lead
    body = _valid_log_activity_payload(lead.id)
    del body["idempotency_key"]
    r = client.post("/api/ai/actions/propose", json=body)
    assert r.status_code == 401


def test_propose_creates_proposed_status(client, owner_lead):
    token, user, lead = owner_lead
    body = _valid_log_activity_payload(lead.id)
    r = client.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "proposed"
    assert data["action_type"] == "propose_log_activity"
    assert data["requires_confirmation"] is True
    assert data["target_entity_id"] == lead.id

    db = SessionLocal()
    try:
        row = db.query(AiAction).filter(AiAction.action_id == data["action_id"]).first()
        assert row is not None
        assert row.organization_id == user.id
        assert row.requested_by == user.id
        assert row.status == "proposed"
        db.delete(row)
        db.commit()
    finally:
        db.close()


def test_propose_persists_source_fields(client, owner_lead):
    token, _user, lead = owner_lead
    body = _valid_log_activity_payload(lead.id)
    body["source_diagnosis_id"] = "follow_up_idle_leads"
    r = client.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["source_diagnosis_id"] == "follow_up_idle_leads"

    db = SessionLocal()
    try:
        row = db.query(AiAction).filter(AiAction.action_id == data["action_id"]).first()
        db.delete(row)
        db.commit()
    finally:
        db.close()


def test_propose_unknown_action_type(client, owner_lead):
    token, _user, lead = owner_lead
    body = _valid_log_activity_payload(lead.id)
    body["action_type"] = "not_registered_xyz"
    r = client.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


def test_propose_blocked_action(client, owner_lead):
    token, _user, lead = owner_lead
    body = _valid_log_activity_payload(lead.id)
    body["action_type"] = "send_whatsapp_message"
    body["parameters"] = {"lead_id": lead.id}
    r = client.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


def test_propose_invalid_params(client, owner_lead):
    token, _user, lead = owner_lead
    body = _valid_log_activity_payload(lead.id)
    body["parameters"]["activity_type"] = "invalid_enum_xyz"
    r = client.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


def test_propose_missing_required_params(client, owner_lead):
    token, _user, lead = owner_lead
    body = _valid_log_activity_payload(lead.id)
    body["parameters"] = {"lead_id": lead.id}
    r = client.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


def test_propose_target_not_in_org(client, owner_lead):
    token, _user, lead = owner_lead
    db = SessionLocal()
    other_id = None
    foreign_id = None
    try:
        other = User(
            username=f"de4_other_{uuid.uuid4().hex[:8]}",
            email=f"de4_{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("testpass123"),
            role="owner",
            email_verified=True,
        )
        db.add(other)
        db.flush()
        other_id = other.id
        other_lead = Lead(user_id=other.id, isletme_adi="Other Lead", durum="Yeni", category="genel")
        db.add(other_lead)
        db.commit()
        db.refresh(other_lead)
        foreign_id = other_lead.id
    finally:
        db.close()

    body = _valid_log_activity_payload(foreign_id)
    r = client.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404

    db = SessionLocal()
    try:
        if foreign_id:
            db.query(Lead).filter(Lead.id == foreign_id).delete()
        if other_id:
            db.query(User).filter(User.id == other_id).delete()
        db.commit()
    finally:
        db.close()


def test_idempotency_same_org(client, owner_lead):
    token, _user, lead = owner_lead
    key = f"idem-{uuid.uuid4().hex[:12]}"
    body = _valid_log_activity_payload(lead.id)
    body["idempotency_key"] = key
    r1 = client.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    r2 = client.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["action_id"] == r2.json()["action_id"]

    db = SessionLocal()
    try:
        count = db.query(AiAction).filter(AiAction.idempotency_key == key).count()
        assert count == 1
        db.query(AiAction).filter(AiAction.idempotency_key == key).delete()
        db.commit()
    finally:
        db.close()


def test_idempotency_different_org_same_key(client, owner_lead):
    token_a, user_a, lead_a = owner_lead
    key = f"shared-{uuid.uuid4().hex[:10]}"

    db = SessionLocal()
    try:
        user_b = User(
            username=f"de4_b_{uuid.uuid4().hex[:8]}",
            email=f"b_{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("testpass123"),
            role="owner",
            email_verified=True,
        )
        db.add(user_b)
        db.flush()
        lead_b = Lead(user_id=user_b.id, isletme_adi="B Lead", durum="Yeni", category="genel")
        db.add(lead_b)
        db.commit()
        db.refresh(user_b)
        db.refresh(lead_b)
        token_b, _ = create_access_token(user_b.id, user_b.username, token_version=0)
    finally:
        db.close()

    body_a = _valid_log_activity_payload(lead_a.id)
    body_a["idempotency_key"] = key
    body_b = _valid_log_activity_payload(lead_b.id)
    body_b["idempotency_key"] = key

    r_a = client.post(
        "/api/ai/actions/propose",
        json=body_a,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    r_b = client.post(
        "/api/ai/actions/propose",
        json=body_b,
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r_a.status_code == 200
    assert r_b.status_code == 200
    assert r_a.json()["action_id"] != r_b.json()["action_id"]

    db = SessionLocal()
    try:
        db.query(AiAction).filter(AiAction.idempotency_key == key).delete()
        db.query(Lead).filter(Lead.user_id == user_b.id).delete()
        db.query(User).filter(User.id == user_b.id).delete()
        db.commit()
    finally:
        db.close()


def test_get_action_other_org_forbidden(client, owner_lead):
    token_a, user_a, lead_a = owner_lead
    body = _valid_log_activity_payload(lead_a.id)
    r = client.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    action_id = r.json()["action_id"]

    db = SessionLocal()
    try:
        user_b = User(
            username=f"de4_c_{uuid.uuid4().hex[:8]}",
            email=f"c_{uuid.uuid4().hex[:8]}@example.com",
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

    r_get = client.get(
        f"/api/ai/actions/{action_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r_get.status_code == 404

    db = SessionLocal()
    try:
        db.query(AiAction).filter(AiAction.action_id == action_id).delete()
        db.query(User).filter(User.id == user_b.id).delete()
        db.commit()
    finally:
        db.close()


def test_security_ignores_client_org_and_status(client, owner_lead):
    token, user, lead = owner_lead
    body = _valid_log_activity_payload(lead.id)
    body["organization_id"] = 999999
    body["requested_by"] = 999999
    body["status"] = "executed"
    r = client.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "proposed"

    db = SessionLocal()
    try:
        row = db.query(AiAction).filter(AiAction.action_id == r.json()["action_id"]).first()
        assert row.organization_id == user.id
        assert row.requested_by == user.id
        assert row.status == "proposed"
        db.delete(row)
        db.commit()
    finally:
        db.close()


def test_mapper_propose_from_recommendation(client, owner_lead):
    token, _user, lead = owner_lead
    r = client.post(
        "/api/ai/actions/propose-from-recommendation",
        json={
            "title": "WhatsApp ile takip",
            "reason": "Müşteriye kısa mesaj yaz",
            "lead_id": lead.id,
            "source_diagnosis_id": "follow_up_idle_leads",
            "idempotency_key": f"map-{uuid.uuid4().hex[:12]}",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["action_type"] == "open_whatsapp_draft"

    db = SessionLocal()
    try:
        row = db.query(AiAction).filter(AiAction.action_id == r.json()["action_id"]).first()
        db.delete(row)
        db.commit()
    finally:
        db.close()


def test_mapper_no_action(client, owner_lead):
    token, _user, lead = owner_lead
    r = client.post(
        "/api/ai/actions/propose-from-recommendation",
        json={
            "title": "Belirsiz öneri",
            "reason": "Rastgele metin 12345",
            "lead_id": lead.id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


def test_list_actions(client, owner_lead):
    token, _user, lead = owner_lead
    body = _valid_log_activity_payload(lead.id)
    client.post(
        "/api/ai/actions/propose",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    listed = client.get(
        "/api/ai/actions?status_filter=proposed",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.status_code == 200
    assert any(i["action_type"] == "propose_log_activity" for i in listed.json()["items"])

    db = SessionLocal()
    try:
        db.query(AiAction).filter(AiAction.idempotency_key == body["idempotency_key"]).delete()
        db.commit()
    finally:
        db.close()
