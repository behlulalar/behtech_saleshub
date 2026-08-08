"""Company Intelligence v1 — structured org profile (deterministic)."""

import json
from collections import defaultdict

from sqlalchemy.orm import Session

from app_timezone import local_now
from dashboard import build_dashboard
from database import Lead, OrgIntelligenceProfile
from intelligence.analytics_engine import compute_kpis
from intelligence.insights import insight_to_dict, list_active_insights

PROFILE_VERSION = "v1"

SOURCE_LABELS = {
    "manual": "Manuel",
    "import": "Excel içe aktarma",
    "discovery": "Keşif",
    "request": "Talep",
}


def _dump(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def _load(row: OrgIntelligenceProfile | None) -> dict | None:
    if not row:
        return None
    try:
        data = json.loads(row.profile_json or "{}")
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _best_lead_source(leads: list[Lead]) -> dict | None:
    wins: dict[str, int] = defaultdict(int)
    totals: dict[str, int] = defaultdict(int)
    for lead in leads:
        key = (lead.source or "manual").strip() or "manual"
        totals[key] += 1
        durum = (lead.durum or "").lower()
        if durum in {"müşteri", "musteri"}:
            wins[key] += 1

    best_key = None
    best_rate = -1.0
    for key, total in totals.items():
        if total < 3:
            continue
        rate = wins[key] / total
        if rate > best_rate:
            best_rate = rate
            best_key = key
    if not best_key:
        return None
    return {
        "source": best_key,
        "label": SOURCE_LABELS.get(best_key, best_key),
        "win_rate_pct": round(best_rate * 100, 1),
        "sample_size": totals[best_key],
    }


def compute_company_profile(db: Session, org_id: int, *, include_revenue: bool = True) -> dict:
    kpis = compute_kpis(db, org_id, period_type="monthly", include_revenue=include_revenue)
    dashboard = build_dashboard(db, org_id)
    leads = db.query(Lead).filter(Lead.user_id == org_id).all()

    lost = sum(1 for l in leads if (l.durum or "").lower() in {"olumsuz", "cevap yok"})
    active_insights = list_active_insights(db, org_id, limit=5)
    insight_snippets = [
        {"title": insight_to_dict(row)["title"], "severity": row.severity}
        for row in active_insights[:3]
    ]

    period = kpis.get("period") or {}
    return {
        "version": PROFILE_VERSION,
        "computed_at": local_now().isoformat(),
        "period_label": period.get("label"),
        "yeni_kayit": period.get("yeni_kayit"),
        "yeni_musteri": period.get("yeni_musteri"),
        "satis_donusum_orani": period.get("satis_donusum_orani"),
        "pipeline_conversion": (kpis.get("pipeline") or {}).get("satis_donusum_orani"),
        "cevap_bekleyen_sayisi": int(dashboard.get("cevap_bekleyen_sayisi") or 0),
        "bugunku_gorevler": int(dashboard.get("bugunku_gorevler") or 0),
        "best_lead_source": _best_lead_source(leads),
        "lost_or_stalled_leads": lost,
        "top_insights": insight_snippets,
        "total_leads": len(leads),
    }


def persist_org_profile(db: Session, org_id: int, profile: dict) -> OrgIntelligenceProfile:
    row = db.query(OrgIntelligenceProfile).filter(OrgIntelligenceProfile.user_id == org_id).first()
    now = local_now()
    if not row:
        row = OrgIntelligenceProfile(user_id=org_id, profile_json=_dump(profile), computed_at=now)
        db.add(row)
    else:
        row.profile_json = _dump(profile)
        row.computed_at = now
        row.version = PROFILE_VERSION
    db.flush()
    return row


def get_org_profile(
    db: Session,
    org_id: int,
    *,
    refresh: bool = False,
    include_revenue: bool = True,
) -> dict:
    row = db.query(OrgIntelligenceProfile).filter(OrgIntelligenceProfile.user_id == org_id).first()
    if row and not refresh:
        cached = _load(row)
        if cached:
            cached["computed_at"] = row.computed_at.isoformat() if row.computed_at else cached.get("computed_at")
            return cached

    profile = compute_company_profile(db, org_id, include_revenue=include_revenue)
    persist_org_profile(db, org_id, profile)
    return profile


def refresh_all_org_profiles(db: Session) -> int:
    from database import User
    from roles import ROLE_OWNER

    owners = db.query(User).filter(User.role == ROLE_OWNER, User.owner_id.is_(None)).all()
    count = 0
    for owner in owners:
        include_revenue = (owner.account_type or "company") == "company"
        profile = compute_company_profile(db, owner.id, include_revenue=include_revenue)
        persist_org_profile(db, owner.id, profile)
        count += 1
    return count
