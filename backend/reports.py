from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from dashboard import get_category_map
from database import Lead
from funnel import build_sales_funnel
from revenue import _parse_date, list_payment_events


def _week_bounds(anchor: date) -> tuple[date, date]:
    start = anchor - timedelta(days=anchor.weekday())
    end = start + timedelta(days=6)
    return start, end


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def _format_period_label(period_type: str, start: date, end: date) -> str:
    if period_type == "daily":
        return start.strftime("%d.%m.%Y")
    if period_type == "weekly":
        return f"{start.strftime('%d.%m.%Y')} – {end.strftime('%d.%m.%Y')}"
    months = [
        "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
        "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
    ]
    return f"{months[start.month - 1]} {start.year}"


def _lead_created_in_range(lead: Lead, start: date, end: date) -> bool:
    if not lead.created_at:
        return False
    created = lead.created_at.date()
    return start <= created <= end


def _lead_became_customer_in_range(lead: Lead, start: date, end: date) -> bool:
    if lead.durum != "Müşteri":
        return False
    sale_day = _parse_date(lead.satis_tarihi or "")
    if sale_day:
        return start <= sale_day <= end
    return False


def _sales_in_range(db: Session, user_id: int, start: date, end: date) -> list[tuple]:
    result = []
    for event in list_payment_events(db, user_id):
        if event.paid_on and start <= event.paid_on <= end:
            result.append(event)
    return result


def build_period_report(
    db: Session,
    user_id: int,
    period_type: str,
    anchor: date | None = None,
    include_revenue: bool = True,
) -> dict:
    today = anchor or date.today()
    if period_type == "daily":
        start = end = today
    elif period_type == "monthly":
        start, end = _month_bounds(today.year, today.month)
    else:
        start, end = _week_bounds(today)

    leads = db.query(Lead).filter(Lead.user_id == user_id).all()
    cat_map = get_category_map(db, user_id)

    period_leads = [lead for lead in leads if _lead_created_in_range(lead, start, end)]
    new_customers = sum(1 for lead in leads if _lead_became_customer_in_range(lead, start, end))
    new_leads = len(period_leads)
    cohort_customers = sum(
        1 for lead in period_leads if _lead_became_customer_in_range(lead, start, end)
    )

    conversion = round((cohort_customers / new_leads) * 100, 1) if new_leads > 0 else None

    funnel = build_sales_funnel(period_leads)

    status_counts = Counter(lead.durum for lead in period_leads)
    durum_dagilimi = [
        {"durum": durum, "count": count}
        for durum, count in status_counts.most_common()
    ]

    category_stats: dict[str, dict] = defaultdict(lambda: {"yeni_kayit": 0, "musteri": 0})
    for lead in period_leads:
        category_stats[lead.category]["yeni_kayit"] += 1
    for lead in leads:
        if _lead_became_customer_in_range(lead, start, end):
            category_stats[lead.category]["musteri"] += 1

    kategori_ozet = [
        {
            "category": cat_id,
            "category_label": cat_map.get(cat_id, cat_id),
            "yeni_kayit": values["yeni_kayit"],
            "musteri": values["musteri"],
        }
        for cat_id, values in category_stats.items()
    ]
    kategori_ozet.sort(key=lambda item: item["yeni_kayit"] + item["musteri"], reverse=True)

    sales_count = None
    total_revenue = None
    average_sale = None
    period_sales: list[dict] = []

    if include_revenue:
        sales = _sales_in_range(db, user_id, start, end)
        sales_count = len(sales)
        total_revenue = round(sum(event.amount for event in sales), 2)
        average_sale = round(total_revenue / sales_count, 2) if sales_count else 0.0
        period_sales = [
            {
                "isletme_adi": event.lead.isletme_adi,
                "category_label": cat_map.get(event.lead.category, event.lead.category),
                "sehir": event.lead.sehir,
                "satis_tutari": event.amount,
                "satis_tarihi": event.paid_on.isoformat() if event.paid_on else "",
            }
            for event in sorted(sales, key=lambda item: item.paid_on or date.min, reverse=True)
        ]

    prev_start = start - timedelta(days=7 if period_type == "weekly" else 0)
    prev_end = end - timedelta(days=7 if period_type == "weekly" else 0)
    if period_type == "monthly":
        prev_month = start.month - 1 or 12
        prev_year = start.year if start.month > 1 else start.year - 1
        prev_start, prev_end = _month_bounds(prev_year, prev_month)

    prev_leads = sum(1 for lead in leads if _lead_created_in_range(lead, prev_start, prev_end))
    prev_customers = sum(1 for lead in leads if _lead_became_customer_in_range(lead, prev_start, prev_end))

    return {
        "period_type": period_type,
        "period_label": _format_period_label(period_type, start, end),
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "yeni_kayit": new_leads,
        "yeni_musteri": new_customers,
        "donusum_orani": conversion,
        "satis_sayisi": sales_count,
        "toplam_gelir": total_revenue,
        "ortalama_satis": average_sale,
        "satis_hunisi": funnel["satis_hunisi"],
        "satis_donusum_orani": funnel["satis_donusum_orani"],
        "durum_dagilimi": durum_dagilimi,
        "kategori_ozet": kategori_ozet,
        "donem_satislar": period_sales,
        "onceki_donem": {
            "yeni_kayit": prev_leads,
            "yeni_musteri": prev_customers,
        },
    }


def parse_report_anchor(period_type: str, date_param: str | None, month_param: str | None) -> date:
    if period_type == "monthly" and month_param:
        try:
            parsed = datetime.strptime(month_param[:7], "%Y-%m").date()
            return date(parsed.year, parsed.month, 1)
        except ValueError:
            pass
    if date_param:
        parsed = _parse_date(date_param)
        if parsed:
            return parsed
    return date.today()


def build_daily_report(
    db: Session,
    user_id: int,
    anchor: date | None = None,
    include_revenue: bool = True,
) -> dict:
    return build_period_report(db, user_id, "daily", anchor, include_revenue)
