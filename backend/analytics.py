from collections import defaultdict
from datetime import date, datetime

from sqlalchemy.orm import Session

from database import CategoryModel, Lead, LeadActivity
from funnel import (
    FUNNEL_DEFINITIONS,
    _rate,
    _reached_cevap,
    _reached_satis,
    _stage_count,
    build_sales_funnel,
)

GUN_LABELS = [
    "Pazartesi",
    "Salı",
    "Çarşamba",
    "Perşembe",
    "Cuma",
    "Cumartesi",
    "Pazar",
]

CONTACT_ACTIVITY_TYPES = frozenset(
    {
        "mesaj_gonderildi",
        "telefon_gorusmesi",
        "demo_gonderildi",
    }
)


def _parse_lead_date(value: str) -> date | None:
    if not value or not value.strip():
        return None
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_analytics_anchor(date_param: str | None) -> date:
    if date_param:
        parsed = _parse_lead_date(date_param)
        if parsed:
            return parsed
    return date.today()


def build_daily_contact_analytics(db: Session, user_id: int, anchor: date | None = None) -> dict:
    """Seçilen günde kategori bazında kaç lead ile iletişime geçildi."""
    day = anchor or date.today()
    leads = db.query(Lead).filter(Lead.user_id == user_id).all()
    cat_map = get_category_map(db, user_id)
    lead_category = {lead.id: lead.category for lead in leads}

    contacted: dict[str, set[int]] = defaultdict(set)

    for lead in leads:
        if _parse_lead_date(lead.ilk_mesaj_tarihi) == day:
            contacted[lead.category].add(lead.id)

    activity_rows = (
        db.query(LeadActivity.lead_id, LeadActivity.activity_type, LeadActivity.activity_date)
        .join(Lead, Lead.id == LeadActivity.lead_id)
        .filter(Lead.user_id == user_id, LeadActivity.activity_type.in_(CONTACT_ACTIVITY_TYPES))
        .all()
    )
    for lead_id, _activity_type, activity_date in activity_rows:
        if activity_date and activity_date.date() == day:
            category = lead_category.get(lead_id)
            if category:
                contacted[category].add(lead_id)

    kategori_bazli: list[dict] = []
    total = 0
    for category_id, lead_ids in contacted.items():
        count = len(lead_ids)
        total += count
        kategori_bazli.append(
            {
                "category": category_id,
                "category_label": cat_map.get(category_id, category_id),
                "iletisim_sayisi": count,
            }
        )

    kategori_bazli.sort(key=lambda item: item["iletisim_sayisi"], reverse=True)

    return {
        "date": day.isoformat(),
        "date_label": day.strftime("%d.%m.%Y"),
        "toplam_iletisim": total,
        "kategori_bazli": kategori_bazli,
    }


def get_category_map(db: Session, user_id: int) -> dict[str, str]:
    cats = db.query(CategoryModel).filter(CategoryModel.user_id == user_id).all()
    return {c.id: c.label for c in cats}


def _parse_hour(value: str) -> int | None:
    if not value or not value.strip():
        return None
    try:
        return int(value.strip().split(":")[0])
    except ValueError:
        return None


def _parse_weekday(value: str) -> int | None:
    if not value or not value.strip():
        return None
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").weekday()
    except ValueError:
        return None


def _build_donusum_oranlari(leads: list[Lead]) -> list[dict]:
    counts = {key: _stage_count(leads, key) for key, _ in FUNNEL_DEFINITIONS}
    stages: list[dict] = []
    previous_count: int | None = None

    for index, (key, label) in enumerate(FUNNEL_DEFINITIONS):
        count = counts[key]
        next_key = FUNNEL_DEFINITIONS[index + 1][0] if index + 1 < len(FUNNEL_DEFINITIONS) else None
        next_count = counts[next_key] if next_key else None

        stages.append(
            {
                "key": key,
                "label": label,
                "count": count,
                "asama_basari_orani": _rate(next_count, count) if next_count is not None else None,
                "onceki_asama_orani": _rate(count, previous_count) if previous_count is not None else None,
                "toplam_orani": _rate(count, counts["iletisim"]) if counts["iletisim"] > 0 else 0.0,
            }
        )
        previous_count = count

    return stages


def _build_sehir_analizi(leads: list[Lead]) -> list[dict]:
    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"toplam": 0, "cevap": 0, "satis": 0})

    for lead in leads:
        sehir = (lead.sehir or "").strip() or "Belirtilmemiş"
        stats[sehir]["toplam"] += 1
        if _reached_cevap(lead):
            stats[sehir]["cevap"] += 1
        if _reached_satis(lead):
            stats[sehir]["satis"] += 1

    result = []
    for sehir, values in stats.items():
        result.append(
            {
                "sehir": sehir,
                "toplam": values["toplam"],
                "cevap": values["cevap"],
                "satis": values["satis"],
                "cevap_orani": _rate(values["cevap"], values["toplam"]) or 0.0,
                "satis_orani": _rate(values["satis"], values["toplam"]) or 0.0,
            }
        )

    result.sort(key=lambda item: (item["satis"], item["cevap_orani"]), reverse=True)
    return result


def _build_kategori_analizi(leads: list[Lead], cat_map: dict[str, str]) -> list[dict]:
    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"toplam": 0, "cevap": 0, "satis": 0})

    for lead in leads:
        stats[lead.category]["toplam"] += 1
        if _reached_cevap(lead):
            stats[lead.category]["cevap"] += 1
        if _reached_satis(lead):
            stats[lead.category]["satis"] += 1

    result = []
    for category_id, values in stats.items():
        result.append(
            {
                "category": category_id,
                "category_label": cat_map.get(category_id, category_id),
                "toplam": values["toplam"],
                "cevap": values["cevap"],
                "satis": values["satis"],
                "cevap_orani": _rate(values["cevap"], values["toplam"]) or 0.0,
                "satis_orani": _rate(values["satis"], values["toplam"]) or 0.0,
            }
        )

    result.sort(key=lambda item: (item["satis"], item["satis_orani"]), reverse=True)
    return result


def _build_saat_analizi(leads: list[Lead]) -> list[dict]:
    stats: dict[int, dict[str, int]] = defaultdict(lambda: {"mesaj": 0, "cevap": 0})

    for lead in leads:
        hour = _parse_hour(lead.ilk_mesaj_saati)
        if hour is None:
            continue
        stats[hour]["mesaj"] += 1
        if _reached_cevap(lead):
            stats[hour]["cevap"] += 1

    result = []
    for hour in range(24):
        values = stats.get(hour, {"mesaj": 0, "cevap": 0})
        result.append(
            {
                "saat": hour,
                "saat_label": f"{hour:02d}:00",
                "mesaj_sayisi": values["mesaj"],
                "cevap_sayisi": values["cevap"],
                "cevap_orani": _rate(values["cevap"], values["mesaj"]) or 0.0,
            }
        )

    result.sort(key=lambda item: (item["cevap_sayisi"], item["cevap_orani"]), reverse=True)
    return result


def _build_gun_analizi(leads: list[Lead]) -> list[dict]:
    stats: dict[int, dict[str, int]] = defaultdict(lambda: {"mesaj": 0, "cevap": 0})

    for lead in leads:
        weekday = _parse_weekday(lead.ilk_mesaj_tarihi)
        if weekday is None:
            continue
        stats[weekday]["mesaj"] += 1
        if _reached_cevap(lead):
            stats[weekday]["cevap"] += 1

    result = []
    for weekday in range(7):
        values = stats.get(weekday, {"mesaj": 0, "cevap": 0})
        result.append(
            {
                "gun": weekday,
                "gun_label": GUN_LABELS[weekday],
                "mesaj_sayisi": values["mesaj"],
                "cevap_sayisi": values["cevap"],
                "cevap_orani": _rate(values["cevap"], values["mesaj"]) or 0.0,
            }
        )

    result.sort(key=lambda item: (item["cevap_sayisi"], item["cevap_orani"]), reverse=True)
    return result


def build_analytics(db: Session, user_id: int) -> dict:
    leads = db.query(Lead).filter(Lead.user_id == user_id).all()
    cat_map = get_category_map(db, user_id)
    funnel = build_sales_funnel(leads)

    return {
        **funnel,
        "donusum_oranlari": _build_donusum_oranlari(leads),
        "sehir_analizi": _build_sehir_analizi(leads),
        "kategori_analizi": _build_kategori_analizi(leads, cat_map),
        "saat_analizi": _build_saat_analizi(leads),
        "gun_analizi": _build_gun_analizi(leads),
    }
