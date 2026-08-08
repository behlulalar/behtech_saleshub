"""Deterministic KPI bundle — single source for intelligence + future AI context."""

from datetime import date

from sqlalchemy.orm import Session

from analytics import build_analytics
from app_timezone import local_now
from reports import build_period_report, parse_report_anchor


def compute_kpis(
    db: Session,
    org_id: int,
    *,
    period_type: str = "monthly",
    anchor: date | None = None,
    include_revenue: bool = True,
) -> dict:
    """
    Wraps existing report/analytics logic without changing legacy endpoints.
    """
    if period_type not in ("daily", "weekly", "monthly"):
        period_type = "monthly"

    if anchor is None:
        if period_type == "monthly":
            anchor = parse_report_anchor("monthly", None, local_now().strftime("%Y-%m"))
        elif period_type == "weekly":
            anchor = parse_report_anchor("weekly", local_now().date().isoformat(), None)
        else:
            anchor = local_now().date()

    period_report = build_period_report(
        db,
        org_id,
        period_type,
        anchor,
        include_revenue=include_revenue,
    )
    analytics = build_analytics(db, org_id)
    funnel_stages = analytics.get("donusum_oranlari") or analytics.get("satis_hunisi") or []

    return {
        "computed_at": local_now().isoformat(),
        "period_type": period_type,
        "period": {
            "label": period_report["period_label"],
            "start": period_report["period_start"],
            "end": period_report["period_end"],
            "yeni_kayit": period_report["yeni_kayit"],
            "yeni_musteri": period_report["yeni_musteri"],
            "donusum_orani": period_report["donusum_orani"],
            "satis_donusum_orani": period_report["satis_donusum_orani"],
            "satis_sayisi": period_report.get("satis_sayisi"),
            "toplam_gelir": period_report.get("toplam_gelir"),
        },
        "pipeline": {
            "satis_donusum_orani": analytics.get("satis_donusum_orani"),
            "funnel_stage_count": len(funnel_stages),
        },
        "funnel_stages": period_report.get("satis_hunisi") or analytics.get("satis_hunisi") or [],
    }
