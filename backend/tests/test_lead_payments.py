"""Alınan miktar (ödeme) tekliften ayrı tutulur ve gelir istatistiklerine yazılır."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from auth import create_access_token
from database import Lead, LeadActivity, SessionLocal, User
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
        username = f"pay_{uuid.uuid4().hex[:10]}"
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=hash_password("TestPass123!"),
            role="owner",
            account_type="company",
            email_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token, _ = create_access_token(user.id, user.username, token_version=user.token_version or 0)
        return token, user
    finally:
        db.close()


def _cleanup(org_id: int) -> None:
    db = SessionLocal()
    try:
        db.query(LeadActivity).filter(LeadActivity.user_id == org_id).delete(synchronize_session=False)
        db.query(Lead).filter(Lead.user_id == org_id).delete(synchronize_session=False)
        db.query(User).filter(User.id == org_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def org():
    token, user = _make_owner()
    yield token, user
    _cleanup(user.id)


def _add_lead(org_id: int, **kwargs) -> Lead:
    db = SessionLocal()
    try:
        lead = Lead(
            user_id=org_id,
            category=kwargs.get("category", "dovme"),
            isletme_adi=kwargs.get("isletme_adi", "Roof Tattoo"),
            durum=kwargs.get("durum", "Teklif Verildi"),
            teklif=kwargs.get("teklif", "8500 TL"),
            satis_tutari=kwargs.get("satis_tutari", 0),
            satis_tarihi=kwargs.get("satis_tarihi", ""),
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        return lead
    finally:
        db.close()


def test_deposit_appears_in_revenue_without_musteri_status(client, org):
    token, user = org
    lead = _add_lead(user.id, teklif="8500 TL", durum="Teklif Verildi")

    res = client.post(
        f"/api/leads/{lead.id}/payments",
        json={"amount": 4500},
        headers=_auth(token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["teklif"] == "8500 TL"
    assert body["durum"] == "Teklif Verildi"
    assert float(body["satis_tutari"]) == 4500
    assert body["satis_tarihi"] == date.today().isoformat()

    revenue = client.get("/api/revenue", headers=_auth(token))
    assert revenue.status_code == 200
    data = revenue.json()
    assert data["toplam_gelir"] == 4500
    assert data["satis_sayisi"] == 1
    assert data["bu_ay_gelir"] == 4500
    assert any(item["id"] == lead.id and item["satis_tutari"] == 4500 for item in data["son_satislar"])


def test_second_payment_is_counted_in_the_month_it_was_recorded(client, org):
    token, user = org
    lead = _add_lead(user.id, teklif="8500 TL", satis_tutari=4500, satis_tarihi="2025-08-01")

    res = client.post(
        f"/api/leads/{lead.id}/payments",
        json={"amount": 2000},
        headers=_auth(token),
    )
    assert res.status_code == 200
    assert float(res.json()["satis_tutari"]) == 6500
    assert res.json()["satis_tarihi"] == "2025-08-01"

    today = date.today()
    all_time = client.get("/api/revenue", headers=_auth(token)).json()
    assert all_time["tum_zamanlar_gelir"] == 6500

    august = client.get("/api/revenue?year=2025&month=8", headers=_auth(token)).json()
    assert august["toplam_gelir"] == 4500

    this_month = client.get(
        f"/api/revenue?year={today.year}&month={today.month}",
        headers=_auth(token),
    ).json()
    assert this_month["toplam_gelir"] == 2000
    assert any(
        item["id"] == lead.id and item["satis_tutari"] == 2000 and item["satis_tarihi"] == today.isoformat()
        for item in this_month["son_satislar"]
    )


def test_payment_on_old_offer_appears_in_entry_month_not_offer_month(client, org):
    token, user = org
    lead = _add_lead(user.id, teklif="8500 TL", durum="Teklif Verildi", satis_tarihi="2025-08-09")

    res = client.post(
        f"/api/leads/{lead.id}/payments",
        json={"amount": 4500},
        headers=_auth(token),
    )
    assert res.status_code == 200
    today = date.today()
    assert res.json()["satis_tarihi"] == "2025-08-09"

    august = client.get("/api/revenue?year=2025&month=8", headers=_auth(token)).json()
    assert august["toplam_gelir"] == 0

    this_month = client.get(
        f"/api/revenue?year={today.year}&month={today.month}",
        headers=_auth(token),
    ).json()
    assert this_month["toplam_gelir"] == 4500
    assert this_month["bu_ay_gelir"] == 4500


def test_invalid_payment_rejected(client, org):
    token, user = org
    lead = _add_lead(user.id)
    res = client.post(
        f"/api/leads/{lead.id}/payments",
        json={"amount": 0},
        headers=_auth(token),
    )
    assert res.status_code == 422


def test_payment_schema_rejects_zero_and_accepts_deposit():
    from pydantic import ValidationError
    from schemas import LeadPaymentCreate

    with pytest.raises(ValidationError):
        LeadPaymentCreate(amount=0)
    payload = LeadPaymentCreate(amount=4500)
    assert payload.amount == 4500


def test_automation_sets_payment_date_without_musteri_status():
    from lead_automation import apply_lead_automation

    out = apply_lead_automation({"isletme_adi": "Roof", "durum": "Teklif Verildi", "satis_tutari": 4500})
    assert out["satis_tarihi"] == date.today().isoformat()
    assert out["durum"] == "Teklif Verildi"
