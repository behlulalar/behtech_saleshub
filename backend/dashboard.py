from datetime import date, timedelta

from sqlalchemy.orm import Session

from app_timezone import local_today
from config import settings
from database import CategoryModel, Lead
from reminders import build_followup_reminders

INACTIVE_STATUSES = {"Olumsuz", "Cevap Yok", "Müşteri"}
TASK_STATUSES = {"Takip Bekliyor", "Görüşme Planlandı", "Demo Gönderildi", "Teklif Verildi"}


def parse_date(value: str) -> date | None:
    if not value or not value.strip():
        return None
    try:
        from datetime import datetime

        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def get_category_map(db: Session, user_id: int) -> dict[str, str]:
    cats = db.query(CategoryModel).filter(CategoryModel.user_id == user_id).all()
    return {c.id: c.label for c in cats}


def _task_item(lead: Lead, cat_label: str, *, task_type: str, type_label: str, date_value: str) -> dict:
    return {
        "id": lead.id,
        "isletme_adi": lead.isletme_adi,
        "category": lead.category,
        "category_label": cat_label,
        "type": task_type,
        "type_label": type_label,
        "date": date_value,
        "durum": lead.durum,
    }


def _build_automation_notifications(
    followup_list: list[dict],
    yaklasan_takipler: list[dict],
    today_tasks: list[dict],
) -> list[dict]:
    notifications: list[dict] = []

    for item in followup_list[:8]:
        notifications.append(
            {
                "kind": "cevap_bekliyor",
                "id": item["id"],
                "isletme_adi": item["isletme_adi"],
                "category_label": item.get("category_label", item.get("category", "")),
                "date": item.get("last_contact_date", item.get("date", "")),
                "durum": item.get("durum", ""),
                "message": f"{item['days_waiting']} gündür cevap yok — takip görevi önerildi",
                "days_until": None,
                "type": "cevap-bekliyor",
            }
        )

    for item in yaklasan_takipler:
        days = item.get("days_until")
        if days is None or days < 0 or days > settings.meeting_reminder_days:
            continue
        when = "Bugün" if days == 0 else ("Yarın" if days == 1 else f"{days} gün sonra")
        notifications.append(
            {
                "kind": "yaklasan" if days > 0 else "bugun",
                "id": item["id"],
                "isletme_adi": item["isletme_adi"],
                "category_label": item.get("category_label", item.get("category", "")),
                "date": item.get("date", ""),
                "durum": item.get("durum", ""),
                "message": f"{when} {item.get('type_label', 'Takip').lower()} — {item['isletme_adi']}",
                "days_until": days,
                "type": item.get("type"),
            }
        )

    for item in today_tasks:
        if item.get("type") == "cevap-bekliyor":
            continue
        if any(n["id"] == item["id"] and n.get("type") == item.get("type") for n in notifications):
            continue
        notifications.append(
            {
                "kind": "bugun_gorev",
                "id": item["id"],
                "isletme_adi": item["isletme_adi"],
                "category_label": item.get("category_label", item.get("category", "")),
                "date": item.get("date", ""),
                "durum": item.get("durum", ""),
                "message": f"Bugün: {item.get('type_label', 'Görev')} — {item['isletme_adi']}",
                "days_until": 0,
                "type": item.get("type"),
            }
        )

    return notifications[:15]


def build_dashboard(db: Session, user_id: int) -> dict:
    today = local_today()
    week_start = today - timedelta(days=today.weekday())

    leads = db.query(Lead).filter(Lead.user_id == user_id).all()
    cat_map = get_category_map(db, user_id)

    toplam = len(leads)
    aktif = sum(1 for l in leads if l.durum not in INACTIVE_STATUSES)
    bu_hafta = sum(1 for l in leads if l.created_at and l.created_at.date() >= week_start)

    bugunku_gorevler_liste = []
    yaklasan_takipler = []
    son_gorusmeler = []
    son_musteriler = []

    for lead in leads:
        cat_label = cat_map.get(lead.category, lead.category)
        gorusme = parse_date(lead.gorusme_tarihi)
        demo = parse_date(lead.demo_tarihi)
        takip_1 = parse_date(lead.takip_1)
        takip_2 = parse_date(lead.takip_2)

        if gorusme == today:
            bugunku_gorevler_liste.append(
                _task_item(lead, cat_label, task_type="gorusme", type_label="Görüşme", date_value=lead.gorusme_tarihi)
            )
        if demo == today:
            bugunku_gorevler_liste.append(
                _task_item(lead, cat_label, task_type="demo", type_label="Demo", date_value=lead.demo_tarihi)
            )
        for takip_date, task_type, type_label, raw_value in (
            (takip_1, "takip-1", "Takip 1", lead.takip_1),
            (takip_2, "takip-2", "Takip 2", lead.takip_2),
        ):
            if takip_date == today:
                bugunku_gorevler_liste.append(
                    _task_item(lead, cat_label, task_type=task_type, type_label=type_label, date_value=raw_value[:10])
                )
            if takip_date and takip_date > today:
                yaklasan_takipler.append({
                    **_task_item(lead, cat_label, task_type=task_type, type_label=type_label, date_value=raw_value[:10]),
                    "days_until": (takip_date - today).days,
                })

        has_scheduled_date = any(d is not None for d in (gorusme, demo, takip_1, takip_2))
        if lead.durum in TASK_STATUSES and not has_scheduled_date:
            bugunku_gorevler_liste.append(
                _task_item(lead, cat_label, task_type="takip", type_label="Takip", date_value=today.isoformat())
            )

        if gorusme and gorusme > today:
            yaklasan_takipler.append({
                **_task_item(lead, cat_label, task_type="gorusme", type_label="Görüşme", date_value=lead.gorusme_tarihi),
                "days_until": (gorusme - today).days,
            })
        if demo and demo > today:
            yaklasan_takipler.append({
                **_task_item(lead, cat_label, task_type="demo", type_label="Demo", date_value=lead.demo_tarihi),
                "days_until": (demo - today).days,
            })

        if gorusme and gorusme <= today:
            son_gorusmeler.append({
                "id": lead.id,
                "isletme_adi": lead.isletme_adi,
                "category": lead.category,
                "category_label": cat_label,
                "date": lead.gorusme_tarihi,
                "durum": lead.durum,
                "detail": lead.yetkili or lead.sehir or "",
            })

        if lead.durum == "Müşteri":
            son_musteriler.append({
                "id": lead.id,
                "isletme_adi": lead.isletme_adi,
                "category": lead.category,
                "category_label": cat_label,
                "date": lead.updated_at.isoformat()[:10] if lead.updated_at else "",
                "durum": lead.durum,
                "detail": lead.sehir or "",
            })

    followup_data = build_followup_reminders(db, user_id, leads, cat_map)

    for item in followup_data["cevap_bekleyen_liste"]:
        bugunku_gorevler_liste.append(
            {
                "id": item["id"],
                "isletme_adi": item["isletme_adi"],
                "category": item["category"],
                "category_label": item["category_label"],
                "type": "cevap-bekliyor",
                "type_label": f"Takip ({item['days_waiting']} gün)",
                "date": item.get("last_contact_date", item.get("date", "")),
                "durum": item.get("durum", ""),
                "detail": item.get("detail", ""),
                "days_waiting": item["days_waiting"],
            }
        )

    yaklasan_takipler.sort(key=lambda x: (x.get("days_until", 999), x["date"]))
    son_gorusmeler.sort(key=lambda x: x["date"], reverse=True)
    son_musteriler.sort(key=lambda x: x["date"], reverse=True)

    seen_takip = set()
    unique_bugun = []
    for item in bugunku_gorevler_liste:
        key = (item["id"], item["type"])
        if key not in seen_takip:
            seen_takip.add(key)
            unique_bugun.append(item)

    from reports import build_daily_report
    from analytics import build_daily_contact_analytics

    daily = build_daily_report(db, user_id, today, include_revenue=True)
    contact = build_daily_contact_analytics(db, user_id, today)

    return {
        "toplam_kayit": toplam,
        "aktif_takip": aktif,
        "bugunku_gorevler": len(unique_bugun),
        "bu_hafta_eklenen": bu_hafta,
        "bugunku_gorevler_liste": unique_bugun[:15],
        "son_gorusmeler": son_gorusmeler[:8],
        "yaklasan_takipler": yaklasan_takipler[:10],
        "son_musteriler": son_musteriler[:8],
        "otomasyon_bildirimleri": _build_automation_notifications(
            followup_data["cevap_bekleyen_liste"],
            yaklasan_takipler,
            unique_bugun,
        ),
        "gunluk_ozet": {
            "date": today.isoformat(),
            "yeni_kayit": daily.get("yeni_kayit", 0),
            "yeni_musteri": daily.get("yeni_musteri", 0),
            "satis_sayisi": daily.get("satis_sayisi"),
            "toplam_gelir": daily.get("toplam_gelir"),
            "donusum_orani": daily.get("donusum_orani"),
            "toplam_iletisim": contact.get("toplam_iletisim", 0),
            "kategori_iletisim": contact.get("kategori_bazli", []),
        },
        **followup_data,
    }
