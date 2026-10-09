"""Personel lead araması: ortak kota, talep olarak gönderme ve onayda Google bilgilerinin taşınması."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

import lead_discovery
from auth import create_access_token
from config import settings
from database import (
    ApiUsageLog,
    CategoryModel,
    Lead,
    LeadActivity,
    LeadDiscoveryScan,
    LeadRequest,
    SessionLocal,
    User,
)
from main import app
from migrate_auth import run_migrations
from security import hash_password

PLACES = [
    {
        "google_place_id": "place-a",
        "business_name": "Mavi Kuaför",
        "phone_number": "0532 111 22 33",
        "address": "Merkez",
        "rating": 4.5,
        "rating_count": 3,
        "latitude": 40.7,
        "longitude": 30.4,
    },
    {
        "google_place_id": "place-b",
        "business_name": "Kırmızı Kuaför",
        "phone_number": "",
        "address": "Merkez",
        "rating": None,
        "rating_count": None,
        "latitude": None,
        "longitude": None,
    },
]


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def fake_places(monkeypatch):
    monkeypatch.setattr(settings, "google_places_api_key", "test-key")
    monkeypatch.setattr(lead_discovery, "resolve_city_coords", lambda *a, **k: (40.7, 30.4))
    monkeypatch.setattr(lead_discovery, "search_text", lambda *a, **k: ([dict(p) for p in PLACES], None))


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _token(user: User) -> str:
    token, _ = create_access_token(user.id, user.username, token_version=user.token_version or 0)
    return token


@pytest.fixture
def org():
    db = SessionLocal()
    try:
        run_migrations(db)
        suffix = uuid.uuid4().hex[:10]
        owner = User(
            username=f"disc_{suffix}",
            email=f"disc_{suffix}@example.com",
            password_hash=hash_password("TestPass123!"),
            role="owner",
            account_type="company",
            email_verified=True,
        )
        db.add(owner)
        db.flush()
        employee = User(
            username=f"disc_emp_{suffix}",
            email=f"disc_emp_{suffix}@example.com",
            password_hash=hash_password("TestPass123!"),
            role="employee",
            owner_id=owner.id,
            account_type="company",
            email_verified=True,
        )
        db.add(employee)
        db.add(CategoryModel(user_id=owner.id, id="kuafor", label="Kuaför"))
        db.commit()
        db.refresh(owner)
        db.refresh(employee)
        yield owner, employee
    finally:
        org_ids = [owner.id]
        db.query(LeadRequest).filter(LeadRequest.owner_id.in_(org_ids)).delete(synchronize_session=False)
        db.query(LeadActivity).filter(LeadActivity.user_id.in_(org_ids)).delete(synchronize_session=False)
        db.query(Lead).filter(Lead.user_id.in_(org_ids)).delete(synchronize_session=False)
        db.query(ApiUsageLog).filter(ApiUsageLog.user_id.in_(org_ids)).delete(synchronize_session=False)
        db.query(LeadDiscoveryScan).filter(LeadDiscoveryScan.user_id.in_(org_ids)).delete(synchronize_session=False)
        db.query(CategoryModel).filter(CategoryModel.user_id.in_(org_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.owner_id == owner.id).delete(synchronize_session=False)
        db.query(User).filter(User.id == owner.id).delete(synchronize_session=False)
        db.commit()
        db.close()


def _discover(client, token: str, **extra):
    return client.post(
        "/api/leads/discover",
        json={"city": "Sakarya", "sector_keyword": "kuaför", "category": "kuafor", "radius_meters": 1000, **extra},
        headers=_auth(token),
    )


def test_employee_can_search_and_usage_is_shared_with_owner(client, org):
    owner, employee = org
    usage = client.get("/api/leads/discover/usage", headers=_auth(_token(employee)))
    assert usage.status_code == 200, usage.text

    res = _discover(client, _token(employee))
    assert res.status_code == 200, res.text
    body = res.json()
    assert {item["google_place_id"] for item in body["results"]} == {"place-a", "place-b"}
    assert body["usage"]["used"] >= 1

    owner_usage = client.get("/api/leads/discover/usage", headers=_auth(_token(owner))).json()
    assert owner_usage["used"] == body["usage"]["used"]


def test_employee_cannot_run_paid_queries_over_quota(client, org):
    owner, employee = org
    db = SessionLocal()
    try:
        db.add(
            ApiUsageLog(
                user_id=owner.id,
                month=lead_discovery.current_month(),
                sku_type=lead_discovery.SKU_TYPE,
                query_count=settings.places_free_quota_monthly,
            )
        )
        db.commit()
    finally:
        db.close()

    res = _discover(client, _token(employee), confirm_over_quota=True)
    assert res.status_code == 403
    assert "kota" in res.json()["detail"]

    owner_res = _discover(client, _token(owner))
    assert owner_res.status_code == 402


def test_employee_selection_becomes_pending_requests_and_approval_keeps_google_data(client, org):
    owner, employee = org
    emp_token = _token(employee)
    payload = {
        "category": "kuafor",
        "city": "Sakarya",
        "places": [{**PLACES[0], "low_digital_presence": True}, PLACES[1]],
    }

    forbidden = client.post("/api/leads/discover/import", json=payload, headers=_auth(emp_token))
    assert forbidden.status_code == 403

    res = client.post("/api/leads/discover/request", json=payload, headers=_auth(emp_token))
    assert res.status_code == 200, res.text
    assert res.json() == {"created": 2, "skipped": 0}

    again = client.post("/api/leads/discover/request", json=payload, headers=_auth(emp_token))
    assert again.json() == {"created": 0, "skipped": 2}

    # Bekleyen talepler arama sonuçlarında işaretlenir.
    results = _discover(client, emp_token, district="Adapazarı").json()["results"]
    assert all(item["already_requested"] for item in results)

    owner_token = _token(owner)
    requests = client.get("/api/lead-requests?status=pending", headers=_auth(owner_token)).json()
    by_name = {item["isletme_adi"]: item for item in requests}
    mavi = by_name["Mavi Kuaför"]
    assert mavi["oncelik"] == "yuksek"
    assert mavi["ilk_iletisim_kanali"] == "Google Places"

    approved = client.post(f"/api/lead-requests/{mavi['id']}/approve", headers=_auth(owner_token))
    assert approved.status_code == 200, approved.text

    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.id == approved.json()["id"]).one()
        assert lead.google_place_id == "place-a"
        assert lead.source == "google_places"
        assert float(lead.google_rating) == 4.5
    finally:
        db.close()

    # Aynı işletme için ikinci talep onaylanamaz (mükerrer kayıt yok).
    db = SessionLocal()
    try:
        dup = LeadRequest(
            owner_id=owner.id,
            requested_by=employee.id,
            category="kuafor",
            status="pending",
            isletme_adi="Mavi Kuaför",
            google_place_id="place-a",
        )
        db.add(dup)
        db.commit()
        dup_id = dup.id
    finally:
        db.close()
    dup_res = client.post(f"/api/lead-requests/{dup_id}/approve", headers=_auth(owner_token))
    assert dup_res.status_code == 409


def test_owner_cannot_use_request_endpoint(client, org):
    owner, _ = org
    res = client.post(
        "/api/leads/discover/request",
        json={"category": "kuafor", "city": "Sakarya", "places": [PLACES[0]]},
        headers=_auth(_token(owner)),
    )
    assert res.status_code == 403
