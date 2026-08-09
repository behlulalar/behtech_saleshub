"""Affected lead cohorts for DE-1 detection and DE-2 priority (shared semantics)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app_timezone import local_today
from dashboard import INACTIVE_STATUSES
from database import Lead
from intelligence.diagnosis.constants import (
    FOLLOWUP_IDLE_DAYS_MEDIUM,
    OFFER_OLD_DAYS_MEDIUM,
    PENDING_OFFER_STATUS,
)
from intelligence.diagnosis.evidence import get_reliable_offer_given_dates
from reminders import get_last_activity_dates, parse_date


@dataclass
class AffectedCandidate:
    lead: Lead
    idle_days: int | None = None
    offer_age_days: int | None = None
    follow_reason: str | None = None  # idle_after_contact | no_contact


def real_contact_date(lead: Lead, activity_dates: dict[int, date]) -> date | None:
    candidates: list[date] = []
    for value in (lead.ilk_mesaj_tarihi, lead.demo_tarihi, lead.gorusme_tarihi):
        parsed = parse_date(value or "")
        if parsed:
            candidates.append(parsed)
    if lead.id in activity_dates:
        candidates.append(activity_dates[lead.id])
    return max(candidates) if candidates else None


def collect_follow_up_affected(
    db: Session,
    org_id: int,
    leads: list[Lead],
    *,
    activity_dates: dict[int, date] | None = None,
    today: date | None = None,
) -> list[AffectedCandidate]:
    today = today or local_today()
    active = [lead for lead in leads if lead.durum not in INACTIVE_STATUSES]
    if not active:
        return []

    lead_ids = [lead.id for lead in active]
    if activity_dates is None:
        activity_dates = get_last_activity_dates(db, org_id, lead_ids)

    out: list[AffectedCandidate] = []
    for lead in active:
        last_contact = real_contact_date(lead, activity_dates)
        if last_contact:
            days_idle = (today - last_contact).days
            if days_idle < FOLLOWUP_IDLE_DAYS_MEDIUM:
                continue
            out.append(
                AffectedCandidate(
                    lead=lead,
                    idle_days=days_idle,
                    follow_reason="idle_after_contact",
                )
            )
            continue

        if not lead.created_at:
            continue
        days_since_created = (today - lead.created_at.date()).days
        if days_since_created < FOLLOWUP_IDLE_DAYS_MEDIUM:
            continue
        out.append(
            AffectedCandidate(
                lead=lead,
                idle_days=days_since_created,
                follow_reason="no_contact",
            )
        )
    return out


def collect_offer_affected_for_priority(
    db: Session,
    org_id: int,
    leads: list[Lead],
    *,
    offer_given_dates: dict[int, date] | None = None,
    today: date | None = None,
) -> list[AffectedCandidate]:
    """Leads in stale-offer cohort (reliable teklif_verildi date, age >= OFFER_OLD_DAYS_MEDIUM)."""
    today = today or local_today()
    pending = [lead for lead in leads if lead.durum in PENDING_OFFER_STATUS]
    if not pending:
        return []

    lead_ids = [lead.id for lead in pending]
    if offer_given_dates is None:
        offer_given_dates = get_reliable_offer_given_dates(db, org_id, lead_ids)

    out: list[AffectedCandidate] = []
    for lead in pending:
        ref = offer_given_dates.get(lead.id)
        if not ref:
            continue
        age_days = (today - ref).days
        if age_days < OFFER_OLD_DAYS_MEDIUM:
            continue
        out.append(AffectedCandidate(lead=lead, offer_age_days=age_days))
    return out
