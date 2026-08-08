"""Batch intelligence refresh for one org (no LLM required)."""

from sqlalchemy.orm import Session

from app_timezone import local_now
from database import Lead
from intelligence.business_events import emit_business_event
from intelligence.insights import org_insights_deterministic, persist_insights
from intelligence.scoring import score_lead


def run_batch_score_leads(db: Session, org_id: int) -> dict:
    today = local_now().date()
    leads = db.query(Lead).filter(Lead.user_id == org_id).order_by(Lead.id.asc()).all()
    updated = 0
    now = local_now()
    for lead in leads:
        score, _reasons, _action = score_lead(db, org_id, lead, today=today)
        lead.intelligence_score = score
        lead.intelligence_updated_at = now
        updated += 1

    org_items = org_insights_deterministic(db, org_id)
    insight_count = 0
    if org_items:
        saved = persist_insights(db, org_id, entity_type="org", entity_id=None, items=org_items)
        insight_count = len(saved)

    emit_business_event(
        db,
        org_id,
        "BatchScoreCompleted",
        payload={"leads_scored": updated, "org_insights": insight_count},
    )

    from intelligence.company_profile import compute_company_profile, persist_org_profile

    profile = compute_company_profile(db, org_id)
    persist_org_profile(db, org_id, profile)

    return {
        "leads_scored": updated,
        "org_insights_persisted": insight_count,
        "org_id": org_id,
    }
