"""Deterministic diagnosis detectors (DE-1)."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app_timezone import local_now, local_today
from dashboard import INACTIVE_STATUSES
from database import Lead
from intelligence.diagnosis.constants import (
    FOLLOWUP_IDLE_DAYS_HIGH,
    FOLLOWUP_IDLE_DAYS_MEDIUM,
    FOLLOWUP_MIN_AFFECTED_LEADS,
    FUNNEL_MIN_ABSOLUTE_DROP_POINTS,
    FUNNEL_MIN_RELATIVE_DROP_PERCENT,
    FUNNEL_MIN_STAGE_DENOMINATOR,
    FUNNEL_TRANSITIONS,
    OFFER_MIN_PENDING_WITH_AGE,
    OFFER_OLD_DAYS_HIGH,
    OFFER_OLD_DAYS_MEDIUM,
    PENDING_OFFER_STATUS,
)
from intelligence.diagnosis.evidence import (
    cohort_leads_in_range,
    comparison_period_bounds,
    funnel_transition_rate,
    get_reliable_offer_given_dates,
    period_label,
)
from intelligence.diagnosis.models import DiagnosisResult
from reminders import get_last_activity_dates, parse_date


def _relative_change_percent(current: float, previous: float) -> float | None:
    if previous <= 0:
        return None
    return round(((current - previous) / previous) * 100, 1)


def _funnel_severity(relative_drop: float, absolute_drop: float) -> str:
    if relative_drop <= -40 or absolute_drop >= 15:
        return "high"
    if relative_drop <= -25 or absolute_drop >= 8:
        return "medium"
    return "low"


def detect_funnel_drops(
    leads: list[Lead],
    *,
    period_type: str,
    anchor: date,
) -> list[DiagnosisResult]:
    cur_start, cur_end, prev_start, prev_end = comparison_period_bounds(period_type, anchor)
    cur_cohort = cohort_leads_in_range(leads, cur_start, cur_end)
    prev_cohort = cohort_leads_in_range(leads, prev_start, prev_end)
    detected_at = local_now().isoformat()
    items: list[DiagnosisResult] = []

    for from_stage, to_stage, metric, diag_suffix in FUNNEL_TRANSITIONS:
        cur_rate, cur_from, cur_to = funnel_transition_rate(cur_cohort, from_stage, to_stage)
        prev_rate, prev_from, prev_to = funnel_transition_rate(prev_cohort, from_stage, to_stage)

        if cur_rate is None or prev_rate is None:
            continue
        if prev_from < FUNNEL_MIN_STAGE_DENOMINATOR or cur_from < FUNNEL_MIN_STAGE_DENOMINATOR:
            continue
        if cur_rate >= prev_rate:
            continue

        absolute_drop = prev_rate - cur_rate
        relative_drop = _relative_change_percent(cur_rate, prev_rate)
        if relative_drop is None:
            continue
        if relative_drop > -FUNNEL_MIN_RELATIVE_DROP_PERCENT:
            continue
        if absolute_drop < FUNNEL_MIN_ABSOLUTE_DROP_POINTS:
            continue

        change_percent = relative_drop
        severity = _funnel_severity(relative_drop, absolute_drop)
        items.append(
            DiagnosisResult(
                diagnosis_id=diag_suffix,
                type="funnel_drop",
                severity=severity,
                title=_funnel_title(from_stage, to_stage),
                description=_funnel_description(from_stage, to_stage, prev_rate, cur_rate),
                metric=metric,
                current_value=cur_rate,
                previous_value=prev_rate,
                change_percent=change_percent,
                evidence={
                    "from_stage": from_stage,
                    "to_stage": to_stage,
                    "current": cur_rate,
                    "previous": prev_rate,
                    "delta": round(cur_rate - prev_rate, 1),
                    "delta_percent": change_percent,
                    "sample_current_from": cur_from,
                    "sample_current_to": cur_to,
                    "sample_previous_from": prev_from,
                    "sample_previous_to": prev_to,
                    "current_period": period_label(period_type, cur_start, cur_end),
                    "previous_period": period_label(period_type, prev_start, prev_end),
                },
                affected_lead_count=cur_to,
                detected_at=detected_at,
            )
        )

    return items


def _funnel_title(from_stage: str, to_stage: str) -> str:
    labels = {"demo": "Demo", "teklif": "Teklif", "satis": "Satış"}
    return f"{labels.get(from_stage, from_stage)} → {labels.get(to_stage, to_stage)} dönüşümü düştü"


def _funnel_description(from_stage: str, to_stage: str, prev: float, cur: float) -> str:
    return (
        f"Önceki döneme göre {from_stage} → {to_stage} dönüşüm oranı "
        f"%{prev} seviyesinden %{cur} seviyesine geriledi."
    )


def _real_contact_date(lead: Lead, activity_dates: dict[int, date]) -> date | None:
    """Gerçek iletişim; created_at fallback yok (no-contact ayrımı için)."""
    candidates: list[date] = []
    for value in (lead.ilk_mesaj_tarihi, lead.demo_tarihi, lead.gorusme_tarihi):
        parsed = parse_date(value or "")
        if parsed:
            candidates.append(parsed)
    if lead.id in activity_dates:
        candidates.append(activity_dates[lead.id])
    return max(candidates) if candidates else None


def detect_follow_up_problems(db: Session, org_id: int, leads: list[Lead]) -> list[DiagnosisResult]:
    today = local_today()
    active = [lead for lead in leads if lead.durum not in INACTIVE_STATUSES]
    if not active:
        return []

    lead_ids = [lead.id for lead in active]
    activity_dates = get_last_activity_dates(db, org_id, lead_ids)

    idle_contact: list[dict] = []
    no_contact: list[dict] = []
    for lead in active:
        last_contact = _real_contact_date(lead, activity_dates)
        if last_contact:
            days_idle = (today - last_contact).days
            if days_idle < FOLLOWUP_IDLE_DAYS_MEDIUM:
                continue
            idle_contact.append(
                {
                    "lead_id": lead.id,
                    "days_idle": days_idle,
                    "durum": lead.durum,
                    "reason": "idle_after_contact",
                }
            )
            continue

        if not lead.created_at:
            continue
        days_since_created = (today - lead.created_at.date()).days
        if days_since_created < FOLLOWUP_IDLE_DAYS_MEDIUM:
            continue
        no_contact.append(
            {
                "lead_id": lead.id,
                "days_idle": days_since_created,
                "durum": lead.durum,
                "reason": "no_contact",
            }
        )

    idle = idle_contact + no_contact
    if len(idle) < FOLLOWUP_MIN_AFFECTED_LEADS:
        return []

    days_list = [row["days_idle"] for row in idle]
    max_idle = max(days_list)
    avg_idle = round(sum(days_list) / len(days_list), 1)
    oldest = max(idle, key=lambda r: r["days_idle"])

    if max_idle >= FOLLOWUP_IDLE_DAYS_HIGH:
        severity = "high"
    elif max_idle >= FOLLOWUP_IDLE_DAYS_MEDIUM:
        severity = "medium"
    else:
        return []

    detected_at = local_now().isoformat()
    no_contact_count = len(no_contact)
    idle_contact_count = len(idle_contact)
    desc_parts = []
    if idle_contact_count:
        desc_parts.append(f"{idle_contact_count} lead'de son temas {FOLLOWUP_IDLE_DAYS_MEDIUM}+ gün önce")
    if no_contact_count:
        desc_parts.append(f"{no_contact_count} lead'de hiç gerçek temas yok ({FOLLOWUP_IDLE_DAYS_MEDIUM}+ gün)")
    description = "; ".join(desc_parts) + f"; en uzun süre {max_idle} gün."

    return [
        DiagnosisResult(
            diagnosis_id="follow_up_idle_leads",
            type="follow_up",
            severity=severity,
            title="Takip gerektiren aktif lead'ler",
            description=description,
            metric="days_since_last_contact",
            current_value=float(max_idle),
            previous_value=None,
            change_percent=None,
            evidence={
                "affected_lead_count": len(idle),
                "idle_contact_count": idle_contact_count,
                "no_contact_count": no_contact_count,
                "oldest_days_idle": max_idle,
                "average_days_idle": avg_idle,
                "threshold_medium_days": FOLLOWUP_IDLE_DAYS_MEDIUM,
                "threshold_high_days": FOLLOWUP_IDLE_DAYS_HIGH,
                "sample_lead_ids": [r["lead_id"] for r in sorted(idle, key=lambda x: -x["days_idle"])[:10]],
                "worst_case": {
                    "lead_id": oldest["lead_id"],
                    "days_idle": oldest["days_idle"],
                    "reason": oldest.get("reason"),
                },
            },
            affected_lead_count=len(idle),
            detected_at=detected_at,
        )
    ]


def _offer_reference_date(lead: Lead, offer_given_dates: dict[int, date]) -> date | None:
    """Yalnızca ``teklif_verildi`` aktivitesinden gelen güvenilir teklif tarihi."""
    if lead.durum not in PENDING_OFFER_STATUS:
        return None
    return offer_given_dates.get(lead.id)


def detect_offer_problems(db: Session, org_id: int, leads: list[Lead]) -> list[DiagnosisResult]:
    today = local_today()
    pending = [lead for lead in leads if lead.durum in PENDING_OFFER_STATUS]
    if not pending:
        return []

    lead_ids = [lead.id for lead in pending]
    offer_given_dates = get_reliable_offer_given_dates(db, org_id, lead_ids)

    aged: list[dict] = []
    for lead in pending:
        ref = _offer_reference_date(lead, offer_given_dates)
        if not ref:
            continue
        age_days = (today - ref).days
        aged.append({"lead_id": lead.id, "age_days": age_days})

    if len(aged) < OFFER_MIN_PENDING_WITH_AGE:
        return []

    old_medium = [r for r in aged if r["age_days"] >= OFFER_OLD_DAYS_MEDIUM]
    old_high = [r for r in aged if r["age_days"] >= OFFER_OLD_DAYS_HIGH]
    if not old_medium:
        return []

    ages = [r["age_days"] for r in aged]
    avg_age = round(sum(ages) / len(ages), 1)
    max_age = max(ages)

    if max_age >= OFFER_OLD_DAYS_HIGH or len(old_high) >= 1:
        severity = "high"
    else:
        severity = "medium"

    detected_at = local_now().isoformat()
    return [
        DiagnosisResult(
            diagnosis_id="offer_pending_stale",
            type="offer",
            severity=severity,
            title="Bekleyen teklifler uzadı",
            description=(
                f"{len(pending)} teklif aşamasındaki lead'den {len(old_medium)} tanesi "
                f"{OFFER_OLD_DAYS_MEDIUM}+ gündür sonuçlanmadı."
            ),
            metric="pending_offer_age_days",
            current_value=float(max_age),
            previous_value=None,
            change_percent=None,
            evidence={
                "pending_offer_count": len(pending),
                "pending_with_reliable_age": len(aged),
                "count_age_gte_medium": len(old_medium),
                "count_age_gte_high": len(old_high),
                "average_offer_age_days": avg_age,
                "max_offer_age_days": max_age,
                "threshold_medium_days": OFFER_OLD_DAYS_MEDIUM,
                "threshold_high_days": OFFER_OLD_DAYS_HIGH,
                "sample_lead_ids": [r["lead_id"] for r in sorted(aged, key=lambda x: -x["age_days"])[:10]],
            },
            affected_lead_count=len(old_medium),
            detected_at=detected_at,
        )
    ]
