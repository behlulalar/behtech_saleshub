"""Emit business events for outcome tracking (Faz 3)."""

import json
from typing import Any

from sqlalchemy.orm import Session

from app_timezone import local_now
from database import BusinessEvent

STAGE_CHANGED = "StageChanged"
LEAD_CREATED = "LeadCreated"
LEAD_WON = "LeadWon"
LEAD_LOST = "LeadLost"
TASK_COMPLETED = "TaskCompleted"
OFFER_SENT = "OfferSent"
RECOMMENDATION_ACCEPTED = "RecommendationAccepted"


def _dump(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def emit_business_event(
    db: Session,
    org_id: int,
    event_type: str,
    *,
    lead_id: int | None = None,
    payload: dict | None = None,
) -> BusinessEvent:
    row = BusinessEvent(
        user_id=org_id,
        event_type=event_type,
        lead_id=lead_id,
        payload_json=_dump(payload or {}),
        occurred_at=local_now(),
    )
    db.add(row)
    return row


def map_durum_to_event(old_durum: str | None, new_durum: str | None) -> str | None:
    if (old_durum or "").strip() == (new_durum or "").strip():
        return None
    new = (new_durum or "").lower()
    if new in {"müşteri", "musteri"}:
        return LEAD_WON
    if new in {"olumsuz", "cevap yok"}:
        return LEAD_LOST
    return STAGE_CHANGED


def stage_changed_payload(old_durum: str | None, new_durum: str | None) -> dict:
    return {"from": old_durum or "", "to": new_durum or ""}


def emit_stage_change_if_needed(
    db: Session,
    org_id: int,
    lead_id: int,
    old_durum: str | None,
    new_durum: str | None,
) -> BusinessEvent | None:
    event_type = map_durum_to_event(old_durum, new_durum)
    if not event_type:
        return None
    payload: dict[str, Any] = stage_changed_payload(old_durum, new_durum)
    return emit_business_event(db, org_id, event_type, lead_id=lead_id, payload=payload)
