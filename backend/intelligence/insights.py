"""Deterministic + persisted insights."""

import json
from datetime import timedelta

from sqlalchemy.orm import Session

from app_timezone import local_now
from config import settings
from dashboard import INACTIVE_STATUSES, get_category_map
from database import IntelligenceInsight, Lead
from intelligence.scoring import score_lead
from reminders import build_followup_reminders


def _dump(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def lead_insights_deterministic(db: Session, org_id: int, lead_id: int) -> list[dict]:
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.user_id == org_id).first()
    if not lead:
        return []

    items: list[dict] = []
    score, reasons, action = score_lead(db, org_id, lead)
    if score >= 45:
        items.append(
            {
                "insight_type": "priority_signal",
                "severity": "high" if score >= 70 else "medium",
                "title": "Takip önceliği yüksek",
                "summary": "; ".join(reasons[:3]),
                "evidence": {"score": score, "action_type": action},
            }
        )

    if lead.durum and lead.durum not in INACTIVE_STATUSES and lead.durum == "Yeni":
        items.append(
            {
                "insight_type": "new_lead",
                "severity": "medium",
                "title": "Yeni lead",
                "summary": f"{lead.isletme_adi} henüz ilk temas aşamasında.",
                "evidence": {"durum": lead.durum},
            }
        )

    return items


def org_insights_deterministic(db: Session, org_id: int) -> list[dict]:
    leads = db.query(Lead).filter(Lead.user_id == org_id).all()
    cat_map = get_category_map(db, org_id)
    followup = build_followup_reminders(db, org_id, leads, cat_map)
    waiting = followup.get("cevap_bekleyen_liste") or []
    if waiting:
        count = len(waiting)
        return [
            {
                "insight_type": "org_followup_backlog",
                "severity": "high" if count >= 5 else "medium",
                "title": "Cevap bekleyen lead'ler",
                "summary": f"{count} lead için takip eşiği ({settings.followup_reminder_days} gün) aşıldı.",
                "evidence": {"count": count},
            }
        ]
    return []


def persist_insights(
    db: Session,
    org_id: int,
    *,
    entity_type: str,
    entity_id: int | None,
    items: list[dict],
    source: str = "deterministic",
) -> list[IntelligenceInsight]:
    expires = local_now() + timedelta(days=7)
    saved: list[IntelligenceInsight] = []
    for item in items:
        row = IntelligenceInsight(
            user_id=org_id,
            insight_type=item["insight_type"],
            severity=item.get("severity", "medium"),
            entity_type=entity_type,
            entity_id=entity_id,
            title=item["title"],
            summary=item.get("summary", ""),
            evidence_json=_dump(item.get("evidence") or {}),
            source=source,
            expires_at=expires,
        )
        db.add(row)
        saved.append(row)
    db.flush()
    return saved


def list_active_insights(db: Session, org_id: int, *, limit: int = 20) -> list[IntelligenceInsight]:
    now = local_now()
    return (
        db.query(IntelligenceInsight)
        .filter(
            IntelligenceInsight.user_id == org_id,
            (IntelligenceInsight.expires_at.is_(None)) | (IntelligenceInsight.expires_at > now),
        )
        .order_by(IntelligenceInsight.created_at.desc())
        .limit(limit)
        .all()
    )


def insight_to_dict(row: IntelligenceInsight) -> dict:
    try:
        evidence = json.loads(row.evidence_json or "{}")
    except json.JSONDecodeError:
        evidence = {}
    return {
        "id": row.id,
        "insight_type": row.insight_type,
        "severity": row.severity,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "title": row.title,
        "summary": row.summary,
        "evidence": evidence,
        "source": row.source,
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }
