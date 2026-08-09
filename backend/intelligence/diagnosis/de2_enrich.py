"""DE-2 enrichment for diagnosis results (priority + impact)."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app_timezone import local_today
from database import Lead
from intelligence.diagnosis.affected import (
    collect_follow_up_affected,
    collect_offer_affected_for_priority,
)
from intelligence.diagnosis.impact import compute_impact, empty_impact
from intelligence.diagnosis.models import DiagnosisResult
from intelligence.diagnosis.priority import build_priority_rows, top_priority_leads


def enrich_diagnosis_de2(
    db: Session,
    org_id: int,
    leads: list[Lead],
    item: DiagnosisResult,
    *,
    activity_dates: dict[int, date],
    offer_given_dates: dict[int, date],
) -> None:
    if item.type == "funnel_drop":
        item.affected_leads_available = False
        item.impact = empty_impact()
        item.top_priority_leads = []
        return

    if item.type == "follow_up":
        candidates = collect_follow_up_affected(
            db,
            org_id,
            leads,
            activity_dates=activity_dates,
            today=local_today(),
        )
    elif item.type == "offer":
        candidates = collect_offer_affected_for_priority(
            db,
            org_id,
            leads,
            offer_given_dates=offer_given_dates,
            today=local_today(),
        )
    else:
        item.affected_leads_available = False
        item.impact = empty_impact()
        item.top_priority_leads = []
        return

    item.affected_leads_available = True
    all_rows = build_priority_rows(
        db,
        org_id,
        candidates,
        diagnosis_type=item.type,
        diagnosis_severity=item.severity,
        activity_dates=activity_dates,
    )
    item.impact = compute_impact(all_rows)
    item.top_priority_leads = top_priority_leads(all_rows)
