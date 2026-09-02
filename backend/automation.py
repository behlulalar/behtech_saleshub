from datetime import timedelta

from sqlalchemy.orm import Session

from app_timezone import local_now, local_today
from config import settings
from dashboard import build_dashboard
from database import User
from email_service import send_automation_email
from reports import build_daily_report
from revenue import list_payment_events
from roles import ROLE_OWNER


def _owner_users(db: Session) -> list[User]:
    return db.query(User).filter(User.role == ROLE_OWNER).all()


def _format_try(amount: float) -> str:
    return f"{amount:,.0f} ₺".replace(",", ".")


def format_revenue_digest_lines(
    *,
    today_total: float,
    today_count: int,
    month_total: float,
    year_total: float,
    today_items: list[tuple[str, float, str]],
) -> list[str]:
    """Mail gövdesi: tahsilat, kaydedildiği güne göre (teklif tarihi değil)."""
    lines = [
        "Alınan ödemeler (kayıt gününe göre):",
        f"  Bugün: {_format_try(today_total)} · {today_count} ödeme",
        f"  Bu ay: {_format_try(month_total)}",
        f"  Bu yıl: {_format_try(year_total)}",
    ]
    if today_items:
        lines.append("")
        lines.append("Bugünkü tahsilatlar:")
        for name, amount, offer in today_items[:12]:
            extra = f" · teklif {offer}" if offer else ""
            lines.append(f"  • {name} — {_format_try(amount)}{extra}")
    return lines


def collect_revenue_digest_lines(db: Session, user_id: int) -> list[str]:
    today = local_today()
    events = list_payment_events(db, user_id)
    today_events = [event for event in events if event.paid_on == today]
    month_events = [
        event
        for event in events
        if event.paid_on and event.paid_on.year == today.year and event.paid_on.month == today.month
    ]
    year_events = [event for event in events if event.paid_on and event.paid_on.year == today.year]
    today_items = [
        (event.lead.isletme_adi, event.amount, (event.lead.teklif or "").strip())
        for event in today_events
    ]
    return format_revenue_digest_lines(
        today_total=sum(event.amount for event in today_events),
        today_count=len(today_events),
        month_total=sum(event.amount for event in month_events),
        year_total=sum(event.amount for event in year_events),
        today_items=today_items,
    )


def _owner_users(db: Session) -> list[User]:
    return db.query(User).filter(User.role == ROLE_OWNER).all()


def _automation_subject(kind: str) -> str:
    """Konu satırında Türkiye saati açık olsun (Gmail hesabı UTC ise liste saati 3 saat geri görünür)."""
    day = local_today().strftime("%d.%m.%Y")
    clock = local_now().strftime("%H:%M")
    if kind == "morning":
        return f"Sales Hub sabah özeti — {day}, gönderim {clock} (Türkiye saati)"
    return f"Sales Hub gün sonu özeti — {day}, gönderim {clock} (Türkiye saati)"


def _send_time_banner() -> str:
    clock = local_now().strftime("%d.%m.%Y %H:%M")
    return f"Gönderim saati (Türkiye): {clock}\n"


def _optional_ai_paragraph(db: Session, user_id: int) -> str:
    try:
        from ai.capabilities.daily_email_paragraph import build_daily_email_paragraph

        paragraph = build_daily_email_paragraph(db, user_id, requested_by=user_id)
        if not paragraph:
            return ""
        return f"\n\n— AI kısa özet —\n{paragraph}\n"
    except Exception:
        return ""


def build_morning_digest_text(db: Session, user_id: int, include_revenue: bool = True) -> str | None:
    dashboard = build_dashboard(db, user_id)
    lines: list[str] = []

    if include_revenue:
        lines.extend(collect_revenue_digest_lines(db, user_id))

    followups = dashboard.get("cevap_bekleyen_liste") or []
    if followups:
        if lines:
            lines.append("")
        lines.append(f"Cevap bekleyen müşteriler ({dashboard.get('cevap_bekleyen_gun', 3)}+ gün):")
        for item in followups[:10]:
            lines.append(
                f"  • {item['isletme_adi']} — {item['days_waiting']} gün ({item.get('durum', '')})"
            )

    upcoming = dashboard.get("yaklasan_takipler") or []
    soon = [
        item
        for item in upcoming
        if item.get("days_until") is not None
        and 0 <= item["days_until"] <= settings.meeting_reminder_days
    ]
    if soon:
        lines.append("")
        lines.append("Yaklaşan görüşme / demo / takipler:")
        for item in soon[:10]:
            when = "Bugün" if item["days_until"] == 0 else f"{item['days_until']} gün sonra"
            lines.append(
                f"  • {when}: {item['isletme_adi']} — {item.get('type_label', 'Takip')}"
            )

    today_tasks = dashboard.get("bugunku_gorevler_liste") or []
    if today_tasks:
        lines.append("")
        lines.append(f"Bugünkü görevler ({len(today_tasks)}):")
        for item in today_tasks[:8]:
            lines.append(f"  • {item['isletme_adi']} — {item.get('type_label', 'Görev')}")

    if not lines:
        return None

    header = (
        f"BehTech Sales Hub — Sabah özeti ({local_today().strftime('%d.%m.%Y')})\n"
        f"{_send_time_banner()}\n"
    )
    ai_block = _optional_ai_paragraph(db, user_id)
    sent_at = local_now().strftime("%d.%m.%Y %H:%M")
    footer = f"\n\nGönderim: {sent_at} (İstanbul)\nPanel: {settings.app_url}"
    return header + "\n".join(lines) + ai_block + footer


def build_eod_summary_text(db: Session, user_id: int, include_revenue: bool = True) -> str:
    report = build_daily_report(db, user_id, local_today(), include_revenue=include_revenue)
    lines = [
        f"BehTech Sales Hub — Gün sonu özeti ({report['period_label']})",
        _send_time_banner().strip(),
        "",
        f"Yeni kayıt: {report['yeni_kayit']}",
        f"Yeni müşteri: {report['yeni_musteri']}",
    ]
    if report.get("donusum_orani") is not None:
        lines.append(f"Dönüşüm oranı: %{report['donusum_orani']}")

    if include_revenue:
        lines.append("")
        lines.extend(collect_revenue_digest_lines(db, user_id))

    status = report.get("durum_dagilimi") or []
    if status:
        lines.append("")
        lines.append("Durum dağılımı (bugün eklenenler):")
        for row in status[:6]:
            lines.append(f"  • {row['durum']}: {row['count']}")

    dashboard = build_dashboard(db, user_id)
    waiting = dashboard.get("cevap_bekleyen_sayisi", 0)
    if waiting:
        lines.append("")
        lines.append(f"Cevap bekleyen müşteri: {waiting}")

    tomorrow = local_today() + timedelta(days=1)
    tomorrow_items = [
        item
        for item in (dashboard.get("yaklasan_takipler") or [])
        if item.get("days_until") == 1
    ]
    if tomorrow_items:
        lines.append("")
        lines.append("Yarın planlanan:")
        for item in tomorrow_items[:8]:
            lines.append(f"  • {item['isletme_adi']} — {item.get('type_label', 'Takip')}")

    sent_at = local_now().strftime("%d.%m.%Y %H:%M")
    ai_block = _optional_ai_paragraph(db, user_id)
    lines.append(ai_block.rstrip() if ai_block else "")
    lines.append(f"\n\nGönderim: {sent_at} (İstanbul)\nPanel: {settings.app_url}")
    return "\n".join(line for line in lines if line is not None)


def run_morning_digests(db: Session) -> int:
    if not settings.automation_email_enabled or not settings.smtp_configured:
        return 0

    sent = 0
    for user in _owner_users(db):
        include_revenue = (user.account_type or "company") == "company"
        body = build_morning_digest_text(db, user.id, include_revenue=include_revenue)
        if not body:
            continue
        send_automation_email(
            user.email,
            _automation_subject("morning"),
            body,
        )
        sent += 1
    return sent


def run_eod_summaries(db: Session) -> int:
    if not settings.automation_email_enabled or not settings.smtp_configured:
        return 0

    sent = 0
    for user in _owner_users(db):
        include_revenue = (user.account_type or "company") == "company"
        body = build_eod_summary_text(db, user.id, include_revenue=include_revenue)
        send_automation_email(
            user.email,
            _automation_subject("eod"),
            body,
        )
        sent += 1
    return sent
