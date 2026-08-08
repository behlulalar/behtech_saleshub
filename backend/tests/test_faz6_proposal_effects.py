"""Unit tests for proposal approval side effects (no DB)."""

from datetime import date
from unittest.mock import MagicMock

from intelligence.proposal_effects import apply_accept_recommendation_effects


def test_follow_up_sets_takip_1(monkeypatch):
    monkeypatch.setattr("intelligence.proposal_effects.local_today", lambda: date(2026, 8, 8))

    lead = MagicMock()
    lead.user_id = 1
    lead.id = 10
    lead.takip_1 = ""
    lead.takip_2 = ""
    lead.gorusme_tarihi = ""
    lead.durum = "Yeni"

    db = MagicMock()
    summary = apply_accept_recommendation_effects(
        db, 1, lead, action_type="follow_up", actor_user_id=99
    )

    assert lead.takip_1 == "2026-08-08"
    assert "Bugün" in summary
    assert db.add.called
