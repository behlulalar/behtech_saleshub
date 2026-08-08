import time

from sqlalchemy.orm import Session

from database import User
from ai.store import create_run, finish_run_success
from intelligence.insights import org_insights_deterministic, persist_insights
from intelligence.recommendations import (
    build_priority_recommendations,
    load_cached_priorities,
    record_recommendations,
    update_lead_scores,
)

MAX_LIMIT = 10


def run_priorities(
    db: Session,
    *,
    user: User,
    org_id: int,
    limit: int = 10,
    refresh: bool = False,
) -> tuple[list[dict], int | None, bool]:
    limit = max(1, min(limit, MAX_LIMIT))

    if not refresh:
        cached = load_cached_priorities(db, org_id, limit=limit)
        if cached:
            items, run_id = cached
            return items, run_id, True

    items = build_priority_recommendations(db, org_id, limit=limit)

    org_items = org_insights_deterministic(db, org_id)
    if org_items:
        persist_insights(db, org_id, entity_type="org", entity_id=None, items=org_items)

    run = create_run(
        db,
        org_id=org_id,
        requested_by=user.id,
        run_type="priorities",
        input_data={"limit": limit, "refresh": refresh},
        provider="heuristic",
        model="scoring_v0",
        prompt_version="priorities_v0_heuristic",
    )
    started = time.perf_counter()

    recommendations = []
    for item in items:
        recommendations.append(
            {
                "lead_id": item["lead_id"],
                "isletme_adi": item["isletme_adi"],
                "category_label": item.get("category_label"),
                "durum": item.get("durum"),
                "score": item["score"],
                "priority": item["priority"],
                "action_type": item["action_type"],
                "reasons": item["reasons"],
                "insight_ids": [],
            }
        )

    if recommendations:
        record_recommendations(db, org_id, recommendations, ai_run_id=run.id)
        update_lead_scores(db, org_id, recommendations)

    duration_ms = int((time.perf_counter() - started) * 1000)
    finish_run_success(
        db,
        run,
        output_data={"count": len(recommendations)},
        tokens_prompt=0,
        tokens_completion=0,
        tokens_total=0,
        duration_ms=duration_ms,
    )
    db.commit()
    db.refresh(run)
    return recommendations, run.id, False
