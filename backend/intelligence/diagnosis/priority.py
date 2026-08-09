"""DE-2 diagnosis priority scoring (lead-specific modifiers only; no severity in score)."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from intelligence.diagnosis.affected import AffectedCandidate
from intelligence.diagnosis.constants import (
    DE2_TOP_LEADS_LIMIT,
    FOLLOWUP_IDLE_DAYS_HIGH,
    FOLLOWUP_IDLE_DAYS_MEDIUM,
    NO_CONTACT_MODIFIER,
    OFFER_AGE_MODIFIER_HIGH,
    OFFER_AGE_MODIFIER_MEDIUM,
    OFFER_OLD_DAYS_HIGH,
    OFFER_OLD_DAYS_MEDIUM,
    PRIORITY_BAND_HIGH,
    PRIORITY_BAND_MEDIUM,
)
from intelligence.scoring import score_lead


def lead_specific_modifier(candidate: AffectedCandidate, diagnosis_type: str) -> int:
    if diagnosis_type == "follow_up":
        if candidate.follow_reason == "no_contact":
            return NO_CONTACT_MODIFIER
        return 0
    if diagnosis_type == "offer":
        age = candidate.offer_age_days
        if age is None:
            return 0
        if age >= OFFER_OLD_DAYS_HIGH:
            return OFFER_AGE_MODIFIER_HIGH
        if age >= OFFER_OLD_DAYS_MEDIUM:
            return OFFER_AGE_MODIFIER_MEDIUM
        return 0
    return 0


def clamp_score(value: int) -> int:
    return max(0, min(100, value))


def priority_band(score: int) -> str:
    if score >= PRIORITY_BAND_HIGH:
        return "high"
    if score >= PRIORITY_BAND_MEDIUM:
        return "medium"
    return "low"


def build_reason_codes(
    *,
    existing_lead_score: int,
    diagnosis_severity: str,
    candidate: AffectedCandidate,
    diagnosis_type: str,
) -> list[str]:
    codes: list[str] = []
    if diagnosis_severity == "high":
        codes.append("diagnosis_high")
    elif diagnosis_severity == "medium":
        codes.append("diagnosis_medium")
    elif diagnosis_severity == "low":
        codes.append("diagnosis_low")

    if existing_lead_score >= PRIORITY_BAND_HIGH:
        codes.append("high_lead_score")
    elif existing_lead_score >= PRIORITY_BAND_MEDIUM:
        codes.append("medium_lead_score")
    else:
        codes.append("low_lead_score")

    if diagnosis_type == "follow_up":
        if candidate.follow_reason == "no_contact":
            codes.append("no_contact")
        if candidate.idle_days is not None:
            if candidate.idle_days >= FOLLOWUP_IDLE_DAYS_HIGH:
                codes.append("very_long_idle")
            elif candidate.idle_days >= FOLLOWUP_IDLE_DAYS_MEDIUM:
                codes.append("long_idle")

    if diagnosis_type == "offer" and candidate.offer_age_days is not None:
        if candidate.offer_age_days >= OFFER_OLD_DAYS_HIGH:
            codes.append("very_old_offer")
        elif candidate.offer_age_days >= OFFER_OLD_DAYS_MEDIUM:
            codes.append("old_offer")

    return codes


def build_priority_rows(
    db: Session,
    org_id: int,
    candidates: list[AffectedCandidate],
    *,
    diagnosis_type: str,
    diagnosis_severity: str,
    activity_dates: dict[int, date] | None = None,
) -> list[dict]:
    rows: list[dict] = []
    for candidate in candidates:
        lead = candidate.lead
        existing, _reasons, _action = score_lead(
            db,
            org_id,
            lead,
            activity_dates=activity_dates or {},
        )
        modifier = lead_specific_modifier(candidate, diagnosis_type)
        priority_score = clamp_score(existing + modifier)
        rows.append(
            {
                "lead_id": lead.id,
                "lead_name": lead.isletme_adi or lead.yetkili or f"Lead #{lead.id}",
                "durum": lead.durum,
                "existing_lead_score": existing,
                "diagnosis_modifier": modifier,
                "diagnosis_priority_score": priority_score,
                "priority": priority_band(priority_score),
                "reason_codes": build_reason_codes(
                    existing_lead_score=existing,
                    diagnosis_severity=diagnosis_severity,
                    candidate=candidate,
                    diagnosis_type=diagnosis_type,
                ),
                "idle_days": candidate.idle_days,
                "offer_age_days": candidate.offer_age_days,
            }
        )

    rows.sort(
        key=lambda r: (
            -r["diagnosis_priority_score"],
            -r["existing_lead_score"],
            r["lead_id"],
        )
    )
    return rows


def top_priority_leads(rows: list[dict]) -> list[dict]:
    return rows[:DE2_TOP_LEADS_LIMIT]
