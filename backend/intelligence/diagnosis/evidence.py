"""Period bounds and funnel metrics — reuses report/funnel helpers."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import LeadActivity
from funnel import build_sales_funnel
from reports import _format_period_label, _lead_created_in_range, _month_bounds, _week_bounds

RELIABLE_OFFER_ACTIVITY_TYPE = "teklif_verildi"


def comparison_period_bounds(period_type: str, anchor: date) -> tuple[date, date, date, date]:
    """Current and previous period of equal length (Europe/Istanbul calendar via anchor date)."""
    if period_type == "daily":
        start = end = anchor
        prev_start = prev_end = anchor - timedelta(days=1)
        return start, end, prev_start, prev_end

    if period_type == "monthly":
        start, end = _month_bounds(anchor.year, anchor.month)
        prev_month = anchor.month - 1 or 12
        prev_year = anchor.year if anchor.month > 1 else anchor.year - 1
        prev_start, prev_end = _month_bounds(prev_year, prev_month)
        return start, end, prev_start, prev_end

    start, end = _week_bounds(anchor)
    prev_start = start - timedelta(days=7)
    prev_end = end - timedelta(days=7)
    return start, end, prev_start, prev_end


def period_label(period_type: str, start: date, end: date) -> str:
    return _format_period_label(period_type, start, end)


def cohort_leads_in_range(leads: list, start: date, end: date) -> list:
    return [lead for lead in leads if _lead_created_in_range(lead, start, end)]


def funnel_transition_rate(leads: list, from_stage: str, to_stage: str) -> tuple[float | None, int, int]:
    """
    Conversion rate from ``from_stage`` count to ``to_stage`` count on the same cohort.
    Matches ``build_sales_funnel`` stage-to-stage semantics.
    """
    funnel = build_sales_funnel(leads)
    by_key = {stage["key"]: stage for stage in funnel.get("satis_hunisi") or []}
    if from_stage not in by_key or to_stage not in by_key:
        return None, 0, 0
    from_count = int(by_key[from_stage]["count"] or 0)
    to_count = int(by_key[to_stage]["count"] or 0)
    if from_count <= 0:
        return None, from_count, to_count
    rate = round((to_count / from_count) * 100, 1)
    return rate, from_count, to_count


def get_reliable_offer_given_dates(db: Session, org_id: int, lead_ids: list[int]) -> dict[int, date]:
    """
    First ``teklif_verildi`` activity date per lead — güvenilir teklif veriliş zamanı.
    Lead modelinde ayrı teklif tarihi alanı yok; yalnızca bu aktivite tipi kullanılır.
    """
    if not lead_ids:
        return {}

    rows = (
        db.query(LeadActivity.lead_id, func.min(LeadActivity.activity_date))
        .filter(
            LeadActivity.user_id == org_id,
            LeadActivity.lead_id.in_(lead_ids),
            LeadActivity.activity_type == RELIABLE_OFFER_ACTIVITY_TYPE,
        )
        .group_by(LeadActivity.lead_id)
        .all()
    )
    return {lead_id: activity_date.date() for lead_id, activity_date in rows if activity_date}
