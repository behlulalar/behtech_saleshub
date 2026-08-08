"""Aggregate org context for owner priorities (minimal PII)."""

from sqlalchemy.orm import Session

from dashboard import build_dashboard, INACTIVE_STATUSES
from database import Lead
from intelligence.analytics_engine import compute_kpis


def build_org_snapshot(db: Session, org_id: int, *, include_revenue: bool = True) -> dict:
    dash = build_dashboard(db, org_id)
    kpis = compute_kpis(db, org_id, period_type="weekly", include_revenue=include_revenue)

    active = (
        db.query(Lead)
        .filter(Lead.user_id == org_id, Lead.durum.notin_(INACTIVE_STATUSES))
        .count()
    )

    return {
        "active_leads": active,
        "dashboard_summary": {
            "toplam": dash.get("toplam_kayit", 0),
            "aktif": dash.get("aktif_takip", 0),
            "bugunku_gorev_sayisi": dash.get("bugunku_gorevler", 0),
            "cevap_bekleyen": dash.get("cevap_bekleyen_sayisi", 0),
        },
        "weekly_kpis": kpis.get("period", {}),
    }
