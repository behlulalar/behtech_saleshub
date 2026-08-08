"""Period bounds and funnel metrics — reuses report/funnel helpers."""

from __future__ import annotations

from datetime import date, timedelta

from funnel import build_sales_funnel
from reports import _format_period_label, _lead_created_in_range, _month_bounds, _week_bounds


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
