"""DE-5.0-B — diagnosis sync / persistence tests."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from database import DiagnosisCase, DiagnosisSnapshot, SessionLocal, User
from intelligence.diagnosis.fingerprint import (
    compute_observation_fingerprint,
    observation_fingerprint_payload,
)
from intelligence.diagnosis.lifecycle_constants import (
    PERIOD_KEY_CURRENT,
    STATE_ACTIVE,
    STATE_IMPROVING,
    STATE_NEW,
    STATE_RESOLVED,
    STATE_WORSENING,
)
from intelligence.diagnosis.sync import (
    canonical_period_key,
    compute_next_state,
    sync_diagnoses,
)
from migrate_auth import run_migrations


def _owner_ids(db: Session) -> list[int]:
    return [int(u.id) for u in db.query(User).filter(User.role == "owner").order_by(User.id.asc()).all()]


def _org(db: Session) -> int:
    ids = _owner_ids(db)
    if not ids:
        pytest.skip("No owner")
    return ids[0]


def _cleanup_org(db: Session, org_id: int) -> None:
    db.query(DiagnosisSnapshot).filter(DiagnosisSnapshot.organization_id == org_id).delete(
        synchronize_session=False
    )
    db.query(DiagnosisCase).filter(DiagnosisCase.organization_id == org_id).delete(
        synchronize_session=False
    )
    db.commit()


def _follow_up(
    *,
    current_value: float = 12.0,
    severity: str = "high",
    affected: int = 3,
    lead_ids: list[int] | None = None,
    title: str = "Takip gerektiren aktif lead'ler",
    description: str = "idle",
) -> dict:
    leads = [{"lead_id": lid, "priority": "high"} for lid in (lead_ids or [10, 20])]
    return {
        "diagnosis_id": "follow_up_idle_leads",
        "type": "follow_up",
        "severity": severity,
        "title": title,
        "description": description,
        "metric": "days_since_last_contact",
        "current_value": current_value,
        "previous_value": None,
        "change_percent": None,
        "affected_lead_count": affected,
        "evidence": {
            "affected_lead_count": affected,
            "oldest_days_idle": int(current_value),
            "average_days_idle": current_value - 1,
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


def _offer(
    *,
    current_value: float = 14.0,
    severity: str = "medium",
    affected: int = 2,
) -> dict:
    return {
        "diagnosis_id": "offer_pending_stale",
        "type": "offer",
        "severity": severity,
        "title": "Bekleyen teklifler uzadı",
        "description": "stale",
        "metric": "pending_offer_age_days",
        "current_value": current_value,
        "previous_value": None,
        "change_percent": None,
        "affected_lead_count": affected,
        "evidence": {
            "max_offer_age_days": int(current_value),
            "average_offer_age_days": current_value - 2,
            "count_age_gte_medium": affected,
        },
        "detected_at": "2026-01-01T00:00:00",
        "impact": {
            "affected_lead_count": affected,
            "high_priority_count": 0,
            "medium_priority_count": affected,
            "low_priority_count": 0,
        },
        "top_priority_leads": [{"lead_id": 5, "priority": "medium"}],
    }


def _funnel(
    *,
    diagnosis_id: str = "funnel_demo_to_offer_drop",
    current_value: float = 20.0,
    previous_value: float = 30.0,
    change_percent: float = -33.3,
    severity: str = "medium",
    sample_from: int = 10,
    sample_to: int = 2,
) -> dict:
    return {
        "diagnosis_id": diagnosis_id,
        "type": "funnel_drop",
        "severity": severity,
        "title": "Demo → Teklif dönüşümü düştü",
        "description": "drop",
        "metric": "demo_to_offer_conversion",
        "current_value": current_value,
        "previous_value": previous_value,
        "change_percent": change_percent,
        "affected_lead_count": sample_to,
        "evidence": {
            "from_stage": "demo",
            "to_stage": "teklif",
            "current": current_value,
            "previous": previous_value,
            "sample_current_from": sample_from,
            "sample_current_to": sample_to,
            "current_period": "Aug 2026",
            "previous_period": "Jul 2026",
        },
        "detected_at": "2026-08-01T00:00:00",
        "impact": {
            "affected_lead_count": 0,
            "high_priority_count": 0,
            "medium_priority_count": 0,
            "low_priority_count": 0,
        },
        "top_priority_leads": [],
    }


def _payload(items: list[dict], *, period: str = "monthly", anchor: str = "2026-08-11") -> dict:
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "duration_ms": 1,
        "period_type": period,
        "anchor": anchor,
        "items": items,
    }


@pytest.fixture
def db():
    session = SessionLocal()
    run_migrations(session)
    org_id = _org(session)
    _cleanup_org(session, org_id)
    try:
        yield session, org_id
    finally:
        _cleanup_org(session, org_id)
        session.close()


def test_canonical_period_keys():
    assert canonical_period_key("funnel_drop", "weekly") == "weekly"
    assert canonical_period_key("follow_up", "monthly") == PERIOD_KEY_CURRENT
    assert canonical_period_key("offer", "daily") == PERIOD_KEY_CURRENT


def test_fingerprint_deterministic_and_ignores_noise():
    a = _follow_up(title="A", description="one")
    b = _follow_up(title="B", description="two")
    b["detected_at"] = "different"
    b["evidence"]["average_days_idle"] = 999
    assert compute_observation_fingerprint(a) == compute_observation_fingerprint(b)

    c = _follow_up(lead_ids=[20, 10])
    d = _follow_up(lead_ids=[99])
    assert compute_observation_fingerprint(c) != compute_observation_fingerprint(d)

    payload = observation_fingerprint_payload(a)
    assert "average_days_idle" not in str(payload)
    assert "title" not in payload


def test_A_first_sync_creates_new_case_and_snapshot(db):
    session, org_id = db
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up()]),
    ):
        result = sync_diagnoses(session, org_id, period="monthly")
        session.commit()
    assert result.created_cases == 1
    assert result.new_snapshots == 1
    case = session.query(DiagnosisCase).filter_by(organization_id=org_id).one()
    assert case.state == STATE_NEW
    assert case.period_key == PERIOD_KEY_CURRENT
    assert session.query(DiagnosisSnapshot).filter_by(case_id=case.id).count() == 1


def test_B_second_sync_same_observation_no_new_snapshot(db):
    session, org_id = db
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up()]),
    ):
        sync_diagnoses(session, org_id)
        session.commit()
        r2 = sync_diagnoses(session, org_id)
        session.commit()
    assert r2.created_cases == 0
    assert r2.new_snapshots == 0
    assert r2.unchanged_cases == 1
    assert session.query(DiagnosisCase).count() == 1
    assert session.query(DiagnosisSnapshot).count() == 1


def test_C_observation_change_adds_snapshot(db):
    session, org_id = db
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up(current_value=10)]),
    ):
        sync_diagnoses(session, org_id)
        session.commit()
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up(current_value=20)]),
    ):
        r = sync_diagnoses(session, org_id)
        session.commit()
    assert r.new_snapshots == 1
    assert session.query(DiagnosisSnapshot).count() == 2
    assert session.query(DiagnosisCase).count() == 1


def test_D_worsening_state(db):
    session, org_id = db
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up(current_value=8, severity="medium")]),
    ):
        sync_diagnoses(session, org_id)
        session.commit()
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up(current_value=20, severity="high")]),
    ):
        sync_diagnoses(session, org_id)
        session.commit()
    case = session.query(DiagnosisCase).one()
    assert case.state == STATE_WORSENING


def test_E_improving_state(db):
    session, org_id = db
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up(current_value=20, severity="high")]),
    ):
        sync_diagnoses(session, org_id)
        session.commit()
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up(current_value=8, severity="medium")]),
    ):
        sync_diagnoses(session, org_id)
        session.commit()
    assert session.query(DiagnosisCase).one().state == STATE_IMPROVING


def test_F_active_when_direction_unclear():
    prev = {"severity": "high", "current_value": 10.0, "affected_lead_count": 2}
    cur = {
        "severity": "high",
        "current_value": 10.0,
        "affected_lead_count": 2,
        "diagnosis_type": "follow_up",
    }
    # lead-set-only change is represented as fingerprint change with same metrics
    assert (
        compute_next_state(
            diagnosis_type="follow_up",
            previous=prev,
            current=cur,
            was_resolved=False,
        )
        == STATE_ACTIVE
    )


def test_G_resolve_when_missing(db):
    session, org_id = db
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up()]),
    ):
        sync_diagnoses(session, org_id)
        session.commit()
    case = session.query(DiagnosisCase).one()
    last_seen = case.last_seen_at
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([]),
    ):
        r = sync_diagnoses(session, org_id)
        session.commit()
    session.refresh(case)
    assert r.resolved_cases == 1
    assert case.state == STATE_RESOLVED
    assert case.resolved_at is not None
    assert case.last_seen_at == last_seen
    assert session.query(DiagnosisSnapshot).filter_by(state=STATE_RESOLVED).count() == 1


def test_H_reappear_same_case(db):
    session, org_id = db
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up()]),
    ):
        sync_diagnoses(session, org_id)
        session.commit()
    case = session.query(DiagnosisCase).one()
    first_seen = case.first_seen_at
    case_id = case.id
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([]),
    ):
        sync_diagnoses(session, org_id)
        session.commit()
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up(current_value=15)]),
    ):
        r = sync_diagnoses(session, org_id)
        session.commit()
    session.refresh(case)
    assert r.reopened_cases == 1
    assert session.query(DiagnosisCase).count() == 1
    assert case.id == case_id
    assert case.first_seen_at == first_seen
    assert case.resolved_at is None
    assert case.state == STATE_ACTIVE


def test_I_funnel_period_isolation(db):
    session, org_id = db
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_funnel()], period="monthly"),
    ):
        sync_diagnoses(session, org_id, period="monthly")
        session.commit()
    monthly = session.query(DiagnosisCase).filter_by(period_key="monthly").one()
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([], period="weekly"),
    ):
        sync_diagnoses(session, org_id, period="weekly")
        session.commit()
    session.refresh(monthly)
    assert monthly.state != STATE_RESOLVED


def test_J_follow_up_current_identity_across_periods(db):
    session, org_id = db
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up()], period="monthly"),
    ):
        sync_diagnoses(session, org_id, period="monthly")
        session.commit()
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up()], period="daily"),
    ):
        sync_diagnoses(session, org_id, period="daily")
        session.commit()
    cases = session.query(DiagnosisCase).filter_by(diagnosis_id="follow_up_idle_leads").all()
    assert len(cases) == 1
    assert cases[0].period_key == PERIOD_KEY_CURRENT


def test_K_offer_current_identity(db):
    session, org_id = db
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_offer()], period="weekly"),
    ):
        sync_diagnoses(session, org_id, period="weekly")
        session.commit()
    assert session.query(DiagnosisCase).one().period_key == PERIOD_KEY_CURRENT


def test_L_sync_calls_unfiltered_compute(db):
    session, org_id = db
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([]),
    ) as mocked:
        sync_diagnoses(session, org_id, period="monthly")
        session.commit()
    kwargs = mocked.call_args.kwargs
    assert kwargs.get("diagnosis_type") is None
    assert kwargs.get("severity") is None


def test_M_engine_exception_no_db_writes(db):
    session, org_id = db
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        side_effect=RuntimeError("boom"),
    ):
        with pytest.raises(RuntimeError):
            sync_diagnoses(session, org_id)
        session.rollback()
    assert session.query(DiagnosisCase).filter_by(organization_id=org_id).count() == 0
    assert session.query(DiagnosisSnapshot).filter_by(organization_id=org_id).count() == 0


def test_N_org_isolation(db):
    session, org_id = db
    owners = _owner_ids(session)
    if len(owners) < 2:
        # synthesize foreign org row with fake org id unlikely to collide
        other_org = org_id + 10_000_000
        now = datetime.utcnow()
        foreign = DiagnosisCase(
            organization_id=other_org,
            diagnosis_id="follow_up_idle_leads",
            diagnosis_type="follow_up",
            period_key=PERIOD_KEY_CURRENT,
            state=STATE_NEW,
            severity="high",
            title="foreign",
            metric="days_since_last_contact",
            affected_lead_count=1,
            fingerprint="foreign-fp",
            first_seen_at=now,
            last_seen_at=now,
            last_synced_at=now,
        )
        # May fail FK if org doesn't exist — skip
        try:
            session.add(foreign)
            session.commit()
        except Exception:
            session.rollback()
            pytest.skip("Cannot create cross-org fixture without second owner")
        other_id = other_org
    else:
        other_id = owners[1]
        _cleanup_org(session, other_id)
        now = datetime.utcnow()
        session.add(
            DiagnosisCase(
                organization_id=other_id,
                diagnosis_id="follow_up_idle_leads",
                diagnosis_type="follow_up",
                period_key=PERIOD_KEY_CURRENT,
                state=STATE_NEW,
                severity="high",
                title="other",
                metric="days_since_last_contact",
                affected_lead_count=1,
                fingerprint="other-fp",
                first_seen_at=now,
                last_seen_at=now,
                last_synced_at=now,
            )
        )
        session.commit()

    before = session.query(DiagnosisCase).filter_by(organization_id=other_id).one()
    fp_before = before.fingerprint
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up()]),
    ):
        sync_diagnoses(session, org_id)
        session.commit()
    session.refresh(before)
    assert before.fingerprint == fp_before
    if other_id != org_id + 10_000_000:
        _cleanup_org(session, other_id)
    else:
        session.query(DiagnosisCase).filter_by(organization_id=other_id).delete(
            synchronize_session=False
        )
        session.commit()


def test_O_unique_identity(db):
    session, org_id = db
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up(), _follow_up()]),
    ):
        sync_diagnoses(session, org_id)
        session.commit()
    assert session.query(DiagnosisCase).filter_by(organization_id=org_id).count() == 1


def test_P_fingerprint_determinism():
    item = _funnel()
    assert compute_observation_fingerprint(item) == compute_observation_fingerprint(dict(item))


def test_Q_timestamp_only_change_no_snapshot(db):
    session, org_id = db
    item = _follow_up()
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([item]),
    ):
        sync_diagnoses(session, org_id)
        session.commit()
    item2 = _follow_up()
    item2["detected_at"] = "2099-01-01T00:00:00"
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([item2]),
    ):
        r = sync_diagnoses(session, org_id)
        session.commit()
    assert r.new_snapshots == 0


def test_R_title_description_change_no_snapshot(db):
    session, org_id = db
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up(title="one", description="a")]),
    ):
        sync_diagnoses(session, org_id)
        session.commit()
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up(title="two", description="b")]),
    ):
        r = sync_diagnoses(session, org_id)
        session.commit()
    assert r.new_snapshots == 0


def test_S_lead_set_change_new_snapshot(db):
    session, org_id = db
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up(lead_ids=[1, 2])]),
    ):
        sync_diagnoses(session, org_id)
        session.commit()
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up(lead_ids=[1, 2, 3])]),
    ):
        r = sync_diagnoses(session, org_id)
        session.commit()
    assert r.new_snapshots == 1


def test_T_severity_change_new_snapshot(db):
    session, org_id = db
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up(severity="medium", current_value=8)]),
    ):
        sync_diagnoses(session, org_id)
        session.commit()
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up(severity="high", current_value=8)]),
    ):
        r = sync_diagnoses(session, org_id)
        session.commit()
    assert r.new_snapshots == 1


def test_U_affected_count_change_new_snapshot(db):
    session, org_id = db
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up(affected=2, current_value=10)]),
    ):
        sync_diagnoses(session, org_id)
        session.commit()
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up(affected=5, current_value=10)]),
    ):
        r = sync_diagnoses(session, org_id)
        session.commit()
    assert r.new_snapshots == 1
    assert session.query(DiagnosisCase).one().state == STATE_WORSENING


def test_V_transaction_rollback_on_persistence_error(db):
    session, org_id = db
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_follow_up()]),
    ), patch(
        "intelligence.diagnosis.sync._create_snapshot",
        side_effect=RuntimeError("persist fail"),
    ):
        with pytest.raises(RuntimeError):
            sync_diagnoses(session, org_id)
        session.rollback()
    assert session.query(DiagnosisCase).filter_by(organization_id=org_id).count() == 0
    assert session.query(DiagnosisSnapshot).filter_by(organization_id=org_id).count() == 0


def test_W_resolve_preserves_last_seen(db):
    test_G_resolve_when_missing(db)


def test_X_reappear_preserves_first_seen(db):
    test_H_reappear_same_case(db)


def test_funnel_improving_by_conversion_rate(db):
    session, org_id = db
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_funnel(current_value=15.0, previous_value=30.0)]),
    ):
        sync_diagnoses(session, org_id, period="monthly")
        session.commit()
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload([_funnel(current_value=25.0, previous_value=30.0, change_percent=-16.7)]),
    ):
        sync_diagnoses(session, org_id, period="monthly")
        session.commit()
    assert session.query(DiagnosisCase).one().state == STATE_IMPROVING
