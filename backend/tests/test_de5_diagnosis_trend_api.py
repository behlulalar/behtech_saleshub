"""DE-5.1-B — history API trend block (HTTP)."""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from auth import create_access_token
from config import settings
from database import DiagnosisCase, DiagnosisSnapshot, SessionLocal, User
from main import app
from migrate_auth import run_migrations
from security import hash_password


HISTORY_URL = "/api/intelligence/diagnoses/{diagnosis_id}/history"
SYNC_URL = "/api/intelligence/diagnoses/sync"

TREND_FORBIDDEN_KEYS = frozenset(
    {
        "fingerprint",
        "organization_id",
        "evidence",
        "evidence_json",
        "impact_json",
        "top_leads_json",
        "top_leads",
        "case_id",
        "latest_snapshot_id",
    }
)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _owner_token(db) -> tuple[str, User]:
    user = db.query(User).filter(User.role == "owner").order_by(User.id.asc()).first()
    if not user:
        pytest.skip("No owner user")
    token, _ = create_access_token(user.id, user.username, token_version=user.token_version or 0)
    return token, user


def _employee_token(db, owner_id: int | None = None) -> tuple[str, User]:
    q = db.query(User).filter(User.role == "employee")
    if owner_id is not None:
        q = q.filter(User.owner_id == owner_id)
    emp = q.first()
    if not emp:
        pytest.skip("No employee user")
    token, _ = create_access_token(emp.id, emp.username, token_version=emp.token_version or 0)
    return token, emp


def _cleanup_org(db, org_id: int) -> None:
    db.query(DiagnosisSnapshot).filter(DiagnosisSnapshot.organization_id == org_id).delete(
        synchronize_session=False
    )
    db.query(DiagnosisCase).filter(DiagnosisCase.organization_id == org_id).delete(
        synchronize_session=False
    )
    db.commit()


def _follow_up(
    *,
    current_value: float = 7.0,
    severity: str = "medium",
    affected: int = 1,
    lead_ids: list[int] | None = None,
) -> dict:
    leads = [{"lead_id": lid, "priority": "high"} for lid in (lead_ids or [10])]
    return {
        "diagnosis_id": "follow_up_idle_leads",
        "type": "follow_up",
        "severity": severity,
        "title": "Takip",
        "description": "idle",
        "metric": "days_since_last_contact",
        "current_value": current_value,
        "previous_value": None,
        "change_percent": None,
        "affected_lead_count": affected,
        "evidence": {
            "affected_lead_count": affected,
            "oldest_days_idle": int(current_value),
            "internal_debug": "nope",
        },
        "detected_at": datetime.utcnow().isoformat(),
        "impact": {
            "affected_lead_count": affected,
            "high_priority_count": affected,
            "medium_priority_count": 0,
            "low_priority_count": 0,
        },
        "top_priority_leads": leads,
    }


def _funnel(*, current_value: float = 0.2, severity: str = "medium") -> dict:
    return {
        "diagnosis_id": "funnel_demo_to_offer_drop",
        "type": "funnel_drop",
        "severity": severity,
        "title": "Funnel",
        "description": "drop",
        "metric": "demo_to_offer_conversion",
        "current_value": current_value,
        "previous_value": 0.4,
        "change_percent": -50.0,
        "affected_lead_count": 0,
        "evidence": {
            "from_stage": "Demo",
            "to_stage": "Teklif",
            "current": current_value,
            "sample_current_from": 10,
            "sample_current_to": 2,
        },
        "detected_at": datetime.utcnow().isoformat(),
        "impact": {
            "affected_lead_count": 0,
            "high_priority_count": 0,
            "medium_priority_count": 0,
            "low_priority_count": 0,
        },
        "top_priority_leads": [],
    }


def _offer(*, current_value: float = 10.0, severity: str = "medium", affected: int = 2) -> dict:
    return {
        "diagnosis_id": "offer_pending_stale",
        "type": "offer",
        "severity": severity,
        "title": "Offer",
        "description": "stale",
        "metric": "pending_offer_age_days",
        "current_value": current_value,
        "previous_value": None,
        "change_percent": None,
        "affected_lead_count": affected,
        "evidence": {
            "pending_offer_count": affected,
            "max_offer_age_days": int(current_value),
            "threshold_medium_days": 7,
            "threshold_high_days": 14,
        },
        "detected_at": datetime.utcnow().isoformat(),
        "impact": {
            "affected_lead_count": affected,
            "high_priority_count": 0,
            "medium_priority_count": affected,
            "low_priority_count": 0,
        },
        "top_priority_leads": [{"lead_id": 99, "priority": "medium"}],
    }


def _payload(items: list[dict], *, period: str = "monthly") -> dict:
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "duration_ms": 1,
        "period_type": period,
        "anchor": "2026-08-11",
        "items": items,
    }


def _assert_no_forbidden(obj, *, path: str = "trend") -> None:
    if isinstance(obj, dict):
        for key, val in obj.items():
            assert key not in TREND_FORBIDDEN_KEYS, f"leak {path}.{key}"
            # Nested snapshot refs must not carry DB id.
            if path.endswith("snapshot") or path.endswith("_snapshot"):
                assert key != "id", f"leak {path}.id"
            _assert_no_forbidden(val, path=f"{path}.{key}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _assert_no_forbidden(item, path=f"{path}[{i}]")


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def diagnosis_on():
    prev = settings.diagnosis_engine_enabled
    settings.diagnosis_engine_enabled = True
    try:
        yield
    finally:
        settings.diagnosis_engine_enabled = prev


@pytest.fixture
def owner_ctx(diagnosis_on):
    db = SessionLocal()
    run_migrations(db)
    token, user = _owner_token(db)
    _cleanup_org(db, user.id)
    try:
        yield token, user
    finally:
        _cleanup_org(db, user.id)
        db.close()


def _sync(client, token: str, items: list[dict], *, period: str = "monthly"):
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload(items, period=period),
    ):
        r = client.post(SYNC_URL, json={"period": period}, headers=_auth(token))
    assert r.status_code == 200
    return r.json()


def _history(client, token: str, diagnosis_id: str = "follow_up_idle_leads", **params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = HISTORY_URL.format(diagnosis_id=diagnosis_id)
    if qs:
        url = f"{url}?{qs}"
    return client.get(url, headers=_auth(token))


def test_A_first_snapshot_newly_detected(client, owner_ctx):
    token, _ = owner_ctx
    _sync(client, token, [_follow_up(current_value=7)])
    r = _history(client, token)
    assert r.status_code == 200
    trend = r.json()["trend"]
    assert trend["direction"] == "newly_detected"
    assert trend["substantive_count"] == 1
    assert trend["previous_snapshot"] is None
    assert trend["current_snapshot"] is not None


def test_B_second_worse_worsening(client, owner_ctx):
    token, _ = owner_ctx
    _sync(client, token, [_follow_up(current_value=5, affected=1)])
    _sync(client, token, [_follow_up(current_value=12, affected=3, severity="high")])
    trend = _history(client, token).json()["trend"]
    assert trend["direction"] == "worsening"
    assert "metric_worsened" in trend["reason_codes"] or "severity_increased" in trend["reason_codes"]
    assert trend["changes"]["current_value_from"] == 5
    assert trend["changes"]["current_value_to"] == 12


def test_C_improved_improving(client, owner_ctx):
    token, _ = owner_ctx
    _sync(client, token, [_follow_up(current_value=12, severity="high", affected=3)])
    _sync(client, token, [_follow_up(current_value=6, severity="medium", affected=1)])
    trend = _history(client, token).json()["trend"]
    assert trend["direction"] == "improving"


def test_D_same_observation_stable(client, owner_ctx):
    token, user = owner_ctx
    _sync(client, token, [_follow_up(current_value=7, affected=1)])
    _sync(client, token, [_follow_up(current_value=10, affected=2)])
    # Fingerprint blocks duplicate equal observations via sync; insert twin for stable pair.
    db = SessionLocal()
    try:
        case = (
            db.query(DiagnosisCase)
            .filter(
                DiagnosisCase.organization_id == user.id,
                DiagnosisCase.diagnosis_id == "follow_up_idle_leads",
            )
            .one()
        )
        last = (
            db.query(DiagnosisSnapshot)
            .filter(DiagnosisSnapshot.case_id == case.id)
            .order_by(DiagnosisSnapshot.id.desc())
            .first()
        )
        assert last is not None
        twin = DiagnosisSnapshot(
            organization_id=case.organization_id,
            case_id=case.id,
            diagnosis_id=case.diagnosis_id,
            period_key=case.period_key,
            anchor=last.anchor,
            observed_at=datetime.utcnow(),
            state="active",
            severity=last.severity,
            metric=last.metric,
            current_value=last.current_value,
            engine_previous_value=last.engine_previous_value,
            change_percent=last.change_percent,
            affected_lead_count=last.affected_lead_count,
            impact_json=last.impact_json,
            top_leads_json=last.top_leads_json,
            evidence_json=last.evidence_json,
            fingerprint="twin-stable-" + uuid.uuid4().hex[:8],
            trigger="sync",
        )
        db.add(twin)
        db.commit()
    finally:
        db.close()

    trend = _history(client, token).json()["trend"]
    assert trend["direction"] == "stable"
    assert trend["reason_codes"] == []


def test_E_resolved(client, owner_ctx):
    token, _ = owner_ctx
    _sync(client, token, [_follow_up(current_value=7)])
    _sync(client, token, [])  # missing → resolve
    trend = _history(client, token).json()["trend"]
    assert trend["direction"] == "resolved"
    body = _history(client, token).json()
    assert body["state"] == "resolved"


def test_F_reopened(client, owner_ctx):
    token, _ = owner_ctx
    _sync(client, token, [_follow_up(current_value=7)])
    _sync(client, token, [])
    _sync(client, token, [_follow_up(current_value=8)])
    body = _history(client, token).json()
    assert body["state"] == "active"  # lifecycle
    assert body["trend"]["direction"] == "reopened"  # trend layer


def test_G_reason_codes(client, owner_ctx):
    token, _ = owner_ctx
    _sync(client, token, [_follow_up(current_value=5, severity="medium", affected=1, lead_ids=[1])])
    _sync(
        client,
        token,
        [_follow_up(current_value=12, severity="high", affected=3, lead_ids=[1, 2])],
    )
    codes = _history(client, token).json()["trend"]["reason_codes"]
    assert "severity_increased" in codes
    assert "metric_worsened" in codes
    assert "affected_lead_count_increased" in codes


def test_H_episode_metrics(client, owner_ctx):
    token, _ = owner_ctx
    _sync(client, token, [_follow_up(current_value=5)])
    _sync(client, token, [_follow_up(current_value=15, severity="high", affected=4)])
    metrics = _history(client, token).json()["trend"]["metrics"]
    assert metrics["substantive_count"] == 2
    assert metrics["total_snapshot_count"] == 2
    assert metrics["reopen_count"] == 0
    assert metrics["active_duration_seconds"] is not None
    assert metrics["last_substantive_change_at"]
    wp = metrics["worst_point"]
    assert wp is not None
    assert wp["severity"] == "high"
    assert wp["current_value"] == 15
    assert "fingerprint" not in wp
    assert "id" not in wp


def test_I_org_isolation(client, owner_ctx, diagnosis_on):
    token_a, user_a = owner_ctx
    _sync(client, token_a, [_follow_up(current_value=7)])

    db = SessionLocal()
    try:
        other = User(
            username=f"trend_iso_{uuid.uuid4().hex[:8]}",
            email=f"trend_iso_{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("testpass123"),
            role="owner",
            email_verified=True,
        )
        db.add(other)
        db.commit()
        db.refresh(other)
        uid_b = other.id
        token_b, _ = create_access_token(other.id, other.username, token_version=0)
        _cleanup_org(db, uid_b)
    finally:
        db.close()

    r = client.get(
        HISTORY_URL.format(diagnosis_id="follow_up_idle_leads"),
        headers=_auth(token_b),
    )
    assert r.status_code == 404

    db = SessionLocal()
    try:
        _cleanup_org(db, uid_b)
        db.query(User).filter(User.id == uid_b).delete()
        db.commit()
    finally:
        db.close()


def test_J_employee_forbidden_owner_ok(client, owner_ctx):
    token, user = owner_ctx
    _sync(client, token, [_follow_up()])
    assert _history(client, token).status_code == 200
    db = SessionLocal()
    try:
        emp_token, _ = _employee_token(db, owner_id=user.id)
    finally:
        db.close()
    r = client.get(
        HISTORY_URL.format(diagnosis_id="follow_up_idle_leads"),
        headers=_auth(emp_token),
    )
    assert r.status_code in (401, 403)


def test_K_trend_no_internal_leak(client, owner_ctx):
    token, _ = owner_ctx
    _sync(client, token, [_follow_up(current_value=5)])
    _sync(client, token, [_follow_up(current_value=12, severity="high", affected=3)])
    trend = _history(client, token).json()["trend"]
    _assert_no_forbidden(trend)
    for ref in (trend.get("previous_snapshot"), trend.get("current_snapshot")):
        if ref:
            assert "id" not in ref
            assert "fingerprint" not in ref
            assert "evidence" not in ref


def test_L_funnel_direction(client, owner_ctx):
    token, _ = owner_ctx
    _sync(client, token, [_funnel(current_value=0.20)], period="monthly")
    _sync(client, token, [_funnel(current_value=0.10)], period="monthly")
    r = _history(client, token, "funnel_demo_to_offer_drop", period_key="monthly")
    assert r.status_code == 200
    trend = r.json()["trend"]
    assert trend["direction"] == "worsening"
    assert "metric_worsened" in trend["reason_codes"]

    _sync(client, token, [_funnel(current_value=0.35)], period="monthly")
    trend2 = _history(client, token, "funnel_demo_to_offer_drop", period_key="monthly").json()[
        "trend"
    ]
    assert trend2["direction"] == "improving"


def test_M_follow_up_direction(client, owner_ctx):
    token, _ = owner_ctx
    _sync(client, token, [_follow_up(current_value=5)])
    _sync(client, token, [_follow_up(current_value=9)])
    assert _history(client, token).json()["trend"]["direction"] == "worsening"


def test_N_offer_direction(client, owner_ctx):
    token, _ = owner_ctx
    _sync(client, token, [_offer(current_value=10)])
    _sync(client, token, [_offer(current_value=18)])
    r = _history(client, token, "offer_pending_stale")
    assert r.status_code == 200
    assert r.json()["trend"]["direction"] == "worsening"
    _sync(client, token, [_offer(current_value=8)])
    assert _history(client, token, "offer_pending_stale").json()["trend"]["direction"] == "improving"


def test_trend_stable_across_pagination_pages(client, owner_ctx):
    token, _ = owner_ctx
    _sync(client, token, [_follow_up(current_value=5)])
    _sync(client, token, [_follow_up(current_value=8)])
    _sync(client, token, [_follow_up(current_value=12)])
    r1 = _history(client, token, page=1, limit=1)
    r2 = _history(client, token, page=2, limit=1)
    assert r1.json()["trend"]["direction"] == r2.json()["trend"]["direction"]
    assert r1.json()["trend"]["substantive_count"] == r2.json()["trend"]["substantive_count"]
    assert len(r1.json()["snapshots"]) == 1
    assert len(r2.json()["snapshots"]) == 1
