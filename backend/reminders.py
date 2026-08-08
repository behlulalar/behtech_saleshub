from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from config import settings
from database import Lead, LeadActivity

RESPONSE_WAITING_STATUSES = {
    "İletişime Geçildi",
    "Takip Bekliyor",
    "Demo Gönderildi",
    "Görüşme Planlandı",
    "Teklif Verildi",
}


def parse_date(value: str) -> date | None:
    if not value or not value.strip():
        return None
    try:
        from datetime import datetime

        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def get_last_activity_dates(db: Session, user_id: int, lead_ids: list[int]) -> dict[int, date]:
    if not lead_ids:
        return {}

    rows = (
        db.query(LeadActivity.lead_id, func.max(LeadActivity.activity_date))
        .filter(LeadActivity.user_id == user_id, LeadActivity.lead_id.in_(lead_ids))
        .group_by(LeadActivity.lead_id)
        .all()
    )
    return {lead_id: activity_date.date() for lead_id, activity_date in rows}


def get_last_contact_date(lead: Lead, activity_dates: dict[int, date]) -> date | None:
    candidates: list[date] = []

    for value in (lead.ilk_mesaj_tarihi, lead.demo_tarihi, lead.gorusme_tarihi):
        parsed = parse_date(value)
        if parsed:
            candidates.append(parsed)

    if lead.id in activity_dates:
        candidates.append(activity_dates[lead.id])

    if not candidates and lead.created_at:
        candidates.append(lead.created_at.date())

    return max(candidates) if candidates else None


def build_followup_reminders(
    db: Session,
    user_id: int,
    leads: list[Lead],
    cat_map: dict[str, str],
    *,
    threshold_days: int | None = None,
) -> dict:
    threshold = threshold_days or settings.followup_reminder_days
    today = date.today()
    lead_ids = [lead.id for lead in leads if lead.durum in RESPONSE_WAITING_STATUSES]
    activity_dates = get_last_activity_dates(db, user_id, lead_ids)

    reminders: list[dict] = []

    for lead in leads:
        if lead.durum not in RESPONSE_WAITING_STATUSES:
            continue

        last_contact = get_last_contact_date(lead, activity_dates)
        if not last_contact:
            continue

        days_waiting = (today - last_contact).days
        if days_waiting < threshold:
            continue

        detail_parts = []
        if lead.yetkili:
            detail_parts.append(lead.yetkili)
        if lead.ilk_iletisim_kanali:
            detail_parts.append(lead.ilk_iletisim_kanali)

        reminders.append(
            {
                "id": lead.id,
                "isletme_adi": lead.isletme_adi,
                "category": lead.category,
                "category_label": cat_map.get(lead.category, lead.category),
                "date": last_contact.isoformat(),
                "durum": lead.durum,
                "detail": " · ".join(detail_parts),
                "last_contact_date": last_contact.isoformat(),
                "days_waiting": days_waiting,
            }
        )

    reminders.sort(key=lambda item: item["days_waiting"], reverse=True)

    return {
        "cevap_bekleyen_sayisi": len(reminders),
        "cevap_bekleyen_gun": threshold,
        "cevap_bekleyen_liste": reminders[:20],
    }
