"""Diagnosis Engine orchestrator (read-only, deterministic)."""

from __future__ import annotations

import logging
import time
from datetime import date

from sqlalchemy.orm import Session

from app_timezone import local_now, local_today
from database import Lead
from intelligence.diagnosis.models import DiagnosisResult
from intelligence.diagnosis.rules import detect_follow_up_problems, detect_funnel_drops, detect_offer_problems

logger = logging.getLogger("behtech.diagnosis")


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
    items: list[DiagnosisResult] = []

    try:
        if not diagnosis_type or diagnosis_type == "funnel_drop":
            items.extend(detect_funnel_drops(leads, period_type=period_type, anchor=anchor))
        if not diagnosis_type or diagnosis_type == "follow_up":
            items.extend(detect_follow_up_problems(db, org_id, leads))
        if not diagnosis_type or diagnosis_type == "offer":
            items.extend(detect_offer_problems(db, org_id, leads))
    except Exception:
        logger.exception("diagnosis_compute_failed org_id=%s", org_id)
        raise

    if severity:
        items = [d for d in items if d.severity == severity]

    duration_ms = int((time.perf_counter() - started) * 1000)
    return {
        "generated_at": local_now().isoformat(),
        "duration_ms": duration_ms,
        "period_type": period_type,
        "anchor": anchor.isoformat(),
        "items": [item.to_dict() for item in items],
    }
