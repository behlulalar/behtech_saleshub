from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from database import Lead, LeadActivity

ACTIVITY_TYPES: dict[str, str] = {
    "mesaj_gonderildi": "Mesaj gönderildi",
    "demo_gonderildi": "Demo gönderildi",
    "teklif_verildi": "Teklif verildi",
    "telefon_gorusmesi": "Telefon görüşmesi yapıldı",
    "gorusme_planlandi": "Görüşme planlandı",
    "gorusme_yapildi": "Görüşme yapıldı",
    "takip_yapildi": "Takip yapıldı",
    "durum_degisti": "Durum değişti",
    "satis_kaydedildi": "Ödeme kaydedildi",
    "kayit_olusturuldu": "Kayıt oluşturuldu",
    "diger": "Diğer",
}


def log_activity(
    db: Session,
    *,
    user_id: int,
    lead_id: int,
    activity_type: str,
    title: str,
    description: str = "",
    activity_date: Optional[datetime] = None,
) -> LeadActivity:
    activity = LeadActivity(
        user_id=user_id,
        lead_id=lead_id,
        activity_type=activity_type,
        title=title,
        description=description,
        activity_date=activity_date or datetime.utcnow(),
    )
    db.add(activity)
    return activity


def _parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d")
    except ValueError:
        return None


def _parse_datetime(date_str: str, time_str: str = "") -> Optional[datetime]:
    dt = _parse_date(date_str)
    if not dt:
        return None
    if time_str:
        try:
            parts = time_str.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            return dt.replace(hour=hour, minute=minute)
        except (ValueError, IndexError):
            pass
    return dt


def _is_gorusme_future(data: dict) -> bool:
    date_str = data.get("gorusme_tarihi", "")
    if not date_str:
        return False

    if data.get("durum") == "Görüşme Planlandı":
        return True

    dt = _parse_datetime(date_str, data.get("gorusme_saati", ""))
    if not dt:
        return False

    now = datetime.now()
    if data.get("gorusme_saati"):
        return dt > now

    return dt.date() >= now.date()


def _gorusme_detail(data: dict) -> str:
    date_str = data.get("gorusme_tarihi", "")
    if not date_str:
        return ""
    if data.get("gorusme_saati"):
        return f"{date_str} {data['gorusme_saati']}"
    return date_str


def _gorusme_activity(data: dict, *, is_update: bool = False) -> dict:
    is_future = _is_gorusme_future(data)
    if is_future:
        title = "Görüşme tarihi güncellendi" if is_update else "Görüşme planlandı"
        activity_type = "gorusme_planlandi"
    else:
        title = "Görüşme tarihi güncellendi" if is_update else "Görüşme yapıldı"
        activity_type = "gorusme_yapildi"

    return {
        "activity_type": activity_type,
        "title": title,
        "description": _gorusme_detail(data),
        "activity_date": _parse_datetime(
            data.get("gorusme_tarihi", ""),
            data.get("gorusme_saati", ""),
        ),
    }


def activities_for_new_lead(data: dict) -> list[dict]:
    items: list[dict] = [
        {
            "activity_type": "kayit_olusturuldu",
            "title": "Kayıt oluşturuldu",
            "description": data.get("isletme_adi", ""),
        }
    ]

    if data.get("ilk_mesaj_tarihi"):
        items.append(
            {
                "activity_type": "mesaj_gonderildi",
                "title": "Mesaj gönderildi",
                "description": _mesaj_detail(data),
                "activity_date": _mesaj_activity_date(data),
            }
        )

    if data.get("demo_gonderildi") or data.get("demo_tarihi"):
        items.append(
            {
                "activity_type": "demo_gonderildi",
                "title": "Demo gönderildi",
                "description": data.get("demo_tarihi") or "",
                "activity_date": _parse_date(data.get("demo_tarihi", "")),
            }
        )

    if data.get("teklif"):
        items.append(
            {
                "activity_type": "teklif_verildi",
                "title": "Teklif verildi",
                "description": data["teklif"],
            }
        )

    if data.get("gorusme_tarihi"):
        items.append(_gorusme_activity(data))

    if data.get("ilk_iletisim_kanali") == "Telefon":
        items.append(
            {
                "activity_type": "telefon_gorusmesi",
                "title": "Telefon görüşmesi yapıldı",
                "description": data.get("notlar", ""),
            }
        )

    for field, label in (("takip_1", "Takip 1"), ("takip_2", "Takip 2")):
        if data.get(field):
            items.append(
                {
                    "activity_type": "takip_yapildi",
                    "title": "Takip yapıldı",
                    "description": f"{label}: {data[field]}",
                }
            )

    return items


def activities_for_lead_update(old: Lead, data: dict) -> list[dict]:
    items: list[dict] = []

    if not old.ilk_mesaj_tarihi and data.get("ilk_mesaj_tarihi"):
        items.append(
            {
                "activity_type": "mesaj_gonderildi",
                "title": "Mesaj gönderildi",
                "description": _mesaj_detail(data),
                "activity_date": _mesaj_activity_date(data),
            }
        )
    elif old.ilk_mesaj_tarihi != data.get("ilk_mesaj_tarihi") and data.get("ilk_mesaj_tarihi"):
        items.append(
            {
                "activity_type": "mesaj_gonderildi",
                "title": "Mesaj tarihi güncellendi",
                "description": _mesaj_detail(data),
                "activity_date": _mesaj_activity_date(data),
            }
        )

    if (not old.demo_gonderildi and data.get("demo_gonderildi")) or (
        not old.demo_tarihi and data.get("demo_tarihi")
    ):
        items.append(
            {
                "activity_type": "demo_gonderildi",
                "title": "Demo gönderildi",
                "description": data.get("demo_tarihi") or "",
                "activity_date": _parse_date(data.get("demo_tarihi", "")),
            }
        )

    if not old.teklif and data.get("teklif"):
        items.append(
            {
                "activity_type": "teklif_verildi",
                "title": "Teklif verildi",
                "description": data["teklif"],
            }
        )
    elif old.teklif != data.get("teklif") and data.get("teklif"):
        items.append(
            {
                "activity_type": "teklif_verildi",
                "title": "Teklif güncellendi",
                "description": data["teklif"],
            }
        )

    if old.durum != data.get("durum"):
        items.append(
            {
                "activity_type": "durum_degisti",
                "title": "Durum değişti",
                "description": f"{old.durum} → {data.get('durum')}",
            }
        )

    old_amount = float(old.satis_tutari or 0)
    new_amount = float(data.get("satis_tutari") or 0)
    if new_amount > 0 and new_amount != old_amount:
        items.append(
            {
                "activity_type": "satis_kaydedildi",
                "title": "Ödeme kaydedildi" if old_amount == 0 else "Alınan miktar güncellendi",
                "description": f"{new_amount:,.0f} TL".replace(",", "."),
                "activity_date": _parse_date(data.get("satis_tarihi", "")),
            }
        )

    for field, label in (("takip_1", "Takip 1"), ("takip_2", "Takip 2")):
        old_val = getattr(old, field)
        new_val = data.get(field, "")
        if not old_val and new_val:
            items.append(
                {
                    "activity_type": "takip_yapildi",
                    "title": "Takip yapıldı",
                    "description": f"{label}: {new_val}",
                }
            )
        elif old_val != new_val and new_val:
            items.append(
                {
                    "activity_type": "takip_yapildi",
                    "title": "Takip güncellendi",
                    "description": f"{label}: {new_val}",
                }
            )

    return items


def _mesaj_activity_date(data: dict) -> Optional[datetime]:
    return _parse_datetime(data.get("ilk_mesaj_tarihi", ""), data.get("ilk_mesaj_saati", ""))


def _mesaj_detail(data: dict) -> str:
    parts = []
    if data.get("ilk_iletisim_kanali"):
        parts.append(data["ilk_iletisim_kanali"])
    if data.get("ilk_mesaj_tarihi"):
        date_part = data["ilk_mesaj_tarihi"]
        if data.get("ilk_mesaj_saati"):
            date_part += f" {data['ilk_mesaj_saati']}"
        parts.append(date_part)
    return " · ".join(parts)


def record_activities(db: Session, user_id: int, lead_id: int, items: list[dict]) -> None:
    for item in items:
        log_activity(
            db,
            user_id=user_id,
            lead_id=lead_id,
            activity_type=item["activity_type"],
            title=item["title"],
            description=item.get("description", ""),
            activity_date=item.get("activity_date"),
        )


def lead_to_activity_data(lead: Lead) -> dict:
    return {
        "isletme_adi": lead.isletme_adi,
        "ilk_iletisim_kanali": lead.ilk_iletisim_kanali,
        "ilk_mesaj_tarihi": lead.ilk_mesaj_tarihi,
        "ilk_mesaj_saati": lead.ilk_mesaj_saati,
        "demo_gonderildi": lead.demo_gonderildi,
        "demo_tarihi": lead.demo_tarihi,
        "teklif": lead.teklif,
        "gorusme_tarihi": lead.gorusme_tarihi,
        "gorusme_saati": getattr(lead, "gorusme_saati", "") or "",
        "durum": lead.durum,
        "takip_1": lead.takip_1,
        "takip_2": lead.takip_2,
        "notlar": lead.notlar,
    }


def build_initial_activities(lead: Lead) -> list[dict]:
    items = activities_for_new_lead(lead_to_activity_data(lead))
    if items and items[0]["activity_type"] == "kayit_olusturuldu" and lead.created_at:
        items[0]["activity_date"] = lead.created_at
    return items


def ensure_lead_activities(db: Session, lead: Lead) -> bool:
    """Eski kayıtlar için aktivite geçmişi yoksa mevcut veriden oluşturur."""
    exists = (
        db.query(LeadActivity.id)
        .filter(LeadActivity.lead_id == lead.id)
        .limit(1)
        .first()
    )
    if exists:
        return False

    record_activities(db, lead.user_id, lead.id, build_initial_activities(lead))
    db.commit()
    return True


def fix_future_gorusme_activities(db: Session) -> int:
    """Gelecek görüşmeleri yanlışlıkla 'yapıldı' olarak işaretlenmiş aktiviteleri düzeltir."""
    updated = 0
    leads = db.query(Lead).filter(Lead.gorusme_tarihi != "").all()

    for lead in leads:
        data = lead_to_activity_data(lead)
        if not _is_gorusme_future(data):
            continue

        activities = (
            db.query(LeadActivity)
            .filter(
                LeadActivity.lead_id == lead.id,
                LeadActivity.activity_type == "gorusme_yapildi",
            )
            .all()
        )

        for activity in activities:
            activity.activity_type = "gorusme_planlandi"
            if "yapıldı" in activity.title:
                activity.title = activity.title.replace("yapıldı", "planlandı")
            elif activity.title == "Görüşme tarihi güncellendi":
                activity.title = "Görüşme tarihi güncellendi"
            else:
                activity.title = "Görüşme planlandı"

            detail = _gorusme_detail(data)
            if detail:
                activity.description = detail

            meeting_dt = _parse_datetime(lead.gorusme_tarihi, getattr(lead, "gorusme_saati", "") or "")
            if meeting_dt:
                activity.activity_date = meeting_dt

            updated += 1

    if updated:
        db.commit()
    return updated


def sync_gorusme_activity_on_update(
    db: Session, old: Lead, data: dict, user_id: int, lead_id: int
) -> None:
    old_pair = (old.gorusme_tarihi, getattr(old, "gorusme_saati", "") or "")
    new_pair = (data.get("gorusme_tarihi", ""), data.get("gorusme_saati", ""))

    if new_pair == old_pair or not data.get("gorusme_tarihi"):
        return

    is_update = bool(old.gorusme_tarihi)
    new_item = _gorusme_activity(data, is_update=is_update)

    latest = (
        db.query(LeadActivity)
        .filter(
            LeadActivity.lead_id == lead_id,
            LeadActivity.activity_type.in_(["gorusme_planlandi", "gorusme_yapildi"]),
        )
        .order_by(LeadActivity.id.desc())
        .first()
    )

    if latest and is_update and old.gorusme_tarihi == data.get("gorusme_tarihi"):
        latest.activity_type = new_item["activity_type"]
        if old_pair[0] == new_pair[0] and old_pair[1] != new_pair[1]:
            latest.title = "Görüşme saati güncellendi"
        else:
            latest.title = new_item["title"]
        latest.description = new_item["description"]
        if new_item.get("activity_date"):
            latest.activity_date = new_item["activity_date"]
        return

    record_activities(db, user_id, lead_id, [new_item])


def sync_mesaj_activity_on_update(
    db: Session, old: Lead, data: dict, lead_id: int
) -> None:
    old_fields = (
        old.ilk_mesaj_tarihi or "",
        old.ilk_mesaj_saati or "",
        old.ilk_iletisim_kanali or "",
    )
    new_fields = (
        data.get("ilk_mesaj_tarihi", ""),
        data.get("ilk_mesaj_saati", ""),
        data.get("ilk_iletisim_kanali", ""),
    )

    if new_fields == old_fields or not data.get("ilk_mesaj_tarihi"):
        return

    if old_fields[0] != new_fields[0]:
        return

    latest = (
        db.query(LeadActivity)
        .filter(
            LeadActivity.lead_id == lead_id,
            LeadActivity.activity_type == "mesaj_gonderildi",
        )
        .order_by(LeadActivity.id.desc())
        .first()
    )
    if not latest:
        return

    mesaj_dt = _mesaj_activity_date(data)
    latest.description = _mesaj_detail(data)
    if mesaj_dt:
        latest.activity_date = mesaj_dt


def sync_lead_mesaj_activity_date(db: Session, lead: Lead) -> bool:
    """Tek bir lead'in mesaj aktivite saatini ilk mesaj alanlarıyla hizalar."""
    if not lead.ilk_mesaj_tarihi:
        return False

    data = lead_to_activity_data(lead)
    mesaj_dt = _mesaj_activity_date(data)
    if not mesaj_dt:
        return False

    detail = _mesaj_detail(data)
    activities = (
        db.query(LeadActivity)
        .filter(
            LeadActivity.lead_id == lead.id,
            LeadActivity.activity_type == "mesaj_gonderildi",
        )
        .all()
    )

    changed = False
    for activity in activities:
        stored = activity.activity_date
        missing_time = (
            bool(lead.ilk_mesaj_saati)
            and stored.hour == 0
            and stored.minute == 0
            and mesaj_dt.hour != 0
        )
        if missing_time or stored != mesaj_dt or activity.description != detail:
            activity.activity_date = mesaj_dt
            activity.description = detail
            changed = True

    if changed:
        db.commit()
    return changed


def fix_mesaj_activity_dates(db: Session) -> int:
    """Mesaj aktivitelerinin saatini lead kaydındaki ilk mesaj alanlarıyla hizalar."""
    updated = 0
    leads = db.query(Lead).filter(Lead.ilk_mesaj_tarihi != "").all()

    for lead in leads:
        if sync_lead_mesaj_activity_date(db, lead):
            updated += 1

    return updated


def backfill_all_lead_activities(db: Session) -> int:
    leads = db.query(Lead).all()
    created = 0
    for lead in leads:
        if ensure_lead_activities(db, lead):
            created += 1
    return created
