"""Recommendation ledger + priority bundle."""

import json
from datetime import timedelta

from sqlalchemy.orm import Session

from app_timezone import local_now
from database import AiRun, IntelligenceRecommendation, Lead
from intelligence.scoring import rank_leads_for_org

CACHE_TTL_HOURS = 12


def _dump(data) -> str:
    return json.dumps(data, ensure_ascii=False)


def _row_to_item(row: IntelligenceRecommendation, lead: Lead | None) -> dict:
    try:
        reasons = json.loads(row.reasons_json or "[]")
    except json.JSONDecodeError:
        reasons = []
    return {
        "lead_id": row.lead_id,
        "isletme_adi": lead.isletme_adi if lead else "",
        "category_label": lead.category if lead else None,
        "durum": lead.durum if lead else None,
        "score": row.score,
        "priority": row.priority,
        "action_type": row.action_type,
        "reasons": reasons if isinstance(reasons, list) else [],
        "insight_ids": [],
    }


def load_cached_priorities(
    db: Session,
    org_id: int,
    *,
    limit: int = 10,
    max_age_hours: int = CACHE_TTL_HOURS,
) -> tuple[list[dict], int] | None:
    cutoff = local_now() - timedelta(hours=max_age_hours)
    latest_run = (
        db.query(AiRun)
        .filter(
            AiRun.user_id == org_id,
            AiRun.run_type == "priorities",
            AiRun.status == "success",
            AiRun.created_at >= cutoff,
        )
        .order_by(AiRun.created_at.desc())
        .first()
    )
    if not latest_run:
        return None

    rows = (
        db.query(IntelligenceRecommendation)
        .filter(
            IntelligenceRecommendation.user_id == org_id,
            IntelligenceRecommendation.ai_run_id == latest_run.id,
        )
        .order_by(IntelligenceRecommendation.score.desc(), IntelligenceRecommendation.lead_id.asc())
        .limit(limit)
        .all()
    )
    if not rows:
        return None

    items: list[dict] = []
    for row in rows:
        lead = db.query(Lead).filter(Lead.id == row.lead_id, Lead.user_id == org_id).first()
        item = _row_to_item(row, lead)
        if lead:
            from database import CategoryModel

            cat = (
                db.query(CategoryModel)
                .filter(CategoryModel.user_id == org_id, CategoryModel.id == lead.category)
                .first()
            )
            if cat:
                item["category_label"] = cat.label
        items.append(item)

    return items, latest_run.id


def record_recommendations(
    db: Session,
    org_id: int,
    items: list[dict],
    *,
    ai_run_id: int | None = None,
) -> list[IntelligenceRecommendation]:
    rows: list[IntelligenceRecommendation] = []
    for item in items:
        row = IntelligenceRecommendation(
            user_id=org_id,
            lead_id=item["lead_id"],
            action_type=item["action_type"],
            priority=item.get("priority", "medium"),
            score=int(item.get("score") or 0),
            reasons_json=_dump(item.get("reasons") or []),
            insight_ids_json=_dump(item.get("insight_ids") or []),
            ai_run_id=ai_run_id,
            user_action="pending",
        )
        db.add(row)
        rows.append(row)
    db.flush()
    return rows


def update_lead_scores(db: Session, org_id: int, items: list[dict]) -> None:
    now = local_now()
    for item in items:
        lead = db.query(Lead).filter(Lead.id == item["lead_id"], Lead.user_id == org_id).first()
        if lead:
            lead.intelligence_score = int(item.get("score") or 0)
            lead.intelligence_updated_at = now


def build_priority_recommendations(db: Session, org_id: int, *, limit: int = 10) -> list[dict]:
    return rank_leads_for_org(db, org_id, limit=limit)
