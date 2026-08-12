"""DE-5.0-C — diagnosis sync / history HTTP API tests."""

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


SYNC_URL = "/api/intelligence/diagnoses/sync"
HISTORY_URL = "/api/intelligence/diagnoses/{diagnosis_id}/history"
LIST_URL = "/api/intelligence/diagnoses"


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


def _follow_up_item(*, current_value: float = 12.0, affected: int = 3) -> dict:
    return {
        "diagnosis_id": "follow_up_idle_leads",
        "type": "follow_up",
        "severity": "high",
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
            "average_days_idle": current_value - 1,
            "internal_debug": "should_not_leak",
        },
        "detected_at": datetime.utcnow().isoformat(),
        "impact": {
            "affected_lead_count": affected,
            "high_priority_count": affected,
            "medium_priority_count": 0,
            "low_priority_count": 0,
        },
        "top_priority_leads": [{"lead_id": 10, "priority": "high"}],
    }


def _compute_payload(items: list[dict] | None = None, *, period: str = "monthly") -> dict:
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "duration_ms": 1,
        "period_type": period,
        "anchor": "2026-08-11",
        "items": items if items is not None else [_follow_up_item()],
    }


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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- A–E sync auth / response ---


def test_A_owner_sync_200(client, owner_ctx):
    token, user = owner_ctx
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_compute_payload(),
    ) as mock_compute:
        r = client.post(SYNC_URL, json={"period": "monthly"}, headers=_auth(token))
    assert r.status_code == 200, r.text
    mock_compute.assert_called_once()
    assert mock_compute.call_args.args[1] == user.id


def test_B_employee_sync_403(client, owner_ctx):
    token, user = owner_ctx
    db = SessionLocal()
    try:
        emp_token, _ = _employee_token(db, owner_id=user.id)
    finally:
        db.close()
    r = client.post(SYNC_URL, json={"period": "monthly"}, headers=_auth(emp_token))
    assert r.status_code == 403


def test_C_cross_org_sync_isolation(client, owner_ctx):
    token_a, user_a = owner_ctx
    db = SessionLocal()
    try:
        user_b = User(
            username=f"de5c_{uuid.uuid4().hex[:8]}",
            email=f"de5c_{uuid.uuid4().hex[:8]}@example.com",
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

    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_compute_payload(),
    ):
        assert client.post(SYNC_URL, json={}, headers=_auth(token_a)).status_code == 200
        assert (
            client.post(
                SYNC_URL,
                json={"organization_id": user_a.id, "period": "monthly"},
                headers=_auth(token_b),
            ).status_code
            == 200
        )

    db = SessionLocal()
    try:
        cases_a = (
            db.query(DiagnosisCase)
            .filter(DiagnosisCase.organization_id == user_a.id)
            .count()
        )
        cases_b = (
            db.query(DiagnosisCase)
            .filter(DiagnosisCase.organization_id == uid_b)
            .count()
        )
        assert cases_a >= 1
        assert cases_b >= 1
        # Org B must not own org A's case rows
        leaked = (
            db.query(DiagnosisCase)
            .filter(
                DiagnosisCase.organization_id == uid_b,
                DiagnosisCase.diagnosis_id == "follow_up_idle_leads",
            )
            .all()
        )
        for row in leaked:
            assert row.organization_id == uid_b
        _cleanup_org(db, uid_b)
        db.query(User).filter(User.id == uid_b).delete()
        db.commit()
    finally:
        db.close()


def test_D_invalid_period_422(client, owner_ctx):
    token, _ = owner_ctx
    r = client.post(SYNC_URL, json={"period": "yearly"}, headers=_auth(token))
    assert r.status_code == 422


def test_E_sync_response_fields(client, owner_ctx):
    token, _ = owner_ctx
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_compute_payload(),
    ):
        r = client.post(SYNC_URL, json={"period": "weekly"}, headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    for key in (
        "period",
        "created_cases",
        "updated_cases",
        "new_snapshots",
        "resolved_cases",
        "reopened_cases",
        "unchanged_cases",
    ):
        assert key in body
    assert body["period"] == "weekly"
    assert body["created_cases"] >= 1
    assert body["new_snapshots"] >= 1


# --- F–G persistence via API ---


def test_F_first_sync_creates_case(client, owner_ctx):
    token, user = owner_ctx
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_compute_payload(),
    ):
        r = client.post(SYNC_URL, json={}, headers=_auth(token))
    assert r.status_code == 200
    db = SessionLocal()
    try:
        case = (
            db.query(DiagnosisCase)
            .filter(
                DiagnosisCase.organization_id == user.id,
                DiagnosisCase.diagnosis_id == "follow_up_idle_leads",
                DiagnosisCase.period_key == "current",
            )
            .one()
        )
        snaps = (
            db.query(DiagnosisSnapshot)
            .filter(DiagnosisSnapshot.case_id == case.id)
            .count()
        )
        assert snaps == 1
    finally:
        db.close()


def test_G_repeated_sync_no_duplicate_snapshot(client, owner_ctx):
    token, user = owner_ctx
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_compute_payload(),
    ):
        assert client.post(SYNC_URL, json={}, headers=_auth(token)).status_code == 200
        r2 = client.post(SYNC_URL, json={}, headers=_auth(token))
    assert r2.status_code == 200
    assert r2.json()["new_snapshots"] == 0
    db = SessionLocal()
    try:
        n = (
            db.query(DiagnosisSnapshot)
            .filter(
                DiagnosisSnapshot.organization_id == user.id,
                DiagnosisSnapshot.diagnosis_id == "follow_up_idle_leads",
            )
            .count()
        )
        assert n == 1
    finally:
        db.close()


# --- H–N history ---


def test_H_history_owner_200(client, owner_ctx):
    token, _ = owner_ctx
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_compute_payload(),
    ):
        client.post(SYNC_URL, json={}, headers=_auth(token))
    r = client.get(
        HISTORY_URL.format(diagnosis_id="follow_up_idle_leads"),
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["diagnosis_id"] == "follow_up_idle_leads"
    assert r.json()["period_key"] == "current"


def test_I_history_returns_snapshots(client, owner_ctx):
    token, _ = owner_ctx
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_compute_payload(),
    ):
        client.post(SYNC_URL, json={}, headers=_auth(token))
    r = client.get(
        HISTORY_URL.format(diagnosis_id="follow_up_idle_leads"),
        headers=_auth(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert len(body["snapshots"]) >= 1
    snap = body["snapshots"][0]
    for key in (
        "id",
        "observed_at",
        "state",
        "severity",
        "metric",
        "current_value",
        "fingerprint",
        "trigger",
        "evidence",
        "impact",
        "top_leads",
    ):
        assert key in snap
    assert "internal_debug" not in snap["evidence"]
    assert "average_days_idle" not in snap["evidence"]


def test_J_history_pagination(client, owner_ctx):
    token, _user = owner_ctx
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_compute_payload([_follow_up_item(current_value=12)]),
    ):
        client.post(SYNC_URL, json={}, headers=_auth(token))
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_compute_payload([_follow_up_item(current_value=20, affected=5)]),
    ):
        client.post(SYNC_URL, json={}, headers=_auth(token))
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_compute_payload([_follow_up_item(current_value=30, affected=7)]),
    ):
        client.post(SYNC_URL, json={}, headers=_auth(token))

    r1 = client.get(
        HISTORY_URL.format(diagnosis_id="follow_up_idle_leads") + "?page=1&limit=1",
        headers=_auth(token),
    )
    r2 = client.get(
        HISTORY_URL.format(diagnosis_id="follow_up_idle_leads") + "?page=2&limit=1",
        headers=_auth(token),
    )
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["total"] >= 3
    assert len(r1.json()["snapshots"]) == 1
    assert len(r2.json()["snapshots"]) == 1
    assert r1.json()["snapshots"][0]["id"] != r2.json()["snapshots"][0]["id"]
    # Newest first
    assert r1.json()["snapshots"][0]["id"] > r2.json()["snapshots"][0]["id"]


def test_K_history_cross_org_404(client, owner_ctx):
    token_a, user_a = owner_ctx
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_compute_payload(),
    ):
        client.post(SYNC_URL, json={}, headers=_auth(token_a))

    db = SessionLocal()
    try:
        user_b = User(
            username=f"de5ch_{uuid.uuid4().hex[:8]}",
            email=f"de5ch_{uuid.uuid4().hex[:8]}@example.com",
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

    r = client.get(
        HISTORY_URL.format(diagnosis_id="follow_up_idle_leads"),
        headers=_auth(token_b),
    )
    assert r.status_code == 404

    db = SessionLocal()
    try:
        db.query(User).filter(User.id == uid_b).delete()
        db.commit()
    finally:
        db.close()
    _ = user_a


def test_L_history_employee_403(client, owner_ctx):
    token, user = owner_ctx
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_compute_payload(),
    ):
        client.post(SYNC_URL, json={}, headers=_auth(token))
    db = SessionLocal()
    try:
        emp_token, _ = _employee_token(db, owner_id=user.id)
    finally:
        db.close()
    r = client.get(
        HISTORY_URL.format(diagnosis_id="follow_up_idle_leads"),
        headers=_auth(emp_token),
    )
    assert r.status_code == 403


def test_M_unknown_diagnosis_404(client, owner_ctx):
    token, _ = owner_ctx
    r = client.get(
        HISTORY_URL.format(diagnosis_id="does_not_exist_xyz"),
        headers=_auth(token),
    )
    assert r.status_code == 404


def test_N_diagnosis_id_collision_across_orgs_isolated(client, owner_ctx):
    token_a, user_a = owner_ctx
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_compute_payload([_follow_up_item(current_value=11)]),
    ):
        client.post(SYNC_URL, json={}, headers=_auth(token_a))

    db = SessionLocal()
    try:
        user_b = User(
            username=f"de5cn_{uuid.uuid4().hex[:8]}",
            email=f"de5cn_{uuid.uuid4().hex[:8]}@example.com",
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

    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_compute_payload([_follow_up_item(current_value=99, affected=9)]),
    ):
        assert client.post(SYNC_URL, json={}, headers=_auth(token_b)).status_code == 200

    ha = client.get(
        HISTORY_URL.format(diagnosis_id="follow_up_idle_leads"),
        headers=_auth(token_a),
    )
    hb = client.get(
        HISTORY_URL.format(diagnosis_id="follow_up_idle_leads"),
        headers=_auth(token_b),
    )
    assert ha.status_code == 200 and hb.status_code == 200
    assert ha.json()["snapshots"][0]["current_value"] == 11
    assert hb.json()["snapshots"][0]["current_value"] == 99

    db = SessionLocal()
    try:
        _cleanup_org(db, uid_b)
        db.query(User).filter(User.id == uid_b).delete()
        db.commit()
    finally:
        db.close()
    _ = user_a


# --- O–R GET compatibility / failure / openai ---


def test_O_get_diagnoses_does_not_create_snapshot(client, owner_ctx):
    token, user = owner_ctx
    db = SessionLocal()
    try:
        before = (
            db.query(DiagnosisSnapshot)
            .filter(DiagnosisSnapshot.organization_id == user.id)
            .count()
        )
    finally:
        db.close()

    with patch(
        "intelligence.router.compute_diagnoses",
        return_value=_compute_payload([]),
    ):
        r = client.get(LIST_URL, headers=_auth(token))
    assert r.status_code == 200

    db = SessionLocal()
    try:
        after = (
            db.query(DiagnosisSnapshot)
            .filter(DiagnosisSnapshot.organization_id == user.id)
            .count()
        )
        assert after == before == 0
        assert db.query(DiagnosisCase).filter(DiagnosisCase.organization_id == user.id).count() == 0
    finally:
        db.close()


def test_P_sync_failure_rolls_back(client, owner_ctx):
    token, user = owner_ctx
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_compute_payload(),
    ):
        assert client.post(SYNC_URL, json={}, headers=_auth(token)).status_code == 200

    db = SessionLocal()
    try:
        before_cases = (
            db.query(DiagnosisCase).filter(DiagnosisCase.organization_id == user.id).count()
        )
        before_snaps = (
            db.query(DiagnosisSnapshot)
            .filter(DiagnosisSnapshot.organization_id == user.id)
            .count()
        )
    finally:
        db.close()

    with patch(
        "intelligence.router.sync_diagnoses",
        side_effect=RuntimeError("boom"),
    ):
        r = client.post(SYNC_URL, json={}, headers=_auth(token))
    assert r.status_code == 500
    assert "boom" not in r.text

    db = SessionLocal()
    try:
        assert (
            db.query(DiagnosisCase).filter(DiagnosisCase.organization_id == user.id).count()
            == before_cases
        )
        assert (
            db.query(DiagnosisSnapshot)
            .filter(DiagnosisSnapshot.organization_id == user.id)
            .count()
            == before_snaps
        )
    finally:
        db.close()


def test_Q_no_openai_invocation(client, owner_ctx):
    token, _ = owner_ctx
    with (
        patch("intelligence.diagnosis.sync.compute_diagnoses", return_value=_compute_payload()) as compute,
        patch("ai.capabilities.diagnosis_interpreter.run_diagnosis_interpret", create=True) as interpret,
    ):
        r = client.post(SYNC_URL, json={}, headers=_auth(token))
        assert r.status_code == 200
        h = client.get(
            HISTORY_URL.format(diagnosis_id="follow_up_idle_leads"),
            headers=_auth(token),
        )
        assert h.status_code == 200
        compute.assert_called()
        interpret.assert_not_called()


def test_R_existing_diagnosis_get_regression(client, owner_ctx):
    token, _ = owner_ctx
    payload = _compute_payload([])
    with patch("intelligence.router.compute_diagnoses", return_value=payload) as mock_compute:
        r = client.get(LIST_URL + "?period=monthly", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["period_type"] == "monthly"
    mock_compute.assert_called_once()


def test_S_de4_endpoints_regression(client, owner_ctx):
    """DE-4 propose still owner-gated; sync must not break AI router mount."""
    token, user = owner_ctx
    prev = settings.ai_enabled
    settings.ai_enabled = True
    try:
        r = client.get("/api/ai/actions", headers=_auth(token))
        assert r.status_code == 200

        db = SessionLocal()
        try:
            emp_token, _ = _employee_token(db, owner_id=user.id)
        finally:
            db.close()
        r_emp = client.post(
            "/api/ai/actions/propose",
            json={
                "action_type": "propose_log_activity",
                "target_entity": "lead",
                "target_entity_id": 1,
                "parameters": {
                    "lead_id": 1,
                    "activity_type": "takip_yapildi",
                    "title": "x",
                    "description": "y",
                },
                "reason": "regression",
                "idempotency_key": f"de5c-{uuid.uuid4().hex[:12]}",
            },
            headers=_auth(emp_token),
        )
        assert r_emp.status_code == 403
    finally:
        settings.ai_enabled = prev
