"""DE-5.0-A — diagnosis_cases / diagnosis_snapshots DB foundation."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy import inspect

from database import DiagnosisCase, DiagnosisSnapshot, SessionLocal, User
from migrate_auth import run_migrations


def _owner_id(db) -> int:
    user = db.query(User).filter(User.role == "owner").order_by(User.id.asc()).first()
    if not user:
        pytest.skip("No owner user")
    return int(user.id)


def test_diagnosis_history_tables_exist_after_migration():
    db = SessionLocal()
    try:
        run_migrations(db)
        tables = set(inspect(db.bind).get_table_names())
        assert "diagnosis_cases" in tables
        assert "diagnosis_snapshots" in tables
    finally:
        db.close()


def test_migration_idempotent_second_run():
    db = SessionLocal()
    try:
        run_migrations(db)
        run_migrations(db)
        tables = set(inspect(db.bind).get_table_names())
        assert "diagnosis_cases" in tables
        assert "diagnosis_snapshots" in tables
    finally:
        db.close()


def test_diagnosis_case_unique_constraint():
    db = SessionLocal()
    marker = None
    try:
        run_migrations(db)
        org_id = _owner_id(db)
        now = datetime.utcnow()
        marker = f"de5a-unique-{now.timestamp()}"
        row = DiagnosisCase(
            organization_id=org_id,
            diagnosis_id=marker,
            diagnosis_type="follow_up",
            period_key="current",
            state="new",
            severity="medium",
            title="t",
            metric="days_since_last_contact",
            affected_lead_count=1,
            fingerprint="fp1",
            first_seen_at=now,
            last_seen_at=now,
            last_synced_at=now,
        )
        db.add(row)
        db.commit()

        dup = DiagnosisCase(
            organization_id=org_id,
            diagnosis_id=marker,
            diagnosis_type="follow_up",
            period_key="current",
            state="active",
            severity="high",
            title="t2",
            metric="days_since_last_contact",
            affected_lead_count=2,
            fingerprint="fp2",
            first_seen_at=now,
            last_seen_at=now,
            last_synced_at=now,
        )
        db.add(dup)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        if marker:
            db.query(DiagnosisCase).filter(DiagnosisCase.diagnosis_id == marker).delete(
                synchronize_session=False
            )
            db.commit()
        db.close()


def test_diagnosis_snapshot_case_fk_and_cascade():
    db = SessionLocal()
    case_id = None
    marker = None
    try:
        run_migrations(db)
        org_id = _owner_id(db)
        now = datetime.utcnow()
        marker = f"de5a-fk-{now.timestamp()}"
        case = DiagnosisCase(
            organization_id=org_id,
            diagnosis_id=marker,
            diagnosis_type="offer",
            period_key="current",
            state="new",
            severity="medium",
            title="offer",
            metric="pending_offer_age_days",
            affected_lead_count=2,
            fingerprint="fp-case",
            first_seen_at=now,
            last_seen_at=now,
            last_synced_at=now,
        )
        db.add(case)
        db.commit()
        db.refresh(case)
        case_id = case.id

        snap = DiagnosisSnapshot(
            organization_id=org_id,
            case_id=case_id,
            diagnosis_id=marker,
            period_key="current",
            anchor=now.date().isoformat(),
            observed_at=now,
            state="new",
            severity="medium",
            metric="pending_offer_age_days",
            affected_lead_count=2,
            impact_json="{}",
            top_leads_json="[]",
            evidence_json="{}",
            fingerprint="fp-snap",
            trigger="sync",
        )
        db.add(snap)
        db.commit()
        db.refresh(snap)
        assert snap.id is not None
        assert snap.organization_id == org_id
        assert snap.case_id == case_id

        bad = DiagnosisSnapshot(
            organization_id=org_id,
            case_id=-1,
            diagnosis_id=marker,
            period_key="current",
            anchor=now.date().isoformat(),
            observed_at=now,
            state="new",
            severity="medium",
            metric="pending_offer_age_days",
            affected_lead_count=0,
            fingerprint="fp-bad",
            trigger="sync",
        )
        db.add(bad)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        db.query(DiagnosisCase).filter(DiagnosisCase.id == case_id).delete(synchronize_session=False)
        db.commit()
        remaining = (
            db.query(DiagnosisSnapshot).filter(DiagnosisSnapshot.case_id == case_id).count()
        )
        assert remaining == 0
        case_id = None
    finally:
        if case_id is not None:
            db.query(DiagnosisSnapshot).filter(DiagnosisSnapshot.case_id == case_id).delete(
                synchronize_session=False
            )
            db.query(DiagnosisCase).filter(DiagnosisCase.id == case_id).delete(
                synchronize_session=False
            )
            db.commit()
        elif marker:
            db.query(DiagnosisCase).filter(DiagnosisCase.diagnosis_id == marker).delete(
                synchronize_session=False
            )
            db.commit()
        db.close()


def test_diagnosis_case_has_organization_isolation_column():
    db = SessionLocal()
    try:
        run_migrations(db)
        cols = {c["name"] for c in inspect(db.bind).get_columns("diagnosis_cases")}
        snap_cols = {c["name"] for c in inspect(db.bind).get_columns("diagnosis_snapshots")}
        assert "organization_id" in cols
        assert "organization_id" in snap_cols
        assert "period_key" in cols
        assert "fingerprint" in cols
        assert "engine_previous_value" in cols
        assert "case_id" in snap_cols
        assert "trigger" in snap_cols
    finally:
        db.close()
