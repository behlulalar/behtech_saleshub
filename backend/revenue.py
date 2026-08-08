from collections import defaultdict
from datetime import date, datetime

from sqlalchemy.orm import Session

from database import CategoryModel, Lead


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _sale_amount(lead: Lead) -> float:
    return float(lead.satis_tutari or 0)


def _sale_date(lead: Lead) -> date | None:
    if _sale_amount(lead) <= 0:
        return None
    parsed = _parse_date(lead.satis_tarihi)
    if parsed:
        return parsed
    if lead.durum == "Müşteri" and lead.updated_at:
        return lead.updated_at.date()
    return None


def _month_key(d: date) -> str:
    return d.strftime("%Y-%m")


def _month_label(key: str) -> str:
    year, month = key.split("-")
    months = [
        "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
        "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
    ]
    return f"{months[int(month) - 1]} {year}"


def build_revenue(db: Session, user_id: int) -> dict:
    leads = db.query(Lead).filter(Lead.user_id == user_id).all()
    categories = {
        cat.id: cat.label
        for cat in db.query(CategoryModel).filter(CategoryModel.user_id == user_id).all()
    }

    sales = [lead for lead in leads if _sale_amount(lead) > 0]
    today = date.today()
    this_month_key = _month_key(today)
    this_year = str(today.year)

    total_revenue = sum(_sale_amount(lead) for lead in sales)
    month_revenue = 0.0
    year_revenue = 0.0

    by_category: dict[str, dict] = defaultdict(lambda: {"gelir": 0.0, "satis_sayisi": 0})
    by_month: dict[str, float] = defaultdict(float)
    sale_items: list[dict] = []

    for lead in sales:
        amount = _sale_amount(lead)
        sale_day = _sale_date(lead)

        if sale_day:
            month_key = _month_key(sale_day)
            by_month[month_key] += amount
            if month_key == this_month_key:
                month_revenue += amount
            if str(sale_day.year) == this_year:
                year_revenue += amount

        cat_id = lead.category
        by_category[cat_id]["gelir"] += amount
        by_category[cat_id]["satis_sayisi"] += 1

        sale_items.append(
            {
                "id": lead.id,
                "isletme_adi": lead.isletme_adi,
                "category": cat_id,
                "category_label": categories.get(cat_id, cat_id),
                "sehir": lead.sehir,
                "satis_tutari": amount,
                "satis_tarihi": lead.satis_tarihi or (sale_day.isoformat() if sale_day else ""),
                "teklif": lead.teklif,
            }
        )

    sale_items.sort(key=lambda item: item["satis_tarihi"] or "", reverse=True)

    month_series = []
    for offset in range(11, -1, -1):
        month = today.month - offset
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        key = f"{year:04d}-{month:02d}"
        month_series.append(
            {
                "ay": key,
                "ay_label": _month_label(key),
                "gelir": round(by_month.get(key, 0.0), 2),
            }
        )

    category_breakdown = [
        {
            "category": cat_id,
            "category_label": categories.get(cat_id, cat_id),
            "gelir": round(values["gelir"], 2),
            "satis_sayisi": values["satis_sayisi"],
        }
        for cat_id, values in by_category.items()
    ]
    category_breakdown.sort(key=lambda item: item["gelir"], reverse=True)

    customer_count = sum(1 for lead in leads if lead.durum == "Müşteri")
    sale_count = len(sales)
    avg_sale = round(total_revenue / sale_count, 2) if sale_count else 0.0

    return {
        "toplam_gelir": round(total_revenue, 2),
        "bu_ay_gelir": round(month_revenue, 2),
        "bu_yil_gelir": round(year_revenue, 2),
        "ortalama_satis": avg_sale,
        "satis_sayisi": sale_count,
        "musteri_sayisi": customer_count,
        "kategori_dagilimi": category_breakdown,
        "aylik_gelir": month_series,
        "son_satislar": sale_items[:20],
    }
