"""DE-1 — Diagnosis Engine (deterministic, read-only)."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from config import settings
from database import Lead
from intelligence.diagnosis.evidence import comparison_period_bounds, funnel_transition_rate
from intelligence.diagnosis.rules import detect_follow_up_problems, detect_funnel_drops, detect_offer_problems
from main import app


def _lead(
    lead_id: int,
    durum: str,
    *,
    created: date,
    ilk_mesaj: str = "",
    demo_tarihi: str = "",
    gorusme_tarihi: str = "",
    demo_gonderildi: bool = False,
    teklif: str = "",
) -> Lead:
    row = MagicMock(spec=Lead)
    row.id = lead_id
    row.durum = durum
    row.created_at = datetime.combine(created, datetime.min.time())
    row.ilk_mesaj_tarihi = ilk_mesaj
    row.demo_tarihi = demo_tarihi
    row.gorusme_tarihi = gorusme_tarihi
    row.demo_gonderildi = demo_gonderildi
    row.teklif = teklif
    row.yetkili = ""
    row.ilk_iletisim_kanali = ""
    return row


# --- funnel ---


def test_funnel_normal_conversion_no_diagnosis():
    anchor = date(2026, 8, 15)
    cur_start, _, _, _ = comparison_period_bounds("monthly", anchor)
    leads = []
    for i in range(8):
        leads.append(
            _lead(
                i + 1,
                "Müşteri" if i < 4 else "Teklif Verildi",
                created=cur_start,
                teklif="x" if i < 6 else "",
                demo_gonderildi=True,
            )
        )
    prev_leads = []
    for i in range(8):
        prev_leads.append(
            _lead(
                100 + i,
                "Müşteri" if i < 4 else "Teklif Verildi",
                created=date(2026, 7, 10),
                teklif="x",
                demo_gonderildi=True,
            )
        )
    all_leads = leads + prev_leads
    items = detect_funnel_drops(all_leads, period_type="monthly", anchor=anchor)
    assert items == []


def test_funnel_meaningful_drop_produces_diagnosis():
    anchor = date(2026, 8, 15)
    cur_start, _, prev_start, _ = comparison_period_bounds("monthly", anchor)

    def cohort(start: date, won: int, offer: int):
        rows = []
        n = 0
        for _ in range(won):
            n += 1
            rows.append(_lead(n, "Müşteri", created=start, teklif="p", demo_gonderildi=True))
        for _ in range(offer - won):
            n += 1
            rows.append(_lead(n, "Teklif Verildi", created=start, teklif="p", demo_gonderildi=True))
        return rows

    prev = cohort(prev_start, won=4, offer=8)
    cur = cohort(cur_start, won=1, offer=8)
    items = detect_funnel_drops(prev + cur, period_type="monthly", anchor=anchor)
    assert len(items) >= 1
    offer_drop = next(i for i in items if i.diagnosis_id == "funnel_offer_to_won_drop")
    assert offer_drop.type == "funnel_drop"
    assert offer_drop.previous_value == 50.0
    assert offer_drop.current_value == 12.5
    assert offer_drop.change_percent is not None and offer_drop.change_percent < 0


def test_funnel_small_sample_no_diagnosis():
    anchor = date(2026, 8, 15)
    cur_start, _, prev_start, _ = comparison_period_bounds("monthly", anchor)
    cur = [_lead(1, "Müşteri", created=cur_start, teklif="1")]
    prev = [_lead(2, "Olumsuz", created=prev_start, teklif="1")]
    assert detect_funnel_drops(cur + prev, period_type="monthly", anchor=anchor) == []


def test_funnel_improvement_no_diagnosis():
    anchor = date(2026, 8, 15)
    cur_start, _, prev_start, _ = comparison_period_bounds("monthly", anchor)

    def cohort(start: date, won: int, offer: int):
        rows = []
        for i in range(offer):
            d = "Müşteri" if i < won else "Teklif Verildi"
            rows.append(_lead(i + start.day, d, created=start, teklif="t", demo_gonderildi=True))
        return rows

    prev = cohort(prev_start, won=2, offer=8)
    cur = cohort(cur_start, won=6, offer=8)
    assert detect_funnel_drops(prev + cur, period_type="monthly", anchor=anchor) == []


def test_funnel_zero_previous_rate_safe():
    anchor = date(2026, 8, 15)
    cur_start, _, prev_start, _ = comparison_period_bounds("monthly", anchor)
    prev = [
        _lead(i, "Teklif Verildi", created=prev_start, teklif="t", demo_gonderildi=True) for i in range(6)
    ]
    cur = [
        _lead(i + 50, "Müşteri", created=cur_start, teklif="t", demo_gonderildi=True) for i in range(6)
    ]
    items = detect_funnel_drops(prev + cur, period_type="monthly", anchor=anchor)
    assert items == []


def test_funnel_transition_rate_helper():
    leads = [
        _lead(1, "Müşteri", created=date(2026, 8, 1), teklif="a", demo_gonderildi=True),
        _lead(2, "Teklif Verildi", created=date(2026, 8, 2), teklif="b", demo_gonderildi=True),
    ]
    rate, from_c, to_c = funnel_transition_rate(leads, "teklif", "satis")
    assert from_c == 2
    assert to_c == 1
    assert rate == 50.0


# --- follow-up ---


def test_follow_up_recent_activity_no_diagnosis(monkeypatch):
    db = MagicMock()
    today = date(2026, 8, 8)
    monkeypatch.setattr("intelligence.diagnosis.rules.local_today", lambda: today)
    lead = _lead(1, "Takip Bekliyor", created=date(2026, 8, 1), ilk_mesaj="2026-08-07")
    with patch("intelligence.diagnosis.rules.get_last_activity_dates", return_value={}):
        assert detect_follow_up_problems(db, 1, [lead]) == []


def test_follow_up_5_days_warning(monkeypatch):
    db = MagicMock()
    today = date(2026, 8, 10)
    monkeypatch.setattr("intelligence.diagnosis.rules.local_today", lambda: today)
    lead = _lead(1, "İletişime Geçildi", created=date(2026, 7, 1), ilk_mesaj="2026-08-04")
    with patch("intelligence.diagnosis.rules.get_last_activity_dates", return_value={}):
        items = detect_follow_up_problems(db, 10, [lead])
    assert len(items) == 1
    assert items[0].severity == "medium"
    assert items[0].type == "follow_up"


def test_follow_up_10_days_high(monkeypatch):
    db = MagicMock()
    today = date(2026, 8, 20)
    monkeypatch.setattr("intelligence.diagnosis.rules.local_today", lambda: today)
    lead = _lead(1, "Demo Gönderildi", created=date(2026, 7, 1), demo_tarihi="2026-08-05")
    with patch("intelligence.diagnosis.rules.get_last_activity_dates", return_value={}):
        items = detect_follow_up_problems(db, 10, [lead])
    assert items[0].severity == "high"


def test_follow_up_terminal_lead_excluded(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr("intelligence.diagnosis.rules.local_today", lambda: date(2026, 8, 20))
    lead = _lead(1, "Müşteri", created=date(2026, 1, 1), ilk_mesaj="2026-01-01")
    with patch("intelligence.diagnosis.rules.get_last_activity_dates", return_value={}):
        assert detect_follow_up_problems(db, 1, [lead]) == []


def test_follow_up_uses_activity_not_updated_at(monkeypatch):
    db = MagicMock()
    today = date(2026, 8, 10)
    monkeypatch.setattr("intelligence.diagnosis.rules.local_today", lambda: today)
    lead = _lead(1, "Takip Bekliyor", created=date(2026, 7, 1))
    lead.updated_at = datetime(2026, 8, 9, 12, 0, 0)
    with patch(
        "intelligence.diagnosis.rules.get_last_activity_dates",
        return_value={1: date(2026, 8, 9)},
    ):
        assert detect_follow_up_problems(db, 1, [lead]) == []


def test_follow_up_new_lead_no_contact_excluded(monkeypatch):
    db = MagicMock()
    today = date(2026, 8, 10)
    monkeypatch.setattr("intelligence.diagnosis.rules.local_today", lambda: today)
    lead = _lead(1, "Yeni", created=date(2026, 8, 9))
    lead.created_at = datetime(2026, 8, 9, 10, 0, 0)
    with patch("intelligence.diagnosis.rules.get_last_activity_dates", return_value={}):
        assert detect_follow_up_problems(db, 1, [lead]) == []


def test_follow_up_old_lead_no_contact_included(monkeypatch):
    db = MagicMock()
    today = date(2026, 8, 10)
    monkeypatch.setattr("intelligence.diagnosis.rules.local_today", lambda: today)
    lead = _lead(1, "Yeni", created=date(2026, 8, 1))
    lead.created_at = datetime(2026, 8, 1, 10, 0, 0)
    with patch("intelligence.diagnosis.rules.get_last_activity_dates", return_value={}):
        items = detect_follow_up_problems(db, 1, [lead])
    assert len(items) == 1
    assert items[0].evidence["no_contact_count"] == 1
    assert items[0].evidence["idle_contact_count"] == 0
    assert items[0].evidence["worst_case"]["reason"] == "no_contact"


def test_follow_up_idle_contact_evidence_unchanged(monkeypatch):
    db = MagicMock()
    today = date(2026, 8, 10)
    monkeypatch.setattr("intelligence.diagnosis.rules.local_today", lambda: today)
    lead = _lead(1, "İletişime Geçildi", created=date(2026, 7, 1), ilk_mesaj="2026-08-04")
    with patch("intelligence.diagnosis.rules.get_last_activity_dates", return_value={}):
        items = detect_follow_up_problems(db, 10, [lead])
    assert items[0].evidence["idle_contact_count"] == 1
    assert items[0].evidence["no_contact_count"] == 0


# --- offer ---


def test_offer_normal_pending_no_diagnosis(monkeypatch):
    db = MagicMock()
    today = date(2026, 8, 10)
    monkeypatch.setattr("intelligence.diagnosis.rules.local_today", lambda: today)
    leads = [
        _lead(1, "Teklif Verildi", created=date(2026, 8, 1)),
        _lead(2, "Teklif Verildi", created=date(2026, 8, 1)),
    ]
    with patch(
        "intelligence.diagnosis.rules.get_reliable_offer_given_dates",
        return_value={1: date(2026, 8, 8), 2: date(2026, 8, 9)},
    ):
        assert detect_offer_problems(db, 1, leads) == []


def test_offer_old_pending_diagnosis(monkeypatch):
    db = MagicMock()
    today = date(2026, 8, 20)
    monkeypatch.setattr("intelligence.diagnosis.rules.local_today", lambda: today)
    leads = [
        _lead(1, "Teklif Verildi", created=date(2026, 7, 1)),
        _lead(2, "Teklif Verildi", created=date(2026, 7, 1)),
    ]
    with patch(
        "intelligence.diagnosis.rules.get_reliable_offer_given_dates",
        return_value={1: date(2026, 8, 1), 2: date(2026, 8, 2)},
    ):
        items = detect_offer_problems(db, 1, leads)
    assert len(items) == 1
    assert items[0].type == "offer"
    assert items[0].severity in ("medium", "high")


def test_offer_age_ignores_later_contact(monkeypatch):
    db = MagicMock()
    today = date(2026, 8, 10)
    monkeypatch.setattr("intelligence.diagnosis.rules.local_today", lambda: today)
    leads = [
        _lead(1, "Teklif Verildi", created=date(2026, 7, 1), gorusme_tarihi="2026-08-07"),
        _lead(2, "Teklif Verildi", created=date(2026, 7, 1), gorusme_tarihi="2026-08-07"),
    ]
    with patch(
        "intelligence.diagnosis.rules.get_reliable_offer_given_dates",
        return_value={1: date(2026, 8, 1), 2: date(2026, 8, 1)},
    ):
        with patch(
            "intelligence.diagnosis.rules.get_last_activity_dates",
            return_value={1: date(2026, 8, 7), 2: date(2026, 8, 7)},
        ):
            items = detect_offer_problems(db, 1, leads)
    assert len(items) == 1
    assert items[0].evidence["max_offer_age_days"] == 9


def test_offer_no_reliable_date_skips_gorusme_and_contact(monkeypatch):
    db = MagicMock()
    today = date(2026, 8, 20)
    monkeypatch.setattr("intelligence.diagnosis.rules.local_today", lambda: today)
    leads = [
        _lead(1, "Teklif Verildi", created=date(2026, 1, 1), gorusme_tarihi="2026-08-01"),
        _lead(2, "Teklif Verildi", created=date(2026, 1, 1), gorusme_tarihi="2026-08-02"),
    ]
    with patch("intelligence.diagnosis.rules.get_reliable_offer_given_dates", return_value={}):
        with patch(
            "intelligence.diagnosis.rules.get_last_activity_dates",
            return_value={1: date(2026, 8, 15), 2: date(2026, 8, 16)},
        ):
            assert detect_offer_problems(db, 1, leads) == []


def test_offer_terminal_excluded(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr("intelligence.diagnosis.rules.local_today", lambda: date(2026, 8, 20))
    leads = [_lead(1, "Müşteri", created=date(2026, 1, 1), gorusme_tarihi="2026-01-01")]
    assert detect_offer_problems(db, 1, leads) == []


def test_offer_insufficient_dated_pending(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr("intelligence.diagnosis.rules.local_today", lambda: date(2026, 8, 20))
    leads = [_lead(1, "Teklif Verildi", created=date(2026, 1, 1))]
    with patch("intelligence.diagnosis.rules.get_reliable_offer_given_dates", return_value={}):
        assert detect_offer_problems(db, 1, leads) == []


# --- timezone period boundaries ---


def test_comparison_period_monthly_istanbul_calendar():
    anchor = date(2026, 3, 15)
    cur_s, cur_e, prev_s, prev_e = comparison_period_bounds("monthly", anchor)
    assert cur_s == date(2026, 3, 1)
    assert cur_e == date(2026, 3, 31)
    assert prev_s == date(2026, 2, 1)
    assert prev_e == date(2026, 2, 28)


# --- API ---


@pytest.fixture
def client():
    return TestClient(app)


def _override_user(role: str, user_id: int = 10, org_owner_id: int = 10):
    user = MagicMock()
    if role == "owner":
        user.id = org_owner_id
        user.owner_id = None
    else:
        user.id = user_id + 1
        user.owner_id = org_owner_id
    user.role = role
    user.account_type = "company"
    return user


def test_diagnoses_api_requires_auth(client):
    res = client.get("/api/intelligence/diagnoses")
    assert res.status_code == 401


def test_diagnoses_api_owner_and_employee(client):
    from auth import verify_token
    from database import get_db

    prev = settings.diagnosis_engine_enabled
    settings.diagnosis_engine_enabled = True
    payload = {
        "generated_at": "2026-08-08T12:00:00+03:00",
        "duration_ms": 1,
        "period_type": "monthly",
        "anchor": "2026-08-08",
        "items": [],
    }
    db = MagicMock()

    def _db():
        yield db

    try:
        with patch("intelligence.router.compute_diagnoses", return_value=payload):
            for role in ("owner", "employee"):
                app.dependency_overrides[verify_token] = lambda r=role: _override_user(r)
                app.dependency_overrides[get_db] = _db
                res = client.get(
                    "/api/intelligence/diagnoses",
                    headers={"Authorization": "Bearer test"},
                )
                assert res.status_code == 200, role
                body = res.json()
                assert body["items"] == []
                assert body["period_type"] == "monthly"
    finally:
        settings.diagnosis_engine_enabled = prev
        app.dependency_overrides.clear()


def test_diagnoses_api_disabled_flag(client):
    from auth import verify_token

    prev = settings.diagnosis_engine_enabled
    settings.diagnosis_engine_enabled = False
    try:
        app.dependency_overrides[verify_token] = lambda: _override_user("owner")
        res = client.get("/api/intelligence/diagnoses", headers={"Authorization": "Bearer test"})
        assert res.status_code == 404
    finally:
        settings.diagnosis_engine_enabled = prev
        app.dependency_overrides.clear()


def test_diagnoses_api_malformed_period(client):
    from auth import verify_token
    from database import get_db

    prev = settings.diagnosis_engine_enabled
    settings.diagnosis_engine_enabled = True
    db = MagicMock()

    def _db():
        yield db

    try:
        app.dependency_overrides[verify_token] = lambda: _override_user("owner")
        app.dependency_overrides[get_db] = _db
        with patch(
            "intelligence.router.compute_diagnoses",
            return_value={
                "generated_at": "",
                "duration_ms": 0,
                "period_type": "monthly",
                "anchor": "2026-08-08",
                "items": [],
            },
        ):
            res = client.get(
                "/api/intelligence/diagnoses?period=monthly&date=not-a-date",
                headers={"Authorization": "Bearer test"},
            )
        assert res.status_code == 200
    finally:
        settings.diagnosis_engine_enabled = prev
        app.dependency_overrides.clear()


def test_diagnoses_api_filters_passed(client):
    from auth import verify_token
    from database import get_db

    prev = settings.diagnosis_engine_enabled
    settings.diagnosis_engine_enabled = True
    db = MagicMock()

    def _db():
        yield db

    try:
        app.dependency_overrides[verify_token] = lambda: _override_user("owner")
        app.dependency_overrides[get_db] = _db
        with patch(
            "intelligence.router.compute_diagnoses",
            return_value={
                "generated_at": "",
                "duration_ms": 0,
                "period_type": "monthly",
                "anchor": "2026-08-01",
                "items": [],
            },
        ) as mock_compute:
            client.get(
                "/api/intelligence/diagnoses?type=funnel_drop&severity=high",
                headers={"Authorization": "Bearer test"},
            )
            mock_compute.assert_called_once()
            kwargs = mock_compute.call_args.kwargs
            assert kwargs.get("diagnosis_type") == "funnel_drop"
            assert kwargs.get("severity") == "high"
    finally:
        settings.diagnosis_engine_enabled = prev
        app.dependency_overrides.clear()
