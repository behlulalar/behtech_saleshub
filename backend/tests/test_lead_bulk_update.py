"""Seçili müşterilerde öncelik, durum ve etiketlerin toplu güncellenmesi."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from auth import create_access_token
from database import BusinessEvent, Lead, LeadActivity, LeadTag, SessionLocal, TagModel, User
from main import app
from migrate_auth import run_migrations
from security import hash_password


@pytest.fixture
def client():
    return TestClient(app)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_owner() -> tuple[str, User]:
    db = SessionLocal()
    try:
        run_migrations(db)
        username = f"bulk_{uuid.uuid4().hex[:10]}"
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=hash_password("TestPass123!"),
            role="owner",
            account_type="company",
            email_verified=True,
        )
        db.add(user)
        db.flush()
        db.add(TagModel(user_id=user.id, id="sicak", label="Sıcak", color="red"))
        db.add(TagModel(user_id=user.id, id="soguk", label="Soğuk", color="blue"))
        db.commit()
        db.refresh(user)
        token, _ = create_access_token(user.id, user.username, token_version=user.token_version or 0)
        return token, user
    finally:
        db.close()


def _cleanup(org_id: int) -> None:
    db = SessionLocal()
    try:
        db.query(BusinessEvent).filter(BusinessEvent.user_id == org_id).delete(synchronize_session=False)
        db.query(LeadActivity).filter(LeadActivity.user_id == org_id).delete(synchronize_session=False)
        db.query(LeadTag).filter(LeadTag.user_id == org_id).delete(synchronize_session=False)
        db.query(Lead).filter(Lead.user_id == org_id).delete(synchronize_session=False)
        db.query(TagModel).filter(TagModel.user_id == org_id).delete(synchronize_session=False)
        db.query(User).filter(User.id == org_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def org():
    token, user = _make_owner()
    yield token, user
    _cleanup(user.id)


def _add_lead(org_id: int, tag_ids: tuple[str, ...] = (), **kwargs) -> int:
    db = SessionLocal()
    try:
        lead = Lead(
            user_id=org_id,
            category="dovme",
            isletme_adi=kwargs.get("isletme_adi", "Roof Tattoo"),
            durum=kwargs.get("durum", "Yeni"),
            oncelik=kwargs.get("oncelik", "orta"),
            demo_gonderildi=kwargs.get("demo_gonderildi", False),
        )
        db.add(lead)
        db.flush()
        for tag_id in tag_ids:
            db.add(LeadTag(user_id=org_id, lead_id=lead.id, tag_id=tag_id))
        db.commit()
        return lead.id
    finally:
        db.close()


def _lead_state(lead_id: int) -> tuple[str, str, set[str], int]:
    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).one()
        tags = {row.tag_id for row in db.query(LeadTag).filter(LeadTag.lead_id == lead_id).all()}
        status_activities = (
            db.query(LeadActivity)
            .filter(LeadActivity.lead_id == lead_id, LeadActivity.activity_type == "durum_degisti")
            .count()
        )
        return lead.oncelik, lead.durum, tags, status_activities
    finally:
        db.close()


def test_bulk_update_priority_status_and_tags(client, org):
    token, user = org
    a = _add_lead(user.id, tag_ids=("soguk",))
    b = _add_lead(user.id, durum="Takip Bekliyor", oncelik="dusuk")

    res = client.post(
        "/api/leads/bulk-update",
        json={
            "lead_ids": [a, b],
            "oncelik": "yuksek",
            "durum": "Teklif Verildi",
            "add_tag_ids": ["sicak"],
            "remove_tag_ids": ["soguk"],
        },
        headers=_auth(token),
    )
    assert res.status_code == 200, res.text
    assert res.json() == {"updated": 2}

    assert _lead_state(a) == ("yuksek", "Teklif Verildi", {"sicak"}, 1)
    assert _lead_state(b) == ("yuksek", "Teklif Verildi", {"sicak"}, 1)


def test_bulk_update_only_priority_leaves_other_fields(client, org):
    token, user = org
    a = _add_lead(user.id, durum="Müşteri", tag_ids=("soguk",))

    res = client.post(
        "/api/leads/bulk-update",
        json={"lead_ids": [a], "oncelik": "dusuk"},
        headers=_auth(token),
    )
    assert res.status_code == 200, res.text
    assert _lead_state(a) == ("dusuk", "Müşteri", {"soguk"}, 0)


def test_bulk_update_keeps_demo_automation(client, org):
    token, user = org
    a = _add_lead(user.id, durum="Demo Gönderildi", demo_gonderildi=True)

    res = client.post(
        "/api/leads/bulk-update",
        json={"lead_ids": [a], "durum": "Yeni"},
        headers=_auth(token),
    )
    assert res.status_code == 200, res.text
    assert _lead_state(a)[1] == "Demo Gönderildi"


def test_bulk_update_rejects_invalid_input(client, org):
    token, user = org
    a = _add_lead(user.id)
    other_token, other_user = _make_owner()
    try:
        cases = [
            ({"lead_ids": [a], "oncelik": "acil"}, 400),
            ({"lead_ids": [a], "durum": "Bilinmiyor"}, 400),
            ({"lead_ids": [a], "add_tag_ids": ["yok"]}, 400),
            ({"lead_ids": [a]}, 400),
            ({"lead_ids": []}, 422),
        ]
        for payload, expected in cases:
            res = client.post("/api/leads/bulk-update", json=payload, headers=_auth(token))
            assert res.status_code == expected, (payload, res.text)

        foreign = client.post(
            "/api/leads/bulk-update",
            json={"lead_ids": [a], "oncelik": "yuksek"},
            headers=_auth(other_token),
        )
        assert foreign.status_code == 404
        assert _lead_state(a)[0] == "orta"
    finally:
        _cleanup(other_user.id)
