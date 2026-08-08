"""Prediction v0 — rule-based lead priority scores (no ML)."""

from datetime import date

from sqlalchemy.orm import Session

from app_timezone import local_today
from config import settings
from dashboard import INACTIVE_STATUSES, parse_date
from database import Lead
from reminders import RESPONSE_WAITING_STATUSES, get_last_activity_dates, get_last_contact_date


def _priority_weight(oncelik: str) -> int:
    key = (oncelik or "orta").lower()
    if key == "yuksek":
        return 25
    if key == "dusuk":
        return 0
    return 10


def score_lead(
    db: Session,
    org_id: int,
    lead: Lead,
    *,
    today: date | None = None,
    activity_dates: dict[int, date] | None = None,
) -> tuple[int, list[str], str]:
    """
    Returns (score 0-100, reason strings, suggested action_type).
    """
    today = today or local_today()
    reasons: list[str] = []
    score = 0
    action = "follow_up"

    if lead.durum in INACTIVE_STATUSES or (lead.durum or "").lower() in {"müşteri", "musteri"}:
        return 0, ["Pasif veya kapanmış lead"], "none"

    score += _priority_weight(lead.oncelik)
    if lead.oncelik == "yuksek":
        reasons.append("Öncelik: yüksek")

    activity_dates = activity_dates if activity_dates is not None else get_last_activity_dates(db, org_id, [lead.id])
    last_contact = get_last_contact_date(lead, activity_dates)
    if last_contact:
        days_idle = (today - last_contact).days
        if days_idle >= settings.followup_reminder_days:
            score += min(40, 10 + days_idle * 3)
            reasons.append(f"{days_idle} gündür iletişim yok")
            action = "call_or_message"
        elif days_idle >= 2:
            score += 8
            reasons.append(f"Son temas {days_idle} gün önce")
    else:
        score += 15
        reasons.append("Henüz kayıtlı iletişim tarihi yok")
        action = "intro_message"

    durum = lead.durum or ""
    if durum in RESPONSE_WAITING_STATUSES:
        score += 12
        reasons.append(f"Durum: {durum}")

    gorusme = parse_date(lead.gorusme_tarihi or "")
    if gorusme and 0 <= (gorusme - today).days <= settings.meeting_reminder_days:
        score += 20
        reasons.append("Yaklaşan görüşme")
        action = "prepare_meeting"

    demo = parse_date(lead.demo_tarihi or "")
    if demo == today:
        score += 18
        reasons.append("Demo bugün")
        action = "demo_follow_up"

    if lead.demo_gonderildi and durum == "Demo Gönderildi":
        score += 10
        reasons.append("Demo gönderildi — geri bildirim bekle")
        action = "demo_follow_up"

    if durum == "Yeni":
        score += 14
        reasons.append("Yeni lead")
        action = "intro_message"

    score = max(0, min(100, score))
    if not reasons:
        reasons.append("Genel takip önerilir")
    return score, reasons, action


def rank_leads_for_org(db: Session, org_id: int, *, limit: int = 10) -> list[dict]:
    leads = (
        db.query(Lead)
        .filter(Lead.user_id == org_id)
        .order_by(Lead.id.asc())
        .all()
    )
    cat_map: dict[str, str] = {}
    from database import CategoryModel

    for row in db.query(CategoryModel).filter(CategoryModel.user_id == org_id).all():
        cat_map[row.id] = row.label

    lead_ids = [lead.id for lead in leads]
    activity_dates = get_last_activity_dates(db, org_id, lead_ids)

    scored: list[dict] = []
    for lead in leads:
        score, reasons, action = score_lead(db, org_id, lead, activity_dates=activity_dates)
        if score <= 0 or action == "none":
            continue
        scored.append(
            {
                "lead_id": lead.id,
                "isletme_adi": lead.isletme_adi,
                "category": lead.category,
                "category_label": cat_map.get(lead.category, lead.category),
                "durum": lead.durum,
                "oncelik": lead.oncelik,
                "score": score,
                "reasons": reasons,
                "action_type": action,
                "priority": "high" if score >= 70 else ("medium" if score >= 45 else "low"),
            }
        )

    scored.sort(key=lambda x: (-x["score"], x["lead_id"]))
    return scored[:limit]
