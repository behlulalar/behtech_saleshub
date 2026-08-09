"""DE-2 — diagnosis priority scoring and enrichment."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from database import Lead
from intelligence.diagnosis.constants import (
    NO_CONTACT_MODIFIER,
    OFFER_AGE_MODIFIER_HIGH,
    PRIORITY_BAND_HIGH,
)
from intelligence.diagnosis.de2_enrich import enrich_diagnosis_de2
from intelligence.diagnosis.models import DiagnosisResult
from intelligence.diagnosis.priority import (
    build_priority_rows,
    lead_specific_modifier,
    priority_band,
)
from intelligence.diagnosis.affected import AffectedCandidate


def _lead(
    lead_id: int,
    durum: str,
    *,
    created: date,
    oncelik: str = "orta",
    ilk_mesaj: str = "",
) -> Lead:
    row = MagicMock(spec=Lead)
    row.id = lead_id
    row.durum = durum
    row.oncelik = oncelik
    row.created_at = datetime.combine(created, datetime.min.time())
    row.ilk_mesaj_tarihi = ilk_mesaj
    row.demo_tarihi = ""
    row.gorusme_tarihi = ""
    row.demo_gonderildi = False
    row.isletme_adi = f"Firma {lead_id}"
    row.yetkili = ""
    return row


def test_lead_specific_modifier_no_contact_only():
    lead = _lead(1, "Yeni", created=date(2026, 8, 1))
    idle = AffectedCandidate(lead=lead, idle_days=12, follow_reason="idle_after_contact")
    no_c = AffectedCandidate(lead=lead, idle_days=12, follow_reason="no_contact")
    assert lead_specific_modifier(idle, "follow_up") == 0
    assert lead_specific_modifier(no_c, "follow_up") == NO_CONTACT_MODIFIER


def test_lead_specific_modifier_offer_tiers_max_one():
    lead = _lead(1, "Teklif Verildi", created=date(2026, 1, 1))
    medium = AffectedCandidate(lead=lead, offer_age_days=8)
    high = AffectedCandidate(lead=lead, offer_age_days=15)
    assert lead_specific_modifier(medium, "offer") == 6
    assert lead_specific_modifier(high, "offer") == OFFER_AGE_MODIFIER_HIGH


def test_diagnosis_severity_not_in_modifier():
    """Org-level severity must not change diagnosis_modifier."""
    lead = _lead(1, "Yeni", created=date(2026, 8, 1))
    c = AffectedCandidate(lead=lead, idle_days=20, follow_reason="idle_after_contact")
    assert lead_specific_modifier(c, "follow_up") == 0


def test_priority_band_matches_rank_leads():
    assert priority_band(70) == "high"
    assert priority_band(69) == "medium"
    assert priority_band(45) == "medium"
    assert priority_band(44) == "low"


def test_build_priority_rows_severity_high_does_not_bump_score(monkeypatch):
    db = MagicMock()
    lead = _lead(1, "İletişime Geçildi", created=date(2026, 7, 1), ilk_mesaj="2026-08-01")
    candidate = AffectedCandidate(lead=lead, idle_days=10, follow_reason="idle_after_contact")

    with patch(
        "intelligence.diagnosis.priority.score_lead",
        return_value=(68, ["x"], "follow_up"),
    ):
        rows = build_priority_rows(
            db,
            1,
            [candidate],
            diagnosis_type="follow_up",
            diagnosis_severity="high",
            activity_dates={},
        )

    assert rows[0]["existing_lead_score"] == 68
    assert rows[0]["diagnosis_modifier"] == 0
    assert rows[0]["diagnosis_priority_score"] == 68
    assert rows[0]["priority"] == "medium"
    assert "diagnosis_high" in rows[0]["reason_codes"]
    assert rows[0]["diagnosis_priority_score"] < PRIORITY_BAND_HIGH


def test_build_priority_rows_offer_age_can_reach_high(monkeypatch):
    db = MagicMock()
    lead = _lead(1, "Teklif Verildi", created=date(2026, 1, 1))
    candidate = AffectedCandidate(lead=lead, offer_age_days=12)

    with patch(
        "intelligence.diagnosis.priority.score_lead",
        return_value=(68, ["x"], "follow_up"),
    ):
        rows = build_priority_rows(
            db,
            1,
            [candidate],
            diagnosis_type="offer",
            diagnosis_severity="high",
            activity_dates={},
        )

    assert rows[0]["diagnosis_modifier"] == OFFER_AGE_MODIFIER_HIGH
    assert rows[0]["diagnosis_priority_score"] == 68 + OFFER_AGE_MODIFIER_HIGH
    assert rows[0]["priority"] == "high"


def test_enrich_funnel_no_priority_leads():
    db = MagicMock()
    item = DiagnosisResult(
        diagnosis_id="funnel_offer_to_won_drop",
        type="funnel_drop",
        severity="high",
        title="t",
        description="d",
        metric="m",
    )
    enrich_diagnosis_de2(db, 1, [], item, activity_dates={}, offer_given_dates={})
    assert item.affected_leads_available is False
    assert item.top_priority_leads == []
    assert item.impact["estimated_pipeline_value"] is None


def test_enrich_follow_up_sets_impact_and_top(monkeypatch):
    db = MagicMock()
    today = date(2026, 8, 10)
    monkeypatch.setattr("intelligence.diagnosis.affected.local_today", lambda: today)
    leads = [
        _lead(1, "Yeni", created=date(2026, 8, 1)),
        _lead(2, "Yeni", created=date(2026, 8, 1)),
    ]
    item = DiagnosisResult(
        diagnosis_id="follow_up_idle_leads",
        type="follow_up",
        severity="medium",
        title="t",
        description="d",
        metric="days_since_last_contact",
        affected_lead_count=2,
    )

    with patch(
        "intelligence.diagnosis.de2_enrich.build_priority_rows",
        return_value=[
            {
                "lead_id": 2,
                "lead_name": "Firma 2",
                "durum": "Yeni",
                "existing_lead_score": 50,
                "diagnosis_modifier": NO_CONTACT_MODIFIER,
                "diagnosis_priority_score": 58,
                "priority": "medium",
                "reason_codes": ["no_contact"],
                "idle_days": 9,
                "offer_age_days": None,
            },
            {
                "lead_id": 1,
                "lead_name": "Firma 1",
                "durum": "Yeni",
                "existing_lead_score": 40,
                "diagnosis_modifier": 0,
                "diagnosis_priority_score": 40,
                "priority": "low",
                "reason_codes": [],
                "idle_days": 9,
                "offer_age_days": None,
            },
        ],
    ):
        enrich_diagnosis_de2(db, 1, leads, item, activity_dates={}, offer_given_dates={})

    assert item.affected_leads_available is True
    assert item.impact["high_priority_count"] == 0
    assert item.impact["medium_priority_count"] == 1
    assert len(item.top_priority_leads) == 2
