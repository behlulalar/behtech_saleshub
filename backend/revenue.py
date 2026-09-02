from collections import defaultdict
from calendar import monthrange
from datetime import date, datetime
import re

from sqlalchemy.orm import Session

from database import CategoryModel, Lead

MONTHS_TR = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]


def parse_offer_amount(text: str) -> float:
    digits = re.sub(r"\D", "", text or "")
    if not digits:
        return 0.0
    try:
        return float(digits)
    except ValueError:
        return 0.0


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _as_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def resolve_sale_date(
    *,
    satis_tarihi: str = "",
    updated_at=None,
    created_at=None,
) -> date | None:
    parsed = _parse_date(satis_tarihi)
    if parsed:
        return parsed
    return _as_date(updated_at) or _as_date(created_at)


def in_period(day: date | None, year: int | None, month: int | None) -> bool:
    if day is None:
        return year is None and month is None
    if year is None:
        return True
    if day.year != year:
        return False
    if month is None:
        return True
    return day.month == month


def _sale_amount(lead: Lead) -> float:
    return float(lead.satis_tutari or 0)


def _sale_date(lead: Lead) -> date | None:
    if _sale_amount(lead) <= 0:
        return None
    return resolve_sale_date(
        satis_tarihi=lead.satis_tarihi or "",
        updated_at=lead.updated_at,
        created_at=lead.created_at,
    )


def _month_key(d: date) -> str:
    return d.strftime("%Y-%m")


def _month_label(key: str) -> str:
    year, month = key.split("-")
    return f"{MONTHS_TR[int(month) - 1]} {year}"


def _period_label(year: int | None, month: int | None) -> str:
    if year and month:
        return f"{MONTHS_TR[month - 1]} {year}"
    if year:
        return str(year)
    return "Tüm zamanlar"


def _previous_period(year: int | None, month: int | None) -> tuple[int | None, int | None]:
    if year and month:
        if month == 1:
            return year - 1, 12
        return year, month - 1
    if year:
        return year - 1, None
    return None, None


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    total = year * 12 + (month - 1) + delta
    return total // 12, total % 12 + 1


def build_revenue(
    db: Session,
    user_id: int,
    year: int | None = None,
    month: int | None = None,
) -> dict:
    if month is not None and year is None:
        year = date.today().year

    leads = db.query(Lead).filter(Lead.user_id == user_id).all()
    categories = {
        cat.id: cat.label
        for cat in db.query(CategoryModel).filter(CategoryModel.user_id == user_id).all()
    }

    today = date.today()
    this_month_key = _month_key(today)
    this_year = today.year

    all_sales: list[tuple[Lead, float, date | None]] = []
    for lead in leads:
        amount = _sale_amount(lead)
        if amount <= 0:
            continue
        all_sales.append((lead, amount, _sale_date(lead)))

    period_sales = [
        item for item in all_sales if in_period(item[2], year, month)
    ]
    prev_year, prev_month = _previous_period(year, month)
    previous_revenue = 0.0
    if year is not None:
        previous_revenue = sum(
            amount for _, amount, day in all_sales if in_period(day, prev_year, prev_month)
        )

    total_revenue = sum(amount for _, amount, _ in period_sales)
    all_time_revenue = sum(amount for _, amount, _ in all_sales)
    month_revenue = 0.0
    year_revenue = 0.0
    by_category: dict[str, dict] = defaultdict(lambda: {"gelir": 0.0, "satis_sayisi": 0})
    by_month: dict[str, float] = defaultdict(float)
    by_day: dict[str, float] = defaultdict(float)
    sale_items: list[dict] = []
    years: set[int] = {today.year}

    for lead, amount, sale_day in all_sales:
        if sale_day:
            years.add(sale_day.year)
            by_month[_month_key(sale_day)] += amount
            if _month_key(sale_day) == this_month_key:
                month_revenue += amount
            if sale_day.year == this_year:
                year_revenue += amount

    offer_total = 0.0
    for lead, amount, sale_day in period_sales:
        cat_id = lead.category
        by_category[cat_id]["gelir"] += amount
        by_category[cat_id]["satis_sayisi"] += 1
        offer_total += parse_offer_amount(lead.teklif or "")
        if sale_day:
            by_day[sale_day.isoformat()] += amount
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

    if year and month:
        chart_year, chart_month = year, month
        month_series = []
        for offset in range(11, -1, -1):
            y, m = _shift_month(chart_year, chart_month, -offset)
            key = f"{y:04d}-{m:02d}"
            month_series.append(
                {"ay": key, "ay_label": _month_label(key), "gelir": round(by_month.get(key, 0.0), 2)}
            )
        days_in_month = monthrange(year, month)[1]
        daily_series = []
        for day_n in range(1, days_in_month + 1):
            day = date(year, month, day_n)
            daily_series.append(
                {
                    "gun": day.isoformat(),
                    "gun_label": str(day_n),
                    "gelir": round(by_day.get(day.isoformat(), 0.0), 2),
                }
            )
    elif year:
        month_series = []
        for m in range(1, 13):
            key = f"{year:04d}-{m:02d}"
            month_series.append(
                {"ay": key, "ay_label": _month_label(key), "gelir": round(by_month.get(key, 0.0), 2)}
            )
        daily_series = []
    else:
        month_series = []
        for offset in range(11, -1, -1):
            y, m = _shift_month(today.year, today.month, -offset)
            key = f"{y:04d}-{m:02d}"
            month_series.append(
                {"ay": key, "ay_label": _month_label(key), "gelir": round(by_month.get(key, 0.0), 2)}
            )
        daily_series = []

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

    sale_count = len(period_sales)
    avg_sale = round(total_revenue / sale_count, 2) if sale_count else 0.0
    remaining = max(offer_total - total_revenue, 0.0)
    change_pct = None
    if year is not None and previous_revenue > 0:
        change_pct = round(((total_revenue - previous_revenue) / previous_revenue) * 100, 1)
    elif year is not None and previous_revenue == 0 and total_revenue > 0:
        change_pct = 100.0

    customer_count = sum(
        1
        for lead, amount, day in period_sales
        if lead.durum == "Müşteri" or amount > 0
    )

    return {
        "year": year,
        "month": month,
        "period_label": _period_label(year, month),
        "available_years": sorted(years, reverse=True),
        "toplam_gelir": round(total_revenue, 2),
        "tum_zamanlar_gelir": round(all_time_revenue, 2),
        "bu_ay_gelir": round(month_revenue, 2),
        "bu_yil_gelir": round(year_revenue, 2),
        "onceki_donem_gelir": round(previous_revenue, 2) if year is not None else None,
        "degisim_yuzde": change_pct,
        "ortalama_satis": avg_sale,
        "satis_sayisi": sale_count,
        "musteri_sayisi": customer_count,
        "teklif_toplami": round(offer_total, 2),
        "kalan_toplam": round(remaining, 2),
        "kategori_dagilimi": category_breakdown,
        "aylik_gelir": month_series,
        "gunluk_gelir": daily_series,
        "son_satislar": sale_items[:50],
    }
