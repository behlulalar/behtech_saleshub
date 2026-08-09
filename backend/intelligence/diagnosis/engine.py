"""Diagnosis Engine orchestrator (read-only, deterministic)."""

from __future__ import annotations

import logging
import time
from datetime import date

from sqlalchemy.orm import Session

from app_timezone import local_now, local_today
from dashboard import INACTIVE_STATUSES
from database import Lead
from intelligence.diagnosis.constants import PENDING_OFFER_STATUS
from intelligence.diagnosis.de2_enrich import enrich_diagnosis_de2
from intelligence.diagnosis.evidence import get_reliable_offer_given_dates
from intelligence.diagnosis.models import DiagnosisResult
from intelligence.diagnosis.rules import detect_follow_up_problems, detect_funnel_drops, detect_offer_problems
from reminders import get_last_activity_dates

logger = logging.getLogger("behtech.diagnosis")


def _batch_activity_dates(db: Session, org_id: int, leads: list[Lead]) -> dict[int, date]:
    active = [lead for lead in leads if lead.durum not in INACTIVE_STATUSES]
    if not active:
        return {}
    lead_ids = [lead.id for lead in active]
    return get_last_activity_dates(db, org_id, lead_ids)


def _batch_offer_dates(db: Session, org_id: int, leads: list[Lead]) -> dict[int, date]:
    pending = [lead for lead in leads if lead.durum in PENDING_OFFER_STATUS]
    if not pending:
        return {}
    lead_ids = [lead.id for lead in pending]
    return get_reliable_offer_given_dates(db, org_id, lead_ids)


def compute_diagnoses(
    db: Session,
    org_id: int,
    *,
    period_type: str = "monthly",
    anchor: date | None = None,
    diagnosis_type: str | None = None,
    severity: str | None = None,
) -> dict:
    if period_type not in ("daily", "weekly", "monthly"):
        period_type = "monthly"
    anchor = anchor or local_today()

    started = time.perf_counter()
    leads = db.query(Lead).filter(Lead.user_id == org_id).all()

    run_follow_up = diagnosis_type is None or diagnosis_type == "follow_up"
    run_offer = diagnosis_type is None or diagnosis_type == "offer"

    activity_dates: dict[int, date] = (
        _batch_activity_dates(db, org_id, leads) if run_follow_up else {}
    )
    offer_given_dates: dict[int, date] = (
        _batch_offer_dates(db, org_id, leads) if run_offer else {}
    )
    items: list[DiagnosisResult] = []

    try:
        if not diagnosis_type or diagnosis_type == "funnel_drop":
            items.extend(detect_funnel_drops(leads, period_type=period_type, anchor=anchor))
        if not diagnosis_type or diagnosis_type == "follow_up":
            items.extend(
                detect_follow_up_problems(db, org_id, leads, activity_dates=activity_dates)
            )
        if not diagnosis_type or diagnosis_type == "offer":
            items.extend(
                detect_offer_problems(db, org_id, leads, offer_given_dates=offer_given_dates)
            )
    except Exception:
        logger.exception("diagnosis_compute_failed org_id=%s", org_id)
        raise

    if severity:
        items = [d for d in items if d.severity == severity]

    for item in items:
        enrich_diagnosis_de2(
            db,
            org_id,
            leads,
            item,
            activity_dates=activity_dates,
            offer_given_dates=offer_given_dates,
        )

    duration_ms = int((time.perf_counter() - started) * 1000)
    return {
        "generated_at": local_now().isoformat(),
        "duration_ms": duration_ms,
        "period_type": period_type,
        "anchor": anchor.isoformat(),
        "items": [item.to_dict() for item in items],
    }
