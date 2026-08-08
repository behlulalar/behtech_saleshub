"""CRM side effects when an action proposal is approved (Faz 6)."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from activities import log_activity
from app_timezone import local_today
from dashboard import parse_date
from database import Lead

ACTION_LABELS_TR: dict[str, str] = {
    "follow_up": "Takip",
    "call_or_message": "Arama / mesaj",
    "intro_message": "İlk mesaj",
    "prepare_meeting": "Görüşme hazırlığı",
    "demo_follow_up": "Demo takibi",
}


def _first_free_takip_slot(lead: Lead, iso_date: str) -> str | None:
    if not (lead.takip_1 or "").strip():
        lead.takip_1 = iso_date
        return "takip_1"
    if not (lead.takip_2 or "").strip():
        lead.takip_2 = iso_date
        return "takip_2"
    existing = parse_date(lead.takip_2 or "")
    today = local_today()
    if existing and existing >= today:
        return None
    lead.takip_2 = iso_date
    return "takip_2"


def apply_accept_recommendation_effects(
    db: Session,
    org_id: int,
    lead: Lead,
    *,
    action_type: str,
    actor_user_id: int,
) -> str:
    """
    Schedule follow-up fields on the lead. Returns a short Turkish summary for UI/logs.
    """
    if lead.user_id != org_id:
        raise ValueError("lead_org_mismatch")

    today = local_today()
    today_iso = today.isoformat()
    action = (action_type or "follow_up").strip() or "follow_up"
    label = ACTION_LABELS_TR.get(action, action)

    effect = ""

    if action == "prepare_meeting":
        gorusme = parse_date(lead.gorusme_tarihi or "")
        if gorusme is None or gorusme < today:
            lead.gorusme_tarihi = (today + timedelta(days=1)).isoformat()
            if (lead.durum or "") in {"", "Yeni", "İlk Mesaj Gönderildi", "Cevap Bekleniyor"}:
                lead.durum = "Görüşme Planlandı"
            effect = "Yarın için görüşme tarihi planlandı"
            log_activity(
                db,
                user_id=actor_user_id,
                lead_id=lead.id,
                activity_type="gorusme_planlandi",
                title="AI önerisi onaylandı",
                description=f"{label}: {effect}",
            )
        else:
            effect = "Mevcut görüşme tarihi korundu"
            log_activity(
                db,
                user_id=actor_user_id,
                lead_id=lead.id,
                activity_type="diger",
                title="AI önerisi onaylandı",
                description=f"{label}: {effect}",
            )

    elif action == "demo_follow_up":
        slot = _first_free_takip_slot(lead, today_iso)
        if slot:
            effect = "Bugün için demo takip görevi planlandı"
            log_activity(
                db,
                user_id=actor_user_id,
                lead_id=lead.id,
                activity_type="takip_yapildi",
                title="AI önerisi onaylandı",
                description=f"{label}: {effect} ({slot})",
            )
        else:
            effect = "Takip alanları dolu — manuel planlayın"
            log_activity(
                db,
                user_id=actor_user_id,
                lead_id=lead.id,
                activity_type="diger",
                title="AI önerisi onaylandı",
                description=f"{label}: {effect}",
            )

    else:
        slot = _first_free_takip_slot(lead, today_iso)
        if slot:
            effect = "Bugün için takip görevi planlandı"
            log_activity(
                db,
                user_id=actor_user_id,
                lead_id=lead.id,
                activity_type="takip_yapildi",
                title="AI önerisi onaylandı",
                description=f"{label}: {effect} ({slot})",
            )
        else:
            effect = "Takip alanları dolu — manuel planlayın"
            log_activity(
                db,
                user_id=actor_user_id,
                lead_id=lead.id,
                activity_type="diger",
                title="AI önerisi onaylandı",
                description=f"{label}: {effect}",
            )

    db.flush()
    return effect
